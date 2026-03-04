"""Run WS1-WS5 water system configuration stress tests and validate results."""
import sys
import traceback
from pathlib import Path

import pandas as pd
import numpy as np

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from stress_testing.run_test import run

BASELINE = _repo_root / 'stress_testing' / 'baseline'
TESTS_DIR = _repo_root / 'stress_testing' / 'individual_tests'
REGISTRY = _repo_root / 'settings' / 'data_registry_base.yaml'

TESTS = [
    'ws_01_single_well',
    'ws_02_high_tds_only',
    'ws_03_no_treatment',
    'ws_04_small_treatment',
    'ws_05_large_treatment',
]


def validate(water_df, energy_df):
    """Run validation checks on simulation outputs.

    Args:
        water_df: Daily water balance DataFrame.
        energy_df: Daily energy balance DataFrame.

    Returns:
        List of failure strings (empty if all pass).
    """
    failures = []

    # Check 1: no NaN in key water columns
    key_water_cols = [c for c in water_df.columns if any(
        k in c for k in ['demand', 'supply', 'cost', 'deficit', 'tank', 'treatment', 'municipal', 'groundwater']
    )]
    nan_cols = [c for c in key_water_cols if water_df[c].isna().any()]
    if nan_cols:
        failures.append(f"NaN in water columns: {nan_cols}")

    # Check 2: non-negative quantities
    non_neg_cols = [c for c in water_df.columns if any(
        k in c for k in ['_m3', '_kwh', '_cost', 'tank_level']
    )]
    for col in non_neg_cols:
        if (water_df[col] < -0.01).any():
            neg_count = (water_df[col] < -0.01).sum()
            failures.append(f"Negative values in {col}: {neg_count} rows")

    # Check 3: water balance check (skip row 0 — initial tank state)
    bal_col = next((c for c in water_df.columns if 'balance_check' in c), None)
    if bal_col and pd.api.types.is_numeric_dtype(water_df[bal_col]):
        check_rows = water_df.iloc[1:]
        bad = (check_rows[bal_col].abs() > 0.01).sum()
        if bad > 0:
            max_err = check_rows[bal_col].abs().max()
            failures.append(f"{bal_col} > 0.01 on {bad} rows (max={max_err:.4f})")

    # Check 4: date continuity
    if 'day' in water_df.columns:
        dates = pd.to_datetime(water_df['day'])
        diffs = dates.diff().iloc[1:]
        if not (diffs == pd.Timedelta('1D')).all():
            failures.append("Date continuity broken in water_df")

    # Check 5: tank bounds
    if 'tank_level_m3' in water_df.columns:
        # find tank capacity from water systems — use a loose check
        max_level = water_df['tank_level_m3'].max()
        if max_level > 10000:
            failures.append(f"tank_level_m3 suspiciously large: {max_level:.1f}")
        if (water_df['tank_level_m3'] < -0.01).any():
            failures.append("tank_level_m3 went negative")

    return failures


def extract_metrics(water_df):
    """Extract key summary metrics from water balance DataFrame.

    Args:
        water_df: Daily water balance DataFrame.

    Returns:
        Dict of metric name to value.
    """
    metrics = {}

    # total water cost
    cost_cols = [c for c in water_df.columns if 'cost' in c and '_m3' not in c]
    if cost_cols:
        metrics['total_water_cost'] = water_df[cost_cols].sum().sum()
    else:
        metrics['total_water_cost'] = None

    # total treatment
    treat_cols = [c for c in water_df.columns if 'treatment' in c and '_m3' in c and 'cost' not in c]
    if treat_cols:
        metrics['total_treatment_m3'] = water_df[treat_cols].sum().sum()
    else:
        metrics['total_treatment_m3'] = 0.0

    # total municipal
    muni_cols = [c for c in water_df.columns if 'municipal' in c and '_m3' in c and 'cost' not in c]
    if muni_cols:
        metrics['total_municipal_m3'] = water_df[muni_cols].sum().sum()
    else:
        metrics['total_municipal_m3'] = 0.0

    # total groundwater
    gw_cols = [c for c in water_df.columns if 'groundwater' in c and '_m3' in c and 'cost' not in c]
    if gw_cols:
        metrics['total_groundwater_m3'] = water_df[gw_cols].sum().sum()
    else:
        metrics['total_groundwater_m3'] = 0.0

    # deficit
    deficit_cols = [c for c in water_df.columns if 'deficit' in c and '_m3' in c]
    if deficit_cols:
        metrics['total_deficit_m3'] = water_df[deficit_cols].sum().sum()
        metrics['deficit_day_count'] = (water_df[deficit_cols].sum(axis=1) > 0.01).sum()
    else:
        metrics['total_deficit_m3'] = 0.0
        metrics['deficit_day_count'] = 0

    return metrics


results = {}

for test_name in TESTS:
    test_dir = TESTS_DIR / test_name
    print(f"\n{'='*60}")
    print(f"Running {test_name} ...")
    print('='*60)

    status = 'PASS'
    failures = []
    metrics = {}
    water_df = None
    energy_df = None

    try:
        water_df, energy_df = run(
            farm_profiles_path=test_dir / 'farm_profile.yaml',
            water_systems_path=test_dir / 'water_systems.yaml',
            water_policy_path=test_dir / 'water_policy.yaml',
            community_config_path=BASELINE / 'community_demands.yaml',
            energy_config_path=test_dir / 'energy_system.yaml',
            energy_policy_path=test_dir / 'energy_policy.yaml',
            registry_path=REGISTRY,
            output_dir=test_dir / 'results',
        )
        print(f"  Simulation completed. water_df shape={water_df.shape}")
        failures = validate(water_df, energy_df)
        metrics = extract_metrics(water_df)
        if failures:
            status = 'FAIL'
    except Exception as e:
        status = 'CRASH'
        failures = [f"CRASH: {e}"]
        traceback.print_exc()

    results[test_name] = {
        'status': status,
        'failures': failures,
        'metrics': metrics,
    }
    print(f"  Status: {status}")
    if failures:
        for f in failures:
            print(f"    FAIL: {f}")
    if metrics:
        for k, v in metrics.items():
            print(f"    {k}: {v:.2f}" if isinstance(v, float) else f"    {k}: {v}")


# Final summary
print("\n\n" + "="*60)
print("FINAL SUMMARY")
print("="*60)
for test_name, r in results.items():
    print(f"\n{test_name}: {r['status']}")
    if r['failures']:
        for f in r['failures']:
            print(f"  FAIL: {f}")
    for k, v in r['metrics'].items():
        print(f"  {k}: {v:.2f}" if isinstance(v, float) else f"  {k}: {v}")
