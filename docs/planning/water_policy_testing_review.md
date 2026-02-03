# Water Policy Testing Scenario Review
## Configuration Analysis & Data Gap Assessment

**Date**: 2026-02-03  
**Scenario**: `settings/scenarios/water_policy_testing.yaml`  
**Purpose**: Review new configuration elements, assess data availability, and plan background calculations

---

## Executive Summary

The `water_policy_testing.yaml` scenario introduces significant new infrastructure configuration elements across energy, water, and food processing systems. Many of these require background calculations to derive operational parameters from user-facing settings. This document identifies data gaps and provides an implementation plan for required calculations.

---

## 1. New Configuration Elements Analysis

### 1.1 Energy Infrastructure

#### PV System (`energy_infrastructure.pv`)
**New Elements:**
- `sys_capacity_kw` (500 kW) - **RENAME**: Currently `capacity_kw` in loader.py
- `type` (fixed_tilt) - **NEW**: Currently not in loader.py
- `percent_over_crops` (0.50) - **NEW**: Not in loader.py or data files
- `height_m` (3 m) - **NEW**: Not in loader.py, but exists in `pv_systems-toy.csv` as `panel_height_m`
- `tilt_angle` (28°) - **EXISTS**: In loader.py
- `density` (medium) - **EXISTS**: In loader.py and `pv_systems-toy.csv`

**Data Availability:**
- ✅ `data/parameters/equipment/pv_systems-toy.csv` - Contains density specs, panel height, efficiency
- ✅ `data/precomputed/pv_power/pv_normalized_kwh_per_kw_daily-toy.csv` - Power output by density
- ✅ `data/parameters/costs/capital_costs-toy.csv` - PV system costs ($850/kW)
- ✅ `data/parameters/costs/operating_costs-toy.csv` - PV O&M costs ($18/kW/year)

**Missing Data:**
- ❌ Panel count calculation parameters (panel wattage, area per panel)
- ❌ Area coverage calculations (hectares covered by PV based on `percent_over_crops`)

**Required Calculations:**
1. **Panel count**: `sys_capacity_kw` → number of panels (need panel wattage from equipment file)
2. **Area covered**: `percent_over_crops` × `total_area_ha` → hectares under panels
3. **Ground coverage validation**: Verify `percent_over_crops` × `density.ground_coverage_pct` ≤ 1.0

#### Wind System (`energy_infrastructure.wind`)
**New Elements:**
- `sys_capacity_kw` (50 kW) - **RENAME**: Currently `capacity_kw` in loader.py
- `type` (small) - **NEW**: Maps to turbine size (small=10kW, medium=30kW, large=60kW)
- `hub_height_m` (15 m) - **EXISTS**: In loader.py

**Data Availability:**
- ✅ `data/parameters/equipment/wind_turbines-toy.csv` - Contains turbine specs by type
- ✅ `data/precomputed/wind_power/wind_normalized_kwh_per_kw_daily-toy.csv` - Power output
- ✅ `data/parameters/costs/capital_costs-toy.csv` - Wind turbine costs by type
- ✅ `data/parameters/costs/operating_costs-toy.csv` - Wind O&M costs by type

**Missing Data:**
- ❌ Turbine count calculation (how many turbines of `type` needed for `sys_capacity_kw`)

**Required Calculations:**
1. **Turbine count**: `sys_capacity_kw` / `turbine_type.rated_capacity_kw` → number of turbines
2. **Hub height validation**: Verify `hub_height_m` matches or exceeds turbine minimum height

#### Battery System (`energy_infrastructure.battery`)
**New Elements:**
- `sys_capacity_kwh` (1000 kWh) - **EXISTS**: In loader.py
- `units` (2) - **EXISTS**: In loader.py
- `chemistry` (LFP) - **EXISTS**: In loader.py

**Data Availability:**
- ✅ `data/parameters/equipment/batteries-toy.csv` - Contains LFP battery specs
- ✅ `data/parameters/costs/capital_costs-toy.csv` - Battery costs ($280/kWh for LFP)
- ✅ `data/parameters/costs/operating_costs-toy.csv` - Battery O&M ($6/kWh/year)

**Missing Data:**
- ❌ Individual battery unit sizing (how to split `sys_capacity_kwh` across `units`)

