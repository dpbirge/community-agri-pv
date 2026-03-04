"""Daily water supply simulation for community irrigation.

Central mixing tank model: all water sources (groundwater, treated water,
municipal) flow into a storage tank. The tank mixes to a single TDS value.
Fields draw only from the tank. Tank volume and TDS carry day-to-day.

When crop TDS requirements become stricter than the current tank TDS, the
tank is flushed to the fields (no water wasted) and refilled with fresh
water at the correct TDS. At the daily timestep, both flush and refill
are assumed to occur within a single day.

Supports four dispatch strategies: minimize_cost, minimize_treatment,
minimize_draw, and maximize_treatment_efficiency. The first three are
demand-matching (source exactly what's needed each day). The fourth runs
the BWRO treatment plant at a steady rate near its efficiency sweet spot
(70-85% utilization), using the storage tank as a buffer.

System sizing and optimization functions are in src.water_sizing.

Usage:
    from src.water import compute_water_supply

    df = compute_water_supply(
        water_systems_path='settings/water_systems_base.yaml',
        registry_path='settings/data_registry_base.yaml',
        irrigation_demand_df=demand_df,
        water_policy_path='settings/water_policy_base.yaml',
    )
"""

import calendar
import logging
import math
from pathlib import Path

import pandas as pd
import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers — loading and path resolution
# ---------------------------------------------------------------------------

def _load_yaml(path):
    """Load and parse a YAML file."""
    with open(path) as f:
        return yaml.safe_load(f)


def _load_csv(path):
    """Load CSV, skipping comment lines that start with '#'."""
    return pd.read_csv(path, comment='#')


def _resolve_water_paths(registry, root_dir):
    """Resolve relative water supply paths from registry to absolute paths.

    Args:
        registry: Parsed data_registry.yaml dict.
        root_dir: Repository root directory.

    Returns:
        Dict mapping registry key to absolute Path.
    """
    return {
        k: Path(root_dir) / v
        for k, v in registry['water_supply'].items()
        if v is not None
    }


def _load_well_specs(system_config, pump_df):
    """Merge well configs from YAML with pump specs from CSV.

    Args:
        system_config: The system dict from water_systems.yaml containing 'wells'.
        pump_df: DataFrame from pump_systems CSV.

    Returns:
        List of dicts, each with keys: name, depth_m, tds_ppm, pump_type,
        rated_flow_m3_hr, pump_efficiency, motor_kw, om_cost_per_year,
        max_daily_m3.
    """
    pump_lookup = pump_df.set_index('pump_type').to_dict('index')
    wells = []
    for w in system_config['wells']:
        pump = pump_lookup[w['pump_type']]
        wells.append({
            'name': w['name'],
            'depth_m': w['depth_m'],
            'tds_ppm': w['tds_ppm'],
            'pump_type': w['pump_type'],
            'rated_flow_m3_hr': pump['rated_flow_m3_hr'],
            'pump_efficiency': pump['pump_efficiency'],
            'motor_kw': pump['motor_kw'],
            'om_cost_per_year': pump['om_cost_per_year'],
            'max_daily_m3': pump['rated_flow_m3_hr'] * 24,
        })
    return wells


def _load_treatment_lookup(path):
    """Load treatment lookup CSV with numeric tds_ppm column.

    Args:
        path: Path to water_treatment-research.csv.

    Returns:
        DataFrame sorted by tds_ppm for nearest-snap lookup.
    """
    df = _load_csv(path)
    return df.sort_values('tds_ppm').reset_index(drop=True)


# ---------------------------------------------------------------------------
# Internal helpers — physics and blending
# ---------------------------------------------------------------------------

def _snap_tds_to_band(input_tds, treatment_df):
    """Find the treatment lookup row closest to input_tds.

    Args:
        input_tds: Scalar TDS value (ppm) of feed water.
        treatment_df: DataFrame from _load_treatment_lookup.

    Returns:
        Series (single row from treatment_df) for the nearest TDS band.
    """
    idx = (treatment_df['tds_ppm'] - input_tds).abs().idxmin()
    return treatment_df.loc[idx]


def _pumping_energy_kwh(volume_m3, depth_m, pump_efficiency):
    """Hydraulic energy to lift water from a well.

    Formula: (rho * g * depth * volume) / (efficiency * 3_600_000)
    where rho=1025 kg/m3 (brackish water), g=9.81 m/s2,
    3_600_000 converts J to kWh.

    Args:
        volume_m3: Volume of water extracted (m3).
        depth_m: Well depth (meters).
        pump_efficiency: Combined pump+motor efficiency (fraction).

    Returns:
        Energy in kWh.
    """
    if volume_m3 <= 0:
        return 0.0
    return (1025 * 9.81 * depth_m * volume_m3) / (pump_efficiency * 3_600_000)


def _blend_tds(volumes, tds_values):
    """Volume-weighted average TDS across multiple water streams.

    Args:
        volumes: Sequence of volumes (m3).
        tds_values: Sequence of TDS values (ppm), same length as volumes.

    Returns:
        Blended TDS (float). Returns 0.0 if total volume is zero.
    """
    total_vol = sum(volumes)
    if total_vol <= 0:
        return 0.0
    return sum(v * t for v, t in zip(volumes, tds_values)) / total_vol


def _sourced_blend_tds(gw_untreated, gw_treated, muni_vol,
                       raw_gw_tds, treated_tds, muni_tds):
    """Volume-weighted TDS of the three sourced water streams.

    Args:
        gw_untreated: Untreated groundwater volume (m3).
        gw_treated: Treated groundwater product volume (m3).
        muni_vol: Municipal water volume (m3).
        raw_gw_tds: TDS of raw groundwater (ppm).
        treated_tds: TDS of treated water output (ppm).
        muni_tds: TDS of municipal water (ppm).

    Returns:
        Blended TDS (ppm). Returns 0.0 if total volume is zero.
    """
    return _blend_tds([gw_untreated, gw_treated, muni_vol],
                      [raw_gw_tds, treated_tds, muni_tds])


def _daily_cap_allowance(day, monthly_cap, used_this_month, look_ahead):
    """Compute how much of a monthly cap is available today.

    Args:
        day: Date (datetime-like with .year, .month, .day).
        monthly_cap: Monthly volume cap (m3), or None for unlimited.
        used_this_month: Volume already consumed this month (m3).
        look_ahead: If True, spread remaining cap evenly over remaining days.

    Returns:
        Available volume today (m3). float('inf') when uncapped.
    """
    if monthly_cap is None:
        return float('inf')
    remaining = monthly_cap - used_this_month
    if remaining <= 0:
        return 0.0
    if not look_ahead:
        return remaining
    days_in_month = calendar.monthrange(day.year, day.month)[1]
    remaining_days = days_in_month - day.day + 1
    return remaining / remaining_days


# ---------------------------------------------------------------------------
# Internal helpers — well extraction distribution
# ---------------------------------------------------------------------------

def _well_distribution(wells, total_extraction):
    """Compute per-well extraction volumes using equal distribution with capacity limits.

    Distributes total_extraction evenly across wells, respecting each well's
    max_daily_m3 cap. Wells that hit capacity are removed from the pool and
    remaining volume is redistributed.

    Args:
        wells: List of well spec dicts with 'name' and 'max_daily_m3' keys.
        total_extraction: Total volume to extract across all wells (m3).

    Returns:
        Dict mapping well name to extraction volume (m3).
    """
    assigned = {w['name']: 0.0 for w in wells}
    if total_extraction <= 0 or not wells:
        return assigned
    remaining = total_extraction
    uncapped = list(wells)
    while remaining > 1e-9 and uncapped:
        share = remaining / len(uncapped)
        still_uncapped = []
        for w in uncapped:
            headroom = w['max_daily_m3'] - assigned[w['name']]
            alloc = min(share, headroom)
            assigned[w['name']] += alloc
            remaining -= alloc
            if assigned[w['name']] < w['max_daily_m3'] - 1e-9:
                still_uncapped.append(w)
        if len(still_uncapped) == len(uncapped):
            break
        uncapped = still_uncapped
    return assigned


