# Water Policy Testing Implementation - Multi-Agent Prompt

**Date**: 2026-02-03  
**Purpose**: Launch parallel research agents to create/update data files, then implement loader, validation, and calculation modules

**Context**: The `water_policy_testing.yaml` scenario introduces new infrastructure configuration elements that require background calculations. Before implementing the calculation logic, we need to ensure all required data files exist with appropriate specifications for Egyptian community farm context.

---

## Phase 0: Parallel Research Tasks

**Objective**: Create or update data files with research-backed specifications appropriate for Egyptian community farms in the Sinai Peninsula.

**Instructions for Each Agent**: 
- Review existing data files in `data/parameters/equipment/` to understand format and metadata structure
- Research appropriate specifications for Egyptian community farm context (not industrial-scale)
- Create or update CSV files following the existing format with metadata headers
- Include sources, assumptions, and logic in metadata comments
- All costs should be in 2024 USD
- Focus on small-scale, labor-intensive operations where appropriate

---

### Agent 1: Groundwater Wells Research

**Task**: Create `data/parameters/equipment/wells-toy.csv`

**Research Focus**:
- Well drilling costs for Sinai Peninsula (brackish groundwater, 30-100m depth)
- Pumping energy requirements (kWh/m³) based on well depth
- O&M costs for small-scale community wells
- Pump specifications and costs

**Required Columns**:
- `well_depth_m` (meters) - Depth categories: 30, 50, 75, 100
- `flow_rate_m3_day` (m³/day) - Flow rate categories: 50, 100, 150, 200
- `pumping_energy_kwh_per_m3` (kWh/m³) - Calculated from depth and pump efficiency
- `capital_cost_per_well` (USD) - Drilling + casing + pump + installation
- `om_cost_per_year` (USD/year) - Annual maintenance and repairs

**Context**:
- Location: Sinai Peninsula, Egypt
- Water type: Brackish groundwater
- Scale: Community wells (10-20 wells per community)
- Typical depth: 30-100 meters
- Typical flow: 50-200 m³/day per well

**Research Sources**:
- FAO irrigation and water management guides
- Egyptian well drilling cost databases
- Pump manufacturer specifications (solar and electric)
- Small-scale community water system case studies

**Deliverable**: CSV file with metadata header following format of existing equipment files

---

### Agent 2: Irrigation Systems Research

**Task**: Create `data/parameters/equipment/irrigation_systems-toy.csv`

**Research Focus**:
- Irrigation efficiency by type (drip, sprinkler, furrow) for hot arid climate
- Capital costs per hectare for each irrigation type
- O&M costs per hectare per year
- Egyptian market prices for irrigation equipment

**Required Columns**:
- `irrigation_type` - Options: drip_irrigation, sprinkler_irrigation, furrow_irrigation
- `efficiency` (decimal) - Water application efficiency (0.60-0.90)
- `capital_cost_per_ha` (USD/ha) - Equipment + installation costs
- `om_cost_per_ha_per_year` (USD/ha/year) - Annual maintenance, repairs, replacement parts

**Context**:
- Location: Sinai Peninsula, Egypt
- Climate: Hot arid, year-round irrigation needed
- Scale: Small-scale community farms (10-50 ha per farm)
- Water source: Treated brackish groundwater
- Current assumption: Drip irrigation at 90% efficiency (used in existing irrigation demand calculations)

**Research Sources**:
- FAO Irrigation and Drainage Papers
- Egyptian irrigation equipment suppliers
- Irrigation efficiency studies for hot arid climates
- Community farm case studies

**Deliverable**: CSV file with metadata header

---

### Agent 3: Storage Systems Research

**Task**: Create `data/parameters/equipment/storage_systems-toy.csv`

**Research Focus**:
- Evaporation rates by storage type in hot arid climate
- Capital costs per m³ for different storage types
- O&M costs per m³ per year
- Egyptian construction costs for storage infrastructure

**Required Columns**:
- `storage_type` - Options: underground_tank, surface_tank, reservoir
- `evaporation_rate_annual_pct` (%) - Annual evaporation loss percentage
- `capital_cost_per_m3` (USD/m³) - Construction + equipment costs
- `om_cost_per_m3_per_year` (USD/m³/year) - Annual maintenance, cleaning, repairs

**Context**:
- Location: Sinai Peninsula, Egypt
- Climate: Hot arid, high evaporation rates
- Storage capacity: 100-2000 m³ typical
- Water type: Treated irrigation water
- Use case: Buffer storage between treatment and irrigation

**Research Sources**:
- Evaporation studies for hot arid climates
- Egyptian construction cost databases
- Water storage infrastructure case studies
- FAO water storage guides

**Deliverable**: CSV file with metadata header

---

