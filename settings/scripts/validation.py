# Validation for Community Agri-PV simulation settings
# Layer 2: Design configuration
#
# Validates:
#   - Data registry: all referenced files exist
#   - Scenarios: valid YAML syntax and policy references

import os
import yaml
from pathlib import Path


def _get_project_root():
    """Get project root directory (parent of settings/)."""
    return Path(__file__).parent.parent.parent


def _extract_paths_from_dict(obj, paths=None):
    """Recursively extract all file paths from nested dict."""
    if paths is None:
        paths = []

    if isinstance(obj, dict):
        for v in obj.values():
            _extract_paths_from_dict(v, paths)
    elif isinstance(obj, str):
        if obj.endswith(".csv") or obj.endswith(".yaml"):
            paths.append(obj)

    return paths


def validate_registry(registry_path="settings/data_registry.yaml"):
    """Validate that all files in the data registry exist.

    Args:
        registry_path: Path to registry YAML (relative to project root)

    Returns:
        Dict with 'valid', 'missing', 'found', 'total' keys
    """
    project_root = _get_project_root()
    full_path = project_root / registry_path

    if not full_path.exists():
        return {
            "valid": False,
            "missing": [f"Registry not found: {registry_path}"],
            "found": [],
            "total": 0,
        }

    with open(full_path, "r") as f:
        registry = yaml.safe_load(f)

    paths = _extract_paths_from_dict(registry)
    missing = []
    found = []

    for file_path in paths:
        if (project_root / file_path).exists():
            found.append(file_path)
        else:
            missing.append(file_path)

    return {
        "valid": len(missing) == 0,
        "missing": missing,
        "found": found,
        "total": len(paths),
    }


def validate_scenario(scenario_path):
    """Validate scenario YAML syntax and structure.

    Args:
        scenario_path: Path to scenario YAML (relative or absolute)

    Returns:
        Dict with 'valid', 'errors' keys
    """
    project_root = _get_project_root()
    full_path = Path(scenario_path)
    if not full_path.is_absolute():
        full_path = project_root / scenario_path

    errors = []
    warnings = []

    if not full_path.exists():
        return {"valid": False, "errors": [f"Scenario not found: {scenario_path}"]}

    try:
        with open(full_path, "r") as f:
            scenario = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return {"valid": False, "errors": [f"YAML parse error: {e}"]}

    # Check required sections
    required = ["scenario", "simulation", "energy_infrastructure", "water_infrastructure", "food_processing_infrastructure", "community_structure", "economics"]
    for section in required:
        if section not in scenario:
            errors.append(f"Missing required section: {section}")

    # Check energy infrastructure sections
    if "energy_infrastructure" in scenario:
        energy_infra = scenario["energy_infrastructure"]
        required_energy = ["pv", "wind", "battery", "backup_generator"]
        for section in required_energy:
            if section not in energy_infra:
                errors.append(f"Missing required energy_infrastructure section: {section}")
        
        # Validate PV configuration
        if "pv" in energy_infra:
            pv = energy_infra["pv"]
            if "percent_over_crops" in pv:
                pct = pv["percent_over_crops"]
                if not (0 <= pct <= 1):
                    errors.append(f"PV percent_over_crops must be between 0 and 1, got {pct}")
                if "density" in pv:
                    density = pv["density"]
                    density_coverage = {"low": 0.30, "medium": 0.50, "high": 0.80}.get(density, 0.50)
                    if density_coverage * pct > 1.0:
                        errors.append(f"PV density × percent_over_crops ({density_coverage} × {pct} = {density_coverage * pct}) must be ≤ 1.0")

    # Check water infrastructure sections
    if "water_infrastructure" in scenario:
        water_infra = scenario["water_infrastructure"]
        required_water = ["groundwater_wells", "water_treatment", "irrigation_water_storage", "irrigation_system"]
        for section in required_water:
            if section not in water_infra:
                errors.append(f"Missing required water_infrastructure section: {section}")
        
        # Validate wells
        if "groundwater_wells" in water_infra:
            wells = water_infra["groundwater_wells"]
            if "number_of_wells" in wells and wells["number_of_wells"] <= 0:
                errors.append(f"groundwater_wells.number_of_wells must be > 0, got {wells['number_of_wells']}")
        
        # Validate water treatment
        if "water_treatment" in water_infra:
            treatment = water_infra["water_treatment"]
            if "number_of_units" in treatment and treatment["number_of_units"] <= 0:
                errors.append(f"water_treatment.number_of_units must be > 0, got {treatment['number_of_units']}")

    # Check food processing infrastructure sections
    if "food_processing_infrastructure" in scenario:
        food_infra = scenario["food_processing_infrastructure"]
        required_food = ["fresh_food_packaging", "drying", "canning", "packaging"]
        for section in required_food:
            if section not in food_infra:
                errors.append(f"Missing required food_processing_infrastructure section: {section}")

        # Validate equipment lists
        for section in required_food:
            if section in food_infra:
                proc = food_infra[section]
                if "equipment" not in proc:
                    errors.append(f"{section} missing required 'equipment' list")
                else:
                    equipment_list = proc["equipment"]
                    if not equipment_list:
                        errors.append(f"{section}.equipment list cannot be empty")
                    else:
                        total_fraction = 0.0
                        for i, eq in enumerate(equipment_list):
                            if "type" not in eq:
                                errors.append(f"{section}.equipment[{i}] missing 'type'")
                            if "fraction" not in eq:
                                errors.append(f"{section}.equipment[{i}] missing 'fraction'")
                            else:
                                total_fraction += eq.get("fraction", 0)
                        if abs(total_fraction - 1.0) > 0.01:
                            errors.append(f"{section}.equipment fractions must sum to 1.0, got {total_fraction}")

    # Check farms have policies
    if "community_structure" in scenario and "farms" in scenario["community_structure"]:
        for i, farm in enumerate(scenario["community_structure"]["farms"]):
            if "policies" not in farm:
                errors.append(f"Farm {i+1} missing 'policies' section")

    # Cross-validation checks (warnings, not errors - these are capacity mismatches)
    if "water_infrastructure" in scenario:
        water = scenario["water_infrastructure"]

        # Check treatment capacity vs well capacity
        if "groundwater_wells" in water and "water_treatment" in water:
            wells = water["groundwater_wells"]
            treatment = water["water_treatment"]

            total_well_capacity = wells.get("number_of_wells", 0) * wells.get("well_flow_rate_m3_day", 0)
            treatment_capacity = treatment.get("system_capacity_m3_day", 0)

            # Warning 1: Treatment undersized vs simultaneous well operation
            if treatment_capacity < total_well_capacity * 0.5:
                warnings.append(
                    f"Treatment capacity ({treatment_capacity} m³/day) is less than 50% of "
                    f"total well capacity ({total_well_capacity} m³/day). Treatment may bottleneck."
                )

            # Warning 2: Treatment heavily oversized
            if treatment_capacity > total_well_capacity * 2:
                warnings.append(
                    f"Treatment capacity ({treatment_capacity} m³/day) is more than 2x "
                    f"total well capacity ({total_well_capacity} m³/day). Consider smaller treatment."
                )

        # Check storage is reasonable for throughput
        if "irrigation_water_storage" in water and "water_treatment" in water:
            storage = water["irrigation_water_storage"]
            treatment = water["water_treatment"]

            storage_capacity = storage.get("capacity_m3", 0)
            daily_treatment = treatment.get("system_capacity_m3_day", 0)

            # Warning 3: Storage too small for treatment throughput
            if storage_capacity < daily_treatment * 0.25:
                warnings.append(
                    f"Storage ({storage_capacity} m³) provides less than 6 hours buffer "
                    f"for treatment throughput ({daily_treatment} m³/day)."
                )

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


