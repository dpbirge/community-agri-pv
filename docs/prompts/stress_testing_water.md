# Stress Testing: Water Policy & Water Systems

Systematic stress testing of the water dispatch system — both policy parameters (`water_policy.yaml`) and physical infrastructure (`water_systems.yaml`) — by running the simulation under varied configurations and validating outputs.

## Goal

Verify that the water supply dispatch engine (`src/water.py`, `src/water_balance.py`) correctly implements:

- All three dispatch strategies (minimize_cost, minimize_treatment, minimize_draw) plus maximize_treatment_efficiency
- Monthly cap enforcement with and without look-ahead
- Prefill logic (enabled/disabled, varying horizons)
- Irrigation modes (static policies, dynamic FAO-based yield)
- Physical infrastructure variations (well count, TDS levels, treatment capacity, tank sizing, municipal pricing)
- TDS blending and tank flush logic
- Graceful degradation under deficit conditions

## Why Supporting Systems Matter

Water dispatch is not affected by agri-PV generation level, but the simulation still requires valid energy and farm profile settings to run end-to-end. The setup phase configures these supporting systems so they don't interfere with water testing:

- **Farm profile**: Uses FP-M (mixed openfield + underpv_medium) to produce realistic irrigation demand without extremes. Moderate agri-PV doesn't affect water dispatch but provides a realistic energy coupling.
- **Energy system**: Uses a balanced configuration — enough community solar + wind + battery to avoid energy crashes, but not so much that the energy side is trivially easy. Energy is not the focus here; it just needs to run without errors.

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
│   ├── farm_profile_mixed.yaml          # FP-M: default for water tests
│   ├── energy_system_balanced.yaml      # supporting energy config
│   ├── energy_policy_balanced.yaml      # supporting energy policy
│   ├── water_systems_oversupply.yaml
│   ├── water_systems_balanced.yaml
│   └── water_systems_undersupply.yaml
├── individual_tests/
│   ├── water_01_minimize_cost/
│   │   ├── farm_profile.yaml
│   │   ├── energy_system.yaml
│   │   ├── energy_policy.yaml
│   │   ├── water_policy.yaml
│   │   ├── water_systems.yaml
│   │   └── results/
│   └── ...
└── water_stress_test_report.md
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

Run from the repo root: `python -c "from stress_testing.run_test import run; run(...)"` or import and call.

## Phase 1: Setup — Configure Supporting Systems

Before running any water tests, the coordinator must create the supporting settings files that hold energy and farming stable.

### Farm Profile: FP-M (Mixed)

Create `stress_testing/baseline/farm_profile_mixed.yaml` — 4 fields, 2-2.5 ha each, year-round planting sequences with few fallow gaps.

- 2 fields: `openfield`, sprinkler irrigation
- 2 fields: `underpv_medium`, sprinkler irrigation
- Purpose: Produces realistic, moderate irrigation demand. The `underpv_medium` fields generate some agri-PV but don't dominate energy. Sprinkler irrigation (efficiency ~0.75) creates meaningful water demand.

Available crops/plantings: cucumber (apr01, feb15, oct15, sep01), kale (dec01, feb01, mar15, oct01), onion (apr01, dec01, jan15), potato (jan15, nov15, sep15), tomato (apr01, aug01, feb15, nov01).

### Energy System: Balanced

Create `stress_testing/baseline/energy_system_balanced.yaml`:

- Moderate community solar (0.05 ha each density level)
- 2-4 small wind turbines
- Battery enabled (200 kWh)
- Generator enabled (50 kW rated)
- `full_grid` connection

This gives enough energy generation to avoid energy crashes across all water test scenarios without being the focus.

### Energy Policy: Balanced

Create `stress_testing/baseline/energy_policy_balanced.yaml`:

- `strategy: minimize_cost`
- `grid.mode: full_grid`
- Default battery SOC limits
- Default generator min load

### Community Demands

Copy from `settings/community_demands_base.yaml` as-is.

### Water System Supply Regimes

Create three water system variants:

| Regime | File | Wells | Treatment | Tank | Municipal | Design intent |
|--------|------|-------|-----------|------|-----------|---------------|
| **Oversupply** | `water_systems_oversupply.yaml` | All 3 wells | `throughput_m3_hr: 200` | `capacity_m3: 1000` | `cost_per_m3: 0.50` | Treatment and storage far exceed any demand; deficit should never occur |
| **Near-balanced** | `water_systems_balanced.yaml` | All 3 wells | `throughput_m3_hr: 50` | `capacity_m3: 200` | `cost_per_m3: 0.50` | Throughput ≈ peak demand; tank provides modest buffer; stress is visible |
| **Undersupply** | `water_systems_undersupply.yaml` | 2 wells (remove well_1) | `throughput_m3_hr: 10` | `capacity_m3: 50` | `cost_per_m3: 0.50`, `monthly_cap_m3: 200` in policy | Treatment bottlenecked; deficit expected on high-demand days |

### Validation Run

Run one baseline simulation with FP-M + balanced energy + each water supply regime to verify the setup produces valid output. Fix any issues before proceeding.

## Phase 2: Water Policy Tests

Each test varies one parameter group from the water policy file. Uses **FP-M** (mixed) as farm profile. Energy uses the balanced config from Phase 1.

| # | Test Name | What to Vary | Supply Regime | Key Checks |
|---|-----------|-------------|---------------|------------|
| W1 | `minimize_cost` | `strategy: minimize_cost` | All three | Cheapest sources used first; `total_water_cost` is lowest among W1-W3 |
| W2 | `minimize_treatment` | `strategy: minimize_treatment` | All three | Treatment volume is lowest; more municipal used |
| W3 | `minimize_draw` | `strategy: minimize_draw` | All three | Municipal used first up to cap; groundwater only after cap exhausted |
| W4 | `maximize_treatment_efficiency` | `strategy: maximize_treatment_efficiency` + `treatment_smoothing` block | Near-balanced | Treatment runs at 70-85% of rated capacity; fallow treatment fills tank |
| W5 | `look_ahead_on` | `cap_enforcement.look_ahead: true` | Near-balanced | Municipal usage spread evenly across month; no zero-supply days at month-end |
| W6 | `look_ahead_off` | `cap_enforcement.look_ahead: false` | Near-balanced | Municipal cap consumed early; zero-supply days late in month |
| W7 | `tight_municipal_cap` | `municipal.monthly_cap_m3: 50` | Near-balanced | Cap is hit; deficit appears |
| W8 | `no_municipal_cap` | `municipal.monthly_cap_m3: null` | Near-balanced | Municipal never capped; cost higher |
| W9 | `groundwater_cap` | `groundwater.monthly_cap_m3: 200` | Near-balanced | Groundwater capped; more municipal or deficit |
| W10 | `prefill_disabled` | `prefill.enabled: false` | Near-balanced | More deficit days than with prefill enabled |
| W11 | `prefill_long_horizon` | `prefill.look_ahead_days: 7` | Near-balanced | Compare to W5; fewer deficit spikes |
| W12 | `dynamic_irrigation` | `irrigation.mode: dynamic` | Near-balanced | Yield computed from FAO formula; `deficit_m3 > 0` on some days |
| W13 | `static_deficit_60` | `irrigation.mode: static`, `static_policy: deficit_60` | Oversupply | Demand is 60% of full ETo; no deficit expected |

## Phase 3: Water System Configuration Tests

Each test varies the physical infrastructure in `water_systems.yaml` while holding the water policy at `minimize_cost` with default caps. Uses **FP-M** (mixed) for realistic water demand.

