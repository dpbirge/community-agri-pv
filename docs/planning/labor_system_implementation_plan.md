# Labor System Implementation Plan

Implementation plan for `src/labor.py` and supporting changes per
`specs/labor_system_specification.md`. Each task is designed for paired subagents:
one writes code, one reviews and fixes bugs.

---

## Task Dependency Graph

```
T1 (config) ──→ T3 (data loading) ──→ T4 (schedules) ──→ T5 (spreading) ──→ T7 (assembly)
T2 (rename) ──→ T4                                                             │
                 T6 (fixed/maintenance) ────────────────────────────────────→ T7
                                                                               │
                                                                        T8 (public API)
                                                                               │
                                                                        T9 (helpers)
                                                                               │
                                                                        T10 (validation)
```

---

## T1 — Configuration and Registry Updates

**Files modified:** `settings/data_registry_base.yaml`, `settings/labor_policy_base.yaml` (new),
`scenarios/scenario_base.yaml`

**What to do:**

1. Add to `settings/data_registry_base.yaml`:
   - `crops.crop_coefficients: data/crops/crop_params/crop_coefficients-research.csv`
   - New `weather:` section with `openfield` and `underpv` keys
   - `energy_equipment.pv_systems: data/energy/pv_systems-research.csv`
   - `energy_equipment.wind_turbines: data/energy/wind_turbines-research.csv`
   - New `labor:` section with `requirements`, `wages`, and `worker_mapping` keys

2. Create `settings/labor_policy_base.yaml` with the exact YAML from the spec
   (Section: Labor Policy File): `working_hours`, `heat_stress`, `irrigation_labor_multipliers`,
   `harvest_flex_days`, `cost_currency`.

3. Add `labor_policy: settings/labor_policy_base.yaml` to `scenarios/scenario_base.yaml`.

**Review focus:** Verify all file paths resolve to existing files. Check that added
registry keys don't collide with existing keys. Confirm the scenario file still loads
cleanly with `yaml.safe_load()`.

---

## T2 — Rename `_load_season_lengths` to Public API

**Files modified:** `src/farm_profile.py`, `src/crop_yield.py`

**What to do:**

1. In `src/farm_profile.py`: rename `_load_season_lengths` → `load_season_lengths`.
   Update the internal call in `validate_no_overlap` (line 78).

2. In `src/crop_yield.py`: update the import (line 40) from
   `_load_season_lengths` → `load_season_lengths` and the call site (line 247).

3. Run `python -m pytest tests/` to confirm no regressions.

**Review focus:** Grep the entire codebase for `_load_season_lengths` to ensure no
references remain. Check that `validate_no_overlap` and `compute_community_harvest`
still function correctly.

---

## T3 — Labor Module Scaffolding and Data Loading

**File created:** `src/labor.py` (initial skeleton)

**What to do:**

Create `src/labor.py` with the module docstring and these internal helpers:

1. `_load_yaml(path)` — identical pattern to other modules.

2. `_load_csv(path)` — load with `comment='#'`.

3. `_load_labor_requirements(registry, root_dir)` — load
   `labor_requirements-research.csv` via `registry['labor']['requirements']`.
   Parse into structured dicts:
   - `field_ops`: dict keyed by `(activity_type, crop)` with `hours_per_unit` and
     `worker_category`. For `crop='all'` entries, store under the key `'all'`.
   - `fixed_daily`: dict keyed by `activity_type` for `per_day` entries.
   - `maintenance`: dict keyed by `activity_type` for `per_*_per_year` entries.
   - `avs_multipliers`: dict keyed by `activity_type` for Section 7 entries.

4. `_load_wages(registry, root_dir)` — load `labor_wages-research.csv`. Return
   dict keyed by `worker_category` with `usd_per_hour`.

5. `_load_stage_durations(registry, root_dir)` — load
   `crop_coefficients-research.csv` via `registry['crops']['crop_coefficients']`.
   Return dict keyed by `(crop, stage)` with `days_in_stage`. Also return a dict
   keyed by `crop` with ordered list of `(stage, days)` tuples.

**Review focus:** Verify CSV parsing handles the `comment='#'` headers. Check that
the `crop='all'` entries are correctly handled (they apply to all 5 crops). Confirm
that the parsed structures match what downstream functions expect.

---

## T4 — Field Schedule Building

**File modified:** `src/labor.py`

**Dependencies:** T2 (needs `load_season_lengths`), T3 (needs data loading helpers)

**What to do:**

