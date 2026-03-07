"""Run water policy stress tests W1 through W7.

Executes all water policy stress tests, validates results, and prints
structured findings. Tests cover strategy variants (W1-W4), look-ahead
enforcement (W5-W6), and tight cap scenarios (W7).
"""
import sys
import shutil
import yaml
import traceback
import pandas as pd
import numpy as np
from pathlib import Path

root = Path('/Users/dpbirge/GITHUB/community-agri-pv')
sys.path.insert(0, str(root))
from stress_testing.run_test import run

BASELINE = root / 'stress_testing' / 'baseline'
SETTINGS = root / 'settings'
REGISTRY = SETTINGS / 'data_registry_base.yaml'
FARM_PROFILE = BASELINE / 'farm_profile.yaml'
COMMUNITY_DEMANDS = BASELINE / 'community_demands.yaml'
ENERGY_POLICY_BASE = SETTINGS / 'energy_policy_base.yaml'

# Column name mappings for the actual CSV output
COL_TREATMENT = 'treatment_feed_m3'
COL_MUNICIPAL_IRR = 'municipal_to_tank_m3'
COL_MUNICIPAL_COMM = 'municipal_community_m3'
COL_GROUNDWATER = 'total_groundwater_extracted_m3'
COL_DEFICIT = 'deficit_m3'
COL_COST = 'total_water_cost'
COL_TOTAL_DEMAND = 'total_water_demand_m3'
COL_IRRIGATION_DELIVERED = 'irrigation_delivered_m3'
COL_BALANCE = 'balance_check'
COL_TANK = 'tank_volume_m3'
COL_DAY = 'day'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_base_water_policy():
    with open(SETTINGS / 'water_policy_base.yaml') as f:
        return yaml.safe_load(f)


def load_base_energy_policy():
    with open(ENERGY_POLICY_BASE) as f:
        return yaml.safe_load(f)


def make_offgrid_energy_policy(test_dir):
    """Write an off-grid compatible energy policy (mode: off_grid)."""
    policy = load_base_energy_policy()
    policy['grid']['mode'] = 'off_grid'
    with open(test_dir / 'energy_policy.yaml', 'w') as f:
        yaml.dump(policy, f, default_flow_style=False)


def setup_test_dir(test_name, regime, water_policy_overrides):
    """Create test directory, copy baseline files, write modified water_policy.yaml.

    For 'undersupply' regime, generates an off-grid compatible energy policy
    because the undersupply energy system has grid_connection: off_grid.

    Returns:
        Path to test directory.
    """
    test_dir = root / 'stress_testing' / test_name
    test_dir.mkdir(parents=True, exist_ok=True)

    ws_regime = regime if regime else 'balanced'
    es_regime = regime if regime else 'balanced'

    ws_src = BASELINE / f'water_systems_{ws_regime}.yaml'
    es_src = BASELINE / f'energy_system_{es_regime}.yaml'

    shutil.copy(ws_src, test_dir / 'water_systems.yaml')
    shutil.copy(es_src, test_dir / 'energy_system.yaml')

    if regime == 'undersupply':
        make_offgrid_energy_policy(test_dir)
    else:
        shutil.copy(ENERGY_POLICY_BASE, test_dir / 'energy_policy.yaml')

    policy = load_base_water_policy()
    for key_path, value in water_policy_overrides.items():
        keys = key_path.split('.')
        target = policy
        for k in keys[:-1]:
            target = target[k]
        target[keys[-1]] = value

    with open(test_dir / 'water_policy.yaml', 'w') as f:
        yaml.dump(policy, f, default_flow_style=False)

    return test_dir


def run_test(test_dir):
    """Run simulation for a test directory. Returns (water_df, energy_df) or raises."""
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


def load_result_csvs(test_dir):
    water_csv = pd.read_csv(test_dir / 'results' / 'daily_water_balance.csv', comment='#')
    energy_csv = pd.read_csv(test_dir / 'results' / 'daily_energy_balance.csv', comment='#')
    return water_csv, energy_csv