def _volume_weighted_tds(wells, total_extraction):
    """Volume-weighted average TDS for a given total extraction across wells.

    Args:
        wells: List of well spec dicts with 'name' and 'tds_ppm' keys.
        total_extraction: Total volume to extract (m3), distributed via _well_distribution.

    Returns:
        Blended TDS (float). Returns 0.0 if total extraction is zero.
    """
    if total_extraction <= 0 or not wells:
        return 0.0
    dist = _well_distribution(wells, total_extraction)
    total = sum(dist.values())
    if total <= 0:
        return 0.0
    return sum(dist[w['name']] * w['tds_ppm'] for w in wells) / total


def _assign_well_extraction(wells, total_extraction, row):
    """Distribute total extraction across wells and record in output row.

    Args:
        wells: List of well spec dicts.
        total_extraction: Total volume to distribute (m3).
        row: Output row dict (mutated in place with per-well extraction values).
    """
    dist = _well_distribution(wells, total_extraction)
    for w in wells:
        row[f'{w["name"]}_extraction_m3'] = dist[w['name']]


def _compute_gw_energy_and_cost(wells, treatment_row, treated_product, row):
    """Compute pumping energy, treatment energy, and groundwater cost.

    Reads per-well extraction from row to compute pumping energy.
    Updates row in place with energy and cost fields.
    """
    total_pump_kwh = 0.0
    for w in wells:
        vol = row.get(f'{w["name"]}_extraction_m3', 0.0)
        well_energy = _pumping_energy_kwh(vol, w['depth_m'], w['pump_efficiency'])
        row[f'{w["name"]}_pumping_kwh'] = well_energy
        total_pump_kwh += well_energy
    row['pumping_energy_kwh'] = total_pump_kwh

    if treatment_row is not None and treated_product > 0:
        row['treatment_energy_kwh'] = treated_product * treatment_row['energy_kwh_per_m3']
        recovery_rate = treatment_row['recovery_rate_pct'] / 100.0
        feed_vol = treated_product / recovery_rate if recovery_rate > 0 else treated_product
        row['treatment_feed_m3'] = feed_vol
        row['treatment_reject_m3'] = feed_vol - treated_product
        row['groundwater_cost'] = treated_product * treatment_row['maintenance_cost_per_m3']

    row['groundwater_cost'] = row.get('groundwater_cost', 0.0) + sum(
        w['om_cost_per_year'] / 365.0
        for w in wells if row.get(f'{w["name"]}_extraction_m3', 0.0) > 0
    )


# ---------------------------------------------------------------------------
# Internal helpers — source computations (pure, no side effects)
# ---------------------------------------------------------------------------

def _gw_source(target_vol, tds_req, wells, treatment, gw_cap_state,
               already_extracted=0.0):
    """Compute groundwater sourcing to produce target_vol at <= tds_req.

    Determines the split between treated and untreated GW product, accounting
    for BWRO recovery loss and respecting extraction and throughput limits.

    Args:
        target_vol: Desired product volume (m3).
        tds_req: Maximum acceptable TDS for the product (ppm).
        wells: List of well spec dicts.
        treatment: Dict with goal_output_tds_ppm, throughput_m3_hr, lookup_df.
        gw_cap_state: Dict with monthly_cap, used, day, look_ahead.
        already_extracted: GW already extracted today (m3), reduces allowance.

    Returns:
        Tuple of (delivery_m3, treated_product_m3, untreated_m3,
                  total_extraction_m3, treatment_row_or_None).
    """
    if target_vol <= 0 or not wells:
        return 0.0, 0.0, 0.0, 0.0, None

    gw_allowance = _daily_cap_allowance(
        gw_cap_state['day'], gw_cap_state['monthly_cap'],
        gw_cap_state['used'], gw_cap_state['look_ahead'],
    )
    total_well_capacity = sum(w['max_daily_m3'] for w in wells)
    gw_extraction_limit = min(total_well_capacity, gw_allowance) - already_extracted
    if gw_extraction_limit <= 0:
        return 0.0, 0.0, 0.0, 0.0, None

    raw_gw_tds = _volume_weighted_tds(wells, gw_extraction_limit)

    if raw_gw_tds <= tds_req:
        delivery = min(target_vol, gw_extraction_limit)
        return delivery, 0.0, delivery, delivery, None

    # Treatment unavailable — raw GW exceeds TDS requirement and cannot be treated
    if treatment['lookup_df'] is None:
        return 0.0, 0.0, 0.0, 0.0, None

    goal_tds = treatment['goal_output_tds_ppm']

    # Blending ratio: fraction of product that must be treated
    if goal_tds >= tds_req:
        f_treat = 1.0
    elif abs(raw_gw_tds - goal_tds) < 1e-9:
        f_treat = 1.0
    else:
        f_treat = (raw_gw_tds - tds_req) / (raw_gw_tds - goal_tds)
        f_treat = max(0.0, min(1.0, f_treat))

    treatment_row = _snap_tds_to_band(raw_gw_tds, treatment['lookup_df'])
    recovery_rate = treatment_row['recovery_rate_pct'] / 100.0

    desired = target_vol
    treated_product = desired * f_treat
    untreated = desired * (1 - f_treat)
    feed = treated_product / recovery_rate if recovery_rate > 0 else treated_product
    extraction = feed + untreated

    if extraction > gw_extraction_limit:
        scale = gw_extraction_limit / extraction
        desired *= scale
        treated_product = desired * f_treat
        untreated = desired * (1 - f_treat)
        feed = treated_product / recovery_rate if recovery_rate > 0 else treated_product
        extraction = feed + untreated

    max_feed_m3 = treatment['throughput_m3_hr'] * 24
    if feed > max_feed_m3:
        feed = max_feed_m3
        treated_product = feed * recovery_rate
        if f_treat > 0:
            desired = treated_product / f_treat
            untreated = desired * (1 - f_treat)
        else:
            desired = treated_product
            untreated = 0.0
        extraction = feed + untreated
        if extraction > gw_extraction_limit:
            scale = gw_extraction_limit / extraction
            treated_product *= scale
            untreated *= scale
            feed = treated_product / recovery_rate if recovery_rate > 0 else treated_product
            extraction = feed + untreated
            desired = treated_product + untreated

    return desired, treated_product, untreated, extraction, treatment_row


def _muni_source(target_vol, municipal, muni_cap_state, already_used=0.0):
    """Compute municipal water volume available for sourcing.

    Args:
        target_vol: Desired volume (m3).
        municipal: Dict with tds_ppm, cost_per_m3, throughput_m3_hr.
        muni_cap_state: Dict with monthly_cap, used, day, look_ahead.
        already_used: Municipal already used today (m3), reduces allowance.

    Returns:
        Volume available to source (m3).
    """
    if target_vol <= 0:
        return 0.0
    allowance = _daily_cap_allowance(
        muni_cap_state['day'], muni_cap_state['monthly_cap'],
        muni_cap_state['used'], muni_cap_state['look_ahead'],
    )
    max_muni = municipal['throughput_m3_hr'] * 24
    available = min(allowance, max_muni) - already_used
    return min(target_vol, max(0.0, available))


# ---------------------------------------------------------------------------
# Internal helpers — tank sourcing (modifies tank and row)
# ---------------------------------------------------------------------------

