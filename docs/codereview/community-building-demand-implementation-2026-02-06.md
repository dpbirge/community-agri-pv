# Community Building Demand Implementation

**Date:** 2026-02-06
**Status:** Completed
**Scope:** Add community building energy and water consumption data and integrate into simulation

## Summary

Added complete support for community building (non-residential, non-industrial) energy and water demands, including offices, storage, meeting halls, and maintenance workshops. Data varies daily based on weather/temperature, similar to household demands.

## Changes Made

### 1. Data Files Created

#### Baseline Specifications
- **File:** `data/parameters/community/community_buildings_energy_water-toy.csv`
- **Content:** Building type specifications with energy (0.03-0.15 kWh/m²/day) and water (0.002-0.012 m³/m²/day) demand rates
- **Building types:** office_admin, storage_warehouse, meeting_hall, workshop_maintenance

#### Precomputed Daily Demands
- **Script:** `data/scripts/generate_community_building_demand.py`
  - Generates daily demand files based on weather data
  - Applies temperature-based cooling/ventilation multipliers (20-50% of energy varies with temperature)
  - Supports configurable building areas via command-line arguments

- **Output files:**
  - `data/precomputed/community_buildings/community_buildings_energy_kwh_per_day-toy.csv`
  - `data/precomputed/community_buildings/community_buildings_water_m3_per_day-toy.csv`

- **Default configuration (2000 m² total):**
  - Office: 500 m²
  - Storage: 1000 m²
  - Meeting hall: 300 m²
  - Workshop: 200 m²

- **Daily demand ranges:**
  - Energy: 122.8 - 189.2 kWh/day (varies with temperature)
  - Water: 11.8 - 13.6 m³/day (slight variation with temperature)

### 2. Configuration Schema Updates

#### CommunityConfig Dataclass
- **File:** `src/settings/loader.py`
- **Changes:** Added two fields to `CommunityConfig`:
  ```python
  industrial_buildings_m2: float = 0.0  # Square meters of industrial/processing facilities
  community_buildings_m2: float = 0.0  # Square meters of community buildings (offices, halls, etc.)
  ```

#### Scenario Loader
- **File:** `src/settings/loader.py`
- **Changes:** Updated `CommunityConfig` instantiation to load building square footage from YAML:
  ```python
  industrial_buildings_m2=community_data.get("industrial_buildings_m2", 0.0),
  community_buildings_m2=community_data.get("community_buildings_m2", 0.0),
  ```

#### Data Registry
- **File:** `settings/data_registry.yaml`
- **Changes:** Added registry entries:
  ```yaml
  community:
    buildings: data/parameters/community/community_buildings_energy_water-toy.csv

  community_buildings:
    energy: data/precomputed/community_buildings/community_buildings_energy_kwh_per_day-toy.csv
    water: data/precomputed/community_buildings/community_buildings_water_m3_per_day-toy.csv
  ```

### 3. Calculation Functions

#### New Function: calculate_community_building_demand()
- **File:** `src/settings/calculations.py`
- **Location:** After `calculate_household_demand()`, before `calculate_infrastructure()`
- **Purpose:** Calculate community building energy and water demand based on square footage
- **Returns:** Dict with total_area_m2, total_energy_kwh_day, total_water_m3_day, and per-m² rates

#### Updated: calculate_infrastructure()
- **File:** `src/settings/calculations.py`
- **Changes:** Modified `results["community"]` structure to include both household and buildings:
  ```python
  results["community"] = {
      "household": calculate_household_demand(scenario.community),
      "buildings": calculate_community_building_demand(scenario.community),
  }
  ```

### 4. Data Loader Updates

#### New Load Functions
- **File:** `src/simulation/data_loader.py`
- **Functions added:**
  - `load_household_demand_data(registry, project_root)` - Loads daily household energy/water CSVs
  - `load_community_building_demand_data(registry, project_root)` - Loads daily building energy/water CSVs

#### SimulationDataLoader Class
- **File:** `src/simulation/data_loader.py`
- **__init__ updates:** Added loading of household and community building demand data:
  ```python
  self.household_demand = load_household_demand_data(self.registry, self.project_root)
  self.community_building_demand = load_community_building_demand_data(self.registry, self.project_root)
  ```

