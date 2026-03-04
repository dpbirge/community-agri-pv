"""Run FP1-FP8 farm profile stress tests."""
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from stress_testing.run_test import run

REGISTRY = _repo_root / 'settings' / 'data_registry_base.yaml'
TESTS = _repo_root / 'stress_testing' / 'individual_tests'


def _run(test_dir, farm_profile=None):
    d = TESTS / test_dir
    fp = Path(farm_profile) if farm_profile else d / 'farm_profile.yaml'
    return run(
        farm_profiles_path=fp,
        water_systems_path=d / 'water_systems.yaml',
        water_policy_path=d / 'water_policy.yaml',
        community_config_path=d / 'community_demands.yaml',
        energy_config_path=d / 'energy_system.yaml',
        energy_policy_path=d / 'energy_policy.yaml',
        registry_path=REGISTRY,
        output_dir=d / 'results',
    )


tests = [
    'fp_01_all_openfield',
    'fp_02_all_underpv_high',
    'fp_03_mixed_pv_densities',
    'fp_04_small_drip_no_pv',
    'fp_05_large_furrow_high_demand',
    'fp_06_single_field_underpv_high',
    'fp_07_many_small_fields',
]

for t in tests:
    print(f"\n{'='*60}\nRunning {t}\n{'='*60}")
    try:
        _run(t)
        print(f"PASSED: {t}")
    except Exception as e:
        print(f"FAILED: {t} — {e}")
        import traceback; traceback.print_exc()

# FP8 — two sub-tests
for subdir in ['openfield', 'heavy_pv']:
    tag = f'fp_08_pv_vs_openfield_comparison/{subdir}'
    d = TESTS / 'fp_08_pv_vs_openfield_comparison' / subdir
    print(f"\n{'='*60}\nRunning fp_08/{subdir}\n{'='*60}")
    try:
        run(
            farm_profiles_path=d / 'farm_profile.yaml',
            water_systems_path=d / 'water_systems.yaml',
            water_policy_path=d / 'water_policy.yaml',
            community_config_path=d / 'community_demands.yaml',
            energy_config_path=d / 'energy_system.yaml',
            energy_policy_path=d / 'energy_policy.yaml',
            registry_path=REGISTRY,
            output_dir=d / 'results',
        )
        print(f"PASSED: fp_08/{subdir}")
    except Exception as e:
        print(f"FAILED: fp_08/{subdir} — {e}")
        import traceback; traceback.print_exc()

print("\nAll FP tests complete.")
