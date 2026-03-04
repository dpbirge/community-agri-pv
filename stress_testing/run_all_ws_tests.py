"""Run all WS1-WS10 water system stress tests and collect structured results."""
import sys
import shutil
import yaml
import traceback
from pathlib import Path

import pandas as pd
import numpy as np

root = Path('/Users/dpbirge/GITHUB/community-agri-pv')
sys.path.insert(0, str(root))

from stress_testing.run_test import run

BASELINE_DIR = root / 'stress_testing' / 'baseline'
SETTINGS_DIR = root / 'settings'
BASELINE_WSYS = BASELINE_DIR / 'water_systems_balanced.yaml'
BASELINE_ESYS = BASELINE_DIR / 'energy_system_balanced.yaml'
WATER_POLICY = SETTINGS_DIR / 'water_policy_base.yaml'
ENERGY_POLICY = SETTINGS_DIR / 'energy_policy_base.yaml'
FARM_PROFILE = BASELINE_DIR / 'farm_profile.yaml'
COMMUNITY_CONFIG = BASELINE_DIR / 'community_demands.yaml'
REGISTRY = SETTINGS_DIR / 'data_registry_base.yaml'


def load_baseline_wsys():
    with open(BASELINE_WSYS) as f:
        return yaml.safe_load(f)


def setup_test_dir(test_dir_name):
    test_dir = root / 'stress_testing' / test_dir_name
    test_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(BASELINE_ESYS, test_dir / 'energy_system.yaml')
    shutil.copy(WATER_POLICY, test_dir / 'water_policy.yaml')
    shutil.copy(ENERGY_POLICY, test_dir / 'energy_policy.yaml')
    return test_dir


def write_wsys(wsys, test_dir):
    with open(test_dir / 'water_systems.yaml', 'w') as f:
        yaml.dump(wsys, f, default_flow_style=False)


def run_test(test_dir):
    return run(
        farm_profiles_path=FARM_PROFILE,
        water_systems_path=test_dir / 'water_systems.yaml',
        water_policy_path=test_dir / 'water_policy.yaml',
        community_config_path=COMMUNITY_CONFIG,
        energy_config_path=test_dir / 'energy_system.yaml',
        energy_policy_path=test_dir / 'energy_policy.yaml',
        registry_path=REGISTRY,
        output_dir=test_dir / 'results',
    )


def validate(water_df, test_id, has_tank=True):
    """Run universal validation checks. Returns dict of check results."""
    checks = {}

    # Check 1: No NaN in key columns
    key_cols = ['total_demand_m3', 'total_delivered_m3', 'deficit_m3']
    nan_check = all(
        col in water_df.columns and not water_df[col].isna().any()
        for col in key_cols
    )
    checks['no_nan_key_cols'] = nan_check

    # Check 2: Non-negative quantities
    m3_cols = [c for c in water_df.columns if c.endswith('_m3')]
    kwh_cols = [c for c in water_df.columns if c.endswith('_kwh')]
    cost_cols = [c for c in water_df.columns if c.endswith('_cost')]
    non_neg_cols = m3_cols + kwh_cols + cost_cols
    non_neg_ok = all(
        water_df[c].ge(0).all() for c in non_neg_cols if c in water_df.columns
    )
    checks['non_negative_quantities'] = non_neg_ok

    # Check 3: Water balance (skip row 0 which may be NaN)
    if 'balance_check' in water_df.columns:
        balance_ok = water_df['balance_check'].iloc[1:].abs().lt(0.01).all()
        checks['water_balance_check'] = balance_ok
    else:
        checks['water_balance_check'] = 'MISSING_COL'

    # Check 4: Date continuity
    if 'day' in water_df.columns:
        days = pd.to_datetime(water_df['day'])
        diffs = days.diff().dropna()
        date_ok = (diffs == pd.Timedelta('1D')).all()
        checks['date_continuity'] = bool(date_ok)
    else:
        checks['date_continuity'] = 'MISSING_COL'

    # Check 5: Tank bounds
    if has_tank and 'tank_volume_m3' in water_df.columns:
        # Try to get capacity from water systems yaml
        tank_min_ok = water_df['tank_volume_m3'].ge(-0.01).all()
        checks['tank_lower_bound'] = bool(tank_min_ok)
    else:
        checks['tank_lower_bound'] = 'N/A'

    return checks


def key_metrics(water_df):
    metrics = {}
    for col in ['total_water_cost', 'treatment_m3', 'municipal_m3',
                'groundwater_m3', 'deficit_m3']:
        if col in water_df.columns:
            metrics[f'total_{col}'] = round(water_df[col].sum(), 2)
        else:
            metrics[f'total_{col}'] = 'N/A'
    if 'deficit_m3' in water_df.columns:
        metrics['deficit_days_count'] = int((water_df['deficit_m3'] > 0.001).sum())
    else:
        metrics['deficit_days_count'] = 'N/A'
    return metrics


