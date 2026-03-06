"""Planting schedule optimizer for irrigation demand smoothing.

Optimizes crop planting dates and field area splits to smooth daily
irrigation demand across the year. Preserves crop types and total area
per field while varying planting dates and allowing fields to be split
into sub-fields with different schedules.

Two objectives are supported:
    minimize_variance — flatten the demand curve (lowest peak-to-average)
    match_supply — align demand shape with available renewable energy

Usage:
    from src.planting_optimizer import optimize_planting_schedule, save_optimized_profile

    result = optimize_planting_schedule(
        farm_profiles_path='settings/farm_profile_base.yaml',
        registry_path='settings/data_registry_base.yaml',
        objective='minimize_variance',
    )
    save_optimized_profile(result['farm_config'], 'settings/farm_profile_optimized.yaml')
"""

from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta
from itertools import combinations, product
from pathlib import Path

import warnings

import numpy as np
import pandas as pd
import yaml
from scipy.optimize import minimize as scipy_minimize

from src.farm_profile import planting_code_to_mmdd


# ---------------------------------------------------------------------------
# Internal helpers — loading
# ---------------------------------------------------------------------------

_MM_TO_ABBREV = {
    '01': 'jan', '02': 'feb', '03': 'mar', '04': 'apr',
    '05': 'may', '06': 'jun', '07': 'jul', '08': 'aug',
    '09': 'sep', '10': 'oct', '11': 'nov', '12': 'dec',
}


def _load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


def _load_planting_windows(registry, root_dir):
    """Load planting windows CSV.

    Returns:
        available: dict mapping crop -> list of planting codes
        season_lengths: dict mapping (crop, mmdd) -> season_length_days
    """
    path = root_dir / registry['crops']['planting_windows']
    df = pd.read_csv(path, comment='#')

    available = {}
    season_lengths = {}
    for _, row in df.iterrows():
        crop = row['crop']
        mmdd = row['planting_date_mmdd']
        season_lengths[(crop, mmdd)] = int(row['expected_season_length_days'])
        mm, dd = mmdd.split('-')
        code = _MM_TO_ABBREV[mm] + dd
        available.setdefault(crop, []).append(code)

    return available, season_lengths


def _load_irrigation_efficiency(registry, root_dir):
    """Load irrigation system efficiency lookup."""
    path = root_dir / registry['water_supply']['irrigation_systems']
    df = pd.read_csv(path, comment='#')
    lookup = {}
    for _, row in df.iterrows():
        name = row['irrigation_type']
        lookup[name] = row['efficiency']
        lookup[name.replace('_irrigation', '')] = row['efficiency']
    return lookup


def _load_irrigation_curve(growth_dir, crop, planting, condition, irrigation_policy):
    """Load daily irrigation mm for one (crop, planting, condition) triple."""
    path = growth_dir / crop / f"{crop}_{planting}_{condition}-research.csv"
    df = pd.read_csv(path, comment='#', parse_dates=['date'])
    df = df[df['irrigation_policy'] == irrigation_policy]
    return df[['date', 'irrigation_mm']].copy()


def _resolve_irrigation_policy(water_policy_path):
    """Resolve irrigation policy string from water policy config."""
    config = _load_yaml(water_policy_path)
    mode = config['irrigation']['mode']
    if mode == 'static':
        return config['irrigation']['static_policy']
    return 'full_eto'


# ---------------------------------------------------------------------------
# Internal helpers — schedule enumeration
# ---------------------------------------------------------------------------

def _seasons_overlap(schedule, season_lengths):
    """Check if any plantings in a schedule have overlapping growing seasons."""
    ref_years = [2020, 2021]
    intervals = []
    for crop, code in schedule:
        mmdd = planting_code_to_mmdd(code)
        length = season_lengths[(crop, mmdd)]
        for y in ref_years:
            start = datetime.strptime(f"{y}-{mmdd}", "%Y-%m-%d")
            end = start + timedelta(days=length)
            intervals.append((start, end, crop, code))

    for i, (s1, e1, c1, p1) in enumerate(intervals):
        for s2, e2, c2, p2 in intervals[i + 1:]:
            if c1 == c2 and p1 == p2:
                continue
            if s1 < e2 and s2 < e1:
                return True
    return False