def validate_all():
    """Validate registry and all scenarios.

    Returns:
        Dict with overall status and per-file results
    """
    project_root = _get_project_root()
    results = {"registry": None, "scenarios": {}}

    # Validate registry
    results["registry"] = validate_registry()

    # Validate all scenarios
    scenarios_dir = project_root / "settings" / "scenarios"
    if scenarios_dir.exists():
        for f in scenarios_dir.glob("*.yaml"):
            rel_path = f.relative_to(project_root)
            results["scenarios"][str(rel_path)] = validate_scenario(str(rel_path))

    # Overall status
    all_valid = results["registry"]["valid"]
    for scenario_result in results["scenarios"].values():
        all_valid = all_valid and scenario_result["valid"]

    results["all_valid"] = all_valid
    return results


def load_registry():
    """Load the data registry as a dict.

    Returns:
        Dict with all data paths organized by category
    """
    project_root = _get_project_root()
    registry_path = project_root / "settings" / "data_registry.yaml"

    with open(registry_path, "r") as f:
        return yaml.safe_load(f)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--registry":
        result = validate_registry()
        print("Data Registry Validation")
        print("=" * 40)
        print(f"Total files: {result['total']}")
        print(f"Found: {len(result['found'])}")
        print(f"Missing: {len(result['missing'])}")
        if result["missing"]:
            print("\nMissing files:")
            for f in result["missing"]:
                print(f"  - {f}")
        else:
            print("\nAll data files found.")
        sys.exit(0 if result["valid"] else 1)

    elif len(sys.argv) > 1 and sys.argv[1] != "--all":
        result = validate_scenario(sys.argv[1])
        print(f"Scenario: {sys.argv[1]}")
        print("=" * 40)
        if result["valid"]:
            print("Valid")
        else:
            print("Errors:")
            for e in result["errors"]:
                print(f"  - {e}")
        if result.get("warnings"):
            print("\nWarnings:")
            for w in result["warnings"]:
                print(f"  - {w}")
        sys.exit(0 if result["valid"] else 1)

    else:
        results = validate_all()
        print("Full Validation")
        print("=" * 40)

        print(f"\nRegistry: {'PASS' if results['registry']['valid'] else 'FAIL'}")
        print(f"  Files: {len(results['registry']['found'])}/{results['registry']['total']}")

        print("\nScenarios:")
        for name, result in results["scenarios"].items():
            status = "PASS" if result["valid"] else "FAIL"
            print(f"  {name}: {status}")
            if not result["valid"]:
                for e in result["errors"]:
                    print(f"    - {e}")
            if result.get("warnings"):
                for w in result["warnings"]:
                    print(f"    [WARN] {w}")

        print(f"\nOverall: {'PASS' if results['all_valid'] else 'FAIL'}")
        sys.exit(0 if results["all_valid"] else 1)
