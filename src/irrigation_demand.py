"""Daily irrigation water demand from farm profiles and crop growth data.

Reads farm profiles (fields, plantings, areas, irrigation systems) and
precomputed crop daily growth files to produce daily irrigation water demand
per field, aggregated per water system, with crop TDS requirements.

Conversion: 1 mm of water over 1 ha = 10 m3.
Delivery demand = water_applied_mm * area (ha) * 10 / irrigation_efficiency.

Usage:
    from src.irrigation_demand import compute_irrigation_demand, save_irrigation_demand

    df = compute_irrigation_demand(
        farm_profiles_path='settings/farm_profiles.yaml',
        registry_path='settings/data_registry.yaml',
    )
    save_irrigation_demand(df, output_dir='simulation/')
"""

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.farm_profile import normalize_plantings, validate_no_overlap


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_yaml(path):
    """Load and parse a YAML file."""
    with open(path) as f:
        return yaml.safe_load(f)


def _load_water_policy(path):
    """Resolve irrigation_policy string from a water policy config file.

    For static mode, returns the static_policy value directly.
    For dynamic mode, returns 'full_eto' (full demand used as baseline).
    """
    config = _load_yaml(path)
    mode = config['irrigation']['mode']
    if mode == 'static':
        return config['irrigation']['static_policy']
    return 'full_eto'


def _load_irrigation_efficiency(path):
    """Load irrigation system efficiency lookup.

    Returns dict mapping irrigation type name to efficiency fraction.
    Registers both full names ('drip_irrigation') and short names ('drip')
    so farm_profiles can use either convention.
    """
    df = pd.read_csv(path, comment='#')
    lookup = {}
    for _, row in df.iterrows():
        full_name = row['irrigation_type']
        lookup[full_name] = row['efficiency']
        lookup[full_name.replace('_irrigation', '')] = row['efficiency']
    return lookup


def _load_crop_tds(path):
    """Load TDS no-penalty thresholds per crop.

    Returns dict mapping crop name to tds_no_penalty_ppm.
    """
    df = pd.read_csv(path, comment='#')
    return dict(zip(df['crop'], df['tds_no_penalty_ppm']))


def _load_daily_water_applied(growth_dir, crop, planting, condition, irrigation_policy):
    """Load daily water application from a crop growth file, filtered by irrigation policy.

    Returns DataFrame with columns: date, water_applied_mm, etc_mm, crop.
    water_applied_mm reflects the irrigation policy (e.g. deficit_60 applies ~60% of ETc).
    etc_mm is the biological crop water need, identical across policies (used by yield model).
    One row per calendar date across all weather years (dates are unique).
    """
    path = growth_dir / crop / f"{crop}_{planting}_{condition}-research.csv"
    df = pd.read_csv(path, comment='#', parse_dates=['date'])
    df = df[df['irrigation_policy'] == irrigation_policy]
    result = df[['date', 'water_applied_mm', 'etc_mm']].copy()
    result['crop'] = crop
    return result


def _compute_field_demand(growth_dir, field, irrigation_lookup, irrigation_policy):
    """Compute daily water demand for one field across all its plantings.

    Args:
        growth_dir: Path to crop_daily_growth directory.
        field: Field dict from farm_profiles.yaml.
        irrigation_lookup: Dict mapping irrigation type to efficiency.
        irrigation_policy: Irrigation policy to filter (e.g. 'full_eto').

    Returns:
        DataFrame with columns: date, {name}_etc_mm_per_ha, {name}_demand_m3,
            {name}_etc_m3, {name}_crop.
        demand_m3 uses water_applied_mm (policy-adjusted).
        etc_m3 uses etc_mm (biological crop water need, for yield model).
    """
    name = field['name']
    area_ha = field['area_ha']
    efficiency = irrigation_lookup[field['irrigation_system']]
    condition = field['condition']

    parts = []
    for p in normalize_plantings(field):
        wa_df = _load_daily_water_applied(
            growth_dir, p['crop'], p['planting'], condition, irrigation_policy
        )
        parts.append(wa_df)

    col_etc = f'{name}_etc_mm_per_ha'
    col_demand = f'{name}_demand_m3'
    col_etc_m3 = f'{name}_etc_m3'
    col_crop = f'{name}_crop'

    if not parts:
        return pd.DataFrame(columns=['date', col_etc, col_demand, col_etc_m3, col_crop])

    combined = pd.concat(parts, ignore_index=True).sort_values('date')
    combined[col_etc] = combined['water_applied_mm'].round(2)
    combined[col_demand] = (combined['water_applied_mm'] * area_ha * 10 / efficiency).round(3)
    combined[col_etc_m3] = (combined['etc_mm'] * area_ha * 10 / efficiency).round(3)
    combined[col_crop] = combined['crop']

    return combined[['date', col_etc, col_demand, col_etc_m3, col_crop]]