def _source_water(target_vol, tds_req, wells, treatment, municipal,
                  tank, gw_cap_state, muni_cap_state, row, strategy):
    """Source water from available sources and mix into tank.

    Determines sourcing volumes per strategy, mixes sourced water into the
    tank (volume-weighted TDS), and records extraction, energy, and cost
    in the output row.

    Args:
        target_vol: Desired volume to source (m3). Capped at tank headroom.
        tds_req: Maximum acceptable TDS for sourced water (ppm).
        wells: List of well spec dicts.
        treatment: Dict with goal_output_tds_ppm, throughput_m3_hr, lookup_df.
        municipal: Dict with tds_ppm, cost_per_m3, throughput_m3_hr.
        tank: Dict with fill_m3, tds_ppm, capacity_m3 (mutated in place).
        gw_cap_state: Dict with monthly_cap, used, day, look_ahead.
        muni_cap_state: Dict with monthly_cap, used, day, look_ahead.
        row: Output row dict (mutated in place).
        strategy: One of 'minimize_cost', 'minimize_treatment', 'minimize_draw'.

    Returns:
        Actual volume sourced and mixed into tank (m3).
    """
    if target_vol <= 0:
        return 0.0

    headroom = tank['capacity_m3'] - tank['fill_m3']
    target_vol = min(target_vol, headroom)
    if target_vol <= 0:
        return 0.0

    remaining = target_vol
    gw_untreated = 0.0
    gw_treated = 0.0
    gw_extraction = 0.0
    muni_vol = 0.0
    treat_row = None
    raw_gw_tds = _volume_weighted_tds(wells, sum(w['max_daily_m3'] for w in wells)) if wells else float('inf')

    if strategy == 'minimize_cost':
        delivery, tp, ut, ext, tr = _gw_source(
            remaining, tds_req, wells, treatment, gw_cap_state)
        gw_treated, gw_untreated, gw_extraction, treat_row = tp, ut, ext, tr
        remaining -= delivery
        if remaining > 0:
            muni_vol = _muni_source(remaining, municipal, muni_cap_state)
            remaining -= muni_vol

    elif strategy == 'minimize_treatment':
        if raw_gw_tds <= tds_req:
            delivery, _, ut, ext, _ = _gw_source(
                remaining, tds_req, wells, treatment, gw_cap_state)
            gw_untreated = ut
            gw_extraction = ext
            remaining -= delivery
        if remaining > 0:
            muni_vol = _muni_source(remaining, municipal, muni_cap_state)
            remaining -= muni_vol
        if remaining > 0 and raw_gw_tds > tds_req:
            delivery, tp, ut, ext, tr = _gw_source(
                remaining, tds_req, wells, treatment, gw_cap_state,
                already_extracted=gw_extraction)
            gw_treated += tp
            gw_untreated += ut
            gw_extraction += ext
            treat_row = tr
            remaining -= delivery

    elif strategy == 'minimize_draw':
        muni_vol = _muni_source(remaining, municipal, muni_cap_state)
        remaining -= muni_vol
        if remaining > 0:
            delivery, tp, ut, ext, tr = _gw_source(
                remaining, tds_req, wells, treatment, gw_cap_state)
            gw_treated, gw_untreated, gw_extraction, treat_row = tp, ut, ext, tr
            remaining -= delivery

    # Recompute GW TDS from actual extraction distribution
    if gw_extraction > 0:
        raw_gw_tds = _volume_weighted_tds(wells, gw_extraction)

    # TDS correction: if sourced water blend exceeds tds_req, add municipal
    # to bring it down. This is the default policy (GW -> treatment ->
    # municipal for TDS) and applies regardless of dispatch strategy.
    treated_tds = treatment['goal_output_tds_ppm'] if treatment['lookup_df'] is not None else 0.0
    sourced_before_tds_fix = gw_untreated + gw_treated + muni_vol
    if sourced_before_tds_fix > 0 and municipal['tds_ppm'] < tds_req:
        blend_tds_check = _sourced_blend_tds(
            gw_untreated, gw_treated, muni_vol,
            raw_gw_tds, treated_tds, municipal['tds_ppm'])
        if blend_tds_check > tds_req:
            muni_for_tds = (sourced_before_tds_fix
                            * (blend_tds_check - tds_req)
                            / (tds_req - municipal['tds_ppm']))
            muni_correction = _muni_source(
                muni_for_tds, municipal, muni_cap_state,
                already_used=muni_vol)
            muni_vol += muni_correction

    # Enforce tank capacity after TDS correction
    headroom = tank['capacity_m3'] - tank['fill_m3']
    sourced = gw_untreated + gw_treated + muni_vol
    if sourced > headroom:
        muni_vol = max(0.0, muni_vol - (sourced - headroom))
        sourced = gw_untreated + gw_treated + muni_vol
        if sourced > 0:
            trim_tds = _sourced_blend_tds(
                gw_untreated, gw_treated, muni_vol,
                raw_gw_tds, treated_tds, municipal['tds_ppm'])
            if trim_tds > tds_req:
                logger.warning(
                    'Tank headroom limited TDS correction: sourced TDS %.0f ppm '
                    'exceeds crop requirement %.0f ppm', trim_tds, tds_req)

    # Mix sourced water into tank
    sourced_tds = 0.0
    if sourced > 0:
        sourced_tds = _sourced_blend_tds(
            gw_untreated, gw_treated, muni_vol,
            raw_gw_tds, treated_tds, municipal['tds_ppm'])
        if tank['fill_m3'] > 0:
            tank['tds_ppm'] = _blend_tds(
                [tank['fill_m3'], sourced],
                [tank['tds_ppm'], sourced_tds])
        else:
            tank['tds_ppm'] = sourced_tds
        tank['fill_m3'] += sourced
    row['sourced_tds_ppm'] = sourced_tds

    # Record in output row
    row['gw_untreated_to_tank_m3'] = gw_untreated
    row['gw_treated_to_tank_m3'] = gw_treated
    row['municipal_to_tank_m3'] = muni_vol
    row['total_groundwater_extracted_m3'] = gw_extraction

    _assign_well_extraction(wells, gw_extraction, row)
    _compute_gw_energy_and_cost(wells, treat_row, gw_treated, row)
    row['municipal_cost'] = muni_vol * municipal['cost_per_m3']

    return sourced


# ---------------------------------------------------------------------------
# Internal helpers — daily dispatch
# ---------------------------------------------------------------------------

def _init_dispatch_row(wells, tds_req, treatment_throughput_m3_hr,
                       tank_fill_m3, tank_tds_ppm, strategy):
    """Build a zeroed-out output row dict for a single dispatch day.

    Args:
        wells: List of well spec dicts.
        tds_req: Crop TDS requirement for this day (ppm).
        treatment_throughput_m3_hr: Treatment system throughput (m3/hr).
        tank_fill_m3: Current tank fill level (m3).
        tank_tds_ppm: Current tank TDS (ppm).
        strategy: Dispatch strategy string.

    Returns:
        Dict with all output row keys initialized to zero/defaults.
    """
    row = {}
    for w in wells:
        row[f'{w["name"]}_extraction_m3'] = 0.0
        row[f'{w["name"]}_tds_ppm'] = w['tds_ppm']
        row[f'{w["name"]}_pumping_kwh'] = 0.0
    row.update({
        'gw_untreated_to_tank_m3': 0.0,
        'gw_treated_to_tank_m3': 0.0,
        'municipal_to_tank_m3': 0.0,
        'total_sourced_to_tank_m3': 0.0,
        'total_groundwater_extracted_m3': 0.0,
        'sourced_tds_ppm': 0.0,
        'treatment_feed_m3': 0.0,
        'treatment_max_feed_m3': treatment_throughput_m3_hr * 24,
        'treatment_reject_m3': 0.0,
        'treatment_energy_kwh': 0.0,
        'pumping_energy_kwh': 0.0,
        'municipal_cost': 0.0,
        'groundwater_cost': 0.0,
        'total_water_cost': 0.0,
        'delivered_tds_ppm': 0.0,
        'crop_tds_requirement_ppm': tds_req,
        'tds_exceedance_ppm': 0.0,
        'total_delivered_m3': 0.0,
        'tank_flush_delivered_m3': 0.0,
        'safety_flush_m3': 0.0,
        'look_ahead_drain_m3': 0.0,
        'deficit_m3': 0.0,
        'tank_volume_m3': tank_fill_m3,
        'tank_tds_ppm': tank_tds_ppm,
        'total_sourcing_energy_kwh': 0.0,
        'prefill_m3': 0.0,
        'policy_strategy': strategy,
        'policy_primary_source': 'none',
        'policy_flush_reason': 'none',
        'policy_deficit': False,
        'treatment_target_m3': 0.0,
        'treatment_utilization_pct': 0.0,
        'treatment_energy_multiplier': 1.0,
        'treatment_on': True,
    })
    return row


