# Layer 2 Code Review - Comprehensive Audit Prompt

Perform a thorough code review of the Layer 2 configuration system. Focus on logic errors, calculation bugs, code inefficiencies, and dead code. This review is critical before starting Layer 3 simulation development.

---

## Scope

### Files to Review

**Configuration Scripts** (Primary Focus):
- `settings/scripts/loader.py` - Scenario YAML loader, dataclass definitions
- `settings/scripts/validation.py` - Registry and scenario validation
- `settings/scripts/calculations.py` - Infrastructure calculations

**Scenario Configuration**:
- `settings/scenarios/water_policy_testing.yaml` - Test scenario

**Policy Implementations**:
- `settings/policies/water_policies.py` - 4 water allocation policies (functional)
- `settings/policies/energy_policies.py` - Energy policies (stubbed)
- `settings/policies/crop_policies.py` - Crop policies (stubbed)
- `settings/policies/economic_policies.py` - Economic policies (stubbed)
- `settings/policies/market_policies.py` - Market policies (stubbed)

**Data Registry**:
- `settings/data_registry.yaml` - Central file path registry

**Supporting Data Files** (spot check for consistency):
- `data/parameters/equipment/*.csv` - Equipment specifications
- `data/parameters/community/*.csv` - Community parameters
- `data/precomputed/*.csv` - Pre-computed physical data

---

## Review Checklist

### 1. Logic Errors

**loader.py**:
- [ ] Verify all dataclass fields have correct types and defaults
- [ ] Check policy instantiation logic handles all policy names correctly
- [ ] Verify nested object creation doesn't silently fail on missing keys
- [ ] Check date parsing handles edge cases (invalid formats, out-of-range dates)
- [ ] Verify farm policy assignments propagate correctly to Scenario object

**validation.py**:
- [ ] Verify all required sections are actually checked
- [ ] Check cross-validation logic (treatment vs well capacity, storage vs throughput)
- [ ] Verify error messages accurately describe the validation failure
- [ ] Check that validation catches realistic misconfiguration scenarios

**calculations.py**:
- [ ] Verify CSV column names match what the code expects
- [ ] Check that equipment lookups handle "not found" cases gracefully
- [ ] Verify unit conversions are correct (ha→km², m³/day→kWh, etc.)
- [ ] Check that default values make physical sense

### 2. Calculation Errors

**Energy Calculations**:
- [ ] `calculate_pv_config`: Panel count = capacity_kw × panels_per_kw (verify formula)
- [ ] `calculate_wind_config`: Turbine count rounding logic (ceiling vs floor)
- [ ] `calculate_battery_config`: Units per bank calculation logic
- [ ] `calculate_generator_config`: Closest-match selection algorithm

**Water Calculations**:
- [ ] `calculate_well_pumping_energy`: Energy/m³ lookup logic
- [ ] `calculate_well_costs`: Cost aggregation across wells
- [ ] `calculate_treatment_unit_sizing`: Division by number of units
- [ ] `calculate_storage_evaporation`: Daily vs annual conversion
- [ ] `calculate_distances`: Geometric distance formula coefficients

**Processing Calculations**:
- [ ] `calculate_processing_energy_demand`: Energy × throughput
- [ ] `calculate_processing_labor_demand`: Labor hours × throughput
- [ ] `validate_processing_capacity`: Equipment type matching

**Community Calculations**:
- [ ] `calculate_household_demand`: Weighted average calculation from housing data
- [ ] Fallback values when data files are missing

### 3. Code Bugs

**Common Bug Patterns to Check**:
- [ ] Off-by-one errors in loops and indexing
- [ ] Division by zero when counts are 0
- [ ] Empty DataFrame handling (`.iloc[0]` on empty results)
- [ ] String matching case sensitivity issues
- [ ] Missing `return` statements in conditional branches
- [ ] Mutable default arguments in function signatures
- [ ] Variable shadowing (reusing names in nested scopes)

**File I/O**:
- [ ] CSV metadata header skipping works for all file formats
- [ ] Path handling works on all platforms (use `Path` not string concatenation)
- [ ] Missing file exceptions are caught and handled appropriately

**Type Safety**:
- [ ] Numeric values from YAML are correctly typed (int vs float)
- [ ] Boolean checks don't confuse `None`, `0`, `""`, and `False`
- [ ] List/dict access uses `.get()` with defaults where appropriate

### 4. Inefficient Code

**Performance**:
- [ ] Repeated file loads that could be cached
- [ ] DataFrame operations that iterate row-by-row (use vectorized ops)
- [ ] String concatenation in loops (use `join` or f-strings)
- [ ] Redundant calculations of the same value

**Code Structure**:
- [ ] Duplicated code that should be extracted to functions
- [ ] Overly complex conditionals that could be simplified
- [ ] Magic numbers that should be constants
- [ ] Deeply nested code that could be flattened

### 5. Dead Code

- [ ] Functions defined but never called
- [ ] Variables assigned but never used
- [ ] Commented-out code blocks
- [ ] Unreachable code after return/raise statements
- [ ] Import statements for unused modules
- [ ] Conditional branches that can never execute

---

