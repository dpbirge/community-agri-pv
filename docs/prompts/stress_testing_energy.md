# Stress Testing: Energy Policy & Energy Systems

Systematic stress testing of the energy dispatch system — both policy parameters (`energy_policy.yaml`) and physical infrastructure (`energy_system.yaml`) — by running the simulation under varied configurations and validating outputs.

## Goal

Verify that the energy dispatch engine (`src/energy_balance.py`) correctly implements:

- All three dispatch strategies (minimize_cost, minimize_grid_reliance, minimize_generator)
- All grid modes (full_grid, net_metering, feed_in_tariff, self_consumption, limited_grid, off_grid)
- Battery charge/discharge cycling with SOC bounds
- Generator dispatch with min-load constraints
- Monthly grid cap enforcement with and without look-ahead
- Surplus handling (export, curtailment, battery saturation)
- Deficit cascading through battery → grid → generator
- Graceful degradation when all sources are exhausted

## Why Supporting Systems Matter — The Agri-PV Problem

Fields with `underpv_*` conditions generate agri-PV solar energy proportional to field area and PV density. This energy feeds directly into the energy balance as renewable generation. **A few hectares of `underpv_high` fields can produce more energy than the entire community solar + wind system combined**, which masks dispatch behavior: grid import never triggers, generator never runs, battery never discharges, and deficit never appears.

To properly stress-test energy dispatch, most tests need a farm profile with **no agri-PV** (all `openfield`) so that community solar + wind are the only renewable sources and deficit/grid/generator/battery paths are genuinely exercised. The exceptions are surplus/export tests, which intentionally use heavy agri-PV to guarantee large surpluses.

### Setup Principle

| Test category | Farm profile | Why |
|---------------|-------------|-----|
| Deficit/dispatch tests (E1-E3, E8-E13) | **FP-O** (all openfield, no agri-PV) | Community solar + wind are the only renewables; deficit/grid/generator/battery paths are exercised |
| Surplus/export tests (E5-E7) | **FP-H** (all underpv_high, 3 ha each) | Massive agri-PV guarantees large surpluses for testing export, curtailment, battery saturation |
| Balanced tests (E4) | **FP-M** (mixed openfield + underpv_medium) | Realistic middle ground for full_grid mode testing |

## Rules

1. **No /src changes.** All source code is read-only.
2. **All test files go in `/stress_testing/`.** Copy settings files into per-test subdirectories there. Never modify files in `/settings/`, `/scenarios/`, or `/data/`.
3. **The data registry is shared.** Every test uses the same `settings/data_registry_base.yaml`.

## Directory Layout

```
stress_testing/
├── run_test.py              # shared runner script (see below)
├── baseline/                # shared settings + farm profile library
│   ├── community_demands.yaml
│   ├── farm_profile_openfield.yaml      # FP-O: no agri-PV (deficit tests)
│   ├── farm_profile_mixed.yaml          # FP-M: moderate agri-PV (balanced tests)
│   ├── farm_profile_heavy_pv.yaml       # FP-H: max agri-PV (surplus tests)
│   ├── farm_profile_all_pv_densities.yaml # FP-D: one per density (ES2 wind-only)
│   ├── water_systems_balanced.yaml      # supporting water config
│   ├── water_policy_balanced.yaml       # supporting water policy
│   ├── energy_system_oversupply.yaml
│   ├── energy_system_balanced.yaml
│   └── energy_system_undersupply.yaml
├── individual_tests/
│   ├── energy_01_minimize_cost/
│   │   ├── farm_profile.yaml
│   │   ├── water_systems.yaml
│   │   ├── water_policy.yaml
│   │   ├── energy_system.yaml
│   │   ├── energy_policy.yaml
│   │   └── results/
│   └── ...
└── energy_stress_test_report.md
```

## Runner Script

Create `stress_testing/run_test.py` — a standalone script that accepts paths to each settings file and an output directory, runs the water balance and energy balance, and saves the CSVs:

```python
"""Run water + energy simulation with the given settings files."""
from pathlib import Path
from src.water_balance import compute_daily_water_balance, save_daily_water_balance
from src.energy_balance import compute_daily_energy_balance, save_energy_balance

def run(*, farm_profiles_path, water_systems_path, water_policy_path,
        community_config_path, energy_config_path, energy_policy_path,
        registry_path, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    water_df = compute_daily_water_balance(
        farm_profiles_path=farm_profiles_path,
        water_systems_path=water_systems_path,
        water_policy_path=water_policy_path,
        community_config_path=community_config_path,
        registry_path=registry_path,
    )
    save_daily_water_balance(water_df, output_dir=output_dir)

    energy_df = compute_daily_energy_balance(
        energy_config_path=energy_config_path,
        energy_policy_path=energy_policy_path,
        community_config_path=community_config_path,
        farm_profiles_path=farm_profiles_path,
        registry_path=registry_path,
        water_balance_df=water_df,
    )
    save_energy_balance(energy_df, output_dir=output_dir)
    return water_df, energy_df
```

## Phase 1: Setup — Configure Supporting Systems

Before running any energy tests, the coordinator must create the supporting settings files that hold water and farming stable.

### Farm Profile Library

Create these farm profile archetypes in `stress_testing/baseline/`. All profiles should use year-round planting sequences with few fallow gaps.

Available crops/plantings: cucumber (apr01, feb15, oct15, sep01), kale (dec01, feb01, mar15, oct01), onion (apr01, dec01, jan15), potato (jan15, nov15, sep15), tomato (apr01, aug01, feb15, nov01).

Available conditions: `openfield`, `underpv_low`, `underpv_medium`, `underpv_high`.

| ID | File | Condition | Fields | Irrigation | Purpose |
|----|------|-----------|--------|------------|---------|
| **FP-O** | `farm_profile_openfield.yaml` | All `openfield` | 4 fields, 2-2.5 ha each | sprinkler | **No agri-PV.** Deficit/dispatch tests. Community solar + wind are the only renewable sources. |
| **FP-M** | `farm_profile_mixed.yaml` | 2 `openfield` + 2 `underpv_medium` | 4 fields, 2-2.5 ha each | sprinkler | **Moderate agri-PV.** Balanced tests (E4). |
| **FP-H** | `farm_profile_heavy_pv.yaml` | All `underpv_high` | 4 fields, 3 ha each | sprinkler | **Maximum agri-PV.** Surplus/export tests (E5-E7). Guarantees large renewable surplus. |
| **FP-D** | `farm_profile_all_pv_densities.yaml` | 1 `openfield` + 1 `underpv_low` + 1 `underpv_medium` + 1 `underpv_high` | 4 fields, 1.5 ha each | mixed | **All PV densities.** Verifies agri-PV scaling (ES2). |

### Water System: Balanced (Supporting)

Create `stress_testing/baseline/water_systems_balanced.yaml`:

- All 3 wells (20m/1400ppm, 50m/3500ppm, 100m/6500ppm)
- Treatment: `throughput_m3_hr: 50`
- Tank: `capacity_m3: 200`
- Municipal: `cost_per_m3: 0.50`

This provides enough water capacity to avoid water-side crashes across all farm profiles without being the focus.

### Water Policy: Balanced (Supporting)

Create `stress_testing/baseline/water_policy_balanced.yaml`:

- `strategy: minimize_cost`
- `irrigation.mode: static`, `static_policy: full_eto`
- `prefill.enabled: true`
- Default caps (no municipal cap, groundwater cap 15000)
- `cap_enforcement.look_ahead: true`

### Community Demands

Copy from `settings/community_demands_base.yaml` as-is.

### Energy System Supply Regimes

Create three energy system variants:

| Regime | File | Solar | Wind | Battery | Generator | Grid | Design intent |
|--------|------|-------|------|---------|-----------|------|---------------|
| **Oversupply** | `energy_system_oversupply.yaml` | All densities at 2.0 ha | `small: 4, medium: 2, large: 2` | `capacity_kwh: 500` | `rated_capacity_kw: 100` | `full_grid` | Renewable generation far exceeds demand |
| **Near-balanced** | `energy_system_balanced.yaml` | All densities at 0.05 ha | `small: 4` | `capacity_kwh: 200` | `rated_capacity_kw: 50` | `full_grid` | Generation ≈ demand; dispatch decisions matter |
| **Undersupply** | `energy_system_undersupply.yaml` | All densities at 0.01 ha | `small: 1` | `has_battery: false` | `has_generator: false` | `off_grid` | Minimal renewables, no backup; deficit expected |

