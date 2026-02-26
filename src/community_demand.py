"""Daily community energy and water demand computation.

Parses community configuration (household counts, building areas, multipliers) and
precomputed per-unit demand data to produce scaled daily totals for each building type.

Usage:
    from src.demand import compute_daily_demands, save_demands

    df = compute_daily_demands(
        config_path='settings/community_demands.yaml',
        registry_path='settings/data_registry.yaml',
    )
    save_demands(df, output_dir='simulation/')
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
    return pd.read_csv(path, comment='#', parse_dates=['date'])


def _resolve_paths(registry, root_dir):
    """Resolve relative data paths from registry to absolute paths.

    Args:
        registry: Parsed data_registry.yaml dict.
        root_dir: Repository root directory.

    Returns:
        Dict mapping registry key to absolute Path.
    """
    return {k: Path(root_dir) / v for k, v in registry['building_demands'].items()}


def _scale_households(df, households, src_suffix, out_suffix, scale_key, multiplier_key):
    """Scale per-unit household demand to community totals for one resource type.

    Args:
        df: DataFrame with per-unit demand columns named '{hh_type}_{src_suffix}'.
        households: Dict of household config from community_demands.yaml.
        src_suffix: Column suffix in source data (e.g., 'kwh').
        out_suffix: Column suffix for output (e.g., 'energy_kwh').
        scale_key: Config key for unit count (e.g., 'count').
        multiplier_key: Config key for optional demand multiplier (e.g., 'energy_multiplier').

    Returns:
        DataFrame with one scaled total column per household type.
    """
    cols = {
        f'{hh_type}_{out_suffix}': (
            df[f'{hh_type}_{src_suffix}']
            * cfg[scale_key]
            * cfg.get(multiplier_key, 1.0)
        )
        for hh_type, cfg in households.items()
    }
    return pd.DataFrame(cols)


def _scale_buildings(df, buildings, src_suffix, out_suffix, scale_key, multiplier_key):
    """Scale per-m² building demand factors to community totals for one resource type.

    Args:
        df: DataFrame with per-m² demand columns named '{bld_type}_{src_suffix}'.
        buildings: Dict of building config from community_demands.yaml.
        src_suffix: Column suffix in source data (e.g., 'kwh_per_m2').
        out_suffix: Column suffix for output (e.g., 'energy_kwh').
        scale_key: Config key for area scaling (e.g., 'area_m2').
        multiplier_key: Config key for optional demand multiplier (e.g., 'energy_multiplier').

    Returns:
        DataFrame with one scaled total column per building type.
    """
    cols = {
        f'{bld_type}_{out_suffix}': (
            df[f'{bld_type}_{src_suffix}']
            * cfg[scale_key]
            * cfg.get(multiplier_key, 1.0)
        )
        for bld_type, cfg in buildings.items()
    }
    return pd.DataFrame(cols)


def _add_totals(df, hh_energy_cols, hh_water_cols, bld_energy_cols, bld_water_cols):
    """Append subtotal and grand total columns for energy and water.

    Args:
        df: DataFrame with all per-type demand columns.
        hh_energy_cols: List of household energy column names.
        hh_water_cols: List of household water column names.
        bld_energy_cols: List of building energy column names.
        bld_water_cols: List of building water column names.

    Returns:
        DataFrame with subtotal and total columns appended.
    """
    df = df.copy()
    df['total_household_energy_kwh'] = df[hh_energy_cols].sum(axis=1)
    df['total_building_energy_kwh'] = df[bld_energy_cols].sum(axis=1)
    df['total_energy_kwh'] = df['total_household_energy_kwh'] + df['total_building_energy_kwh']
    df['total_household_water_m3'] = df[hh_water_cols].sum(axis=1)
    df['total_building_water_m3'] = df[bld_water_cols].sum(axis=1)
    df['total_water_m3'] = df['total_household_water_m3'] + df['total_building_water_m3']
    return df


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_daily_demands(config_path, registry_path, *, root_dir=None):
    """Compute daily community energy and water demands.

    Combines precomputed per-unit demand data with community configuration
    (household counts, building areas, and optional multipliers) to produce
    scaled daily totals for each building type, plus community-wide subtotals
    and grand totals.

    Args:
        config_path: Path to community_demands.yaml.
        registry_path: Path to data_registry.yaml.
        root_dir: Repository root directory. Defaults to the parent of the
            directory containing registry_path (i.e., parent of settings/).

    Returns:
        DataFrame indexed by day with columns:
            - day
            - {hh_type}_energy_kwh  (per household type, total across all units)
            - {hh_type}_water_m3    (per household type, total across all units)
            - {bld_type}_energy_kwh (per building type)
            - {bld_type}_water_m3   (per building type)
            - total_household_energy_kwh, total_building_energy_kwh, total_energy_kwh
            - total_household_water_m3, total_building_water_m3, total_water_m3
    """
    if root_dir is None:
        root_dir = Path(registry_path).parent.parent

    config = _load_yaml(config_path)
    registry = _load_yaml(registry_path)
    paths = _resolve_paths(registry, root_dir)

    households = config['households']
    buildings = config['community_buildings']

    hh_energy_df = _load_csv(paths['household_energy'])
    hh_water_df = _load_csv(paths['household_water'])
    bld_energy_df = _load_csv(paths['buildings_energy'])
    bld_water_df = _load_csv(paths['buildings_water'])

    hh_energy = _scale_households(hh_energy_df, households, 'kwh', 'energy_kwh', 'count', 'energy_multiplier')
    hh_water = _scale_households(hh_water_df, households, 'm3', 'water_m3', 'count', 'water_multiplier')
    bld_energy = _scale_buildings(bld_energy_df, buildings, 'kwh_per_m2', 'energy_kwh', 'area_m2', 'energy_multiplier')
    bld_water = _scale_buildings(bld_water_df, buildings, 'm3_per_m2', 'water_m3', 'area_m2', 'water_multiplier')

    df = pd.concat(
        [hh_energy_df[['date']].rename(columns={'date': 'day'}), hh_energy, hh_water, bld_energy, bld_water],
        axis=1,
    )

    return _add_totals(
        df,
        hh_energy_cols=list(hh_energy.columns),
        hh_water_cols=list(hh_water.columns),
        bld_energy_cols=list(bld_energy.columns),
        bld_water_cols=list(bld_water.columns),
    )


def save_demands(df, output_dir, *, filename='community_daily_demands.csv', decimals=3):
    """Save daily demands DataFrame to CSV.

    Args:
        df: DataFrame returned by compute_daily_demands.
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


def load_demands(path):
    """Load a saved demands CSV produced by save_demands.

    Args:
        path: Path to the demands CSV file.

    Returns:
        DataFrame with the same structure as compute_daily_demands output.
    """
    return pd.read_csv(path, parse_dates=['day'])


# ---------------------------------------------------------------------------
# Entry point for quick verification
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    root = Path(__file__).parent.parent
    df = compute_daily_demands(
        config_path=root / 'settings' / 'community_demands_base.yaml',
        registry_path=root / 'settings' / 'data_registry_base.yaml',
    )
    out = save_demands(df, output_dir=root / 'simulation')
    print(f'Saved {len(df)} rows to {out}')
    print(df.head(3).to_string())
