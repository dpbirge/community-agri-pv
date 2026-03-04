"""Run ES1–ES5 energy system stress tests and print per-test results."""
import sys
from pathlib import Path

repo = Path(__file__).resolve().parent.parent
if str(repo) not in sys.path:
    sys.path.insert(0, str(repo))

from stress_testing.run_test import run

REGISTRY = repo / 'settings' / 'data_registry_base.yaml'
COMMUNITY = repo / 'stress_testing' / 'baseline' / 'community_demands.yaml'
BASE = repo / 'stress_testing' / 'individual_tests'

TESTS = [
    'es_01_solar_only',
    'es_02_wind_only',
    'es_03_minimal_solar',
    'es_04_large_solar',
    'es_05_single_small_turbine',
]

for test_name in TESTS:
    td = BASE / test_name
    print(f'\n=== Running {test_name} ===')
    try:
        water_df, energy_df = run(
            farm_profiles_path=td / 'farm_profile.yaml',
            water_systems_path=td / 'water_systems.yaml',
            water_policy_path=td / 'water_policy.yaml',
            community_config_path=COMMUNITY,
            energy_config_path=td / 'energy_system.yaml',
            energy_policy_path=td / 'energy_policy.yaml',
            registry_path=REGISTRY,
            output_dir=td / 'results',
        )
        print(f'  PASS — rows: {len(energy_df)}')
        print(f'  Columns: {list(energy_df.columns)}')
    except Exception as e:
        print(f'  FAIL — {type(e).__name__}: {e}')

print('\nAll tests complete.')