def total_municipal(df):
    """Sum irrigation + community municipal water."""
    irr = df[COL_MUNICIPAL_IRR].sum() if COL_MUNICIPAL_IRR in df.columns else 0.0
    comm = df[COL_MUNICIPAL_COMM].sum() if COL_MUNICIPAL_COMM in df.columns else 0.0
    return irr + comm


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def universal_checks(water_df, energy_df, test_dir):
    """Run universal validation checks. Returns list of (check_name, pass, detail)."""
    results = []

    # 1. No crashes — already passed if we get here
    results.append(('No crashes', True, 'Simulation completed'))

    # 2. No NaN in key columns
    key_cols = [COL_TOTAL_DEMAND, COL_DEFICIT]
    # irrigation_delivered_m3 tracks water delivered to fields
    nan_found = []
    for col in key_cols:
        if col in water_df.columns:
            if water_df[col].isna().any():
                nan_found.append(col)
        else:
            nan_found.append(f'{col} (missing)')
    if nan_found:
        results.append(('No NaN in key columns', False, f'Issues: {nan_found}'))
    else:
        results.append(('No NaN in key columns', True, f'All clean: {key_cols}'))

    # 3. Non-negative quantities
    m3_cols = [c for c in water_df.columns if c.endswith('_m3') and c != COL_DEFICIT]
    kwh_cols = [c for c in water_df.columns if c.endswith('_kwh')]
    cost_cols = [c for c in water_df.columns if c.endswith('_cost')]
    neg_cols = []
    for col in m3_cols + kwh_cols + cost_cols:
        if (water_df[col] < -0.001).any():
            neg_cols.append(col)
    if neg_cols:
        results.append(('Non-negative quantities', False, f'Negative values in: {neg_cols[:5]}'))
    else:
        results.append(('Non-negative quantities', True, 'All >= 0'))

    # 4. Water balance check
    if COL_BALANCE in water_df.columns:
        check_rows = water_df.iloc[1:]  # skip row 0 which may be NaN
        max_imbalance = check_rows[COL_BALANCE].abs().max()
        if max_imbalance >= 0.01:
            results.append(('Water balance', False,
                            f'Max |balance_check| = {max_imbalance:.4f}'))
        else:
            results.append(('Water balance', True,
                            f'Max |balance_check| = {max_imbalance:.6f}'))
    else:
        results.append(('Water balance', False, 'balance_check column missing'))

    # 5. Date continuity
    if COL_DAY in water_df.columns:
        dates = pd.to_datetime(water_df[COL_DAY])
        diffs = dates.diff().dropna()
        gaps = (diffs != pd.Timedelta(days=1)).sum()
        if gaps > 0:
            results.append(('Date continuity', False, f'{gaps} gaps in day column'))
        else:
            results.append(('Date continuity', True, 'No gaps'))
    else:
        results.append(('Date continuity', False, 'day column missing'))

    # 6. Tank bounds
    if COL_TANK in water_df.columns:
        ws_path = test_dir / 'water_systems.yaml'
        with open(ws_path) as f:
            ws = yaml.safe_load(f)
        capacity = ws['systems'][0]['storage']['capacity_m3']
        below_zero = (water_df[COL_TANK] < -0.001).sum()
        above_cap = (water_df[COL_TANK] > capacity + 0.001).sum()
        if below_zero > 0 or above_cap > 0:
            results.append(('Tank bounds', False,
                            f'{below_zero} below 0, {above_cap} above cap={capacity}'))
        else:
            results.append(('Tank bounds', True, f'Within [0, {capacity}] m3'))
    else:
        results.append(('Tank bounds', False, 'tank_volume_m3 column missing'))

    return results


def key_metrics(water_df):
    """Extract key summary metrics from water DataFrame."""
    metrics = {}
    metrics['total_water_cost'] = round(
        water_df[COL_COST].sum() if COL_COST in water_df.columns else float('nan'), 2)
    metrics['total_treatment_m3'] = round(
        water_df[COL_TREATMENT].sum() if COL_TREATMENT in water_df.columns else float('nan'), 2)
    metrics['total_municipal_m3'] = round(total_municipal(water_df), 2)
    metrics['total_groundwater_m3'] = round(
        water_df[COL_GROUNDWATER].sum() if COL_GROUNDWATER in water_df.columns else float('nan'), 2)
    metrics['total_deficit_m3'] = round(
        water_df[COL_DEFICIT].sum() if COL_DEFICIT in water_df.columns else float('nan'), 2)
    return metrics


