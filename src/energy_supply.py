"""Daily community energy supply computation.

Parses energy system configuration (community solar area by density, wind turbine
counts) and optionally farm profiles (agri-PV fields) along with precomputed
per-unit energy output data to produce scaled daily totals for each generator type,
category subtotals, and a combined total.

Usage:
    from src.energy import compute_daily_energy, save_energy

    df = compute_daily_energy(
        config_path='settings/energy_system.yaml',
        registry_path='settings/data_registry.yaml',
        farm_profiles_path='settings/farm_profiles.yaml',
    )
    save_energy(df, output_dir='simulation/')
"""

import yaml
import pandas as pd
from pathlib import Path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_yaml(path):
    """Load and parse a YAML file."""
    with open(path) as f:
        return yaml.safe_load(f)


def _load_csv(path):
    """Load CSV, skipping comment lines that start with '#', parsing 'date' column."""
    df = pd.read_csv(path, comment='#', parse_dates=['date'])
    df = df.drop(columns=['weather_scenario_id'], errors='ignore')
    return df


def _resolve_energy_paths(registry, root_dir):
    """Resolve relative energy supply paths from registry to absolute paths.

    Args:
        registry: Parsed data_registry.yaml dict.
        root_dir: Repository root directory.

    Returns:
        Dict mapping registry key to absolute Path.
    """
    return {k: Path(root_dir) / v for k, v in registry['energy_supply'].items() if v is not None}


def _scale_solar(pv_df, solar_config):
    """Scale per-hectare PV output to community totals for each density level.

    Expects CSV columns named '{config_key}_kwh_per_ha' (e.g. low_density_kwh_per_ha).
    Output columns are named '{config_key}_comm_solar_kwh'.

    Args:
        pv_df: DataFrame with per-ha output columns and a 'date' column.
        solar_config: Dict of solar config entries from energy_system.yaml,
            keyed by density label (e.g. low_density). Each entry must have
            an 'area_ha' field.

    Returns:
        DataFrame with one scaled total column per density level.
    """
    cols = {
        f'{key}_comm_solar_kwh': pv_df[f'{key}_kwh_per_ha'] * cfg['area_ha']
        for key, cfg in solar_config.items()
    }
    return pd.DataFrame(cols)


def _scale_wind(wind_df, wind_config):
    """Scale per-turbine wind output to community totals for each turbine type.

    Expects CSV columns named '{config_key}_kwh' (e.g. small_turbine_kwh).
    Output columns are named '{config_key}_wind_kwh'.

    Args:
        wind_df: DataFrame with per-turbine output columns and a 'date' column.
        wind_config: Dict of wind turbine config entries from energy_system.yaml,
            keyed by turbine label (e.g. small_turbine). Each entry must have
            a 'number' field.

    Returns:
        DataFrame with one scaled total column per turbine type.
    """
    cols = {
        f'{key}_wind_kwh': wind_df[f'{key}_kwh'] * cfg['number']
        for key, cfg in wind_config.items()
    }
    return pd.DataFrame(cols)


def _extract_agripv_farms(farm_config):
    """Extract agri-PV field specs from farm profiles.

    Includes all farms. Farms without underpv fields get an empty list,
    producing a zero-valued column in the output.

    Args:
        farm_config: Parsed farm_profiles.yaml dict.

    Returns:
        Dict mapping every farm name to a list of (density_key, area_ha) tuples.
    """
    farms = {}
    for farm in farm_config['farms']:
        fields = []
        for field in farm['fields']:
            cond = field['condition']
            if cond.startswith('underpv_'):
                density_key = cond.replace('underpv_', '') + '_density'
                fields.append((density_key, field['area_ha']))
        farms[farm['name']] = fields
    return farms


def _scale_agripv(pv_df, agripv_farms):
    """Scale per-hectare PV output to agri-PV totals for each farm.

    For each farm, sums energy across all underpv fields. Farms with no
    underpv fields produce a column of zeros.

    Args:
        pv_df: DataFrame with per-ha PV output columns.
        agripv_farms: Dict from _extract_agripv_farms mapping farm name
            to list of (density_key, area_ha) tuples.

    Returns:
        DataFrame with one column per farm: '{farm_name}_agripv_kwh'.
    """
    cols = {}
    for farm_name, fields in agripv_farms.items():
        if fields:
            total = sum(
                pv_df[f'{density_key}_kwh_per_ha'] * area_ha
                for density_key, area_ha in fields
            )
        else:
            total = 0
        cols[f'{farm_name}_agripv_kwh'] = total
    return pd.DataFrame(cols, index=pv_df.index)


def _apply_degradation(df, solar_cols, rate_per_year, start_date):
    """Apply annual degradation to solar output columns.

    Args:
        df: DataFrame with a 'day' column and solar energy columns.
        solar_cols: List of solar column names to degrade.
        rate_per_year: Annual degradation rate (e.g., 0.005 for 0.5%/yr).
        start_date: Reference date for year-zero (installation date).

    Returns:
        DataFrame with degraded solar columns and updated totals.
    """
    df = df.copy()
    years_elapsed = (df['day'] - pd.Timestamp(start_date)).dt.days / 365.25
    factor = (1 - rate_per_year) ** years_elapsed
    for col in solar_cols:
        df[col] = df[col] * factor
    return df