**Required Calculations:**
1. **Battery unit capacity**: `sys_capacity_kwh` / `units` → capacity per battery bank
2. **Battery selection**: Match calculated capacity to nearest standard battery size from equipment file

#### Backup Generator (`energy_infrastructure.backup_generator`)
**New Elements:**
- `capacity_kw` (100 kW) - **EXISTS**: In loader.py
- `type` (diesel) - **NEW**: Not in loader.py

**Data Availability:**
- ✅ `data/parameters/costs/capital_costs-toy.csv` - Diesel generator costs ($350/kW)
- ✅ `data/parameters/costs/operating_costs-toy.csv` - Diesel O&M ($0.08/kWh + $15/kW/year)
- ✅ `data/prices/diesel/historical_diesel_prices-toy.csv` - Fuel prices

**Missing Data:**
- ❌ Generator efficiency/consumption rates (L/kWh or L/kW-hour)
- ❌ Generator startup/shutdown characteristics

**Required Calculations:**
1. **Fuel consumption**: Need efficiency curve or consumption rate (L/kWh) for diesel generator

---

### 1.2 Water Infrastructure

#### Groundwater Wells (`water_infrastructure.groundwater_wells`)
**New Elements:**
- `well_depth_m` (50 m) - **NEW**: Not in any data file
- `well_flow_rate_m3_day` (100 m³/day) - **NEW**: Not in any data file
- `number_of_wells` (10) - **NEW**: Not in any data file

**Data Availability:**
- ✅ `data/prices/water/historical_municipal_water_prices-toy.csv` - Water prices
- ❌ Well pumping energy requirements (kWh/m³ based on depth)
- ❌ Well capital costs (drilling, casing, pump)
- ❌ Well O&M costs

**Missing Data:**
- ❌ Well pumping power calculation parameters
- ❌ Well capital costs per well
- ❌ Well O&M costs
- ❌ Distance calculations (wells to treatment facilities)

**Required Calculations:**
1. **Pumping energy**: `well_depth_m` → kWh/m³ (pumping power calculation)
2. **Total well capacity**: `number_of_wells` × `well_flow_rate_m3_day` → total m³/day available
3. **Average distance to treatment**: Based on `number_of_wells` and `water_treatment.number_of_units`
4. **Well capital costs**: Need cost per well (drilling + equipment)
5. **Well O&M costs**: Annual maintenance per well

#### Water Treatment (`water_infrastructure.water_treatment`)
**New Elements:**
- `system_capacity_m3_day` (2000 m³/day) - **RENAME**: Currently `capacity_m3_day` in loader.py
- `number_of_units` (4) - **NEW**: Not in loader.py
- `salinity_level` (moderate) - **EXISTS**: In loader.py
- `tds_ppm` (6500) - **EXISTS**: In loader.py

**Data Availability:**
- ✅ `data/parameters/equipment/water_treatment-toy.csv` - Treatment specs by salinity
- ✅ `data/precomputed/water_treatment/treatment_kwh_per_m3-toy.csv` - Energy requirements
- ✅ `data/parameters/costs/capital_costs-toy.csv` - Treatment costs by salinity level
- ✅ `data/parameters/costs/operating_costs-toy.csv` - Treatment O&M costs

**Missing Data:**
- ❌ Individual unit sizing (how to split `system_capacity_m3_day` across `number_of_units`)
- ❌ Distance calculations (treatment units to fields)

**Required Calculations:**
1. **Unit capacity**: `system_capacity_m3_day` / `number_of_units` → capacity per treatment unit
2. **Average distance from wells**: Based on `groundwater_wells.number_of_wells` and `number_of_units`
3. **Average distance to fields**: Based on `number_of_units` and farm locations

#### Irrigation Water Storage (`water_infrastructure.irrigation_water_storage`)
**New Elements:**
- `capacity_m3` (500 m³) - **NEW**: Not in loader.py
- `type` (reservoir) - **NEW**: Not in loader.py (options: underground_tank, surface_tank, reservoir)

**Data Availability:**
- ✅ `data/parameters/costs/capital_costs-toy.csv` - Storage tank costs ($85-120/m³)
- ✅ `data/parameters/costs/operating_costs-toy.csv` - Storage O&M ($3/m³/year)

