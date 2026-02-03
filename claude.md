# Community Agri-PV Simulation Model

An educational simulation tool for farming communities exploring co-ownership models for water, energy, and agricultural systems. Simulates a collective farm in the Sinai Peninsula, Egypt (hot arid climate, year-round irrigation) to help communities understand trade-offs between infrastructure configurations, policies, and risk management strategies.

## Tech Stack

- **Language**: Python 3.x
- **Key Libraries**: pandas, numpy, pyyaml (pvlib planned for enhanced PV modeling)
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
  - `/data/parameters` - Static parameters (crops, equipment, labor, community, costs)
  - `/data/precomputed` - Layer 1 outputs (weather, PV/wind power, irrigation demand, crop yields, water treatment, microclimate)
  - `/data/prices` - Historical price time-series (crops, processed goods, electricity, water, diesel)
  - `/data/scripts` - Data generation scripts (Layer 1)
- `/docs` - Documentation
  - `/docs/codereview` - Empty (planned for code review notes)
  - `/docs/planning` - Model specifications and implementation plans
  - `/docs/prompts` - AI assistant prompts for development workflows
  - `/docs/research` - Empty (planned for scientific methodology documentation)
  - `/docs/validation` - Data validation reports
- `/notebooks` - Jupyter notebooks for interactive analysis and testing
- `/results` - Empty (simulation outputs will be written here)
- `/scripts` - Empty (legacy, scripts moved to `/data/scripts`)
- `/settings` - Layer 2 configuration (scenarios, policies, data registry)
  - `/settings/policies` - Policy implementations (water policies functional, others stubbed)
  - `/settings/scenarios` - Scenario YAML configurations
  - `/settings/scripts` - Configuration utilities (loader, validation)
- `/src` - Empty (Layer 3 simulation engine code - planned)
- `/testing` - Empty (test files - planned)

## Key Files

**Planning docs:**

- [community-model-plan.md](docs/planning/community-model-plan.md) - Complete model specifications
- [data-organization.md](docs/planning/data-organization.md) - Data structure and format specifications
- [data-generation-orchestration.md](docs/planning/data-generation-orchestration.md) - Dataset generation task breakdown

**Data generation scripts (Layer 1):**

- [generate_weather_data.py](data/scripts/generate_weather_data.py) - 15-year synthetic weather for Sinai (~28N, 34E)
- [generate_crop_parameters.py](data/scripts/generate_crop_parameters.py) - Crop coefficients, growth stages, processing specs
- [generate_price_data.py](data/scripts/generate_price_data.py) - Historical prices (crops, processed, electricity, water, diesel)
- [generate_irrigation_and_yields.py](data/scripts/generate_irrigation_and_yields.py) - FAO Penman-Monteith irrigation demand and yield calculations
- [generate_power_data.py](data/scripts/generate_power_data.py) - PV and wind normalized power output

**Configuration (Layer 2):**

- [loader.py](settings/scripts/loader.py) - Scenario loader: loads YAML scenarios into structured dataclasses
- [data_registry.yaml](settings/data_registry.yaml) - Central registry for all data file paths
- [validation.py](settings/scripts/validation.py) - Validates registry files exist and scenarios are valid
- [water_policies.py](settings/policies/water_policies.py) - 4 functional water allocation policies
- [toy_4farm.yaml](settings/scenarios/toy_4farm.yaml) - Example scenario with 4 farms and distinct policies

**Validation:**

- [data_generation_validation_report.md](docs/validation/data_generation_validation_report.md) - Layer 1 toy dataset validation (all 11 tasks passed)

## Key Functions

- `settings.scripts.loader.load_scenario(path)` - Loads YAML scenario file, instantiates policies, returns Scenario dataclass
- `settings.policies.get_water_policy(name, **kwargs)` - Factory function to instantiate water policies by name
- `BaseWaterPolicy.allocate_water(ctx)` - Policy pattern: takes WaterPolicyContext, returns WaterAllocation with groundwater/municipal split and costs
- `data/scripts/generate_*.py` - Each script has a `main()` function that generates and validates datasets

## Conventions

- **Policy pattern**: Policies are classes with `allocate_*` methods taking context objects, returning allocation results
- **Configuration**: Scenarios reference policies by name; data files referenced via central registry (`data_registry.yaml`)
- **Layer separation**: Layer 3 (simulation) cannot modify Layer 1 (precomputed) or Layer 2 (design) during execution
- **Data format**: CSV files with metadata headers; filename suffixes: `-toy` (synthetic), `-research` (empirical), `-real` (measured)

## Project Context

- **Location**: Sinai Peninsula, Red Sea coast, Egypt (~28°N, 34°E)
- **Climate**: Hot arid, negligible rainfall, year-round irrigation required
- **Community**: 20 farms, 500 hectares farmland, ~150 population
- **Crops**: Tomato, potato, onion, kale, cucumber
- **Infrastructure**: Agri-PV (fixed-tilt 28°), wind turbines, battery storage, brackish groundwater desalination, drip irrigation
- **Data**: 50 toy datasets (complete), 14 research datasets (in progress), 5,479 days weather data (2010-2024)

## Development

- **Status**: Layer 1 complete (toy datasets validated), Layer 2 partially complete (scenarios/policies implemented), research datasets in progress
- **Run**: 
  - `python data/scripts/generate_weather_data.py` (regenerates weather data)
  - `python settings/scripts/validation.py --registry` (validate data registry)
  - `python settings/scripts/validation.py settings/scenarios/toy_4farm.yaml` (validate scenario)
- **Test**: TBD
- **Build**: TBD

## Development Phases

Model is built incrementally per the implementation guide in the model plan:

1. ✅ Layer 1 libraries (pre-compute physical data) - **COMPLETE**
2. ✅ Layer 2 configuration (scenarios, policies, data registry) - **PARTIALLY COMPLETE**
   - ✅ Scenario loader (YAML → dataclasses)
   - ✅ Water policies (4 functional policies)
   - ✅ Data registry system
   - ⏳ Energy/crop/economic/market policies (stubbed)
3. Physical systems (single farm, deterministic)
4. Scale to 3 farms
5. Add policies and events
6. Post-harvest system
7. Economic system
8. Multi-year simulation
9. Stochastic elements
10. Monte Carlo capability
11. Scale to full community (20+ farms)
12. Scenario comparison and reporting

## Next Steps

**Immediate priorities:**

1. **Complete Layer 2 policies** - Implement energy, crop, economic, and market policies (currently stubbed)
   - Energy policies: battery charging/discharging, grid import/export decisions
   - Crop policies: planting schedules, harvest timing, crop selection
   - Economic policies: pricing strategies, cost allocation, profit distribution
   - Market policies: sale timing, storage decisions, price negotiation

2. **Begin Layer 3 (Simulation Engine)** - Start with Phase 3: Physical systems for a single farm
   - Create `/src` directory structure for simulation modules
   - Implement daily time-step loop
   - Build physical flow tracking (water, energy, crops)
   - Add material balance reconciliation

3. **Research datasets** - Complete remaining research-grade datasets (14 files in progress)
   - Replace synthetic values with empirically-grounded data from literature
   - Validate against real-world measurements where available

4. **Testing infrastructure** - Set up test framework
   - Create `/testing` directory
   - Add unit tests for policies
   - Add integration tests for data generation scripts
   - Add validation tests for scenario loading

5. **Documentation** - Complete implementation guides
   - Layer 3 architecture specification
   - Policy development guide
   - Simulation execution workflow
