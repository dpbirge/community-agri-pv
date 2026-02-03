# Community Agri-PV Simulation Model

An educational simulation tool for farming communities exploring co-ownership models for water, energy, and agricultural systems. Simulates a collective farm in the Sinai Peninsula, Egypt (hot arid climate, year-round irrigation) to help communities understand trade-offs between infrastructure configurations, policies, and risk management strategies.

## Tech Stack

- **Language**: Python 3.12
- **Key Libraries**: pandas, numpy, pyyaml, matplotlib
- **Data Format**: CSV with embedded metadata headers
- **Configuration**: YAML scenario files and data registry

## Architecture

Three-layer computational model with strict separation of concerns:

1. **Layer 1 (Pre-computation)**: Generates physical reference libraries (weather, PV/wind output, crop irrigation demand) - runs once before simulation
2. **Layer 2 (Design)**: Configures infrastructure, community structure, and policy selections from scenario YAML files
3. **Layer 3 (Simulation)**: Daily time-step simulation executing policies, tracking physical flows, and recording economics

Layers interact through read-only data contracts. Layer 3 cannot re-compute physics or modify designs during execution.

## Directory Structure

- `/data` - All simulation datasets
  - `/parameters` - Static parameters (crops, equipment, labor, community, costs)
  - `/precomputed` - Layer 1 outputs (weather, PV/wind, irrigation, yields, microclimate)
  - `/prices` - Historical price time-series (crops, processed, electricity, water, diesel)
  - `/scripts` - Data generation scripts (Layer 1)
- `/docs` - Documentation
  - `/codereview` - Code review notes
  - `/planning` - Model specifications and implementation plans
  - `/prompts` - AI assistant prompts for development workflows
  - `/research` - Empty (planned for scientific methodology)
  - `/validation` - Data validation reports
- `/notebooks` - Jupyter notebooks for interactive analysis
- `/results` - Simulation outputs (timestamped folders with CSV, JSON, plots)
- `/scripts` - Legacy (moved to `/data/scripts`)
- `/settings` - Layer 2 configuration
  - `/policies` - Policy implementations (water functional, others stubbed)
  - `/scenarios` - Scenario YAML configurations
  - `/scripts` - Configuration utilities (loader, validation, calculations)
- `/src` - Layer 3 simulation engine (water simulation MVP)
- `/testing` - Empty (test files planned)

## Key Files

**Simulation Engine (Layer 3):**

- [simulation.py](src/simulation.py) - Main simulation loop (`run_simulation()`)
- [state.py](src/state.py) - State management dataclasses (SimulationState, FarmState, CropState)
- [data_loader.py](src/data_loader.py) - Data loading and caching (`SimulationDataLoader`)
- [metrics.py](src/metrics.py) - Metrics calculation (`compute_all_metrics()`, `compare_policies()`)
- [results.py](src/results.py) - Output generation (CSV, JSON, matplotlib plots)

**Configuration (Layer 2):**

- [loader.py](settings/scripts/loader.py) - Scenario loader: loads YAML scenarios into structured dataclasses
- [data_registry.yaml](settings/data_registry.yaml) - Central registry for all data file paths
- [validation.py](settings/scripts/validation.py) - Validates registry files exist and scenarios are valid
- [water_policies.py](settings/policies/water_policies.py) - 4 functional water allocation policies

**Data Generation (Layer 1):**

- [generate_weather_data.py](data/scripts/generate_weather_data.py) - 15-year synthetic weather for Sinai (~28N, 34E)
- [generate_crop_parameters.py](data/scripts/generate_crop_parameters.py) - Crop coefficients, growth stages, processing specs
- [generate_irrigation_and_yields.py](data/scripts/generate_irrigation_and_yields.py) - FAO Penman-Monteith irrigation demand and yield calculations
- [generate_power_data.py](data/scripts/generate_power_data.py) - PV and wind normalized power output

**Planning:**

