# Community Agri-PV Simulation Model

An educational simulation tool for farming communities exploring co-ownership models for water, energy, and agricultural systems. Simulates a collective farm in the Sinai Peninsula, Egypt (hot arid climate, year-round irrigation) to help communities understand trade-offs between infrastructure configurations, policies, and risk management strategies.

## Tech Stack

- **Language**: Python (planned)
- **Key Libraries**: pvlib (PV power), pandas, numpy
- **Data Format**: CSV with embedded metadata headers
- **Configuration**: YAML scenario files

## Architecture

Three-layer computational model with strict separation of concerns:

1. **Layer 1 (Pre-computation)**: Generates physical reference libraries (weather, PV/wind output, crop irrigation demand) - runs once before simulation
2. **Layer 2 (Design)**: Configures infrastructure, community structure, and policy selections from scenario YAML files
3. **Layer 3 (Simulation)**: Daily time-step simulation executing policies, tracking physical flows, and recording economics

Layers interact through read-only data contracts. Layer 3 cannot re-compute physics or modify designs during execution.

## Directory Structure

- `/src` - Python source code (simulation modules)
- `/scripts` - Utility and data generation scripts
- `/notebooks` - Jupyter notebooks for analysis
- `/testing` - Test files
- `/data/precomputed` - Layer 1 outputs (weather, PV/wind power, irrigation demand, crop yields)
- `/data/parameters` - Static parameters (crops, equipment, labor, community, costs)
- `/data/prices` - Historical price time-series (crops, electricity, water, diesel)
- `/settings/scenarios` - Scenario YAML configurations
- `/settings/policies` - Policy definitions (Python code + docs)
- `/results` - Simulation outputs
- `/docs/planning` - Model specifications and planning documents

## Key Files

**Planning docs:**

- [community-model-plan.md](docs/planning/community-model-plan.md) - Complete model specifications
- [data-organization.md](docs/planning/data-organization.md) - Data structure and format specifications
- [data-generation-orchestration.md](docs/planning/data-generation-orchestration.md) - Dataset generation task breakdown

**Data generation scripts:**

- [generate_weather_data.py](scripts/generate_weather_data.py) - 15-year synthetic weather for Sinai (~28N, 34E)
- [generate_crop_parameters.py](scripts/generate_crop_parameters.py) - Crop coefficients, growth stages, processing specs
- [generate_price_data.py](data/prices/generate_price_data.py) - Historical prices (crops, processed, electricity, water, diesel)

## Data Conventions

- **Filename suffixes**: `-toy` (synthetic data), `-real` (empirical data)
- **Metadata headers**: Every CSV must include SOURCE, DATE, DESCRIPTION, UNITS, LOGIC, DEPENDENCIES, ASSUMPTIONS
- **Normalization**: Layer 1 outputs are normalized (kWh/kW, m³/ha) for linear scaling
- **Currency**: USD for all calculations, original currency documented with conversion rates

## Project Context

- **Location**: Sinai Peninsula, Red Sea coast, Egypt
- **Climate**: Hot arid, negligible rainfall, year-round irrigation required
- **Community**: 20 farms, 500 hectares farmland, ~150 population
- **Crops**: Tomato, potato, onion, kale, cucumber
- **Infrastructure**: Agri-PV (fixed-tilt 28°), wind turbines, battery storage, brackish groundwater desalination, drip irrigation

## Development

- **Status**: Layer 1 data generation in progress - toy datasets being created
- **Run**: `python scripts/generate_weather_data.py` (example)
- **Test**: TBD
- **Build**: TBD

## Development Phases

Model is built incrementally per the implementation guide in the model plan:

1. Layer 1 libraries (pre-compute physical data)
2. Physical systems (single farm, deterministic)
3. Scale to 3 farms
4. Add policies and events
5. Post-harvest system
6. Economic system
7. Multi-year simulation
8. Stochastic elements
9. Monte Carlo capability
10. Scale to full community (20+ farms)
11. Scenario comparison and reporting