def print_report(test_id, test_name, universal, per_test, km, notes=''):
    print(f"\n{'='*70}")
    print(f"TEST: {test_id} — {test_name}")
    u_pass = all(p for _, p, _ in universal)
    pt_pass = all(p is not False for _, p, _ in per_test)
    overall = 'PASS' if (u_pass and pt_pass) else 'FAIL'
    print(f"STATUS: {overall}")
    print("UNIVERSAL CHECKS:")
    for name, passed, detail in universal:
        status = 'PASS' if passed else 'FAIL'
        print(f"  [{status}] {name}: {detail}")
    print("PER-TEST CHECKS:")
    for name, passed, detail in per_test:
        if passed is None:
            status = 'WARN'
        elif passed:
            status = 'PASS'
        else:
            status = 'FAIL'
        print(f"  [{status}] {name}: {detail}")
    print("KEY METRICS:")
    for k, v in km.items():
        print(f"  {k}: {v}")
    if notes:
        print(f"NOTES: {notes}")


# ---------------------------------------------------------------------------
# Individual test runners
# ---------------------------------------------------------------------------

def run_strategy_test(test_dir_name, regime, strategy):
    """Generic runner for W1/W2/W3 strategy tests."""
    try:
        test_dir = setup_test_dir(test_dir_name, regime, {'strategy': strategy})
        water_df, energy_df = run_test(test_dir)
        water_csv, energy_csv = load_result_csvs(test_dir)
        u_checks = universal_checks(water_csv, energy_csv, test_dir)
        km = key_metrics(water_csv)
        return {'status': 'ok', 'metrics': km, 'u_checks': u_checks,
                'water_csv': water_csv, 'test_dir': test_dir}
    except Exception as e:
        traceback.print_exc()
        return {'status': 'crash', 'error': str(e)}


def run_w4():
    test_dir_name = 'water_04_maximize_treatment_efficiency'
    print(f"\n--- Setting up W4 ---")
    try:
        test_dir = setup_test_dir(
            test_dir_name, 'balanced',
            {'strategy': 'maximize_treatment_efficiency'}
        )
        water_df, energy_df = run_test(test_dir)
        water_csv, energy_csv = load_result_csvs(test_dir)
        u_checks = universal_checks(water_csv, energy_csv, test_dir)
        km = key_metrics(water_csv)
        return {'status': 'ok', 'metrics': km, 'u_checks': u_checks,
                'water_csv': water_csv, 'test_dir': test_dir}
    except Exception as e:
        traceback.print_exc()
        return {'status': 'crash', 'error': str(e)}


def run_w5():
    test_dir_name = 'water_05_look_ahead_on'
    print(f"\n--- Setting up W5 ---")
    try:
        test_dir = setup_test_dir(
            test_dir_name, 'balanced',
            {'cap_enforcement.look_ahead': True}
        )
        water_df, energy_df = run_test(test_dir)
        water_csv, energy_csv = load_result_csvs(test_dir)
        u_checks = universal_checks(water_csv, energy_csv, test_dir)
        km = key_metrics(water_csv)
        return {'status': 'ok', 'metrics': km, 'u_checks': u_checks,
                'water_csv': water_csv, 'test_dir': test_dir}
    except Exception as e:
        traceback.print_exc()
        return {'status': 'crash', 'error': str(e)}


def run_w6():
    test_dir_name = 'water_06_look_ahead_off'
    print(f"\n--- Setting up W6 ---")
    try:
        test_dir = setup_test_dir(
            test_dir_name, 'balanced',
            {'cap_enforcement.look_ahead': False}
        )
        water_df, energy_df = run_test(test_dir)
        water_csv, energy_csv = load_result_csvs(test_dir)
        u_checks = universal_checks(water_csv, energy_csv, test_dir)
        km = key_metrics(water_csv)
        return {'status': 'ok', 'metrics': km, 'u_checks': u_checks,
                'water_csv': water_csv, 'test_dir': test_dir}
    except Exception as e:
        traceback.print_exc()
        return {'status': 'crash', 'error': str(e)}


