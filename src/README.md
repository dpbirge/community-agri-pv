# Source Code (Layer 3: Simulation Engine)

Water simulation MVP implementation for comparing water allocation policies across multiple farms.

## Architecture

The simulation engine runs a daily time-step loop that:
1. Calculates irrigation demand for each farm based on active crops
2. Executes water policies to determine groundwater vs municipal allocation
3. Tracks water usage, costs, and yields
4. Generates yearly metrics and comparison reports

## Modules

- **simulation.py** - Main simulation loop (`run_simulation()`)
  - Processes daily water allocation for each farm
  - Handles year boundaries (metrics snapshot, crop replanting)
  - Supports multi-year simulation with configurable scenarios

- **state.py** - State management dataclasses
  - `SimulationState` - Top-level simulation state
  - `FarmState` - Per-farm tracking (water, costs, yields)
  - `CropState` - Per-crop tracking (planting, harvest, water use)
  - `DailyWaterRecord` - Daily allocation records

- **data_loader.py** - Data loading and caching
  - `SimulationDataLoader` - Loads all precomputed data at startup
  - Provides fast daily lookups for irrigation, yields, prices

- **metrics.py** - Metrics calculation
  - `compute_yearly_metrics()` - Per-farm derived metrics
  - `aggregate_community_metrics()` - Community-wide aggregates
  - `compare_policies()` - Policy comparison summaries

- **results.py** - Output generation
  - CSV files: yearly_summary, yearly_community_summary, daily_farm_results
  - JSON: simulation_config snapshot
  - Plots: water use, costs, self-sufficiency, policy comparison

## Usage

```bash
# Run simulation with output
python src/results.py settings/scenarios/water_policy_only.yaml

# Run simulation (console output only)
python src/simulation.py settings/scenarios/water_policy_only.yaml
```

## Key Functions

- `run_simulation(scenario)` - Main entry point, returns SimulationState
- `write_results(state, scenario)` - Generates all outputs to results/

## Status

Water simulation MVP complete. Supports:
- Multi-farm simulation with different water policies
- 10-year simulation periods
- 4 water allocation policies
- Yearly metrics and policy comparison

Energy, crop, and economic simulations planned for future phases.
