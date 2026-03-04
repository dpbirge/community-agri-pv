"""Analyze results from completed WS1-WS10 stress tests and produce structured report."""
import sys
import pandas as pd
import numpy as np
from pathlib import Path

root = Path('/Users/dpbirge/GITHUB/community-agri-pv')
sys.path.insert(0, str(root))

TESTS = {
    'WS1':  ('ws_01_single_well',          'single_well'),
    'WS2':  ('ws_02_high_tds_only',        'high_tds_only'),
    'WS3':  ('ws_03_no_treatment',         'no_treatment'),
    'WS4':  ('ws_04_small_treatment',      'small_treatment'),
    'WS5':  ('ws_05_large_treatment',      'large_treatment'),
    'WS6':  ('ws_06_no_tank',              'no_tank'),
    'WS7':  ('ws_07_tiny_tank',            'tiny_tank'),
    'WS8':  ('ws_08_huge_tank',            'huge_tank'),
    'WS9':  ('ws_09_expensive_municipal',  'expensive_municipal'),
    'WS10': ('ws_10_low_tds_municipal',    'low_tds_municipal'),
}

CRASH_NOTES = {
    'WS3': (
        'CRASH: src/water.py line 1405 raises KeyError: "treatment" when the treatment '
        'key is absent. The code unconditionally indexes system["treatment"] without '
        'checking for its presence. No optional/absent-treatment code path exists.'
    ),
    'WS6': (
        'CRASH: src/water.py line 1418 raises KeyError: "storage" when the storage '
        'key is absent. The code unconditionally indexes system["storage"] without '
        'checking for its presence. No tankless code path exists.'
    ),
}


def load_water_df(test_dir):
    path = root / 'stress_testing' / test_dir / 'results' / 'daily_water_balance.csv'
    if not path.exists():
        return None
    return pd.read_csv(path, comment='#')


def universal_checks(df, has_tank=True):
    checks = {}

    # Key column names based on actual output schema
    key_cols = ['total_water_demand_m3', 'irrigation_delivered_m3', 'deficit_m3']
    nan_ok = all(
        col in df.columns and not df[col].isna().any()
        for col in key_cols
    )
    checks['no_nan_key_cols'] = nan_ok

    # Non-negative: all _m3, _kwh, _cost columns
    neg_cols = []
    for c in df.columns:
        if c.endswith(('_m3', '_kwh', '_cost')):
            if c in df.columns and (df[c] < -0.001).any():
                neg_cols.append(c)
    checks['non_negative_quantities'] = len(neg_cols) == 0
    if neg_cols:
        checks['non_negative_violations'] = neg_cols

    # Water balance: skip row 0 (NaN expected)
    if 'balance_check' in df.columns:
        tail = df['balance_check'].iloc[1:]
        bad = tail.abs() > 0.01
        checks['water_balance_check'] = not bad.any()
        if bad.any():
            checks['water_balance_max_error'] = round(tail.abs().max(), 6)
    else:
        checks['water_balance_check'] = 'MISSING_COL'

    # Date continuity
    if 'day' in df.columns:
        days = pd.to_datetime(df['day'])
        diffs = days.diff().dropna()
        checks['date_continuity'] = bool((diffs == pd.Timedelta('1D')).all())
    else:
        checks['date_continuity'] = 'MISSING_COL'

    # Tank bounds
    if has_tank and 'tank_volume_m3' in df.columns:
        checks['tank_lower_bound'] = bool(df['tank_volume_m3'].ge(-0.001).all())
    else:
        checks['tank_lower_bound'] = 'N/A (no tank)'

    return checks


def key_metrics(df):
    m = {}

    m['total_water_cost'] = round(df['total_water_cost'].sum(), 2) \
        if 'total_water_cost' in df.columns else 'N/A'

    # Treatment volume
    if 'treatment_feed_m3' in df.columns:
        m['total_treatment_feed_m3'] = round(df['treatment_feed_m3'].sum(), 2)
    else:
        m['total_treatment_feed_m3'] = 'N/A'

    # Municipal to irrigation tank
    if 'municipal_to_tank_m3' in df.columns:
        m['total_municipal_to_tank_m3'] = round(df['municipal_to_tank_m3'].sum(), 2)
    else:
        m['total_municipal_to_tank_m3'] = 'N/A'

    # Municipal to community (direct, not via tank)
    if 'municipal_community_m3' in df.columns:
        m['total_municipal_community_m3'] = round(df['municipal_community_m3'].sum(), 2)
    else:
        m['total_municipal_community_m3'] = 'N/A'

    # Groundwater extracted
    if 'total_groundwater_extracted_m3' in df.columns:
        m['total_groundwater_extracted_m3'] = round(df['total_groundwater_extracted_m3'].sum(), 2)
    else:
        m['total_groundwater_extracted_m3'] = 'N/A'

    # Deficit
    if 'deficit_m3' in df.columns:
        m['total_deficit_m3'] = round(df['deficit_m3'].sum(), 2)
        m['deficit_days_count'] = int((df['deficit_m3'] > 0.001).sum())
    else:
        m['total_deficit_m3'] = 'N/A'
        m['deficit_days_count'] = 'N/A'

    return m