### Agent 4: Generator Specifications Research

**Task**: Create `data/parameters/equipment/generators-toy.csv`

**Research Focus**:
- Diesel generator fuel consumption rates (L/kWh)
- Generator efficiency curves
- Minimum load requirements
- Startup/shutdown characteristics

**Required Columns**:
- `generator_type` - Options: diesel (only option for now)
- `capacity_kw` (kW) - Generator capacity categories: 50, 100, 150, 200
- `fuel_consumption_l_per_kwh` (L/kWh) - Fuel consumption at various load factors
- `efficiency` (decimal) - Generator efficiency (typically 0.30-0.40)
- `min_load_pct` (%) - Minimum recommended load percentage
- `startup_time_min` (minutes) - Time to start and reach full capacity

**Context**:
- Location: Sinai Peninsula, Egypt
- Use case: Backup power for critical loads
- Fuel: Diesel (available in Egypt)
- Scale: Small-scale community microgrid (50-200 kW)

**Research Sources**:
- Diesel generator manufacturer specifications
- Generator efficiency studies
- Egyptian fuel prices and availability
- Microgrid backup power case studies

**Deliverable**: CSV file with metadata header

---

### Agent 5: Fresh Food Packaging Research

**Task**: Create `data/parameters/equipment/fresh_packaging-toy.csv` (NEW FILE)

**Research Focus**:
- Packaging materials for shipping fresh produce (boxes, crates, bags, pallets)
- Labor requirements for packaging fresh produce
- Material costs per kg of produce
- Energy requirements (minimal - mostly manual)
- Shelf life extension from proper packaging

**Required Columns**:
- `packaging_type` - Options: cardboard_box, plastic_crate, mesh_bag, wooden_crate, pallet
- `capacity_kg_per_unit` (kg) - Typical capacity of packaging unit
- `labor_hours_per_kg` (hours/kg) - Manual labor time to package produce
- `material_cost_per_kg` (USD/kg) - Cost of packaging materials per kg of produce
- `energy_kwh_per_kg` (kWh/kg) - Energy for any machinery (likely minimal)
- `shelf_life_extension_days` (days) - Additional shelf life from proper packaging

**Context**:
- Location: Egyptian community farms
- Scale: Small-scale, manual labor with simple tools
- Products: Fresh vegetables (tomato, potato, onion, kale, cucumber)
- Destination: Local markets, distribution centers
- **Important**: Focus on simple, affordable packaging appropriate for community farms, not industrial packaging

**Research Sources**:
- FAO post-harvest handling guides
- Egyptian packaging material suppliers
- Community farm packaging case studies
- Post-harvest loss reduction studies

**Deliverable**: CSV file with metadata header

---

### Agent 6: Food Drying Research

**Task**: Update `data/parameters/equipment/processing_equipment-toy.csv` or create `drying_equipment-toy.csv`

**Research Focus**:
- Simple drying methods appropriate for Egyptian community farms
- Solar drying vs simple dehydrator equipment
- Labor-intensive drying processes (not industrial)
- Energy requirements for simple dehydrators
- Capital and O&M costs for small-scale drying

**Required Columns**:
- `equipment_type` - Options: solar_drying_rack, simple_dehydrator, solar_tunnel_dryer
- `capacity_kg_per_day` (kg/day) - Daily processing capacity
- `energy_kw_continuous` (kW) - Energy for dehydrators (solar = 0)
- `labor_hours_per_kg` (hours/kg) - Manual labor requirements
- `capital_cost_usd` (USD) - Equipment + installation costs
- `maintenance_cost_per_year_usd` (USD/year) - Annual maintenance
- `lifespan_years` (years) - Equipment lifespan

**Context**:
- Location: Egyptian community farms
- Scale: Small-scale, mostly manual labor
- Products: Tomatoes, kale (primary dried products)
- Climate: Hot arid - solar drying highly effective
- **Important**: Focus on simple machines and manual processes, not industrial equipment

**Research Sources**:
- FAO food preservation guides
- Solar drying technology for small-scale farms
- Egyptian agricultural processing case studies
- Simple dehydrator equipment suppliers

**Deliverable**: Updated or new CSV file with metadata header

---

### Agent 7: Food Canning Research

**Task**: Update `data/parameters/equipment/processing_equipment-toy.csv` or create `canning_equipment-toy.csv`

**Research Focus**:
- Small-scale canning equipment appropriate for Egyptian community farms
- Manual canning processes with simple sealing equipment
- Labor-intensive canning (not industrial)
- Energy requirements for heating/sterilization
- Capital and O&M costs for small-scale canning