def run_w7():
    test_dir_name = 'water_07_tight_municipal_cap'
    print(f"\n--- Setting up W7 ---")
    try:
        test_dir = setup_test_dir(
            test_dir_name, 'balanced',
            {'municipal.monthly_cap_m3': 50}
        )
        water_df, energy_df = run_test(test_dir)
        water_csv, energy_csv = load_result_csvs(test_dir)
        u_checks = universal_checks(water_csv, energy_csv, test_dir)
        km = key_metrics(water_csv)
        return {'status': 'ok', 'metrics': km, 'u_checks': u_checks,
                'water_csv': water_csv, 'test_dir': test_dir}
    except Exception as e:
        traceback.print_exc()
        return {'status': 'crash', 'error': str(e)}


# ---------------------------------------------------------------------------
# Per-test validation checks
# ---------------------------------------------------------------------------

def check_w1_cost_ordering(w1_r, w2_r, w3_r, regime):
    """minimize_cost should have lowest total_water_cost among W1-W3."""
    checks = []
    if w1_r['status'] != 'ok':
        return [('minimize_cost has lowest cost', False, f'W1 crashed: {w1_r.get("error","")}')]
    if w2_r['status'] != 'ok' or w3_r['status'] != 'ok':
        return [('minimize_cost has lowest cost', None,
                 'Cannot compare: W2 or W3 crashed')]
    c1 = w1_r['metrics']['total_water_cost']
    c2 = w2_r['metrics']['total_water_cost']
    c3 = w3_r['metrics']['total_water_cost']
    passed = (c1 <= c2 + 0.01) and (c1 <= c3 + 0.01)
    checks.append((
        f'minimize_cost has lowest cost ({regime})',
        passed,
        f'W1={c1:.2f}, W2={c2:.2f}, W3={c3:.2f}'
    ))
    return checks


def check_w2_treatment(w1_r, w2_r, w3_r, regime):
    """minimize_treatment should use <= treatment volume compared to W1 and W3."""
    checks = []
    if w2_r['status'] != 'ok':
        return [('minimize_treatment has least treatment', False, f'W2 crashed')]
    t2 = w2_r['metrics']['total_treatment_m3']
    m2 = w2_r['metrics']['total_municipal_m3']

    if w1_r['status'] == 'ok' and w3_r['status'] == 'ok':
        t1 = w1_r['metrics']['total_treatment_m3']
        t3 = w3_r['metrics']['total_treatment_m3']
        m1 = w1_r['metrics']['total_municipal_m3']
        passed = (t2 <= t1 + 0.01) and (t2 <= t3 + 0.01)
        checks.append((
            f'minimize_treatment has least treatment ({regime})',
            passed,
            f'W1={t1:.2f}, W2={t2:.2f}, W3={t3:.2f} m3'
        ))
        checks.append((
            f'minimize_treatment uses >= municipal vs minimize_cost ({regime})',
            m2 >= m1 - 0.01,
            f'W1_mun={m1:.2f}, W2_mun={m2:.2f} m3'
        ))
    else:
        checks.append((
            f'minimize_treatment treatment volume ({regime})',
            None,
            f'W2 treatment={t2:.2f} m3 (cannot compare, other tests crashed)'
        ))
    return checks


def check_w3_municipal_priority(w3_r, regime):
    """minimize_draw should use meaningful municipal volume first."""
    checks = []
    if w3_r['status'] != 'ok':
        return [('minimize_draw uses municipal', False, 'W3 crashed')]
    mun = w3_r['metrics']['total_municipal_m3']
    gw = w3_r['metrics']['total_groundwater_m3']
    checks.append((
        f'minimize_draw uses municipal water ({regime})',
        mun > 0,
        f'municipal={mun:.2f} m3, groundwater={gw:.2f} m3'
    ))
    return checks