1. `_build_field_schedule(field, stage_lookup, season_lookup, sim_year)`:
   - Import `planting_code_to_mmdd`, `normalize_plantings`, `load_season_lengths`
     from `src.farm_profile`.
   - For each planting in the field, compute planting date as
     `datetime(sim_year, MM, DD)` from the planting code.
   - Look up season length from `season_lookup[(crop, mmdd)]`.
   - Look up stage durations from `stage_lookup[crop]` — ordered list of
     `(stage_name, days)`.
   - **Late-stage adjustment:** sum non-late stage durations. Adjusted late days =
     `season_length - sum(non_late_days)`. If adjusted late days <= 0, raise
     `ValueError` with crop, planting window, and mismatch details.
   - Generate a row per day of the season with columns:
     `[day, crop, growth_stage, day_of_season]`.
   - Handle year-boundary wrapping (e.g., `dec01` kale with 85-day season extends
     into February of sim_year+1 — clip to Dec 31 of sim_year, then continue from
     Jan 1 if needed). The output should cover all 365 days of sim_year.
   - Fill fallow days (between plantings or before/after) with
     `crop='none', growth_stage='fallow'`.

2. `_build_all_field_schedules(farm_config, season_lookup, stage_lookup, sim_year, *, water_system_name)`:
   - Iterate all farms → fields, filter by `water_system == water_system_name`.
   - Call `_build_field_schedule` for each field.
   - Return `{field_name: schedule_df}`.

**Key edge cases:**
- `kale` stage durations sum to 95 days but some planting windows have season
  lengths of 75 or 85 days. Late stage (15 days) gets adjusted to -5 or 5 days.
  The 75-day window (spring mar15) is invalid (non-late sum = 80 > 75) — must
  raise ValueError.
- `cucumber` stage durations sum to 100 days but spring `apr01` window is 85 days.
  Non-late sum = 85 = season length → late stage = 0 → must raise ValueError.
- Plantings that start in late Nov/Dec and extend into the next year.

**Review focus:** Test with the baseline farm profile. Verify all 365 days are
covered for each field. Confirm fallow periods are correct between sequential
plantings (e.g., north_field kale oct01 85-day season ends ~Dec 24, then fallow
until tomato feb15). Validate that ValueError is raised for invalid windows.

---

## T5 — Activity Spreading

**File modified:** `src/labor.py`

**Dependencies:** T3 (requirements data), T4 (field schedules)

**What to do:**

1. `_spread_activity(total_hours, stage_days, field_area, *, method='uniform')`:
   - `daily_hours = (total_hours * field_area) / stage_days`
   - Return a float (daily hours for uniform spreading). For pulse methods
     (fertilizer), return a dict of `{day_range: daily_hours}`.

2. `_compute_field_daily_labor(field_name, field_config, schedule_df, requirements, avs_multipliers)`:
   - For each day in schedule_df, determine active crop and growth stage.
   - Map growth stages to activities per the spec's activity mapping table:
     - `initial` → land_preparation (first 5 days only), planting (days 6+),
       fertilizer_application (days 1-7)
     - `development` → weeding (spread across stage), pest_scouting (1 day/week),
       irrigation_management
     - `mid` → irrigation_management, pest_scouting (1 day/week),
       fertilizer_application (days 1-min(7, stage_days))
     - `late` → harvesting (spread across stage), irrigation_management
   - Look up crop-specific hours from requirements. Use `(activity, crop)` key
     first; fall back to `(activity, 'all')`.
   - Apply agrivoltaic multipliers based on `field_config['condition']`:
     - `underpv_low` / `underpv_medium` → 1.07 for all field ops except weeding
     - `underpv_high` → 1.22 for all field ops except weeding
     - All `underpv_*` → 0.85 for weeding
     - `openfield` → no adjustment
   - Apply irrigation labor multiplier from policy based on
     `field_config['irrigation_system']`.
   - Return DataFrame with columns per activity (daily hours) plus
     `worker_category` assignment per activity.

**Spreading detail for each activity:**
- `land_preparation`: 22 hrs/ha uniform over first 5 days of initial stage →
  `22 * area / 5` per day
- `planting_transplant` or `planting_direct_seed`: crop-specific hrs/ha uniform
  over initial stage days 6 to end → `hrs * area / (initial_days - 5)` per day
- `weeding_manual`: crop-specific hrs/ha uniform over development stage
- `fertilizer_application`: 35 hrs/ha split 50/50: first pulse over days 1-7 of
  initial, second pulse over days 1-min(7, mid_stage_days) of mid
