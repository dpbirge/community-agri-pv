# Layer 2 Fixes - Implementation Prompt

Complete the following fixes to finalize Layer 2 configuration before starting Layer 3 simulation.

---

## Task 1: Update Data Registry (Critical)

**File**: `settings/data_registry.yaml`

Add the 6 new equipment files that were created but not registered:

```yaml
# Add under equipment: section
equipment:
  pv_systems: data/parameters/equipment/pv_systems-toy.csv
  wind_turbines: data/parameters/equipment/wind_turbines-toy.csv
  batteries: data/parameters/equipment/batteries-toy.csv
  processing: data/parameters/equipment/processing_equipment-toy.csv
  failure_rates: data/parameters/equipment/equipment_failure_rates-toy.csv
  # ADD THESE:
  wells: data/parameters/equipment/wells-toy.csv
  irrigation_systems: data/parameters/equipment/irrigation_systems-toy.csv
  storage_systems: data/parameters/equipment/storage_systems-toy.csv
  generators: data/parameters/equipment/generators-toy.csv
  fresh_packaging: data/parameters/equipment/fresh_packaging-toy.csv
  processed_packaging: data/parameters/equipment/processed_packaging-toy.csv
```

**Verify**: Run `python settings/scripts/validation.py --registry` - should show all files found.

---

## Task 2: Implement Processing Validation (Critical)

**File**: `settings/scripts/calculations.py`

Replace the stub `validate_processing_capacity` function (lines 397-409) with actual validation:

```python
def validate_processing_capacity(processing_config, equipment_file_path: str = None) -> Dict[str, Any]:
    """Validate processing capacity against equipment capabilities.
    
    Args:
        processing_config: Processing configuration from scenario
        equipment_file_path: Path to equipment CSV (uses default if None)
    
    Returns:
        Dict with 'valid', 'warnings', 'errors' keys
    """
    if equipment_file_path is None:
        equipment_file_path = _get_project_root() / "data/parameters/equipment/processing_equipment-toy.csv"
    
    equipment_specs = _load_csv_with_metadata(equipment_file_path)
    
    warnings = []
    errors = []
    
    # Get max capacities from equipment file
    max_capacities = {}
    for _, row in equipment_specs.iterrows():
        eq_type = row["equipment_type"]
        max_capacities[eq_type] = row["capacity_kg_per_day"]
    
    # Check each processing type
    processing_checks = [
        ("drying", processing_config.drying.processing_capacity_kg_day, "dried"),
        ("canning", processing_config.canning.processing_capacity_kg_day, "canned"),
        ("packaging", processing_config.packaging.processing_capacity_kg_day, "packaged"),
    ]
    
    for name, config_capacity, eq_type in processing_checks:
        if eq_type in max_capacities:
            max_cap = max_capacities[eq_type]
            if config_capacity > max_cap * 2:
                warnings.append(f"{name} capacity ({config_capacity} kg/day) exceeds 2x equipment max ({max_cap} kg/day)")
    
    return {
        "valid": len(errors) == 0,
        "warnings": warnings,
        "errors": errors,
    }
```

---

## Task 3: Add Cross-Validation to validation.py (Critical)

**File**: `settings/scripts/validation.py`

Add these checks to the `validate_scenario` function after the existing validation code (before the final return):

```python
# Cross-validation checks
if "water_infrastructure" in scenario:
    water = scenario["water_infrastructure"]
    
    # Check treatment capacity vs well capacity
    if "groundwater_wells" in water and "water_treatment" in water:
        wells = water["groundwater_wells"]
        treatment = water["water_treatment"]
        
        total_well_capacity = wells.get("number_of_wells", 0) * wells.get("well_flow_rate_m3_day", 0)
        treatment_capacity = treatment.get("system_capacity_m3_day", 0)
        
        if treatment_capacity < total_well_capacity:
            errors.append(
                f"Water treatment capacity ({treatment_capacity} m³/day) is less than "
                f"total well capacity ({total_well_capacity} m³/day)"
            )
    
    # Check storage is reasonable for throughput
    if "irrigation_water_storage" in water and "water_treatment" in water:
        storage = water["irrigation_water_storage"]
        treatment = water["water_treatment"]
        
        storage_capacity = storage.get("capacity_m3", 0)
        daily_treatment = treatment.get("system_capacity_m3_day", 0)
        
        # Storage should hold at least 0.25 days of treatment output
        if storage_capacity < daily_treatment * 0.25:
            errors.append(
                f"Storage capacity ({storage_capacity} m³) is very small relative to "
                f"daily treatment ({daily_treatment} m³/day) - less than 6 hours buffer"
            )
```