def _collect_fields(farm_config, water_system_name):
    """Collect all fields linked to a given water system."""
    fields = []
    for farm in farm_config['farms']:
        for field in farm['fields']:
            if field.get('water_system') == water_system_name:
                fields.append(field)
    return fields


def _compute_tds_requirement(result, crop_cols, crop_tds):
    """Compute daily TDS requirement as min tds_no_penalty across active crops.

    On days with no active crop, returns NaN.
    """
    tds = np.full(len(result), np.inf)
    for col in crop_cols:
        for crop_name, tds_val in crop_tds.items():
            mask = (result[col] == crop_name).values
            tds[mask] = np.minimum(tds[mask], tds_val)
    tds[np.isinf(tds)] = np.nan
    return tds


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_irrigation_demand(farm_profiles_path, registry_path, *,
                              water_system_name='main_irrigation',
                              irrigation_policy='full_eto',
                              water_policy_path=None,
                              root_dir=None):
    """Compute daily irrigation water demand for a water system.

    Reads farm profiles to find all fields linked to the specified water system,
    loads their crop daily growth data under the specified condition, and scales
    ETc by field area and irrigation efficiency to produce water delivery demand
    in m3/day.

    Args:
        farm_profiles_path: Path to farm_profiles.yaml.
        registry_path: Path to data_registry.yaml.
        water_system_name: Name of the water system to compute demand for.
        irrigation_policy: Irrigation policy from crop growth files.
        water_policy_path: Optional path to water_policy.yaml. When provided,
            overrides irrigation_policy: static mode uses static_policy value;
            dynamic mode uses 'full_eto' as the demand baseline.
        root_dir: Repository root. Defaults to parent of settings/.

    Returns:
        DataFrame with columns:
            - day
            - {field}_etc_mm_per_ha  (per field, policy-adjusted water_applied_mm)
            - {field}_demand_m3      (per field, policy-adjusted, area + efficiency scaled)
            - {field}_etc_m3         (per field, full ETc reference for yield model)
            - {field}_crop           (crop name active on that date, 'none' if fallow)
            - total_demand_m3        (sum across all fields)
            - crop_tds_requirement_ppm (min TDS threshold across active crops)
    """
    if water_policy_path is not None:
        irrigation_policy = _load_water_policy(water_policy_path)

    if root_dir is None:
        root_dir = Path(registry_path).parent.parent

    farm_config = _load_yaml(farm_profiles_path)
    registry = _load_yaml(registry_path)
    validate_no_overlap(farm_config, registry, root_dir)

    growth_dir = root_dir / registry['crops']['daily_growth_dir']
    irrig_path = root_dir / registry['water_supply']['irrigation_systems']
    crop_params_path = root_dir / registry['crops']['growth_params']

    irrig_lookup = _load_irrigation_efficiency(irrig_path)
    crop_tds = _load_crop_tds(crop_params_path)
    fields = _collect_fields(farm_config, water_system_name)

    field_dfs = [
        _compute_field_demand(growth_dir, f, irrig_lookup, irrigation_policy)
        for f in fields
    ]

    # Build a complete daily date axis for full calendar years.
    # Ensures every day of each year is plotted (365/366 days) and fallow days
    # (when no field has a crop) are included with zero demand.
    all_dates_union = pd.concat([df[['date']] for df in field_dfs]).drop_duplicates()
    date_min = all_dates_union['date'].min()
    date_max = all_dates_union['date'].max()
    year_min = date_min.year
    year_max = date_max.year
    all_dates = pd.DataFrame({
        'date': pd.date_range(
            start=pd.Timestamp(year=year_min, month=1, day=1),
            end=pd.Timestamp(year=year_max, month=12, day=31),
            freq='D',
        ),
    })
    result = all_dates.copy()

    demand_cols = []
    etc_cols = []
    etc_m3_cols = []
    crop_cols = []
    for fdf in field_dfs:
        demand_col = [c for c in fdf.columns if c.endswith('_demand_m3')][0]
        etc_col = [c for c in fdf.columns if c.endswith('_etc_mm_per_ha')][0]
        etc_m3_col = [c for c in fdf.columns if c.endswith('_etc_m3')][0]
        crop_col = [c for c in fdf.columns if c.endswith('_crop')][0]
        demand_cols.append(demand_col)
        etc_cols.append(etc_col)
        etc_m3_cols.append(etc_m3_col)
        crop_cols.append(crop_col)
        result = result.merge(fdf, on='date', how='left')

    for col in demand_cols + etc_cols + etc_m3_cols:
        result[col] = result[col].fillna(0.0)
    for col in crop_cols:
        result[col] = result[col].fillna('none')

    result['total_demand_m3'] = result[demand_cols].sum(axis=1).round(3)
    result['crop_tds_requirement_ppm'] = _compute_tds_requirement(result, crop_cols, crop_tds)
    result = result.rename(columns={'date': 'day'})

    return result