- `pest_scouting`: 25 hrs/ha, one day per week during development + mid stages.
  Count the weekly days, divide total hours by that count.
- `irrigation_management`: 40 hrs/ha/year × irrigation_multiplier, uniform over
  the active season days for this planting
- `harvesting`: crop-specific hrs/ha uniform over late stage (plus harvest_flex_days)

**Review focus:** Verify conservation — for each field and planting, sum of daily
hours per activity across the growing season must equal `hours_per_unit * field_area`
(within float tolerance). Test with north_field (4.9 ha openfield drip) and
west_field (0.1 ha underpv_low sprinkler) to exercise multipliers. Confirm fallow
days produce zero field labor.

---

## T6 — Fixed Daily and Maintenance Labor

**File modified:** `src/labor.py`

**Dependencies:** T3 (requirements data)

**What to do:**

1. `_compute_fixed_daily_labor(requirements)`:
   - Sum management + logistics `per_day` entries from requirements.
   - Return `{activity: hours}` and `{worker_category: hours}`.
   - Expected values (from data):
     - `management_planning`: 5 hrs/day → `manager_administrator`
     - `management_coordination`: 5 hrs/day → `field_supervisor`
     - `management_sales`: 3 hrs/day → `manager_administrator`
     - `management_administration`: 5 hrs/day → `manager_administrator`
     - `logistics_transport`: 4 hrs/day → `logistics_driver`
     - `logistics_inventory`: 3 hrs/day → `field_supervisor`

2. `_compute_maintenance_daily_labor(requirements, energy_config, water_config, farm_config, registry, root_dir)`:
   - **PV kW computation:**
     - Community solar: for each density in `energy_config['community_solar']`,
       load `pv_systems-research.csv` via `registry['energy_equipment']['pv_systems']`.
       `kw = area_ha * 10000 * (ground_coverage_pct / 100) / panel_area_m2 * panel_wattage_w / 1000`
     - Agri-PV: for each field with `condition: underpv_*`, extract density from
       suffix (e.g., `underpv_low` → `low`). Same formula with field's `area_ha`.
     - Total PV kW = community + agri-PV.
     - Maintenance: `40 hrs/100kW/yr * total_pv_kw / 100 / 365`
   - **Wind kW computation:**
     - For each turbine type in `energy_config['wind_turbines']`, load
       `wind_turbines-research.csv` via `registry['energy_equipment']['wind_turbines']`.
       `kw = number * rated_capacity_kw`
     - Maintenance: `50 hrs/100kW/yr * total_wind_kw / 100 / 365`
   - **Other equipment:**
     - BWRO: count treatment units in `water_config['systems']` →
       `300 hrs/unit/yr / 365`
     - Wells: count wells → `100 hrs/well/yr / 365`
     - Batteries: 0 or 1 from `energy_config['battery']['has_battery']` →
       `25 hrs/unit/yr / 365`
     - Generators: 0 or 1 from `energy_config['generator']['has_generator']` →
       `35 hrs/unit/yr / 365`
     - Irrigation: total irrigated area (ha) from farm_config →
       `7 hrs/ha/yr / 365`
   - Return `{equipment_type: daily_hours}` and total daily maintenance hours.
   - All maintenance labor maps to `maintenance_technician` except
     `maintenance_irrigation` which maps to `irrigation_technician`.

**Baseline expected values (for verification):**
- Community solar: 0.04 ha low density → `0.04 * 10000 * 0.30 / 2.58 * 580 / 1000`
  = ~27 kW
- Agri-PV: south_field 0.1 ha low + west_field 0.1 ha low → ~13.5 kW total
- Wind: 4 small turbines × 10 kW = 40 kW
- PV maintenance: ~40.5 kW × 40/100/365 = ~0.044 hrs/day
- Wind maintenance: 40 kW × 50/100/365 = ~0.055 hrs/day
- BWRO: 1 unit × 300/365 = ~0.82 hrs/day
- Wells: 3 × 100/365 = ~0.82 hrs/day
- Battery: 1 × 25/365 = ~0.068 hrs/day
- Generator: 1 × 35/365 = ~0.096 hrs/day
- Irrigation: 10 ha × 7/365 = ~0.19 hrs/day

**Review focus:** Verify kW computations against the PV and wind CSV data. Confirm
that omitting `energy_system_path` or `water_systems_path` (None) skips those
maintenance categories gracefully. Check that total daily maintenance is reasonable
(~2.1 hrs/day for baseline).

