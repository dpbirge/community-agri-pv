"""Daily energy balance dispatch for community agri-PV microgrid.

Dispatch model: daily renewable generation (solar + wind) is matched against
daily demand (community buildings + water systems). Surplus energy flows
through battery → grid export → curtailment. Deficit energy flows through
battery → grid import → diesel generator. Battery SOC carries day-to-day.

Supports three dispatch strategies: minimize_cost, minimize_grid_reliance,
minimize_generator. Six grid interaction modes control import/export
availability. Monthly caps enforce grid and fuel limits.

Usage:
    from src.energy_balance import compute_daily_energy_balance, save_energy_balance
    from src.water_balance import compute_daily_water_balance

    water_df = compute_daily_water_balance(...)
    df = compute_daily_energy_balance(
        energy_config_path='settings/energy_system_base.yaml',
        energy_policy_path='settings/energy_policy_base.yaml',
        community_config_path='settings/community_demands_base.yaml',
        farm_profiles_path='settings/farm_profile_base.yaml',
        registry_path='settings/data_registry_base.yaml',
        water_balance_df=water_df,
    )
    save_energy_balance(df, output_dir='simulation/')
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


def _resolve_energy_balance_paths(registry, root_dir):
    """Resolve paths from energy_equipment, electricity_pricing, and fuel_pricing.

    Args:
        registry: Parsed data_registry.yaml dict.
        root_dir: Repository root directory.

    Returns:
        Flat dict mapping registry key to absolute Path.
    """
    paths = {}
    for section in ('energy_equipment', 'electricity_pricing', 'fuel_pricing'):
        for k, v in registry.get(section, {}).items():
            if v is not None:
                paths[k] = Path(root_dir) / v
    return paths


# ---------------------------------------------------------------------------
# Internal helpers — price loading
# ---------------------------------------------------------------------------

def _load_price_series(csv_path, column):
    """Load a monthly price CSV and return a date-indexed Series.

    Args:
        csv_path: Path to price CSV (comment='#', date column).
        column: Column name to extract (e.g. 'usd_per_kwh_avg_daily').

    Returns:
        Series indexed by date with the specified column's values.
    """
    df = pd.read_csv(csv_path, comment='#', parse_dates=['date'])
    return df.set_index('date')[column]


def _daily_price_lookup(price_series, dates):
    """Map monthly price data to daily simulation dates via forward-fill.

    Args:
        price_series: Monthly Series indexed by date.
        dates: DatetimeIndex of simulation dates.

    Returns:
        Series of daily rates aligned to simulation dates.

    Raises:
        ValueError: If the first simulation date precedes the first price entry.
    """
    if dates[0] < price_series.index[0]:
        raise ValueError(
            f'Simulation start {dates[0].date()} precedes first price entry '
            f'{price_series.index[0].date()}'
        )
    combined = price_series.reindex(price_series.index.union(dates))
    combined = combined.ffill()
    return combined.reindex(dates)


# ---------------------------------------------------------------------------
# Internal helpers — equipment spec builders
# ---------------------------------------------------------------------------

def _load_equipment_specs(csv_path, type_id):
    """Load equipment CSV and return the row matching type_id as a dict.

    Args:
        csv_path: Path to equipment CSV (batteries or generators).
        type_id: Value to match in the 'type_id' column.

    Returns:
        Dict of the matched row's columns and values.

    Raises:
        ValueError: If no row matches type_id.
    """
    df = pd.read_csv(csv_path, comment='#')
    match = df[df['type_id'] == type_id]
    if match.empty:
        raise ValueError(f"No equipment found with type_id='{type_id}' in {csv_path}")
    return match.iloc[0].to_dict()


def _build_battery_specs(energy_system_config, policy_config, equipment_path):
    """Build battery specs dict from config and equipment CSV.

    Returns None when has_battery is false. Policy SOC limits override CSV defaults.

    Args:
        energy_system_config: Parsed energy_system.yaml dict.
        policy_config: Parsed energy_policy.yaml dict.
        equipment_path: Path to batteries CSV.

    Returns:
        Dict with capacity_kwh, soc_min_kwh, soc_max_kwh,
        charge_efficiency, discharge_efficiency. Or None.
    """
    bat_cfg = energy_system_config.get('battery', {})
    if not bat_cfg.get('has_battery', False):
        return None

    row = _load_equipment_specs(equipment_path, bat_cfg['type'])
    pol_bat = policy_config.get('battery', {})
    capacity = bat_cfg.get('capacity_kwh', row['capacity_kwh'])

    return {
        'capacity_kwh': capacity,
        'soc_min_kwh': pol_bat.get('soc_min', row['soc_min']) * capacity,
        'soc_max_kwh': pol_bat.get('soc_max', row['soc_max']) * capacity,
        'initial_soc_kwh': pol_bat.get('soc_initial', row['initial_soc']) * capacity,
        'charge_efficiency': row['charge_efficiency'],
        'discharge_efficiency': row['discharge_efficiency'],
    }


def _build_generator_specs(energy_system_config, policy_config, equipment_path):
    """Build generator specs dict from config and equipment CSV.

    Returns None when has_generator is false.

    Args:
        energy_system_config: Parsed energy_system.yaml dict.
        policy_config: Parsed energy_policy.yaml dict.
        equipment_path: Path to generators CSV.

    Returns:
        Dict with rated_capacity_kw, min_load_kw, sfc_coefficient_a,
        sfc_coefficient_b. Or None.
    """
    gen_cfg = energy_system_config.get('generator', {})
    if not gen_cfg.get('has_generator', False):
        return None

    row = _load_equipment_specs(equipment_path, gen_cfg['type'])
    pol_gen = policy_config.get('generator', {})
    rated_kw = gen_cfg.get('rated_capacity_kw', row['capacity_kw'])
    min_load_frac = pol_gen.get('min_load_fraction', row.get('min_load_fraction', 0.30))

    return {
        'rated_capacity_kw': rated_kw,
        'min_load_kw': min_load_frac * rated_kw,
        'sfc_coefficient_a': row['sfc_coefficient_a'],
        'sfc_coefficient_b': row['sfc_coefficient_b'],
    }


# ---------------------------------------------------------------------------
# Internal helpers — grid validation and export rate
# ---------------------------------------------------------------------------

_VALID_GRID_MODES = {
    'full_grid': {'full_grid', 'net_metering', 'feed_in_tariff', 'self_consumption'},
    'limited_grid': {'limited_grid', 'self_consumption', 'off_grid'},
    'off_grid': {'off_grid'},
}


def _validate_grid_config(grid_connection, grid_mode):
    """Validate grid_connection and grid.mode compatibility.

    Args:
        grid_connection: Physical connection from energy_system config.
        grid_mode: Policy grid mode from energy_policy config.

    Raises:
        ValueError: If the combination is invalid.
    """
    valid = _VALID_GRID_MODES.get(grid_connection)
    if valid is None:
        raise ValueError(f"Unknown grid_connection: '{grid_connection}'")
    if grid_mode not in valid:
        raise ValueError(
            f"grid.mode '{grid_mode}' is not valid with "
            f"grid_connection '{grid_connection}'. "
            f"Valid modes: {sorted(valid)}"
        )


def _validate_energy_system_config(config):
    """Validate energy_system config keys and values at runtime.

    Args:
        config: Parsed energy_system.yaml dict.

    Raises:
        ValueError: On missing keys, invalid types, or out-of-range values.
    """
    required = {'community_solar', 'wind_turbines', 'generator', 'battery', 'grid_connection'}
    missing = required - set(config.keys())
    if missing:
        raise ValueError(f"energy_system config missing required keys: {sorted(missing)}")

    valid_gc = {'full_grid', 'limited_grid', 'off_grid'}
    gc = config['grid_connection']
    if gc not in valid_gc:
        raise ValueError(
            f"energy_system grid_connection '{gc}' invalid. Must be one of: {sorted(valid_gc)}"
        )

    for key, entry in config.get('community_solar', {}).items():
        if 'area_ha' not in entry:
            raise ValueError(f"community_solar.{key} missing 'area_ha'")
        if not isinstance(entry['area_ha'], (int, float)) or entry['area_ha'] < 0:
            raise ValueError(f"community_solar.{key}.area_ha must be a non-negative number")

    for key, entry in config.get('wind_turbines', {}).items():
        if 'number' not in entry:
            raise ValueError(f"wind_turbines.{key} missing 'number'")
        if not isinstance(entry['number'], (int, float)) or entry['number'] < 0:
            raise ValueError(f"wind_turbines.{key}.number must be a non-negative number")

    gen = config.get('generator', {})
    if 'has_generator' not in gen:
        raise ValueError("generator section missing 'has_generator'")
    if not isinstance(gen['has_generator'], bool):
        raise ValueError("generator.has_generator must be a boolean")
    if gen['has_generator']:
        if not gen.get('type') or not isinstance(gen['type'], str):
            raise ValueError("generator.type must be a non-empty string when has_generator is true")
        rc = gen.get('rated_capacity_kw')
        if not isinstance(rc, (int, float)) or rc <= 0:
            raise ValueError("generator.rated_capacity_kw must be a positive number")

    bat = config.get('battery', {})
    if 'has_battery' not in bat:
        raise ValueError("battery section missing 'has_battery'")
    if not isinstance(bat['has_battery'], bool):
        raise ValueError("battery.has_battery must be a boolean")
    if bat['has_battery']:
        if not bat.get('type') or not isinstance(bat['type'], str):
            raise ValueError("battery.type must be a non-empty string when has_battery is true")
        cap = bat.get('capacity_kwh')
        if not isinstance(cap, (int, float)) or cap <= 0:
            raise ValueError("battery.capacity_kwh must be a positive number")


def _validate_energy_policy_config(config):
    """Validate energy_policy config keys and values at runtime.

    Args:
        config: Parsed energy_policy.yaml dict.

    Raises:
        ValueError: On missing keys, invalid types, or out-of-range values.
    """
    required = {'strategy', 'grid', 'cap_enforcement', 'tariff', 'battery', 'generator'}
    missing = required - set(config.keys())
    if missing:
        raise ValueError(f"energy_policy config missing required keys: {sorted(missing)}")

    valid_strategies = {'minimize_cost', 'minimize_grid_reliance', 'minimize_generator'}
    strat = config['strategy']
    if strat not in valid_strategies:
        raise ValueError(
            f"energy_policy strategy '{strat}' invalid. "
            f"Must be one of: {sorted(valid_strategies)}"
        )

    grid = config.get('grid', {})
    valid_modes = {'full_grid', 'net_metering', 'feed_in_tariff',
                   'self_consumption', 'limited_grid', 'off_grid'}
    mode = grid.get('mode')
    if mode not in valid_modes:
        raise ValueError(
            f"energy_policy grid.mode '{mode}' invalid. Must be one of: {sorted(valid_modes)}"
        )

    bat = config.get('battery', {})
    for key in ('soc_min', 'soc_max', 'soc_initial'):
        val = bat.get(key)
        if val is not None:
            if not isinstance(val, (int, float)) or val < 0 or val > 1:
                raise ValueError(f"energy_policy battery.{key} must be a number in [0, 1]")
    soc_min = bat.get('soc_min', 0)
    soc_max = bat.get('soc_max', 1)
    if soc_min >= soc_max:
        raise ValueError(
            f"energy_policy battery.soc_min ({soc_min}) must be less than soc_max ({soc_max})"
        )

    gen = config.get('generator', {})
    mlf = gen.get('min_load_fraction')
    if mlf is not None:
        if not isinstance(mlf, (int, float)) or mlf <= 0 or mlf > 1:
            raise ValueError("energy_policy generator.min_load_fraction must be in (0, 1]")


def _resolve_export_rate(policy_grid, registry_paths):
    """Determine grid export compensation rate.

    Args:
        policy_grid: The grid section of energy_policy config.
        registry_paths: Dict of resolved registry paths.

    Returns:
        Export rate in USD/kWh. 0.0 for non-export modes.
    """
    mode = policy_grid.get('mode', 'self_consumption')
    if mode != 'feed_in_tariff':
        return 0.0

    explicit = policy_grid.get('export_rate_usd_kwh')
    if explicit is not None:
        return explicit

    tier = policy_grid.get('capacity_tier')
    if tier is None:
        raise ValueError(
            "feed_in_tariff mode requires either export_rate_usd_kwh or "
            "capacity_tier in energy policy grid config"
        )

    fit_path = registry_paths.get('feed_in_tariff')
    if fit_path is None:
        raise ValueError("feed_in_tariff CSV not found in registry")

    df = pd.read_csv(fit_path, comment='#')
    match = df[df['project_size_category'] == tier]
    if match.empty:
        raise ValueError(
            f"No FIT rate found for capacity_tier='{tier}' in {fit_path}"
        )
    return match.sort_values('date_effective').iloc[-1]['rate_usd_kwh_effective']


# ---------------------------------------------------------------------------
# Internal helpers — monthly cap and daily allowance
# ---------------------------------------------------------------------------

def _daily_cap_allowance(monthly_cap, used, day, look_ahead):
    """Compute available daily allowance from a monthly cap.

    Args:
        monthly_cap: Monthly limit, or None for unlimited.
        used: Amount consumed so far this month.
        day: Date (datetime-like with .year, .month, .day).
        look_ahead: If True, spread remaining cap evenly over remaining days.

    Returns:
        Available allowance for today. math.inf when uncapped.
    """
    if monthly_cap is None:
        return math.inf
    remaining = monthly_cap - used
    if remaining <= 0:
        return 0.0
    if not look_ahead:
        return remaining
    days_in_month = calendar.monthrange(day.year, day.month)[1]
    remaining_days = days_in_month - day.day + 1
    # Clamp to remaining to prevent floating-point accumulation from exceeding the cap
    return min(remaining / remaining_days, remaining)


# ---------------------------------------------------------------------------
# Internal helpers — battery
# ---------------------------------------------------------------------------

def _charge_battery(surplus_kwh, battery_specs, battery_state, renewable=True):
    """Charge battery from surplus energy.

    At the daily timestep the battery absorbs whatever surplus is available
    up to its SOC ceiling, applying charge efficiency losses.  No intra-day
    charge-rate limit — the daily timestep assumes the battery handles
    moment-to-moment power flows within the day without issue.

    Args:
        surplus_kwh: Available surplus energy (kWh).
        battery_specs: Battery specs dict.
        battery_state: Mutable dict with soc_kwh, renewable_fraction.
        renewable: True if energy source is renewable.

    Returns:
        Tuple of (accepted_kwh, stored_kwh) where accepted_kwh is the surplus
        consumed and stored_kwh is what entered the battery after losses.
    """
    if battery_specs is None or surplus_kwh <= 0:
        return 0.0, 0.0

    headroom = battery_specs['soc_max_kwh'] - battery_state['soc_kwh']
    if headroom <= 0:
        return 0.0, 0.0

    eff = battery_specs['charge_efficiency']
    stored = min(surplus_kwh * eff, headroom)
    accepted = stored / eff if eff > 0 else 0.0

    old_soc = battery_state['soc_kwh']
    old_frac = battery_state['renewable_fraction']
    new_soc = old_soc + stored
    source_frac = 1.0 if renewable else 0.0

    if new_soc > 0:
        battery_state['renewable_fraction'] = (
            (old_soc * old_frac + stored * source_frac) / new_soc
        )
    battery_state['soc_kwh'] = new_soc

    return accepted, stored


def _discharge_battery(deficit_kwh, battery_specs, battery_state):
    """Discharge battery to cover deficit.

    At the daily timestep the battery delivers whatever is needed down to
    its SOC floor, applying discharge efficiency losses.  No intra-day
    discharge-rate limit — same daily-timestep assumption as charging.

    Args:
        deficit_kwh: Energy needed (kWh).
        battery_specs: Battery specs dict.
        battery_state: Mutable dict with soc_kwh, renewable_fraction.

    Returns:
        Tuple of (delivered_kwh, soc_draw_kwh, renewable_delivered_kwh).
    """
    if battery_specs is None or deficit_kwh <= 0:
        return 0.0, 0.0, 0.0

    available = battery_state['soc_kwh'] - battery_specs['soc_min_kwh']
    if available <= 0:
        return 0.0, 0.0, 0.0

    eff = battery_specs['discharge_efficiency']
    delivered = min(deficit_kwh, available * eff)
    soc_draw = delivered / eff if eff > 0 else delivered

    renewable_delivered = delivered * battery_state['renewable_fraction']
    battery_state['soc_kwh'] -= soc_draw

    return delivered, soc_draw, renewable_delivered


# ---------------------------------------------------------------------------
# Internal helpers — grid
# ---------------------------------------------------------------------------

def _grid_import_available(grid_mode, grid_cap_state):
    """Compute daily grid import allowance.

    Args:
        grid_mode: Grid interaction mode string.
        grid_cap_state: Dict with 'import' and 'export' sub-dicts.

    Returns:
        Available import kWh for today. 0.0 for off_grid.
    """
    if grid_mode == 'off_grid':
        return 0.0
    cap = grid_cap_state['import']
    return _daily_cap_allowance(
        cap['monthly_cap'], cap['used'], cap['day'], cap['look_ahead']
    )


def _grid_export_available(grid_mode, grid_cap_state):
    """Compute daily grid export allowance.

    Args:
        grid_mode: Grid interaction mode string.
        grid_cap_state: Dict with 'import' and 'export' sub-dicts.

    Returns:
        Available export kWh for today. 0.0 for off_grid, self_consumption,
        limited_grid.
    """
    if grid_mode in ('off_grid', 'self_consumption', 'limited_grid'):
        return 0.0
    cap = grid_cap_state['export']
    return _daily_cap_allowance(
        cap['monthly_cap'], cap['used'], cap['day'], cap['look_ahead']
    )


# ---------------------------------------------------------------------------
# Internal helpers — generator
# ---------------------------------------------------------------------------

_GENERATOR_MIN_RUNTIME_HOURS = 6


def _run_generator(deficit_kwh, generator_specs):
    """Run diesel generator to cover deficit.

    When the deficit requires less than min_load power, the generator runs at
    minimum load for at least 6 hours (one operational shift: startup, run,
    shutdown). Excess beyond the deficit is offered to the battery or curtailed.
    Fuel consumption follows the Willans line model.

    Args:
        deficit_kwh: Energy needed from generator (kWh).
        generator_specs: Generator specs dict.

    Returns:
        Tuple of (delivered_kwh, excess_kwh, fuel_liters, runtime_hours).
    """
    # 10 Wh threshold — avoids generator startup for float residuals (e.g. ~1e-10 kWh)
    if generator_specs is None or deficit_kwh <= 0.01:
        return 0.0, 0.0, 0.0, 0.0

    rated_kw = generator_specs['rated_capacity_kw']
    min_load_kw = generator_specs['min_load_kw']
    a = generator_specs['sfc_coefficient_a']
    b = generator_specs['sfc_coefficient_b']

    power_kw = max(deficit_kwh / 24.0, min_load_kw)
    power_kw = min(power_kw, rated_kw)

    if power_kw <= min_load_kw + 1e-9:
        # Running at minimum load — enforce minimum runtime of 6 hours
        hours = max(_GENERATOR_MIN_RUNTIME_HOURS, deficit_kwh / min_load_kw)
        hours = min(hours, 24.0)
        output = min_load_kw * hours
        delivered = min(output, deficit_kwh)
        excess = output - delivered
    else:
        hours = deficit_kwh / power_kw
        hours = min(hours, 24.0)
        output = power_kw * hours
        delivered = min(output, deficit_kwh)
        excess = output - delivered

    # Fuel via Willans line
    fuel = (a * rated_kw + b * power_kw) * hours

    return delivered, excess, fuel, hours


# ---------------------------------------------------------------------------
# Internal helpers — cost and metrics
# ---------------------------------------------------------------------------

def _compute_grid_import_cost(import_kwh, community_kwh, water_kwh, total_kwh,
                              ag_tariff, commercial_tariff):
    """Compute grid import cost split by demand category tariff.

    Args:
        import_kwh: Total grid import for the day (kWh).
        community_kwh: Community building demand (kWh).
        water_kwh: Water system demand (kWh).
        total_kwh: Total demand (kWh).
        ag_tariff: Agricultural electricity rate (USD/kWh).
        commercial_tariff: Commercial electricity rate (USD/kWh).

    Returns:
        Import cost in USD.
    """
    if import_kwh <= 0 or total_kwh <= 0:
        return 0.0
    water_share = water_kwh / total_kwh
    community_share = 1.0 - water_share
    return import_kwh * (water_share * ag_tariff + community_share * commercial_tariff)


def _compute_net_metering_cost(import_kwh, export_kwh, net_metering_state,
                               ag_tariff, commercial_tariff,
                               community_kwh, water_kwh, total_kwh):
    """Compute daily grid cost under monthly net metering rules.

    Uses incremental billing: the daily cost is based on the change in
    the monthly net billable position. The billable position is
    max(0, monthly_import - monthly_export). Only the incremental increase
    in billable kWh is charged, ensuring daily costs sum to the correct
    monthly net-metered bill.

    Args:
        import_kwh: Daily grid import (kWh).
        export_kwh: Daily grid export (kWh).
        net_metering_state: Mutable dict tracking monthly_import, monthly_export.
        ag_tariff: Agricultural rate (USD/kWh).
        commercial_tariff: Commercial rate (USD/kWh).
        community_kwh: Community building demand (kWh).
        water_kwh: Water system demand (kWh).
        total_kwh: Total demand (kWh).

    Returns:
        Daily grid import cost in USD.
    """
    old_billable = max(0.0, net_metering_state['monthly_import']
                       - net_metering_state['monthly_export'])

    net_metering_state['monthly_import'] += import_kwh
    net_metering_state['monthly_export'] += export_kwh

    new_billable = max(0.0, net_metering_state['monthly_import']
                       - net_metering_state['monthly_export'])

    incremental_kwh = max(0.0, new_billable - old_billable)
    if incremental_kwh <= 0:
        return 0.0

    return _compute_grid_import_cost(
        incremental_kwh, community_kwh, water_kwh, total_kwh,
        ag_tariff, commercial_tariff
    )


def _init_energy_dispatch_row(day, community_demand_kwh, water_demand_kwh,
                              total_demand_kwh, total_solar_kwh, total_wind_kwh,
                              total_renewable_kwh, battery_specs):
    """Create a zeroed output row dict with all column keys.

    Args:
        day: Date for this row.
        community_demand_kwh: Community building energy demand.
        water_demand_kwh: Water system energy demand.
        total_demand_kwh: Total energy demand.
        total_solar_kwh: Solar generation.
        total_wind_kwh: Wind generation.
        total_renewable_kwh: Total renewable generation.
        battery_specs: Battery specs dict or None.

    Returns:
        Dict with all output column keys initialized.
    """
    row = {
        'day': day,
        'community_energy_demand_kwh': community_demand_kwh,
        'water_energy_demand_kwh': water_demand_kwh,
        'total_demand_kwh': total_demand_kwh,
        'total_solar_kwh': total_solar_kwh,
        'total_wind_kwh': total_wind_kwh,
        'total_renewable_kwh': total_renewable_kwh,
        'renewable_consumed_kwh': 0.0,
        'renewable_surplus_kwh': 0.0,
        'battery_charge_kwh': 0.0,
        'battery_discharge_kwh': 0.0,
        'grid_import_kwh': 0.0,
        'grid_export_kwh': 0.0,
        'generator_kwh': 0.0,
        'generator_excess_kwh': 0.0,
        'curtailed_kwh': 0.0,
        'deficit_kwh': 0.0,
        'generator_fuel_liters': 0.0,
        'generator_runtime_hours': 0.0,
        'grid_import_cost': 0.0,
        'grid_export_revenue': 0.0,
        'generator_fuel_cost': 0.0,
        'total_energy_cost': 0.0,
        'self_sufficiency_ratio': 0.0,
        'self_consumption_ratio': 0.0,
        'renewable_fraction': 0.0,
        'policy_strategy': '',
        'policy_grid_mode': '',
        'policy_deficit': False,
    }

    if battery_specs is not None:
        row['battery_soc_kwh'] = 0.0
        row['battery_soc_fraction'] = 0.0
        row['battery_renewable_fraction'] = 0.0

    return row


def _finalize_energy_dispatch_row(row, battery_specs, battery_state):
    """Compute metrics and cost totals for a dispatch row.

    Args:
        row: Output row dict (mutated in place).
        battery_specs: Battery specs dict or None.
        battery_state: Battery state dict with soc_kwh, renewable_fraction.
    """
    total_demand = row['total_demand_kwh']
    total_renewable = row['total_renewable_kwh']
    grid_import = row['grid_import_kwh']
    renewable_consumed = row['renewable_consumed_kwh']
    discharge = row['battery_discharge_kwh']

    # Self-sufficiency: fraction of demand met without grid import
    if total_demand > 0:
        row['self_sufficiency_ratio'] = (total_demand - grid_import - row['deficit_kwh']) / total_demand
    else:
        row['self_sufficiency_ratio'] = 1.0

    # Self-consumption: fraction of renewable generation consumed or stored locally
    # (includes renewable energy stored in battery, simplified to count at charge time)
    renewable_charge = row.pop('_battery_charge_renewable_kwh', 0.0)
    if total_renewable > 0:
        row['self_consumption_ratio'] = (renewable_consumed + renewable_charge) / total_renewable
    else:
        row['self_consumption_ratio'] = 0.0

    # Renewable fraction of demand met (uses discharge-time renewable fraction,
    # captured before any same-day generator cycle charging dilutes it)
    if total_demand > 0:
        discharge_renewable = row.pop('_discharge_renewable_kwh', 0.0)
        row['renewable_fraction'] = (renewable_consumed + discharge_renewable) / total_demand
    else:
        row.pop('_discharge_renewable_kwh', None)
        row['renewable_fraction'] = 0.0

    # Battery state columns
    if battery_specs is not None:
        row['battery_soc_kwh'] = battery_state['soc_kwh']
        row['battery_soc_fraction'] = battery_state['soc_kwh'] / battery_specs['capacity_kwh']
        row['battery_renewable_fraction'] = battery_state['renewable_fraction']

    # Total energy cost
    row['total_energy_cost'] = (
        row['grid_import_cost']
        + row['generator_fuel_cost']
        - row['grid_export_revenue']
    )

    row['policy_deficit'] = row['deficit_kwh'] > 0.001


# ---------------------------------------------------------------------------
# Internal helpers — dispatch day
# ---------------------------------------------------------------------------

_SURPLUS_ORDER = {
    'minimize_cost': ['battery', 'export', 'curtail'],
    'minimize_grid_reliance': ['battery', 'export', 'curtail'],
    'minimize_generator': ['battery', 'export', 'curtail'],
}

_DEFICIT_ORDER = {
    'minimize_cost': ['battery', 'grid', 'generator'],
    'minimize_grid_reliance': ['battery', 'generator', 'grid'],
    'minimize_generator': ['battery', 'grid', 'generator'],
}


def _handle_surplus(surplus, strategy, row, battery_specs, battery_state,
                    grid_mode, grid_cap_state):
    """Dispatch renewable surplus through battery, export, and curtailment.

    Modifies row dict in place.

    Args:
        surplus: Surplus energy in kWh (positive).
        strategy: Dispatch strategy string.
        row: Mutable row dict to update with dispatch results.
        battery_specs: Battery specs dict or None.
        battery_state: Mutable battery state dict.
        grid_mode: Grid interaction mode string.
        grid_cap_state: Monthly grid cap tracking dict.
    """
    row['renewable_surplus_kwh'] = surplus
    remaining = surplus

    for action in _SURPLUS_ORDER[strategy]:
        if remaining <= 0:
            break

        if action == 'battery' and battery_specs is not None:
            accepted, stored = _charge_battery(
                remaining, battery_specs, battery_state, renewable=True)
            row['battery_charge_kwh'] += accepted
            row['_battery_charge_renewable_kwh'] = row.get('_battery_charge_renewable_kwh', 0.0) + accepted
            remaining -= accepted

        elif action == 'export':
            export_avail = _grid_export_available(grid_mode, grid_cap_state)
            exported = min(remaining, export_avail)
            row['grid_export_kwh'] += exported
            remaining -= exported

        elif action == 'curtail':
            row['curtailed_kwh'] += remaining
            remaining = 0.0


def _handle_deficit(deficit, strategy, row, battery_specs, battery_state,
                    generator_specs, grid_mode, grid_cap_state):
    """Fulfill energy deficit through battery, grid, and generator.

    Modifies row dict in place.

    Args:
        deficit: Deficit energy in kWh (positive).
        strategy: Dispatch strategy string.
        row: Mutable row dict to update with dispatch results.
        battery_specs: Battery specs dict or None.
        battery_state: Mutable battery state dict.
        generator_specs: Generator specs dict or None.
        grid_mode: Grid interaction mode string.
        grid_cap_state: Monthly grid cap tracking dict.
    """
    remaining = deficit

    for action in _DEFICIT_ORDER[strategy]:
        if remaining <= 0:
            break

        if action == 'battery' and battery_specs is not None:
            delivered, soc_draw, ren_del = _discharge_battery(
                remaining, battery_specs, battery_state)
            row['battery_discharge_kwh'] += delivered
            row['_discharge_renewable_kwh'] = row.get('_discharge_renewable_kwh', 0.0) + ren_del
            remaining -= delivered

        elif action == 'grid':
            import_avail = _grid_import_available(grid_mode, grid_cap_state)
            imported = min(remaining, import_avail)
            row['grid_import_kwh'] += imported
            remaining -= imported

        elif action == 'generator' and generator_specs is not None:
            delivered, excess, fuel, hours = _run_generator(
                remaining, generator_specs)
            row['generator_kwh'] += delivered
            row['generator_fuel_liters'] += fuel
            row['generator_runtime_hours'] += hours
            remaining -= delivered

            # Generator min-load excess: charge battery then curtail
            if excess > 0:
                row['generator_excess_kwh'] += excess
                if battery_specs is not None:
                    accepted, stored = _charge_battery(
                        excess, battery_specs, battery_state, renewable=False)
                    row['battery_charge_kwh'] += accepted
                    excess -= accepted
                row['curtailed_kwh'] += excess

    row['deficit_kwh'] = max(0.0, remaining)


def _dispatch_day(day, total_demand_kwh, community_demand_kwh, water_demand_kwh,
                  total_renewable_kwh, total_solar_kwh, total_wind_kwh, ctx):
    """Dispatch energy for a single day.

    Args:
        day: Date for this row.
        total_demand_kwh: Total energy demand (community + water).
        community_demand_kwh: Community building demand for tariff split.
        water_demand_kwh: Water system demand for tariff split.
        total_renewable_kwh: Total renewable generation.
        total_solar_kwh: Solar subtotal (pass-through).
        total_wind_kwh: Wind subtotal (pass-through).
        ctx: Dispatch context dict with keys: battery_specs, generator_specs,
            battery_state, strategy, grid_mode, grid_cap_state,
            net_metering_state, ag_tariff, commercial_tariff, diesel_price,
            export_rate.

    Returns:
        Tuple of (row_dict, battery_state).
    """
    battery_specs = ctx['battery_specs']
    battery_state = ctx['battery_state']
    strategy = ctx['strategy']
    grid_mode = ctx['grid_mode']

    row = _init_energy_dispatch_row(
        day, community_demand_kwh, water_demand_kwh, total_demand_kwh,
        total_solar_kwh, total_wind_kwh, total_renewable_kwh, battery_specs
    )
    row['policy_strategy'] = strategy
    row['policy_grid_mode'] = grid_mode

    net_load = total_demand_kwh - total_renewable_kwh
    row['renewable_consumed_kwh'] = min(total_renewable_kwh, total_demand_kwh)

    if net_load <= 0:
        _handle_surplus(-net_load, strategy, row, battery_specs, battery_state,
                        grid_mode, ctx['grid_cap_state'])
    else:
        _handle_deficit(net_load, strategy, row, battery_specs, battery_state,
                        ctx['generator_specs'], grid_mode, ctx['grid_cap_state'])

    # --- Costs ---
    row['generator_fuel_cost'] = row['generator_fuel_liters'] * ctx['diesel_price']

    if grid_mode == 'net_metering':
        row['grid_import_cost'] = _compute_net_metering_cost(
            row['grid_import_kwh'], row['grid_export_kwh'],
            ctx['net_metering_state'], ctx['ag_tariff'], ctx['commercial_tariff'],
            community_demand_kwh, water_demand_kwh, total_demand_kwh
        )
    else:
        row['grid_import_cost'] = _compute_grid_import_cost(
            row['grid_import_kwh'], community_demand_kwh, water_demand_kwh,
            total_demand_kwh, ctx['ag_tariff'], ctx['commercial_tariff']
        )

    if grid_mode == 'feed_in_tariff':
        row['grid_export_revenue'] = row['grid_export_kwh'] * ctx['export_rate']
    elif grid_mode == 'net_metering':
        row['grid_export_revenue'] = 0.0
    else:
        row['grid_export_revenue'] = 0.0

    _finalize_energy_dispatch_row(row, battery_specs, battery_state)

    return row, battery_state


# ---------------------------------------------------------------------------
# Internal helper — simulation loop
# ---------------------------------------------------------------------------

def _run_simulation(energy_df, demand_df, water_energy_series,
                    battery_specs, generator_specs, policy_config,
                    grid_mode, look_ahead,
                    ag_price_daily, commercial_price_daily, diesel_price_daily,
                    export_rate, dates):
    """Run the daily dispatch loop over the simulation period.

    Args:
        energy_df: Renewable generation DataFrame with day, total_solar_kwh, etc.
        demand_df: Community demand DataFrame with day, total_community_energy_kwh.
        water_energy_series: Dict of daily water energy demand keyed by Timestamp.
        battery_specs: Battery specs dict or None.
        generator_specs: Generator specs dict or None.
        policy_config: Parsed energy policy dict.
        grid_mode: Grid interaction mode.
        look_ahead: Boolean for cap enforcement.
        ag_price_daily: Series of daily ag tariff rates.
        commercial_price_daily: Series of daily commercial tariff rates.
        diesel_price_daily: Series of daily diesel prices.
        export_rate: Grid export rate (USD/kWh).
        dates: DatetimeIndex of simulation dates.

    Returns:
        DataFrame with all daily energy balance columns.
    """
    strategy = policy_config.get('strategy', 'minimize_cost')
    grid_cfg = policy_config.get('grid', {})

    # Initial battery state
    if battery_specs is not None:
        battery_state = {
            'soc_kwh': battery_specs['initial_soc_kwh'],
            'renewable_fraction': 1.0,
        }
    else:
        battery_state = {'soc_kwh': 0.0, 'renewable_fraction': 1.0}

    # Monthly grid cap tracking
    grid_cap_state = {
        'import': {
            'monthly_cap': grid_cfg.get('monthly_import_cap_kwh'),
            'used': 0.0,
            'day': None,
            'look_ahead': look_ahead,
        },
        'export': {
            'monthly_cap': grid_cfg.get('monthly_export_cap_kwh'),
            'used': 0.0,
            'day': None,
            'look_ahead': look_ahead,
        },
    }

    net_metering_state = {
        'monthly_import': 0.0,
        'monthly_export': 0.0,
    }

    # Dispatch context: equipment, policy, and mutable state
    ctx = {
        'battery_specs': battery_specs,
        'generator_specs': generator_specs,
        'battery_state': battery_state,
        'strategy': strategy,
        'grid_mode': grid_mode,
        'grid_cap_state': grid_cap_state,
        'net_metering_state': net_metering_state,
        'export_rate': export_rate,
    }

    # Index energy and demand DataFrames by day for lookup
    energy_lookup = energy_df.set_index('day')
    demand_lookup = demand_df.set_index('day')

    # Validate no duplicate dates
    if energy_lookup.index.duplicated().any():
        raise ValueError("Duplicate dates in energy generation data")
    if demand_lookup.index.duplicated().any():
        raise ValueError("Duplicate dates in community demand data")

    current_month = None
    rows = []

    for day in dates:
        day_ts = pd.Timestamp(day)

        # Month boundary reset
        ym = (day_ts.year, day_ts.month)
        if current_month != ym:
            current_month = ym
            grid_cap_state['import']['used'] = 0.0
            grid_cap_state['export']['used'] = 0.0
            net_metering_state['monthly_import'] = 0.0
            net_metering_state['monthly_export'] = 0.0

        # Update day references for cap calculations
        grid_cap_state['import']['day'] = day_ts
        grid_cap_state['export']['day'] = day_ts

        # Look up daily values
        e_row = energy_lookup.loc[day_ts]
        total_solar = e_row['total_solar_kwh']
        total_wind = e_row['total_wind_kwh']
        total_renewable = e_row['total_renewable_kwh']

        d_row = demand_lookup.loc[day_ts]
        community_demand = d_row['total_community_energy_kwh']

        water_demand = water_energy_series[day_ts]
        total_demand = community_demand + water_demand

        ctx['ag_tariff'] = ag_price_daily.loc[day_ts]
        ctx['commercial_tariff'] = commercial_price_daily.loc[day_ts]
        ctx['diesel_price'] = diesel_price_daily.loc[day_ts]

        row, battery_state = _dispatch_day(
            day=day_ts,
            total_demand_kwh=total_demand,
            community_demand_kwh=community_demand,
            water_demand_kwh=water_demand,
            total_renewable_kwh=total_renewable,
            total_solar_kwh=total_solar,
            total_wind_kwh=total_wind,
            ctx=ctx,
        )

        # Update monthly accumulators
        grid_cap_state['import']['used'] += row['grid_import_kwh']
        grid_cap_state['export']['used'] += row['grid_export_kwh']

        # Stamp cap tracking columns
        row['grid_import_cap_used_kwh'] = grid_cap_state['import']['used']
        row['grid_export_cap_used_kwh'] = grid_cap_state['export']['used']
        import_cap = grid_cap_state['import']['monthly_cap']
        export_cap = grid_cap_state['export']['monthly_cap']
        row['grid_monthly_import_cap_kwh'] = import_cap if import_cap is not None else math.inf
        row['grid_monthly_export_cap_kwh'] = export_cap if export_cap is not None else math.inf

        rows.append(row)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Internal helper — column ordering
# ---------------------------------------------------------------------------

def _order_energy_balance_columns(df):
    """Reorder columns in semantic groups matching the spec.

    Args:
        df: DataFrame with all energy balance columns.

    Returns:
        DataFrame with columns reordered.
    """
    demand_cols = ['day', 'community_energy_demand_kwh', 'water_energy_demand_kwh',
                   'total_demand_kwh']

    generation_cols = ['total_solar_kwh', 'total_wind_kwh', 'total_renewable_kwh']

    dispatch_cols = ['renewable_consumed_kwh', 'renewable_surplus_kwh',
                     'battery_charge_kwh', 'battery_discharge_kwh',
                     'grid_import_kwh', 'grid_export_kwh',
                     'generator_kwh', 'generator_excess_kwh',
                     'curtailed_kwh', 'deficit_kwh']

    battery_cols = ['battery_soc_kwh', 'battery_soc_fraction',
                    'battery_renewable_fraction']

    generator_cols = ['generator_fuel_liters', 'generator_runtime_hours']

    cost_cols = ['grid_import_cost', 'grid_export_revenue',
                 'generator_fuel_cost', 'total_energy_cost']

    metrics_cols = ['self_sufficiency_ratio', 'self_consumption_ratio',
                    'renewable_fraction']

    policy_cols = ['policy_strategy', 'policy_grid_mode', 'policy_deficit',
                   'grid_import_cap_used_kwh', 'grid_export_cap_used_kwh',
                   'grid_monthly_import_cap_kwh', 'grid_monthly_export_cap_kwh']

    ordered = (demand_cols + generation_cols + dispatch_cols + battery_cols
               + generator_cols + cost_cols + metrics_cols + policy_cols)

    # Only include columns present in the DataFrame
    ordered = [c for c in ordered if c in df.columns]
    remaining = [c for c in df.columns if c not in ordered]
    return df[ordered + remaining]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_daily_energy_balance(energy_config_path, energy_policy_path,
                                 community_config_path, farm_profiles_path,
                                 registry_path, *, water_balance_df=None,
                                 root_dir=None):
    """Compute daily energy balance for the community microgrid.

    Orchestrates renewable generation, community demand, and water system
    energy into a unified daily DataFrame with dispatch, storage state,
    grid exchange, cost, and policy decisions.

    Args:
        energy_config_path: Path to energy_system.yaml.
        energy_policy_path: Path to energy_policy.yaml.
        community_config_path: Path to community_demands.yaml.
        farm_profiles_path: Path to farm_profiles.yaml.
        registry_path: Path to data_registry.yaml.
        water_balance_df: Pre-computed water balance DataFrame with
            day and total_water_energy_kwh columns. When None, water
            energy demand is zero.
        root_dir: Repository root. Defaults to parent of settings/.

    Returns:
        DataFrame with all daily energy balance columns.
    """
    from src.energy_supply import compute_daily_energy
    from src.community_demand import compute_daily_demands

    if root_dir is None:
        root_dir = Path(registry_path).parent.parent

    # 1. Renewable generation
    energy_df = compute_daily_energy(
        config_path=energy_config_path,
        registry_path=registry_path,
        farm_profiles_path=farm_profiles_path,
        root_dir=root_dir,
    )

    # 2. Community demand
    demand_df = compute_daily_demands(
        config_path=community_config_path,
        registry_path=registry_path,
        root_dir=root_dir,
    )

    # 3. Water energy demand
    if water_balance_df is not None:
        water_energy = water_balance_df.set_index('day')['total_water_energy_kwh']
    else:
        water_energy = pd.Series(dtype=float)

    # 4. Date intersection
    energy_dates = set(energy_df['day'])
    demand_dates = set(demand_df['day'])
    common_dates = energy_dates & demand_dates
    if water_balance_df is not None:
        water_dates = set(water_balance_df['day'])
        common_dates = common_dates & water_dates

    common_dates = sorted(common_dates)
    if not common_dates:
        raise ValueError(
            'No overlapping dates between input sources. '
            f'Energy: {min(energy_dates).date()}–{max(energy_dates).date()}, '
            f'Demand: {min(demand_dates).date()}–{max(demand_dates).date()}'
            + (f', Water: {min(water_dates).date()}–{max(water_dates).date()}' if water_balance_df is not None else '')
        )
    dates = pd.DatetimeIndex(common_dates)

    energy_df = energy_df[energy_df['day'].isin(dates)].reset_index(drop=True)
    demand_df = demand_df[demand_df['day'].isin(dates)].reset_index(drop=True)

    # 5. Load configs
    energy_config = _load_yaml(energy_config_path)
    policy_config = _load_yaml(energy_policy_path)
    registry = _load_yaml(registry_path)
    paths = _resolve_energy_balance_paths(registry, root_dir)

    # 5b. Validate configs
    _validate_energy_system_config(energy_config)
    _validate_energy_policy_config(policy_config)

    # 6. Load price data — raises ValueError if simulation dates precede price data
    tariff_cfg = policy_config.get('tariff', {})
    ag_key = tariff_cfg.get('water_energy', 'agricultural')
    commercial_key = tariff_cfg.get('building_energy', 'commercial')

    ag_price_series = _load_price_series(paths[ag_key], 'usd_per_kwh_avg_daily')
    commercial_price_series = _load_price_series(paths[commercial_key], 'usd_per_kwh_avg_daily')
    diesel_price_series = _load_price_series(paths['diesel'], 'usd_per_liter')

    ag_price_daily = _daily_price_lookup(ag_price_series, dates)
    commercial_price_daily = _daily_price_lookup(commercial_price_series, dates)
    diesel_price_daily = _daily_price_lookup(diesel_price_series, dates)

    # 7. Equipment specs
    battery_specs = _build_battery_specs(energy_config, policy_config, paths['batteries'])
    generator_specs = _build_generator_specs(energy_config, policy_config, paths['generators'])

    # 8. Grid validation
    grid_connection = energy_config.get('grid_connection', 'full_grid')
    grid_mode = policy_config.get('grid', {}).get('mode', 'self_consumption')
    _validate_grid_config(grid_connection, grid_mode)
    if grid_mode == 'limited_grid':
        import_cap = policy_config.get('grid', {}).get('monthly_import_cap_kwh')
        if import_cap is None:
            raise ValueError(
                "limited_grid mode requires a non-null monthly_import_cap_kwh "
                "in energy policy grid config"
            )

    # 9. Export rate
    export_rate = _resolve_export_rate(policy_config.get('grid', {}), paths)

    # 10. Cap enforcement
    look_ahead = policy_config.get('cap_enforcement', {}).get('look_ahead', True)

    # Water energy as a lookup dict (KeyError on missing days catches alignment bugs)
    if not water_energy.empty:
        water_energy_lookup = water_energy.to_dict()
    else:
        water_energy_lookup = {d: 0.0 for d in dates}

    # 11. Run simulation
    result = _run_simulation(
        energy_df=energy_df,
        demand_df=demand_df,
        water_energy_series=water_energy_lookup,
        battery_specs=battery_specs,
        generator_specs=generator_specs,
        policy_config=policy_config,
        grid_mode=grid_mode,
        look_ahead=look_ahead,
        ag_price_daily=ag_price_daily,
        commercial_price_daily=commercial_price_daily,
        diesel_price_daily=diesel_price_daily,
        export_rate=export_rate,
        dates=dates,
    )

    return _order_energy_balance_columns(result)


def save_energy_balance(df, output_dir, *, filename='daily_energy_balance.csv',
                        decimals=3):
    """Save daily energy balance DataFrame to CSV.

    Args:
        df: DataFrame returned by compute_daily_energy_balance.
        output_dir: Directory to write the output file. Created if needed.
        filename: Output file name.
        decimals: Decimal places for numeric columns.

    Returns:
        Path to the saved CSV file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    numeric_cols = df.select_dtypes(include='number').columns
    out = df.copy()
    out[numeric_cols] = out[numeric_cols].round(decimals)
    out.to_csv(path, index=False)
    return path


