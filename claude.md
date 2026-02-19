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

- `/data` - All simulation datasets (99 CSV files)
  - `/parameters` - Static parameters: crops, equipment, labor, community, costs, economic, water (42 files)
  - `/precomputed` - Layer 1 outputs: weather, PV/wind, irrigation, yields, microclimate, household, community buildings (22 files)
  - `/prices` - Historical price time-series: crops, processed, electricity, water, diesel, inputs (35 files)
  - `/scripts` - Data generation scripts (8 Python files, Layer 1)
- `/docs` - Documentation
  - `/arch` - Core model specifications (6 docs)
  - `/codereview` - Code review reports and archive
  - `/planning` - Implementation plans
  - `/prompts` - AI assistant prompts
- `/notebooks` - Jupyter notebooks for interactive analysis
  - `run_simulation.ipynb` - Primary simulation runner with interactive plots
  - `validations.ipynb` - Data validation and inspection
  - `/exports` - CSV exports from notebook sessions
- `/results` - Simulation outputs (timestamped folders with CSV, JSON, plots)
- `/scripts` - Test plotting scripts (test_plot1-6)
- `/settings` - Layer 2 configuration
  - `data_registry.yaml` - Central registry for all data file paths
  - `settings.yaml` - Active scenario configuration
- `/src` - Layer 3 simulation engine
  - `/plotting` - Visualization modules (notebook plotting, validation plots)
  - `/policies` - Policy implementations (6 domains, 22 total policies)
  - `/settings` - Configuration utilities (loader, validation, calculations)
  - `/simulation` - Simulation engine (state, data_loader, metrics, results, sensitivity, monte_carlo)
- `/testing` - Test files (not yet implemented)

## Key Files

**Simulation Engine (Layer 3):**

- [simulation.py](src/simulation/simulation.py) - Main simulation loop (`run_simulation()`) with energy dispatch
- [state.py](src/simulation/state.py) - State management dataclasses (SimulationState, FarmState, CropState, AquiferState, EnergyState, EconomicState)
- [data_loader.py](src/simulation/data_loader.py) - Data loading and caching (`SimulationDataLoader`)
- [metrics.py](src/simulation/metrics.py) - Metrics calculation (`compute_all_metrics()`, `compare_policies()`, `compute_net_income()`)
- [results.py](src/simulation/results.py) - Output generation (CSV, JSON, matplotlib plots)
- [sensitivity.py](src/simulation/sensitivity.py) - Parameter sensitivity analysis
- [monte_carlo.py](src/simulation/monte_carlo.py) - Monte Carlo simulation framework

**Policies (Layer 2):**

- [water_policies.py](src/policies/water_policies.py) - 5 water allocation policies
- [energy_policies.py](src/policies/energy_policies.py) - 3 energy dispatch policies (merit-order parameters)
- [food_policies.py](src/policies/food_policies.py) - 4 food processing policies
- [crop_policies.py](src/policies/crop_policies.py) - 3 crop management policies
- [economic_policies.py](src/policies/economic_policies.py) - 4 economic strategy policies
- [market_policies.py](src/policies/market_policies.py) - 3 market timing policies

**Configuration (Layer 2):**

- [loader.py](src/settings/loader.py) - Scenario loader: loads YAML scenarios into structured dataclasses
- [data_registry.yaml](settings/data_registry.yaml) - Central registry for all data file paths
- [validation.py](src/settings/validation.py) - Validates registry files exist and scenarios are valid
- [calculations.py](src/settings/calculations.py) - Derived calculations (pumping energy, infrastructure costs, household demand)

**Data Generation (Layer 1):**

- [generate_weather_data.py](data/scripts/generate_weather_data.py) - 15-year synthetic weather for Sinai (~28N, 34E)
- [generate_crop_parameters.py](data/scripts/generate_crop_parameters.py) - Crop coefficients, growth stages, processing specs
- [generate_irrigation_and_yields.py](data/scripts/generate_irrigation_and_yields.py) - FAO Penman-Monteith irrigation demand and yield calculations
- [generate_power_data.py](data/scripts/generate_power_data.py) - PV and wind normalized power output
- [generate_price_data.py](data/scripts/generate_price_data.py) - Historical price time-series
- [generate_household_demand.py](data/scripts/generate_household_demand.py) - Household energy and water demand
- [generate_community_building_demand.py](data/scripts/generate_community_building_demand.py) - Community building energy and water demand
- [generate_missing_processed_prices.py](data/scripts/generate_missing_processed_prices.py) - Fill gaps in processed product price data

**Visualization:**