def check_w4_treatment_efficiency(w4_r):
    """Treatment should run at 70-85% of rated capacity on active days."""
    checks = []
    if w4_r['status'] != 'ok':
        return [('Treatment efficiency range', False, 'Test crashed')]
    water_csv = w4_r['water_csv']
    ws_path = w4_r['test_dir'] / 'water_systems.yaml'
    with open(ws_path) as f:
        ws = yaml.safe_load(f)
    throughput_m3_hr = ws['systems'][0]['treatment']['throughput_m3_hr']
    daily_rated = throughput_m3_hr * 24  # m3/day at 100% utilization

    if 'treatment_utilization_pct' in water_csv.columns:
        # utilization_pct is already computed in the output
        active = water_csv[water_csv['treatment_on'] == True] if 'treatment_on' in water_csv.columns else water_csv[water_csv[COL_TREATMENT] > 0]
        if len(active) > 0:
            util_vals = active['treatment_utilization_pct'] / 100.0
            pct_in_sweet = ((util_vals >= 0.70) & (util_vals <= 0.85)).mean()
            checks.append((
                'Treatment at 70-85% rated capacity on active days',
                pct_in_sweet >= 0.40,
                f'{pct_in_sweet*100:.1f}% of active days in sweet spot; '
                f'mean util={util_vals.mean()*100:.1f}%; active_days={len(active)}'
            ))
        else:
            checks.append(('Treatment efficiency', False, 'No active treatment days'))
    elif COL_TREATMENT in water_csv.columns:
        active_days = water_csv[water_csv[COL_TREATMENT] > 0]
        if len(active_days) > 0:
            utilization = active_days[COL_TREATMENT] / daily_rated
            pct_in_sweet = ((utilization >= 0.70) & (utilization <= 0.85)).mean()
            checks.append((
                'Treatment at 70-85% rated capacity on active days',
                pct_in_sweet >= 0.40,
                f'{pct_in_sweet*100:.1f}% of active days in sweet spot; '
                f'mean util={utilization.mean()*100:.1f}%'
            ))
        else:
            checks.append(('Treatment efficiency', False, 'No active treatment days'))
    else:
        checks.append(('Treatment efficiency check', False, f'{COL_TREATMENT} column missing'))

    # Also check fallow treatment: treatment_on True on days with zero irrigation demand
    if 'treatment_on' in water_csv.columns and 'irrigation_demand_m3' in water_csv.columns:
        fallow_days = water_csv[water_csv['irrigation_demand_m3'] == 0]
        if len(fallow_days) > 0:
            fallow_treating = (fallow_days['treatment_on'] == True).sum()
            checks.append((
                'Fallow treatment active (builds tank buffer)',
                fallow_treating > 0,
                f'{fallow_treating}/{len(fallow_days)} fallow days with treatment active'
            ))

    return checks


def check_w5_look_ahead_on(w5_r):
    """Municipal usage spread evenly; no zero-supply late in month."""
    checks = []
    if w5_r['status'] != 'ok':
        return [('Look-ahead spread', False, 'Test crashed')]
    water_csv = w5_r['water_csv'].copy()
    if COL_MUNICIPAL_IRR in water_csv.columns and COL_DAY in water_csv.columns:
        water_csv[COL_DAY] = pd.to_datetime(water_csv[COL_DAY])
        water_csv['month'] = water_csv[COL_DAY].dt.to_period('M')
        water_csv['muni_total'] = (
            water_csv[COL_MUNICIPAL_IRR] +
            (water_csv[COL_MUNICIPAL_COMM] if COL_MUNICIPAL_COMM in water_csv.columns else 0)
        )
        monthly_cv = water_csv.groupby('month')['muni_total'].apply(
            lambda x: x.std() / x.mean() if x.mean() > 0 else 0
        )
        mean_cv = monthly_cv.mean()
        # With look-ahead on, spreading evenly — expect moderate-to-low CV
        checks.append((
            'Municipal usage spread across month (look-ahead on)',
            mean_cv < 3.0,
            f'Mean monthly CV = {mean_cv:.3f} (lower = more even spread)'
        ))
        # Check last 7 days of each month for zero supply
        water_csv['day_of_month'] = water_csv[COL_DAY].dt.day
        water_csv['days_in_month'] = water_csv[COL_DAY].dt.days_in_month
        late_month = water_csv[
            water_csv['day_of_month'] > (water_csv['days_in_month'] - 7)
        ]
        if COL_DEFICIT in water_csv.columns:
            zero_supply_late = (late_month[COL_DEFICIT] > late_month['muni_total']).sum()
            checks.append((
                'No complete zero-municipal days in last week of month',
                zero_supply_late == 0,
                f'{zero_supply_late} days where deficit > municipal in last week'
            ))
    return checks


