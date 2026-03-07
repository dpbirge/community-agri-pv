"""Run energy system stress tests ES1 through ES10 and print structured results."""

import sys
import shutil
import yaml
import json
import traceback
from pathlib import Path

import pandas as pd
import numpy as np

root = Path('/Users/dpbirge/GITHUB/community-agri-pv')
sys.path.insert(0, str(root))

from stress_testing.run_test import run

BASELINE_DIR = root / 'stress_testing' / 'baseline'
ENERGY_BASELINE = BASELINE_DIR / 'energy_system_balanced.yaml'
WATER_BASELINE = BASELINE_DIR / 'water_systems_balanced.yaml'
WATER_POLICY = root / 'settings' / 'water_policy_base.yaml'
ENERGY_POLICY = root / 'settings' / 'energy_policy_base.yaml'
REGISTRY = root / 'settings' / 'data_registry_base.yaml'
FARM_PROFILE = BASELINE_DIR / 'farm_profile.yaml'
COMMUNITY_DEMANDS = BASELINE_DIR / 'community_demands.yaml'


def load_baseline_energy():
    with open(ENERGY_BASELINE) as f:
        return yaml.safe_load(f)


def setup_test_dir(test_dir_name):
    test_dir = root / 'stress_testing' / test_dir_name
    test_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(WATER_BASELINE, test_dir / 'water_systems.yaml')
    shutil.copy(WATER_POLICY, test_dir / 'water_policy.yaml')
    shutil.copy(ENERGY_POLICY, test_dir / 'energy_policy.yaml')
    return test_dir


def save_energy_config(esys, test_dir):
    with open(test_dir / 'energy_system.yaml', 'w') as f:
        yaml.dump(esys, f, default_flow_style=False)


def run_test(test_dir):
    return run(
        farm_profiles_path=FARM_PROFILE,
        water_systems_path=test_dir / 'water_systems.yaml',
        water_policy_path=test_dir / 'water_policy.yaml',
        community_config_path=COMMUNITY_DEMANDS,
        energy_config_path=test_dir / 'energy_system.yaml',
        energy_policy_path=test_dir / 'energy_policy.yaml',
        registry_path=REGISTRY,
        output_dir=test_dir / 'results',
    )


def universal_checks(energy_df, water_df, has_battery=False):
    checks = {}

    # 1. No NaN in key columns
    key_cols = ['total_demand_kwh', 'total_renewable_kwh']
    nan_found = {c: int(energy_df[c].isna().sum()) for c in key_cols if c in energy_df.columns}
    checks['no_nan_key_cols'] = all(v == 0 for v in nan_found.values())

    # 2. Non-negative quantities
    kwh_cols = [c for c in energy_df.columns if '_kwh' in c or '_cost' in c]
    neg_found = {c: int((energy_df[c] < -1e-6).sum()) for c in kwh_cols if c in energy_df.columns}
    checks['non_negative_quantities'] = all(v == 0 for v in neg_found.values())
    if not checks['non_negative_quantities']:
        checks['non_negative_details'] = neg_found

    # 3. Energy conservation: renewable_consumed + grid_import + generator + battery_discharge + deficit = demand
    req_cols = ['renewable_consumed_kwh', 'total_demand_kwh']
    if all(c in energy_df.columns for c in req_cols):
        supply = energy_df['renewable_consumed_kwh'].copy()
        for col in ['generator_kwh', 'grid_import_kwh', 'battery_discharge_kwh']:
            if col in energy_df.columns:
                supply = supply + energy_df[col]
        if 'deficit_kwh' in energy_df.columns:
            supply = supply + energy_df['deficit_kwh']
        imbalance = (supply - energy_df['total_demand_kwh']).abs()
        max_imbalance = float(imbalance.max()) if len(imbalance) > 0 else 0.0
        checks['energy_conservation_max_imbalance_kwh'] = round(max_imbalance, 4)
        checks['energy_conservation_ok'] = max_imbalance < 1.0  # allow 1 kWh tolerance

    # 4. Date continuity
    if 'day' in energy_df.columns:
        days = pd.to_datetime(energy_df['day'])
        diffs = days.diff().dropna()
        checks['date_continuity'] = bool((diffs == pd.Timedelta('1D')).all())

    # 5. Battery bounds
    if has_battery and 'battery_soc_kwh' in energy_df.columns:
        soc = energy_df['battery_soc_kwh']
        checks['battery_soc_min_ok'] = bool((soc >= -1e-6).all())
        checks['battery_soc_max_ok'] = bool((soc <= energy_df['battery_capacity_kwh'].max() + 1e-6).all()) if 'battery_capacity_kwh' in energy_df.columns else 'N/A'

    return checks


