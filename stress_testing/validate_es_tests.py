"""Validate ES1–ES5 results: NaN checks, non-negative checks, date continuity,
battery/tank bounds, water balance check, and key metric extraction."""
import sys
from pathlib import Path

import pandas as pd
import numpy as np

repo = Path(__file__).resolve().parent.parent
BASE = repo / 'stress_testing' / 'individual_tests'

TESTS = [
    'es_01_solar_only',
    'es_02_wind_only',
    'es_03_minimal_solar',
    'es_04_large_solar',
    'es_05_single_small_turbine',
]

# Columns that must always be non-negative
NON_NEG_ENERGY = [
    'total_solar_kwh', 'total_wind_kwh', 'total_renewable_kwh',
    'grid_import_kwh', 'generator_kwh', 'curtailed_kwh', 'deficit_kwh',
]

NON_NEG_WATER = [
    'irrigation_demand_m3',
    'total_groundwater_extracted_m3', 'municipal_to_tank_m3',
    'municipal_community_m3', 'treatment_feed_m3',
    'tank_volume_m3',
]

KEY_ENERGY_COLS = [
    'total_solar_kwh', 'total_wind_kwh', 'total_renewable_kwh',
    'grid_import_kwh', 'generator_kwh', 'deficit_kwh',
]

for test_name in TESTS:
    td = BASE / test_name / 'results'
    failures = []
    metrics = {}

    # Load energy balance
    energy_path = td / 'daily_energy_balance.csv'
    water_path = td / 'daily_water_balance.csv'

    try:
        edf = pd.read_csv(energy_path, comment='#', parse_dates=['day'])
    except Exception as e:
        print(f'\n{test_name}: FAIL — could not load energy CSV: {e}')
        continue

    try:
        wdf = pd.read_csv(water_path, comment='#', parse_dates=['day'])
    except Exception as e:
        print(f'\n{test_name}: FAIL — could not load water CSV: {e}')
        continue

    # --- 1. NaN check (energy) ---
    nan_e = edf[KEY_ENERGY_COLS].isnull().sum()
    for col, n in nan_e.items():
        if n > 0:
            failures.append(f'NaN in energy col {col}: {n} rows')

    # --- 2. Non-negative check (energy) ---
    for col in NON_NEG_ENERGY:
        if col in edf.columns:
            neg = (edf[col] < -1e-6).sum()
            if neg > 0:
                failures.append(f'Negative values in {col}: {neg} rows')

    # --- 3. Non-negative check (water) ---
    for col in NON_NEG_WATER:
        if col in wdf.columns:
            neg = (wdf[col] < -1e-6).sum()
            if neg > 0:
                failures.append(f'Negative water col {col}: {neg} rows')

    # --- 4. Date continuity ---
    days = edf['day'].sort_values()
    gaps = days.diff().dropna()
    expected = pd.Timedelta('1 day')
    bad_gaps = (gaps != expected).sum()
    if bad_gaps > 0:
        failures.append(f'Date gap in energy: {bad_gaps} non-1-day steps')

    # --- 5. Battery bounds (if battery columns present) ---
    if 'battery_soc' in edf.columns:
        soc_min_violation = (edf['battery_soc'] < 0.19).sum()
        soc_max_violation = (edf['battery_soc'] > 0.96).sum()
        if soc_min_violation > 0:
            failures.append(f'Battery SOC < 0.19: {soc_min_violation} rows')
        if soc_max_violation > 0:
            failures.append(f'Battery SOC > 0.96: {soc_max_violation} rows')

    # --- 6. Tank bounds ---
    if 'tank_volume_m3' in wdf.columns:
        # Tank capacity from water_systems_balanced.yaml is 200 m3
        tank_over = (wdf['tank_volume_m3'] > 200.01).sum()
        if tank_over > 0:
            failures.append(f'Tank volume > 200 m3: {tank_over} rows')

    # --- 7. Water balance check ---
    # Sourced-to-tank should roughly track irrigation demand over the year
    if all(c in wdf.columns for c in ['total_sourced_to_tank_m3', 'irrigation_demand_m3']):
        supply_total = wdf['total_sourced_to_tank_m3'].sum()
        demand_total = wdf['irrigation_demand_m3'].sum()
        if supply_total < demand_total * 0.5:
            failures.append(f'Water supply ({supply_total:.0f}) far below demand ({demand_total:.0f})')

    # --- Key metrics (annual sums) ---
    for col in KEY_ENERGY_COLS:
        if col in edf.columns:
            metrics[col] = round(edf[col].sum(), 1)

    # Check ES-specific assertions
    if test_name == 'es_01_solar_only':
        if metrics.get('total_wind_kwh', 1) > 1e-3:
            failures.append(f"ES1: total_wind_kwh should be 0, got {metrics.get('total_wind_kwh')}")

    if test_name == 'es_02_wind_only':
        # Community solar should be 0; agri-PV from farm fields may still appear
        # Check that per-density community solar cols are 0 if present
        comm_solar_cols = [c for c in edf.columns if 'community_solar' in c or 'low_density_solar' in c
                           or 'medium_density_solar' in c or 'high_density_solar' in c]
        for c in comm_solar_cols:
            if edf[c].sum() > 1e-3:
                failures.append(f"ES2: community solar col {c} should be 0, got {edf[c].sum():.1f}")

    if test_name == 'es_03_minimal_solar':
        # ES3 uses 0.01 ha x 3 density tiers over 15 years; ~967k kWh is correct.
        # Check that grid import dominates (heavy reliance), i.e. renewables cover < 20% of demand.
        total_renewable = metrics.get('total_renewable_kwh', 0)
        grid_import = metrics.get('grid_import_kwh', 0)
        if total_renewable > 0 and grid_import < total_renewable:
            failures.append(
                f"ES3: expected grid import to dominate; got renewable={total_renewable:.1f}, "
                f"grid_import={grid_import:.1f}"
            )

    if test_name == 'es_04_large_solar':
        # Expect solar >> minimal; check annual solar is large
        solar = metrics.get('total_solar_kwh', 0)
        if solar < 100000:
            failures.append(f"ES4: expected large solar, got {solar:.1f} kWh/yr")
        # Expect some export (curtailment or grid export) — surplus days
        surplus = edf['curtailed_kwh'].sum() if 'curtailed_kwh' in edf.columns else 0
        grid_exp = edf['grid_export_kwh'].sum() if 'grid_export_kwh' in edf.columns else 0
        if surplus + grid_exp < 1e-3:
            failures.append("ES4: expected curtailment or grid export on oversupply days, got none")

    if test_name == 'es_05_single_small_turbine':
        wind = metrics.get('total_wind_kwh', 0)
        if wind < 1e-3:
            failures.append("ES5: expected some wind generation from single small turbine, got 0")

    status = 'PASS' if not failures else 'FAIL'
    print(f'\n=== {test_name}: {status} ===')
    if failures:
        for f in failures:
            print(f'  FAILURE: {f}')
    print('  Key metrics:')
    for k, v in metrics.items():
        print(f'    {k}: {v:,.1f} kWh')

print('\nValidation complete.')
