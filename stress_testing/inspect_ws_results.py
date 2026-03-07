"""Inspect WS test results in detail for key behavioral checks."""
import sys
from pathlib import Path

import pandas as pd

_repo_root = Path(__file__).resolve().parent.parent
TESTS_DIR = _repo_root / 'stress_testing' / 'individual_tests'
TESTS = [
    'ws_01_single_well',
    'ws_02_high_tds_only',
    'ws_03_no_treatment',
    'ws_04_small_treatment',
    'ws_05_large_treatment',
]


def load_water(test_name):
    path = TESTS_DIR / test_name / 'results' / 'daily_water_balance.csv'
    return pd.read_csv(path, comment='#')


for test_name in TESTS:
    df = load_water(test_name)
    print(f"\n{'='*60}")
    print(f"{test_name}")
    print(f"  Columns: {list(df.columns)}")

    # find tank TDS column
    tds_cols = [c for c in df.columns if 'tds' in c.lower()]
    if tds_cols:
        print(f"  TDS columns: {tds_cols}")
        for col in tds_cols:
            print(f"    {col}: min={df[col].min():.1f}, mean={df[col].mean():.1f}, max={df[col].max():.1f}")

    # find flush columns
    flush_cols = [c for c in df.columns if 'flush' in c.lower()]
    if flush_cols:
        print(f"  Flush columns: {flush_cols}")
        for col in flush_cols:
            if pd.api.types.is_numeric_dtype(df[col]):
                flush_days = (df[col] > 0.01).sum()
                print(f"    {col}: {flush_days} days with flush > 0")
            else:
                nonempty = df[col].notna() & (df[col] != '')
                print(f"    {col} (str): {nonempty.sum()} non-empty rows, examples: {df.loc[nonempty, col].value_counts().head(3).to_dict()}")

    # tank level
    tank_cols = [c for c in df.columns if 'tank_volume' in c]
    if tank_cols:
        for col in tank_cols:
            print(f"  {col}: min={df[col].min():.2f}, max={df[col].max():.2f}, mean={df[col].mean():.2f}")

    # treatment cols
    treat_cols = [c for c in df.columns if 'treatment' in c and '_m3' in c and 'cost' not in c]
    if treat_cols:
        for col in treat_cols:
            treat_days = (df[col] > 0.01).sum()
            print(f"  {col}: {treat_days} days active, total={df[col].sum():.1f} m3")
    else:
        print("  No treatment columns found (WS3 expected)")

    # municipal cols
    muni_cols = [c for c in df.columns if 'municipal' in c and '_m3' in c and 'cost' not in c]
    if muni_cols:
        for col in muni_cols:
            print(f"  {col}: total={df[col].sum():.1f} m3, days_active={(df[col]>0.01).sum()}")

    # deficit
    deficit_cols = [c for c in df.columns if 'deficit' in c and '_m3' in c]
    if deficit_cols:
        for col in deficit_cols:
            deficit_days = (df[col] > 0.01).sum()
            print(f"  {col}: {deficit_days} deficit days, total={df[col].sum():.2f} m3")

    # groundwater
    gw_cols = [c for c in df.columns if 'groundwater' in c and '_m3' in c and 'cost' not in c]
    if gw_cols:
        for col in gw_cols:
            print(f"  {col}: total={df[col].sum():.1f} m3, days_active={(df[col]>0.01).sum()}")

    # balance check
    bal_col = next((c for c in df.columns if 'balance_check' in c), None)
    if bal_col:
        check = df.iloc[1:][bal_col]
        if pd.api.types.is_numeric_dtype(check):
            print(f"  {bal_col}: max_abs={check.abs().max():.6f}, violations={(check.abs()>0.01).sum()}")