**Missing Data:**
- ❌ Storage type specifications (evaporation rates, capital costs by type)
- ❌ Storage efficiency/evaporation losses by type

**Required Calculations:**
1. **Evaporation losses**: Based on `type` and climate (from weather data)
2. **Capital costs**: Lookup cost by `type` and `capacity_m3`

#### Irrigation System (`water_infrastructure.irrigation_system`)
**New Elements:**
- `type` (drip_irrigation) - **NEW**: Not in loader.py (options: drip_irrigation, sprinkler_irrigation, furrow_irrigation)

**Data Availability:**
- ✅ `data/parameters/costs/capital_costs-toy.csv` - Drip system costs ($2200/ha)
- ✅ `data/parameters/costs/operating_costs-toy.csv` - Drip O&M ($180/ha/year)
- ✅ Irrigation demand data assumes 90% drip efficiency (in `generate_irrigation_and_yields.py`)

**Missing Data:**
- ❌ Irrigation efficiency by type (drip=90%, sprinkler=75%, furrow=60% typical)
- ❌ Irrigation system specifications by type

**Required Calculations:**
1. **Irrigation efficiency**: Lookup efficiency by `type` (affects irrigation demand calculations)
2. **Capital costs**: Lookup cost by `type` and total area

---

### 1.3 Food Processing Infrastructure

**New Elements (all new):**
- `fresh_food_packaging` - Processing capacity, shelf life, energy, labor, costs, storage
- `drying` - Processing capacity, shelf life, energy, labor, costs, storage
- `canning` - Processing capacity, shelf life, energy, labor, costs, storage
- `packaging` - Processing capacity, shelf life, energy, labor, costs, storage

**Important Context:**
- **Egyptian community farm context**: Processing should focus on human labor with simple machines, not industrial-scale equipment
- **Fresh food packaging**: Must include shipping/packaging materials (boxes, crates, bags) for transporting fresh produce to market
- **Research required**: Each processing type needs dedicated research to understand appropriate equipment, labor requirements, and costs for small-scale Egyptian community farms

**Data Availability:**
- ✅ `data/parameters/equipment/processing_equipment-toy.csv` - Equipment specs (packaged, canned, dried) - **NEEDS REVIEW** for community farm appropriateness
- ✅ `data/parameters/costs/capital_costs-toy.csv` - Processing equipment costs - **NEEDS REVIEW** for simple machine costs
- ✅ `data/parameters/costs/operating_costs-toy.csv` - Processing O&M costs - **NEEDS REVIEW** for labor-intensive operations
- ✅ `data/parameters/crops/processing_specs-toy.csv` - Crop processing specifications
- ✅ `data/parameters/crops/spoilage_rates-toy.csv` - Crop spoilage rates
- ✅ `data/prices/processed/` - Processed product prices

**Missing Data:**
- ❌ Fresh food packaging/shipping materials specifications (boxes, crates, bags, pallets)
- ❌ Labor-intensive processing equipment specs (simple machines, hand tools)
- ❌ Egyptian community farm context processing costs and labor requirements
- ❌ Mapping between YAML processing types and equipment file types
- ❌ Storage capacity validation (does `storage_capacity_kg_total` match equipment specs?)
- ❌ Labor requirements validation (does `labor_hours_per_kg` match equipment specs?)

**Required Research (Parallel Agent Tasks):**
1. **Agent 1 - Fresh Food Packaging Research**: Research appropriate packaging materials, labor requirements, and costs for Egyptian community farms shipping fresh produce
2. **Agent 2 - Drying Research**: Research simple drying methods (solar, simple dehydrators), labor requirements, and costs for Egyptian community farms
3. **Agent 3 - Canning Research**: Research small-scale canning equipment, labor requirements, and costs for Egyptian community farms
4. **Agent 4 - Packaging (Processed) Research**: Research packaging materials and methods for processed goods in Egyptian community farm context

**Required Calculations:**
1. **Equipment matching**: Map YAML processing types to equipment file entries
2. **Capacity validation**: Verify `processing_capacity_kg_day` matches equipment capabilities
3. **Storage validation**: Verify `storage_capacity_kg_total` is reasonable for processing capacity
4. **Packaging materials**: Calculate packaging material costs and requirements for fresh produce shipping