def _enumerate_field_schedules(field, available_plantings, season_lengths):
    """Enumerate all valid non-overlapping planting schedules for a field.

    Preserves the number of plantings per crop. For each crop with N
    plantings in the original profile, picks N dates from available
    options. Returns only combinations with no temporal overlap.
    """
    crop_counts = {}
    for p in field.get('plantings', []):
        crop = p['crop']
        n = len(p['plantings'])
        crop_counts[crop] = crop_counts.get(crop, 0) + n

    if not crop_counts:
        return []

    crop_options = []
    for crop, n_needed in crop_counts.items():
        codes = available_plantings.get(crop, [])
        if len(codes) < n_needed:
            return []
        combos = list(combinations(codes, n_needed))
        crop_options.append([(crop, combo) for combo in combos])

    valid = []
    for combo in product(*crop_options):
        schedule = []
        for crop, dates in combo:
            for d in dates:
                schedule.append((crop, d))
        if not _seasons_overlap(schedule, season_lengths):
            valid.append(schedule)

    return valid


# ---------------------------------------------------------------------------
# Internal helpers — basis matrix
# ---------------------------------------------------------------------------

def _preload_curves(growth_dir, fields, available_plantings, irrigation_policy):
    """Pre-load all irrigation curves into a cache.

    Returns dict mapping (crop, planting_code, condition) -> Series indexed by date.
    """
    cache = {}
    for field in fields:
        condition = field['condition']
        crops = {p['crop'] for p in field.get('plantings', [])}
        for crop in crops:
            for code in available_plantings.get(crop, []):
                key = (crop, code, condition)
                if key not in cache:
                    df = _load_irrigation_curve(
                        growth_dir, crop, code, condition, irrigation_policy
                    )
                    cache[key] = df.set_index('date')['irrigation_mm']
    return cache


def _build_date_index(curves_cache):
    """Build a complete daily date index spanning all curves."""
    sample = next(iter(curves_cache.values()))
    year_min = sample.index.min().year
    year_max = sample.index.max().year
    return pd.date_range(
        start=pd.Timestamp(year=year_min, month=1, day=1),
        end=pd.Timestamp(year=year_max, month=12, day=31),
        freq='D',
    )


def _schedule_basis_vector(schedule, condition, efficiency, curves_cache, date_index):
    """Compute basis vector (m3/ha/day) for one schedule.

    Sums irrigation curves for all (crop, planting) in the schedule,
    converts mm to m3/ha: m3_per_ha = mm * 10 / efficiency.
    """
    total = pd.Series(0.0, index=date_index)
    for crop, code in schedule:
        curve = curves_cache.get((crop, code, condition))
        if curve is not None:
            total = total.add(curve, fill_value=0.0)
    result = (total.reindex(date_index).fillna(0.0) * 10 / efficiency).values
    result = np.nan_to_num(result, nan=0.0, posinf=0.0, neginf=0.0)
    return result


def _build_optimization_problem(fields_with_schedules, curves_cache, date_index,
                                irrig_lookup):
    """Build the basis matrix and constraint structures.

    Returns:
        B: basis matrix shape (n_days, n_vars)
        field_groups: list of (field_name, area_ha, var_indices)
        schedule_labels: list of (field_dict, schedule) per variable
    """
    basis_cols = []
    field_groups = []
    schedule_labels = []

    var_idx = 0
    for field, schedules in fields_with_schedules:
        condition = field['condition']
        efficiency = irrig_lookup[field['irrigation_system']]
        area = field['area_ha']
        indices = list(range(var_idx, var_idx + len(schedules)))

        for sched in schedules:
            bv = _schedule_basis_vector(
                sched, condition, efficiency, curves_cache, date_index
            )
            basis_cols.append(bv)
            schedule_labels.append((field, sched))

        field_groups.append((field['name'], area, indices))
        var_idx += len(schedules)

    if basis_cols:
        B = np.column_stack(basis_cols)
    else:
        B = np.empty((len(date_index), 0))
    return B, field_groups, schedule_labels


# ---------------------------------------------------------------------------
# Internal helpers — solvers
# ---------------------------------------------------------------------------