results = {}


# ─── WS1: single_well ────────────────────────────────────────────────────────
print("\n=== WS1: single_well ===")
test_id = 'WS1'
try:
    test_dir = setup_test_dir('ws_01_single_well')
    wsys = load_baseline_wsys()
    wsys['systems'][0]['wells'] = [wsys['systems'][0]['wells'][0]]  # keep only well_1
    write_wsys(wsys, test_dir)
    water_df, energy_df = run_test(test_dir)
    checks = validate(water_df, test_id)
    metrics = key_metrics(water_df)
    # Per-test checks
    per_test = {}
    if 'groundwater_tds_ppm' in water_df.columns:
        per_test['avg_gw_tds'] = round(water_df['groundwater_tds_ppm'].mean(), 1)
    if 'treatment_m3' in water_df.columns:
        per_test['total_treatment_m3'] = round(water_df['treatment_m3'].sum(), 2)
    results[test_id] = {'status': 'PASS', 'checks': checks, 'metrics': metrics,
                        'per_test': per_test, 'notes': '', 'df': water_df}
    print(f"WS1 PASS — metrics: {metrics}")
except Exception as e:
    results[test_id] = {'status': 'FAIL', 'checks': {}, 'metrics': {}, 'per_test': {},
                        'notes': traceback.format_exc()}
    print(f"WS1 FAIL: {e}")


# ─── WS2: high_tds_only ──────────────────────────────────────────────────────
print("\n=== WS2: high_tds_only ===")
test_id = 'WS2'
try:
    test_dir = setup_test_dir('ws_02_high_tds_only')
    wsys = load_baseline_wsys()
    wsys['systems'][0]['wells'] = wsys['systems'][0]['wells'][1:]  # remove well_1, keep 2+3
    write_wsys(wsys, test_dir)
    water_df, energy_df = run_test(test_dir)
    checks = validate(water_df, test_id)
    metrics = key_metrics(water_df)
    per_test = {}
    if 'treatment_m3' in water_df.columns and 'groundwater_m3' in water_df.columns:
        gw_total = water_df['groundwater_m3'].sum()
        treat_total = water_df['treatment_m3'].sum()
        per_test['treatment_as_pct_of_gw'] = round(
            100 * treat_total / gw_total if gw_total > 0 else 0, 1)
    results[test_id] = {'status': 'PASS', 'checks': checks, 'metrics': metrics,
                        'per_test': per_test, 'notes': '', 'df': water_df}
    print(f"WS2 PASS — metrics: {metrics}")
except Exception as e:
    results[test_id] = {'status': 'FAIL', 'checks': {}, 'metrics': {}, 'per_test': {},
                        'notes': traceback.format_exc()}
    print(f"WS2 FAIL: {e}")


# ─── WS3: no_treatment ───────────────────────────────────────────────────────
print("\n=== WS3: no_treatment ===")
test_id = 'WS3'
try:
    test_dir = setup_test_dir('ws_03_no_treatment')
    wsys = load_baseline_wsys()
    wsys['systems'][0].pop('treatment', None)
    write_wsys(wsys, test_dir)
    water_df, energy_df = run_test(test_dir)
    checks = validate(water_df, test_id)
    metrics = key_metrics(water_df)
    per_test = {}
    if 'flush_m3' in water_df.columns:
        per_test['total_flush_m3'] = round(water_df['flush_m3'].sum(), 2)
    if 'municipal_m3' in water_df.columns:
        per_test['total_municipal_m3'] = round(water_df['municipal_m3'].sum(), 2)
    results[test_id] = {'status': 'PASS', 'checks': checks, 'metrics': metrics,
                        'per_test': per_test, 'notes': '', 'df': water_df}
    print(f"WS3 PASS — metrics: {metrics}")
except Exception as e:
    results[test_id] = {'status': 'FAIL', 'checks': {}, 'metrics': {}, 'per_test': {},
                        'notes': traceback.format_exc()}
    print(f"WS3 FAIL: {e}")


# ─── WS4: small_treatment ────────────────────────────────────────────────────
print("\n=== WS4: small_treatment ===")
test_id = 'WS4'
try:
    test_dir = setup_test_dir('ws_04_small_treatment')
    wsys = load_baseline_wsys()
    wsys['systems'][0]['treatment']['throughput_m3_hr'] = 5
    write_wsys(wsys, test_dir)
    water_df, energy_df = run_test(test_dir)
    checks = validate(water_df, test_id)
    metrics = key_metrics(water_df)
    per_test = {}
    if 'deficit_m3' in water_df.columns:
        per_test['peak_deficit_m3'] = round(water_df['deficit_m3'].max(), 2)
    if 'municipal_m3' in water_df.columns:
        per_test['total_municipal_m3'] = round(water_df['municipal_m3'].sum(), 2)
    results[test_id] = {'status': 'PASS', 'checks': checks, 'metrics': metrics,
                        'per_test': per_test, 'notes': '', 'df': water_df}
    print(f"WS4 PASS — metrics: {metrics}")