---

## T7 — Assembly, Worker Categories, Costs, Heat Stress

**File modified:** `src/labor.py`

**Dependencies:** T5 (field labor), T6 (fixed + maintenance)

**What to do:**

1. `_load_daily_temperatures(registry, root_dir, *, condition='openfield')`:
   - Load weather CSV via `registry['weather'][condition]`.
   - Extract `date` and `temp_max_c` columns.
   - Return Series indexed by datetime date.

2. `_compute_heat_flags(temp_c, policy)`:
   - `heat_stress_flag = 1 if temp_c > policy['heat_stress']['threshold_temp_c'] else 0`
   - `extreme_heat_flag = 1 if temp_c > policy['heat_stress']['extreme_temp_c'] else 0`
   - Return dict with both flags.

3. `_aggregate_by_worker_category(field_labor_df, fixed_labor, maintenance_labor, wages)`:
   - Map every labor hour entry to its worker category using the
     `worker_category` column from requirements data.
   - Sum hours per category per day across all sources (field, fixed, maintenance).
   - Multiply each category's hours by its wage rate from `wages` dict.
   - Return DataFrame with `{category}_hours` and cost columns.

4. `_compute_workforce_counts(category_hours, standard_day_hours)`:
   - For each category: `count = math.ceil(hours / standard_day_hours)`.
   - Return `{category}_count` columns and `total_workforce_count`.

5. `_order_labor_columns(df)`:
   - Group columns in the spec-defined order: day → activity hours →
     `total_field_hours` → `management_hours` → `maintenance_hours` →
     `logistics_hours` → `total_labor_hours` → worker category hours →
     workforce counts → cost → per-field detail → metrics.

6. Compute `peak_ratio` column: `total_field_hours / annual_mean_field_hours`.
   The annual mean is computed once and broadcast to all rows.

**Review focus:** Verify the identity `sum({category}_hours) == total_labor_hours`
holds for every row. Verify `total_labor_cost == sum(hours * wage)` for every row.
Check heat flags against a few known summer dates in the weather data (July/August
should have temp_max > 35C in Sinai). Confirm column ordering matches spec.

---

## T8 — Public API Functions

**File modified:** `src/labor.py`

**Dependencies:** T7 (all internals complete)

**What to do:**

1. `compute_labor_profile(farm_config, registry_path, *, labor_policy_path=None, energy_system_path=None, water_systems_path=None, water_system_name='main_irrigation', sim_year=2023, root_dir=None)`:
   - This is the core orchestrator. All logic lives here.
   - Steps 1-13 from the spec's orchestration steps.
   - `root_dir` defaults to `registry_path.parent.parent` (matching other modules).
   - Load registry, policy (or use defaults), requirements, wages, stage durations,
     season lengths.
   - Build field schedules, compute field labor, fixed labor, maintenance labor.
   - Load temperatures, compute heat flags.
   - Assemble into single DataFrame, aggregate by worker category, compute costs
     and workforce counts.
   - Order columns and return.

2. `compute_daily_labor_demand(farm_profiles_path, registry_path, *, labor_policy_path=None, energy_system_path=None, water_systems_path=None, water_system_name='main_irrigation', sim_year=2023, root_dir=None)`:
   - Thin wrapper: load `farm_profiles_path` YAML → call `compute_labor_profile`.

3. `save_labor_demand(df, output_dir, *, filename='daily_labor_demand.csv', decimals=2)`:
   - Same pattern as `save_energy` in `src/energy_supply.py`.
   - Round numeric columns to `decimals`, write CSV with date format.

4. `load_labor_demand(path)`:
   - Same pattern as `load_energy`. Read CSV with `comment='#'`, parse dates.

5. Add `if __name__ == '__main__':` block matching the spec's standalone
   verification section.

**Review focus:** Run standalone: `python -m src.labor`. Verify output shape (365
rows), column count and names match spec. Verify the saved CSV loads back correctly.
Check that omitting optional paths (energy_system, water_systems) produces valid
output (just without equipment maintenance rows for those categories).

---

## T9 — Labor Smoothing Helper Functions

**File modified:** `src/labor.py`

**Dependencies:** T8 (public API complete)

**What to do:**

1. `summarize_labor_profile(labor_df)`:
   - Compute all metrics from the spec: `total_hours`, `mean_daily_hours`,
     `peak_daily_hours`, `peak_ratio`, `cv`, `summer_hours` (Jun-Aug),
     `summer_share`, `heat_stress_days`, `peak_harvester_count`,
     `peak_field_worker_count`, `seasonal_harvester_person_days`.
   - Return dict.

