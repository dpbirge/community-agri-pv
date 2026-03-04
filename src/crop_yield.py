"""Harvest yield computation from water stress history.

Used in dynamic irrigation mode to compute final crop yield after a simulation
run, based on the ratio of actual water delivered (ETa) to potential demand (ETc).

Formula (FAO Paper 33, Doorenbos & Kassam 1979):
    f     = ETa_season / ETc_season
    alpha = max(1.0, 1 + wue_curvature * (1.15 - ky_whole_season))
    yield_kg_ha = potential_yield_kg_ha * f**(1/alpha) * avg_Kt

Matches the yield model in data/_scripts/generate_crop_lookup.py so that
compute_harvest_yield() cross-validates against precomputed lookup CSV values.

Usage:
    from src.crop_yield import compute_harvest_yield, compute_community_harvest

    yield_kg_ha = compute_harvest_yield(
        crop='tomato',
        planting='feb15',
        condition='openfield',
        weather_year=2010,
        delivered_m3_series=actual_series,
        demand_m3_series=demand_series,
        registry_path='settings/data_registry_base.yaml',
    )

    daily_df, harvests_df = compute_community_harvest(
        water_balance_df,
        farm_profiles_path='settings/farm_profile_base.yaml',
        registry_path='settings/data_registry_base.yaml',
    )
"""

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.farm_profile import normalize_plantings, planting_code_to_mmdd, _load_season_lengths


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_yaml(path):
    """Load and parse a YAML file."""
    with open(path) as f:
        return yaml.safe_load(f)


def _load_yield_params(registry, root_dir, crop):
    """Load yield response and growth parameters for one crop.

    Reads yield_response_factors CSV for ky_whole_season and wue_curvature,
    and crop_growth_params CSV for potential_yield_kg_per_ha.

    Args:
        registry: Parsed data_registry dict.
        root_dir: Repository root Path.
        crop: Crop name string (e.g. 'tomato').

    Returns:
        dict with keys: potential_yield_kg_per_ha, ky_whole_season, wue_curvature.
    """
    yrf_path = root_dir / registry['crops']['yield_response_factors']
    yrf_df = pd.read_csv(yrf_path, comment='#')
    yrf_row = yrf_df[yrf_df['crop'] == crop].iloc[0]

    cgp_path = root_dir / registry['crops']['growth_params']
    cgp_df = pd.read_csv(cgp_path, comment='#')
    cgp_row = cgp_df[cgp_df['crop'] == crop].iloc[0]

    return {
        'potential_yield_kg_per_ha': cgp_row['potential_yield_kg_per_ha'],
        'ky_whole_season':           yrf_row['ky_whole_season'],
        'wue_curvature':             yrf_row['wue_curvature'],
    }