def key_metrics(energy_df):
    metrics = {}
    col_map = {
        'total_energy_cost': 'total_energy_cost',
        'total_renewable_kwh': 'total_renewable_kwh',
        'total_solar_kwh': 'total_solar_kwh',
        'total_wind_kwh': 'total_wind_kwh',
        'grid_import_kwh': 'total_grid_import_kwh',
        'generator_kwh': 'total_generator_kwh',
        'deficit_kwh': 'total_deficit_kwh',
        'curtailed_kwh': 'total_curtailed_kwh',
    }
    for col, label in col_map.items():
        if col in energy_df.columns:
            metrics[label] = round(float(energy_df[col].sum()), 2)
        else:
            metrics[label] = 'N/A'
    return metrics


def print_result(test_id, test_name, status, uchecks, per_test_checks, metrics, notes=''):
    print(f"\n{'='*70}")
    print(f"TEST: {test_id} — {test_name}")
    print(f"STATUS: {status}")
    print("UNIVERSAL CHECKS:")
    for k, v in uchecks.items():
        icon = 'PASS' if v is True else ('FAIL' if v is False else f'INFO: {v}')
        print(f"  {k}: {icon}")
    print("PER-TEST CHECKS:")
    for k, v in per_test_checks.items():
        print(f"  {k}: {v}")
    print("KEY METRICS:")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    if notes:
        print(f"NOTES: {notes}")


# ─────────────────────────────────────────────
# ES1: solar_only
# ─────────────────────────────────────────────
def run_es1():
    test_id, test_name = 'ES1', 'solar_only'
    try:
        test_dir = setup_test_dir('es_01_solar_only')
        esys = load_baseline_energy()
        for k in esys.get('wind_turbines', {}):
            esys['wind_turbines'][k]['number'] = 0
        save_energy_config(esys, test_dir)
        water_df, energy_df = run_test(test_dir)

        uchecks = universal_checks(energy_df, water_df)
        metrics = key_metrics(energy_df)

        # Per-test checks
        per_checks = {}
        wind_zero = (energy_df['total_wind_kwh'] == 0).all() if 'total_wind_kwh' in energy_df.columns else 'N/A'
        per_checks['total_wind_kwh_zero_every_day'] = 'PASS' if wind_zero else f'FAIL — non-zero days: {int((energy_df["total_wind_kwh"] != 0).sum())}'

        # Seasonal pattern: compare summer vs winter solar
        if 'total_solar_kwh' in energy_df.columns:
            energy_df['_month'] = pd.to_datetime(energy_df['day']).dt.month
            summer_avg = energy_df[energy_df['_month'].isin([6,7,8])]['total_solar_kwh'].mean()
            winter_avg = energy_df[energy_df['_month'].isin([12,1,2])]['total_solar_kwh'].mean()
            per_checks['seasonal_pattern_summer_vs_winter_solar_kwh'] = f'summer={summer_avg:.1f} winter={winter_avg:.1f} ratio={summer_avg/winter_avg:.2f}'

        status = 'PASS' if all(v is True for v in uchecks.values() if isinstance(v, bool)) else 'WARNING'
        print_result(test_id, test_name, status, uchecks, per_checks, metrics)
    except Exception as e:
        print(f"\nTEST: {test_id} — {test_name}\nSTATUS: FAIL\nERROR: {e}\n{traceback.format_exc()}")


