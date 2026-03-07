# Community Agri-PV Simulation

Educational simulation for a farming community co-ownership model combining solar PV, wind energy, and irrigated agriculture in the Sinai Peninsula, Egypt. Uses a three-layer architecture: pre-computed physical data (Layer 1), scenario configuration (Layer 2), and daily time-step simulation engine (Layer 3).

## Tech Stack

- Python 3.12+
- pandas, numpy (data processing and simulation)
- matplotlib (visualization)
- PyYAML (configuration)
- Jupyter notebooks (user interface)
- pytest (testing)

## Architecture

Functional programming throughout — no classes, no stateful data. Each `src/` module follows a consistent pattern: `_load_yaml()` / `_load_csv()` internal helpers, `_resolve_*_paths()` for registry-based path resolution, `_scale_*()` for per-unit to community-total scaling, and a `compute_*()` / `save_*()` / `load_*()` public API. Internal helpers are prefixed with `_`; public functions use keyword arguments with defaults. Configuration is composed via YAML files: a scenario file references domain-specific settings files, which reference data files through a central data registry.

## Directory Structure

- `/data` - Pre-computed physical data libraries (Layer 1)
    - `./_plotting` - Data validation notebooks (crop growth, weather scenarios)
    - `./_scripts` - Data generation scripts (generate_*.py)
    - `./building_demands` - Household and community building energy/water per unit
    - `./crops` - Crop growth parameters and daily growth CSVs by crop/planting/condition
    - `./economics` - Capital costs, operating costs, equipment specs
    - `./energy` - PV and wind daily output CSVs, system specs
    - `./food_processing` - Post-harvest processing specs
    - `./labor` - Labor requirements and wages
    - `./prices` - Historical prices (crops, electricity, diesel, water, processed food)
    - `./water` - Wells, pumps, treatment, storage, irrigation system specs
    - `./weather` - Daily weather CSVs (openfield + underpv variants)
- `/docs` - Project documentation
    - `./codereview` - Code review and investigation reports
    - `./planning` - Design and modeling docs
    - `./plans` - Feature implementation plans
    - `./prompts` - Reusable prompt templates
- `/notebooks` - User-facing Jupyter notebooks
    - `./helpers` - Analysis and debugging notebooks (water balance viz, energy checks, sizing)
- `/scenarios` - Scenario composition files (Layer 2 entry points)
- `/settings` - Domain-specific YAML configuration files (Layer 2)
- `/simulation` - Output CSVs from simulation runs (Layer 3 outputs)
- `/specs` - Simulation design specifications (water, energy, farming, labor, food processing)
- `/src` - Simulation engine source code (Layer 3)
- `/stress_testing` - Stress testing scripts and configs
    - `./baseline` - Baseline YAML configs for stress test scenarios (energy, water, farm profiles)
    - `./individual_tests` - Per-scenario test directories (energy_*, water_*, farm_*, cross_*, etc.)
    - `./run_*.py` - Runner scripts for each test domain (energy, water, farm, cross-domain)
- `/tests` - Test suites (pytest)

## Key Files

- `scenarios/scenario_base.yaml` - Scenario entry point composing all domain settings
- `settings/data_registry_base.yaml` - Central index mapping logical data names to file paths
- `settings/farm_profile_base.yaml` - Farm/field definitions with crops, areas, irrigation
- `settings/energy_system_base.yaml` - Community solar areas, wind turbine counts, battery/generator flags
- `settings/energy_policy_base.yaml` - Energy dispatch strategy, grid mode, battery/generator policy
- `settings/water_systems_base.yaml` - Wells, treatment, municipal source, storage tank
- `settings/water_policy_base.yaml` - Water dispatch strategy, caps, irrigation mode
- `settings/community_demands_base.yaml` - Household counts and building areas
- `src/energy_balance.py` - Energy balance dispatch (solar/wind → demand → battery → grid → generator)
- `src/water_balance.py` - Top-level water orchestrator composing irrigation + supply + community
- `src/water.py` - Central mixing tank water supply dispatch
- `src/water_sizing.py` - System sizing and treatment-anchored optimization
- `src/irrigation_demand.py` - Daily field-level irrigation demand from crop growth data
- `src/energy_supply.py` - Daily energy generation (solar + wind + agri-PV)
- `src/community_demand.py` - Daily household/building energy and water demands
- `src/crop_yield.py` - FAO Paper 33 water-yield response function and community harvest
- `src/farm_profile.py` - Planting normalization and overlap validation
- `src/intraday_estimate.py` - Intraday battery adequacy estimation from daily energy balance
- `src/planting_optimizer.py` - Planting schedule optimizer for irrigation demand smoothing
- `src/plots.py` - Stacked area, balance, and policy heatmap visualizations
- `settings/farm_profile_optimized.yaml` - Optimized farm profile output from planting optimizer
- `notebooks/simulation.ipynb` - Main simulation notebook (primary user entry point)
- `notebooks/helpers/planting_optimization.ipynb` - Planting schedule optimization analysis
- `notebooks/helpers/simulation_checks.ipynb` - Post-simulation validation checks