def _load_season_kt(growth_dir, crop, planting, condition, weather_year):
    """Load daily temp_stress_coeff from crop growth CSV for one season.

    Filters to full_eto policy -- temp_stress_coeff depends only on temperature,
    not water application, so it is identical across irrigation policies for the
    same weather year.

    Args:
        growth_dir: Path to crop_daily_growth directory.
        crop: Crop name (e.g. 'tomato').
        planting: Planting date code matching growth file name (e.g. 'feb15').
        condition: Growing condition (e.g. 'openfield').
        weather_year: Integer year for temperature stress lookup.

    Returns:
        pd.Series of temp_stress_coeff indexed by pd.DatetimeIndex.
    """
    path = growth_dir / crop / f"{crop}_{planting}_{condition}-research.csv"
    df = pd.read_csv(path, comment='#', parse_dates=['date'])
    df = df[(df['irrigation_policy'] == 'full_eto') & (df['weather_year'] == weather_year)]
    return df.set_index('date')['temp_stress_coeff']


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_harvest_yield(crop, planting, condition, weather_year,
                          delivered_m3_series, demand_m3_series,
                          *, registry_path, root_dir=None):
    """Compute predicted fresh yield for one field after a dynamic-mode season.

    Implements the FAO Paper 33 water-yield response function:
        f     = ETa_season / ETc_season
        alpha = max(1.0, 1 + wue_curvature * (1.15 - ky_whole_season))
        yield_kg_ha = potential_yield_kg_ha * f**(1/alpha) * avg_Kt

    Args:
        crop: Crop name (e.g. 'tomato').
        planting: Planting date code matching growth file name (e.g. 'feb15').
        condition: Growing condition (e.g. 'openfield').
        weather_year: Integer year for temperature stress lookup.
        delivered_m3_series: pd.Series of actual water delivered to field (m3/day),
            indexed by date. Output from water system simulation.
        demand_m3_series: pd.Series of full_eto demand for field (m3/day),
            indexed by date. Output from compute_irrigation_demand(irrigation_policy='full_eto').
        registry_path: Path to data_registry.yaml.
        root_dir: Repository root. Defaults to parent of settings/.

    Returns:
        float: Predicted fresh weight yield in kg/ha.
    """
    # 1. Resolve paths
    registry_path = Path(registry_path)
    if root_dir is None:
        root_dir = registry_path.parent.parent
    root_dir = Path(root_dir)

    registry = _load_yaml(registry_path)

    # 2. Load yield params
    params = _load_yield_params(registry, root_dir, crop)
    potential_yield  = params['potential_yield_kg_per_ha']
    ky               = params['ky_whole_season']
    wue_curvature    = params['wue_curvature']

    # 3. Load season Kt series
    growth_dir = root_dir / registry['crops']['daily_growth_dir']
    kt_series = _load_season_kt(growth_dir, crop, planting, condition, weather_year)

    # 4. Align delivered and demand on common dates (inner join)
    aligned = pd.concat(
        [delivered_m3_series.rename('delivered'), demand_m3_series.rename('demand')],
        axis=1, join='inner'
    )

    # 5. ETa per day = min(delivered, demand); ETc per day = demand
    eta_daily = np.minimum(aligned['delivered'].values, aligned['demand'].values)
    etc_daily = aligned['demand'].values

    # 6. Compute f = sum(ETa) / sum(ETc); clamp to [0, 1]
    eta_season = eta_daily.sum()
    etc_season = etc_daily.sum()
    f = (eta_season / etc_season) if etc_season > 0 else 0.0
    f = min(f, 1.0)

    # 7. avg_Kt = mean of Kt aligned to the season dates
    kt_aligned = kt_series.reindex(aligned.index)
    avg_kt = kt_aligned.mean()

    # 8. alpha = max(1.0, 1 + wue_curvature * (1.15 - ky_whole_season))
    alpha = max(1.0, 1.0 + wue_curvature * (1.15 - ky))

    # 9. Yield uses FAO Paper 33 water-response formula, not cumulative biomass
    #    from growth CSVs. Biomass columns in daily growth files are diagnostic only.
    yield_kg_ha = potential_yield * (f ** (1.0 / alpha)) * avg_kt

    # 10. Return float
    return float(yield_kg_ha)


def _build_daily_harvest_df(harvest_records, sim_start, sim_end):
    """Pivot harvest records into a daily DataFrame with per-field-crop columns.

    Args:
        harvest_records: List of dicts with harvest_date, field, crop, harvest_kg.
        sim_start: First day of simulation (pd.Timestamp).
        sim_end: Last day of simulation (pd.Timestamp).

    Returns:
        DataFrame with 'day' plus '{field}_{crop}_harvest_kg' columns and
        'total_harvest_kg'.
    """
    all_days = pd.DataFrame({'day': pd.date_range(sim_start, sim_end, freq='D')})

    # Accumulate harvest_kg per (date, field_crop column)
    field_crop_values = {}
    for rec in harvest_records:
        col = f"{rec['field']}_{rec['crop']}_harvest_kg"
        if col not in field_crop_values:
            field_crop_values[col] = {}
        d = rec['harvest_date']
        field_crop_values[col][d] = field_crop_values[col].get(d, 0) + rec['harvest_kg']

    daily_df = all_days.copy()
    for col in sorted(field_crop_values):
        daily_df[col] = daily_df['day'].map(field_crop_values[col]).fillna(0.0).round(1)

    harvest_cols = [c for c in daily_df.columns if c.endswith('_harvest_kg')]
    daily_df['total_harvest_kg'] = daily_df[harvest_cols].sum(axis=1).round(1)

    return daily_df