## Scenario Validation

### water_policy_testing.yaml Cross-Checks

**Physical Consistency**:
- [ ] Total well capacity (10 wells × 100 m³/day = 1000 m³/day) vs treatment capacity (2000 m³/day) - is treatment oversized?
- [ ] Storage capacity (500 m³) vs daily treatment (2000 m³/day) - only 6 hours buffer, is this realistic?
- [ ] Farm areas sum to total (4 × 125 = 500 ha) ✓
- [ ] Crop fractions sum to 1.0 (0.25+0.25+0.20+0.15+0.15 = 1.0) ✓

**Policy Assignments**:
- [ ] All 4 water policies referenced exist in `water_policies.py`
- [ ] All economic policies referenced exist in `economic_policies.py`
- [ ] All energy policies referenced exist in `energy_policies.py`
- [ ] Policy parameter overrides are correctly applied

**Date Ranges**:
- [ ] Simulation dates (2015-01-01 to 2024-12-31) fall within weather data range
- [ ] Weather scenario "001" exists in registry

---

## Data File Consistency

### Equipment Files Spot-Check

For each equipment file, verify:
- [ ] Column names match what `calculations.py` expects
- [ ] Units are consistent with calculations (kW, kWh, m³, kg, etc.)
- [ ] No missing or malformed values
- [ ] Reasonable value ranges for the equipment type

**Key Files**:
- `pv_systems-toy.csv`: Check `density_name`, `panels_per_kw`, `ground_coverage_pct`
- `wind_turbines-toy.csv`: Check `turbine_name`, `rated_capacity_kw`
- `batteries-toy.csv`: Check `battery_type`, `capacity_kwh`, `round_trip_efficiency`
- `wells-toy.csv`: Check `well_depth_m`, `flow_rate_m3_day`, `pumping_energy_kwh_per_m3`
- `storage_systems-toy.csv`: Check `storage_type`, `evaporation_rate_annual_pct`
- `irrigation_systems-toy.csv`: Check `irrigation_type`, `efficiency`
- `processing_equipment-toy.csv`: Check `equipment_type`, `capacity_kg_per_day`
- `generators-toy.csv`: Check `capacity_kw`, `fuel_consumption_l_per_kwh`

### Housing Data
- `housing_energy_water-toy.csv`: Check `occupants_per_household`, `kwh_per_household_per_day`, `m3_per_household_per_day`

---

## Specific Questions to Answer

1. **In `calculate_battery_config`**: The battery selection logic uses string matching (`"lithium_iron_phosphate"`, `"large"`, `"medium"`, `"small"`). Does the actual `batteries-toy.csv` use these exact strings?

2. **In `calculate_well_pumping_energy`**: The weighting formula `combined_diff = depth_diff + flow_diff * 0.01` seems arbitrary. Is this appropriate? What happens if no good match exists?

3. **In `validate_processing_capacity`**: The equipment type mapping uses `"dried"`, `"canned"`, `"packaged"` - do these match the `equipment_type` column in `processing_equipment-toy.csv`?

4. **In `calculate_household_demand`**: The weighted average uses `occupants_per_household` as weights. Should this be `number_of_households` instead?

5. **In `calculate_distances`**: The coefficients 0.3 and 0.4 are described but not justified. Are these empirically reasonable for rural infrastructure?

6. **Cross-validation in validation.py**: The check `treatment_capacity < total_well_capacity` may give false positives if treatment is intentionally sized for peak demand rather than well capacity. Is this the intended behavior?

7. **Policy instantiation in loader.py**: What happens if a policy name in the YAML doesn't match any known policy? Is the error message helpful?

---

## Deliverables

After completing the review, provide:

1. **Bug Report**: List of confirmed bugs with severity (critical/medium/low), affected file:line, and suggested fix

2. **Logic Issues**: List of logic errors or questionable assumptions with explanation

3. **Calculation Corrections**: Any calculation formulas that are incorrect with the correct formula

4. **Code Improvements**: Inefficient or dead code with suggested refactoring

5. **Data Inconsistencies**: Mismatches between code expectations and actual data files

6. **Recommended Fixes**: Prioritized list of changes to make

---

## Verification Commands

After any fixes, run these to verify the system still works:

```bash
# Validate registry
python settings/scripts/validation.py --registry

# Validate scenario
python settings/scripts/validation.py settings/scenarios/water_policy_testing.yaml

# Test loader
python -c "from settings.scripts.loader import load_scenario; s = load_scenario('settings/scenarios/water_policy_testing.yaml'); print('Loaded:', s.scenario.name)"

# Test calculations
python -c "from settings.scripts.loader import load_scenario; from settings.scripts.calculations import calculate_infrastructure; s = load_scenario('settings/scenarios/water_policy_testing.yaml'); calc = calculate_infrastructure(s); print('Energy:', calc['energy']['pv'])"

# Test water policies
python -c "
from settings.scripts.loader import load_scenario
s = load_scenario('settings/scenarios/water_policy_testing.yaml')
for farm in s.farms:
    print(f'{farm.name}: {farm.policies.water.__class__.__name__}')
"
```

---

**End of Review Prompt**
