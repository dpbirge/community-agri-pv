"""Run E1, E2, E3 energy dispatch strategy stress tests across 3 supply regimes.

Nine tests total: each strategy (minimize_cost, minimize_grid_reliance,
minimize_generator) run against oversupply, balanced, and undersupply
energy system configurations.
"""
import sys
import shutil
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from stress_testing.run_test import run

BASELINE = _repo_root / 'stress_testing' / 'baseline'
SETTINGS = _repo_root / 'settings'
OUTPUT_BASE = _repo_root / 'stress_testing' / 'individual_tests'
REGISTRY = SETTINGS / 'data_registry_base.yaml'

ENERGY_POLICY_TEMPLATE = SETTINGS / 'energy_policy_base.yaml'
WATER_POLICY_SRC = SETTINGS / 'water_policy_base.yaml'
FARM_PROFILE_SRC = BASELINE / 'farm_profile_openfield.yaml'
COMMUNITY_DEMANDS = BASELINE / 'community_demands.yaml'

REGIMES = ['oversupply', 'balanced', 'undersupply']

TESTS = [
    dict(
        test_id='E1',
        dir_prefix='energy_01_minimize_cost',
        strategy='minimize_cost',
    ),
    dict(
        test_id='E2',
        dir_prefix='energy_02_minimize_grid',
        strategy='minimize_grid_reliance',
    ),
    dict(
        test_id='E3',
        dir_prefix='energy_03_minimize_generator',
        strategy='minimize_generator',
    ),
]


def _build_energy_policy(strategy, dest_path, energy_system_path):
    """Read template energy policy and write a copy with strategy and grid mode set.

    Grid mode must be compatible with grid_connection in the energy system config.
    For off_grid connections, mode is forced to off_grid regardless of template.
    """
    with open(ENERGY_POLICY_TEMPLATE) as f:
        policy = yaml.safe_load(f)
    with open(energy_system_path) as f:
        esys = yaml.safe_load(f)
    policy['strategy'] = strategy
    grid_connection = esys.get('grid_connection', 'full_grid')
    if grid_connection == 'off_grid':
        policy.setdefault('grid', {})['mode'] = 'off_grid'
    with open(dest_path, 'w') as f:
        yaml.dump(policy, f, default_flow_style=False, sort_keys=False)


def _setup_test_dir(test_dir, regime):
    """Create test directory and copy required settings files."""
    test_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(FARM_PROFILE_SRC, test_dir / 'farm_profile.yaml')
    shutil.copy(WATER_POLICY_SRC, test_dir / 'water_policy.yaml')
    shutil.copy(
        BASELINE / f'water_systems_{regime}.yaml',
        test_dir / 'water_systems.yaml',
    )
    shutil.copy(
        BASELINE / f'energy_system_{regime}.yaml',
        test_dir / 'energy_system.yaml',
    )


def _validate(water_df, energy_df, energy_system_path):
    """Run validation checks and return list of failure strings."""
    failures = []

    # --- No-crash already implied by reaching this point ---

    # 1. NaN check — required columns
    required_water = ['total_demand_m3', 'total_delivered_m3']
    required_energy = ['total_demand_kwh', 'total_renewable_kwh']
    for col in required_water:
        if col in water_df.columns and water_df[col].isna().any():
            failures.append(f'NaN in water column: {col}')
    for col in required_energy:
        if col in energy_df.columns and energy_df[col].isna().any():
            failures.append(f'NaN in energy column: {col}')
    if 'deficit_kwh' in energy_df.columns and energy_df['deficit_kwh'].isna().any():
        failures.append('NaN in energy column: deficit_kwh')
    if 'deficit_m3' in water_df.columns and water_df['deficit_m3'].isna().any():
        failures.append('NaN in water column: deficit_m3')

    # 2. Non-negative check — all _m3 and _kwh and _cost columns
    for df, label in [(water_df, 'water'), (energy_df, 'energy')]:
        for col in df.columns:
            if col.endswith(('_m3', '_kwh', '_cost', '_usd')):
                if (df[col] < -0.01).any():
                    failures.append(
                        f'Negative values in {label} column: {col} '
                        f'(min={df[col].min():.4f})'
                    )

    # 3. Water balance check: abs(balance_check) < 0.01 for rows except row 0
    if 'balance_check' in water_df.columns:
        tail = water_df['balance_check'].iloc[1:]
        bad = (tail.abs() >= 0.01).sum()
        if bad > 0:
            failures.append(
                f'Water balance_check >= 0.01 in {bad} rows '
                f'(max={tail.abs().max():.4f})'
            )

    # 4. Energy conservation (demand-fulfillment identity):
    #    renewable_consumed + generator + grid_import + battery_discharge + deficit
    #    == total_demand
    #
    #    Note: curtailed_kwh is excluded because it includes generator min-load
    #    excess (a source that generates curtailment, not a pure sink). The
    #    demand-fulfillment identity holds regardless of curtailment source.
    e = energy_df
    req_cols = ['renewable_consumed_kwh', 'total_demand_kwh']
    if all(c in e.columns for c in req_cols):
        supply = e['renewable_consumed_kwh'].copy()
        for col in ['generator_kwh', 'grid_import_kwh', 'battery_discharge_kwh']:
            if col in e.columns:
                supply = supply + e[col]
        if 'deficit_kwh' in e.columns:
            supply = supply + e['deficit_kwh']
        imbalance = (supply - e['total_demand_kwh']).abs()
        max_imbal = imbalance.max()
        if max_imbal > 1.0:   # 1 kWh tolerance per day
            failures.append(
                f'Energy conservation violated: max daily imbalance={max_imbal:.2f} kWh'
            )

    # 5. Date continuity
    if 'day' in energy_df.columns:
        dates = pd.to_datetime(energy_df['day'])
        gaps = dates.diff().iloc[1:]
        bad_gaps = (gaps != pd.Timedelta('1D')).sum()
        if bad_gaps > 0:
            failures.append(f'Date gaps in energy output: {bad_gaps} non-consecutive days')

    # 6. Battery SOC bounds (if battery present)
    with open(energy_system_path) as f:
        esys = yaml.safe_load(f)
    has_battery = esys.get('battery', {}).get('has_battery', False)
    if has_battery and 'battery_soc' in energy_df.columns:
        # Read SOC limits from policy template (baseline values)
        with open(ENERGY_POLICY_TEMPLATE) as f:
            pol = yaml.safe_load(f)
        soc_min = pol.get('battery', {}).get('soc_min', 0.0)
        soc_max = pol.get('battery', {}).get('soc_max', 1.0)
        soc = energy_df['battery_soc']
        if (soc < soc_min - 0.01).any():
            failures.append(
                f'Battery SOC below soc_min={soc_min}: min={soc.min():.3f}'
            )
        if (soc > soc_max + 0.01).any():
            failures.append(
                f'Battery SOC above soc_max={soc_max}: max={soc.max():.3f}'
            )

    return failures