def _equal_split_x0(field_groups, n_vars):
    """Initial guess: equal area split across schedules per field."""
    x0 = np.zeros(n_vars)
    for _, area, indices in field_groups:
        n = len(indices)
        for i in indices:
            x0[i] = area / n
    return x0


def _build_constraints(field_groups, min_planted_pct=1.0):
    """Build SLSQP constraints for per-field area totals.

    When min_planted_pct is 1.0, uses equality constraints (areas sum to
    original). When < 1.0, uses inequality constraints allowing the
    optimizer to reduce planted area down to min_planted_pct of original.
    """
    constraints = []
    if min_planted_pct >= 1.0:
        for _, area, indices in field_groups:
            constraints.append({
                'type': 'eq',
                'fun': lambda x, idx=indices, a=area: sum(x[i] for i in idx) - a,
            })
    else:
        for _, area, indices in field_groups:
            constraints.append({
                'type': 'ineq',
                'fun': lambda x, idx=indices, a=area, p=min_planted_pct: (
                    sum(x[i] for i in idx) - a * p),
            })
            constraints.append({
                'type': 'ineq',
                'fun': lambda x, idx=indices, a=area: (
                    a - sum(x[i] for i in idx)),
            })
    return constraints


def _solve_minimize_variance(B, field_groups, min_planted_pct=1.0):
    """Minimize variance of total daily irrigation demand.

    var(B @ x) = mean((B @ x)^2) - mean(B @ x)^2. Both terms are
    quadratic in x, making this a smooth QP solvable with SLSQP.
    """
    n_days, n_vars = B.shape
    if n_vars == 0:
        return np.array([])

    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)

        BtB = B.T @ B / n_days
        Bt_ones = B.mean(axis=0)

        def objective(x):
            return np.var(B @ x)

        def gradient(x):
            Bx = B @ x
            return 2 * (BtB @ x - np.mean(Bx) * Bt_ones)

        x0 = _equal_split_x0(field_groups, n_vars)
        result = scipy_minimize(
            objective, x0, jac=gradient, method='SLSQP',
            bounds=[(0, None)] * n_vars,
            constraints=_build_constraints(field_groups, min_planted_pct),
            options={'maxiter': 1000, 'ftol': 1e-12},
        )
    return result.x


def _solve_match_supply(B, field_groups, target, min_planted_pct=1.0):
    """Minimize squared difference between demand shape and scaled target.

    Target is rescaled so its mean matches initial demand mean, then
    minimizes ||B @ x - target_scaled||^2 (convex QP).
    """
    n_days, n_vars = B.shape
    if n_vars == 0:
        return np.array([])

    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)

        x0 = _equal_split_x0(field_groups, n_vars)
        initial_mean = np.mean(B @ x0)
        target_mean = np.mean(target)

        if target_mean > 0:
            scaled_target = target * (initial_mean / target_mean)
        else:
            scaled_target = np.full(n_days, initial_mean)

        BtB = B.T @ B
        Btt = B.T @ scaled_target

        def objective(x):
            diff = B @ x - scaled_target
            return np.sum(diff ** 2)

        def gradient(x):
            return 2 * (BtB @ x - Btt)

        result = scipy_minimize(
            objective, x0, jac=gradient, method='SLSQP',
            bounds=[(0, None)] * n_vars,
            constraints=_build_constraints(field_groups, min_planted_pct),
            options={'maxiter': 1000, 'ftol': 1e-12},
        )
    return result.x, scaled_target


# ---------------------------------------------------------------------------
# Internal helpers — profile reconstruction
# ---------------------------------------------------------------------------

def _schedule_to_plantings(schedule):
    """Convert [(crop, code), ...] to YAML-style plantings list."""
    crops = OrderedDict()
    for crop, code in schedule:
        crops.setdefault(crop, []).append(code)
    return [{'crop': crop, 'plantings': codes} for crop, codes in crops.items()]


