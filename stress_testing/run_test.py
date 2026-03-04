"""Run water + energy simulation with the given settings files.

Shared runner for stress testing. Each test calls run() with paths to its own
settings files and an output directory. Results are saved as CSVs.
"""
import sys
from pathlib import Path

# Ensure repo root is on sys.path so `from src.*` imports work
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from src.water_balance import compute_daily_water_balance, save_daily_water_balance
from src.energy_balance import compute_daily_energy_balance, save_energy_balance


def run(*, farm_profiles_path, water_systems_path, water_policy_path,
        community_config_path, energy_config_path, energy_policy_path,
        registry_path, output_dir):
    """Run full water + energy simulation and save results.

    Args:
        farm_profiles_path: Path to farm_profile.yaml
        water_systems_path: Path to water_systems.yaml
        water_policy_path: Path to water_policy.yaml
        community_config_path: Path to community_demands.yaml
        energy_config_path: Path to energy_system.yaml
        energy_policy_path: Path to energy_policy.yaml
        registry_path: Path to data_registry_base.yaml
        output_dir: Directory for output CSVs

    Returns:
        Tuple of (water_df, energy_df) DataFrames.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    water_df = compute_daily_water_balance(
        farm_profiles_path=farm_profiles_path,
        water_systems_path=water_systems_path,
        water_policy_path=water_policy_path,
        community_config_path=community_config_path,
        registry_path=registry_path,
    )
    save_daily_water_balance(water_df, output_dir=output_dir)

    energy_df = compute_daily_energy_balance(
        energy_config_path=energy_config_path,
        energy_policy_path=energy_policy_path,
        community_config_path=community_config_path,
        farm_profiles_path=farm_profiles_path,
        registry_path=registry_path,
        water_balance_df=water_df,
    )
    save_energy_balance(energy_df, output_dir=output_dir)

    return water_df, energy_df


if __name__ == '__main__':
    # Quick smoke test with baseline settings
    root = _repo_root
    st = root / 'stress_testing' / 'baseline'
    run(
        farm_profiles_path=st / 'farm_profile.yaml',
        water_systems_path=st / 'water_systems_oversupply.yaml',
        water_policy_path=root / 'settings' / 'water_policy_base.yaml',
        community_config_path=st / 'community_demands.yaml',
        energy_config_path=st / 'energy_system_oversupply.yaml',
        energy_policy_path=root / 'settings' / 'energy_policy_base.yaml',
        registry_path=root / 'settings' / 'data_registry_base.yaml',
        output_dir=st / 'results',
    )
    print("Baseline smoke test complete.")