def _key_metrics(energy_df):
    """Extract key comparison metrics from energy DataFrame."""
    def _sum(col):
        return float(energy_df[col].sum()) if col in energy_df.columns else None

    return dict(
        total_energy_cost=_sum('total_energy_cost'),
        total_grid_import_kwh=_sum('grid_import_kwh'),
        total_generator_kwh=_sum('generator_kwh'),
        total_renewable_kwh=_sum('total_renewable_kwh'),
        total_deficit_kwh=_sum('deficit_kwh'),
    )


def run_all():
    results = []

    for test in TESTS:
        for regime in REGIMES:
            dir_name = f"{test['dir_prefix']}_{regime}"
            test_dir = OUTPUT_BASE / dir_name
            results_dir = test_dir / 'results'
            label = f"{test['test_id']}_{regime}"

            print(f"\n--- {label}: {dir_name} ---")

            try:
                _setup_test_dir(test_dir, regime)
                energy_policy_path = test_dir / 'energy_policy.yaml'
                _build_energy_policy(
                    test['strategy'], energy_policy_path,
                    energy_system_path=test_dir / 'energy_system.yaml',
                )

                water_df, energy_df = run(
                    farm_profiles_path=test_dir / 'farm_profile.yaml',
                    water_systems_path=test_dir / 'water_systems.yaml',
                    water_policy_path=test_dir / 'water_policy.yaml',
                    community_config_path=COMMUNITY_DEMANDS,
                    energy_config_path=test_dir / 'energy_system.yaml',
                    energy_policy_path=energy_policy_path,
                    registry_path=REGISTRY,
                    output_dir=results_dir,
                )

                failures = _validate(
                    water_df, energy_df,
                    energy_system_path=test_dir / 'energy_system.yaml',
                )
                metrics = _key_metrics(energy_df)
                status = 'PASS' if not failures else 'FAIL'

            except Exception:
                failures = [traceback.format_exc()]
                metrics = {}
                status = 'ERROR'

            results.append(dict(
                test_name=dir_name,
                test_id=label,
                strategy=test['strategy'],
                regime=regime,
                status=status,
                failures=failures,
                metrics=metrics,
            ))

            if status == 'PASS':
                print(f"  PASS")
            else:
                print(f"  {status}")
                for f in failures:
                    print(f"    - {f}")

    return results


def _print_summary(results):
    print("\n" + "=" * 70)
    print("ENERGY STRATEGY STRESS TEST SUMMARY (E1/E2/E3)")
    print("=" * 70)

    header = f"{'Test':<48} {'Status':<8} {'Failures'}"
    print(header)
    print("-" * 70)

    for r in results:
        fail_str = str(len(r['failures'])) + ' failure(s)' if r['failures'] else 'none'
        print(f"{r['test_name']:<48} {r['status']:<8} {fail_str}")

    print("\n--- Key Metrics ---")
    metric_header = (
        f"{'Test':<48} {'Cost($)':<12} {'GridImp(kWh)':<15} "
        f"{'Gen(kWh)':<12} {'Renew(kWh)':<13} {'Deficit(kWh)'}"
    )
    print(metric_header)
    print("-" * 110)
    for r in results:
        m = r['metrics']
        cost = f"{m.get('total_energy_cost', 0) or 0:,.0f}" if m else 'N/A'
        grid = f"{m.get('total_grid_import_kwh', 0) or 0:,.0f}" if m else 'N/A'
        gen  = f"{m.get('total_generator_kwh', 0) or 0:,.0f}" if m else 'N/A'
        ren  = f"{m.get('total_renewable_kwh', 0) or 0:,.0f}" if m else 'N/A'
        defi = f"{m.get('total_deficit_kwh', 0) or 0:,.0f}" if m else 'N/A'
        print(
            f"{r['test_name']:<48} {cost:<12} {grid:<15} {gen:<12} {ren:<13} {defi}"
        )

    total = len(results)
    passed = sum(1 for r in results if r['status'] == 'PASS')
    print(f"\nTotal: {passed}/{total} passed")


if __name__ == '__main__':
    results = run_all()
    _print_summary(results)