2. `test_staggered_plantings(farm_config, registry_path, *, crop, offsets_days=None, labor_policy_path=None, sim_year=2023, root_dir=None)`:
   - Default offsets: `[0, 3, 5, 7, 10, 14]`.
   - Find all fields growing `crop`.
   - For each offset: shift each successive field's planting code by
     `field_index * offset` days.
   - Validate: skip offsets that push outside valid planting window (±14 days of
     any registered window) or cause overlap with other plantings in same field.
   - Catch `ValueError` from `_build_field_schedule` (invalid late-stage windows)
     and exclude from results.
   - Call `compute_labor_profile` + `summarize_labor_profile` for each valid config.
   - Return DataFrame sorted by `peak_ratio` ascending.

3. `test_crop_mix(farm_config, registry_path, *, field_name, original_crop, replacement_crops=None, labor_policy_path=None, sim_year=2023, root_dir=None)`:
   - Default replacements: all 5 crops.
   - For each replacement crop, find valid planting dates from
     `planting_windows-research.csv` that don't overlap other plantings in the field.
   - Catch `ValueError` for invalid windows and exclude.
   - Return DataFrame sorted by `peak_ratio`.

4. `compare_farm_profiles(baseline_config, alternative_config, registry_path, *, labor_policy_path=None, sim_year=2023, root_dir=None)`:
   - Run `compute_labor_profile` + `summarize_labor_profile` for both configs.
   - Return dict with `baseline`, `alternative`, and `delta` (numeric differences).

**Review focus:** Test `summarize_labor_profile` with baseline output — verify
metrics are reasonable (peak_ratio should be > 1, summer_share between 0 and 1,
heat_stress_days > 0). Test `test_staggered_plantings` with `crop='cucumber'`
(east_field has two cucumber plantings) — verify it produces multiple rows and that
higher offsets reduce peak_ratio. Verify that invalid window combinations are
excluded rather than raising exceptions.

---

## T10 — Integration Testing and Validation

**Files modified/created:** tests (if needed), notebooks

**Dependencies:** T8 and T9 complete

**What to do:**

1. Run `python -m src.labor` standalone — verify the 7 validation checks from the
   spec:
   - **Conservation:** per-field per-planting activity hour sums match
     `hours_per_unit * field_area`.
   - **Fallow zeros:** field operations are 0 on fallow days.
   - **Stage alignment:** growth stage column matches arithmetic from stage durations.
   - **Heat stress flags:** correct for known hot days.
   - **Worker category totals:** `sum(category_hours) == total_labor_hours` every row.
   - **Cost identity:** `total_labor_cost == sum(hours * wage)` every row.
   - **Existing tests pass:** `python -m pytest tests/`.

2. Run `python -m pytest tests/` to confirm the rename in T2 caused no regressions
   and no existing tests break.

3. Verify the `simulation/daily_labor_demand.csv` output looks reasonable:
   - 365 rows, all expected columns present.
   - Harvesting hours peak during late-stage periods.
   - Management hours are constant (25 hrs/day: 13 manager + 8 supervisor + 4 driver).
   - Maintenance hours are approximately constant (~2.1 hrs/day).
   - Heat stress flags appear in summer months.
   - Total annual labor hours are in a reasonable range for a 10-ha farm.

**Review focus:** This task is primarily about running verification, not writing new
code. The reviewer subagent should independently re-derive expected values for 2-3
spot-check days (e.g., a harvest day, a fallow day, a planting day) and compare
against the CSV output.

---

## Execution Notes

**Parallel opportunities:** T1 and T2 are independent — run concurrently. T3 and T6
have no dependency between them beyond T1, so they can overlap. T9 helper functions
are independent of each other and can be written in parallel once T8 is done.

**Task sizing:** T4 (schedule building) and T5 (activity spreading) are the most
complex and error-prone tasks. T4's year-boundary wrapping and late-stage adjustment
logic requires careful testing. T5's spreading formulas must conserve total hours.

**Key data relationships:**
- `crop_coefficients-research.csv` has 4 rows per crop (stage durations)
- `planting_windows-research.csv` has `expected_season_length_days` per (crop, date)
- The late stage is the adjustment variable: `late_days = season_length - sum(init + dev + mid)`
- `labor_requirements-research.csv` Section 1 has `per_hectare` seasonal totals
  that must be spread, not daily rates