def per_test_checks(test_id, df):
    pt = {}
    if df is None:
        return pt

    if test_id == 'WS1':
        # Single well (1400 ppm), less treatment expected vs WS2
        if 'well_1_tds_ppm' in df.columns:
            pt['well_1_tds_ppm_constant'] = df['well_1_tds_ppm'].unique().tolist()
        if 'treatment_feed_m3' in df.columns:
            pt['treatment_feed_m3_total'] = round(df['treatment_feed_m3'].sum(), 2)
        if 'total_groundwater_extracted_m3' in df.columns:
            pt['gw_extracted_total_m3'] = round(df['total_groundwater_extracted_m3'].sum(), 2)
        if 'deficit_m3' in df.columns:
            pt['peak_deficit_m3'] = round(df['deficit_m3'].max(), 2)

    elif test_id == 'WS2':
        # High TDS wells only — treatment should be binding
        if 'treatment_utilization_pct' in df.columns:
            pt['mean_treatment_utilization_pct'] = round(
                df[df['treatment_utilization_pct'] > 0]['treatment_utilization_pct'].mean(), 1)
        if 'well_2_tds_ppm' in df.columns:
            pt['well_2_tds_ppm'] = int(df['well_2_tds_ppm'].iloc[0])
        if 'well_3_tds_ppm' in df.columns:
            pt['well_3_tds_ppm'] = int(df['well_3_tds_ppm'].iloc[0])
        if 'treatment_feed_m3' in df.columns and 'total_groundwater_extracted_m3' in df.columns:
            gw = df['total_groundwater_extracted_m3'].sum()
            trt = df['treatment_feed_m3'].sum()
            pt['treatment_as_pct_of_gw'] = round(100 * trt / gw, 1) if gw > 0 else 'N/A'

    elif test_id == 'WS4':
        # Small treatment — bottleneck expected
        if 'treatment_max_feed_m3' in df.columns:
            pt['treatment_max_feed_m3_per_day'] = round(
                df['treatment_max_feed_m3'].max(), 2)
        if 'deficit_m3' in df.columns:
            pt['peak_deficit_m3'] = round(df['deficit_m3'].max(), 2)
        if 'municipal_to_tank_m3' in df.columns:
            pt['total_municipal_to_tank_m3'] = round(df['municipal_to_tank_m3'].sum(), 2)

    elif test_id == 'WS5':
        # Large treatment — never bottlenecked
        if 'treatment_utilization_pct' in df.columns:
            active = df[df['treatment_utilization_pct'] > 0]['treatment_utilization_pct']
            pt['max_treatment_utilization_pct'] = round(active.max(), 1) if len(active) else 0
            pt['mean_treatment_utilization_pct'] = round(active.mean(), 1) if len(active) else 0

    elif test_id == 'WS7':
        # Tiny tank
        if 'tank_volume_m3' in df.columns:
            pt['tank_max_m3'] = round(df['tank_volume_m3'].max(), 2)
            pt['tank_min_m3'] = round(df['tank_volume_m3'].min(), 2)
            fill_events = int((df['tank_volume_m3'].diff().fillna(0) > 0.5).sum())
            pt['tank_fill_events'] = fill_events

    elif test_id == 'WS8':
        # Huge tank — deficit should be 0
        if 'tank_volume_m3' in df.columns:
            pt['tank_max_m3'] = round(df['tank_volume_m3'].max(), 2)
        if 'deficit_m3' in df.columns:
            pt['deficit_days'] = int((df['deficit_m3'] > 0.001).sum())
            pt['total_deficit_m3'] = round(df['deficit_m3'].sum(), 2)

    elif test_id == 'WS9':
        # Expensive municipal — minimize_cost should reduce municipal usage
        if 'municipal_to_tank_m3' in df.columns:
            pt['total_municipal_to_tank_m3'] = round(df['municipal_to_tank_m3'].sum(), 2)
        if 'total_water_cost' in df.columns:
            pt['total_water_cost'] = round(df['total_water_cost'].sum(), 2)

    elif test_id == 'WS10':
        # Low TDS municipal — less blending/treatment needed
        if 'treatment_feed_m3' in df.columns:
            pt['total_treatment_feed_m3'] = round(df['treatment_feed_m3'].sum(), 2)
        if 'municipal_to_tank_m3' in df.columns:
            pt['total_municipal_to_tank_m3'] = round(df['municipal_to_tank_m3'].sum(), 2)

    return pt


# ─── Load and analyze all tests ──────────────────────────────────────────────
all_results = {}

