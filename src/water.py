"""Daily water supply simulation for community irrigation.

Dispatches groundwater extraction, BWRO treatment, municipal supplement, and
storage draw to meet daily irrigation demand at crop-required TDS levels.
Supports three blending strategies: minimize_cost, minimize_treatment,
and minimize_draw.

Usage:
    from src.water import compute_water_supply, save_water_supply

    df = compute_water_supply(
        water_systems_path='settings/water_systems_base.yaml',
        registry_path='settings/data_registry_base.yaml',
        irrigation_demand_df=demand_df,
        water_policy_path='settings/water_policy_base.yaml',
    )
    save_water_supply(df, output_dir='simulation/')
"""

import calendar
import math
import yaml
import numpy as np
import pandas as pd
from pathlib import Path


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
    where rho=1000 kg/m3, g=9.81 m/s2, 3_600_000 converts J to kWh.

    Args:
        volume_m3: Volume of water extracted (m3).
        depth_m: Well depth (meters).
        pump_efficiency: Combined pump+motor efficiency (fraction).

    Returns:
        Energy in kWh.
    """
    if volume_m3 <= 0:
        return 0.0
    return (1000 * 9.81 * depth_m * volume_m3) / (pump_efficiency * 3_600_000)


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
# Internal helpers — daily dispatch
# ---------------------------------------------------------------------------

def _dispatch_day(demand_m3, tds_req, wells, treatment, municipal, tank,
                  policy, gw_cap_state, muni_cap_state):
    """Dispatch water from all sources to meet a single day's demand.

    Args:
        demand_m3: Total irrigation demand (m3).
        tds_req: Crop TDS requirement (ppm). NaN on fallow days.
        wells: List of well spec dicts from _load_well_specs.
        treatment: Dict with keys: goal_output_tds_ppm, throughput_m3_hr.
        municipal: Dict with keys: tds_ppm, cost_per_m3, throughput_m3_hr.
        tank: Dict with keys: fill_m3, tds_ppm, capacity_m3,
              max_output_m3_hr.
        policy: Dict with keys: strategy.
        gw_cap_state: Dict with keys: monthly_cap, used, day, look_ahead.
        muni_cap_state: Dict with keys: monthly_cap, used, day, look_ahead.

    Returns:
        Tuple of (row_dict, updated_tank_dict).
    """
    strategy = policy['strategy']

    # Base output row — zeros everywhere
    row = {}
    for w in wells:
        row[f'{w["name"]}_extraction_m3'] = 0.0
        row[f'{w["name"]}_tds_ppm'] = w['tds_ppm']
    row.update({
        'total_groundwater_m3': 0.0,
        'treated_volume_m3': 0.0,
        'treatment_reject_m3': 0.0,
        'treatment_energy_kwh': 0.0,
        'pumping_energy_kwh': 0.0,
        'municipal_volume_m3': 0.0,
        'municipal_cost': 0.0,
        'groundwater_cost': 0.0,
        'total_water_cost': 0.0,
        'blended_tds_delivered_ppm': 0.0,
        'crop_tds_requirement_ppm': tds_req,
        'total_delivered_m3': 0.0,
        'deficit_m3': 0.0,
        'storage_level_m3': tank['fill_m3'],
        'storage_tds_ppm': tank['tds_ppm'],
        'total_energy_kwh': 0.0,
    })

    # Fallow day or zero demand — carry tank unchanged
    if demand_m3 <= 0 or math.isnan(tds_req):
        return row, tank

    tank = dict(tank)  # shallow copy for mutation
    remaining_demand = demand_m3

    if strategy == 'minimize_cost':
        remaining_demand, row, tank = _dispatch_minimize_cost(
            remaining_demand, tds_req, wells, treatment, municipal,
            tank, gw_cap_state, muni_cap_state, row,
        )
    elif strategy == 'minimize_treatment':
        remaining_demand, row, tank = _dispatch_minimize_treatment(
            remaining_demand, tds_req, wells, treatment, municipal,
            tank, gw_cap_state, muni_cap_state, row,
        )
    elif strategy == 'minimize_draw':
        remaining_demand, row, tank = _dispatch_minimize_draw(
            remaining_demand, tds_req, wells, treatment, municipal,
            tank, gw_cap_state, muni_cap_state, row,
        )

    row['deficit_m3'] = max(0.0, remaining_demand)
    row['total_energy_kwh'] = row['pumping_energy_kwh'] + row['treatment_energy_kwh']
    row['total_water_cost'] = row['municipal_cost'] + row['groundwater_cost']
    row['storage_level_m3'] = tank['fill_m3']
    row['storage_tds_ppm'] = tank['tds_ppm']

    return row, tank


def _draw_storage(remaining_demand, tds_req, tank, row):
    """Draw from storage if tank TDS meets crop requirement.

    Returns:
        Tuple of (remaining_demand, storage_volume_drawn, tank).
    """
    if tank['fill_m3'] <= 0 or tank['tds_ppm'] > tds_req:
        return remaining_demand, 0.0, tank
    max_draw = tank['max_output_m3_hr'] * 24
    draw = min(remaining_demand, tank['fill_m3'], max_draw)
    tank = dict(tank)
    tank['fill_m3'] -= draw
    if tank['fill_m3'] <= 0:
        tank['tds_ppm'] = 0.0
    remaining_demand -= draw
    return remaining_demand, draw, tank


def _groundwater_supply(remaining_demand, tds_req, wells, treatment,
                        gw_cap_state, row):
    """Compute groundwater extraction, treatment, and blending.

    Equal-draw across wells. Treats a fraction of GW to meet TDS target
    via blending treated + untreated product. Accounts for recovery loss
    in feed volume.

    Returns:
        Tuple of (gw_delivery_m3, treated_product_m3, untreated_m3,
                  total_extraction_m3, treatment_row, row).
    """
    if remaining_demand <= 0 or not wells:
        return 0.0, 0.0, 0.0, 0.0, None, row

    day = gw_cap_state['day']
    gw_allowance = _daily_cap_allowance(
        day, gw_cap_state['monthly_cap'], gw_cap_state['used'],
        gw_cap_state['look_ahead'],
    )
    if gw_allowance <= 0:
        return 0.0, 0.0, 0.0, 0.0, None, row

    n_wells = len(wells)
    total_well_capacity = sum(w['max_daily_m3'] for w in wells)
    gw_extraction_limit = min(total_well_capacity, gw_allowance)

    # Raw GW TDS (equal draw = simple mean)
    raw_gw_tds = sum(w['tds_ppm'] for w in wells) / n_wells
    goal_tds = treatment['goal_output_tds_ppm']

    if raw_gw_tds <= tds_req:
        # No treatment needed — deliver raw GW directly
        delivery = min(remaining_demand, gw_extraction_limit)
        extraction = delivery  # no recovery loss
        _assign_well_extraction(wells, extraction, row)
        return delivery, 0.0, delivery, extraction, None, row

    # Need treatment: compute fraction of product that must be treated
    if goal_tds >= tds_req:
        f_treat = 1.0  # treatment alone can't meet target; treat everything
    elif abs(raw_gw_tds - goal_tds) < 1e-9:
        f_treat = 1.0  # avoid division by zero; treat all, municipal will dilute if needed
    else:
        f_treat = (raw_gw_tds - tds_req) / (raw_gw_tds - goal_tds)
        f_treat = max(0.0, min(1.0, f_treat))

    # Load treatment parameters by snapping raw GW TDS
    treatment_row = _snap_tds_to_band(raw_gw_tds, treatment['lookup_df'])
    recovery_rate = treatment_row['recovery_rate_pct'] / 100.0

    # Iteratively find delivery that fits within extraction limit.
    # delivery = treated_product + untreated
    # extraction = treated_product / recovery_rate + untreated
    desired_delivery = remaining_demand
    treated_product = desired_delivery * f_treat
    untreated = desired_delivery * (1 - f_treat)
    feed_volume = treated_product / recovery_rate if recovery_rate > 0 else treated_product
    total_extraction = feed_volume + untreated

    if total_extraction > gw_extraction_limit:
        # Scale delivery down proportionally
        scale = gw_extraction_limit / total_extraction
        desired_delivery *= scale
        treated_product = desired_delivery * f_treat
        untreated = desired_delivery * (1 - f_treat)
        feed_volume = treated_product / recovery_rate if recovery_rate > 0 else treated_product
        total_extraction = feed_volume + untreated

    # Also respect treatment throughput
    max_treatment_m3 = treatment['throughput_m3_hr'] * 24  # product capacity
    if treated_product > max_treatment_m3:
        treated_product = max_treatment_m3
        feed_volume = treated_product / recovery_rate if recovery_rate > 0 else treated_product
        untreated = desired_delivery - treated_product
        if untreated < 0:
            untreated = 0.0
            desired_delivery = treated_product
        total_extraction = feed_volume + untreated
        if total_extraction > gw_extraction_limit:
            scale = gw_extraction_limit / total_extraction
            treated_product *= scale
            untreated *= scale
            feed_volume = treated_product / recovery_rate if recovery_rate > 0 else treated_product
            total_extraction = feed_volume + untreated
            desired_delivery = treated_product + untreated

    _assign_well_extraction(wells, total_extraction, row)
    return desired_delivery, treated_product, untreated, total_extraction, treatment_row, row


def _assign_well_extraction(wells, total_extraction, row):
    """Distribute total extraction equally across wells, respecting per-well capacity.

    When a well hits its capacity limit, the excess is redistributed to
    remaining uncapped wells. Returns the actual total extraction achieved
    (may be less than requested if all wells are at capacity).
    """
    remaining = total_extraction
    assigned = {w['name']: 0.0 for w in wells}
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
            break  # no new caps hit this round
        uncapped = still_uncapped

    for w in wells:
        row[f'{w["name"]}_extraction_m3'] = assigned[w['name']]


def _compute_gw_energy_and_cost(wells, treatment_row, treated_product, row):
    """Compute pumping energy, treatment energy, and groundwater cost.

    Updates row in place.
    """
    # Pumping energy
    total_pump_kwh = 0.0
    for w in wells:
        vol = row[f'{w["name"]}_extraction_m3']
        total_pump_kwh += _pumping_energy_kwh(vol, w['depth_m'], w['pump_efficiency'])
    row['pumping_energy_kwh'] = total_pump_kwh

    # Treatment energy and cost
    if treatment_row is not None and treated_product > 0:
        row['treatment_energy_kwh'] = treated_product * treatment_row['energy_kwh_per_m3']
        recovery_rate = treatment_row['recovery_rate_pct'] / 100.0
        feed_vol = treated_product / recovery_rate if recovery_rate > 0 else treated_product
        # Brine = inflow - treated outflow (mass balance)
        row['treatment_reject_m3'] = feed_vol - treated_product
        row['treated_volume_m3'] = treated_product
        row['groundwater_cost'] = treated_product * treatment_row['maintenance_cost_per_m3']
    else:
        row['treated_volume_m3'] = 0.0
        row['treatment_reject_m3'] = 0.0
        row['treatment_energy_kwh'] = 0.0
        row['groundwater_cost'] = 0.0


def _municipal_supplement(remaining_demand, municipal, muni_cap_state, row):
    """Supplement remaining demand with municipal water.

    Returns:
        Tuple of (remaining_demand, municipal_volume).
    """
    if remaining_demand <= 0:
        return remaining_demand, 0.0
    day = muni_cap_state['day']
    muni_allowance = _daily_cap_allowance(
        day, muni_cap_state['monthly_cap'], muni_cap_state['used'],
        muni_cap_state['look_ahead'],
    )
    max_muni = municipal['throughput_m3_hr'] * 24
    available = min(muni_allowance, max_muni)
    vol = min(remaining_demand, available)
    row['municipal_volume_m3'] = vol
    row['municipal_cost'] = vol * municipal['cost_per_m3']
    remaining_demand -= vol
    return remaining_demand, vol


# ---------------------------------------------------------------------------
# Strategy dispatchers
# ---------------------------------------------------------------------------

def _dispatch_minimize_cost(remaining, tds_req, wells, treatment, municipal,
                            tank, gw_cap_state, muni_cap_state, row):
    """Minimize cost: storage -> GW (treat as needed) -> municipal."""
    # 1. Storage draw
    remaining, storage_vol, tank = _draw_storage(remaining, tds_req, tank, row)

    # 2. Groundwater
    gw_delivery, treated_product, untreated, total_extraction, treat_row, row = \
        _groundwater_supply(remaining, tds_req, wells, treatment, gw_cap_state, row)
    remaining -= gw_delivery
    row['total_groundwater_m3'] = total_extraction
    _compute_gw_energy_and_cost(wells, treat_row, treated_product, row)

    # 3. Municipal supplement
    remaining, muni_vol = _municipal_supplement(remaining, municipal, muni_cap_state, row)

    # 4. Blended TDS
    delivered_volumes = [storage_vol, untreated, treated_product, muni_vol]
    raw_gw_tds = sum(w['tds_ppm'] for w in wells) / len(wells) if wells and untreated > 0 else 0.0
    delivered_tds = [
        tank['tds_ppm'] if storage_vol > 0 else 0.0,
        raw_gw_tds,
        treatment['goal_output_tds_ppm'] if treated_product > 0 else 0.0,
        municipal['tds_ppm'] if muni_vol > 0 else 0.0,
    ]
    # Use the pre-draw tank TDS for storage (already in row from initialization)
    storage_tds = row['storage_tds_ppm'] if storage_vol > 0 else 0.0
    delivered_tds[0] = storage_tds
    row['blended_tds_delivered_ppm'] = _blend_tds(delivered_volumes, delivered_tds)
    row['total_delivered_m3'] = sum(delivered_volumes)

    return remaining, row, tank


def _dispatch_minimize_treatment(remaining, tds_req, wells, treatment, municipal,
                                 tank, gw_cap_state, muni_cap_state, row):
    """Minimize treatment: storage -> untreated GW -> municipal -> treat remainder.

    Prefers untreated GW and municipal supplement before resorting to treatment.
    Only treats when untreated GW TDS exceeds target AND municipal cap is exhausted.
    """
    # 1. Storage draw
    remaining, storage_vol, tank = _draw_storage(remaining, tds_req, tank, row)

    raw_gw_tds = sum(w['tds_ppm'] for w in wells) / len(wells) if wells else 0.0

    # Groundwater allowance
    day = gw_cap_state['day']
    gw_allowance = _daily_cap_allowance(
        day, gw_cap_state['monthly_cap'], gw_cap_state['used'],
        gw_cap_state['look_ahead'],
    )
    total_well_capacity = sum(w['max_daily_m3'] for w in wells)
    gw_extraction_limit = min(total_well_capacity, gw_allowance)

    untreated_gw = 0.0
    treated_product = 0.0
    total_extraction = 0.0
    treat_row = None

    if remaining > 0 and raw_gw_tds <= tds_req and gw_extraction_limit > 0:
        # Use untreated GW directly (no treatment needed)
        untreated_gw = min(remaining, gw_extraction_limit)
        total_extraction = untreated_gw
        remaining -= untreated_gw
        _assign_well_extraction(wells, total_extraction, row)

    # 2. Municipal supplement before treatment
    muni_vol = 0.0
    if remaining > 0:
        remaining, muni_vol = _municipal_supplement(remaining, municipal, muni_cap_state, row)

    # 3. Treat only if still short
    if remaining > 0 and raw_gw_tds > tds_req and gw_extraction_limit > 0:
        goal_tds = treatment['goal_output_tds_ppm']
        if goal_tds >= tds_req:
            f_treat = 1.0
        elif abs(raw_gw_tds - goal_tds) < 1e-9:
            f_treat = 1.0  # avoid division by zero
        else:
            f_treat = (raw_gw_tds - tds_req) / (raw_gw_tds - goal_tds)
            f_treat = max(0.0, min(1.0, f_treat))

        treat_row = _snap_tds_to_band(raw_gw_tds, treatment['lookup_df'])
        recovery_rate = treat_row['recovery_rate_pct'] / 100.0

        desired = remaining
        tp = desired * f_treat
        ut = desired * (1 - f_treat)
        feed = tp / recovery_rate if recovery_rate > 0 else tp
        extraction_needed = feed + ut

        available_extraction = gw_extraction_limit - total_extraction
        if extraction_needed > available_extraction:
            scale = available_extraction / extraction_needed
            desired *= scale
            tp = desired * f_treat
            ut = desired * (1 - f_treat)
            feed = tp / recovery_rate if recovery_rate > 0 else tp
            extraction_needed = feed + ut

        max_treat = treatment['throughput_m3_hr'] * 24
        if tp > max_treat:
            tp = max_treat
            feed = tp / recovery_rate if recovery_rate > 0 else tp
            ut = desired - tp
            if ut < 0:
                ut = 0.0
                desired = tp
            extraction_needed = feed + ut
            if extraction_needed > available_extraction:
                scale = available_extraction / extraction_needed
                tp *= scale
                ut *= scale
                feed = tp / recovery_rate if recovery_rate > 0 else tp
                extraction_needed = feed + ut
                desired = tp + ut

        treated_product = tp
        untreated_gw += ut
        total_extraction += extraction_needed
        remaining -= desired
        _assign_well_extraction(wells, total_extraction, row)

    row['total_groundwater_m3'] = total_extraction
    _compute_gw_energy_and_cost(wells, treat_row, treated_product, row)

    # Blended TDS
    storage_tds = row['storage_tds_ppm'] if storage_vol > 0 else 0.0
    delivered_volumes = [storage_vol, untreated_gw, treated_product, muni_vol]
    delivered_tds = [
        storage_tds,
        raw_gw_tds if untreated_gw > 0 else 0.0,
        treatment['goal_output_tds_ppm'] if treated_product > 0 else 0.0,
        municipal['tds_ppm'] if muni_vol > 0 else 0.0,
    ]
    row['blended_tds_delivered_ppm'] = _blend_tds(delivered_volumes, delivered_tds)
    row['total_delivered_m3'] = sum(delivered_volumes)

    return remaining, row, tank


def _dispatch_minimize_draw(remaining, tds_req, wells, treatment, municipal,
                            tank, gw_cap_state, muni_cap_state, row):
    """Minimize draw: storage -> municipal -> GW (treat as needed)."""
    # 1. Storage draw
    remaining, storage_vol, tank = _draw_storage(remaining, tds_req, tank, row)

    # 2. Municipal first
    muni_vol = 0.0
    if remaining > 0:
        remaining, muni_vol = _municipal_supplement(remaining, municipal, muni_cap_state, row)

    # 3. Groundwater to cover remainder
    gw_delivery, treated_product, untreated, total_extraction, treat_row, row = \
        _groundwater_supply(remaining, tds_req, wells, treatment, gw_cap_state, row)
    remaining -= gw_delivery
    row['total_groundwater_m3'] = total_extraction
    _compute_gw_energy_and_cost(wells, treat_row, treated_product, row)

    # 4. Blended TDS
    storage_tds = row['storage_tds_ppm'] if storage_vol > 0 else 0.0
    raw_gw_tds = sum(w['tds_ppm'] for w in wells) / len(wells) if wells else 0.0
    delivered_volumes = [storage_vol, untreated, treated_product, muni_vol]
    delivered_tds = [
        storage_tds,
        raw_gw_tds if untreated > 0 else 0.0,
        treatment['goal_output_tds_ppm'] if treated_product > 0 else 0.0,
        municipal['tds_ppm'] if muni_vol > 0 else 0.0,
    ]
    row['blended_tds_delivered_ppm'] = _blend_tds(delivered_volumes, delivered_tds)
    row['total_delivered_m3'] = sum(delivered_volumes)

    return remaining, row, tank


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
        tank_init: Dict with fill_m3, tds_ppm, capacity_m3, max_output_m3_hr.
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
        'max_output_m3_hr': tank_init['max_output_m3_hr'],
    }
    gw_used_month = 0.0
    muni_used_month = 0.0
    current_month = None
    rows = []

    for _, demand_row in demand_df.iterrows():
        day = demand_row['day']

        # Reset monthly counters on new month
        if current_month != (day.year, day.month):
            current_month = (day.year, day.month)
            gw_used_month = 0.0
            muni_used_month = 0.0

        row, tank = _dispatch_day(
            demand_m3=demand_row['total_demand_m3'],
            tds_req=demand_row['crop_tds_requirement_ppm'],
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
        )
        row['day'] = day
        rows.append(row)

        gw_used_month += row['total_groundwater_m3']
        muni_used_month += row['municipal_volume_m3']

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_water_supply(water_systems_path, registry_path, irrigation_demand_df, *,
                         water_policy_path=None, water_system_name='main_irrigation',
                         root_dir=None):
    """Compute daily water supply dispatch for a community irrigation system.

    Combines water system configuration (wells, treatment, municipal source,
    storage) with irrigation demand to simulate daily water dispatch including
    groundwater extraction, BWRO treatment, municipal supplement, and storage
    draw. Supports multiple blending strategies.

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
        treatment volumes, municipal supplement, blended TDS, energy,
        cost, storage state, and deficit.
    """
    if root_dir is None:
        root_dir = Path(registry_path).parent.parent

    # Load configs
    ws_config = _load_yaml(water_systems_path)
    registry = _load_yaml(registry_path)
    paths = _resolve_water_paths(registry, root_dir)

    # Find the named system
    system = None
    for s in ws_config['systems']:
        if s['name'] == water_system_name:
            system = s
            break
    assert system is not None, f"Water system '{water_system_name}' not found in config"

    # Load pump specs, merge with well configs
    pump_df = _load_csv(paths['pump_systems'])
    wells = _load_well_specs(system, pump_df)

    # Load treatment lookup (research CSV with numeric tds_ppm)
    treatment_df = _load_treatment_lookup(paths['treatment_research'])
    treatment = {
        'goal_output_tds_ppm': system['treatment']['goal_output_tds_ppm'],
        'throughput_m3_hr': system['treatment']['throughput_m3_hr'],
        'lookup_df': treatment_df,
    }

    # Municipal source config
    muni_cfg = system['municipal_source']
    municipal = {
        'tds_ppm': muni_cfg['tds_ppm'],
        'cost_per_m3': muni_cfg['cost_per_m3'],
        'throughput_m3_hr': muni_cfg['throughput_m3_hr'],
    }

    # Storage initial state
    stor = system['storage']
    tank_init = {
        'fill_m3': stor['initial_level_m3'],
        'tds_ppm': stor['initial_tds_ppm'],
        'capacity_m3': stor['capacity_m3'],
        'max_output_m3_hr': stor['max_output_m3_hr'],
    }

    # Load policy; caps come only from policy, not from water_systems
    if water_policy_path is not None:
        pol_config = _load_yaml(water_policy_path)
        strategy = pol_config.get('strategy', 'minimize_cost')
        gw_monthly_cap = pol_config.get('groundwater', {}).get('monthly_cap_m3')
        muni_monthly_cap = pol_config.get('municipal', {}).get('monthly_cap_m3')
        look_ahead = pol_config.get('cap_enforcement', {}).get('look_ahead', True)
    else:
        strategy = 'minimize_cost'
        gw_monthly_cap = None
        muni_monthly_cap = None
        look_ahead = True

    policy = {'strategy': strategy}

    # Run simulation
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

    # Reorder columns: day first, then per-well, then aggregates
    well_cols = []
    for w in wells:
        well_cols.append(f'{w["name"]}_extraction_m3')
        well_cols.append(f'{w["name"]}_tds_ppm')

    agg_cols = [
        'total_groundwater_m3', 'treated_volume_m3', 'treatment_reject_m3',
        'treatment_energy_kwh', 'pumping_energy_kwh',
        'municipal_volume_m3', 'municipal_cost', 'groundwater_cost',
        'total_water_cost', 'blended_tds_delivered_ppm',
        'crop_tds_requirement_ppm', 'total_delivered_m3', 'deficit_m3',
        'storage_level_m3', 'storage_tds_ppm', 'total_energy_kwh',
    ]

    df = df[['day'] + well_cols + agg_cols]
    return df


def save_water_supply(df, output_dir, *, filename='daily_water_supply.csv', decimals=3):
    """Save daily water supply DataFrame to CSV.

    Args:
        df: DataFrame returned by compute_water_supply.
        output_dir: Directory to write the output file. Created if needed.
        filename: Output file name.
        decimals: Decimal places for numeric columns.

    Returns:
        Path to the saved CSV file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    df.round(decimals).to_csv(path, index=False)
    return path


def load_water_supply(path):
    """Load a saved water supply CSV produced by save_water_supply.

    Args:
        path: Path to the water supply CSV file.

    Returns:
        DataFrame with the same structure as compute_water_supply output.
    """
    return pd.read_csv(path, parse_dates=['day'])


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
    out = save_water_supply(df, output_dir=root / 'simulation')
    print(f'Saved {len(df)} rows to {out}')
    print(f'Total delivered: {df["total_delivered_m3"].sum():.0f} m3')
    print(f'Total deficit: {df["deficit_m3"].sum():.0f} m3')
    print(f'Total energy: {df["total_energy_kwh"].sum():.1f} kWh')
    print(df.head(3).to_string())
