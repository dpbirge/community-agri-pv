# Stress Testing: Farm Profile Variations

Systematic stress testing of how different farm profile configurations — field count, area, irrigation type, PV condition, crop selection — affect both the water and energy systems downstream.

## Goal

Verify that the farming-related modules (`src/farm_profile.py`, `src/irrigation_demand.py`, `src/crop_yield.py`, `src/energy_supply.py` agri-PV path) correctly handle:

- Agri-PV energy generation scaling across density levels (openfield → underpv_low → underpv_medium → underpv_high)
- Irrigation demand differences by irrigation system type (drip ~0.90, sprinkler ~0.75, furrow ~0.60 efficiency)
- Water demand scaling with field area
- Many-field and single-field edge cases
- The paired effect of PV condition on both ETc reduction (water side) and agri-PV generation (energy side)
- Correct column generation per farm/field in output CSVs
- Cross-system interactions: large farms driving water energy demand that appears in the energy balance

## Why Supporting Systems Matter — Isolating Farm Profile Effects

Farm profile changes affect both water demand (via irrigation) and energy supply (via agri-PV). To make farm profile differences visible, the water and energy systems must be set at a **near-balanced** level:

- **Water system too large**: Every farm profile gets zero deficit, masking irrigation demand differences between drip and furrow, or between 0.5 ha and 10 ha fields.
- **Water system too small**: Every farm profile gets deficit every day, masking the differences again.
- **Energy system too large**: Even FP-O (no agri-PV) produces zero deficit, so the agri-PV contribution from underpv profiles is invisible.
- **Energy system too small**: The community is always in deficit regardless of agri-PV, masking the effect.

The balanced setup ensures that farm profile choices create measurable, distinguishable differences in both systems.

## Rules

1. **No /src changes.** All source code is read-only.
2. **All test files go in `/stress_testing/`.** Copy settings files into per-test subdirectories there. Never modify files in `/settings/`, `/scenarios/`, or `/data/`.
3. **The data registry is shared.** Every test uses the same `settings/data_registry_base.yaml`.

## Directory Layout