def _prefill_tank(row, tank, wells, treatment, municipal,
                  gw_cap_state, muni_cap_state, strategy,
                  tds_req, upcoming_demands, upcoming_tds):
    """Source buffer water into tank for upcoming peak days.

    Reads today's sourced throughput from row, computes shortfall against
    upcoming demands, and sources additional water into the tank. Accumulates
    prefill energy, cost, and volume into row in place.

    Args:
        row: Main output row dict (mutated: accumulates prefill volumes/costs).
        tank: Tank state dict (mutated by _source_water).
        wells: List of well spec dicts.
        treatment: Treatment config dict.
        municipal: Municipal source config dict.
        gw_cap_state: Groundwater cap state dict.
        muni_cap_state: Municipal cap state dict.
        strategy: Dispatch strategy string.
        tds_req: Today's TDS requirement (fallback for prefill TDS).
        upcoming_demands: List of demand_m3 for next N days.
        upcoming_tds: List of TDS requirements for next N days.

    Returns:
        Volume prefilled into tank (m3). Zero if no prefill needed.
    """
    today_throughput = (row['gw_untreated_to_tank_m3']
                        + row['gw_treated_to_tank_m3']
                        + row['municipal_to_tank_m3'])
    valid_tds = [t for t in (upcoming_tds or []) if not math.isnan(t)]
    prefill_tds_req = min(valid_tds) if valid_tds else tds_req

    shortfall = sum(d - today_throughput for d in upcoming_demands
                    if d > today_throughput)
    if shortfall <= 0:
        return 0.0

    headroom = tank['capacity_m3'] - tank['fill_m3']
    prefill_target = min(shortfall, headroom)

    pf_gw_cap = dict(gw_cap_state)
    pf_gw_cap['used'] = pf_gw_cap['used'] + row['total_groundwater_extracted_m3']
    pf_muni_cap = dict(muni_cap_state)
    pf_muni_cap['used'] = pf_muni_cap['used'] + row['municipal_to_tank_m3']

    pf_row = {}
    for w in wells:
        pf_row[f'{w["name"]}_extraction_m3'] = 0.0
        pf_row[f'{w["name"]}_pumping_kwh'] = 0.0
    pf_row.update({
        'treatment_feed_m3': 0.0, 'treatment_reject_m3': 0.0,
        'treatment_energy_kwh': 0.0, 'pumping_energy_kwh': 0.0,
        'groundwater_cost': 0.0, 'municipal_cost': 0.0,
        'sourced_tds_ppm': 0.0,
        'gw_untreated_to_tank_m3': 0.0, 'gw_treated_to_tank_m3': 0.0,
        'municipal_to_tank_m3': 0.0, 'total_groundwater_extracted_m3': 0.0,
    })

    prefill_vol = _source_water(
        prefill_target, prefill_tds_req, wells, treatment, municipal,
        tank, pf_gw_cap, pf_muni_cap, pf_row, strategy)

    if prefill_vol > 0:
        for w in wells:
            row[f'{w["name"]}_extraction_m3'] += pf_row[f'{w["name"]}_extraction_m3']
            row[f'{w["name"]}_pumping_kwh'] += pf_row[f'{w["name"]}_pumping_kwh']
        row['gw_untreated_to_tank_m3'] += pf_row['gw_untreated_to_tank_m3']
        row['gw_treated_to_tank_m3'] += pf_row['gw_treated_to_tank_m3']
        row['municipal_to_tank_m3'] += pf_row['municipal_to_tank_m3']
        row['total_groundwater_extracted_m3'] += pf_row['total_groundwater_extracted_m3']
        row['pumping_energy_kwh'] += pf_row['pumping_energy_kwh']
        row['treatment_energy_kwh'] += pf_row['treatment_energy_kwh']
        row['treatment_feed_m3'] += pf_row['treatment_feed_m3']
        row['treatment_reject_m3'] += pf_row['treatment_reject_m3']
        row['groundwater_cost'] += pf_row['groundwater_cost']
        row['municipal_cost'] += pf_row['municipal_cost']

    return prefill_vol


# ---------------------------------------------------------------------------
# Internal helpers — treatment smoothing
# ---------------------------------------------------------------------------

def _compute_treatment_target(demand_df, raw_gw_tds, treatment, tank_capacity_m3,
                               smoothing_cfg):
    """Compute the steady-state daily treatment feed target.

    Analyzes the full demand series to find a constant treatment rate that
    produces enough treated water to meet season-total treated demand while
    falling within the BWRO sweet spot (70-85% of rated capacity).

    Args:
        demand_df: Full demand DataFrame with total_demand_m3, crop_tds_requirement_ppm.
        raw_gw_tds: Volume-weighted raw groundwater TDS across all wells.
        treatment: Treatment config dict (goal_output_tds_ppm, throughput_m3_hr, lookup_df).
        tank_capacity_m3: Storage tank capacity.
        smoothing_cfg: Dict from policy['treatment_smoothing'].

    Returns:
        Dict with keys:
            feed_target_m3: Daily treatment feed target (m3).
            source_target_m3: Equivalent source volume (m3) to achieve feed target.
            f_treat: Blending fraction (0-1) — share of product that must be treated.
            recovery_rate: BWRO recovery rate (0-1).
    """
    # No treatment available — return zero targets
    if treatment['lookup_df'] is None:
        return {'feed_target_m3': 0.0, 'source_target_m3': 0.0,
                'f_treat': 0.0, 'recovery_rate': 0.0}

    goal_tds = treatment['goal_output_tds_ppm']
    max_daily_feed = treatment['throughput_m3_hr'] * 24

    # Compute treatment fraction from GW TDS vs strictest crop TDS requirement
    tds_vals = demand_df['crop_tds_requirement_ppm'].dropna()
    if tds_vals.empty:
        return {'feed_target_m3': 0.0, 'source_target_m3': 0.0,
                'f_treat': 0.0, 'recovery_rate': 0.0}
    strictest_tds = tds_vals.min()

    if raw_gw_tds <= strictest_tds:
        f_treat = 0.0
    elif goal_tds >= strictest_tds:
        f_treat = 1.0
    elif abs(raw_gw_tds - goal_tds) < 1e-9:
        f_treat = 1.0
    else:
        f_treat = (raw_gw_tds - strictest_tds) / (raw_gw_tds - goal_tds)
        f_treat = max(0.0, min(1.0, f_treat))

    if f_treat <= 0:
        return {'feed_target_m3': 0.0, 'source_target_m3': 0.0,
                'f_treat': 0.0, 'recovery_rate': 0.0}

    # Recovery rate from treatment lookup for the raw GW TDS band
    treatment_row = _snap_tds_to_band(raw_gw_tds, treatment['lookup_df'])
    recovery_rate = treatment_row['recovery_rate_pct'] / 100.0

    # Total season treated product and feed
    active_mask = demand_df['crop_tds_requirement_ppm'].notna()
    active_demands = demand_df.loc[active_mask, 'total_demand_m3']
    total_treated_product = (active_demands * f_treat).sum()
    total_feed = total_treated_product / recovery_rate if recovery_rate > 0 else total_treated_product

    # Divide by operating days
    fallow_treatment = smoothing_cfg.get('fallow_treatment', True)
    if fallow_treatment:
        n_days = len(demand_df)
    else:
        n_days = active_mask.sum()
    if n_days <= 0:
        return {'feed_target_m3': 0.0, 'source_target_m3': 0.0,
                'f_treat': f_treat, 'recovery_rate': recovery_rate}

    avg_daily_feed = total_feed / n_days

    # Clamp to sweet spot (70-85% of rated capacity)
    feed_target = max(0.70 * max_daily_feed, min(0.85 * max_daily_feed, avg_daily_feed))

    # Convert feed target to source volume: source = feed * recovery_rate / f_treat
    # (treated_product = feed * recovery_rate, then source = treated_product / f_treat)
    source_target = feed_target * recovery_rate / f_treat if f_treat > 0 else feed_target

    # Validate tank capacity as buffer
    if tank_capacity_m3 > 0:
        peak_daily_demand = active_demands.max()
        surplus_per_day = source_target - peak_daily_demand
        if surplus_per_day > 0 and surplus_per_day * 7 > tank_capacity_m3:
            logger.warning(
                'Tank may be undersized for treatment smoothing: %.0f m3 capacity '
                'vs %.0f m3 weekly surplus. Tank feedback will handle overflow.',
                tank_capacity_m3, surplus_per_day * 7)

    return {
        'feed_target_m3': feed_target,
        'source_target_m3': source_target,
        'f_treat': f_treat,
        'recovery_rate': recovery_rate,
    }


