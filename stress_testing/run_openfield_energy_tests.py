# Run energy stress tests with the openfield-only farm profile.
# Removes agri-PV generation to create genuine energy-deficit scenarios.

import sys
from pathlib import Path

repo = Path('/Users/dpbirge/GITHUB/community-agri-pv')
sys.path.insert(0, str(repo))

from stress_testing.run_test import run
import pandas as pd

ST = repo / 'stress_testing'
BL = ST / 'baseline'
SETTINGS = repo / 'settings'

FARM_OPENFIELD = BL / 'farm_profile_openfield.yaml'
WATER_BALANCED = BL / 'water_systems_balanced.yaml'
WATER_POLICY = SETTINGS / 'water_policy_base.yaml'
COMMUNITY = BL / 'community_demands.yaml'
REGISTRY = SETTINGS / 'data_registry_base.yaml'

# Reuse existing test-specific configs where they already exist
E1_DIR = ST / 'energy_01_minimize_cost_balanced'
E9_DIR = ST / 'energy_09_off_grid'
E12_DIR = ST / 'energy_12_no_battery_no_generator'

TESTS = {
    'E1_openfield': {
        'energy_config': E1_DIR / 'energy_system.yaml',
        'energy_policy': E1_DIR / 'energy_policy.yaml',
        'water_systems': E1_DIR / 'water_systems.yaml',
        'water_policy': E1_DIR / 'water_policy.yaml',
    },
    'E9_openfield': {
        'energy_config': E9_DIR / 'energy_system.yaml',
        'energy_policy': E9_DIR / 'energy_policy.yaml',
        'water_systems': E9_DIR / 'water_systems.yaml',
        'water_policy': E9_DIR / 'water_policy.yaml',
    },
    'E12_openfield': {
        'energy_config': E12_DIR / 'energy_system.yaml',
        'energy_policy': E12_DIR / 'energy_policy.yaml',
        'water_systems': E12_DIR / 'water_systems.yaml',
        'water_policy': E12_DIR / 'water_policy.yaml',
    },
    'ES_balanced_openfield': {
        'energy_config': BL / 'energy_system_balanced.yaml',
        'energy_policy': SETTINGS / 'energy_policy_base.yaml',
        'water_systems': WATER_BALANCED,
        'water_policy': WATER_POLICY,
    },
}


def summarize(name, energy_df):
    """Print key energy metrics for one test."""
    total_renewable = energy_df['total_renewable_kwh'].sum()
    total_demand = energy_df['total_demand_kwh'].sum()
    grid_import = energy_df['grid_import_kwh'].sum()
    generator = energy_df['generator_kwh'].sum()
    deficit = energy_df['deficit_kwh'].sum()
    curtailed = energy_df['curtailed_kwh'].sum()
    battery_charge = energy_df['battery_charge_kwh'].sum()
    battery_discharge = energy_df['battery_discharge_kwh'].sum()
    grid_export = energy_df['grid_export_kwh'].sum()

    deficit_days = (energy_df['deficit_kwh'] > 0).sum()
    generator_days = (energy_df['generator_kwh'] > 0).sum()
    grid_import_days = (energy_df['grid_import_kwh'] > 0).sum()

    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    print(f"  Total demand:          {total_demand:>14,.1f} kWh")
    print(f"  Total renewable:       {total_renewable:>14,.1f} kWh")
    print(f"  Renewable/Demand:      {total_renewable/total_demand:>14.2%}")
    print(f"  Grid import:           {grid_import:>14,.1f} kWh  ({grid_import_days} days)")
    print(f"  Grid export:           {grid_export:>14,.1f} kWh")
    print(f"  Generator:             {generator:>14,.1f} kWh  ({generator_days} days)")
    print(f"  Battery charge:        {battery_charge:>14,.1f} kWh")
    print(f"  Battery discharge:     {battery_discharge:>14,.1f} kWh")
    print(f"  Curtailed:             {curtailed:>14,.1f} kWh")
    print(f"  Deficit:               {deficit:>14,.1f} kWh  ({deficit_days} days)")
    print(f"{'='*60}")
    return {
        'test': name,
        'total_demand_kwh': total_demand,
        'total_renewable_kwh': total_renewable,
        'renewable_demand_ratio': total_renewable / total_demand,
        'grid_import_kwh': grid_import,
        'grid_import_days': grid_import_days,
        'grid_export_kwh': grid_export,
        'generator_kwh': generator,
        'generator_days': generator_days,
        'battery_charge_kwh': battery_charge,
        'battery_discharge_kwh': battery_discharge,
        'curtailed_kwh': curtailed,
        'deficit_kwh': deficit,
        'deficit_days': deficit_days,
    }


results = []
for name, cfg in TESTS.items():
    out_dir = ST / 'results' / name
    print(f"\n>>> Running {name} ...")
    water_df, energy_df = run(
        farm_profiles_path=FARM_OPENFIELD,
        water_systems_path=cfg['water_systems'],
        water_policy_path=cfg['water_policy'],
        community_config_path=COMMUNITY,
        energy_config_path=cfg['energy_config'],
        energy_policy_path=cfg['energy_policy'],
        registry_path=REGISTRY,
        output_dir=out_dir,
    )
    row = summarize(name, energy_df)
    results.append(row)

print("\n\n" + "="*80)
print("  SUMMARY TABLE — Openfield Energy Stress Tests")
print("="*80)
summary_df = pd.DataFrame(results)
print(summary_df.to_string(index=False))
print()