def _build_optimized_profile(original_config, schedule_labels, x, min_area_ha):
    """Reconstruct farm profile from optimization results.

    Groups sub-fields under their original farm. Filters allocations
    below min_area_ha and redistributes lost area to the largest
    sub-field for each original field.
    """
    # Collect allocations per original field
    field_allocs = defaultdict(list)
    for (field, schedule), area in zip(schedule_labels, x):
        if area >= min_area_ha:
            field_allocs[field['name']].append({
                'field': field,
                'schedule': schedule,
                'area_ha': area,
            })

    # Compute target area per field: sum of optimizer allocations (including
    # those below min_area_ha that were filtered out), capped at original
    original_areas = {}
    allocated_areas = defaultdict(float)
    for (field, _), area in zip(schedule_labels, x):
        original_areas[field['name']] = field['area_ha']
        allocated_areas[field['name']] += float(area)

    # Redistribute area lost to min_area_ha filtering back to largest sub-field
    for field_name, allocs in field_allocs.items():
        total_kept = sum(a['area_ha'] for a in allocs)
        target = min(allocated_areas[field_name], original_areas[field_name])
        lost = target - total_kept
        if lost > 0.01 and allocs:
            largest = max(allocs, key=lambda a: a['area_ha'])
            largest['area_ha'] += lost

    # Round areas, then correct the largest sub-field so the total matches
    for field_name, allocs in field_allocs.items():
        for a in allocs:
            a['area_ha'] = round(float(a['area_ha']), 2)
        target = round(min(allocated_areas[field_name], original_areas[field_name]), 2)
        rounded_total = sum(a['area_ha'] for a in allocs)
        residual = round(target - rounded_total, 2)
        if abs(residual) > 0 and allocs:
            largest = max(allocs, key=lambda a: a['area_ha'])
            largest['area_ha'] = round(largest['area_ha'] + residual, 2)

    # Map field -> farm
    field_to_farm = {}
    for farm in original_config['farms']:
        for field in farm['fields']:
            field_to_farm[field['name']] = farm['name']

    # Build new farm structures
    new_farms = OrderedDict()
    for farm in original_config['farms']:
        new_farms[farm['name']] = {'name': farm['name'], 'fields': []}

    for field_name, allocs in field_allocs.items():
        farm_name = field_to_farm[field_name]
        orig_field = allocs[0]['field']

        if len(allocs) == 1:
            new_farms[farm_name]['fields'].append({
                'name': field_name,
                'area_ha': allocs[0]['area_ha'],
                'water_system': orig_field['water_system'],
                'irrigation_system': orig_field['irrigation_system'],
                'condition': orig_field['condition'],
                'plantings': _schedule_to_plantings(allocs[0]['schedule']),
            })
        else:
            for i, alloc in enumerate(allocs, 1):
                new_farms[farm_name]['fields'].append({
                    'name': f"{field_name}_s{i}",
                    'area_ha': alloc['area_ha'],
                    'water_system': orig_field['water_system'],
                    'irrigation_system': orig_field['irrigation_system'],
                    'condition': orig_field['condition'],
                    'plantings': _schedule_to_plantings(alloc['schedule']),
                })

    # Preserve fields that had no optimization variables (e.g. no valid
    # schedule alternatives found). These were never in schedule_labels
    # so would otherwise be silently dropped from the output.
    optimized_field_names = set(field_allocs.keys())
    for farm in original_config['farms']:
        for field in farm['fields']:
            if field['name'] not in optimized_field_names:
                new_farms[farm['name']]['fields'].append(dict(field))

    config_name = original_config.get('config_name', 'farm_collective') + '_optimized'
    return {'config_name': config_name, 'farms': list(new_farms.values())}


# ---------------------------------------------------------------------------
# Internal helpers — metrics
# ---------------------------------------------------------------------------