def _effective_treatment_target(base_target_m3, tank, demand_remaining,
                                 max_source_m3, smoothing_cfg, treatment_on):
    """Duty-cycle treatment decision: run at optimal or shut off.

    Uses hysteresis to prevent rapid on/off cycling. When the plant is on,
    it runs at the base target rate (70-85% sweet spot). When off, demand
    is served from tank stock.

    Args:
        base_target_m3: Pre-computed daily source target (m3 product).
        tank: Current tank state dict (fill_m3, capacity_m3).
        demand_remaining: Today's unmet demand after tank draw (m3).
        max_source_m3: Max daily source volume.
        smoothing_cfg: Dict with tank_feedback.high_mark, low_mark.
        treatment_on: Boolean -- was the plant on yesterday?

    Returns:
        Tuple of (effective_volume_m3, treatment_on_today).
    """
    feedback = smoothing_cfg.get('tank_feedback', {})
    high_mark = feedback.get('high_mark', 0.90)
    low_mark = feedback.get('low_mark', 0.15)

    fill_fraction = tank['fill_m3'] / tank['capacity_m3'] if tank['capacity_m3'] > 0 else 1.0

    if fill_fraction > high_mark:
        effective = 0.0
        treatment_on = False
    elif fill_fraction < low_mark:
        effective = max_source_m3
        treatment_on = True
    else:
        # Hysteresis band — keep previous state
        if treatment_on:
            effective = base_target_m3
        else:
            effective = 0.0

    # Demand override: if tank stock alone cannot serve today's demand,
    # turn the plant on regardless of hysteresis state
    if demand_remaining > tank['fill_m3'] and not treatment_on:
        effective = base_target_m3
        treatment_on = True

    # Cap at tank headroom
    effective = min(effective, tank['capacity_m3'] - tank['fill_m3'])

    return (max(0.0, effective), treatment_on)


def _finalize_dispatch_row(row, tank, demand_m3, tds_req, flush_reason,
                           deliveries):
    """Compute delivery totals, energy/cost sums, and policy metadata.

    Args:
        row: Output row dict (mutated in place).
        tank: Tank state dict (read-only -- reads fill_m3 and tds_ppm).
        demand_m3: Today's total irrigation demand.
        tds_req: Crop TDS requirement.
        flush_reason: String describing flush cause (or empty).
        deliveries: Dict with keys 'flush', 'draw_existing', 'draw_fresh',
            'drain', each mapping to a (volume_m3, tds_ppm) tuple.
    """
    flush_vol, flush_tds = deliveries['flush']
    draw_existing, draw_existing_tds = deliveries['draw_existing']
    draw_fresh, draw_fresh_tds = deliveries['draw_fresh']
    drain_vol, drain_tds = deliveries['drain']

    total_delivered = flush_vol + draw_existing + draw_fresh + drain_vol
    if total_delivered > 0:
        delivered_tds = _blend_tds(
            [flush_vol, draw_existing, draw_fresh, drain_vol],
            [flush_tds, draw_existing_tds, draw_fresh_tds, drain_tds])
    else:
        delivered_tds = 0.0

    row['tank_flush_delivered_m3'] = flush_vol + drain_vol
    row['safety_flush_m3'] = flush_vol
    row['look_ahead_drain_m3'] = drain_vol
    row['total_delivered_m3'] = total_delivered
    row['delivered_tds_ppm'] = delivered_tds
    row['tds_exceedance_ppm'] = max(0.0, delivered_tds - tds_req) if total_delivered > 0 else 0.0
    row['deficit_m3'] = max(0.0, demand_m3 - total_delivered)
    row['total_sourced_to_tank_m3'] = (row['gw_untreated_to_tank_m3'] +
                                       row['gw_treated_to_tank_m3'] +
                                       row['municipal_to_tank_m3'])
    row['total_sourcing_energy_kwh'] = row['pumping_energy_kwh'] + row['treatment_energy_kwh']
    row['total_water_cost'] = row['municipal_cost'] + row['groundwater_cost']
    row['tank_volume_m3'] = tank['fill_m3']
    row['tank_tds_ppm'] = tank['tds_ppm']

    row['policy_flush_reason'] = flush_reason
    row['policy_deficit'] = round(row['deficit_m3'], 3) > 0

    gu = row['gw_untreated_to_tank_m3']
    gt = row['gw_treated_to_tank_m3']
    mu = row['municipal_to_tank_m3']
    if gu > 0 or gt > 0 or mu > 0:
        vol_src = [('gw_untreated', gu), ('gw_treated', gt), ('municipal', mu)]
        vol_src.sort(key=lambda x: x[1], reverse=True)
        top1, top2 = vol_src[0], vol_src[1]
        if top1[1] > top2[1]:
            row['policy_primary_source'] = top1[0]
        else:
            row['policy_primary_source'] = 'mixed'
    else:
        row['policy_primary_source'] = 'tank_stock'


def _handle_fallow_day(demand_m3, tds_req, policy, treatment, row, gw_cap_state,
                       upcoming_tds):
    """Handle fallow-day logic with optional treatment smoothing.

    On fallow days (zero demand or NaN TDS), demand-matching strategies skip
    dispatch entirely. The maximize_treatment_efficiency strategy may continue
    sourcing if active irrigation resumes within the fallow horizon.

    Args:
        demand_m3: Total irrigation demand (m3).
        tds_req: Crop TDS requirement (ppm). NaN on fallow days.
        policy: Policy dict with strategy, treatment_smoothing config.
        treatment: Treatment spec dict with goal_output_tds_ppm.
        row: Mutable row dict (updated if smoothing adjusts TDS).
        gw_cap_state: Cap state dict (day used for warning log).
        upcoming_tds: List of TDS requirements for upcoming days.

    Returns:
        Tuple of (demand_m3, tds_req, early_return) where early_return is
        True if the day should end with no dispatch, or False to continue.
    """
    is_fallow = demand_m3 <= 0 or math.isnan(tds_req)
    if not is_fallow:
        return demand_m3, tds_req, False

    if demand_m3 > 0 and math.isnan(tds_req):
        logger.warning(
            'Day %s: positive demand (%.1f m3) but TDS requirement is NaN '
            '— no water dispatched. Check crop TDS lookup coverage.',
            gw_cap_state['day'], demand_m3,
        )

    strategy = policy['strategy']
    smoothing_cfg = policy.get('treatment_smoothing', {})
    if (strategy != 'maximize_treatment_efficiency'
            or not smoothing_cfg.get('fallow_treatment', False)):
        return demand_m3, tds_req, True

    horizon = smoothing_cfg.get('fallow_horizon_days', 14)
    future_tds = upcoming_tds or []
    has_active_ahead = any(not math.isnan(t) for t in future_tds[:horizon])
    if not has_active_ahead:
        return demand_m3, tds_req, True

    demand_m3 = 0.0
    fallback_tds = treatment['goal_output_tds_ppm'] if treatment['lookup_df'] is not None else 0.0
    tds_req = next(
        (t for t in future_tds if not math.isnan(t)),
        fallback_tds)
    row['crop_tds_requirement_ppm'] = tds_req
    return demand_m3, tds_req, False