def _add_energy_totals(df, solar_cols, wind_cols):
    """Append solar subtotal, wind subtotal, and combined total columns.

    Args:
        df: DataFrame with all per-generator energy columns.
        solar_cols: List of solar generator column names.
        wind_cols: List of wind generator column names.

    Returns:
        DataFrame with subtotal and total columns appended.
    """
    df = df.copy()
    df['total_solar_kwh'] = df[solar_cols].sum(axis=1)
    df['total_wind_kwh'] = df[wind_cols].sum(axis=1)
    df['total_energy_kwh'] = df['total_solar_kwh'] + df['total_wind_kwh']
    return df


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_daily_energy(config_path, registry_path, *, farm_profiles_path=None, root_dir=None,
                         degradation_rate=0.005, degradation_start=None):
    """Compute daily community energy supply from solar and wind generators.

    Combines precomputed per-unit energy output data with energy system
    configuration (community solar area by density, wind turbine counts)
    and optionally farm profiles (agri-PV fields) to produce scaled daily
    totals for each generator type, category subtotals, and a combined total.

    Args:
        config_path: Path to energy_system.yaml.
        registry_path: Path to data_registry.yaml.
        farm_profiles_path: Path to farm_profiles.yaml. When provided, fields
            with underpv_* conditions contribute agri-PV energy columns.
        root_dir: Repository root directory. Defaults to the parent of the
            directory containing registry_path (i.e., parent of settings/).
        degradation_rate: Annual solar degradation rate as a fraction
            (default 0.005 = 0.5%/yr per IEC 61215). Set to 0 or None
            to disable degradation.
        degradation_start: Reference date for year-zero (installation date).
            Accepts any value parseable by pd.Timestamp. Defaults to the
            first date in the dataset when None.

    Returns:
        DataFrame with columns:
            - day
            - {farm_name}_agripv_kwh  (per farm with underpv fields, if farm_profiles_path given)
            - {density}_comm_solar_kwh (per community solar density level)
            - {turbine}_wind_kwh      (per turbine type, total across all units)
            - total_solar_kwh         (agri-PV + community solar)
            - total_wind_kwh
            - total_energy_kwh
    """
    if root_dir is None:
        root_dir = Path(registry_path).parent.parent

    config = _load_yaml(config_path)
    registry = _load_yaml(registry_path)
    paths = _resolve_energy_paths(registry, root_dir)

    solar_config = config['community_solar']
    wind_config = config['wind_turbines']

    pv_df = _load_csv(paths['pv_energy'])
    wind_df = _load_csv(paths['wind_energy'])

    community_solar = _scale_solar(pv_df, solar_config)
    wind = _scale_wind(wind_df, wind_config)

    if farm_profiles_path is not None:
        farm_config = _load_yaml(farm_profiles_path)
        agripv = _scale_agripv(pv_df, _extract_agripv_farms(farm_config))
    else:
        agripv = pd.DataFrame()

    day = pv_df['date'].rename('day')
    community_solar = community_solar.assign(day=day.values)
    wind = wind.assign(day=day.values)

    parts = [community_solar]
    if not agripv.empty:
        agripv = agripv.assign(day=day.values)
        parts.insert(0, agripv)
    parts.append(wind)

    df = parts[0]
    for part in parts[1:]:
        df = df.merge(part, on='day')

    # Reorder: day first, then agripv, community solar, wind
    agripv_cols = [c for c in agripv.columns if c != 'day'] if not agripv.empty else []
    col_order = ['day'] + agripv_cols
    col_order += [c for c in community_solar.columns if c != 'day']
    col_order += [c for c in wind.columns if c != 'day']
    df = df[col_order]

    solar_cols = agripv_cols + [c for c in community_solar.columns if c != 'day']
    wind_cols = [c for c in wind.columns if c != 'day']

    df = _add_energy_totals(df, solar_cols=solar_cols, wind_cols=wind_cols)

    if degradation_rate and degradation_rate > 0:
        start = pd.Timestamp(degradation_start) if degradation_start else df['day'].iloc[0]
        df = _apply_degradation(df, solar_cols, degradation_rate, start)
        df['total_solar_kwh'] = df[solar_cols].sum(axis=1)
        df['total_energy_kwh'] = df['total_solar_kwh'] + df['total_wind_kwh']

    return df


def save_energy(df, output_dir, *, filename='daily_energy_generation.csv', decimals=3):
    """Save daily energy supply DataFrame to CSV.

    Args:
        df: DataFrame returned by compute_daily_energy.
        output_dir: Directory to write the output file. Created if it does not exist.
        filename: Output file name.
        decimals: Number of decimal places to round numeric columns (default 3).

    Returns:
        Path to the saved CSV file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    df.round(decimals).to_csv(path, index=False)
    return path


def load_energy(path):
    """Load a saved energy generation CSV produced by save_energy.

    Args:
        path: Path to the energy generation CSV file.

    Returns:
        DataFrame with the same structure as compute_daily_energy output.
    """
    return pd.read_csv(path, parse_dates=['day'])


# ---------------------------------------------------------------------------
# Entry point for quick verification
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    root = Path(__file__).parent.parent
    df = compute_daily_energy(
        config_path=root / 'settings' / 'energy_system_base.yaml',
        registry_path=root / 'settings' / 'data_registry_base.yaml',
        farm_profiles_path=root / 'settings' / 'farm_profile_base.yaml',
    )
    out = save_energy(df, output_dir=root / 'simulation')
    print(f'Saved {len(df)} rows to {out}')
    print(df.head(3).to_string())