def get_field_irrigation_specs(farm_profiles_path, registry_path, *,
                               water_system_name='main_irrigation', root_dir=None):
    """Return per-field irrigation specs for application energy calculation.

    Loads farm profiles and irrigation system data to build a lookup of
    each field's irrigation system type and application energy rate.

    Args:
        farm_profiles_path: Path to farm_profiles.yaml.
        registry_path: Path to data_registry.yaml.
        water_system_name: Name of the water system to collect fields for.
        root_dir: Repository root. Defaults to parent of settings/.

    Returns:
        Dict mapping field_name to dict with keys:
            - irrigation_system: str (e.g. 'drip')
            - application_energy_kwh_per_m3: float
    """
    if root_dir is None:
        root_dir = Path(registry_path).parent.parent

    farm_config = _load_yaml(farm_profiles_path)
    registry = _load_yaml(registry_path)
    irrig_path = root_dir / registry['water_supply']['irrigation_systems']

    df = pd.read_csv(irrig_path, comment='#')
    energy_lookup = {}
    for _, row in df.iterrows():
        full_name = row['irrigation_type']
        energy_lookup[full_name] = row['application_energy_kwh_per_m3']
        energy_lookup[full_name.replace('_irrigation', '')] = row['application_energy_kwh_per_m3']

    fields = _collect_fields(farm_config, water_system_name)
    specs = {}
    for field in fields:
        irrig_sys = field['irrigation_system']
        specs[field['name']] = {
            'irrigation_system': irrig_sys,
            'application_energy_kwh_per_m3': energy_lookup[irrig_sys],
        }
    return specs


def save_irrigation_demand(df, output_dir, *, filename='daily_irrigation_demand.csv', decimals=3):
    """Save daily irrigation demand DataFrame to CSV.

    Args:
        df: DataFrame returned by compute_irrigation_demand.
        output_dir: Directory to write the output file.
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


# ---------------------------------------------------------------------------
# Entry point for quick verification
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    root = Path(__file__).parent.parent
    df = compute_irrigation_demand(
        farm_profiles_path=root / 'settings' / 'farm_profile_base.yaml',
        registry_path=root / 'settings' / 'data_registry_base.yaml',
    )
    out = save_irrigation_demand(df, output_dir=root / 'simulation')

    active_days = (df['total_demand_m3'] > 0).sum()
    peak = df['total_demand_m3'].max()
    print(f"Saved {len(df)} rows to {out}")
    print(f"Active days: {active_days}, Peak demand: {peak:.1f} m3/day")
    print(f"Date range: {df['day'].min()} to {df['day'].max()}")
    print(df.head(3).to_string())