except Exception as e:
    results[test_id] = {'status': 'FAIL', 'checks': {}, 'metrics': {}, 'per_test': {},
                        'notes': traceback.format_exc()}
    print(f"WS4 FAIL: {e}")


# ─── WS5: large_treatment ────────────────────────────────────────────────────
print("\n=== WS5: large_treatment ===")
test_id = 'WS5'
try:
    test_dir = setup_test_dir('ws_05_large_treatment')
    wsys = load_baseline_wsys()
    wsys['systems'][0]['treatment']['throughput_m3_hr'] = 200
    write_wsys(wsys, test_dir)
    water_df, energy_df = run_test(test_dir)
    checks = validate(water_df, test_id)
    metrics = key_metrics(water_df)
    per_test = {}
    if 'treatment_m3' in water_df.columns:
        per_test['peak_treatment_m3'] = round(water_df['treatment_m3'].max(), 2)
    results[test_id] = {'status': 'PASS', 'checks': checks, 'metrics': metrics,
                        'per_test': per_test, 'notes': '', 'df': water_df}
    print(f"WS5 PASS — metrics: {metrics}")
except Exception as e:
    results[test_id] = {'status': 'FAIL', 'checks': {}, 'metrics': {}, 'per_test': {},
                        'notes': traceback.format_exc()}
    print(f"WS5 FAIL: {e}")


# ─── WS6: no_tank ────────────────────────────────────────────────────────────
print("\n=== WS6: no_tank ===")
test_id = 'WS6'
try:
    test_dir = setup_test_dir('ws_06_no_tank')
    wsys = load_baseline_wsys()
    wsys['systems'][0].pop('storage', None)
    write_wsys(wsys, test_dir)
    water_df, energy_df = run_test(test_dir)
    checks = validate(water_df, test_id, has_tank=False)
    metrics = key_metrics(water_df)
    per_test = {}
    if 'tank_volume_m3' in water_df.columns:
        per_test['tank_col_present'] = True
        per_test['tank_all_zero'] = bool(water_df['tank_volume_m3'].eq(0).all())
    else:
        per_test['tank_col_present'] = False
    results[test_id] = {'status': 'PASS', 'checks': checks, 'metrics': metrics,
                        'per_test': per_test, 'notes': '', 'df': water_df}
    print(f"WS6 PASS — metrics: {metrics}")
except Exception as e:
    results[test_id] = {'status': 'FAIL', 'checks': {}, 'metrics': {}, 'per_test': {},
                        'notes': traceback.format_exc()}
    print(f"WS6 FAIL: {e}")


# ─── WS7: tiny_tank ──────────────────────────────────────────────────────────
print("\n=== WS7: tiny_tank ===")
test_id = 'WS7'
try:
    test_dir = setup_test_dir('ws_07_tiny_tank')
    wsys = load_baseline_wsys()
    wsys['systems'][0]['storage']['capacity_m3'] = 50
    wsys['systems'][0]['storage']['initial_level_m3'] = 25
    write_wsys(wsys, test_dir)
    water_df, energy_df = run_test(test_dir)
    checks = validate(water_df, test_id)
    metrics = key_metrics(water_df)
    per_test = {}
    if 'tank_volume_m3' in water_df.columns:
        per_test['tank_max_volume'] = round(water_df['tank_volume_m3'].max(), 2)
        per_test['tank_min_volume'] = round(water_df['tank_volume_m3'].min(), 2)
        per_test['tank_fill_events'] = int(
            (water_df['tank_volume_m3'].diff().fillna(0) > 0).sum())
    results[test_id] = {'status': 'PASS', 'checks': checks, 'metrics': metrics,
                        'per_test': per_test, 'notes': '', 'df': water_df}
    print(f"WS7 PASS — metrics: {metrics}")
except Exception as e:
    results[test_id] = {'status': 'FAIL', 'checks': {}, 'metrics': {}, 'per_test': {},
                        'notes': traceback.format_exc()}
    print(f"WS7 FAIL: {e}")


# ─── WS8: huge_tank ──────────────────────────────────────────────────────────
print("\n=== WS8: huge_tank ===")
test_id = 'WS8'
try:
    test_dir = setup_test_dir('ws_08_huge_tank')
    wsys = load_baseline_wsys()
    wsys['systems'][0]['storage']['capacity_m3'] = 5000
    wsys['systems'][0]['storage']['initial_level_m3'] = 2500
    write_wsys(wsys, test_dir)
    water_df, energy_df = run_test(test_dir)
    checks = validate(water_df, test_id)
    metrics = key_metrics(water_df)
    per_test = {}
    if 'deficit_m3' in water_df.columns:
        per_test['deficit_days'] = int((water_df['deficit_m3'] > 0.001).sum())
    results[test_id] = {'status': 'PASS', 'checks': checks, 'metrics': metrics,
                        'per_test': per_test, 'notes': '', 'df': water_df}
    print(f"WS8 PASS — metrics: {metrics}")