def _demand_metrics(demand):
    """Compute summary metrics for a daily irrigation demand array."""
    active = demand[demand > 0]
    mean_all = float(np.mean(demand))
    return {
        'mean_m3': mean_all,
        'std_m3': float(np.std(demand)),
        'cv': float(np.std(demand) / mean_all) if mean_all > 0 else 0.0,
        'peak_m3': float(np.max(demand)),
        'active_days': int(len(active)),
        'peak_to_mean_active': (
            float(np.max(demand) / np.mean(active)) if len(active) > 0 else 0.0
        ),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def optimize_planting_schedule(farm_profiles_path, registry_path, *,
                               energy_config_path=None,
                               community_config_path=None,
                               objective='minimize_variance',
                               water_policy_path=None,
                               min_area_ha=0.1,
                               min_planted_pct=1.0,
                               n_years=None,
                               root_dir=None):
    """Optimize planting dates and field splits to smooth irrigation demand.

    Preserves crop types and total field areas. Varies planting dates
    and splits fields into sub-fields to reduce demand variability
    or match demand shape to energy supply.

    Args:
        farm_profiles_path: Path to farm_profile.yaml.
        registry_path: Path to data_registry.yaml.
        energy_config_path: Path to energy_system.yaml (for match_supply).
        community_config_path: Path to community_demands.yaml (for match_supply).
        objective: 'minimize_variance' or 'match_supply'.
        water_policy_path: Path to water_policy.yaml.
        min_area_ha: Minimum sub-field area; smaller allocations are pruned.
        min_planted_pct: Minimum planted area as fraction of original total
            per field (0.0-1.0). At 1.0, all area must be planted. Lower
            values let the optimizer reduce planted area to balance demand
            against energy supply.
        n_years: Number of years to optimize over, starting from the first
            year in the data. None uses all available years.
        root_dir: Repository root. Defaults to parent of settings/.

    Returns:
        Dict with keys:
            farm_config: optimized farm profile dict (YAML-ready)
            summary: dict with before/after metrics and schedule counts
            demand_before: Series of daily demand (m3) before optimization
            demand_after: Series of daily demand (m3) after optimization
            date_index: DatetimeIndex for the demand series
            target: scaled target Series (match_supply only), else None
    """
    farm_profiles_path = Path(farm_profiles_path)
    registry_path = Path(registry_path)
    if root_dir is None:
        root_dir = registry_path.parent.parent

    farm_config = _load_yaml(farm_profiles_path)
    registry = _load_yaml(registry_path)
    available, season_lengths = _load_planting_windows(registry, root_dir)
    irrig_lookup = _load_irrigation_efficiency(registry, root_dir)

    irrigation_policy = 'full_eto'
    if water_policy_path is not None:
        irrigation_policy = _resolve_irrigation_policy(water_policy_path)

    # Collect all fields and enumerate valid schedules
    all_fields = [
        field
        for farm in farm_config['farms']
        for field in farm['fields']
    ]

    fields_with_schedules = []
    for field in all_fields:
        schedules = _enumerate_field_schedules(field, available, season_lengths)
        if schedules:
            fields_with_schedules.append((field, schedules))

    # Pre-load curves and build basis matrix
    growth_dir = root_dir / registry['crops']['daily_growth_dir']
    curves_cache = _preload_curves(growth_dir, all_fields, available, irrigation_policy)
    date_index = _build_date_index(curves_cache)

    if n_years is not None:
        cutoff = pd.Timestamp(year=date_index[0].year + n_years, month=1, day=1)
        date_index = date_index[date_index < cutoff]

    B, field_groups, schedule_labels = _build_optimization_problem(
        fields_with_schedules, curves_cache, date_index, irrig_lookup
    )

    # Compute original demand via the existing pipeline
    from src.irrigation_demand import compute_irrigation_demand
    before_df = compute_irrigation_demand(
        farm_profiles_path=farm_profiles_path,
        registry_path=registry_path,
        water_policy_path=water_policy_path,
        root_dir=root_dir,
    )
    demand_before = (
        before_df.set_index('day')['total_demand_m3']
        .reindex(date_index, fill_value=0.0)
        .values
    )

    # Solve optimization
    target = None
    scaled_target = None
    if objective == 'minimize_variance':
        x_opt = _solve_minimize_variance(B, field_groups, min_planted_pct)
    elif objective == 'match_supply':
        if energy_config_path is None or community_config_path is None:
            raise ValueError(
                "energy_config_path and community_config_path required for match_supply"
            )
        from src.energy_supply import compute_daily_energy
        from src.community_demand import compute_daily_demands

        energy_df = compute_daily_energy(
            config_path=energy_config_path,
            registry_path=registry_path,
            farm_profiles_path=farm_profiles_path,
            root_dir=root_dir,
        )
        community_df = compute_daily_demands(
            config_path=community_config_path,
            registry_path=registry_path,
            root_dir=root_dir,
        )
        merged = energy_df[['day', 'total_renewable_kwh']].merge(
            community_df[['day', 'total_community_energy_kwh']], on='day',
        )
        available_energy = (
            merged['total_renewable_kwh'] - merged['total_community_energy_kwh']
        ).clip(lower=0)
        avail_series = pd.Series(available_energy.values, index=merged['day'].values)
        target = avail_series.reindex(date_index, fill_value=0.0).values

        x_opt, scaled_target = _solve_match_supply(B, field_groups, target, min_planted_pct)
    else:
        raise ValueError(f"Unknown objective: {objective}")

    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        demand_after = B @ x_opt

    # Build optimized profile
    optimized_config = _build_optimized_profile(
        farm_config, schedule_labels, x_opt, min_area_ha
    )

    original_total_ha = sum(
        f['area_ha'] for farm in farm_config['farms'] for f in farm['fields'])
    optimized_total_ha = sum(
        f['area_ha'] for farm in optimized_config['farms'] for f in farm['fields'])

    summary = {
        'objective': objective,
        'before': _demand_metrics(demand_before),
        'after': _demand_metrics(demand_after),
        'variance_reduction_pct': (
            (1 - np.var(demand_after) / np.var(demand_before)) * 100
            if np.var(demand_before) > 0 else 0.0
        ),
        'n_fields_before': sum(len(f['fields']) for f in farm_config['farms']),
        'n_fields_after': sum(len(f['fields']) for f in optimized_config['farms']),
        'n_schedules_evaluated': sum(len(s) for _, s in fields_with_schedules),
        'area_ha_before': original_total_ha,
        'area_ha_after': optimized_total_ha,
        'planted_area_pct': (optimized_total_ha / original_total_ha * 100
                             if original_total_ha > 0 else 100.0),
    }

    return {
        'farm_config': optimized_config,
        'summary': summary,
        'demand_before': pd.Series(demand_before, index=date_index, name='demand_m3'),
        'demand_after': pd.Series(demand_after, index=date_index, name='demand_m3'),
        'date_index': date_index,
        'target': (
            pd.Series(scaled_target, index=date_index, name='target_m3')
            if scaled_target is not None else None
        ),
    }


def save_optimized_profile(farm_config, output_path):
    """Save optimized farm profile to YAML.

    Args:
        farm_config: Dict returned as result['farm_config'].
        output_path: Path to write the YAML file.

    Returns:
        Path to the saved file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Custom representer for cleaner YAML output (flow style for planting lists)
    class _Dumper(yaml.SafeDumper):
        pass

    def _list_representer(dumper, data):
        if all(isinstance(item, str) for item in data) and len(data) <= 6:
            return dumper.represent_sequence('tag:yaml.org,2002:seq', data,
                                            flow_style=True)
        return dumper.represent_sequence('tag:yaml.org,2002:seq', data,
                                        flow_style=False)

    _Dumper.add_representer(list, _list_representer)

    with open(output_path, 'w') as f:
        f.write("# Farm Profiles — Optimized\n")
        f.write("# Generated by src/planting_optimizer.py\n")
        f.write("# Planting dates and field splits optimized for demand smoothing.\n\n")
        yaml.dump(farm_config, f, Dumper=_Dumper, default_flow_style=False,
                  sort_keys=False)

    return output_path


# ---------------------------------------------------------------------------
# Entry point for quick verification
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    root = Path(__file__).parent.parent
    settings = root / 'settings'

    result = optimize_planting_schedule(
        farm_profiles_path=settings / 'farm_profile_base.yaml',
        registry_path=settings / 'data_registry_base.yaml',
        objective='minimize_variance',
    )

    s = result['summary']
    print(f"Objective: {s['objective']}")
    print(f"Schedules evaluated: {s['n_schedules_evaluated']}")
    print(f"Fields: {s['n_fields_before']} -> {s['n_fields_after']}")
    print(f"Variance reduction: {s['variance_reduction_pct']:.1f}%")
    print(f"Peak demand: {s['before']['peak_m3']:.0f} -> {s['after']['peak_m3']:.0f} m3/day")
    print(f"CV: {s['before']['cv']:.3f} -> {s['after']['cv']:.3f}")
    print()
    print(yaml.dump(result['farm_config'], default_flow_style=False, sort_keys=False))