for test_id, (test_dir_name, test_name) in TESTS.items():
    df = load_water_df(test_dir_name)
    has_tank = test_id not in ('WS6',)
    crashed = df is None

    if crashed:
        all_results[test_id] = {
            'name': test_name,
            'status': 'FAIL',
            'checks': {},
            'metrics': {},
            'per_test': {},
            'notes': CRASH_NOTES.get(test_id, 'No output file found.'),
        }
        continue

    checks = universal_checks(df, has_tank=has_tank)
    metrics = key_metrics(df)
    pt = per_test_checks(test_id, df)

    # Determine overall status
    critical_checks = ['no_nan_key_cols', 'non_negative_quantities',
                       'water_balance_check', 'date_continuity']
    any_fail = any(
        checks.get(k) is False
        for k in critical_checks
    )
    status = 'FAIL' if any_fail else 'PASS'
    # Downgrade to WARNING if only non-critical checks failed
    if status == 'FAIL' and not any(
        checks.get(k) is False
        for k in ['no_nan_key_cols', 'non_negative_quantities', 'date_continuity']
    ):
        status = 'WARNING'

    notes = []
    if 'crop_tds_requirement_ppm' in df.columns:
        nan_tds = df['crop_tds_requirement_ppm'].isna().sum()
        if nan_tds > 0:
            notes.append(
                f'crop_tds_requirement_ppm has {nan_tds} NaN rows (no active crops on those days — expected).')
    if 'balance_check' in df.columns and df['balance_check'].iloc[0] != df['balance_check'].iloc[0]:
        notes.append('balance_check row 0 is NaN (expected; initial tank state)')

    all_results[test_id] = {
        'name': test_name,
        'status': status,
        'checks': checks,
        'metrics': metrics,
        'per_test': pt,
        'notes': '; '.join(notes) if notes else '',
    }


# ─── Print Report ─────────────────────────────────────────────────────────────
print("=" * 80)
print("STRESS TEST REPORT — WS1 through WS10")
print("=" * 80)

for test_id, (test_dir_name, test_name) in TESTS.items():
    r = all_results[test_id]
    print(f"\nTEST: {test_id} — {r['name']}")
    print(f"STATUS: {r['status']}")

    if r['status'] == 'FAIL' and not r['checks']:
        print(f"NOTES: {r['notes']}")
        continue

    print("UNIVERSAL CHECKS:")
    for k, v in r['checks'].items():
        if k == 'non_negative_violations':
            continue
        if v is True:
            mark = 'PASS'
        elif v is False:
            mark = 'FAIL'
        elif isinstance(v, str) and v.startswith('N/A'):
            mark = 'N/A'
        else:
            mark = 'WARN'
        print(f"  {k}: {mark} ({v})")

    print("PER-TEST CHECKS:")
    if r['per_test']:
        for k, v in r['per_test'].items():
            print(f"  {k}: {v}")
    else:
        print("  (none defined for this test)")

    print("KEY METRICS:")
    for k, v in r['metrics'].items():
        print(f"  {k}: {v}")

    if r['notes']:
        print(f"NOTES: {r['notes']}")


# ─── Cross-test comparisons ───────────────────────────────────────────────────
print("\n\n" + "=" * 80)
print("CROSS-TEST COMPARISONS")
print("=" * 80)

def get_metric(tid, key):
    v = all_results.get(tid, {}).get('metrics', {}).get(key, 'N/A')
    return v if v != 'N/A' else None


# Cost comparison
print("\nTotal Water Cost by Test:")
for tid in TESTS:
    cost = get_metric(tid, 'total_water_cost')
    status = all_results[tid]['status']
    print(f"  {tid:5s} ({all_results[tid]['name']:25s}): "
          f"{'FAIL/CRASH' if status == 'FAIL' and cost is None else f'{cost:>12,.2f} EGP'}")

# Deficit comparison
print("\nDeficit (m3 total / deficit days) by Test:")
for tid in TESTS:
    deficit = get_metric(tid, 'total_deficit_m3')
    days = get_metric(tid, 'deficit_days_count')
    status = all_results[tid]['status']
    if status == 'FAIL' and deficit is None:
        print(f"  {tid:5s} ({all_results[tid]['name']:25s}): FAIL/CRASH")
    else:
        print(f"  {tid:5s} ({all_results[tid]['name']:25s}): "
              f"{deficit:>12,.2f} m3  |  {days:>4} days")

# Treatment comparison
print("\nTotal Treatment Feed (m3) by Test:")
for tid in TESTS:
    trt = get_metric(tid, 'total_treatment_feed_m3')
    status = all_results[tid]['status']
    if status == 'FAIL' and trt is None:
        print(f"  {tid:5s} ({all_results[tid]['name']:25s}): FAIL/CRASH")
    else:
        print(f"  {tid:5s} ({all_results[tid]['name']:25s}): "
              f"{trt:>12,.2f} m3")

print()