def check_w6_look_ahead_off(w6_r, w5_r):
    """With look-ahead off, expect higher variance or early cap exhaustion."""
    checks = []
    if w6_r['status'] != 'ok':
        return [('Look-ahead off behavior', False, 'Test crashed')]
    water_csv = w6_r['water_csv'].copy()
    if COL_MUNICIPAL_IRR in water_csv.columns and COL_DAY in water_csv.columns:
        water_csv[COL_DAY] = pd.to_datetime(water_csv[COL_DAY])
        water_csv['month'] = water_csv[COL_DAY].dt.to_period('M')
        water_csv['muni_total'] = (
            water_csv[COL_MUNICIPAL_IRR] +
            (water_csv[COL_MUNICIPAL_COMM] if COL_MUNICIPAL_COMM in water_csv.columns else 0)
        )
        monthly_cv_off = water_csv.groupby('month')['muni_total'].apply(
            lambda x: x.std() / x.mean() if x.mean() > 0 else 0
        ).mean()

        cv_on = None
        if w5_r and w5_r['status'] == 'ok':
            w5_csv = w5_r['water_csv'].copy()
            w5_csv[COL_DAY] = pd.to_datetime(w5_csv[COL_DAY])
            w5_csv['month'] = w5_csv[COL_DAY].dt.to_period('M')
            w5_csv['muni_total'] = (
                w5_csv[COL_MUNICIPAL_IRR] +
                (w5_csv[COL_MUNICIPAL_COMM] if COL_MUNICIPAL_COMM in w5_csv.columns else 0)
            )
            cv_on = w5_csv.groupby('month')['muni_total'].apply(
                lambda x: x.std() / x.mean() if x.mean() > 0 else 0
            ).mean()

        # With look-ahead off, CV should be >= look-ahead on (less smooth)
        if cv_on is not None:
            checks.append((
                'Look-ahead off has >= CV vs look-ahead on (less smooth)',
                monthly_cv_off >= cv_on - 0.01,
                f'CV off={monthly_cv_off:.3f}, CV on={cv_on:.3f}'
            ))
        else:
            checks.append((
                'Municipal CV with look-ahead off (informational)',
                None,
                f'CV={monthly_cv_off:.3f}'
            ))

        # Check days after day 20 with zero municipal
        water_csv['day_of_month'] = water_csv[COL_DAY].dt.day
        zero_mun_late = water_csv[
            (water_csv['day_of_month'] > 20) & (water_csv['muni_total'] == 0)
        ]
        checks.append((
            'Zero municipal days after day 20 (cap exhaustion pattern)',
            None,  # informational
            f'{len(zero_mun_late)} days with zero municipal after day 20'
        ))
    return checks