```
stress_testing/
├── run_test.py              # shared runner script (see below)
├── baseline/                # shared settings
│   ├── community_demands.yaml
│   ├── energy_system_balanced.yaml      # supporting energy config
│   ├── energy_policy_balanced.yaml      # supporting energy policy
│   ├── water_systems_balanced.yaml      # supporting water config
│   └── water_policy_balanced.yaml       # supporting water policy
├── individual_tests/
│   ├── farm_01_all_openfield/
│   │   ├── farm_profile.yaml            # unique per test
│   │   ├── energy_system.yaml
│   │   ├── energy_policy.yaml
│   │   ├── water_systems.yaml
│   │   ├── water_policy.yaml
│   │   └── results/
│   └── ...
└── farm_stress_test_report.md
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

Before running any farm profile tests, the coordinator must create the supporting settings files that hold water and energy infrastructure stable at near-balanced levels.

### Energy System: Balanced

Create `stress_testing/baseline/energy_system_balanced.yaml`:

- Community solar: all densities at 0.05 ha each
- Wind: `small_turbine: 4`, no medium or large
- Battery: enabled, `capacity_kwh: 200`
- Generator: enabled, `rated_capacity_kw: 50`
- Grid: `full_grid`

This produces moderate community renewable generation. When paired with FP-O (no agri-PV), the system should show some deficit days. When paired with FP-H (heavy agri-PV), the agri-PV surplus should be clearly visible against this moderate community baseline.

### Energy Policy: Balanced

Create `stress_testing/baseline/energy_policy_balanced.yaml`:

- `strategy: minimize_cost`
- `grid.mode: full_grid`
- Default battery and generator settings
- `cap_enforcement.look_ahead: true`

### Water System: Balanced

Create `stress_testing/baseline/water_systems_balanced.yaml`:

- All 3 wells (20m/1400ppm, 50m/3500ppm, 100m/6500ppm)
- Treatment: `throughput_m3_hr: 50`
- Tank: `capacity_m3: 200`, `initial_level_m3: 200`
- Municipal: `cost_per_m3: 0.50`

This provides enough water for moderate farm profiles but will show stress under high-demand profiles (large area, furrow irrigation).

### Water Policy: Balanced

Create `stress_testing/baseline/water_policy_balanced.yaml`:

- `strategy: minimize_cost`
- `irrigation.mode: static`, `static_policy: full_eto`
- `prefill.enabled: true`
- Default caps (no municipal cap, groundwater cap 15000)
- `cap_enforcement.look_ahead: true`

### Community Demands

Copy from `settings/community_demands_base.yaml` as-is.

### Validation Run

Run one baseline simulation with a simple 4-field openfield farm profile + balanced energy + balanced water to verify the setup produces valid output. Fix any issues before proceeding.

## Phase 2: Farm Profile Tests

Each test creates a unique `farm_profile.yaml`. Energy and water systems/policies are held constant at the balanced configurations from Phase 1.

Available crops/plantings: cucumber (apr01, feb15, oct15, sep01), kale (dec01, feb01, mar15, oct01), onion (apr01, dec01, jan15), potato (jan15, nov15, sep15), tomato (apr01, aug01, feb15, nov01).

Available conditions: `openfield`, `underpv_low`, `underpv_medium`, `underpv_high`.

Available irrigation systems: `drip` (~0.90 efficiency), `sprinkler` (~0.75), `furrow` (~0.60).

| # | Test Name | Farm Profile Description | Key Checks |
|---|-----------|------------------------|------------|
| FP1 | `all_openfield` | 4 fields, all `openfield`, 2-2.5 ha, sprinkler. Year-round planting. | `*_agripv_kwh` columns are all zero; total renewable = community solar + wind only |
| FP2 | `all_underpv_high` | 4 fields, all `underpv_high`, 3 ha, sprinkler. Year-round planting. | Agri-PV dominates total renewable; `total_renewable_kwh >> total_demand_kwh`; heavy surplus/curtailment |
| FP3 | `mixed_pv_densities` | 4 fields: 1 `openfield`, 1 `underpv_low`, 1 `underpv_medium`, 1 `underpv_high`. 1.5 ha each, mixed irrigation (2 drip, 2 sprinkler). | Each density level produces a distinct `*_agripv_kwh` column; `high > medium > low` in per-field generation |
| FP4 | `small_drip_no_pv` | 2 fields, 0.5 ha each, drip, openfield. | Low water demand (drip efficiency ~0.90); no agri-PV; minimal water energy; system runs in comfortable surplus |
| FP5 | `large_furrow_high_demand` | 4 fields, 3 ha each, furrow (efficiency ~0.60), openfield. Year-round planting. | High water demand due to furrow inefficiency; water deficit likely on peak days; no agri-PV |
| FP6 | `single_field_underpv_high` | 1 field, 5 ha, `underpv_high`, drip. | Single large agri-PV field; verify single-farm energy column; compare water demand to FP4 (same irrigation type, larger area) |
| FP7 | `many_small_fields` | 8 fields across 4 farms, 0.25 ha each, mixed conditions + irrigation. Total area = 2 ha. | Tests scaling with many fields; each farm gets its own `*_agripv_kwh` column |
| FP8 | `pv_vs_openfield_paired` | Run **twice**: once with all `openfield`, once with all `underpv_high` — same areas (2.5 ha × 4), same crops, same irrigation (sprinkler). | **Paired comparison.** Same demand structure but different agri-PV. Quantify energy surplus difference. Water demand should differ slightly (underpv reduces ETc). |

### Cross-System Interaction Tests

These tests use farm profiles designed to stress the interaction between farming, water, and energy.

| # | Test Name | Farm Profile Description | Key Checks |
|---|-----------|------------------------|------------|
| FP9 | `huge_farm_minimal_infra` | 4 fields, 10 ha each, 2 openfield + 2 `underpv_medium`, sprinkler. | Maximum demand/supply mismatch against balanced infrastructure; tests graceful degradation; large underpv fields also stress agri-PV scaling |
| FP10 | `drip_vs_sprinkler_vs_furrow` | 3 fields, 2 ha each, all `openfield`. Field 1: drip, Field 2: sprinkler, Field 3: furrow. Same crop (tomato, apr01 + nov01). | Compare per-field irrigation demand: furrow >> sprinkler >> drip; total water cost and deficit differences |

## Validation Checks (apply to every test)

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

### Agri-PV specific checks (for tests with underpv fields)

- Verify that `*_agripv_kwh` columns exist for each farm with underpv fields
- Verify generation scales with area: a 3 ha `underpv_high` field should produce ~2x the agri-PV of a 1.5 ha field at the same density
- Verify `openfield` farms produce zero agri-PV

## Agent Workflow

This is designed for a multi-agent session using the Claude Code `Agent` tool. **You are the coordinator.** Do not run tests yourself — delegate every test to a subagent.

### Step 1: Setup (coordinator does this directly)

1. Create the `/stress_testing/` directory structure.
2. Write `stress_testing/run_test.py` (the shared runner script above).
3. Write the supporting baseline files in `stress_testing/baseline/`:
   - **Balanced energy system** and **balanced energy policy**
   - **Balanced water system** and **balanced water policy**
   - **Community demands** (copy from settings)
4. Run one baseline simulation with a simple openfield farm profile to verify the setup produces valid output. Fix any issues before proceeding.

### Step 2: Spawn one subagent per test

Each test row (FP1, FP2, ...) is handled by its own subagent via the `Agent` tool with `model: "sonnet"`. The subagent prompt should include:

- The test ID and name (e.g., "FP5 — large_furrow_high_demand")
- The **complete farm profile specification** to create (field count, area, condition, irrigation, crops/plantings)
- That it should use the **balanced energy** and **balanced water** configs (paths to baseline files)
- The full list of validation checks (universal + per-test key checks + agri-PV checks if applicable)
- The path to `stress_testing/run_test.py` and `settings/data_registry_base.yaml`

Each subagent:
1. Creates its subdirectory (e.g., `stress_testing/individual_tests/farm_05_large_furrow/`)
2. **Creates the farm profile YAML** from the specification in the test table
3. Copies balanced energy system, energy policy, water system, water policy, and community demands from baseline
4. Runs the simulation via `run_test.py`
5. Reads the output CSVs and runs every validation check
6. Returns a structured result: test name, farm profile summary, pass/fail per check, key metric totals (total water demand, total agri-PV, total deficit for both systems), any anomalies

### Step 3: Parallelism rules

All tests can run in parallel — each subagent writes only to its own subdirectory.

**Exception**: FP8 (paired comparison) requires the subagent to run the simulation **twice** with different farm profiles and compare the results. This is still a single subagent — it just does two runs internally.

### Step 4: Collect results

After all subagents return, the coordinator:
1. Reads each subagent's result.
2. Compiles findings into `stress_testing/farm_stress_test_report.md`.
3. Flags any tests that crashed or returned unexpected results.
4. Highlights cross-test comparisons that reveal how farm profile choices affect system behavior (e.g., FP4 vs FP5 water demand, FP1 vs FP2 energy surplus).

## Report Format

```markdown
# Farm Profile Stress Test Report

## Summary
- Tests run: N
- Passed: N
- Failed: N
- Warnings: N

## Results Table
| Test | Farm Profile | Total Water Demand (m3) | Total Agri-PV (kWh) | Water Deficit Days | Energy Deficit Days | Status | Notes |
|------|-------------|------------------------|---------------------|-------------------|-------------------|--------|-------|

## Cross-Test Comparisons
### Irrigation Efficiency Impact
- FP4 (drip, 0.5 ha) vs FP5 (furrow, 3 ha): demand ratio, deficit difference
- FP10 (drip vs sprinkler vs furrow): per-field demand breakdown

### Agri-PV Scaling
- FP1 (openfield) vs FP2 (underpv_high): energy surplus difference
- FP3 (mixed densities): per-density generation ranking
- FP8 (paired): same demand, different agri-PV — quantified impact

### Area Scaling
- FP4 (1 ha total) vs FP5 (12 ha total) vs FP9 (40 ha total)

## Failures (detailed)
### [Test Name]
- **What failed**: specific check that failed
- **Expected**: what the check expected
- **Actual**: what was observed
- **CSV evidence**: column name, row range, values

## Observations
- Parameter sensitivity findings
- Suggestions for additional test coverage
```
