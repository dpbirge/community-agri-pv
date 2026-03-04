"""Run all cross-system stress tests X1-X5."""
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from stress_testing.run_test import run

BASELINE = _repo_root / 'stress_testing' / 'baseline'
TESTS = _repo_root / 'stress_testing' / 'individual_tests'
REGISTRY = _repo_root / 'settings' / 'data_registry_base.yaml'
COMMUNITY = BASELINE / 'community_demands.yaml'
WATER_POLICY_BASE = _repo_root / 'settings' / 'water_policy_base.yaml'
ENERGY_POLICY_BASE = _repo_root / 'settings' / 'energy_policy_base.yaml'


def run_x1():
    t = TESTS / 'cross_01_water_energy_coupling'
    return run(
        farm_profiles_path=BASELINE / 'farm_profile_openfield.yaml',
        water_systems_path=t / 'water_systems.yaml',
        water_policy_path=t / 'water_policy.yaml',
        community_config_path=COMMUNITY,
        energy_config_path=t / 'energy_system.yaml',
        energy_policy_path=t / 'energy_policy.yaml',
        registry_path=REGISTRY,
        output_dir=t / 'results',
    )


def run_x2():
    t = TESTS / 'cross_02_oversupply_both'
    return run(
        farm_profiles_path=BASELINE / 'farm_profile_heavy_pv.yaml',
        water_systems_path=t / 'water_systems.yaml',
        water_policy_path=t / 'water_policy.yaml',
        community_config_path=COMMUNITY,
        energy_config_path=t / 'energy_system.yaml',
        energy_policy_path=t / 'energy_policy.yaml',
        registry_path=REGISTRY,
        output_dir=t / 'results',
    )


def run_x3():
    t = TESTS / 'cross_03_undersupply_both'
    return run(
        farm_profiles_path=BASELINE / 'farm_profile_openfield.yaml',
        water_systems_path=t / 'water_systems.yaml',
        water_policy_path=t / 'water_policy.yaml',
        community_config_path=COMMUNITY,
        energy_config_path=t / 'energy_system.yaml',
        energy_policy_path=t / 'energy_policy.yaml',
        registry_path=REGISTRY,
        output_dir=t / 'results',
    )


def run_x4():
    t = TESTS / 'cross_04_no_treatment_solar_only'
    return run(
        farm_profiles_path=BASELINE / 'farm_profile_mixed.yaml',
        water_systems_path=t / 'water_systems.yaml',
        water_policy_path=t / 'water_policy.yaml',
        community_config_path=COMMUNITY,
        energy_config_path=t / 'energy_system.yaml',
        energy_policy_path=t / 'energy_policy.yaml',
        registry_path=REGISTRY,
        output_dir=t / 'results',
    )


def run_x5():
    t = TESTS / 'cross_05_huge_farm_minimal_infra'
    return run(
        farm_profiles_path=t / 'farm_profile.yaml',
        water_systems_path=t / 'water_systems.yaml',
        water_policy_path=t / 'water_policy.yaml',
        community_config_path=COMMUNITY,
        energy_config_path=t / 'energy_system.yaml',
        energy_policy_path=t / 'energy_policy.yaml',
        registry_path=REGISTRY,
        output_dir=t / 'results',
    )


if __name__ == '__main__':
    tests = [
        ('X1', 'cross_01_water_energy_coupling', run_x1),
        ('X2', 'cross_02_oversupply_both', run_x2),
        ('X3', 'cross_03_undersupply_both', run_x3),
        ('X4', 'cross_04_no_treatment_solar_only', run_x4),
        ('X5', 'cross_05_huge_farm_minimal_infra', run_x5),
    ]
    for test_id, test_name, runner in tests:
        print(f"\n{'='*60}")
        print(f"Running {test_id}: {test_name}")
        print('='*60)
        try:
            water_df, energy_df = runner()
            print(f"  PASSED — water rows={len(water_df)}, energy rows={len(energy_df)}")
        except Exception as e:
            print(f"  FAILED — {type(e).__name__}: {e}")
    print("\nAll cross tests complete.")