---

### 1.4 Community Structure

**New Elements:**
- None - **REMOVED**: `household_size` should not be in settings file

**Data Availability:**
- ✅ `data/parameters/community/housing_energy_water-toy.csv` - Household types with occupants
- ✅ `data/parameters/community/farm_profiles-toy.csv` - Farm profiles
- ✅ `community_population` (150) - **EXISTS**: In loader.py
- ❌ Number of houses/buildings - **MISSING**: Need to add to YAML or calculate from population

**Required Calculations:**
1. **Household count**: Calculate from `community_population` and typical household sizes in `housing_energy_water-toy.csv`
2. **Energy/water demand**: Lookup demand per household type from `housing_energy_water-toy.csv`, multiply by household count
3. **Building count**: Use number of houses (if specified) or estimate from population and household size distribution

---

## 2. Data Gap Summary

### Critical Gaps (Required for Simulation)
1. **Well infrastructure data**:
   - Well pumping energy (kWh/m³) based on depth
   - Well capital costs (drilling + equipment)
   - Well O&M costs
   - Well-to-treatment distance calculations

2. **Distance calculations**:
   - Average distance from wells to treatment facilities
   - Average distance from treatment facilities to fields
   - Pipeline/pumping costs based on distances

3. **Equipment sizing calculations**:
   - PV panel count from system capacity
   - Wind turbine count from system capacity
   - Battery unit sizing from total capacity and unit count
   - Water treatment unit sizing from total capacity and unit count

4. **Irrigation system data**:
   - Efficiency by type (drip, sprinkler, furrow)
   - Capital costs by type

5. **Generator specifications**:
   - Fuel consumption rate (L/kWh or L/kW-hour)
   - Efficiency curve

### Moderate Gaps (Nice to Have)
1. **Storage specifications**:
   - Evaporation rates by storage type
   - Capital costs by storage type (currently only generic tank costs)

2. **Processing validation**:
   - Cross-reference processing capacity with equipment specs
   - Validate storage capacity against processing capacity

---

## 3. Implementation Plan: Background Calculations

### Phase 0: Parallel Research Tasks (First - Data Collection)

**Objective**: Create or update data files needed for calculations. Each research task should be assigned to a separate agent working in parallel.

**Task 0.1: Research - Groundwater Wells (Agent 1)**
- **File**: `data/parameters/equipment/wells-toy.csv`
- **Research focus**: Well drilling costs, pumping energy requirements, O&M costs for Egyptian Sinai context
- **Columns needed**: `well_depth_m`, `flow_rate_m3_day`, `pumping_energy_kwh_per_m3`, `capital_cost_per_well`, `om_cost_per_year`
- **Context**: Sinai Peninsula, brackish groundwater, small-scale community wells (10-100 m³/day flow rates)

**Task 0.2: Research - Irrigation Systems (Agent 2)**
- **File**: `data/parameters/equipment/irrigation_systems-toy.csv`
- **Research focus**: Efficiency and costs for drip, sprinkler, and furrow irrigation in Egyptian context
- **Columns needed**: `irrigation_type`, `efficiency`, `capital_cost_per_ha`, `om_cost_per_ha_per_year`
- **Context**: Small-scale community farms, hot arid climate, Egyptian market prices

**Task 0.3: Research - Storage Systems (Agent 3)**
- **File**: `data/parameters/equipment/storage_systems-toy.csv`
- **Research focus**: Evaporation rates and costs for different storage types in hot arid climate
- **Columns needed**: `storage_type`, `evaporation_rate_annual_pct`, `capital_cost_per_m3`, `om_cost_per_m3_per_year`
- **Context**: Sinai Peninsula climate, underground tanks vs surface tanks vs reservoirs

**Task 0.4: Research - Generators (Agent 4)**
- **File**: `data/parameters/equipment/generators-toy.csv`
- **Research focus**: Diesel generator fuel consumption and efficiency for backup power
- **Columns needed**: `generator_type`, `fuel_consumption_l_per_kwh`, `efficiency`, `min_load_pct`, `startup_time_min`
- **Context**: Small-scale diesel generators (50-200 kW), Egyptian fuel prices