- [notebook_plotting.py](src/plotting/notebook_plotting.py) - Interactive plotting and tables for Jupyter notebooks
- [validation_plots.py](src/plotting/validation_plots.py) - Data validation visualizations
- [run_simulation.ipynb](notebooks/run_simulation.ipynb) - Primary simulation notebook with widget-based plot selection

**Architecture & Planning:**

- [overview.md](docs/arch/overview.md) - Complete model domain specifications
- [structure.md](docs/arch/structure.md) - Configuration schema and policy structure
- [calculations.md](docs/arch/calculations.md) - Calculation methodologies and formulas
- [policies.md](docs/arch/policies.md) - Policy decision rules and pseudocode
- [data.md](docs/arch/data.md) - Data structure and format specifications
- [simulation_flow.md](docs/arch/simulation_flow.md) - Simulation execution flow and daily loop logic

## Key Functions

- `src.simulation.simulation.run_simulation(scenario)` - Main entry point, runs daily loop, returns SimulationState
- `src.simulation.simulation.dispatch_energy(...)` - Merit-order energy dispatch (PV → wind → battery → grid → diesel)
- `src.simulation.simulation.calculate_system_constraints(scenario)` - Per-farm infrastructure capacity allocation
- `src.simulation.results.write_results(state, scenario)` - Generates all output files and plots
- `src.simulation.metrics.compute_all_metrics(state)` - Computes yearly and community metrics
- `src.simulation.metrics.compare_policies(state)` - Cross-policy comparison summaries
- `src.simulation.sensitivity.run_sensitivity(...)` - One-at-a-time parameter sensitivity analysis
- `src.simulation.monte_carlo.run_monte_carlo(...)` - Stochastic simulation with random sampling
- `src.settings.loader.load_scenario(path)` - Loads YAML scenario, returns Scenario dataclass
- `src.settings.calculations.calculate_pumping_energy(...)` - Well pumping energy requirements
- `src.policies.get_water_policy(name, **kwargs)` - Factory function to instantiate water policies
- `BaseWaterPolicy.allocate_water(ctx)` - Policy pattern: takes WaterPolicyContext, returns WaterAllocation

## Conventions

- **Policy pattern**: Policies are classes with `allocate_*` or `decide_*` methods taking context dataclasses, returning allocation/decision dataclasses
- **Factory functions**: Each policy domain has `get_*_policy(name)` for lookup by scenario YAML name
- **Configuration**: Scenarios reference policies by name; data files referenced via central registry
- **Layer separation**: Layer 3 cannot modify Layer 1 or Layer 2 during execution
- **Data format**: CSV files with metadata headers; filename suffixes: `-toy` (synthetic), `-research` (empirical), `-real` (measured)
- **State management**: Dataclasses for all state; daily records appended to lists; yearly metrics snapshotted at year boundaries

## Project Context

- **Location**: Sinai Peninsula, Red Sea coast, Egypt (~28°N, 34°E)
- **Climate**: Hot arid, negligible rainfall, year-round irrigation required
- **Community**: 20 farms, 500 hectares farmland, ~150 population
- **Crops**: Tomato, potato, onion, kale, cucumber
- **Infrastructure**: Agri-PV (fixed-tilt 28°), wind turbines, battery storage, brackish groundwater desalination, drip irrigation
- **Data**: 99 datasets (toy + research), 5,479 days weather data (2010-2024)

## Development

- **Run simulation**: `python src/simulation/results.py settings/settings.yaml`
- **Validate scenario**: `python src/settings/validation.py settings/settings.yaml`
- **Validate data registry**: `python src/settings/validation.py --registry`
- **Regenerate data**: `python data/scripts/generate_weather_data.py`
- **Test**: TBD
- **Build**: TBD

## Development Phases

Model is built incrementally per the implementation guide in the model plan:

1. ✅ Layer 1 libraries (pre-compute physical data) - **COMPLETE**
2. ✅ Layer 2 configuration (scenarios, policies, data registry) - **COMPLETE**
   - ✅ Scenario loader (YAML → dataclasses)
   - ✅ All 6 policy types implemented (water, energy, food, crop, economic, market)
   - ✅ Data registry system
3. ✅ Water simulation MVP - **COMPLETE**
   - ✅ Daily simulation loop with energy dispatch
   - ✅ Multi-farm water policy comparison
   - ✅ Yearly metrics and output generation
   - ✅ Visualization plots and interactive notebook
4. Physical systems (single farm, deterministic)
5. Scale to 3 farms
6. Add policies and events
7. Post-harvest system
8. Economic system
9. Multi-year simulation
10. Stochastic elements
11. Monte Carlo capability (framework implemented in `monte_carlo.py`)
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