| # | Test Name | What to Vary | Key Checks |
|---|-----------|-------------|------------|
| WS1 | `single_well` | Remove wells 2 and 3; keep only well_1 (20m, 1400 ppm) | Lower TDS input; less treatment needed; flow-limited on high-demand days |
| WS2 | `high_tds_only` | Remove well_1; keep wells 2+3 (3500 and 6500 ppm) | All groundwater requires treatment; treatment throughput becomes binding constraint |
| WS3 | `no_treatment` | Remove the `treatment` block entirely (or set `throughput_m3_hr: 0`) | Only municipal and raw groundwater available; TDS flush logic triggers if tank TDS exceeds crop requirement |
| WS4 | `small_treatment` | `throughput_m3_hr: 5` (vs baseline 50) | Treatment bottleneck; more municipal drawn; deficit on peak days |
| WS5 | `large_treatment` | `throughput_m3_hr: 200` | Treatment never bottlenecked; compare cost to WS4 |
| WS6 | `no_tank` | Remove `storage` block (or `capacity_m3: 0`) | No buffering; daily supply must meet daily demand exactly; prefill has no effect |
| WS7 | `tiny_tank` | `capacity_m3: 50`, `initial_level_m3: 25` | Tank fills/empties frequently; prefill behavior more visible |
| WS8 | `huge_tank` | `capacity_m3: 5000`, `initial_level_m3: 2500` | Tank rarely constrains; deficit days should drop vs baseline |
| WS9 | `expensive_municipal` | `cost_per_m3: 5.00` (10x baseline) | `minimize_cost` strategy should avoid municipal; compare cost to baseline |
| WS10 | `low_tds_municipal` | `municipal_source.tds_ppm: 50` | Less blending needed to meet crop TDS; treatment volumes lower |

## Validation Checks (apply to every test)

### Universal checks (must pass for every test)

1. **No crashes** — simulation completes without exceptions.
2. **No NaN in key columns** — `total_demand_m3`, `total_delivered_m3`, `deficit_m3` are never NaN.
3. **Non-negative quantities** — all `_m3` and `_cost` columns are ≥ 0.
4. **Water balance** — `abs(balance_check) < 0.01` for all rows (except row 0 which is NaN by design).
5. **Date continuity** — `day` column has no gaps.
6. **Tank bounds** — `tank_volume_m3` stays within `[0, capacity_m3]`.

### Per-test checks

Each test in the tables above lists specific "Key Checks." Verify these quantitatively by reading the output CSV and comparing totals or checking column values.

## Agent Workflow

This is designed for a multi-agent session using the Claude Code `Agent` tool. **You are the coordinator.** Do not run tests yourself — delegate every test to a subagent.

### Step 1: Setup (coordinator does this directly)

1. Create the `/stress_testing/` directory structure.
2. Write `stress_testing/run_test.py` (the shared runner script above).
3. Write the supporting baseline files in `stress_testing/baseline/`:
   - **FP-M farm profile** (mixed openfield + underpv_medium)
   - **Balanced energy system** and **balanced energy policy** (these stay constant across all water tests)
   - **Community demands** (copy from settings)
   - **Three water system supply regime variants**
4. Run one baseline simulation per water supply regime to verify each produces valid output. Fix any issues before proceeding.

### Step 2: Spawn one subagent per test

Each test row (W1, W2, ..., WS1, ...) is handled by its own subagent via the `Agent` tool with `model: "sonnet"`. The subagent prompt should include:

- The test ID and name (e.g., "W3 — minimize_draw")
- That it should use **FP-M** as farm profile and the **balanced energy config** (paths to these baseline files)
- Which water systems file to copy from `stress_testing/baseline/` and what to modify
- Which water policy parameters to set
- The full list of validation checks (universal + per-test key checks)
- The path to `stress_testing/run_test.py` and `settings/data_registry_base.yaml`

Each subagent:
1. Creates its subdirectory (e.g., `stress_testing/individual_tests/water_03_minimize_draw/`)
2. Copies FP-M, balanced energy system, balanced energy policy, and community demands from baseline
3. Copies the designated water systems file, then edits the relevant YAML values
4. Creates the water policy file with the test's parameter settings
5. Runs the simulation via `run_test.py`
6. Reads the output CSVs and runs every validation check
7. Returns a structured result: test name, pass/fail per check, key metric totals, any anomalies

### Step 3: Parallelism rules

All tests can run in parallel — each subagent writes only to its own subdirectory.

### Step 4: Collect results

After all subagents return, the coordinator:
1. Reads each subagent's result.
2. Compiles findings into `stress_testing/water_stress_test_report.md`.
3. Flags any tests that crashed or returned unexpected results.

## Report Format

```markdown
# Water Stress Test Report

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