**Required Columns**:
- `equipment_type` - Options: manual_canning_line, simple_retort, pressure_canner
- `capacity_kg_per_day` (kg/day) - Daily processing capacity
- `energy_kw_continuous` (kW) - Energy for heating/sterilization
- `labor_hours_per_kg` (hours/kg) - Manual labor requirements
- `capital_cost_usd` (USD) - Equipment + installation costs
- `maintenance_cost_per_year_usd` (USD/year) - Annual maintenance
- `lifespan_years` (years) - Equipment lifespan

**Context**:
- Location: Egyptian community farms
- Scale: Small-scale, mostly manual labor
- Products: Tomatoes, onions (primary canned products)
- **Important**: Focus on simple machines and manual processes, not industrial canning lines

**Research Sources**:
- FAO food preservation guides
- Small-scale canning equipment suppliers
- Egyptian agricultural processing case studies
- Community food processing guides

**Deliverable**: Updated or new CSV file with metadata header

---

### Agent 8: Processed Food Packaging Research

**Task**: Update `data/parameters/equipment/processing_equipment-toy.csv` or create `processed_packaging-toy.csv`

**Research Focus**:
- Packaging materials and methods for processed goods (dried, canned)
- Simple packaging appropriate for Egyptian community farms
- Labor requirements for packaging processed goods
- Material costs per kg
- Energy requirements (minimal)

**Required Columns**:
- `packaging_type` - Options: sealed_bag, glass_jar, metal_can, vacuum_bag
- `capacity_kg_per_unit` (kg) - Typical capacity of packaging unit
- `labor_hours_per_kg` (hours/kg) - Manual labor time to package processed goods
- `material_cost_per_kg` (USD/kg) - Cost of packaging materials per kg
- `energy_kwh_per_kg` (kWh/kg) - Energy for sealing equipment (likely minimal)

**Context**:
- Location: Egyptian community farms
- Scale: Small-scale, manual labor with simple tools
- Products: Dried tomatoes/kale, canned tomatoes/onions
- **Important**: Focus on simple, affordable packaging appropriate for community farms

**Research Sources**:
- FAO food packaging guides
- Egyptian packaging material suppliers
- Community food processing case studies
- Small-scale food packaging methods

**Deliverable**: Updated or new CSV file with metadata header

---

### Agent 9: PV Panel Specifications Update

**Task**: Update `data/parameters/equipment/pv_systems-toy.csv`

**Research Focus**:
- Add panel specifications needed for panel count calculations
- Standard polycrystalline panel wattage and area
- Panels per kW calculation

**Required Columns to Add**:
- `panel_wattage_w` (W) - Standard panel wattage (e.g., 250W, 300W, 400W)
- `panel_area_m2` (m²) - Panel area per panel
- `panels_per_kw` (panels/kW) - Number of panels per kW capacity

**Context**:
- Panel type: Polycrystalline standard (as specified in existing file)
- Use case: Agri-PV installation
- Standard sizes: Common panel sizes used in 2024

**Research Sources**:
- PV panel manufacturer specifications
- NREL PV system specifications
- Standard panel sizes for agri-PV

**Deliverable**: Updated CSV file with new columns added

---

## Phase 1: Implementation Tasks (After Research Complete)

**Note**: These tasks should be assigned after Phase 0 research is complete and data files are validated.

### Agent 10: Update Loader.py

**Task**: Update `settings/scripts/loader.py` to handle new YAML structure

**Changes Required**:
1. Rename `capacity_kw` → `sys_capacity_kw` for PV and Wind configs
2. Rename `capacity_m3_day` → `system_capacity_m3_day` for water treatment
3. Add new fields to `PVConfig`: `type`, `percent_over_crops`, `height_m`
4. Add new field to `WindConfig`: `type`
5. Add new field to `DieselBackupConfig`: `type`
6. Create new dataclasses:
   - `GroundwaterWellsConfig` (well_depth_m, well_flow_rate_m3_day, number_of_wells)
   - `IrrigationStorageConfig` (capacity_m3, type)
   - `IrrigationSystemConfig` (type)
   - `FoodProcessingConfig` with sub-configs for each processing type
7. Update `InfrastructureConfig` to include new water infrastructure configs
8. Update `_load_infrastructure()` function to parse new YAML structure
9. **Remove**: `household_size` from `CommunityConfig` (not in YAML)

**Validation to Add**:
- `percent_over_crops` between 0 and 1
- `density` × `percent_over_crops` ≤ 1.0
- `number_of_wells` > 0
- `number_of_units` > 0 for water treatment
- Processing capacity > 0 for all processing types

**Test**: Load `water_policy_testing.yaml` and verify all fields parse correctly

---

### Agent 11: Update Validation.py

**Task**: Update `settings/scripts/validation.py` to validate new YAML structure