# ---------------------------------------------------------------------------
# Entry point for quick verification
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    from src.water_balance import compute_daily_water_balance
    root = Path(__file__).parent.parent
    registry_path = root / 'settings' / 'data_registry_base.yaml'
    water_df = compute_daily_water_balance(
        farm_profiles_path=root / 'settings' / 'farm_profile_base.yaml',
        water_systems_path=root / 'settings' / 'water_systems_base.yaml',
        water_policy_path=root / 'settings' / 'water_policy_base.yaml',
        community_config_path=root / 'settings' / 'community_demands_base.yaml',
        registry_path=registry_path,
    )
    df = compute_daily_energy_balance(
        energy_config_path=root / 'settings' / 'energy_system_base.yaml',
        energy_policy_path=root / 'settings' / 'energy_policy_base.yaml',
        community_config_path=root / 'settings' / 'community_demands_base.yaml',
        farm_profiles_path=root / 'settings' / 'farm_profile_base.yaml',
        registry_path=registry_path,
        water_balance_df=water_df,
    )
    out = save_energy_balance(df, output_dir=root / 'simulation')
    print(f'Saved {len(df)} rows to {out}')
    print(f'Total demand:      {df["total_demand_kwh"].sum():.1f} kWh')
    print(f'Total renewable:   {df["total_renewable_kwh"].sum():.1f} kWh')
    print(f'Grid import:       {df["grid_import_kwh"].sum():.1f} kWh')
    print(f'Generator:         {df["generator_kwh"].sum():.1f} kWh')
    print(f'Curtailed:         {df["curtailed_kwh"].sum():.1f} kWh')
    print(f'Deficit:           {df["deficit_kwh"].sum():.1f} kWh')
    print(f'Total cost:        {df["total_energy_cost"].sum():.2f} USD')
    print(df.head(3).to_string())
