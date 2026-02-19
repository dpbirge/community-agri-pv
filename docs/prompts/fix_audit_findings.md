# Prompt: Fix Audit Findings — Data Gaps and Hardcoded Values

## Objective

Systematically resolve all 10 recommended actions from the audit report at `docs/codereview/data_gaps_and_hardcoded_values_audit.md`. Work through them in priority order. **Launch a dedicated subagent (Task tool) for each action** so each has room to read files, implement changes, and verify its work without crowding the main context.

## Execution Rules

- Process actions sequentially (1 through 10). Do NOT start the next action until the current subagent returns successfully.
- Each subagent must: (a) read the relevant source files and data files, (b) implement the fix, (c) verify the fix by running `python -c "import src.simulation.simulation"` or equivalent import check to confirm no import errors were introduced.
- After each subagent completes, update the todo list to mark it done.
- If a subagent encounters a design ambiguity, it should make the simplest choice that preserves existing behavior and leave a `# TODO:` comment explaining the trade-off.
- Do NOT change simulation output behavior. Every externalization must produce the same numeric values as the current hardcoded ones. This is a refactor, not a feature change.
- Follow the project's Python coding principles from CLAUDE.md: no typing unless critical, functional style, fail explicitly (no try/except fallbacks that inject dummy values).

## Reference Files

- **Audit report**: `docs/codereview/data_gaps_and_hardcoded_values_audit.md` (the source of truth for line numbers and values)
- **Data registry**: `settings/data_registry.yaml`
- **Scenario config**: `settings/settings.yaml`
- **Key source files**: `src/simulation/simulation.py`, `src/simulation/state.py`, `src/simulation/data_loader.py`, `src/settings/calculations.py`, `src/settings/loader.py`, `src/settings/validation.py`, `src/policies/crop_policies.py`, `src/policies/food_policies.py`, `src/policies/energy_policies.py`
- **Key data files**: `data/parameters/equipment/batteries-toy.csv`, `data/parameters/equipment/generators-toy.csv`, `data/parameters/equipment/pv_systems-toy.csv`, `data/parameters/labor/labor_requirements-toy.csv`, `data/parameters/labor/labor_wages-toy.csv`

---

## Action 1: Externalize Battery and Generator Parameters

**Scope**: `simulation.py:567-575`, `state.py:355-365`
**Target data files**: `equipment/batteries-toy.csv`, `equipment/generators-toy.csv`

Steps:
1. Read `batteries-toy.csv` and `generators-toy.csv` to see what columns already exist.
2. If columns for SOC min/max, charge/discharge efficiency, initial SOC are missing, add them to the CSV with the current hardcoded values.
3. In `simulation.py`, load these values from the CSV at simulation init (likely in `calculate_system_constraints` or early in `run_simulation`) and pass them through to `dispatch_energy`. Replace the 7 hardcoded literals (lines 567-575) with the loaded values.
4. For generator params (min_load=0.30, sfc_a=0.06, sfc_b=0.20), do the same from `generators-toy.csv`.
5. In `state.py`, update `EnergyState` dataclass defaults to `None` or remove defaults entirely so the values must come from the CSV. If removing defaults would break initialization elsewhere, keep the current values as fallbacks but add a comment that these should match the CSV.
6. Also centralize the duplicated PV degradation rate (`0.005` at lines 174 and 639) — load once from `pv_systems-toy.csv` and reference in both locations.
7. Move the shading factors dict (line 642: `{"low": 0.95, "medium": 0.90, "high": 0.85}`) to `pv_systems-toy.csv` as a `shading_factor` column alongside the existing density rows.
8. Verify: `python -c "from src.simulation.simulation import run_simulation; print('OK')"`.

---

## Action 2: Externalize Labor Constants

**Scope**: `calculations.py:821-850` (labor rate, working days, field hours, crop multipliers, processing hours, maintenance hours, admin fraction, harvest multiplier)
**Target data files**: `labor/labor_requirements-toy.csv`, `labor/labor_wages-toy.csv`

