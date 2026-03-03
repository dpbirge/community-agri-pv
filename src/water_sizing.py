"""Water system sizing and treatment-anchored optimization.

Provides two public entry points:

    size_water_system — sizes all components (wells, treatment, storage,
        municipal) from scratch given a demand profile and objective.

    optimize_water_system — takes a fixed treatment throughput as input
        and sizes wells, storage, and municipal around it, using a BWRO
        efficiency curve to target the treatment plant's sweet spot.

Both functions validate their recommendations by running the full daily
simulation and iterating if deficit exceeds the target.

Usage:
    from src.water_sizing import size_water_system, optimize_water_system

    # Size everything from scratch
    result = size_water_system(demand_df, registry_path)

    # Optimize around a fixed 50 m3/hr treatment plant
    result = optimize_water_system(
        demand_df, registry_path,
        treatment_throughput_m3_hr=50,
    )
"""

import logging
import pandas as pd
from pathlib import Path

from src.water import (
    _load_yaml, _load_csv, _resolve_water_paths,
    _load_well_specs, _load_treatment_lookup,
    _snap_tds_to_band, _blend_tds,
    _run_simulation,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SIZING_GOAL_TDS = 400  # BWRO standard output quality (ppm)
_SIZING_MIN_STORAGE_M3 = 50
_SIZING_MAX_STORAGE_M3 = 2000
_SIZING_MUNICIPAL_DEFAULTS = {'tds_ppm': 200, 'cost_per_m3': 0.50, 'throughput_m3_hr': 200}
_SIZING_DISPATCH = {
    'minimize_cost': 'minimize_cost',
    'minimize_energy': 'minimize_cost',
    'minimize_draw': 'minimize_draw',
}

_SWEET_SPOT_LOW = 70   # Lower bound of optimal utilization (%)
_SWEET_SPOT_HIGH = 85  # Upper bound of optimal utilization (%)


# ---------------------------------------------------------------------------
# Internal helpers — demand analysis
# ---------------------------------------------------------------------------

def _analyze_demand(demand_df):
    """Extract demand profile statistics for system sizing (Step 1).

    Uses p90 threshold for consecutive peak day detection (not p75) to
    capture true demand spikes rather than seasonal baselines. Caps at
    14 days since storage tanks buffer short peaks, not whole seasons.

    Args:
        demand_df: DataFrame with day, total_demand_m3, crop_tds_requirement_ppm.

    Returns:
        Dict with peak/avg/p95 daily demand, peak monthly demand,
        strictest TDS, and consecutive peak days.
    """
    active = demand_df[demand_df['total_demand_m3'] > 0]
    if len(active) == 0:
        return {
            'peak_daily_demand_m3': 0.0, 'avg_daily_demand_m3': 0.0,
            'p95_daily_demand_m3': 0.0, 'peak_monthly_demand_m3': 0.0,
            'strictest_tds_ppm': float('inf'), 'consecutive_peak_days': 1,
        }

    p90 = active['total_demand_m3'].quantile(0.90)
    above = (demand_df['total_demand_m3'] > p90).values
    max_run, run = 0, 0
    for v in above:
        if v:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 0

    monthly = demand_df.set_index('day').resample('MS')['total_demand_m3'].sum()
    tds = demand_df['crop_tds_requirement_ppm'].dropna()

    return {
        'peak_daily_demand_m3': float(demand_df['total_demand_m3'].max()),
        'avg_daily_demand_m3': float(active['total_demand_m3'].mean()),
        'p95_daily_demand_m3': float(active['total_demand_m3'].quantile(0.95)),
        'peak_monthly_demand_m3': float(monthly.max()),
        'strictest_tds_ppm': float(tds.min()) if len(tds) > 0 else float('inf'),
        'consecutive_peak_days': min(max(max_run, 1), 14),
    }


# ---------------------------------------------------------------------------
# Internal helpers — feed factor and well selection
# ---------------------------------------------------------------------------

def _compute_feed_factor(blended_tds, strictest_tds, goal_tds, treatment_df):
    """Compute extraction-to-delivery conversion factor (Step 2).

    The feed factor converts delivery volume to extraction volume, accounting
    for the fraction of water that must be treated and the brine loss from
    treatment.

    Args:
        blended_tds: Volume-weighted TDS of all selected wells (ppm).
        strictest_tds: Minimum crop TDS requirement (ppm).
        goal_tds: BWRO treatment output TDS target (ppm).
        treatment_df: Treatment lookup DataFrame for recovery rates.

    Returns:
        Tuple of (feed_factor, f_treat, treatment_row_or_None).
    """
    if blended_tds <= strictest_tds:
        return 1.0, 0.0, None

    if goal_tds >= strictest_tds or abs(blended_tds - goal_tds) < 1e-9:
        f_treat = 1.0
    else:
        f_treat = (blended_tds - strictest_tds) / (blended_tds - goal_tds)
        f_treat = max(0.0, min(1.0, f_treat))

    row = _snap_tds_to_band(blended_tds, treatment_df)
    recovery = row['recovery_rate_pct'] / 100.0
    ff = f_treat / recovery + (1.0 - f_treat)
    return ff, f_treat, row


def _match_pump(depth_m, pump_df):
    """Find cheapest pump that can handle a given well depth.

    Args:
        depth_m: Well depth in meters.
        pump_df: Pump catalog DataFrame with max_depth_m and capital_cost columns.

    Returns:
        Series for the cheapest eligible pump, or None if no pump can handle the depth.
    """
    eligible = pump_df[(pump_df['max_depth_m'] >= depth_m) & (pump_df['max_depth_m'] > 0)]
    if eligible.empty:
        return None
    return eligible.loc[eligible['capital_cost'].idxmin()]


def _build_well_candidates(well_df, pump_df):
    """Build candidate list from well and pump catalogs.

    Each candidate combines a well catalog row with its cheapest matching pump.
    Effective daily flow is min(aquifer yield, pump capacity).

    Returns:
        List of candidate dicts.
    """
    candidates = []
    for _, row in well_df.iterrows():
        pump = _match_pump(row['well_depth_m'], pump_df)
        if pump is None:
            continue
        effective_flow = min(row['flow_rate_m3_day'], pump['rated_flow_m3_hr'] * 24)
        candidates.append({
            'depth_m': int(row['well_depth_m']),
            'tds_ppm': int(row['tds_ppm']),
            'flow_m3_day': effective_flow,
            'well_capital': float(row['capital_cost_per_well']),
            'well_om': float(row['om_cost_per_year']),
            'pump_type': pump['pump_type'],
            'pump_efficiency': float(pump['pump_efficiency']),
            'pump_capital': float(pump['capital_cost']),
            'pump_om': float(pump['om_cost_per_year']),
        })
    return candidates


def _sort_well_candidates(cdf, objective):
    """Sort well candidate DataFrame by objective priority.

    minimize_energy: shallow first (low pumping energy, low TDS), highest flow.
    minimize_cost: best capital cost per m3/day capacity.
    minimize_draw: highest flow first (fewest wells needed).
    """
    if objective == 'minimize_energy':
        return cdf.sort_values(['depth_m', 'flow_m3_day'], ascending=[True, False])
    elif objective == 'minimize_cost':
        cdf = cdf.copy()
        cdf['_cost_eff'] = (cdf['well_capital'] + cdf['pump_capital']) / cdf['flow_m3_day']
        return cdf.sort_values(['_cost_eff', 'depth_m'])
    else:  # minimize_draw — shallow wells for low-TDS backup
        return cdf.sort_values(['depth_m', 'flow_m3_day'], ascending=[True, False])


def _select_wells(well_df, pump_df, target_delivery_m3, strictest_tds, goal_tds,
                  treatment_df, max_wells, objective):
    """Greedy well selection from catalogs (Steps 2-3).

    Adds wells one at a time until total extraction capacity meets
    target_delivery * feed_factor. Feed factor is recomputed after each
    addition because adding deeper wells increases blended TDS and thus
    the treatment fraction and brine loss overhead.

    Args:
        well_df: Well catalog DataFrame.
        pump_df: Pump catalog DataFrame.
        target_delivery_m3: Daily delivery target (m3).
        strictest_tds: Minimum crop TDS requirement.
        goal_tds: Treatment output TDS target.
        treatment_df: Treatment lookup DataFrame.
        max_wells: Maximum number of wells.
        objective: Sizing objective.

    Returns:
        Tuple of (selected_wells, feed_factor, f_treat, blended_tds).
    """
    raw = _build_well_candidates(well_df, pump_df)
    if not raw:
        return [], 1.0, 0.0, 0.0

    cdf = _sort_well_candidates(pd.DataFrame(raw), objective)

    selected = []
    ff, ft, bt = 1.0, 0.0, 0.0
    for _, cand in cdf.iterrows():
        if len(selected) >= max_wells:
            break
        selected.append(cand.to_dict())
        total_flow = sum(s['flow_m3_day'] for s in selected)
        bt = _blend_tds(
            [s['flow_m3_day'] for s in selected],
            [s['tds_ppm'] for s in selected],
        )
        ff, ft, _ = _compute_feed_factor(bt, strictest_tds, goal_tds, treatment_df)
        if total_flow >= target_delivery_m3 * ff:
            break

    for i, w in enumerate(selected):
        w['name'] = f'well_{i + 1}'
    return selected, ff, ft, bt


# ---------------------------------------------------------------------------
# Internal helpers — component sizing
# ---------------------------------------------------------------------------

def _size_storage(demand_analysis, feed_factor, storage_df, objective,
                  well_delivery_m3_day=0.0):
    """Size storage tank based on demand peak-to-average gap (Step 5).

    Buffer capacity absorbs the difference between peak and average demand
    over consecutive-peak-day stretches, allowing wells to be sized for
    average rather than peak throughput. For minimize_draw, storage is
    scaled down proportionally to the GW contribution since municipal
    handles most demand on-demand without buffering.

    Args:
        demand_analysis: Dict from _analyze_demand.
        feed_factor: Extraction-to-delivery factor.
        storage_df: Storage catalog DataFrame.
        objective: Sizing objective.
        well_delivery_m3_day: Well delivery capacity after treatment losses.
            Used to scale storage for minimize_draw.

    Returns:
        Dict with storage_type, capacity_m3, capital_cost, om_cost_per_year.
    """
    peak = demand_analysis['peak_daily_demand_m3']
    avg = demand_analysis['avg_daily_demand_m3']
    buffer_days = demand_analysis['consecutive_peak_days']

    raw = buffer_days * (peak - avg) * feed_factor

    # For minimize_draw, storage only buffers the GW backup contribution.
    # Municipal delivers on-demand and doesn't need tank buffering.
    if objective == 'minimize_draw' and peak > 0:
        gw_share = min(1.0, well_delivery_m3_day / peak)
        raw *= gw_share

    capacity = round(max(_SIZING_MIN_STORAGE_M3, min(_SIZING_MAX_STORAGE_M3, raw)))

    # underground = lowest evaporation (2%) / highest CAPEX
    # reservoir = cheapest / highest evaporation (15%)
    preferred = 'underground_tank' if objective == 'minimize_energy' else 'reservoir'
    row = storage_df[storage_df['storage_type'] == preferred].iloc[0]

    return {
        'storage_type': preferred,
        'capacity_m3': capacity,
        'capital_cost': row['capital_cost_per_m3'] * capacity,
        'om_cost_per_year': row['om_cost_per_m3_per_year'] * capacity,
    }


def _size_municipal(demand_analysis, well_delivery_m3_day, municipal_available, objective):
    """Determine municipal supplement parameters (Step 6).

    Returns:
        Dict with tds_ppm, cost_per_m3, throughput_m3_hr.
    """
    cfg = dict(_SIZING_MUNICIPAL_DEFAULTS)
    if not municipal_available:
        cfg['throughput_m3_hr'] = 0
        return cfg

    peak = demand_analysis['peak_daily_demand_m3']
    daily_gap = max(0.0, peak - well_delivery_m3_day)

    if objective == 'minimize_draw':
        cfg['throughput_m3_hr'] = max(cfg['throughput_m3_hr'], peak * 0.8 / 24)
    elif daily_gap > 0:
        cfg['throughput_m3_hr'] = max(cfg['throughput_m3_hr'], daily_gap / 24)

    return cfg


# ---------------------------------------------------------------------------
# Internal helpers — config assembly and validation
# ---------------------------------------------------------------------------

def _build_sizing_config(wells, treatment_throughput_m3_hr, goal_tds,
                         municipal_cfg, storage, system_name='main_irrigation'):
    """Assemble water_systems YAML-compatible config dict from sizing results.

    Args:
        wells: List of selected well dicts with name, depth_m, tds_ppm, pump_type.
        treatment_throughput_m3_hr: Treatment plant capacity (m3/hr).
        goal_tds: Treatment output TDS target (ppm).
        municipal_cfg: Municipal source config dict.
        storage: Storage dict with storage_type and capacity_m3.
        system_name: Name for the water system entry.

    Returns:
        Dict compatible with water_systems YAML format.
    """
    return {
        'config_name': 'sized_water_system',
        'systems': [{
            'name': system_name,
            'wells': [
                {'name': w['name'], 'depth_m': w['depth_m'],
                 'tds_ppm': w['tds_ppm'], 'pump_type': w['pump_type']}
                for w in wells
            ],
            'treatment': {
                'type': 'bwro',
                'throughput_m3_hr': float(round(treatment_throughput_m3_hr, 1)),
                'goal_output_tds_ppm': goal_tds,
            },
            'municipal_source': municipal_cfg,
            'storage': {
                'type': storage['storage_type'],
                'capacity_m3': storage['capacity_m3'],
                'initial_level_m3': round(storage['capacity_m3'] * 0.5),
                'max_output_m3_hr': 50,
                'initial_tds_ppm': goal_tds,
            },
        }],
    }


def _run_sizing_simulation(config, demand_df, pump_df, treatment_df, strategy):
    """Run water supply simulation from a config dict (no file I/O).

    Builds internal data structures from the config and calls _run_simulation
    directly, bypassing the YAML loading path.

    Args:
        config: water_systems config dict from _build_sizing_config.
        demand_df: Irrigation demand DataFrame with day, total_demand_m3,
            crop_tds_requirement_ppm.
        pump_df: Pump catalog DataFrame.
        treatment_df: Treatment lookup DataFrame.
        strategy: Dispatch strategy string.

    Returns:
        DataFrame with all daily simulation output columns.
    """
    system = config['systems'][0]
    wells = _load_well_specs(system, pump_df)
    treatment = {
        'goal_output_tds_ppm': system['treatment']['goal_output_tds_ppm'],
        'throughput_m3_hr': system['treatment']['throughput_m3_hr'],
        'lookup_df': treatment_df,
    }
    muni = system['municipal_source']
    municipal = {
        'tds_ppm': muni['tds_ppm'],
        'cost_per_m3': muni['cost_per_m3'],
        'throughput_m3_hr': muni['throughput_m3_hr'],
    }
    stor = system['storage']
    tank_init = {
        'fill_m3': stor['initial_level_m3'],
        'tds_ppm': stor['initial_tds_ppm'],
        'capacity_m3': stor['capacity_m3'],
    }
    return _run_simulation(
        demand_df=demand_df, wells=wells, treatment=treatment,
        municipal=municipal, tank_init=tank_init,
        policy={'strategy': strategy},
        gw_monthly_cap=None, muni_monthly_cap=None, look_ahead=True,
    )


def _compute_sizing_metrics(sim_df, demand_df, wells, storage,
                            treatment_throughput, treatment_df, blended_tds):
    """Extract performance metrics from sizing validation simulation (Step 7).

    Returns:
        Dict with deficit_fraction, cost/energy per m3, source fractions,
        brine loss, total_capex, and annual_opex.
    """
    total_demand = demand_df['total_demand_m3'].sum()
    total_delivered = sim_df['total_delivered_m3'].sum()
    total_gw = sim_df['total_groundwater_extracted_m3'].sum()
    total_muni = sim_df['municipal_to_tank_m3'].sum()
    total_treated = sim_df['gw_treated_to_tank_m3'].sum()
    total_reject = sim_df['treatment_reject_m3'].sum()
    total_cost = sim_df['total_water_cost'].sum()
    total_energy = sim_df['total_energy_kwh'].sum()

    # CAPEX: wells + pumps + treatment plant + storage
    well_capex = sum(w['well_capital'] + w['pump_capital'] for w in wells)
    if blended_tds > 0 and treatment_throughput > 0:
        treat_row = _snap_tds_to_band(blended_tds, treatment_df)
        treatment_capex = treat_row['capital_cost_per_m3_day'] * treatment_throughput * 24
    else:
        treatment_capex = 0.0
    total_capex = well_capex + treatment_capex + storage['capital_cost']

    # Annual OPEX: well maintenance + storage maintenance + sim costs
    # Sim total_water_cost already includes pump O&M + treatment maintenance + municipal
    well_om = sum(w['well_om'] for w in wells)
    sim_years = len(demand_df) / 365.25
    annual_sim_cost = total_cost / sim_years if sim_years > 0 else 0.0

    return {
        'deficit_fraction': sim_df['deficit_m3'].sum() / total_demand if total_demand > 0 else 0.0,
        'cost_per_m3_delivered': total_cost / total_delivered if total_delivered > 0 else 0.0,
        'energy_per_m3_delivered': total_energy / total_delivered if total_delivered > 0 else 0.0,
        'gw_fraction': total_gw / total_delivered if total_delivered > 0 else 0.0,
        'municipal_fraction': total_muni / total_delivered if total_delivered > 0 else 0.0,
        'treatment_fraction': total_treated / total_delivered if total_delivered > 0 else 0.0,
        'brine_loss_fraction': total_reject / total_gw if total_gw > 0 else 0.0,
        'total_capex': round(total_capex, 2),
        'annual_opex': round(well_om + storage['om_cost_per_year'] + annual_sim_cost, 2),
    }


# ---------------------------------------------------------------------------
# Internal helpers — efficiency curve
# ---------------------------------------------------------------------------

def _load_efficiency_curve(path):
    """Load treatment efficiency curve CSV.

    Args:
        path: Path to treatment_efficiency_curve CSV.

    Returns:
        DataFrame sorted by utilization_pct for nearest-snap lookup.
    """
    df = _load_csv(path)
    return df.sort_values('utilization_pct').reset_index(drop=True)


def _snap_utilization(utilization_pct, efficiency_df):
    """Find the efficiency curve row closest to the given utilization.

    Args:
        utilization_pct: Current utilization as percentage (0-100+).
        efficiency_df: DataFrame from _load_efficiency_curve.

    Returns:
        Series (single row) for the nearest utilization band.
    """
    idx = (efficiency_df['utilization_pct'] - utilization_pct).abs().idxmin()
    return efficiency_df.loc[idx]


def _apply_efficiency_adjustment(sim_df, treatment_throughput_m3_hr, efficiency_df):
    """Post-process simulation output with utilization-based multipliers.

    Adjusts treatment_energy_kwh and groundwater_cost columns based on
    daily treatment utilization. Also adjusts total_energy_kwh and
    total_water_cost to stay consistent.

    Args:
        sim_df: DataFrame from _run_sizing_simulation.
        treatment_throughput_m3_hr: Rated treatment capacity (m3/hr).
        efficiency_df: DataFrame from _load_efficiency_curve.

    Returns:
        DataFrame with adjusted energy and cost columns.
    """
    df = sim_df.copy()
    max_feed_m3 = treatment_throughput_m3_hr * 24

    if max_feed_m3 <= 0 or efficiency_df is None:
        return df

    for i in df.index:
        feed = df.at[i, 'treatment_feed_m3']
        if feed <= 0:
            continue

        util_pct = (feed / max_feed_m3) * 100
        eff_row = _snap_utilization(util_pct, efficiency_df)

        # Adjust treatment energy
        old_energy = df.at[i, 'treatment_energy_kwh']
        new_energy = old_energy * eff_row['energy_multiplier']
        energy_delta = new_energy - old_energy
        df.at[i, 'treatment_energy_kwh'] = new_energy
        df.at[i, 'total_energy_kwh'] += energy_delta

        # Adjust maintenance cost within groundwater_cost
        # groundwater_cost includes pumping O&M + treatment maintenance
        # We adjust the treatment maintenance portion only
        treated_product = df.at[i, 'gw_treated_to_tank_m3']
        if treated_product > 0 and 'treatment_energy_kwh' in df.columns:
            # Estimate base maintenance from the treatment lookup band
            # The multiplier scales the maintenance portion of gw cost
            maint_mult = eff_row['maintenance_multiplier']
            if maint_mult != 1.0:
                # Approximate maintenance cost = treated_product * base_rate
                # We don't have the exact base rate here, but we know the
                # multiplier shift. Apply it as a fraction of gw cost.
                old_gw_cost = df.at[i, 'groundwater_cost']
                # Maintenance is typically ~40-60% of groundwater_cost on
                # treatment-heavy days. Use treatment fraction as proxy.
                total_sourced = df.at[i, 'total_sourced_to_tank_m3']
                treat_fraction = treated_product / total_sourced if total_sourced > 0 else 0.0
                maint_portion = old_gw_cost * treat_fraction
                cost_delta = maint_portion * (maint_mult - 1.0)
                df.at[i, 'groundwater_cost'] += cost_delta
                df.at[i, 'total_water_cost'] += cost_delta

    return df


# ---------------------------------------------------------------------------
# Internal helpers — treatment-anchored well selection
# ---------------------------------------------------------------------------

def _select_wells_for_treatment(well_df, pump_df, treatment_feed_target_m3,
                                strictest_tds, goal_tds, treatment_df,
                                max_wells, objective):
    """Select wells to feed a fixed treatment plant at target utilization.

    Unlike _select_wells which targets delivery volume (delivery * feed_factor),
    this targets extraction volume to supply the treatment plant at its optimal
    operating point.

    Args:
        well_df: Well catalog DataFrame.
        pump_df: Pump catalog DataFrame.
        treatment_feed_target_m3: Daily extraction volume target (m3). Typically
            throughput_m3_hr * 24 * target_utilization.
        strictest_tds: Minimum crop TDS requirement (ppm).
        goal_tds: Treatment output TDS target (ppm).
        treatment_df: Treatment lookup DataFrame.
        max_wells: Maximum number of wells.
        objective: Sizing objective for sort order.

    Returns:
        Tuple of (selected_wells, feed_factor, f_treat, blended_tds).
    """
    raw = _build_well_candidates(well_df, pump_df)
    if not raw:
        return [], 1.0, 0.0, 0.0

    cdf = _sort_well_candidates(pd.DataFrame(raw), objective)

    selected = []
    ff, ft, bt = 1.0, 0.0, 0.0
    for _, cand in cdf.iterrows():
        if len(selected) >= max_wells:
            break
        selected.append(cand.to_dict())
        total_flow = sum(s['flow_m3_day'] for s in selected)
        bt = _blend_tds(
            [s['flow_m3_day'] for s in selected],
            [s['tds_ppm'] for s in selected],
        )
        ff, ft, _ = _compute_feed_factor(bt, strictest_tds, goal_tds, treatment_df)
        # Stop when well extraction capacity meets the treatment feed target
        if total_flow >= treatment_feed_target_m3:
            break

    for i, w in enumerate(selected):
        w['name'] = f'well_{i + 1}'
    return selected, ff, ft, bt


# ---------------------------------------------------------------------------
# Internal helpers — utilization metrics
# ---------------------------------------------------------------------------

def _compute_utilization_metrics(sim_df, treatment_throughput_m3_hr,
                                 efficiency_df=None):
    """Compute treatment utilization statistics from simulation results.

    Args:
        sim_df: DataFrame from _run_sizing_simulation.
        treatment_throughput_m3_hr: Rated treatment capacity (m3/hr).
        efficiency_df: Efficiency curve DataFrame. When provided, computes
            efficiency-adjusted energy and maintenance metrics.

    Returns:
        Dict with utilization statistics and efficiency metrics.
    """
    max_feed_m3 = treatment_throughput_m3_hr * 24

    # Daily utilization on days when treatment is active
    active_mask = sim_df['treatment_feed_m3'] > 0
    active = sim_df[active_mask]

    if len(active) == 0 or max_feed_m3 <= 0:
        return {
            'treatment_throughput_m3_hr': treatment_throughput_m3_hr,
            'active_treatment_days': 0,
            'avg_utilization_pct': 0.0,
            'median_utilization_pct': 0.0,
            'p95_utilization_pct': 0.0,
            'days_below_sweet_spot': 0,
            'days_in_sweet_spot': 0,
            'days_above_sweet_spot': 0,
            'sweet_spot_fraction': 0.0,
            'treatment_capex_excluded': True,
        }

    util_pct = (active['treatment_feed_m3'] / max_feed_m3) * 100

    below = (util_pct < _SWEET_SPOT_LOW).sum()
    above = (util_pct > _SWEET_SPOT_HIGH).sum()
    in_spot = len(util_pct) - below - above

    metrics = {
        'treatment_throughput_m3_hr': treatment_throughput_m3_hr,
        'active_treatment_days': int(len(active)),
        'avg_utilization_pct': round(float(util_pct.mean()), 1),
        'median_utilization_pct': round(float(util_pct.median()), 1),
        'p95_utilization_pct': round(float(util_pct.quantile(0.95)), 1),
        'days_below_sweet_spot': int(below),
        'days_in_sweet_spot': int(in_spot),
        'days_above_sweet_spot': int(above),
        'sweet_spot_fraction': round(float(in_spot / len(util_pct)), 3),
        'treatment_capex_excluded': True,
    }

    # Efficiency-adjusted metrics when curve is available
    if efficiency_df is not None:
        energy_mults = []
        maint_mults = []
        life_mults = []
        for u in util_pct:
            row = _snap_utilization(u, efficiency_df)
            energy_mults.append(row['energy_multiplier'])
            maint_mults.append(row['maintenance_multiplier'])
            life_mults.append(row['membrane_life_multiplier'])

        metrics['avg_energy_multiplier'] = round(float(pd.Series(energy_mults).mean()), 3)
        metrics['avg_maintenance_multiplier'] = round(float(pd.Series(maint_mults).mean()), 3)
        metrics['avg_membrane_life_multiplier'] = round(float(pd.Series(life_mults).mean()), 3)

    return metrics


# ---------------------------------------------------------------------------
# Public API — from-scratch sizing
# ---------------------------------------------------------------------------

def size_water_system(irrigation_demand_df, registry_path, *,
                      objective='minimize_cost',
                      municipal_available=True,
                      max_wells=6,
                      max_capital_budget=None,
                      target_deficit_fraction=0.0,
                      root_dir=None):
    """Recommend a water system configuration based on irrigation demand.

    Given a demand profile from compute_irrigation_demand, selects wells,
    treatment, storage, and municipal supplement from the component catalogs
    to meet demand while optimizing the chosen objective. Validates the
    recommended configuration by running the full daily simulation and
    iterates if deficit exceeds the target.

    Args:
        irrigation_demand_df: DataFrame from compute_irrigation_demand with
            columns day, total_demand_m3, crop_tds_requirement_ppm.
        registry_path: Path to data_registry.yaml.
        objective: One of 'minimize_cost', 'minimize_energy', 'minimize_draw'.
        municipal_available: Whether municipal water is available.
        max_wells: Maximum number of wells to select.
        max_capital_budget: Maximum total CAPEX (USD). Logs warning if exceeded.
        target_deficit_fraction: Acceptable deficit as fraction of total demand.
        root_dir: Repository root. Defaults to parent of settings/.

    Returns:
        Dict with keys:
            config: water_systems YAML-compatible dict
            summary: objective, component counts, feed_factor, metrics
            demand_analysis: demand profile statistics
    """
    if root_dir is None:
        root_dir = Path(registry_path).parent.parent
    registry = _load_yaml(registry_path)
    paths = _resolve_water_paths(registry, root_dir)

    well_df = _load_csv(paths['wells'])
    pump_df = _load_csv(paths['pump_systems'])
    treatment_df = _load_treatment_lookup(paths['treatment_research'])
    storage_df = _load_csv(paths['storage_systems'])
    dispatch_strategy = _SIZING_DISPATCH.get(objective, 'minimize_cost')

    # Step 1: Demand analysis
    demand = _analyze_demand(irrigation_demand_df)
    goal_tds = _SIZING_GOAL_TDS
    strictest_tds = demand['strictest_tds_ppm']

    if demand['peak_daily_demand_m3'] <= 0:
        logger.warning('No irrigation demand — returning minimal config')
        storage = {'storage_type': 'reservoir', 'capacity_m3': _SIZING_MIN_STORAGE_M3,
                    'capital_cost': 0, 'om_cost_per_year': 0}
        config = _build_sizing_config([], 1.0, goal_tds,
                                      _SIZING_MUNICIPAL_DEFAULTS, storage)
        return {'config': config, 'summary': {}, 'demand_analysis': demand}

    # Steps 2-3: Initial well selection targeting p95 (pre-storage sizing)
    # For minimize_draw, wells are backup only — target 25% of avg demand
    if objective == 'minimize_draw' and municipal_available:
        initial_target = demand['avg_daily_demand_m3'] * 0.25
    else:
        initial_target = demand['p95_daily_demand_m3']
    wells_pre, ff_pre, ft_pre, bt_pre = _select_wells(
        well_df, pump_df, initial_target,
        strictest_tds, goal_tds, treatment_df, max_wells, objective)

    # Step 5: Size storage — pass well delivery capacity for GW-share scaling
    well_delivery_pre = sum(w['flow_m3_day'] for w in wells_pre) / ff_pre if ff_pre > 0 else 0.0
    storage = _size_storage(demand, ff_pre, storage_df, objective,
                            well_delivery_m3_day=well_delivery_pre)

    # Re-select wells targeting avg demand (or reduced for minimize_draw)
    if objective == 'minimize_draw' and municipal_available:
        avg_target = demand['avg_daily_demand_m3'] * 0.25
    else:
        avg_target = demand['avg_daily_demand_m3']
    wells, ff, ft, bt = _select_wells(
        well_df, pump_df, avg_target,
        strictest_tds, goal_tds, treatment_df, max_wells, objective)

    # Step 4: Treatment throughput
    # Demand-based: sized for p95 daily peak.
    # Well-based cap: treatment can never process more than wells extract.
    well_extraction_capacity = sum(w['flow_m3_day'] for w in wells)
    if ft > 0 and bt > 0:
        treat_row = _snap_tds_to_band(bt, treatment_df)
        recovery = treat_row['recovery_rate_pct'] / 100.0
        demand_based = (demand['p95_daily_demand_m3'] * ft) / (24 * recovery)
        well_based = well_extraction_capacity / 24
        treatment_throughput = min(demand_based, well_based)
    else:
        treatment_throughput = 1.0
        recovery = 1.0

    # Step 6: Municipal supplement
    well_delivery = well_extraction_capacity / ff if ff > 0 else 0.0
    municipal_cfg = _size_municipal(demand, well_delivery, municipal_available, objective)

    # Build config and validate
    config = _build_sizing_config(wells, treatment_throughput, goal_tds,
                                  municipal_cfg, storage)
    sim_df = _run_sizing_simulation(config, irrigation_demand_df,
                                    pump_df, treatment_df, dispatch_strategy)
    metrics = _compute_sizing_metrics(sim_df, irrigation_demand_df, wells, storage,
                                      treatment_throughput, treatment_df, bt)

    # Step 7: Iterate if deficit exceeds target
    for iteration in range(3):
        if metrics['deficit_fraction'] <= target_deficit_fraction:
            break
        logger.info('Sizing iteration %d: deficit %.4f > target %.4f',
                    iteration + 1, metrics['deficit_fraction'], target_deficit_fraction)

        if len(wells) < max_wells:
            wells, ff, ft, bt = _select_wells(
                well_df, pump_df, demand['p95_daily_demand_m3'],
                strictest_tds, goal_tds, treatment_df, len(wells) + 1, objective)
        else:
            new_cap = min(_SIZING_MAX_STORAGE_M3, int(storage['capacity_m3'] * 1.5))
            stor_row = storage_df[storage_df['storage_type'] == storage['storage_type']].iloc[0]
            storage = {
                'storage_type': storage['storage_type'],
                'capacity_m3': new_cap,
                'capital_cost': stor_row['capital_cost_per_m3'] * new_cap,
                'om_cost_per_year': stor_row['om_cost_per_m3_per_year'] * new_cap,
            }

        well_extraction_capacity = sum(w['flow_m3_day'] for w in wells)
        if ft > 0 and bt > 0:
            treat_row = _snap_tds_to_band(bt, treatment_df)
            recovery = treat_row['recovery_rate_pct'] / 100.0
            demand_based = (demand['p95_daily_demand_m3'] * ft) / (24 * recovery)
            well_based = well_extraction_capacity / 24
            treatment_throughput = min(demand_based, well_based)

        well_delivery = well_extraction_capacity / ff if ff > 0 else 0.0
        municipal_cfg = _size_municipal(demand, well_delivery, municipal_available, objective)
        config = _build_sizing_config(wells, treatment_throughput, goal_tds,
                                      municipal_cfg, storage)
        sim_df = _run_sizing_simulation(config, irrigation_demand_df,
                                        pump_df, treatment_df, dispatch_strategy)
        metrics = _compute_sizing_metrics(sim_df, irrigation_demand_df, wells, storage,
                                          treatment_throughput, treatment_df, bt)

    if max_capital_budget is not None and metrics['total_capex'] > max_capital_budget:
        logger.warning('Sized system CAPEX (%.0f) exceeds budget (%.0f)',
                       metrics['total_capex'], max_capital_budget)

    return {
        'config': config,
        'summary': {
            'objective': objective,
            'n_wells': len(wells),
            'well_depths_m': [w['depth_m'] for w in wells],
            'feed_factor': round(ff, 3),
            'f_treat': round(ft, 3),
            'blended_well_tds_ppm': round(bt, 0),
            'treatment_throughput_m3_hr': round(treatment_throughput, 1),
            'storage_type': storage['storage_type'],
            'storage_capacity_m3': storage['capacity_m3'],
            'municipal_available': municipal_available,
            'metrics': metrics,
        },
        'demand_analysis': demand,
    }


# ---------------------------------------------------------------------------
# Public API — treatment-anchored optimization
# ---------------------------------------------------------------------------

def optimize_water_system(irrigation_demand_df, registry_path, *,
                          treatment_throughput_m3_hr,
                          target_utilization=0.80,
                          objective='minimize_cost',
                          municipal_available=True,
                          max_wells=6,
                          max_capital_budget=None,
                          target_deficit_fraction=0.0,
                          apply_efficiency_curve=True,
                          root_dir=None):
    """Size a water system around a fixed treatment plant capacity.

    Given a pre-determined BWRO treatment throughput, selects wells, storage,
    and municipal supplement to feed the treatment plant near its optimal
    utilization while meeting irrigation demand. Uses a treatment efficiency
    curve to model how energy, maintenance, and membrane life vary with the
    utilization ratio (fraction of rated capacity in use).

    The treatment plant is the anchor — all other components adapt to it.
    Treatment CAPEX is excluded from cost metrics since the plant is
    pre-existing.

    Args:
        irrigation_demand_df: DataFrame from compute_irrigation_demand with
            columns day, total_demand_m3, crop_tds_requirement_ppm.
        registry_path: Path to data_registry.yaml.
        treatment_throughput_m3_hr: Fixed BWRO throughput capacity (m3/hr).
            This is the anchor — it is not resized.
        target_utilization: Target utilization fraction (0.0-1.0). Default
            0.80 is the center of the BWRO sweet spot (70-85%).
        objective: One of 'minimize_cost', 'minimize_energy', 'minimize_draw'.
            Controls well sorting and storage type selection.
        municipal_available: Whether municipal water supplement is available.
        max_wells: Maximum number of wells to select.
        max_capital_budget: Maximum CAPEX for non-treatment components (USD).
            Treatment plant cost is excluded since it is pre-existing.
        target_deficit_fraction: Acceptable deficit as fraction of total demand.
        apply_efficiency_curve: When True, applies utilization-based multipliers
            to the validation simulation's energy and cost outputs.
        root_dir: Repository root. Defaults to parent of settings/.

    Returns:
        Dict with keys:
            config: water_systems YAML-compatible dict
            summary: objective, component counts, feed_factor, metrics
            demand_analysis: demand profile statistics
            utilization_metrics: treatment utilization statistics
    """
    if root_dir is None:
        root_dir = Path(registry_path).parent.parent
    registry = _load_yaml(registry_path)
    paths = _resolve_water_paths(registry, root_dir)

    well_df = _load_csv(paths['wells'])
    pump_df = _load_csv(paths['pump_systems'])
    treatment_df = _load_treatment_lookup(paths['treatment_research'])
    storage_df = _load_csv(paths['storage_systems'])
    dispatch_strategy = _SIZING_DISPATCH.get(objective, 'minimize_cost')

    efficiency_df = None
    if apply_efficiency_curve and 'treatment_efficiency' in paths:
        efficiency_df = _load_efficiency_curve(paths['treatment_efficiency'])

    # Step 1: Demand analysis
    demand = _analyze_demand(irrigation_demand_df)
    goal_tds = _SIZING_GOAL_TDS
    strictest_tds = demand['strictest_tds_ppm']

    if demand['peak_daily_demand_m3'] <= 0:
        logger.warning('No irrigation demand — returning minimal config')
        storage = {'storage_type': 'reservoir', 'capacity_m3': _SIZING_MIN_STORAGE_M3,
                    'capital_cost': 0, 'om_cost_per_year': 0}
        config = _build_sizing_config([], treatment_throughput_m3_hr, goal_tds,
                                      _SIZING_MUNICIPAL_DEFAULTS, storage)
        return {
            'config': config, 'summary': {}, 'demand_analysis': demand,
            'utilization_metrics': _compute_utilization_metrics(
                pd.DataFrame(), treatment_throughput_m3_hr),
        }

    # Step 2: Compute treatment feed target at optimal utilization
    max_daily_feed_m3 = treatment_throughput_m3_hr * 24
    optimal_daily_feed_m3 = max_daily_feed_m3 * target_utilization

    # Step 3: Select wells to supply the treatment feed target
    wells, ff, ft, bt = _select_wells_for_treatment(
        well_df, pump_df, optimal_daily_feed_m3,
        strictest_tds, goal_tds, treatment_df, max_wells, objective)

    well_extraction_capacity = sum(w['flow_m3_day'] for w in wells)

    if well_extraction_capacity < optimal_daily_feed_m3:
        logger.warning(
            'Well capacity (%.0f m3/day) is less than treatment feed target '
            '(%.0f m3/day). Treatment will operate below target utilization.',
            well_extraction_capacity, optimal_daily_feed_m3)

    # Step 4: Compute delivery capacity from treatment-anchored system
    # Wells deliver: some treated (through BWRO) + some untreated (if TDS allows)
    well_delivery = well_extraction_capacity / ff if ff > 0 else 0.0

    # Step 5: Size storage for peak-avg demand gap
    storage = _size_storage(demand, ff, storage_df, objective,
                            well_delivery_m3_day=well_delivery)

    # Step 6: Municipal covers the gap between well+treatment delivery and demand
    municipal_cfg = _size_municipal(demand, well_delivery, municipal_available, objective)

    # Build config and validate
    config = _build_sizing_config(wells, treatment_throughput_m3_hr, goal_tds,
                                  municipal_cfg, storage)
    sim_df = _run_sizing_simulation(config, irrigation_demand_df,
                                    pump_df, treatment_df, dispatch_strategy)

    # Apply efficiency curve adjustments to simulation output
    if efficiency_df is not None:
        sim_df = _apply_efficiency_adjustment(
            sim_df, treatment_throughput_m3_hr, efficiency_df)

    # Compute metrics (treatment CAPEX excluded for optimizer)
    metrics = _compute_sizing_metrics(sim_df, irrigation_demand_df, wells, storage,
                                      treatment_throughput_m3_hr, treatment_df, bt)
    # Remove treatment CAPEX from the total since plant is pre-existing
    if bt > 0 and treatment_throughput_m3_hr > 0:
        treat_row = _snap_tds_to_band(bt, treatment_df)
        treatment_capex = treat_row['capital_cost_per_m3_day'] * treatment_throughput_m3_hr * 24
        metrics['total_capex'] = round(metrics['total_capex'] - treatment_capex, 2)
    metrics['treatment_capex_excluded'] = True

    utilization_metrics = _compute_utilization_metrics(
        sim_df, treatment_throughput_m3_hr, efficiency_df)

    # Step 7: Iterate if deficit exceeds target
    for iteration in range(3):
        if metrics['deficit_fraction'] <= target_deficit_fraction:
            break
        logger.info('Optimizer iteration %d: deficit %.4f > target %.4f',
                    iteration + 1, metrics['deficit_fraction'], target_deficit_fraction)

        # Try adding wells first, then expand storage
        if len(wells) < max_wells:
            wells, ff, ft, bt = _select_wells_for_treatment(
                well_df, pump_df, max_daily_feed_m3,
                strictest_tds, goal_tds, treatment_df, len(wells) + 1, objective)
        else:
            new_cap = min(_SIZING_MAX_STORAGE_M3, int(storage['capacity_m3'] * 1.5))
            stor_row = storage_df[storage_df['storage_type'] == storage['storage_type']].iloc[0]
            storage = {
                'storage_type': storage['storage_type'],
                'capacity_m3': new_cap,
                'capital_cost': stor_row['capital_cost_per_m3'] * new_cap,
                'om_cost_per_year': stor_row['om_cost_per_m3_per_year'] * new_cap,
            }

        well_extraction_capacity = sum(w['flow_m3_day'] for w in wells)
        well_delivery = well_extraction_capacity / ff if ff > 0 else 0.0
        municipal_cfg = _size_municipal(demand, well_delivery, municipal_available, objective)

        config = _build_sizing_config(wells, treatment_throughput_m3_hr, goal_tds,
                                      municipal_cfg, storage)
        sim_df = _run_sizing_simulation(config, irrigation_demand_df,
                                        pump_df, treatment_df, dispatch_strategy)

        if efficiency_df is not None:
            sim_df = _apply_efficiency_adjustment(
                sim_df, treatment_throughput_m3_hr, efficiency_df)

        metrics = _compute_sizing_metrics(sim_df, irrigation_demand_df, wells, storage,
                                          treatment_throughput_m3_hr, treatment_df, bt)
        if bt > 0 and treatment_throughput_m3_hr > 0:
            treat_row = _snap_tds_to_band(bt, treatment_df)
            treatment_capex = treat_row['capital_cost_per_m3_day'] * treatment_throughput_m3_hr * 24
            metrics['total_capex'] = round(metrics['total_capex'] - treatment_capex, 2)
        metrics['treatment_capex_excluded'] = True

        utilization_metrics = _compute_utilization_metrics(
            sim_df, treatment_throughput_m3_hr, efficiency_df)

    if max_capital_budget is not None and metrics['total_capex'] > max_capital_budget:
        logger.warning('Optimized system CAPEX (%.0f) exceeds budget (%.0f)',
                       metrics['total_capex'], max_capital_budget)

    return {
        'config': config,
        'summary': {
            'objective': objective,
            'n_wells': len(wells),
            'well_depths_m': [w['depth_m'] for w in wells],
            'feed_factor': round(ff, 3),
            'f_treat': round(ft, 3),
            'blended_well_tds_ppm': round(bt, 0),
            'treatment_throughput_m3_hr': treatment_throughput_m3_hr,
            'target_utilization': target_utilization,
            'storage_type': storage['storage_type'],
            'storage_capacity_m3': storage['capacity_m3'],
            'municipal_available': municipal_available,
            'metrics': metrics,
        },
        'demand_analysis': demand,
        'utilization_metrics': utilization_metrics,
    }


# ---------------------------------------------------------------------------
# Entry point for quick verification
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    from src.irrigation_demand import compute_irrigation_demand

    root = Path(__file__).parent.parent
    registry = root / 'settings' / 'data_registry_base.yaml'
    demand_df = compute_irrigation_demand(
        farm_profiles_path=root / 'settings' / 'farm_profile_base.yaml',
        registry_path=registry,
    )

    print('=' * 60)
    print('size_water_system (from-scratch sizing)')
    print('=' * 60)
    result = size_water_system(demand_df, registry)
    s = result['summary']
    m = s.get('metrics', {})
    print(f"  Wells: {s.get('n_wells', 0)} at depths {s.get('well_depths_m', [])}")
    print(f"  Treatment: {s.get('treatment_throughput_m3_hr', 0):.1f} m3/hr")
    print(f"  Storage: {s.get('storage_capacity_m3', 0)} m3 ({s.get('storage_type', '')})")
    print(f"  Feed factor: {s.get('feed_factor', 0):.3f}")
    print(f"  Deficit: {m.get('deficit_fraction', 0):.4f}")
    print(f"  Cost/m3: ${m.get('cost_per_m3_delivered', 0):.2f}")
    print(f"  Energy/m3: {m.get('energy_per_m3_delivered', 0):.2f} kWh")
    print(f"  CAPEX: ${m.get('total_capex', 0):,.0f}")
    print(f"  Annual OPEX: ${m.get('annual_opex', 0):,.0f}")

    print()
    print('=' * 60)
    print('optimize_water_system (treatment-anchored at 50 m3/hr)')
    print('=' * 60)
    opt = optimize_water_system(
        demand_df, registry,
        treatment_throughput_m3_hr=50,
        target_utilization=0.80,
    )
    s = opt['summary']
    m = s.get('metrics', {})
    u = opt['utilization_metrics']
    print(f"  Wells: {s.get('n_wells', 0)} at depths {s.get('well_depths_m', [])}")
    print(f"  Treatment: {s.get('treatment_throughput_m3_hr', 0):.1f} m3/hr (fixed)")
    print(f"  Target utilization: {s.get('target_utilization', 0):.0%}")
    print(f"  Storage: {s.get('storage_capacity_m3', 0)} m3 ({s.get('storage_type', '')})")
    print(f"  Feed factor: {s.get('feed_factor', 0):.3f}")
    print(f"  Deficit: {m.get('deficit_fraction', 0):.4f}")
    print(f"  Cost/m3: ${m.get('cost_per_m3_delivered', 0):.2f}")
    print(f"  Energy/m3: {m.get('energy_per_m3_delivered', 0):.2f} kWh")
    print(f"  CAPEX (excl. treatment): ${m.get('total_capex', 0):,.0f}")
    print(f"  Annual OPEX: ${m.get('annual_opex', 0):,.0f}")
    print(f"  Utilization:")
    print(f"    Avg: {u.get('avg_utilization_pct', 0):.1f}%")
    print(f"    Median: {u.get('median_utilization_pct', 0):.1f}%")
    print(f"    P95: {u.get('p95_utilization_pct', 0):.1f}%")
    print(f"    Days in sweet spot: {u.get('days_in_sweet_spot', 0)}")
    print(f"    Days below: {u.get('days_below_sweet_spot', 0)}")
    print(f"    Days above: {u.get('days_above_sweet_spot', 0)}")
    print(f"    Sweet spot fraction: {u.get('sweet_spot_fraction', 0):.1%}")
    if 'avg_energy_multiplier' in u:
        print(f"    Avg energy multiplier: {u['avg_energy_multiplier']:.3f}")
        print(f"    Avg maintenance multiplier: {u['avg_maintenance_multiplier']:.3f}")
        print(f"    Avg membrane life multiplier: {u['avg_membrane_life_multiplier']:.3f}")