def _second_source_pass(demand_remaining, tds_req, wells, treatment, municipal,
                        tank, gw_cap_state, muni_cap_state, row, source_priority,
                        draw_fresh, draw_fresh_tds):
    """Run a second source+draw pass when demand exceeds single-pass throughput.

    When the first pass fills and drains the tank but leaves unmet demand,
    uses the freed headroom to source+draw the remainder via a scratch row
    to avoid overwriting first-pass accounting.

    Modifies row and tank in place.

    Args:
        demand_remaining: Unmet demand after first pass (m3).
        tds_req: Crop TDS requirement (ppm).
        wells: List of well spec dicts.
        treatment: Treatment spec dict.
        municipal: Municipal source spec dict.
        tank: Mutable tank state dict.
        gw_cap_state: Groundwater cap state dict.
        muni_cap_state: Municipal cap state dict.
        row: Mutable main row dict (accumulates second-pass volumes).
        source_priority: Strategy for sourcing priority.
        draw_fresh: First-pass fresh draw volume (m3).
        draw_fresh_tds: First-pass fresh draw TDS (ppm).

    Returns:
        Tuple of (demand_remaining, draw_fresh, draw_fresh_tds).
    """
    if not (demand_remaining > 0 and tank['fill_m3'] < 1e-9):
        return demand_remaining, draw_fresh, draw_fresh_tds

    p2_row = {}
    for w in wells:
        p2_row[f'{w["name"]}_extraction_m3'] = 0.0
        p2_row[f'{w["name"]}_pumping_kwh'] = 0.0
    p2_row.update({
        'treatment_feed_m3': 0.0, 'treatment_reject_m3': 0.0,
        'treatment_energy_kwh': 0.0, 'pumping_energy_kwh': 0.0,
        'groundwater_cost': 0.0, 'municipal_cost': 0.0,
        'sourced_tds_ppm': 0.0,
        'gw_untreated_to_tank_m3': 0.0, 'gw_treated_to_tank_m3': 0.0,
        'municipal_to_tank_m3': 0.0, 'total_groundwater_extracted_m3': 0.0,
    })

    _source_water(demand_remaining, tds_req, wells, treatment, municipal,
                  tank, gw_cap_state, muni_cap_state, p2_row, source_priority)

    # Accumulate second-pass accounting into main row
    for w in wells:
        row[f'{w["name"]}_extraction_m3'] += p2_row[f'{w["name"]}_extraction_m3']
        row[f'{w["name"]}_pumping_kwh'] += p2_row[f'{w["name"]}_pumping_kwh']
    row['gw_untreated_to_tank_m3'] += p2_row['gw_untreated_to_tank_m3']
    row['gw_treated_to_tank_m3'] += p2_row['gw_treated_to_tank_m3']
    row['municipal_to_tank_m3'] += p2_row['municipal_to_tank_m3']
    row['total_groundwater_extracted_m3'] += p2_row['total_groundwater_extracted_m3']
    row['pumping_energy_kwh'] += p2_row['pumping_energy_kwh']
    row['treatment_energy_kwh'] += p2_row['treatment_energy_kwh']
    row['treatment_feed_m3'] += p2_row['treatment_feed_m3']
    row['treatment_reject_m3'] += p2_row['treatment_reject_m3']
    row['groundwater_cost'] += p2_row['groundwater_cost']
    row['municipal_cost'] += p2_row['municipal_cost']

    if tank['fill_m3'] > 0:
        draw2 = min(demand_remaining, tank['fill_m3'])
        draw_fresh_tds = _blend_tds(
            [draw_fresh, draw2],
            [draw_fresh_tds, tank['tds_ppm']])
        draw_fresh += draw2
        tank['fill_m3'] -= draw2
        demand_remaining -= draw2
        if tank['fill_m3'] < 1e-9:
            tank['fill_m3'] = 0.0
            tank['tds_ppm'] = 0.0

    return demand_remaining, draw_fresh, draw_fresh_tds


def _look_ahead_drain(tank, next_tds_req, flush_reason):
    """Drain tank if next day needs stricter TDS than current tank holds.

    Delivers all remaining tank water to fields so the tank starts empty
    tomorrow morning for a fresh fill at the required TDS.

    Modifies tank in place.

    Args:
        tank: Mutable tank state dict.
        next_tds_req: Next day's crop TDS requirement (ppm).
        flush_reason: Current flush reason string.

    Returns:
        Tuple of (drain_vol, drain_tds, flush_reason).
    """
    if (tank['fill_m3'] > 0
            and not math.isnan(next_tds_req)
            and tank['tds_ppm'] > next_tds_req):
        drain_vol = tank['fill_m3']
        drain_tds = tank['tds_ppm']
        tank['fill_m3'] = 0.0
        tank['tds_ppm'] = 0.0
        if flush_reason == 'none':
            flush_reason = 'look_ahead_drain'
        return drain_vol, drain_tds, flush_reason
    return 0.0, 0.0, flush_reason


def _dispatch_day(demand_m3, tds_req, next_tds_req, wells, treatment, municipal,
                  tank, policy, gw_cap_state, muni_cap_state,
                  upcoming_demands=None, upcoming_tds=None):
    """Dispatch water through central mixing tank for a single day.

    Daily flow:
      1. Handle fallow days (with optional treatment smoothing).
      2. Safety flush if tank TDS exceeds today's requirement.
      3. Draw from existing tank stock to meet demand.
      4. Source the shortfall and draw from freshly sourced water.
      5. Second source+draw pass if demand exceeds single-pass throughput.
      6. Look-ahead prefill for upcoming peak days.
      7. Look-ahead drain if next day needs stricter TDS.

    Args:
        demand_m3: Total irrigation demand (m3).
        tds_req: Crop TDS requirement (ppm). NaN on fallow days.
        next_tds_req: Next day's crop TDS requirement (ppm). NaN if last
            day or next day is fallow.
        wells: List of well spec dicts from _load_well_specs.
        treatment: Dict with goal_output_tds_ppm, throughput_m3_hr, lookup_df.
        municipal: Dict with tds_ppm, cost_per_m3, throughput_m3_hr.
        tank: Dict with fill_m3, tds_ppm, capacity_m3.
        policy: Dict with strategy, prefill_enabled, prefill_look_ahead_days.
        gw_cap_state: Dict with monthly_cap, used, day, look_ahead.
        muni_cap_state: Dict with monthly_cap, used, day, look_ahead.
        upcoming_demands: List of demand_m3 values for next N days.
        upcoming_tds: List of TDS requirements for next N days.

    Returns:
        Tuple of (row_dict, updated_tank_dict).
    """
    strategy = policy['strategy']
    row = _init_dispatch_row(wells, tds_req, treatment['throughput_m3_hr'],
                             tank['fill_m3'], tank['tds_ppm'], strategy)

    # 1. Fallow day handling
    demand_m3, tds_req, early = _handle_fallow_day(
        demand_m3, tds_req, policy, treatment, row, gw_cap_state, upcoming_tds)
    if early:
        return row, tank

    tank = dict(tank)
    flush_vol = 0.0
    flush_tds = 0.0
    flush_reason = 'none'

    # 2. Safety flush: tank TDS exceeds today's requirement
    if tank['fill_m3'] > 0 and tank['tds_ppm'] > tds_req:
        flush_vol = tank['fill_m3']
        flush_tds = tank['tds_ppm']
        tank['fill_m3'] = 0.0
        tank['tds_ppm'] = 0.0
        flush_reason = 'tds_exceedance'

    # 3. Draw from existing tank water
    demand_remaining = max(0.0, demand_m3 - flush_vol)
    draw_existing = 0.0
    draw_existing_tds = 0.0
    if tank['fill_m3'] > 0 and tank['tds_ppm'] <= tds_req and demand_remaining > 0:
        draw_existing = min(demand_remaining, tank['fill_m3'])
        draw_existing_tds = tank['tds_ppm']
        tank['fill_m3'] -= draw_existing
        demand_remaining -= draw_existing
        if tank['fill_m3'] < 1e-9:
            tank['fill_m3'] = 0.0
            tank['tds_ppm'] = 0.0

    # 4. Source shortfall — strategy-dependent
    if strategy == 'maximize_treatment_efficiency':
        source_vol, treatment_on_today = _effective_treatment_target(
            policy['_treatment_target_m3'], tank, demand_remaining,
            policy['_max_source_m3'], policy.get('treatment_smoothing', {}),
            policy.get('_treatment_on', True))
        policy['_treatment_on'] = treatment_on_today
        source_priority = policy.get('treatment_smoothing', {}).get(
            'source_priority', 'minimize_cost')
    else:
        source_vol = demand_remaining
        source_priority = strategy

    if source_vol > 0:
        _source_water(source_vol, tds_req, wells, treatment, municipal,
                      tank, gw_cap_state, muni_cap_state, row, source_priority)

    if strategy == 'maximize_treatment_efficiency':
        row['treatment_target_m3'] = policy.get('_feed_target_m3', 0.0)
        row['treatment_on'] = policy.get('_treatment_on', True)

    # Draw remaining demand from tank (now contains fresh sourced water)
    draw_fresh = 0.0
    draw_fresh_tds = 0.0
    if demand_remaining > 0 and tank['fill_m3'] > 0:
        draw_fresh = min(demand_remaining, tank['fill_m3'])
        draw_fresh_tds = tank['tds_ppm']
        tank['fill_m3'] -= draw_fresh
        demand_remaining -= draw_fresh
        if tank['fill_m3'] < 1e-9:
            tank['fill_m3'] = 0.0
            tank['tds_ppm'] = 0.0

    # 5. Second source+draw pass
    demand_remaining, draw_fresh, draw_fresh_tds = _second_source_pass(
        demand_remaining, tds_req, wells, treatment, municipal,
        tank, gw_cap_state, muni_cap_state, row, source_priority,
        draw_fresh, draw_fresh_tds)

    # 6. Look-ahead prefill
    prefill_vol = 0.0
    if (strategy != 'maximize_treatment_efficiency'
            and policy.get('prefill_enabled', False)
            and upcoming_demands
            and tank['capacity_m3'] - tank['fill_m3'] > 1.0):
        prefill_vol = _prefill_tank(
            row, tank, wells, treatment, municipal,
            gw_cap_state, muni_cap_state, strategy,
            tds_req, upcoming_demands, upcoming_tds)
    row['prefill_m3'] = prefill_vol

    # Apply treatment efficiency curve
    efficiency_df = treatment.get('efficiency_df')
    if efficiency_df is not None and row['treatment_feed_m3'] > 0:
        max_feed = treatment['throughput_m3_hr'] * 24
        if max_feed > 0:
            util_pct = (row['treatment_feed_m3'] / max_feed) * 100
            idx = (efficiency_df['utilization_pct'] - util_pct).abs().idxmin()
            eff_row = efficiency_df.loc[idx]
            multiplier = eff_row['energy_multiplier']
            row['treatment_energy_kwh'] *= multiplier
            row['treatment_energy_multiplier'] = multiplier

    if strategy == 'maximize_treatment_efficiency':
        max_feed = treatment['throughput_m3_hr'] * 24
        row['treatment_utilization_pct'] = (
            row['treatment_feed_m3'] / max_feed * 100 if max_feed > 0 else 0.0)

    # 7. Look-ahead drain
    drain_vol, drain_tds, flush_reason = _look_ahead_drain(
        tank, next_tds_req, flush_reason)

    # Finalize delivery totals, energy/cost sums, and policy metadata
    deliveries = {
        'flush': (flush_vol, flush_tds),
        'draw_existing': (draw_existing, draw_existing_tds),
        'draw_fresh': (draw_fresh, draw_fresh_tds),
        'drain': (drain_vol, drain_tds),
    }
    _finalize_dispatch_row(row, tank, demand_m3, tds_req, flush_reason,
                           deliveries)

    return row, tank