### Validation Run

Run one baseline simulation per farm profile archetype (FP-O, FP-M, FP-H, FP-D) with balanced water + balanced energy to verify each produces valid output. Fix any issues before proceeding.

## Phase 2: Energy Policy Tests

Each test varies one parameter group from the energy policy file. Farm profile selection is critical — see the table's Farm Profile column and the reasoning in "Why Supporting Systems Matter" above.

| # | Test Name | What to Vary | Farm Profile | Supply Regime | Key Checks |
|---|-----------|-------------|--------------|---------------|------------|
| E1 | `minimize_cost` | `strategy: minimize_cost` | FP-O | All three | Grid import cheapest option; `total_energy_cost` is lowest among E1-E3 |
| E2 | `minimize_grid_reliance` | `strategy: minimize_grid_reliance` | FP-O | All three | Grid import is lowest; generator used before grid |
| E3 | `minimize_generator` | `strategy: minimize_generator` | FP-O | All three | Generator output is lowest; grid used before generator |
| E4 | `full_grid` | `grid.mode: full_grid` | FP-M | Near-balanced | Unlimited import/export; no curtailment |
| E5 | `net_metering` | `grid.mode: net_metering` | FP-H | Oversupply | Monthly net calculation; export offsets import |
| E6 | `feed_in_tariff` | `grid.mode: feed_in_tariff`, set `capacity_tier` | FP-H | Oversupply | Export revenue appears; `grid_export_kwh > 0` |
| E7 | `self_consumption` | `grid.mode: self_consumption` | FP-H | Oversupply | No export; surplus → battery → curtailed |
| E8 | `limited_grid` | `grid.mode: limited_grid`, `monthly_import_cap_kwh: 500` | FP-O | Near-balanced | Cap enforced; generator/battery cover remaining |
| E9 | `off_grid` | `grid.mode: off_grid` | FP-O | Undersupply | `grid_import_kwh = 0` every day; generator + battery only |
| E10 | `no_battery` | `battery.has_battery: false` | FP-O | Near-balanced | No charge/discharge columns; more grid or generator |
| E11 | `no_generator` | `generator.has_generator: false` | FP-O | Near-balanced | No generator columns; more grid or deficit |
| E12 | `no_battery_no_generator` | Both false | FP-O | Undersupply + `off_grid` | Only renewables; `deficit_kwh` on low-sun days |
| E13 | `grid_cap_look_ahead` | `cap_enforcement.look_ahead: true/false` | FP-O | Near-balanced + `limited_grid` | Same pattern as water: spread vs. exhaust early |

## Phase 3: Energy System Configuration Tests

Each test varies the physical infrastructure in `energy_system.yaml` while holding the energy policy at `minimize_cost` / `self_consumption`. Farm profile is **FP-O** unless noted.

| # | Test Name | What to Vary | Farm Profile | Key Checks |
|---|-----------|-------------|--------------|------------|
| ES1 | `solar_only` | Remove all `wind_turbines` entries | FP-O | `total_wind_kwh = 0` every day; seasonal pattern more pronounced |
| ES2 | `wind_only` | Remove all `community_solar` entries | FP-D | `total_solar_kwh = 0` (community solar); agri-PV from farm fields still appears with per-density columns |
| ES3 | `minimal_solar` | All solar areas to 0.01 ha | FP-O | Very low generation; heavy grid/generator reliance |
| ES4 | `large_solar` | All solar areas to 5.0 ha | FP-O | Oversupply on sunny days; surplus → battery → curtailed |
| ES5 | `single_small_turbine` | `small_turbine: 1`, remove medium and large | FP-O | Minimal wind; compare generation profile to ES1 |
| ES6 | `many_large_turbines` | `large_turbine: 20`, remove small and medium | FP-O | Wind-dominant supply; less seasonal than solar |
| ES7 | `tiny_battery` | `capacity_kwh: 10` | FP-O | Battery saturates quickly; more curtailment or grid export |
| ES8 | `huge_battery` | `capacity_kwh: 2000` | FP-O | Battery absorbs most surplus; less curtailment; higher self-consumption ratio |
| ES9 | `large_generator` | `rated_capacity_kw: 500` | FP-O | Generator covers all deficits easily; fuel cost dominates |
| ES10 | `no_renewables` | Remove solar and wind entirely | FP-O | `total_renewable_kwh = 0`; 100% grid + generator; maximum cost baseline |

