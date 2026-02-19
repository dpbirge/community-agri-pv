# Source Code (Layer 3: Simulation Engine)

Simulation engine for the Community Agri-PV model. Runs daily time-step simulations comparing water, energy, crop, food processing, economic, and market policies across multiple farms.

## Architecture

The simulation engine runs a daily time-step loop that:
1. Calculates irrigation demand for each farm based on active crops
2. Dispatches energy from PV, wind, battery, grid, and diesel sources
3. Executes water policies to determine groundwater vs municipal allocation
4. Applies crop management policies (irrigation adjustments)
5. Processes harvests through food processing policies
6. Tracks all physical flows, costs, yields, and economic state
7. Generates yearly metrics and comparison reports

## Module Structure

```
src/
├── __init__.py
├── plotting/                  # Visualization modules
│   ├── __init__.py
│   ├── notebook_plotting.py   # Interactive plotting and tables for Jupyter notebooks
│   └── validation_plots.py    # Data validation visualizations
├── policies/                  # Policy implementations (6 domains, 22 policies)
│   ├── __init__.py            # Policy registry and factory functions
│   ├── water_policies.py      # 5 water allocation policies
│   ├── energy_policies.py     # 3 energy dispatch policies
│   ├── food_policies.py       # 4 food processing policies
│   ├── crop_policies.py       # 3 crop management policies
│   ├── economic_policies.py   # 4 economic strategy policies
│   └── market_policies.py     # 3 market timing policies
├── settings/                  # Configuration utilities
│   ├── __init__.py
│   ├── loader.py              # Scenario loader (YAML → dataclasses)
│   ├── validation.py          # Registry and scenario validation
│   └── calculations.py        # Derived calculations (pumping energy, costs, demand)
└── simulation/                # Simulation engine
    ├── __init__.py
    ├── simulation.py          # Main simulation loop (run_simulation())
    ├── state.py               # State management dataclasses
    ├── data_loader.py         # Data loading and caching
    ├── metrics.py             # Metrics calculation and policy comparison
    ├── results.py             # Output generation (CSV, JSON, plots)
    ├── sensitivity.py         # Parameter sensitivity analysis
    └── monte_carlo.py         # Monte Carlo simulation framework
```

## Key Modules

### `simulation/simulation.py` - Main simulation loop
- `run_simulation(scenario)` - Entry point, runs daily loop, returns `SimulationState`
- `calculate_system_constraints(scenario)` - Infrastructure capacity allocation per farm
- `dispatch_energy()` - Merit-order energy dispatch (PV → wind → battery → grid → diesel)
- Handles year boundaries (metrics snapshot, crop replanting)

### `simulation/state.py` - State management
- `SimulationState` - Top-level simulation state
- `FarmState` - Per-farm tracking (water, energy, costs, yields)
- `CropState` - Per-crop tracking (planting, harvest, water use)
- `AquiferState`, `WaterStorageState`, `EnergyState`, `EconomicState` - Subsystem states
- `DailyWaterRecord`, `DailyEnergyRecord` - Daily allocation records

### `simulation/data_loader.py` - Data loading
- `SimulationDataLoader` - Loads all precomputed data at startup
- Provides fast daily lookups for irrigation, yields, prices, weather
- `calculate_tiered_cost()` - Tiered utility pricing calculations

### `simulation/metrics.py` - Metrics and comparison
- `compute_yearly_metrics()` - Per-farm derived metrics
- `aggregate_community_metrics()` - Community-wide aggregates
- `compare_policies()` - Policy comparison summaries
- `compute_net_income()` - Net income calculations

### `simulation/results.py` - Output generation
- CSV: yearly_summary, yearly_community_summary, daily_farm_results
- JSON: simulation_config snapshot
- Plots: water use, costs, self-sufficiency, policy comparison

### `simulation/sensitivity.py` - Sensitivity analysis
- One-at-a-time parameter perturbation
- Measures impact on net farm income

### `simulation/monte_carlo.py` - Monte Carlo framework
- Simultaneous random sampling across all parameters
- Price and yield variation with configurable CVs
- Community resilience evaluation under uncertainty

### `plotting/notebook_plotting.py` - Interactive visualization
- Summary tables, monthly metric charts, yearly comparison panels
- Designed for use in Jupyter notebooks with widget-based plot selection

### `plotting/validation_plots.py` - Validation visualization

- Plots for validating data integrity and simulation outputs

## Usage

```bash
# Run simulation with full output
python src/simulation/results.py settings/settings.yaml

# Run simulation (console output only)
python src/simulation/simulation.py settings/settings.yaml
```