---

## Task 4: Fix Household Demand Calculation (Medium)

**File**: `settings/scripts/calculations.py`

Update `calculate_household_demand` function (lines 440-464) to load from housing data:

```python
def calculate_household_demand(community_config, housing_data_path: str = None) -> Dict[str, float]:
    """Calculate household energy and water demand.
    
    Args:
        community_config: Community configuration
        housing_data_path: Path to housing CSV (uses default if None)
    
    Returns:
        Dict with total_energy_kwh_day, total_water_m3_day, etc.
    """
    population = community_config.population
    
    # Try to load housing data
    if housing_data_path is None:
        housing_data_path = _get_project_root() / "data/parameters/community/housing_energy_water-toy.csv"
    
    try:
        housing_data = _load_csv_with_metadata(housing_data_path)
        
        # Use weighted average from housing data
        total_occupants = housing_data["occupants_per_household"].sum()
        avg_energy = (housing_data["kwh_per_household_per_day"] * housing_data["occupants_per_household"]).sum() / total_occupants
        avg_water = (housing_data["m3_per_household_per_day"] * housing_data["occupants_per_household"]).sum() / total_occupants
        avg_household_size = total_occupants / len(housing_data)
        
        households = population / avg_household_size
        
        return {
            "households": households,
            "total_energy_kwh_day": households * avg_energy,
            "total_water_m3_day": households * avg_water,
            "energy_per_household_kwh_day": avg_energy,
            "water_per_household_m3_day": avg_water,
        }
    except Exception:
        # Fallback to hardcoded values if file not found
        households = population / 5
        return {
            "households": households,
            "total_energy_kwh_day": households * 8.0,
            "total_water_m3_day": population * 0.15,
            "energy_per_household_kwh_day": 8.0,
            "water_per_person_m3_day": 0.15,
        }
```

---

## Task 5: Document Distance Calculations (Medium)

**File**: `settings/scripts/calculations.py`

Update the docstring and add comments to `calculate_distances` function (lines 272-301) explaining the formulas:

```python
def calculate_distances(wells_config, treatment_config, farms) -> Dict[str, float]:
    """Calculate average distances between infrastructure components.
    
    Uses simplified geometric estimation assuming uniform distribution of
    infrastructure across the farm area. Formula based on expected distance
    between uniformly distributed points in a square region:
    
        E[d] = (0.52 * sqrt(A)) / sqrt(n)
    
    where A = area, n = number of points. Coefficients (0.3, 0.4) are adjusted
    for typical rural infrastructure placement patterns.
    
    Args:
        wells_config: Groundwater wells configuration
        treatment_config: Water treatment configuration  
        farms: List of farm objects
    
    Returns:
        Dict with average_well_to_treatment_km, average_treatment_to_farm_km, etc.
    """
    # ... rest of function unchanged
```

---

## Verification

After completing all tasks, run:

```bash
# 1. Verify registry
python settings/scripts/validation.py --registry

# 2. Verify scenario loads
python -c "from settings.scripts.loader import load_scenario; s = load_scenario('settings/scenarios/water_policy_testing.yaml'); print('Loader OK')"

# 3. Verify calculations
python -c "from settings.scripts.loader import load_scenario; from settings.scripts.calculations import calculate_infrastructure; s = load_scenario('settings/scenarios/water_policy_testing.yaml'); calc = calculate_infrastructure(s); print('Calculations OK:', list(calc.keys()))"

# 4. Verify full validation
python settings/scripts/validation.py settings/scenarios/water_policy_testing.yaml
```

All commands should pass without errors.

---

**End of Prompt**