# ─────────────────────────────────────────────
# ES2: wind_only
# ─────────────────────────────────────────────
def run_es2():
    test_id, test_name = 'ES2', 'wind_only'
    try:
        test_dir = setup_test_dir('es_02_wind_only')
        esys = load_baseline_energy()
        for k in esys.get('community_solar', {}):
            esys['community_solar'][k]['area_ha'] = 0.0
        save_energy_config(esys, test_dir)
        water_df, energy_df = run_test(test_dir)

        uchecks = universal_checks(energy_df, water_df)
        metrics = key_metrics(energy_df)

        per_checks = {}
        # Community solar = 0, agri-PV may still appear
        if 'total_solar_kwh' in energy_df.columns:
            # Check if there are solar columns related to community_solar specifically
            community_solar_cols = [c for c in energy_df.columns if 'low_density' in c or 'medium_density' in c or 'high_density' in c]
            if community_solar_cols:
                comm_solar_sum = energy_df[community_solar_cols].sum().sum()
                per_checks['community_solar_cols_zero'] = f'PASS (sum={comm_solar_sum:.2f})' if comm_solar_sum < 1 else f'FAIL (sum={comm_solar_sum:.2f})'
            agri_pv_cols = [c for c in energy_df.columns if 'agri' in c.lower() or 'farm' in c.lower() or 'field' in c.lower()]
            per_checks['agri_pv_cols_found'] = agri_pv_cols if agri_pv_cols else 'none found'
            per_checks['total_solar_kwh_annual'] = round(float(energy_df['total_solar_kwh'].sum()), 2)
        total_wind_sum = energy_df['total_wind_kwh'].sum() if 'total_wind_kwh' in energy_df.columns else 0
        per_checks['wind_still_present'] = f'PASS ({total_wind_sum:.1f} kWh/yr)' if total_wind_sum > 0 else 'FAIL — no wind'

        status = 'PASS' if all(v is True for v in uchecks.values() if isinstance(v, bool)) else 'WARNING'
        print_result(test_id, test_name, status, uchecks, per_checks, metrics)
    except Exception as e:
        print(f"\nTEST: {test_id} — {test_name}\nSTATUS: FAIL\nERROR: {e}\n{traceback.format_exc()}")


# ─────────────────────────────────────────────
# ES3: minimal_solar
# ─────────────────────────────────────────────
def run_es3():
    test_id, test_name = 'ES3', 'minimal_solar'
    try:
        test_dir = setup_test_dir('es_03_minimal_solar')
        esys = load_baseline_energy()
        for k in esys.get('community_solar', {}):
            esys['community_solar'][k]['area_ha'] = 0.01
        save_energy_config(esys, test_dir)
        water_df, energy_df = run_test(test_dir)

        uchecks = universal_checks(energy_df, water_df)
        metrics = key_metrics(energy_df)

        per_checks = {}
        if 'total_solar_kwh' in energy_df.columns and 'total_renewable_kwh' in energy_df.columns:
            solar_fraction = energy_df['total_solar_kwh'].sum() / max(energy_df['total_renewable_kwh'].sum(), 1)
            per_checks['solar_fraction_of_renewable'] = f'{solar_fraction:.3f}'
        if 'grid_import_kwh' in energy_df.columns and 'generator_kwh' in energy_df.columns:
            grid_gen_sum = energy_df['grid_import_kwh'].sum() + energy_df['generator_kwh'].sum()
            per_checks['heavy_grid_generator_reliance_kwh'] = round(float(grid_gen_sum), 2)
        if 'total_demand_kwh' in energy_df.columns:
            per_checks['total_demand_kwh'] = round(float(energy_df['total_demand_kwh'].sum()), 2)

        status = 'PASS' if all(v is True for v in uchecks.values() if isinstance(v, bool)) else 'WARNING'
        print_result(test_id, test_name, status, uchecks, per_checks, metrics)
    except Exception as e:
        print(f"\nTEST: {test_id} — {test_name}\nSTATUS: FAIL\nERROR: {e}\n{traceback.format_exc()}")