**Changes Required**:
1. Add validation for new infrastructure sections:
   - `water_infrastructure.groundwater_wells`
   - `water_infrastructure.irrigation_water_storage`
   - `water_infrastructure.irrigation_system`
   - `food_processing_infrastructure`
2. Add validation for new energy infrastructure fields
3. Add cross-validation checks:
   - Treatment capacity should be reasonable relative to well capacity
   - Processing capacity should match equipment capabilities
   - PV coverage should not exceed total area

**Test**: Run validation on `water_policy_testing.yaml` and verify all checks pass

---

### Agent 12: Create Calculations Module

**Task**: Create `settings/scripts/calculations.py` with all calculation functions

**Required Functions**:

1. **Energy Infrastructure**:
   - `calculate_pv_config(scenario)` - Panel count, area covered, ground coverage
   - `calculate_wind_config(scenario)` - Turbine count, turbine specs
   - `calculate_battery_config(scenario)` - Battery unit capacity, battery selection
   - `calculate_generator_config(scenario)` - Fuel consumption, efficiency

2. **Water Infrastructure**:
   - `calculate_well_pumping_energy(well_depth_m, flow_rate_m3_day)` - kWh/m³
   - `calculate_well_costs(number_of_wells, well_depth_m, flow_rate_m3_day)` - Capital and O&M costs
   - `calculate_treatment_unit_sizing(total_capacity, number_of_units)` - Capacity per unit
   - `calculate_distances(wells_config, treatment_config, farms)` - Average distances
   - `calculate_storage_evaporation(capacity_m3, storage_type, weather_data)` - Evaporation losses
   - `calculate_storage_costs(capacity_m3, storage_type)` - Capital costs

3. **Irrigation**:
   - `get_irrigation_efficiency(irrigation_type)` - Efficiency lookup
   - `calculate_irrigation_demand_adjustment(base_demand, irrigation_type)` - Adjust for efficiency

4. **Processing**:
   - `validate_processing_capacity(processing_config, equipment_specs)` - Capacity validation
   - `calculate_processing_energy_demand(processing_config, daily_throughput)` - Total energy
   - `calculate_processing_labor_demand(processing_config, daily_throughput)` - Total labor

5. **Community**:
   - `calculate_household_demand(community_config, housing_data)` - Energy and water demand

6. **Main Function**:
   - `calculate_infrastructure(scenario)` - Main function that calls all calculations and returns structured results

**Test**: Run calculations on loaded scenario and verify all values are reasonable

---

## Execution Instructions

### For Phase 0 (Research Tasks):

**Launch 9 parallel agents** with the following assignments:

```
Agent 1: [Copy Agent 1 task description above]
Agent 2: [Copy Agent 2 task description above]
Agent 3: [Copy Agent 3 task description above]
Agent 4: [Copy Agent 4 task description above]
Agent 5: [Copy Agent 5 task description above]
Agent 6: [Copy Agent 6 task description above]
Agent 7: [Copy Agent 7 task description above]
Agent 8: [Copy Agent 8 task description above]
Agent 9: [Copy Agent 9 task description above]
```

**Each agent should**:
1. Review existing data files to understand format
2. Research appropriate specifications
3. Create/update CSV file with metadata header
4. Validate file format matches existing files
5. Report completion and file location

**After all Phase 0 agents complete**:
- Review all created/updated files
- Validate data consistency
- Proceed to Phase 1 implementation

### For Phase 1 (Implementation Tasks):

**Launch 3 sequential agents** (can be parallel after loader is updated):

```
Agent 10: [Copy Agent 10 task description above]
Agent 11: [Copy Agent 11 task description above] - Wait for Agent 10
Agent 12: [Copy Agent 12 task description above] - Wait for Agent 10
```

**After all agents complete**:
- Run full validation: `python settings/scripts/validation.py settings/scenarios/water_policy_testing.yaml`
- Test loader: `python -c "from settings.scripts.loader import load_scenario; s = load_scenario('settings/scenarios/water_policy_testing.yaml'); print(s)"`
- Test calculations: `python -c "from settings.scripts.loader import load_scenario; from settings.scripts.calculations import calculate_infrastructure; s = load_scenario('settings/scenarios/water_policy_testing.yaml'); calc = calculate_infrastructure(s); print(calc)"`

---

## Success Criteria

**Phase 0 Complete When**:
- ✅ All 9 data files created/updated
- ✅ Files follow existing format with metadata headers
- ✅ Data appropriate for Egyptian community farm context
- ✅ Files validated for format consistency

**Phase 1 Complete When**:
- ✅ Loader.py successfully loads `water_policy_testing.yaml`
- ✅ Validation.py passes all checks
- ✅ Calculations.py produces reasonable results
- ✅ All tests pass

---

**End of Implementation Prompt**