## Conventions

- CSV files use `#` comment headers — always use `comment='#'` in `pd.read_csv`
- CSV date column is `date`; renamed to `day` in output DataFrames
- File suffixes: `-research` (peer-reviewed sources), `-toy` (synthetic/placeholder)
- Settings files use `_base` suffix (e.g., `energy_system_base.yaml`)
- Column naming: `{config_key}_kwh_per_ha`, `{config_key}_kwh`, `{type}_energy_kwh`, `{type}_water_m3`
- Each module has `if __name__ == '__main__':` block for standalone verification
- Path resolution: `root_dir` defaults to `registry_path.parent.parent` (parent of `settings/`)

## Key Functions

- `compute_daily_energy_balance()` — top-level energy dispatch in `src/energy_balance.py`; matches renewable generation against demand, dispatches surplus/deficit through battery → grid → generator with SOC tracking, monthly caps, and three strategies (minimize_cost, minimize_grid_reliance, minimize_generator)
- `compute_daily_water_balance()` — top-level water orchestrator in `src/water_balance.py`; calls irrigation demand, water supply dispatch, and community demand, then composes a unified daily DataFrame with demands, sources, energy, costs, tank state, and policy decisions
- `compute_water_supply()` — central mixing tank dispatch in `src/water.py`; supports three strategies (minimize_cost, minimize_treatment, minimize_draw) with monthly caps, TDS blending, and tank flush logic
- `size_water_system()` — from-scratch system sizing in `src/water_sizing.py`; selects wells, treatment, storage, and municipal from catalogs to meet demand under a chosen objective
- `optimize_water_system()` — treatment-anchored optimization in `src/water_sizing.py`; takes a fixed BWRO throughput and sizes wells/storage/municipal around it using an efficiency curve to target the treatment sweet spot (70-85% utilization)
- `compute_irrigation_demand()` — per-field daily irrigation demand in `src/irrigation_demand.py`; scales ETc by area and irrigation efficiency, includes crop TDS requirements
- `compute_daily_energy()` — community energy supply in `src/energy_supply.py`; scales per-unit PV/wind output by configuration, includes agri-PV from farm profiles and solar degradation
- `compute_daily_demands()` — community building demands in `src/community_demand.py`; scales per-unit data by household count or building area with optional multipliers
- `compute_harvest_yield()` — FAO water-yield response in `src/crop_yield.py`; computes final yield from cumulative ETa/ETc ratio after dynamic irrigation simulation
- `compute_community_harvest()` — community-level harvest in `src/crop_yield.py`; runs yield model for all fields in the water balance, returns daily growth and final yields per field
- `estimate_intraday_balance()` — battery adequacy screening in `src/intraday_estimate.py`; decomposes daily totals into hourly profiles via shape factors, computes minimum battery swing per day using cumulative net energy method
- `optimize_planting_schedule()` — planting date optimizer in `src/planting_optimizer.py`; varies planting dates and field splits to smooth irrigation demand (minimize_variance) or align with renewable supply (match_supply)

## Development

- **Test**: `python -m pytest tests/`
- **Run module standalone**: `python -m src.energy_supply` (each module has `__main__` block)
- **Run notebook**: `jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=900 <notebook.ipynb>`
- **Generate data**: `python data/_scripts/generate_energy_output.py` (and similar generate_*.py scripts)