# ─────────────────────────────────────────────
# ES4: large_solar
# ─────────────────────────────────────────────
def run_es4():
    test_id, test_name = 'ES4', 'large_solar'
    try:
        test_dir = setup_test_dir('es_04_large_solar')
        esys = load_baseline_energy()
        for k in esys.get('community_solar', {}):
            esys['community_solar'][k]['area_ha'] = 5.0
        save_energy_config(esys, test_dir)
        water_df, energy_df = run_test(test_dir)

        uchecks = universal_checks(energy_df, water_df)
        metrics = key_metrics(energy_df)

        per_checks = {}
        if 'curtailed_kwh' in energy_df.columns:
            curtailed_sum = energy_df['curtailed_kwh'].sum()
            per_checks['curtailed_kwh_total'] = round(float(curtailed_sum), 2)
            per_checks['curtailment_occurs'] = 'PASS' if curtailed_sum > 0 else 'NOTE — no curtailment detected'
        if 'total_solar_kwh' in energy_df.columns and 'total_demand_kwh' in energy_df.columns:
            solar_to_demand = energy_df['total_solar_kwh'].sum() / max(energy_df['total_demand_kwh'].sum(), 1)
            per_checks['solar_to_demand_ratio'] = round(float(solar_to_demand), 3)

        status = 'PASS' if all(v is True for v in uchecks.values() if isinstance(v, bool)) else 'WARNING'
        print_result(test_id, test_name, status, uchecks, per_checks, metrics)
    except Exception as e:
        print(f"\nTEST: {test_id} — {test_name}\nSTATUS: FAIL\nERROR: {e}\n{traceback.format_exc()}")


# ─────────────────────────────────────────────
# ES5: single_small_turbine
# ─────────────────────────────────────────────
def run_es5():
    test_id, test_name = 'ES5', 'single_small_turbine'
    try:
        test_dir = setup_test_dir('es_05_single_small_turbine')
        esys = load_baseline_energy()
        esys['wind_turbines']['small_turbine']['number'] = 1
        esys['wind_turbines']['medium_turbine']['number'] = 0
        esys['wind_turbines']['large_turbine']['number'] = 0
        save_energy_config(esys, test_dir)
        water_df, energy_df = run_test(test_dir)

        uchecks = universal_checks(energy_df, water_df)
        metrics = key_metrics(energy_df)

        per_checks = {}
        if 'total_wind_kwh' in energy_df.columns:
            per_checks['total_wind_kwh_annual'] = round(float(energy_df['total_wind_kwh'].sum()), 2)
            per_checks['wind_nonzero'] = 'PASS' if energy_df['total_wind_kwh'].sum() > 0 else 'FAIL'
        if 'total_solar_kwh' in energy_df.columns and 'total_wind_kwh' in energy_df.columns:
            per_checks['solar_vs_wind_ratio'] = round(float(energy_df['total_solar_kwh'].sum() / max(energy_df['total_wind_kwh'].sum(), 1)), 2)

        status = 'PASS' if all(v is True for v in uchecks.values() if isinstance(v, bool)) else 'WARNING'
        print_result(test_id, test_name, status, uchecks, per_checks, metrics)
    except Exception as e:
        print(f"\nTEST: {test_id} — {test_name}\nSTATUS: FAIL\nERROR: {e}\n{traceback.format_exc()}")


# ─────────────────────────────────────────────
# ES6: many_large_turbines
# ─────────────────────────────────────────────
def run_es6():
    test_id, test_name = 'ES6', 'many_large_turbines'
    try:
        test_dir = setup_test_dir('es_06_many_large_turbines')
        esys = load_baseline_energy()
        esys['wind_turbines']['large_turbine']['number'] = 20
        esys['wind_turbines']['small_turbine']['number'] = 0
        esys['wind_turbines']['medium_turbine']['number'] = 0
        save_energy_config(esys, test_dir)
        water_df, energy_df = run_test(test_dir)

        uchecks = universal_checks(energy_df, water_df)
        metrics = key_metrics(energy_df)

        per_checks = {}
        if 'total_wind_kwh' in energy_df.columns and 'total_solar_kwh' in energy_df.columns:
            wind_sum = energy_df['total_wind_kwh'].sum()
            solar_sum = energy_df['total_solar_kwh'].sum()
            per_checks['wind_dominant'] = 'PASS' if wind_sum > solar_sum else f'NOTE — wind={wind_sum:.0f} solar={solar_sum:.0f}'
            per_checks['wind_annual_kwh'] = round(float(wind_sum), 2)
        # Check seasonality of wind vs solar (CV = coeff of variation)
        if 'total_wind_kwh' in energy_df.columns:
            wind_cv = energy_df['total_wind_kwh'].std() / max(energy_df['total_wind_kwh'].mean(), 1)
            per_checks['wind_cv_seasonality'] = round(float(wind_cv), 3)
        if 'total_solar_kwh' in energy_df.columns:
            solar_cv = energy_df['total_solar_kwh'].std() / max(energy_df['total_solar_kwh'].mean(), 1)
            per_checks['solar_cv_seasonality'] = round(float(solar_cv), 3)

        status = 'PASS' if all(v is True for v in uchecks.values() if isinstance(v, bool)) else 'WARNING'
        print_result(test_id, test_name, status, uchecks, per_checks, metrics)
    except Exception as e:
        print(f"\nTEST: {test_id} — {test_name}\nSTATUS: FAIL\nERROR: {e}\n{traceback.format_exc()}")