- [community-model-plan.md](docs/planning/community-model-plan.md) - Complete model specifications
- [data-organization.md](docs/planning/data-organization.md) - Data structure and format specifications
- [water_simulation_mvp_plan.md](docs/planning/water_simulation_mvp_plan.md) - Water simulation implementation plan

## Key Functions

- `src.simulation.run_simulation(scenario)` - Main entry point, runs daily loop, returns SimulationState
- `src.results.write_results(state, scenario)` - Generates all output files and plots
- `settings.scripts.loader.load_scenario(path)` - Loads YAML scenario, returns Scenario dataclass
- `settings.policies.get_water_policy(name, **kwargs)` - Factory function to instantiate water policies
- `BaseWaterPolicy.allocate_water(ctx)` - Policy pattern: takes WaterPolicyContext, returns WaterAllocation

## Conventions

- **Policy pattern**: Policies are classes with `allocate_*` methods taking context objects, returning allocation results
- **Configuration**: Scenarios reference policies by name; data files referenced via central registry
- **Layer separation**: Layer 3 cannot modify Layer 1 or Layer 2 during execution
- **Data format**: CSV files with metadata headers; filename suffixes: `-toy` (synthetic), `-research` (empirical), `-real` (measured)

## Project Context

- **Location**: Sinai Peninsula, Red Sea coast, Egypt (~28°N, 34°E)
- **Climate**: Hot arid, negligible rainfall, year-round irrigation required
- **Community**: 20 farms, 500 hectares farmland, ~150 population
- **Crops**: Tomato, potato, onion, kale, cucumber
- **Infrastructure**: Agri-PV (fixed-tilt 28°), wind turbines, battery storage, brackish groundwater desalination, drip irrigation
- **Data**: 50 toy datasets (complete), 14 research datasets (in progress), 5,479 days weather data (2010-2024)

## Development

- **Run simulation**:
  ```bash
  python src/results.py settings/scenarios/water_policy_only.yaml
  ```
- **Validate scenario**:
  ```bash
  python settings/scripts/validation.py settings/scenarios/water_policy_only.yaml
  ```
- **Validate data registry**:
  ```bash
  python settings/scripts/validation.py --registry
  ```
- **Regenerate data**:
  ```bash
  python data/scripts/generate_weather_data.py
  ```
- **Test**: TBD
- **Build**: TBD

## Development Phases

Model is built incrementally per the implementation guide in the model plan:

1. ✅ Layer 1 libraries (pre-compute physical data) - **COMPLETE**
2. ✅ Layer 2 configuration (scenarios, policies, data registry) - **COMPLETE**
   - ✅ Scenario loader (YAML → dataclasses)
   - ✅ Water policies (4 functional policies)
   - ✅ Data registry system
   - ⏳ Energy/crop/economic/market policies (stubbed)
3. ✅ Water simulation MVP - **COMPLETE**
   - ✅ Daily simulation loop
   - ✅ Multi-farm water policy comparison
   - ✅ Yearly metrics and output generation
   - ✅ Visualization plots
4. Physical systems (single farm, deterministic)
5. Scale to 3 farms
6. Add policies and events
7. Post-harvest system
8. Economic system
9. Multi-year simulation
10. Stochastic elements
11. Monte Carlo capability
12. Scale to full community (20+ farms)
13. Scenario comparison and reporting

## Next Steps

**Immediate priorities:**

1. **Extend Layer 3** - Add energy tracking to water simulation
   - Track PV/wind generation alongside water treatment
   - Add energy constraints to water allocation
   - Compare policy outcomes with limited energy

2. **Complete Layer 2 policies** - Implement remaining policy types
   - Energy policies: battery charging/discharging, grid import/export
   - Crop policies: planting schedules, harvest timing
   - Economic policies: pricing, cost allocation, profit distribution

3. **Testing infrastructure** - Set up test framework
   - Unit tests for water policies
   - Integration tests for simulation
   - Validation tests for scenarios

4. **Research datasets** - Complete remaining research-grade datasets
   - Replace synthetic values with empirically-grounded data
   - Validate against real-world measurements