Steps:
1. Read both labor CSVs to see existing columns.
2. Add missing columns/rows for: base_field_hours_per_ha_per_year, crop multipliers (per crop row), processing_hours_per_kg, maintenance hours (per equipment type), admin_overhead_fraction, harvest_multiplier, working_days_per_year.
3. Add labor_rate_usd_per_hour to `labor_wages-toy.csv` if not present.
4. In `calculations.py`, write a loader function that reads these CSVs and returns the values. Replace the ~12 hardcoded constants with calls to this loader.
5. Keep the `LABOR_CROP_MULTIPLIERS` dict structure but populate it from CSV data instead of inline literals.
6. Verify: `python -c "from src.settings.calculations import calculate_labor_costs; print('OK')"` (or whatever the relevant function is named).

---

## Action 3: Centralize PV Density Coverage Lookup

**Scope**: `validation.py:122`, `loader.py:368`, `calculations.py:368` — all contain `{"low": 0.30, "medium": 0.50, "high": 0.80}`
**Target data file**: `equipment/pv_systems-toy.csv` (already has `ground_coverage_pct` column)

Steps:
1. Read `pv_systems-toy.csv` to confirm the `ground_coverage_pct` column exists and has values for low/medium/high density rows.
2. Create a single shared utility function (in `data_loader.py` or a small helper) that loads the density-to-coverage mapping from the CSV and returns a dict.
3. Replace the inline dict in all 3 files with a call to this shared function.
4. If the CSV values differ from the hardcoded `{0.30, 0.50, 0.80}`, use the CSV values (they are the source of truth) and note the discrepancy.
5. Verify: `python -c "from src.settings.validation import validate_scenario; print('OK')"`.

---

## Action 4: Derive Crop List from Registry

**Scope**: `data_loader.py:684, 689, 709` — hardcoded `["tomato","potato","onion","kale","cucumber"]` in 3 places

Steps:
1. Read `data_registry.yaml` to identify the pattern for crop-specific entries (likely keys like `irrigation_demand_tomato`, `yield_tomato`, `prices_tomato`, etc.).
2. Write a function in `data_loader.py` that extracts the crop list by scanning registry keys for a consistent pattern (e.g., keys matching `yield_*` or `irrigation_demand_*`).
3. Replace all 3 hardcoded crop lists with calls to this function.
4. Verify the derived list matches `["tomato","potato","onion","kale","cucumber"]` exactly.
5. Verify: `python -c "from src.simulation.data_loader import SimulationDataLoader; print('OK')"`.

---

## Action 5: Create crop_salinity_tolerance.csv

**Scope**: New file `data/parameters/crops/crop_salinity_tolerance-toy.csv`

Steps:
1. Read `docs/arch/calculations.md` section on soil salinity / FAO-29 to find what columns are needed (ECe threshold, slope b, crop name at minimum).
2. Create the CSV with the standard metadata header format (see any existing CSV in `data/parameters/crops/` for the template).
3. Populate with FAO-29 values for the 5 project crops (tomato, potato, onion, kale, cucumber). Use published FAO Irrigation and Drainage Paper 29 values:
   - Tomato: ECe threshold = 2.5 dS/m, slope b = 9.9%
   - Potato: ECe threshold = 1.7 dS/m, slope b = 12.0%
   - Onion: ECe threshold = 1.2 dS/m, slope b = 16.0%
   - Kale (use cabbage proxy): ECe threshold = 1.8 dS/m, slope b = 9.7%
   - Cucumber: ECe threshold = 2.5 dS/m, slope b = 13.0%
4. Add the new file to `data_registry.yaml` under an appropriate key (e.g., `crop_salinity_tolerance`).
5. Verify the CSV is well-formed: `python -c "import pandas as pd; df = pd.read_csv('data/parameters/crops/crop_salinity_tolerance-toy.csv', comment='#'); print(df)"`.

---

## Action 6: Fix loader.py Fallback Mismatches

**Scope**: `loader.py:406` (PV height 4.0 vs settings.yaml 3.0 m), `loader.py:591` (unsubsidized ag water price 1.20 vs settings.yaml 0.75 USD/m3)

Steps:
1. Read `loader.py` around lines 400-410 and 585-595.
2. Read `settings.yaml` to confirm the canonical values.
3. Update the two fallback values in `loader.py` to match `settings.yaml`:
   - PV height: `4.0` → `3.0`
   - Unsubsidized ag water price: `1.20` → match whatever `settings.yaml` says for the unsubsidized agricultural rate (check the exact key path)
4. Add a comment on each fallback line: `# fallback must match settings.yaml default`
5. Verify: `python -c "from src.settings.loader import load_scenario; print('OK')"`.