# ─────────────────────────────────────────────
# ES7: tiny_battery
# ─────────────────────────────────────────────
def run_es7():
    test_id, test_name = 'ES7', 'tiny_battery'
    try:
        test_dir = setup_test_dir('es_07_tiny_battery')
        esys = load_baseline_energy()
        esys['battery']['has_battery'] = True
        esys['battery']['capacity_kwh'] = 10
        save_energy_config(esys, test_dir)
        water_df, energy_df = run_test(test_dir)

        uchecks = universal_checks(energy_df, water_df, has_battery=True)
        metrics = key_metrics(energy_df)

        per_checks = {}
        if 'battery_soc_kwh' in energy_df.columns:
            soc_max_hit = (energy_df['battery_soc_kwh'] >= 10 * 0.95).sum()
            per_checks['battery_saturates_frequently'] = f'PASS — {soc_max_hit} days near full' if soc_max_hit > 0 else 'NOTE — never saturated'
            per_checks['battery_soc_max_kwh'] = round(float(energy_df['battery_soc_kwh'].max()), 2)
            per_checks['battery_soc_min_kwh'] = round(float(energy_df['battery_soc_kwh'].min()), 2)
        if 'curtailed_kwh' in energy_df.columns:
            per_checks['curtailed_kwh_total'] = round(float(energy_df['curtailed_kwh'].sum()), 2)

        status = 'PASS' if all(v is True for v in uchecks.values() if isinstance(v, bool)) else 'WARNING'
        print_result(test_id, test_name, status, uchecks, per_checks, metrics)
    except Exception as e:
        print(f"\nTEST: {test_id} — {test_name}\nSTATUS: FAIL\nERROR: {e}\n{traceback.format_exc()}")


# ─────────────────────────────────────────────
# ES8: huge_battery
# ─────────────────────────────────────────────
def run_es8():
    test_id, test_name = 'ES8', 'huge_battery'
    try:
        test_dir = setup_test_dir('es_08_huge_battery')
        esys = load_baseline_energy()
        esys['battery']['has_battery'] = True
        esys['battery']['capacity_kwh'] = 2000
        save_energy_config(esys, test_dir)
        water_df, energy_df = run_test(test_dir)

        uchecks = universal_checks(energy_df, water_df, has_battery=True)
        metrics = key_metrics(energy_df)

        per_checks = {}
        if 'curtailed_kwh' in energy_df.columns:
            per_checks['curtailed_kwh_total'] = round(float(energy_df['curtailed_kwh'].sum()), 2)
        if 'battery_soc_kwh' in energy_df.columns:
            per_checks['battery_soc_max_kwh'] = round(float(energy_df['battery_soc_kwh'].max()), 2)
            per_checks['battery_never_saturated'] = 'PASS' if energy_df['battery_soc_kwh'].max() < 2000 else 'NOTE — huge battery still filled'
        # Self-consumption ratio
        if 'total_renewable_kwh' in energy_df.columns and 'curtailed_kwh' in energy_df.columns:
            renewable = energy_df['total_renewable_kwh'].sum()
            curtailed = energy_df['curtailed_kwh'].sum()
            self_con = 1 - curtailed / max(renewable, 1)
            per_checks['self_consumption_ratio'] = round(float(self_con), 4)

        status = 'PASS' if all(v is True for v in uchecks.values() if isinstance(v, bool)) else 'WARNING'
        print_result(test_id, test_name, status, uchecks, per_checks, metrics)
    except Exception as e:
        print(f"\nTEST: {test_id} — {test_name}\nSTATUS: FAIL\nERROR: {e}\n{traceback.format_exc()}")