# ---------------------------------------------------------------------------
# Internal helper — simulation loop
# ---------------------------------------------------------------------------

def _run_simulation(demand_df, wells, treatment, municipal, tank_init, policy,
                    gw_monthly_cap, muni_monthly_cap, look_ahead):
    """Run the daily dispatch loop over the full demand time series.

    Args:
        demand_df: DataFrame with columns day, total_demand_m3,
                   crop_tds_requirement_ppm.
        wells: List of well spec dicts.
        treatment: Dict with goal_output_tds_ppm, throughput_m3_hr, lookup_df.
        municipal: Dict with tds_ppm, cost_per_m3, throughput_m3_hr.
        tank_init: Dict with fill_m3, tds_ppm, capacity_m3.
        policy: Dict with strategy key.
        gw_monthly_cap: Monthly groundwater cap (m3) or None.
        muni_monthly_cap: Monthly municipal cap (m3) or None.
        look_ahead: Boolean for cap enforcement mode.

    Returns:
        DataFrame with all daily output columns.
    """
    tank = {
        'fill_m3': tank_init['fill_m3'],
        'tds_ppm': tank_init['tds_ppm'],
        'capacity_m3': tank_init['capacity_m3'],
    }
    gw_used_month = 0.0
    muni_used_month = 0.0
    current_month = None
    rows = []

    tds_col = demand_df['crop_tds_requirement_ppm'].values
    n_days = len(demand_df)

    # Pre-compute treatment target for smoothing strategy
    if policy.get('strategy') == 'maximize_treatment_efficiency':
        raw_gw_tds = _volume_weighted_tds(wells, sum(w['max_daily_m3'] for w in wells))
        smoothing_cfg = policy.get('treatment_smoothing', {})
        target_info = _compute_treatment_target(
            demand_df, raw_gw_tds, treatment, tank['capacity_m3'], smoothing_cfg)
        policy['_treatment_target_m3'] = target_info['source_target_m3']
        policy['_feed_target_m3'] = target_info['feed_target_m3']
        policy['_treatment_on'] = True
        # Max source volume: max feed converted to source-volume units
        max_daily_feed = treatment['throughput_m3_hr'] * 24
        f_treat = target_info['f_treat']
        rr = target_info['recovery_rate']
        policy['_max_source_m3'] = (
            max_daily_feed * rr / f_treat if f_treat > 0 else max_daily_feed)
        if max_daily_feed > 0:
            logger.info(
                'Treatment smoothing: feed target %.1f m3/day (%.0f%% utilization), '
                'source target %.1f m3/day',
                target_info['feed_target_m3'],
                target_info['feed_target_m3'] / max_daily_feed * 100,
                target_info['source_target_m3'])

    for i, (_, demand_row) in enumerate(demand_df.iterrows()):
        day = demand_row['day']

        if current_month != (day.year, day.month):
            current_month = (day.year, day.month)
            gw_used_month = 0.0
            muni_used_month = 0.0

        next_tds_req = float('nan')
        for j in range(i + 1, n_days):
            if not math.isnan(tds_col[j]):
                next_tds_req = tds_col[j]
                break

        prefill_days = policy.get('prefill_look_ahead_days', 0)
        # Smoothing needs a longer look-ahead for fallow horizon checks
        smoothing_horizon = policy.get('treatment_smoothing', {}).get(
            'fallow_horizon_days', 0)
        look_ahead_days = max(prefill_days, smoothing_horizon)

        upcoming_demands = []
        upcoming_tds = []
        if look_ahead_days > 0:
            for j in range(i + 1, min(i + 1 + look_ahead_days, n_days)):
                upcoming_demands.append(demand_df.iloc[j]['total_demand_m3'])
                upcoming_tds.append(tds_col[j])

        row, tank = _dispatch_day(
            demand_m3=demand_row['total_demand_m3'],
            tds_req=demand_row['crop_tds_requirement_ppm'],
            next_tds_req=next_tds_req,
            wells=wells,
            treatment=treatment,
            municipal=municipal,
            tank=tank,
            policy=policy,
            gw_cap_state={
                'monthly_cap': gw_monthly_cap,
                'used': gw_used_month,
                'day': day,
                'look_ahead': look_ahead,
            },
            muni_cap_state={
                'monthly_cap': muni_monthly_cap,
                'used': muni_used_month,
                'day': day,
                'look_ahead': look_ahead,
            },
            upcoming_demands=upcoming_demands,
            upcoming_tds=upcoming_tds,
        )
        row['day'] = day

        gw_used_month += row['total_groundwater_extracted_m3']
        muni_used_month += row['municipal_to_tank_m3']

        row['gw_cap_used_month_m3'] = gw_used_month
        row['muni_cap_used_month_m3'] = muni_used_month
        row['gw_monthly_cap_m3'] = gw_monthly_cap if gw_monthly_cap is not None else float('inf')
        row['muni_monthly_cap_m3'] = muni_monthly_cap if muni_monthly_cap is not None else float('inf')

        rows.append(row)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_water_supply(water_systems_path, registry_path, irrigation_demand_df, *,
                         water_policy_path=None, water_system_name='main_irrigation',
                         root_dir=None):
    """Compute daily water supply dispatch for a community irrigation system.

    Uses a central mixing tank model: all water sources pump into the storage
    tank, which mixes to a single TDS. Fields draw only from the tank.

    Args:
        water_systems_path: Path to water_systems.yaml.
        registry_path: Path to data_registry.yaml.
        irrigation_demand_df: DataFrame from src.irrigation_demand with columns
            day, total_demand_m3, crop_tds_requirement_ppm.
        water_policy_path: Path to water_policy.yaml. Uses defaults when None.
        water_system_name: Name of the system to simulate from the config.
        root_dir: Repository root. Defaults to parent of settings/.

    Returns:
        DataFrame with daily water supply columns: per-well extraction,
        source volumes into tank, treatment, municipal, TDS, energy,
        cost, tank state, and deficit.
    """
    if root_dir is None:
        root_dir = Path(registry_path).parent.parent

    ws_config = _load_yaml(water_systems_path)
    registry = _load_yaml(registry_path)
    paths = _resolve_water_paths(registry, root_dir)

    system = None
    for s in ws_config['systems']:
        if s['name'] == water_system_name:
            system = s
            break
    if system is None:
        raise ValueError(f"Water system '{water_system_name}' not found in config")

    pump_df = _load_csv(paths['pump_systems'])
    wells = _load_well_specs(system, pump_df)

    if 'treatment' in system:
        treatment_df = _load_treatment_lookup(paths['treatment_research'])
        efficiency_df = None
        if 'treatment_efficiency' in paths:
            efficiency_df = _load_csv(paths['treatment_efficiency'])
            efficiency_df = efficiency_df.sort_values('utilization_pct').reset_index(drop=True)
        treatment = {
            'goal_output_tds_ppm': system['treatment']['goal_output_tds_ppm'],
            'throughput_m3_hr': system['treatment']['throughput_m3_hr'],
            'lookup_df': treatment_df,
            'efficiency_df': efficiency_df,
        }
    else:
        treatment = {
            'goal_output_tds_ppm': 0,
            'throughput_m3_hr': 0,
            'lookup_df': None,
            'efficiency_df': None,
        }

    muni_cfg = system['municipal_source']
    municipal = {
        'tds_ppm': muni_cfg['tds_ppm'],
        'cost_per_m3': muni_cfg['cost_per_m3'],
        'throughput_m3_hr': muni_cfg['throughput_m3_hr'],
    }

    if 'storage' in system:
        stor = system['storage']
        tank_init = {
            'fill_m3': stor['initial_level_m3'],
            'tds_ppm': stor['initial_tds_ppm'],
            'capacity_m3': stor['capacity_m3'],
        }
    else:
        tank_init = {
            'fill_m3': 0.0,
            'tds_ppm': 0.0,
            'capacity_m3': float('inf'),
        }

    if water_policy_path is not None:
        pol_config = _load_yaml(water_policy_path)
        strategy = pol_config.get('strategy', 'minimize_cost')
        gw_monthly_cap = pol_config.get('groundwater', {}).get('monthly_cap_m3')
        muni_monthly_cap = pol_config.get('municipal', {}).get('monthly_cap_m3')
        look_ahead = pol_config.get('cap_enforcement', {}).get('look_ahead', True)
        prefill_cfg = pol_config.get('prefill', {})
    else:
        strategy = 'minimize_cost'
        gw_monthly_cap = None
        muni_monthly_cap = None
        look_ahead = True
        prefill_cfg = {}

    # Fall back from maximize_treatment_efficiency when no treatment is configured
    if strategy == 'maximize_treatment_efficiency' and treatment['lookup_df'] is None:
        logger.warning(
            'Strategy maximize_treatment_efficiency requires treatment config; '
            'falling back to minimize_cost.')
        strategy = 'minimize_cost'

    policy = {
        'strategy': strategy,
        'prefill_enabled': prefill_cfg.get('enabled', False),
        'prefill_look_ahead_days': prefill_cfg.get('look_ahead_days', 3),
    }

    # Treatment smoothing config (only used by maximize_treatment_efficiency)
    if strategy == 'maximize_treatment_efficiency':
        smoothing = (pol_config or {}).get('treatment_smoothing', {})
        policy['treatment_smoothing'] = {
            'source_priority': smoothing.get('source_priority', 'minimize_cost'),
            'fallow_treatment': smoothing.get('fallow_treatment', True),
            'fallow_horizon_days': smoothing.get('fallow_horizon_days', 14),
            'tank_feedback': smoothing.get('tank_feedback', {
                'high_mark': 0.90,
                'low_mark': 0.15,
            }),
        }

    df = _run_simulation(
        demand_df=irrigation_demand_df,
        wells=wells,
        treatment=treatment,
        municipal=municipal,
        tank_init=tank_init,
        policy=policy,
        gw_monthly_cap=gw_monthly_cap,
        muni_monthly_cap=muni_monthly_cap,
        look_ahead=look_ahead,
    )

    well_cols = []
    for w in wells:
        well_cols.append(f'{w["name"]}_extraction_m3')
        well_cols.append(f'{w["name"]}_tds_ppm')
        well_cols.append(f'{w["name"]}_pumping_kwh')

    agg_cols = [
        'gw_untreated_to_tank_m3', 'gw_treated_to_tank_m3',
        'municipal_to_tank_m3', 'total_sourced_to_tank_m3',
        'total_groundwater_extracted_m3',
        'sourced_tds_ppm',
        'treatment_feed_m3', 'treatment_max_feed_m3',
        'treatment_reject_m3', 'treatment_energy_kwh', 'pumping_energy_kwh',
        'municipal_cost', 'groundwater_cost', 'total_water_cost',
        'delivered_tds_ppm', 'crop_tds_requirement_ppm', 'tds_exceedance_ppm',
        'total_delivered_m3', 'tank_flush_delivered_m3',
        'safety_flush_m3', 'look_ahead_drain_m3',
        'deficit_m3',
        'tank_volume_m3', 'tank_tds_ppm', 'total_sourcing_energy_kwh',
        'policy_strategy', 'policy_primary_source', 'policy_flush_reason', 'policy_deficit',
        'gw_cap_used_month_m3', 'muni_cap_used_month_m3',
        'gw_monthly_cap_m3', 'muni_monthly_cap_m3',
        'prefill_m3',
        'treatment_target_m3', 'treatment_utilization_pct',
        'treatment_energy_multiplier', 'treatment_on',
    ]

    df = df[['day'] + well_cols + agg_cols]
    return df


# ---------------------------------------------------------------------------
# Entry point for quick verification
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    from src.irrigation_demand import compute_irrigation_demand

    root = Path(__file__).parent.parent
    demand_df = compute_irrigation_demand(
        farm_profiles_path=root / 'settings' / 'farm_profile_base.yaml',
        registry_path=root / 'settings' / 'data_registry_base.yaml',
    )
    df = compute_water_supply(
        water_systems_path=root / 'settings' / 'water_systems_base.yaml',
        registry_path=root / 'settings' / 'data_registry_base.yaml',
        irrigation_demand_df=demand_df,
        water_policy_path=root / 'settings' / 'water_policy_base.yaml',
    )
    print(f'Computed {len(df)} rows')
    print(f'Total delivered: {df["total_delivered_m3"].sum():.0f} m3')
    print(f'Total deficit: {df["deficit_m3"].sum():.0f} m3')
    print(f'Total energy: {df["total_sourcing_energy_kwh"].sum():.1f} kWh')
    flush_days = (df['tank_flush_delivered_m3'] > 0).sum()
    print(f'Tank flush days: {flush_days}')
    print(df.head(3).to_string())