**Task 0.5: Research - Fresh Food Packaging (Agent 5)**
- **File**: `data/parameters/equipment/fresh_packaging-toy.csv` (NEW)
- **Research focus**: Packaging materials, labor, and costs for shipping fresh produce from Egyptian community farms
- **Columns needed**: `packaging_type`, `capacity_kg_per_unit`, `labor_hours_per_kg`, `material_cost_per_kg`, `energy_kwh_per_kg`, `shelf_life_days`
- **Context**: Egyptian community farms, simple packaging (boxes, crates, bags), manual labor with simple tools
- **Note**: This is separate from processed food packaging - focuses on shipping fresh produce to market

**Task 0.6: Research - Food Drying (Agent 6)**
- **File**: Update `data/parameters/equipment/processing_equipment-toy.csv` or create `drying_equipment-toy.csv`
- **Research focus**: Simple drying methods appropriate for Egyptian community farms (solar drying, simple dehydrators)
- **Columns needed**: `equipment_type`, `capacity_kg_per_day`, `energy_kw_continuous`, `labor_hours_per_kg`, `capital_cost_usd`, `maintenance_cost_per_year_usd`, `lifespan_years`
- **Context**: Human labor with simple machines, not industrial equipment, Egyptian market

**Task 0.7: Research - Food Canning (Agent 7)**
- **File**: Update `data/parameters/equipment/processing_equipment-toy.csv` or create `canning_equipment-toy.csv`
- **Research focus**: Small-scale canning equipment appropriate for Egyptian community farms
- **Columns needed**: `equipment_type`, `capacity_kg_per_day`, `energy_kw_continuous`, `labor_hours_per_kg`, `capital_cost_usd`, `maintenance_cost_per_year_usd`, `lifespan_years`
- **Context**: Human labor with simple machines, not industrial equipment, Egyptian market

**Task 0.8: Research - Processed Food Packaging (Agent 8)**
- **File**: Update `data/parameters/equipment/processing_equipment-toy.csv` or create `processed_packaging-toy.csv`
- **Research focus**: Packaging materials and methods for processed goods (dried, canned) in Egyptian community farm context
- **Columns needed**: `packaging_type`, `capacity_kg_per_unit`, `labor_hours_per_kg`, `material_cost_per_kg`, `energy_kwh_per_kg`
- **Context**: Egyptian community farms, simple packaging methods, manual labor

**Task 0.9: Research - PV Panel Specifications (Agent 9)**
- **File**: Update `data/parameters/equipment/pv_systems-toy.csv`
- **Research focus**: Add panel wattage and area specifications needed for panel count calculations
- **Columns to add**: `panel_wattage_w`, `panel_area_m2`, `panels_per_kw`
- **Context**: Standard polycrystalline panels used in agri-PV installations

---

### Phase 1: Update Loader.py (After Research Complete)

**Task 1.1: Update dataclasses to match YAML structure**
- Rename `capacity_kw` → `sys_capacity_kw` for PV and Wind
- Rename `capacity_m3_day` → `system_capacity_m3_day` for water treatment
- Add new fields: `type`, `percent_over_crops`, `height_m` for PV
- Add new fields: `type` for Wind and Backup Generator
- Add new dataclasses: `GroundwaterWellsConfig`, `IrrigationStorageConfig`, `IrrigationSystemConfig`
- Add new dataclass: `FoodProcessingConfig` with sub-configs for each processing type
- **REMOVE**: `household_size` from `CommunityConfig` (not in YAML)

**Task 1.2: Update loader validation**
- Validate `percent_over_crops` is between 0 and 1
- Validate `density` × `percent_over_crops` ≤ 1.0 (ground coverage check)
- Validate `number_of_wells` > 0
- Validate `number_of_units` > 0 for water treatment
- Validate processing capacity > 0 for all processing types
- **REMOVE**: `household_size` validation

---

### Phase 2: Create Calculation Module (Post-Loader)

**File**: `settings/scripts/calculations.py`

**Task 2.1: Energy Infrastructure Calculations**