## Validation Checks (apply to every test)

### Universal checks (must pass for every test)

1. **No crashes** — simulation completes without exceptions.
2. **No NaN in key columns** — `total_demand_kwh`, `total_renewable_kwh` are never NaN.
3. **Non-negative quantities** — all `_kwh` and `_cost` columns are ≥ 0.
4. **Energy conservation** — on surplus days: `total_renewable ≈ consumed + charge + export + curtailed`. On deficit days: `demand ≈ renewable + discharge + grid + generator + deficit`.
5. **Date continuity** — `day` column has no gaps.
6. **Battery bounds** — `battery_soc` stays within `[soc_min, soc_max]`.

### Per-test checks

Each test in the tables above lists specific "Key Checks." Verify these quantitatively by reading the output CSV and comparing totals or checking column values.

## Agent Workflow

This is designed for a multi-agent session using the Claude Code `Agent` tool. **You are the coordinator.** Do not run tests yourself — delegate every test to a subagent.

### Step 1: Setup (coordinator does this directly)

1. Create the `/stress_testing/` directory structure.
2. Write `stress_testing/run_test.py` (the shared runner script above).
3. Write the supporting baseline files in `stress_testing/baseline/`:
   - **All four farm profile archetypes** (FP-O, FP-M, FP-H, FP-D)
   - **Balanced water system** and **balanced water policy** (these stay constant across all energy tests)
   - **Community demands** (copy from settings)
   - **Three energy system supply regime variants**
4. Run one baseline simulation per farm profile archetype to verify each produces valid output. Fix any issues before proceeding.

### Step 2: Spawn one subagent per test

Each test row (E1, E2, ..., ES1, ...) is handled by its own subagent via the `Agent` tool with `model: "sonnet"`. The subagent prompt should include:

- The test ID and name (e.g., "E3 — minimize_generator")
- Which **farm profile archetype** to use (see Farm Profile column) and **why** (so the subagent understands the reasoning)
- That it should use the **balanced water config** (paths to baseline water files)
- Which energy systems file to copy from baseline and what to modify
- Which energy policy parameters to set
- The full list of validation checks (universal + per-test key checks)
- The path to `stress_testing/run_test.py` and `settings/data_registry_base.yaml`

Each subagent:
1. Creates its subdirectory (e.g., `stress_testing/individual_tests/energy_03_minimize_generator/`)
2. Copies the designated farm profile, balanced water system, balanced water policy, and community demands from baseline
3. Copies the designated energy systems file, then edits values as needed
4. Creates the energy policy file with the test's parameter settings
5. Runs the simulation via `run_test.py`
6. Reads the output CSVs and runs every validation check
7. Returns a structured result: test name, farm profile used, pass/fail per check, key metric totals, any anomalies

### Step 3: Parallelism rules

All tests can run in parallel — each subagent writes only to its own subdirectory.

### Step 4: Collect results

After all subagents return, the coordinator:
1. Reads each subagent's result.
2. Compiles findings into `stress_testing/energy_stress_test_report.md`.
3. Flags any tests that crashed or returned unexpected results.

## Report Format

```markdown
# Energy Stress Test Report

## Summary
- Tests run: N
- Passed: N
- Failed: N
- Warnings: N

## Results Table
| Test | Status | Key Metrics | Notes |
|------|--------|-------------|-------|

## Failures (detailed)
### [Test Name]
- **What failed**: specific check that failed
- **Expected**: what the check expected
- **Actual**: what was observed
- **CSV evidence**: column name, row range, values

## Observations
- Cross-test comparisons (e.g., cost ranking across strategies)
- Parameter sensitivity findings
- Suggestions for additional test coverage
```
