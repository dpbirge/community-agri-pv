# Layer 2 Fixes Implementation Plan

**STATUS: Reference Document (Layer 2 Complete)**

Layer 2 configuration system is functional and validated. This document served as the implementation roadmap during Layer 2 development. Issues documented here have been addressed.

---

Based on code review findings and user feedback. This plan addresses bugs, data inconsistencies, and improvements identified before Layer 3 development.

---

## Task Overview

| # | Task | Priority | Complexity |
|---|------|----------|------------|
| 1 | Fix processing equipment type mismatch | High | Medium |
| 2 | Fix battery empty filter IndexError | High | Low |
| 3 | Add `economics` to validation required sections | High | Low |
| 4 | Add battery units > 0 validation in loader | High | Low |
| 5 | Remove dead code and unused parameters | Medium | Low |
| 6 | Fix all silent failures | High | Medium |
| 7 | Improve well/treatment cross-validation warnings | Medium | Low |
| 8 | Replace well pumping lookup with engineering calculation | High | Medium |
| 9 | Simplify battery calculations | Medium | Medium |
| 10 | Create seasonal household energy/water files | Medium | Medium |
| 11 | Replace hardcoded paths with registry lookups | High | Medium |

---

## Task 1: Fix Processing Equipment Type Mismatch

### Problem
Code expects `equipment_type` values `"dried"`, `"canned"`, `"packaged"` but CSV has specific equipment names like `"solar_tunnel_dryer"`. Additionally, YAML currently duplicates values that should come from CSV.

### Design Principle
- **YAML** specifies which machinery (or mix of machinery) is used for each processing category
- **CSV** specifies the equipment specifications (labor, energy, costs, capacity)
- **Code** looks up values from CSV based on YAML equipment selection

### Solution

**1.1 Update `processing_equipment-toy.csv`** - Add `category` column:

```csv
category,equipment_type,capacity_kg_per_day,energy_kw_continuous,labor_hours_per_kg,capital_cost_usd,maintenance_cost_per_year_usd,lifespan_years
packaging,packaged,5000,8,0.05,45000,2500,15
drying,solar_drying_rack,800,0,0.15,5000,200,10
drying,simple_dehydrator,1200,12,0.10,18000,1200,12
drying,solar_tunnel_dryer,1500,2,0.08,25000,1500,15
canning,manual_canning_line,1500,8,0.12,35000,2000,15
canning,simple_retort,2000,18,0.10,55000,3500,18
canning,pressure_canner,2500,25,0.08,85000,5500,20
fresh_packaging,washing_sorting_line,3000,5,0.06,30000,1800,12
fresh_packaging,cold_storage_packing,2000,15,0.08,50000,3000,15
```

**1.2 Update `water_policy_testing.yaml`** - Specify equipment mix:

```yaml
food_processing_infrastructure:
  fresh_food_packaging:
    equipment:
      - type: washing_sorting_line
        fraction: 1.0
    storage_capacity_kg_total: 20000
    shelf_life_days: 3

  drying:
    equipment:
      - type: solar_tunnel_dryer
        fraction: 0.6
      - type: simple_dehydrator
        fraction: 0.4
    storage_capacity_kg_total: 20000
    shelf_life_days: 180

  canning:
    equipment:
      - type: simple_retort
        fraction: 1.0
    storage_capacity_kg_total: 20000
    shelf_life_days: 365

  packaging:
    equipment:
      - type: packaged
        fraction: 1.0
    storage_capacity_kg_total: 20000
    shelf_life_days: 14
```

**1.3 Update `loader.py`**:
- Create new dataclass `ProcessingEquipmentConfig` with `type` and `fraction` fields
- Update processing config dataclasses to use `equipment: list[ProcessingEquipmentConfig]`
- Remove `energy_kwh_per_kg`, `labor_hours_per_kg`, `additional_cost_per_kg`, `processing_capacity_kg_day` from YAML (looked up from CSV)
- Keep `storage_capacity_kg_total` and `shelf_life_days` in YAML (scenario-specific)