```python
def calculate_pv_config(scenario):
    """Calculate PV system details from user settings."""
    # Input: scenario.infrastructure.pv
    # Output: dict with panel_count, area_covered_ha, etc.
    
def calculate_wind_config(scenario):
    """Calculate wind system details from user settings."""
    # Input: scenario.infrastructure.wind
    # Output: dict with turbine_count, turbine_type_specs, etc.
    
def calculate_battery_config(scenario):
    """Calculate battery system details from user settings."""
    # Input: scenario.infrastructure.battery
    # Output: dict with battery_unit_capacity, battery_count_per_unit, etc.
```

**Task 2.2: Water Infrastructure Calculations**

```python
def calculate_well_pumping_energy(well_depth_m, flow_rate_m3_day):
    """Calculate energy required to pump water from well."""
    # Formula: E = (ρ × g × h × V) / η
    # Where: ρ = water density, g = gravity, h = depth, V = volume, η = pump efficiency
    # Returns: kWh/m³
    
def calculate_well_costs(number_of_wells, well_depth_m):
    """Calculate capital and O&M costs for wells."""
    # Lookup drilling costs per meter, pump costs, etc.
    
def calculate_distances(wells_config, treatment_config, farms):
    """Calculate average distances between infrastructure components."""
    # Uses geometric assumptions:
    # - Wells distributed evenly across area
    # - Treatment units distributed evenly
    # - Average distance = function of number of units and area
    # Returns: dict with well_to_treatment_km, treatment_to_field_km, etc.
    
def calculate_treatment_unit_sizing(total_capacity, number_of_units):
    """Calculate capacity per treatment unit."""
    # Returns: capacity_m3_day_per_unit
```

**Task 2.3: Irrigation Calculations**

```python
def get_irrigation_efficiency(irrigation_type):
    """Lookup irrigation efficiency by type."""
    # drip_irrigation: 0.90
    # sprinkler_irrigation: 0.75
    # furrow_irrigation: 0.60
    
def calculate_irrigation_demand_adjustment(base_demand, irrigation_type):
    """Adjust irrigation demand based on system efficiency."""
    # base_demand assumes 90% drip efficiency
    # Adjust for other types: base_demand × (0.90 / actual_efficiency)
```

**Task 2.4: Storage Calculations**

```python
def calculate_storage_evaporation(capacity_m3, storage_type, weather_data):
    """Calculate evaporation losses from storage."""
    # Lookup evaporation rate by type:
    # - underground_tank: 0% (negligible)
    # - surface_tank: ~5-10% annual
    # - reservoir: ~10-20% annual (depends on surface area)
    
def calculate_storage_costs(capacity_m3, storage_type):
    """Calculate capital costs for storage."""
    # Lookup cost per m³ by type from capital_costs-toy.csv
```

**Task 2.5: Generator Calculations**

```python
def calculate_generator_fuel_consumption(capacity_kw, load_factor, generator_type):
    """Calculate fuel consumption for diesel generator."""
    # Typical: 0.25-0.30 L/kWh for diesel generators
    # Returns: L/hour or L/kWh
```

**Task 2.6: Processing Calculations**

```python
def validate_processing_capacity(processing_config, equipment_specs):
    """Validate processing capacity matches equipment capabilities."""
    # Cross-reference YAML capacity with equipment file specs
    
def calculate_processing_energy_demand(processing_config, daily_throughput):
    """Calculate total energy demand for processing."""
    # Sum energy_kwh_per_kg × daily_throughput for each processing type
```

**Task 2.7: Community Calculations**

```python
def calculate_household_demand(community_config, housing_data):
    """Calculate total community energy and water demand."""
    # Calculate household distribution from population and housing_data
    # Use typical household sizes from housing_energy_water-toy.csv
    # Calculate household_count based on population distribution
    # Lookup demand per household type from housing_energy_water-toy.csv
    # Multiply by household_count for each type
    # Returns: total_energy_kwh_per_day, total_water_m3_per_day
```

---

### Phase 3: Create Calculation Data Files (Completed in Phase 0)

**Note**: All data files should be created/updated in Phase 0 (parallel research tasks) before proceeding to implementation phases.

---

### Phase 4: Integration with Validation

**Task 4.1: Add calculation validation to validation.py**
- After loading scenario, run calculations
- Validate calculated values are within reasonable ranges
- Check for inconsistencies (e.g., treatment capacity < well capacity)