---

## Action 7: Externalize Crop Policy Temperature Thresholds

**Scope**: `crop_policies.py:133-141` — temperature thresholds (40, 35, 20°C) and irrigation multipliers (1.15, 1.05, 0.85)

Steps:
1. Read `crop_policies.py` to understand the `WeatherAdaptive` policy class structure.
2. Make these thresholds configurable: either (a) add them as constructor parameters with current values as defaults, or (b) load from a new section in `settings.yaml` under `policy_parameters.crop.weather_adaptive`.
3. Prefer option (a) — constructor params with defaults — since these are policy tuning knobs, not physical data.
4. Update the scenario YAML schema in `structure.md` if adding new YAML keys.
5. Verify: `python -c "from src.policies.crop_policies import get_crop_policy; p = get_crop_policy('weather_adaptive'); print('OK')"`.

---

## Action 8: Externalize Food Policy Reference Prices

**Scope**: `food_policies.py:149-154` — `REFERENCE_PRICES = {"tomato": 0.30, "potato": 0.25, ...}`

Steps:
1. Read `food_policies.py` to understand how `REFERENCE_PRICES` is used (likely in `market_responsive` policy).
2. The recommendation is to derive these from historical price data at runtime. Read one of the price files (e.g., `data/prices/crops/historical_tomato_prices-research.csv`) to understand the format.
3. Write a function that computes the mean or median price from historical data for each crop, and use that as the reference price.
4. If historical data isn't available for all crops at the time the policy initializes, fall back to the current hardcoded values but print a warning.
5. The function should accept the data loader or registry path so it can find the price files.
6. Verify: `python -c "from src.policies.food_policies import get_food_policy; print('OK')"`.

---

## Action 9: Fix Filename Discrepancies in Architecture Docs

**Scope**: 8 discrepancies listed in audit report Section 1.2

Steps:
1. Read the audit report Section 1.2 for the full list of 8 discrepancies.
2. For each discrepancy, read the relevant section of the architecture doc and update the file path references to match the actual filenames on disk.
3. Specifically in `calculations.md`:
   - `data/precomputed/irrigation/crop_water_requirements-toy.csv` → `data/precomputed/irrigation_demand/irrigation_m3_per_ha_<crop>-toy.csv`
   - `crop_parameters-toy.csv` → `crop_coefficients-toy.csv`
   - `data/precomputed/power/pv_power_output_normalized-toy.csv` → `data/precomputed/pv_power/pv_normalized_kwh_per_kw_daily-toy.csv`
   - `data/precomputed/power/wind_power_output_normalized-toy.csv` → `data/precomputed/wind_power/wind_normalized_kwh_per_kw_daily-toy.csv`
   - `data/precomputed/yields/crop_yields-toy.csv` → `data/precomputed/crop_yields/yield_kg_per_ha_<crop>-toy.csv`
   - `data/parameters/processing/food_processing_equipment-toy.csv` → `data/parameters/equipment/processing_equipment-toy.csv`
4. In `data.md`:
   - `tomato_prices-research.csv` → `historical_tomato_prices-research.csv` (and similar for all crop price references)
   - `post_harvest_losses-*.csv` → `handling_loss_rates-*.csv`
5. Verify each referenced file actually exists on disk using glob.

---

## Action 10: Add Fertilizer Costs to Data Registry

**Scope**: `settings/data_registry.yaml` — missing entry for `data/prices/inputs/historical_fertilizer_costs-toy.csv`

Steps:
1. Read `data_registry.yaml` to find where price entries are organized.
2. Confirm the file exists: `data/prices/inputs/historical_fertilizer_costs-toy.csv`.
3. Add a new section `prices_inputs` (or append to existing price section) with a `fertilizer_costs` key pointing to the file.
4. Follow the existing registry format exactly (check indentation, comment style).
5. Run the registry validator: `python src/settings/validation.py --registry` to confirm no errors.

---

## Completion

After all 10 actions are done:
1. Run a full import check: `python -c "from src.simulation.simulation import run_simulation; from src.settings.loader import load_scenario; from src.settings.calculations import *; print('All imports OK')"`.
2. Update the audit report summary section to note which actions have been resolved.
3. Report back with a summary of all changes made, any design decisions that required judgment calls, and any items that could not be fully resolved.