# ─────────────────────────────────────────────
# ES9: large_generator
# ─────────────────────────────────────────────
def run_es9():
    test_id, test_name = 'ES9', 'large_generator'
    try:
        test_dir = setup_test_dir('es_09_large_generator')
        esys = load_baseline_energy()
        esys['generator']['rated_capacity_kw'] = 500
        save_energy_config(esys, test_dir)
        water_df, energy_df = run_test(test_dir)

        uchecks = universal_checks(energy_df, water_df)
        metrics = key_metrics(energy_df)

        per_checks = {}
        if 'generator_kwh' in energy_df.columns:
            per_checks['generator_kwh_annual'] = round(float(energy_df['generator_kwh'].sum()), 2)
        if 'deficit_kwh' in energy_df.columns:
            per_checks['deficit_kwh_total'] = round(float(energy_df['deficit_kwh'].sum()), 2)
            per_checks['deficit_zero'] = 'PASS' if energy_df['deficit_kwh'].sum() < 1 else 'NOTE — deficit present'
        # Fuel cost dominance: check if generator cost is large fraction of total
        gen_cost_cols = [c for c in energy_df.columns if 'generator' in c and 'cost' in c]
        if gen_cost_cols:
            per_checks['generator_cost_col'] = gen_cost_cols
            for gc in gen_cost_cols:
                per_checks[f'{gc}_annual'] = round(float(energy_df[gc].sum()), 2)

        status = 'PASS' if all(v is True for v in uchecks.values() if isinstance(v, bool)) else 'WARNING'
        print_result(test_id, test_name, status, uchecks, per_checks, metrics)
    except Exception as e:
        print(f"\nTEST: {test_id} — {test_name}\nSTATUS: FAIL\nERROR: {e}\n{traceback.format_exc()}")


# ─────────────────────────────────────────────
# ES10: no_renewables
# ─────────────────────────────────────────────
def run_es10():
    test_id, test_name = 'ES10', 'no_renewables'
    try:
        test_dir = setup_test_dir('es_10_no_renewables')
        esys = load_baseline_energy()
        for k in esys.get('community_solar', {}):
            esys['community_solar'][k]['area_ha'] = 0.0
        for k in esys.get('wind_turbines', {}):
            esys['wind_turbines'][k]['number'] = 0
        save_energy_config(esys, test_dir)
        water_df, energy_df = run_test(test_dir)

        uchecks = universal_checks(energy_df, water_df)
        metrics = key_metrics(energy_df)

        per_checks = {}
        # total_renewable_kwh - agri-PV from farm may still appear
        if 'total_renewable_kwh' in energy_df.columns:
            renewable_sum = energy_df['total_renewable_kwh'].sum()
            per_checks['total_renewable_kwh_annual'] = round(float(renewable_sum), 2)
            # Community solar and wind should be 0; agri-PV may remain
        if 'total_wind_kwh' in energy_df.columns:
            per_checks['wind_zero'] = 'PASS' if energy_df['total_wind_kwh'].sum() < 1 else f'FAIL ({energy_df["total_wind_kwh"].sum():.1f})'
        # Check that grid + generator covers demand
        if 'grid_import_kwh' in energy_df.columns and 'generator_kwh' in energy_df.columns and 'total_demand_kwh' in energy_df.columns:
            grid_gen = energy_df['grid_import_kwh'].sum() + energy_df['generator_kwh'].sum()
            demand = energy_df['total_demand_kwh'].sum()
            # For no_renewables, renewable supply may still include agri-PV
            per_checks['grid_generator_sum_kwh'] = round(float(grid_gen), 2)
            per_checks['total_demand_kwh'] = round(float(demand), 2)

        status = 'PASS' if all(v is True for v in uchecks.values() if isinstance(v, bool)) else 'WARNING'
        print_result(test_id, test_name, status, uchecks, per_checks, metrics)
    except Exception as e:
        print(f"\nTEST: {test_id} — {test_name}\nSTATUS: FAIL\nERROR: {e}\n{traceback.format_exc()}")


if __name__ == '__main__':
    print("Running ES1-ES10 energy system stress tests...")
    run_es1()
    run_es2()
    run_es3()
    run_es4()
    run_es5()
    run_es6()
    run_es7()
    run_es8()
    run_es9()
    run_es10()
    print("\nAll tests complete.")