**Task 4.2: Create calculation results dataclass**
- `CalculatedInfrastructure` dataclass containing all derived values
- Attach to `Scenario` object after loading

---

## 4. Example Calculation Flow

```python
# After loader.py runs:
scenario = load_scenario("settings/scenarios/water_policy_testing.yaml")

# Then calculations.py runs:
from settings.scripts.calculations import calculate_infrastructure

calculated = calculate_infrastructure(scenario)

# Returns:
# {
#   "pv": {
#     "panel_count": 2000,  # Assuming 250W panels for 500kW
#     "area_covered_ha": 250,  # 0.50 × 500 ha
#     "ground_coverage_pct": 0.50  # percent_over_crops × density
#   },
#   "wind": {
#     "turbine_count": 5,  # 50kW / 10kW per small turbine
#     "turbine_specs": {...}  # From equipment file
#   },
#   "battery": {
#     "capacity_per_unit_kwh": 500,  # 1000 kWh / 2 units
#     "battery_type": "lithium_iron_phosphate_large"  # Matched from equipment file
#   },
#   "wells": {
#     "total_capacity_m3_day": 1000,  # 10 wells × 100 m³/day
#     "pumping_energy_kwh_per_m3": 0.15,  # Calculated from depth
#     "capital_cost_usd": 500000,  # 10 wells × $50k per well
#     "average_distance_to_treatment_km": 2.5  # Geometric calculation
#   },
#   "treatment": {
#     "capacity_per_unit_m3_day": 500,  # 2000 m³/day / 4 units
#     "average_distance_to_fields_km": 1.5  # Geometric calculation
#   },
#   "irrigation": {
#     "efficiency": 0.90,  # drip_irrigation
#     "demand_multiplier": 1.0  # No adjustment needed (already assumes drip)
#   },
#   "storage": {
#     "evaporation_rate_annual_pct": 15.0,  # reservoir type
#     "capital_cost_usd": 60000  # 500 m³ × $120/m³
#   },
#   "generator": {
#     "fuel_consumption_l_per_kwh": 0.28,  # diesel generator
#     "fuel_consumption_l_per_hour_at_full_load": 28.0  # 100kW × 0.28 L/kWh
#   },
#   "processing": {
#     "total_energy_demand_kw": 73.0,  # Sum of all processing types
#     "total_labor_hours_per_day": 400.0  # Sum of all processing types
#   },
#   "community": {
#     "household_count": 30,  # 150 people / 5 per household
#     "total_energy_demand_kwh_per_day": 480.0,  # 30 households × 16 kWh/day avg
#     "total_water_demand_m3_per_day": 13.5  # 30 households × 0.45 m³/day avg
#   }
# }
```

---

## 5. Recommendations

### Research Priority (Phase 0 - Parallel Agents)
1. **Critical**: `wells-toy.csv` (Agent 1) - Required for water pumping calculations
2. **Critical**: `irrigation_systems-toy.csv` (Agent 2) - Required for irrigation efficiency
3. **High**: `fresh_packaging-toy.csv` (Agent 5) - Missing fresh produce shipping capability
4. **High**: Processing equipment updates (Agents 6-8) - Need Egyptian community farm context
5. **Medium**: `storage_systems-toy.csv` (Agent 3) - Needed for evaporation calculations
6. **Medium**: `generators-toy.csv` (Agent 4) - Needed for fuel consumption
7. **Low**: PV panel specs update (Agent 9) - Nice to have for detailed calculations

### Implementation Priority (After Research)
1. **Phase 1**: Update loader.py to handle new YAML structure
2. **Phase 2**: Implement calculation module with all functions
3. **Phase 4**: Add validation for calculated values
4. **Testing**: Test with `water_policy_testing.yaml` scenario

### User-Facing Simplifications
- Keep YAML simple: users specify `sys_capacity_kw`, not panel count
- Hide complexity: calculations happen automatically after loading
- Provide validation errors: if `percent_over_crops` × `density` > 1.0, show clear error
- Remove `household_size`: calculate from population and housing data

---

## 6. Implementation Prompt for Multiple Agents

See `docs/prompts/water_policy_testing_implementation.md` for detailed agent assignment prompts.

---

**End of Report**