def compute_community_harvest(water_balance_df, *, farm_profiles_path,
                               registry_path, root_dir=None):
    """Compute harvest yields for all fields, crops, plantings, and years.

    Iterates over every (farm, field, crop, planting_code, year) combination
    in the farm profile. For each, extracts the delivered and demand series
    from the water balance DataFrame and calls compute_harvest_yield().

    Args:
        water_balance_df: DataFrame from compute_daily_water_balance() with
            per-field delivered_m3 and etc_m3 columns plus a 'day' column.
        farm_profiles_path: Path to farm_profile YAML.
        registry_path: Path to data_registry YAML.
        root_dir: Repository root. Defaults to registry_path.parent.parent.

    Returns:
        Tuple of (daily_df, harvests_df) where:
            daily_df: DataFrame with 'day' column plus per-field-crop harvest_kg
                columns and total_harvest_kg. One row per calendar day; non-harvest
                days are zero.
            harvests_df: DataFrame with one row per harvest event containing
                harvest_date, field, crop, planting, condition, yield_kg_per_ha,
                area_ha, harvest_kg.
    """
    registry_path = Path(registry_path)
    if root_dir is None:
        root_dir = registry_path.parent.parent
    root_dir = Path(root_dir)

    farm_config = _load_yaml(farm_profiles_path)
    registry = _load_yaml(registry_path)
    season_lookup = _load_season_lengths(registry, root_dir)

    sim_start = water_balance_df['day'].min()
    sim_end = water_balance_df['day'].max()

    harvest_records = []
    for farm in farm_config['farms']:
        for field in farm['fields']:
            field_name = field['name']
            area_ha = field['area_ha']
            condition = field['condition']
            delivered_col = f'{field_name}_delivered_m3'
            etc_col = f'{field_name}_etc_m3'

            for planting_entry in field['plantings']:
                crop = planting_entry['crop']
                for planting_code in planting_entry['plantings']:
                    mmdd = planting_code_to_mmdd(planting_code)
                    season_length = season_lookup[(crop, mmdd)]

                    for year in range(sim_start.year, sim_end.year + 1):
                        planting_date = pd.Timestamp(f'{year}-{mmdd}')
                        harvest_date = planting_date + pd.Timedelta(days=season_length)

                        if harvest_date > sim_end or planting_date < sim_start:
                            continue

                        mask = (water_balance_df['day'] >= planting_date) & (
                            water_balance_df['day'] < harvest_date)
                        season_df = water_balance_df.loc[mask]
                        if season_df.empty:
                            continue

                        delivered = season_df.set_index('day')[delivered_col]
                        etc_ref = season_df.set_index('day')[etc_col]

                        yield_kg_ha = compute_harvest_yield(
                            crop=crop, planting=planting_code,
                            condition=condition, weather_year=year,
                            delivered_m3_series=delivered,
                            demand_m3_series=etc_ref,
                            registry_path=registry_path,
                            root_dir=root_dir,
                        )

                        harvest_records.append({
                            'harvest_date': harvest_date,
                            'field': field_name,
                            'crop': crop,
                            'planting': planting_code,
                            'condition': condition,
                            'yield_kg_per_ha': round(yield_kg_ha, 1),
                            'area_ha': area_ha,
                            'harvest_kg': round(yield_kg_ha * area_ha, 1),
                        })

    daily_df = _build_daily_harvest_df(harvest_records, sim_start, sim_end)
    harvests_df = pd.DataFrame(harvest_records)

    return daily_df, harvests_df


def save_harvest_yields(daily_df, output_dir, *, filename='daily_harvest_yields.csv',
                         decimals=1):
    """Save daily harvest yields DataFrame to CSV.

    Args:
        daily_df: DataFrame from compute_community_harvest (first element).
        output_dir: Directory to write. Created if needed.
        filename: Output file name.
        decimals: Decimal places for numeric columns.

    Returns:
        Path to the saved CSV file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    daily_df.round(decimals).to_csv(path, index=False)
    return path


# ---------------------------------------------------------------------------
# Entry point for standalone verification
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    from src.water_balance import compute_daily_water_balance

    root = Path(__file__).parent.parent
    wb_df = compute_daily_water_balance(
        farm_profiles_path=root / 'settings' / 'farm_profile_base.yaml',
        water_systems_path=root / 'settings' / 'water_systems_base.yaml',
        water_policy_path=root / 'settings' / 'water_policy_base.yaml',
        community_config_path=root / 'settings' / 'community_demands_base.yaml',
        registry_path=root / 'settings' / 'data_registry_base.yaml',
    )

    daily_df, harvests_df = compute_community_harvest(
        wb_df,
        farm_profiles_path=root / 'settings' / 'farm_profile_base.yaml',
        registry_path=root / 'settings' / 'data_registry_base.yaml',
    )

    out = save_harvest_yields(daily_df, output_dir=root / 'simulation')
    print(f"Saved {len(daily_df)} days to {out}")
    print(f"Harvest events: {len(harvests_df)}")
    print(f"Total harvest: {daily_df['total_harvest_kg'].sum():,.0f} kg")
    for crop, group in harvests_df.groupby('crop'):
        avg_yield = group['yield_kg_per_ha'].mean()
        total_kg = group['harvest_kg'].sum()
        print(f"  {crop}: {len(group)} harvests, avg {avg_yield:,.0f} kg/ha, total {total_kg:,.0f} kg")
