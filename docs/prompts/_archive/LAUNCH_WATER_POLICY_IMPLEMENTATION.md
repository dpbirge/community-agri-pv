# Launch: Water Policy Testing Implementation

**Quick Start**: Use this prompt to launch parallel research agents, then implementation agents.

---

## Phase 0: Launch 9 Parallel Research Agents

Copy and paste the following prompts to launch 9 agents in parallel:

### Agent 1 - Groundwater Wells
```
You are Agent 1 for the Community Agri-PV simulation project.

TASK: Create `data/parameters/equipment/wells-toy.csv` with well specifications for Egyptian community farms.

Read the full task specification: docs/prompts/water_policy_testing_implementation.md (Agent 1 section)

Key requirements:
- Research well drilling costs, pumping energy, and O&M costs for Sinai Peninsula
- Create CSV with columns: well_depth_m, flow_rate_m3_day, pumping_energy_kwh_per_m3, capital_cost_per_well, om_cost_per_year
- Follow format of existing equipment files (check data/parameters/equipment/pv_systems-toy.csv for reference)
- Include metadata header with sources and assumptions
- Focus on small-scale community wells (30-100m depth, 50-200 m³/day flow)

Report when complete with file location.
```

### Agent 2 - Irrigation Systems
```
You are Agent 2 for the Community Agri-PV simulation project.

TASK: Create `data/parameters/equipment/irrigation_systems-toy.csv` with irrigation system specifications.

Read the full task specification: docs/prompts/water_policy_testing_implementation.md (Agent 2 section)

Key requirements:
- Research efficiency and costs for drip, sprinkler, and furrow irrigation
- Create CSV with columns: irrigation_type, efficiency, capital_cost_per_ha, om_cost_per_ha_per_year
- Follow format of existing equipment files
- Include metadata header with sources and assumptions
- Focus on Egyptian community farms, hot arid climate

Report when complete with file location.
```

### Agent 3 - Storage Systems
```
You are Agent 3 for the Community Agri-PV simulation project.

TASK: Create `data/parameters/equipment/storage_systems-toy.csv` with water storage specifications.

Read the full task specification: docs/prompts/water_policy_testing_implementation.md (Agent 3 section)

Key requirements:
- Research evaporation rates and costs for underground_tank, surface_tank, reservoir
- Create CSV with columns: storage_type, evaporation_rate_annual_pct, capital_cost_per_m3, om_cost_per_m3_per_year
- Follow format of existing equipment files
- Include metadata header with sources and assumptions
- Focus on hot arid climate (Sinai Peninsula)

Report when complete with file location.
```

### Agent 4 - Generators
```
You are Agent 4 for the Community Agri-PV simulation project.

TASK: Create `data/parameters/equipment/generators-toy.csv` with diesel generator specifications.

Read the full task specification: docs/prompts/water_policy_testing_implementation.md (Agent 4 section)

Key requirements:
- Research fuel consumption, efficiency, and operating characteristics
- Create CSV with columns: generator_type, capacity_kw, fuel_consumption_l_per_kwh, efficiency, min_load_pct, startup_time_min
- Follow format of existing equipment files
- Include metadata header with sources and assumptions
- Focus on small-scale backup generators (50-200 kW)

Report when complete with file location.
```

### Agent 5 - Fresh Food Packaging
```
You are Agent 5 for the Community Agri-PV simulation project.

TASK: Create `data/parameters/equipment/fresh_packaging-toy.csv` with fresh produce packaging specifications.

Read the full task specification: docs/prompts/water_policy_testing_implementation.md (Agent 5 section)

Key requirements:
- Research packaging materials for shipping fresh produce (boxes, crates, bags)
- Create CSV with columns: packaging_type, capacity_kg_per_unit, labor_hours_per_kg, material_cost_per_kg, energy_kwh_per_kg, shelf_life_extension_days
- Follow format of existing equipment files
- Include metadata header with sources and assumptions
- Focus on Egyptian community farms - simple, manual labor, affordable packaging

Report when complete with file location.
```

### Agent 6 - Food Drying
```
You are Agent 6 for the Community Agri-PV simulation project.

TASK: Update `data/parameters/equipment/processing_equipment-toy.csv` or create `drying_equipment-toy.csv` with drying specifications.

Read the full task specification: docs/prompts/water_policy_testing_implementation.md (Agent 6 section)

Key requirements:
- Research simple drying methods (solar drying, simple dehydrators) for Egyptian community farms
- Update existing file or create new with columns: equipment_type, capacity_kg_per_day, energy_kw_continuous, labor_hours_per_kg, capital_cost_usd, maintenance_cost_per_year_usd, lifespan_years
- Follow format of existing equipment files
- Include metadata header with sources and assumptions
- Focus on human labor with simple machines, NOT industrial equipment

Report when complete with file location.
```

