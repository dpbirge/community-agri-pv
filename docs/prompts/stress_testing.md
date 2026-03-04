# Stress Testing: Water and Energy Policy Sweep

Systematic stress testing of water and energy dispatch policies by running the simulation under varied configurations and validating outputs.

## Scope

Test every policy option and key parameter in `settings/water_policy_base.yaml` and `settings/energy_policy_base.yaml` by creating modified copies of the settings files, running the simulation against them, and checking the output CSVs for correctness.

## Rules

1. **No /src changes.** All source code is read-only.
2. **All test files go in `/stress_testing/`.** Copy settings files into per-test subdirectories there. Never modify files in `/settings/`, `/scenarios/`, or `/data/`.
3. **The data registry is shared.** Every test uses the same `settings/data_registry_base.yaml` — only policy, system, and farm profile files vary.

## Directory Layout

```
stress_testing/
├── run_test.py              # shared runner script (see below)
├── baseline/                # shared settings + farm profile library
│   ├── community_demands.yaml
│   ├── farm_profile_openfield.yaml      # FP-O: all openfield, no agri-PV
│   ├── farm_profile_mixed.yaml          # FP-M: mix of openfield + underpv_medium
│   ├── farm_profile_heavy_pv.yaml       # FP-H: all underpv_high, large areas
│   ├── farm_profile_drip_small.yaml     # FP-S: small fields, drip irrigation
│   ├── farm_profile_all_pv_densities.yaml  # FP-D: one field per PV density level
│   ├── energy_system_oversupply.yaml
│   ├── energy_system_balanced.yaml
│   ├── energy_system_undersupply.yaml
│   ├── water_systems_oversupply.yaml
│   ├── water_systems_balanced.yaml
│   └── water_systems_undersupply.yaml
├── individual_tests/        # per-test subdirectories (git-ignored)
│   ├── water_01_minimize_cost/
│   │   ├── farm_profile.yaml    # each test gets its own farm profile copy
│   │   ├── water_policy.yaml
│   │   ├── water_systems.yaml
│   │   └── results/             # output CSVs land here
│   ├── energy_01_minimize_cost_openfield/
│   │   ├── farm_profile.yaml    # copied from baseline, possibly modified
│   │   ├── energy_system.yaml
│   │   ├── energy_policy.yaml
│   │   └── results/
│   └── ...
└── stress_test_report.md    # final report
```

## Runner Script

Create `stress_testing/run_test.py` — a standalone script that accepts paths to each settings file and an output directory, runs the water balance and energy balance, and saves the CSVs. Pattern from the `__main__` blocks:

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

## Phase 1: Baseline Farm Profiles and Supply Regimes

### Why farm profiles matter for energy testing

Fields with `underpv_*` conditions generate agri-PV solar energy proportional to field area and PV density. This energy feeds directly into the energy balance. A few hectares of `underpv_high` fields can produce more energy than the entire community solar + wind system combined, which masks dispatch behavior (grid import, generator, battery cycling, deficit). **Every test must use a farm profile chosen to make the tested parameter's effect visible.**

### Farm Profile Library

Create the following farm profile archetypes in `stress_testing/baseline/`. All profiles should use year-round planting sequences with few fallow gaps.

Available crops/plantings: cucumber (apr01, feb15, oct15, sep01), kale (dec01, feb01, mar15, oct01), onion (apr01, dec01, jan15), potato (jan15, nov15, sep15), tomato (apr01, aug01, feb15, nov01).

Available conditions: `openfield`, `underpv_low`, `underpv_medium`, `underpv_high`.

