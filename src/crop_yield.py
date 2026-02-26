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
    from src.crop_yield import compute_harvest_yield

    yield_kg_ha = compute_harvest_yield(
        crop='tomato',
        planting='feb15',
        condition='openfield',
        weather_year=2010,
        delivered_m3_series=actual_series,
        demand_m3_series=demand_series,
        registry_path='settings/data_registry_base.yaml',
    )
"""

import yaml
import numpy as np
import pandas as pd
from pathlib import Path


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
    yrf_row = yrf_df[yrf_df['crop_name'] == crop].iloc[0]

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

    Filters to irrigation_policy='full_eto' and the given weather_year.
    Returns a pd.Series of temp_stress_coeff values indexed by date (DatetimeIndex).

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

    # 9. yield_kg_ha = potential_yield * f**(1/alpha) * avg_Kt
    yield_kg_ha = potential_yield * (f ** (1.0 / alpha)) * avg_kt

    # 10. Return float
    return float(yield_kg_ha)