except Exception as e:
    results[test_id] = {'status': 'FAIL', 'checks': {}, 'metrics': {}, 'per_test': {},
                        'notes': traceback.format_exc()}
    print(f"WS8 FAIL: {e}")


# ─── WS9: expensive_municipal ────────────────────────────────────────────────
print("\n=== WS9: expensive_municipal ===")
test_id = 'WS9'
try:
    test_dir = setup_test_dir('ws_09_expensive_municipal')
    wsys = load_baseline_wsys()
    wsys['systems'][0]['municipal_source']['cost_per_m3'] = 5.00
    write_wsys(wsys, test_dir)
    water_df, energy_df = run_test(test_dir)
    checks = validate(water_df, test_id)
    metrics = key_metrics(water_df)
    per_test = {}
    if 'municipal_m3' in water_df.columns:
        per_test['total_municipal_m3'] = round(water_df['municipal_m3'].sum(), 2)
    if 'total_water_cost' in water_df.columns:
        per_test['total_water_cost'] = round(water_df['total_water_cost'].sum(), 2)
    results[test_id] = {'status': 'PASS', 'checks': checks, 'metrics': metrics,
                        'per_test': per_test, 'notes': '', 'df': water_df}
    print(f"WS9 PASS — metrics: {metrics}")
except Exception as e:
    results[test_id] = {'status': 'FAIL', 'checks': {}, 'metrics': {}, 'per_test': {},
                        'notes': traceback.format_exc()}
    print(f"WS9 FAIL: {e}")


# ─── WS10: low_tds_municipal ─────────────────────────────────────────────────
print("\n=== WS10: low_tds_municipal ===")
test_id = 'WS10'
try:
    test_dir = setup_test_dir('ws_10_low_tds_municipal')
    wsys = load_baseline_wsys()
    wsys['systems'][0]['municipal_source']['tds_ppm'] = 50
    write_wsys(wsys, test_dir)
    water_df, energy_df = run_test(test_dir)
    checks = validate(water_df, test_id)
    metrics = key_metrics(water_df)
    per_test = {}
    if 'treatment_m3' in water_df.columns:
        per_test['total_treatment_m3'] = round(water_df['treatment_m3'].sum(), 2)
    if 'municipal_m3' in water_df.columns:
        per_test['total_municipal_m3'] = round(water_df['municipal_m3'].sum(), 2)
    results[test_id] = {'status': 'PASS', 'checks': checks, 'metrics': metrics,
                        'per_test': per_test, 'notes': '', 'df': water_df}
    print(f"WS10 PASS — metrics: {metrics}")
except Exception as e:
    results[test_id] = {'status': 'FAIL', 'checks': {}, 'metrics': {}, 'per_test': {},
                        'notes': traceback.format_exc()}
    print(f"WS10 FAIL: {e}")


# ─── PRINT FULL REPORT ───────────────────────────────────────────────────────
print("\n\n" + "="*80)
print("STRESS TEST REPORT — WS1 through WS10")
print("="*80)

test_names = {
    'WS1': 'single_well',
    'WS2': 'high_tds_only',
    'WS3': 'no_treatment',
    'WS4': 'small_treatment',
    'WS5': 'large_treatment',
    'WS6': 'no_tank',
    'WS7': 'tiny_tank',
    'WS8': 'huge_tank',
    'WS9': 'expensive_municipal',
    'WS10': 'low_tds_municipal',
}

for tid, tname in test_names.items():
    r = results.get(tid, {})
    status = r.get('status', 'NOT RUN')
    print(f"\nTEST: {tid} — {tname}")
    print(f"STATUS: {status}")

    if status == 'FAIL':
        print("NOTES (traceback):")
        print(r.get('notes', ''))
        continue

    print("UNIVERSAL CHECKS:")
    for k, v in r.get('checks', {}).items():
        mark = 'PASS' if v is True else ('N/A' if v == 'N/A' else 'FAIL')
        print(f"  {k}: {mark} ({v})")

    print("PER-TEST CHECKS:")
    for k, v in r.get('per_test', {}).items():
        print(f"  {k}: {v}")

    print("KEY METRICS:")
    for k, v in r.get('metrics', {}).items():
        print(f"  {k}: {v}")

    # Additional column listing for debugging
    df = r.get('df')
    if df is not None:
        print(f"  [columns: {list(df.columns)}]")