| ID | File | Condition | Fields | Irrigation | Purpose |
|----|------|-----------|--------|------------|---------|
| **FP-O** | `farm_profile_openfield.yaml` | All `openfield` | 4 fields, 2-2.5 ha each | sprinkler | **No agri-PV.** Use for energy dispatch tests where you need deficit/grid/generator paths to be exercised. |
| **FP-M** | `farm_profile_mixed.yaml` | 2 `openfield` + 2 `underpv_medium` | 4 fields, 2-2.5 ha each | sprinkler | **Moderate agri-PV.** Use for water tests (agri-PV level doesn't affect water) and cross-system tests needing realistic energy. |
| **FP-H** | `farm_profile_heavy_pv.yaml` | All `underpv_high` | 4 fields, 3 ha each | sprinkler | **Maximum agri-PV.** Use for energy surplus tests (curtailment, export, battery saturation). |
| **FP-S** | `farm_profile_drip_small.yaml` | All `openfield` | 2 fields, 0.5 ha each | drip | **Minimal demand.** Low water demand (drip efficiency ~0.90), no agri-PV. For testing oversupply behavior when demand is small. |
| **FP-D** | `farm_profile_all_pv_densities.yaml` | 1 `openfield` + 1 `underpv_low` + 1 `underpv_medium` + 1 `underpv_high` | 4 fields, 1.5 ha each | mixed (2 drip, 2 sprinkler) | **All PV densities.** Verifies agri-PV scaling across density levels; useful for agri-PV integration tests. |

### Supply Regimes

Also create energy system and water system variants that produce three supply regimes:

| Regime | Water | Energy | How to create |
|--------|-------|--------|---------------|
| **Oversupply** | Treatment throughput >> demand, large tank | Large solar + wind + battery | Baseline or larger systems |
| **Near-balanced** | Throughput ≈ peak demand, small tank | Moderate solar, no battery | Reduce areas/turbines, disable battery |
| **Undersupply** | Low throughput, tight municipal cap | Minimal solar, no battery, off-grid | Tiny systems, `off_grid` mode |

These supply regimes and farm profiles are combined per-test as specified in the phase tables below.

### Per-Test Farm Profile Rule

**Every test subdirectory must contain its own `farm_profile.yaml`.** Copy the appropriate baseline archetype into the test directory, then modify if the test requires specific adjustments (e.g., X5 needs 10 ha fields). This ensures each test is self-contained and reproducible.

## Phase 2: Water Policy Tests

Each test varies one parameter group from the water policy file. Run under all three supply regimes where noted. Water dispatch is not affected by agri-PV generation, so these tests use **FP-M** (mixed) to maintain realistic energy coupling.

| # | Test Name | What to Vary | Farm Profile | Supply Regime | Key Checks |
|---|-----------|-------------|--------------|---------------|------------|
| W1 | `minimize_cost` | `strategy: minimize_cost` | FP-M | All three | Cheapest sources used first; `total_water_cost` is lowest among W1-W3 |
| W2 | `minimize_treatment` | `strategy: minimize_treatment` | FP-M | All three | Treatment volume is lowest; more municipal used |
| W3 | `minimize_draw` | `strategy: minimize_draw` | FP-M | All three | Municipal used first up to cap; groundwater only after cap exhausted |
| W4 | `maximize_treatment_efficiency` | `strategy: maximize_treatment_efficiency` + `treatment_smoothing` block | FP-M | Near-balanced | Treatment runs at 70-85% of rated capacity; fallow treatment fills tank |
| W5 | `look_ahead_on` | `cap_enforcement.look_ahead: true` | FP-M | Near-balanced | Municipal usage spread evenly across month; no zero-supply days at month-end |
| W6 | `look_ahead_off` | `cap_enforcement.look_ahead: false` | FP-M | Near-balanced | Municipal cap consumed early; zero-supply days late in month |
| W7 | `tight_municipal_cap` | `municipal.monthly_cap_m3: 50` | FP-M | Near-balanced | Cap is hit; deficit appears |
| W8 | `no_municipal_cap` | `municipal.monthly_cap_m3: null` | FP-M | Near-balanced | Municipal never capped; cost higher |
| W9 | `groundwater_cap` | `groundwater.monthly_cap_m3: 200` | FP-M | Near-balanced | Groundwater capped; more municipal or deficit |
| W10 | `prefill_disabled` | `prefill.enabled: false` | FP-M | Near-balanced | More deficit days than with prefill enabled |
| W11 | `prefill_long_horizon` | `prefill.look_ahead_days: 7` | FP-M | Near-balanced | Compare to W5; fewer deficit spikes |
| W12 | `dynamic_irrigation` | `irrigation.mode: dynamic` | FP-M | Near-balanced | Yield computed from FAO formula; `deficit_m3 > 0` on some days |
| W13 | `static_deficit_60` | `irrigation.mode: static`, `static_policy: deficit_60` | FP-M | Oversupply | Demand is 60% of full ETo; no deficit expected |

## Phase 3: Energy Policy Tests

Each test varies one parameter group from the energy policy file. Farm profile selection is critical here: agri-PV from `underpv_*` fields feeds directly into renewable generation and can mask dispatch behavior.

- **Deficit/dispatch tests** (E1-E3, E8-E13): Use **FP-O** (all openfield, no agri-PV) so that community solar + wind are the only renewable sources and deficit/grid/generator/battery paths are genuinely exercised.
- **Surplus/export tests** (E5-E7): Use **FP-H** (heavy PV) to guarantee large surpluses that test export, curtailment, and battery saturation paths.
- **Balanced tests** (E4): Use **FP-M** (mixed) for a realistic middle ground.

| # | Test Name | What to Vary | Farm Profile | Supply Regime | Key Checks |
|---|-----------|-------------|--------------|---------------|------------|
| E1 | `minimize_cost` | `strategy: minimize_cost` | FP-O | All three | Grid import cheapest option; `total_energy_cost` is lowest |
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

## Phase 4: Water System Configuration Tests

Each test varies the physical infrastructure in `water_systems.yaml` while holding the water policy at `minimize_cost` with default caps. Uses **FP-M** (mixed) for realistic water demand with moderate agri-PV.

| # | Test Name | What to Vary | Farm Profile | Key Checks |
|---|-----------|-------------|--------------|------------|
| WS1 | `single_well` | Remove wells 2 and 3; keep only well_1 (20m, 1400 ppm) | FP-M | Lower TDS input; less treatment needed; flow-limited on high-demand days |
| WS2 | `high_tds_only` | Remove well_1; keep wells 2+3 (3500 and 6500 ppm) | FP-M | All groundwater requires treatment; treatment throughput becomes binding constraint |
| WS3 | `no_treatment` | Remove the `treatment` block entirely (or set `throughput_m3_hr: 0`) | FP-M | Only municipal and raw groundwater available; TDS flush logic triggers if tank TDS exceeds crop requirement |
| WS4 | `small_treatment` | `throughput_m3_hr: 5` (vs baseline 50) | FP-M | Treatment bottleneck; more municipal drawn; deficit on peak days |
| WS5 | `large_treatment` | `throughput_m3_hr: 200` | FP-M | Treatment never bottlenecked; compare cost to WS4 |
| WS6 | `no_tank` | Remove `storage` block (or `capacity_m3: 0`) | FP-M | No buffering; daily supply must meet daily demand exactly; prefill has no effect |
| WS7 | `tiny_tank` | `capacity_m3: 50`, `initial_level_m3: 25` | FP-M | Tank fills/empties frequently; prefill behavior more visible |
| WS8 | `huge_tank` | `capacity_m3: 5000`, `initial_level_m3: 2500` | FP-M | Tank rarely constrains; deficit days should drop vs baseline |
| WS9 | `expensive_municipal` | `cost_per_m3: 5.00` (10x baseline) | FP-M | `minimize_cost` strategy should avoid municipal; compare cost to baseline |
| WS10 | `low_tds_municipal` | `municipal_source.tds_ppm: 50` | FP-M | Less blending needed to meet crop TDS; treatment volumes lower |

## Phase 5: Energy System Configuration Tests

Each test varies the physical infrastructure in `energy_system.yaml` while holding the energy policy at `minimize_cost` / `self_consumption`. Farm profile choice depends on what the test exercises:

- **Deficit/reliance tests** (ES1, ES3, ES5, ES9, ES10): Use **FP-O** (openfield) so community infrastructure is the only energy source, making system sizing differences visible.
- **Surplus/storage tests** (ES4, ES6, ES7, ES8): Use **FP-O** to isolate the effect of community system sizing on surplus handling without agri-PV noise.
- **Agri-PV integration test** (ES2): Use **FP-D** (all PV densities) to verify that agri-PV generation scales correctly across `underpv_low`, `underpv_medium`, and `underpv_high` when community solar is removed.

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

## Phase 6: Cross-System Tests

These tests combine water and energy stress together. Farm profile is chosen to amplify the interaction being tested.

| # | Test Name | What to Vary | Farm Profile | Key Checks |
|---|-----------|-------------|--------------|------------|
| X1 | `water_energy_coupling` | High water demand + undersupply energy | FP-O | `total_water_energy_kwh` appears as demand in energy balance; energy deficit may constrain water pumping. No agri-PV ensures energy undersupply is real. |
| X2 | `oversupply_both` | Oversupply water + oversupply energy | FP-H | No deficits anywhere; surplus energy curtailed or exported. Heavy agri-PV guarantees massive energy surplus. |
| X3 | `undersupply_both` | Undersupply water + off-grid energy | FP-O | Both deficits > 0; system degrades gracefully (no crashes, no NaN). No agri-PV ensures genuine undersupply. |
| X4 | `no_treatment_solar_only` | WS3 + ES1 | FP-M | Combined infrastructure stress; TDS management without treatment under limited energy. Mixed PV provides moderate agri-PV. |
| X5 | `huge_farm_minimal_infra` | WS4 + ES3, but with custom large fields | Custom: 4 fields at 10 ha, 2 openfield + 2 underpv_medium, sprinkler | Maximum demand/supply mismatch; tests graceful degradation at extremes. Large underpv fields also stress agri-PV scaling. |

## Phase 7: Farm Profile Variation Tests

These tests hold energy and water policy/systems constant at near-balanced defaults (`minimize_cost` strategy) and vary the farm profile to test how different field configurations affect both the water and energy systems. Each test creates a unique `farm_profile.yaml`.

| # | Test Name | Farm Profile | Energy System | Key Checks |
|---|-----------|-------------|---------------|------------|
| FP1 | `all_openfield` | FP-O: 4 fields, all `openfield`, 2-2.5 ha, sprinkler | Balanced | `*_agripv_kwh` columns are all zero; total renewable = community solar + wind only |
| FP2 | `all_underpv_high` | FP-H: 4 fields, all `underpv_high`, 3 ha, sprinkler | Balanced | Agri-PV dominates total renewable; `total_renewable_kwh >> total_demand_kwh`; heavy surplus/curtailment |
| FP3 | `mixed_pv_densities` | FP-D: 4 fields, one per condition, 1.5 ha, mixed irrigation | Balanced | Each density level produces a distinct `*_agripv_kwh` column; `high > medium > low` in per-field generation |
| FP4 | `small_drip_no_pv` | FP-S: 2 fields, 0.5 ha, drip, openfield | Balanced | Low water demand (drip efficiency ~0.90); no agri-PV; minimal water energy; system runs in comfortable surplus |
| FP5 | `large_furrow_high_demand` | Custom: 4 fields, 3 ha, furrow (efficiency ~0.60), openfield | Balanced | High water demand due to furrow inefficiency; water deficit likely on peak days; no agri-PV |
| FP6 | `single_field_underpv_high` | Custom: 1 field, 5 ha, `underpv_high`, drip | Balanced | Single large agri-PV field; verify single-farm energy column; compare water demand to FP4 (same irrigation, larger area) |
| FP7 | `many_small_fields` | Custom: 8 fields across 4 farms, 0.25 ha each, mixed conditions + irrigation | Balanced | Tests scaling with many fields; each farm gets its own `*_agripv_kwh` column; total area = 2 ha |
| FP8 | `pv_vs_openfield_comparison` | Run twice: once with FP-O, once with FP-H (same areas/crops/irrigation) | Balanced | **Paired comparison.** Same demand but different agri-PV. Quantify the energy surplus difference. Water demand should also differ slightly (underpv reduces ETc). |

## Validation Checks (apply to every test)

After each simulation run, validate the output CSVs:

### Universal checks (must pass for every test)
1. **No crashes** — simulation completes without exceptions.
2. **No NaN in key columns** — `total_demand_m3`, `total_delivered_m3`, `deficit_m3`, `total_demand_kwh`, `total_renewable_kwh` are never NaN.
3. **Non-negative quantities** — all `_m3`, `_kwh`, `_cost` columns are ≥ 0.
4. **Water balance** — `abs(balance_check) < 0.01` for all rows (except row 0 which is NaN by design).
5. **Energy conservation** — on surplus days: `total_renewable ≈ consumed + charge + export + curtailed`. On deficit days: `demand ≈ renewable + discharge + grid + generator + deficit`.
6. **Date continuity** — `day` column has no gaps.
7. **Tank bounds** — `tank_volume_m3` stays within `[0, capacity_m3]`.
8. **Battery bounds** — `battery_soc` stays within `[soc_min, soc_max]`.

### Per-test checks
Each test in the tables above lists specific "Key Checks." Verify these quantitatively by reading the output CSV and comparing totals or checking column values.

## Agent Workflow

This is designed for a multi-agent session using the Claude Code `Agent` tool. **You are the coordinator.** Do not run tests yourself — delegate every test to a subagent.

### Step 1: Setup (coordinator does this directly)

1. Create the `/stress_testing/` directory structure.
2. Write `stress_testing/run_test.py` (the shared runner script above).
3. Write the baseline settings files in `stress_testing/baseline/`:
   - **All five farm profile archetypes** (FP-O, FP-M, FP-H, FP-S, FP-D) as defined in the Farm Profile Library table
   - Community demands
   - Three supply-regime variants for water systems and energy systems
4. Run one baseline simulation per farm profile archetype to verify each produces valid output. Fix any issues before proceeding.

### Step 2: Spawn one subagent per test

Each test row (W1, W2, ..., WS1, ..., ES1, ..., FP1, ..., X1, ...) is handled by its own subagent via the `Agent` tool with `model: "sonnet"`. The subagent prompt should include:

- The test ID and name (e.g., "W3 — minimize_draw")
- Which **farm profile archetype** to use (FP-O, FP-M, FP-H, FP-S, FP-D, or a custom profile spec) — see the Farm Profile column in each phase table
- Which settings files to copy from `stress_testing/baseline/` and what to modify
- Which supply regime to use (oversupply / near-balanced / undersupply)
- The full list of validation checks to run (universal + per-test key checks from the tables above)
- The path to `stress_testing/run_test.py` and the `settings/data_registry_base.yaml` registry

Each subagent:
1. Creates its subdirectory (e.g., `stress_testing/individual_tests/water_03_minimize_draw/`)
2. **Copies the designated farm profile archetype** from `stress_testing/baseline/` into its subdirectory as `farm_profile.yaml`. If the test specifies "Custom", the subagent creates the farm profile from the spec in the table.
3. Copies other baseline settings files into the subdirectory, then edits the relevant YAML values
4. Runs the simulation via `run_test.py` pointing to its own settings files (including its local `farm_profile.yaml`)
5. Reads the output CSVs and runs every validation check
6. Returns a structured result: test name, farm profile used, pass/fail per check, key metric totals, any anomalies

### Step 3: Parallelism rules

Subagents read only from `/data/` and `/settings/data_registry_base.yaml` (shared, read-only) and write only to their own subdirectory. This means:

- **All tests within a phase can run in parallel** — they have no file conflicts.
- **All phases can run in parallel** — water policy tests, energy policy tests, system config tests, and cross-system tests are independent.
- Launch as many subagents concurrently as practical. Do not wait for one test to finish before starting the next unless it depends on the output (none do — each test runs its own full simulation).

### Step 4: Collect results

After all subagents return, the coordinator:
1. Reads each subagent's result.
2. Compiles the combined findings into `stress_testing/stress_test_report.md` using the report format below.
3. Flags any tests that crashed or returned unexpected results for manual review.

## Report Format

`stress_testing/stress_test_report.md` should contain:

```markdown
# Stress Test Report

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