**1.4 Update `calculations.py`**:
- Look up each equipment type from CSV by `equipment_type` column
- Validate that equipment category matches processing category (e.g., can't use canning equipment for drying)
- Calculate weighted averages for mixed equipment:
  - `total_capacity = sum(equipment_capacity * fraction)`
  - `weighted_energy = sum(energy_kw * fraction)`
  - `weighted_labor = sum(labor_hours_per_kg * fraction)`
- Raise error if equipment type not found (no silent failures)

**1.5 Update `validate_processing_capacity`**:
- Validate equipment types exist in CSV
- Validate fractions sum to 1.0 for each processing category
- Validate category matches

### Files Modified
- `data/parameters/equipment/processing_equipment-toy.csv`
- `settings/scenarios/water_policy_testing.yaml`
- `settings/scripts/loader.py`
- `settings/scripts/calculations.py`
- `settings/scripts/validation.py`

---

## Task 2: Fix Battery Empty Filter IndexError

### Problem
`battery_row[size_filter].iloc[0]` raises unhelpful IndexError if no batteries match the size filter.

### Solution
Add explicit check before indexing:

```python
filtered = battery_row[size_filter]
if filtered.empty:
    raise ValueError(
        f"No {battery_config.chemistry} battery found for capacity "
        f"{battery_config.sys_capacity_kwh} kWh. Available sizes: small (<200), "
        f"medium (200-500), large (>500)"
    )
battery_data = filtered.iloc[0]
```

### Files Modified
- `settings/scripts/calculations.py` (line ~152)

---

## Task 3: Add `economics` to Validation Required Sections

### Problem
`economics` section is required by loader.py but not validated.

### Solution
Update line 100 in validation.py:

```python
required = ["scenario", "simulation", "energy_infrastructure", "water_infrastructure",
            "food_processing_infrastructure", "community_structure", "economics"]
```

### Files Modified
- `settings/scripts/validation.py` (line 100)

---

## Task 4: Add Battery Units > 0 Validation

### Problem
`battery_config.units` could be 0, causing division by zero in calculations.

### Solution
Add validation in `_load_infrastructure()` in loader.py:

```python
battery_units = _require(battery, "units", "energy_infrastructure.battery")
if battery_units <= 0:
    raise ValueError(f"battery.units must be > 0, got {battery_units}")
```

### Files Modified
- `settings/scripts/loader.py` (in `_load_infrastructure` function)

---

## Task 5: Remove Dead Code and Unused Parameters

### Items to Remove

**5.1 calculations.py line 190-192** - Dead `if gen_row.empty` check:
```python
# Remove these lines - argsort always returns rows if DataFrame non-empty
if gen_row.empty:
    raise ValueError(f"Generator capacity {gen_config.capacity_kw} kW not found")
```

**5.2 calculations.py line 315** - Unused `weather_data` parameter:
```python
# Change from:
def calculate_storage_evaporation(capacity_m3: float, storage_type: str, weather_data: pd.DataFrame = None) -> Dict[str, float]:
# To:
def calculate_storage_evaporation(capacity_m3: float, storage_type: str) -> Dict[str, float]:
```

### Files Modified
- `settings/scripts/calculations.py`

---

## Task 6: Fix All Silent Failures

### Problem
Several places catch exceptions or skip processing without raising errors.

### Locations to Fix

**6.1 calculations.py line 514** - `calculate_household_demand` has `except Exception` fallback:
```python
except Exception:
    # Fallback to hardcoded values if file not found
```
Change to: Raise explicit error, no silent fallback.

**6.2 calculations.py `validate_processing_capacity`** - Silent skip when equipment type not found:
```python
if eq_type in max_capacities:  # Silently skips if not found
```
Change to: Raise error if expected type not in CSV.

**6.3 Any other try/except blocks** - Audit and remove graceful fallbacks per CLAUDE.md guidelines.

### Files Modified
- `settings/scripts/calculations.py`

---

## Task 7: Improve Well/Treatment Cross-Validation Warnings

### Problem
Current check `treatment_capacity < total_well_capacity` may give false positives.

### Solution
Replace single check with multiple informative warnings:

```python
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

# Warning 3: Storage too small for treatment throughput
if storage_capacity < daily_treatment * 0.25:
    warnings.append(
        f"Storage ({storage_capacity} m³) provides less than 6 hours buffer "
        f"for treatment throughput ({daily_treatment} m³/day)."
    )
```

### Files Modified
- `settings/scripts/validation.py`

---

## Task 8: Replace Well Pumping Lookup with Engineering Calculation

### Problem
Current lookup uses arbitrary weighting formula that makes flow rate irrelevant.

### Solution
Calculate pumping energy from first principles:

```python
def calculate_pumping_energy(
    well_depth_m: float,
    flow_rate_m3_day: float,
    horizontal_distance_km: float,
    pipe_diameter_m: float = 0.1,
    pump_efficiency: float = 0.60
) -> Dict[str, float]:
    """Calculate pumping energy using hydraulic engineering principles.

    Energy components:
    1. Lift energy: E_lift = (ρgh) / (η × 3.6e6) kWh/m³
       - ρ = water density (~1025 kg/m³ for brackish)
       - g = 9.81 m/s²
       - h = total head (m)
       - η = pump efficiency

    2. Friction losses: Darcy-Weisbach equation for horizontal pipe flow
       - Head loss = f × (L/D) × (v²/2g)
       - f = friction factor (~0.02 for PVC pipes)
    """
    WATER_DENSITY = 1025  # kg/m³ (brackish)
    GRAVITY = 9.81  # m/s²
    FRICTION_FACTOR = 0.02  # PVC pipe

    # Vertical lift energy (well to surface)
    lift_head_m = well_depth_m
    lift_energy_kwh_per_m3 = (WATER_DENSITY * GRAVITY * lift_head_m) / (pump_efficiency * 3.6e6)

    # Horizontal friction losses
    velocity_m_s = (flow_rate_m3_day / 86400) / (3.14159 * (pipe_diameter_m/2)**2)
    friction_head_m = FRICTION_FACTOR * (horizontal_distance_km * 1000 / pipe_diameter_m) * (velocity_m_s**2 / (2 * GRAVITY))
    friction_energy_kwh_per_m3 = (WATER_DENSITY * GRAVITY * friction_head_m) / (pump_efficiency * 3.6e6)

    return {
        "lift_energy_kwh_per_m3": lift_energy_kwh_per_m3,
        "friction_energy_kwh_per_m3": friction_energy_kwh_per_m3,
        "total_pumping_energy_kwh_per_m3": lift_energy_kwh_per_m3 + friction_energy_kwh_per_m3,
        "lift_head_m": lift_head_m,
        "friction_head_m": friction_head_m,
    }
```

### Additional Changes
- Update `wells-toy.csv` to remove `pumping_energy_kwh_per_m3` column (now calculated)
- Add pipe specifications to scenario YAML or use defaults
- Calculate distances from infrastructure layout

### Files Modified
- `settings/scripts/calculations.py`
- `data/parameters/equipment/wells-toy.csv`
- `settings/scenarios/water_policy_testing.yaml` (optional: add pipe specs)

---

## Task 9: Simplify Battery Calculations

### Problem
Current battery calculation is complex with units_per_bank logic that's confusing.

### Solution

**9.1 Update `batteries-toy.csv`** - Add cost column:
```csv
battery_type,capacity_kwh,power_kw,round_trip_efficiency,cycle_life,depth_of_discharge_pct,lifespan_years,capital_cost_per_kwh
lithium_iron_phosphate_small,50,12.5,0.92,4500,80,12,350
lithium_iron_phosphate_medium,200,50,0.92,4500,80,12,300
lithium_iron_phosphate_large,500,125,0.92,4500,80,12,250
```

**9.2 Simplify `calculate_battery_config`**:
```python
def calculate_battery_config(scenario: Scenario) -> Dict[str, Any]:
    """Calculate battery configuration.

    Each bank = one battery unit. Total capacity = unit_capacity × num_banks.
    """
    battery_config = scenario.infrastructure.battery
    battery_specs = _load_csv_with_metadata(battery_specs_path)

    # Find matching chemistry
    chemistry_rows = battery_specs[
        battery_specs["battery_type"].str.contains(battery_config.chemistry, case=False, na=False)
    ]
    if chemistry_rows.empty:
        raise ValueError(f"Battery chemistry '{battery_config.chemistry}' not found")

    # Select size based on per-bank capacity
    capacity_per_bank = battery_config.sys_capacity_kwh / battery_config.units

    # Find closest match
    size_diff = (chemistry_rows["capacity_kwh"] - capacity_per_bank).abs()
    battery_data = chemistry_rows.loc[size_diff.idxmin()]

    return {
        "battery_type": battery_data["battery_type"],
        "num_banks": battery_config.units,
        "capacity_per_bank_kwh": battery_data["capacity_kwh"],
        "total_capacity_kwh": battery_data["capacity_kwh"] * battery_config.units,
        "power_per_bank_kw": battery_data["power_kw"],
        "total_power_kw": battery_data["power_kw"] * battery_config.units,
        "round_trip_efficiency": battery_data["round_trip_efficiency"],
        "cycle_life": battery_data["cycle_life"],
        "capital_cost_per_kwh": battery_data["capital_cost_per_kwh"],
        "total_capital_cost": battery_data["capital_cost_per_kwh"] * battery_data["capacity_kwh"] * battery_config.units,
    }
```

### Files Modified
- `data/parameters/equipment/batteries-toy.csv`
- `settings/scripts/calculations.py`

---

## Task 10: Create Seasonal Household Energy/Water Files

### Problem
Household energy and water demand varies by season (AC usage in summer).

### Solution

**10.1 Create calculation script**: `data/scripts/generate_household_demand.py`

Logic:
- Base energy demand from housing types
- AC multiplier based on daily temperature (from weather data)
- Water multiplier based on temperature (slight increase in summer)

**10.2 Create output files**:
- `data/precomputed/household/household_energy_kwh_per_day-toy.csv`
- `data/precomputed/household/household_water_m3_per_day-toy.csv`

Format (matching weather data dates):
```csv
date,small_household_kwh,medium_household_kwh,large_household_kwh,total_community_kwh
2010-01-01,10.5,13.0,16.0,452.5
2010-01-02,10.8,13.2,16.3,460.1
...
```

**10.3 Update data_registry.yaml**:
```yaml
household:
  energy: data/precomputed/household/household_energy_kwh_per_day-toy.csv
  water: data/precomputed/household/household_water_m3_per_day-toy.csv
```

### Files Created
- `data/scripts/generate_household_demand.py`
- `data/precomputed/household/household_energy_kwh_per_day-toy.csv`
- `data/precomputed/household/household_water_m3_per_day-toy.csv`

### Files Modified
- `settings/data_registry.yaml`

---

## Task 11: Replace Hardcoded Paths with Registry Lookups

### Problem
`calculations.py` has hardcoded paths like:
```python
pv_specs_path = _get_project_root() / "data/parameters/equipment/pv_systems-toy.csv"
```

This defeats the purpose of the data registry.

### Solution

**11.1 Add function to load registry**:
```python
def _get_registry():
    """Load data registry. Cache for performance."""
    if not hasattr(_get_registry, "_cache"):
        from settings.scripts.validation import load_registry
        _get_registry._cache = load_registry()
    return _get_registry._cache

def _get_data_path(category: str, subcategory: str) -> Path:
    """Get data file path from registry."""
    registry = _get_registry()
    try:
        path = registry[category][subcategory]
    except KeyError:
        raise KeyError(f"Registry path not found: {category}.{subcategory}")
    return _get_project_root() / path
```

**11.2 Update all path references**:
```python
# Before:
pv_specs_path = _get_project_root() / "data/parameters/equipment/pv_systems-toy.csv"

# After:
pv_specs_path = _get_data_path("equipment", "pv_systems")
```

**11.3 Ensure registry has all needed paths**:
Add any missing equipment paths to `data_registry.yaml`.

### Files Modified
- `settings/scripts/calculations.py`
- `settings/data_registry.yaml` (if paths missing)

---

## Implementation Order

Recommended sequence to minimize conflicts:

1. **Task 3** - Add economics validation (quick fix)
2. **Task 4** - Add battery units validation (quick fix)
3. **Task 2** - Fix battery IndexError (quick fix)
4. **Task 5** - Remove dead code (quick cleanup)
5. **Task 11** - Replace hardcoded paths (foundational change)
6. **Task 6** - Fix silent failures (requires audit)
7. **Task 7** - Improve cross-validation warnings
8. **Task 9** - Simplify battery calculations
9. **Task 8** - Engineering-based pumping calculation
10. **Task 1** - Processing equipment restructure
11. **Task 10** - Seasonal household demand files

---

## Verification

After all fixes, run:

```bash
# Validate registry
python settings/scripts/validation.py --registry

# Validate scenario
python settings/scripts/validation.py settings/scenarios/water_policy_testing.yaml

# Test loader
python -c "from settings.scripts.loader import load_scenario; s = load_scenario('settings/scenarios/water_policy_testing.yaml'); print('Loaded:', s.metadata.name)"

# Test calculations
python -c "
from settings.scripts.loader import load_scenario
from settings.scripts.calculations import calculate_infrastructure
s = load_scenario('settings/scenarios/water_policy_testing.yaml')
calc = calculate_infrastructure(s)
print('PV panels:', calc['energy']['pv']['panel_count'])
print('Battery:', calc['energy']['battery'])
print('Pumping energy:', calc['water']['pumping'])
"
```

---

## Notes

- All changes should maintain backward compatibility with existing scenario files where possible
- New required fields in YAML should have clear error messages
- Unit tests should be added for calculation functions (future task)