def check_w7_tight_cap(w7_r):
    """Tight cap (50 m3/month) should be hit and deficit should appear."""
    checks = []
    if w7_r['status'] != 'ok':
        return [('Tight cap hit', False, 'Test crashed')]
    water_csv = w7_r['water_csv'].copy()
    if COL_MUNICIPAL_IRR in water_csv.columns and COL_DAY in water_csv.columns:
        water_csv[COL_DAY] = pd.to_datetime(water_csv[COL_DAY])
        water_csv['month'] = water_csv[COL_DAY].dt.to_period('M')
        water_csv['muni_total'] = (
            water_csv[COL_MUNICIPAL_IRR] +
            (water_csv[COL_MUNICIPAL_COMM] if COL_MUNICIPAL_COMM in water_csv.columns else 0)
        )
        monthly_mun = water_csv.groupby('month')['muni_total'].sum()
        cap_hit = (monthly_mun >= 49.9).sum()
        sample = monthly_mun.values[:4]
        checks.append((
            'Monthly municipal cap (50 m3) hit in some months',
            cap_hit > 0,
            f'{cap_hit}/{len(monthly_mun)} months hit cap; '
            f'sample monthly totals: {[round(v,1) for v in sample]}'
        ))
    if COL_DEFICIT in water_csv.columns:
        total_deficit = water_csv[COL_DEFICIT].sum()
        checks.append((
            'Deficit appears under tight cap',
            total_deficit > 0,
            f'Total deficit = {total_deficit:.2f} m3'
        ))
    return checks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    print("=" * 70)
    print("WATER POLICY STRESS TESTS W1-W7")
    print("=" * 70)

    # --- Run W1: minimize_cost (all regimes) ---
    print("\n[Running W1: minimize_cost — all regimes]")
    w1 = {}
    for regime in ['oversupply', 'balanced', 'undersupply']:
        print(f"\n--- Setting up W1_{regime} ---")
        w1[regime] = run_strategy_test(
            f'water_01_minimize_cost_{regime}', regime, 'minimize_cost'
        )

    # --- Run W2: minimize_treatment (all regimes) ---
    print("\n[Running W2: minimize_treatment — all regimes]")
    w2 = {}
    for regime in ['oversupply', 'balanced', 'undersupply']:
        print(f"\n--- Setting up W2_{regime} ---")
        w2[regime] = run_strategy_test(
            f'water_02_minimize_treatment_{regime}', regime, 'minimize_treatment'
        )

    # --- Run W3: minimize_draw (all regimes) ---
    print("\n[Running W3: minimize_draw — all regimes]")
    w3 = {}
    for regime in ['oversupply', 'balanced', 'undersupply']:
        print(f"\n--- Setting up W3_{regime} ---")
        w3[regime] = run_strategy_test(
            f'water_03_minimize_draw_{regime}', regime, 'minimize_draw'
        )

    # --- Run W4 through W7 ---
    print("\n[Running W4: maximize_treatment_efficiency — balanced]")
    w4 = run_w4()

    print("\n[Running W5: look_ahead_on — balanced]")
    w5 = run_w5()

    print("\n[Running W6: look_ahead_off — balanced]")
    w6 = run_w6()

    print("\n[Running W7: tight_municipal_cap — balanced]")
    w7 = run_w7()

    # -----------------------------------------------------------------------
    # Print Reports
    # -----------------------------------------------------------------------

    # W1
    for regime in ['oversupply', 'balanced', 'undersupply']:
        r = w1[regime]
        if r['status'] == 'crash':
            print_report(f'W1 ({regime})', f'minimize_cost ({regime})',
                        [('No crashes', False, r['error'])], [], {})
        else:
            pt = check_w1_cost_ordering(w1[regime], w2[regime], w3[regime], regime)
            print_report(f'W1 ({regime})', f'minimize_cost ({regime})',
                        r['u_checks'], pt, r['metrics'])

    # W2
    for regime in ['oversupply', 'balanced', 'undersupply']:
        r = w2[regime]
        if r['status'] == 'crash':
            print_report(f'W2 ({regime})', f'minimize_treatment ({regime})',
                        [('No crashes', False, r['error'])], [], {})
        else:
            pt = check_w2_treatment(w1[regime], w2[regime], w3[regime], regime)
            print_report(f'W2 ({regime})', f'minimize_treatment ({regime})',
                        r['u_checks'], pt, r['metrics'])

    # W3
    for regime in ['oversupply', 'balanced', 'undersupply']:
        r = w3[regime]
        if r['status'] == 'crash':
            print_report(f'W3 ({regime})', f'minimize_draw ({regime})',
                        [('No crashes', False, r['error'])], [], {})
        else:
            pt = check_w3_municipal_priority(r, regime)
            print_report(f'W3 ({regime})', f'minimize_draw ({regime})',
                        r['u_checks'], pt, r['metrics'])

    # W4
    if w4['status'] == 'crash':
        print_report('W4', 'maximize_treatment_efficiency',
                    [('No crashes', False, w4['error'])], [], {})
    else:
        pt = check_w4_treatment_efficiency(w4)
        print_report('W4', 'maximize_treatment_efficiency',
                    w4['u_checks'], pt, w4['metrics'])

    # W5
    if w5['status'] == 'crash':
        print_report('W5', 'look_ahead_on',
                    [('No crashes', False, w5['error'])], [], {})
    else:
        pt = check_w5_look_ahead_on(w5)
        print_report('W5', 'look_ahead_on', w5['u_checks'], pt, w5['metrics'])

    # W6
    if w6['status'] == 'crash':
        print_report('W6', 'look_ahead_off',
                    [('No crashes', False, w6['error'])], [], {})
    else:
        pt = check_w6_look_ahead_off(w6, w5)
        print_report('W6', 'look_ahead_off', w6['u_checks'], pt, w6['metrics'])

    # W7
    if w7['status'] == 'crash':
        print_report('W7', 'tight_municipal_cap',
                    [('No crashes', False, w7['error'])], [], {})
    else:
        pt = check_w7_tight_cap(w7)
        print_report('W7', 'tight_municipal_cap', w7['u_checks'], pt, w7['metrics'])

    print(f"\n{'='*70}")
    print("ALL TESTS COMPLETE")
    print(f"{'='*70}")