### Agent 7 - Food Canning
```
You are Agent 7 for the Community Agri-PV simulation project.

TASK: Update `data/parameters/equipment/processing_equipment-toy.csv` or create `canning_equipment-toy.csv` with canning specifications.

Read the full task specification: docs/prompts/water_policy_testing_implementation.md (Agent 7 section)

Key requirements:
- Research small-scale canning equipment appropriate for Egyptian community farms
- Update existing file or create new with columns: equipment_type, capacity_kg_per_day, energy_kw_continuous, labor_hours_per_kg, capital_cost_usd, maintenance_cost_per_year_usd, lifespan_years
- Follow format of existing equipment files
- Include metadata header with sources and assumptions
- Focus on human labor with simple machines, NOT industrial canning lines

Report when complete with file location.
```

### Agent 8 - Processed Food Packaging
```
You are Agent 8 for the Community Agri-PV simulation project.

TASK: Update `data/parameters/equipment/processing_equipment-toy.csv` or create `processed_packaging-toy.csv` with processed goods packaging specifications.

Read the full task specification: docs/prompts/water_policy_testing_implementation.md (Agent 8 section)

Key requirements:
- Research packaging materials for processed goods (dried, canned) in Egyptian community farm context
- Update existing file or create new with columns: packaging_type, capacity_kg_per_unit, labor_hours_per_kg, material_cost_per_kg, energy_kwh_per_kg
- Follow format of existing equipment files
- Include metadata header with sources and assumptions
- Focus on simple, affordable packaging appropriate for community farms

Report when complete with file location.
```

### Agent 9 - PV Panel Specifications
```
You are Agent 9 for the Community Agri-PV simulation project.

TASK: Update `data/parameters/equipment/pv_systems-toy.csv` to add panel specifications.

Read the full task specification: docs/prompts/water_policy_testing_implementation.md (Agent 9 section)

Key requirements:
- Add columns: panel_wattage_w, panel_area_m2, panels_per_kw
- Research standard polycrystalline panel specifications
- Update existing file (don't break existing format)
- Include metadata updates explaining new columns

Report when complete with file location.
```

---

## Phase 1: Launch Implementation Agents (After Phase 0 Complete)

Wait for all Phase 0 agents to complete and validate their files, then launch:

### Agent 10 - Update Loader
```
You are Agent 10 for the Community Agri-PV simulation project.

TASK: Update `settings/scripts/loader.py` to handle new YAML structure from water_policy_testing.yaml.

Read the full task specification: docs/prompts/water_policy_testing_implementation.md (Agent 10 section)

Key changes:
- Rename capacity_kw → sys_capacity_kw for PV/Wind
- Rename capacity_m3_day → system_capacity_m3_day for water treatment
- Add new fields: type, percent_over_crops, height_m for PV
- Add new dataclasses: GroundwaterWellsConfig, IrrigationStorageConfig, IrrigationSystemConfig, FoodProcessingConfig
- Remove household_size from CommunityConfig
- Add validation for new fields

Test by loading: python -c "from settings.scripts.loader import load_scenario; s = load_scenario('settings/scenarios/water_policy_testing.yaml'); print(s)"

Report when complete.
```

### Agent 11 - Update Validation
```
You are Agent 11 for the Community Agri-PV simulation project.

TASK: Update `settings/scripts/validation.py` to validate new YAML structure.

Read the full task specification: docs/prompts/water_policy_testing_implementation.md (Agent 11 section)

Key changes:
- Add validation for new infrastructure sections
- Add cross-validation checks (treatment capacity vs well capacity, etc.)

Test by running: python settings/scripts/validation.py settings/scenarios/water_policy_testing.yaml

Report when complete.
```

### Agent 12 - Create Calculations Module
```
You are Agent 12 for the Community Agri-PV simulation project.

TASK: Create `settings/scripts/calculations.py` with all calculation functions.

Read the full task specification: docs/prompts/water_policy_testing_implementation.md (Agent 12 section)

Key functions needed:
- Energy: calculate_pv_config, calculate_wind_config, calculate_battery_config, calculate_generator_config
- Water: calculate_well_pumping_energy, calculate_well_costs, calculate_treatment_unit_sizing, calculate_distances, calculate_storage_evaporation, calculate_storage_costs
- Irrigation: get_irrigation_efficiency, calculate_irrigation_demand_adjustment
- Processing: validate_processing_capacity, calculate_processing_energy_demand, calculate_processing_labor_demand
- Community: calculate_household_demand
- Main: calculate_infrastructure(scenario)

Test by running calculations on loaded scenario and verify results are reasonable.

Report when complete.
```

---

## Validation Checklist

After all agents complete:

- [ ] All 9 data files created/updated with proper format
- [ ] Loader.py successfully loads water_policy_testing.yaml
- [ ] Validation.py passes all checks
- [ ] Calculations.py produces reasonable results
- [ ] All tests pass

Run final validation:
```bash
python settings/scripts/validation.py settings/scenarios/water_policy_testing.yaml
python -c "from settings.scripts.loader import load_scenario; from settings.scripts.calculations import calculate_infrastructure; s = load_scenario('settings/scenarios/water_policy_testing.yaml'); calc = calculate_infrastructure(s); print('Calculations complete:', list(calc.keys()))"
```

---

**End of Launch Prompt**