- **New getter methods:**
  - `get_household_energy_kwh(target_date)` - Returns total community household energy demand for date
  - `get_household_water_m3(target_date)` - Returns total community household water demand for date
  - `get_community_building_energy_kwh(target_date)` - Returns total community building energy demand for date
  - `get_community_building_water_m3(target_date)` - Returns total community building water demand for date

### 5. Simulation Integration

#### Energy Demand
- **File:** `src/simulation/simulation.py`
- **Changes:**
  - Removed static household energy calculation (previously computed once before loop)
  - Added daily retrieval of household and community building energy demands inside main loop
  - Updated total energy demand calculation:
    ```python
    total_energy_demand_kwh = (day_total_water_energy_kwh +
                               daily_household_energy_kwh +
                               daily_community_building_energy_kwh)
    ```

#### Water Demand
- **File:** `src/simulation/simulation.py`
- **Status:** Household and community building water demands are retrieved daily but **not yet integrated** into water allocation
- **Rationale:** Current water allocation policies focus on irrigation only. Integrating non-irrigation water demands requires updates to the water policy framework
- **Future work:** Add household/community building water to water allocation policies

## Validation

### Test Results
- Scenario loading: ✓ Successfully loads community_buildings_m2 (1000 m²) and industrial_buildings_m2 (2000 m²)
- Data loader: ✓ Successfully loads and retrieves daily demand data
- Sample day (2010-07-15, summer):
  - Household energy: 678.6 kWh/day
  - Community building energy: 189.2 kWh/day
  - **Total energy: 867.8 kWh/day** (now included in energy dispatch)
  - Household water: 17.0 m³/day (data available, not yet used)
  - Community building water: 13.6 m³/day (data available, not yet used)
- Simulation: ✓ Runs successfully with new demand components

### Impact on Energy Dispatch
- Previous: Water treatment/pumping energy + static household energy
- New: Water treatment/pumping energy + **daily-varying household energy** + **daily-varying community building energy**
- Community building energy adds ~120-190 kWh/day depending on temperature
- Total community energy demand now more accurately reflects actual loads

## Configuration Example

To use community building demands in a scenario YAML file:

```yaml
community_structure:
  community_area_km2: 1000
  total_farms: 1
  total_farming_area_ha: 125
  community_population: 30
  houses: 10
  industrial_buildings_m2: 2000  # Food processing facilities (energy handled separately)
  community_buildings_m2: 1000   # Offices, storage, halls, workshops
```

To regenerate community building demand files with different building areas:

```bash
python data/scripts/generate_community_building_demand.py \
  --office 500 \
  --storage 1000 \
  --meeting 300 \
  --workshop 200
```

## Notes

1. **Industrial vs. Community Buildings:**
   - `industrial_buildings_m2` refers to food processing facilities (energy demand handled separately via processing equipment specs)
   - `community_buildings_m2` refers to non-residential, non-industrial buildings (offices, storage, meeting halls, workshops)

2. **Household Water Now Available:**
   - As a side effect of this work, household water demand data is now loaded and available
   - Previously, only household energy was used; water demand was calculated but never loaded
   - Both household and community building water demands can be integrated into water policies in future work

3. **Temperature Sensitivity:**
   - Community building energy demand varies 20-50% with temperature (depending on building type)
   - Offices have highest temperature sensitivity (50% cooling fraction)
   - Storage has lowest (20% ventilation fraction)

4. **Data Quality:**
   - Current data is synthetic ("toy" dataset)
   - Based on reasonable engineering estimates for hot arid climate
   - Should be replaced with measured data or Egyptian building energy standards for research-grade simulations

## Files Modified

**New files (7):**
- `data/parameters/community/community_buildings_energy_water-toy.csv`
- `data/scripts/generate_community_building_demand.py`
- `data/precomputed/community_buildings/community_buildings_energy_kwh_per_day-toy.csv`
- `data/precomputed/community_buildings/community_buildings_water_m3_per_day-toy.csv`
- `docs/codereview/community-building-demand-implementation-2026-02-06.md` (this file)

**Modified files (4):**
- `src/settings/loader.py` - Added building fields to CommunityConfig and loader
- `src/settings/calculations.py` - Added calculate_community_building_demand() function
- `src/simulation/data_loader.py` - Added load functions and getter methods
- `src/simulation/simulation.py` - Integrated daily demands into energy dispatch
- `settings/data_registry.yaml` - Added community building data paths
