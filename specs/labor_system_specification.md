# Labor System Specification

---

## Purpose

Compute daily labor demand, cost, and workforce requirements for the community
farm system. The labor module is an **observer** — it reads decisions made by
other modules (farm profiles, crop growth, water balance, energy balance) and
reports their labor consequences. It does not influence dispatch or scheduling.

A companion set of **helper functions** enables testing alternative farm profile
configurations (crop mixes, planting dates, staggered starts) to smooth daily
labor demand curves and reduce peak workforce requirements, especially during
hot summer months.

---

## Implementation Status

### Complete

**Data files** (`data/labor/`):

- `labor_requirements-research.csv` — crop-specific and activity-based labor
  hours per hectare, per kg, per day, and per unit. 7 sections: field
  operations, processing, management, equipment maintenance, logistics, model
  parameters, agrivoltaic adjustments. 10 worker categories.
- `labor_wages-research.csv` — 10 worker categories with USD/hour and EGP/hour
  wages, skill levels, typical hours per week. Based on 2024 Egyptian minimum
  wage (EGP 28/hour baseline).
- `worker_category_mapping-research.csv` — bridge table mapping 10 worker
  categories to 3 skill levels (unskilled, semi-skilled, skilled) with wage
  multipliers and value chain stage assignments.
- `processing_labor-research.csv` — per-kg processing labor hours by crop and
  processing type (fresh, packaged, canned, dried).
- `storage_labor-research.csv` — recurring monthly per-ton storage labor and
  one-time loading/curing operations for cold and ambient storage.
- `distribution_labor-research.csv` — farmgate distribution model: daily
  operations, per-transaction labor, record keeping, transport coordination.
- `fresh_packaging_labor-toy.csv` — toy-grade packaging labor rates.
- `processed_packaging_labor-toy.csv` — toy-grade processed packaging labor.
- `labor_requirements-toy.csv` — simplified toy-grade labor benchmarks.

**Configuration files** (`settings/`):

- `farm_profile_base.yaml` — field definitions with crop assignments, planting
  dates, areas, irrigation systems, and agri-PV conditions. This is the primary
  input that drives labor demand timing.

**Source modules** (`src/`):

- `src/farm_profile.py` — planting code conversion (`oct01` → `10-01`),
  planting normalization, overlap validation. Used by the labor module to
  resolve planting schedules.
- `src/irrigation_demand.py` — loads crop daily growth CSVs and computes daily
  field-level demand. The labor module reuses the same crop daily growth data
  to determine growth stage on each day.

**Crop parameter data** (`data/crops/crop_params/`):

- `crop_coefficients-research.csv` — growth stage durations in days per crop
  (initial, development, mid, late). The labor module computes growth stage
  timing arithmetically from planting date + these durations. It does **not**
  read the `growth_stage` column from crop daily growth CSVs — this decouples
  labor from the pre-computed data pipeline and allows the helper functions to
  test arbitrary planting date offsets.
- `planting_windows-research.csv` — season lengths and valid planting date
  windows for all 5 crops. Used to validate planting date offsets in helpers.

### Not Yet Implemented

- `src/labor.py` — daily labor demand computation module
- `settings/labor_policy_base.yaml` — labor policy configuration
- `data_registry_base.yaml` updates — labor section in the data registry
- `simulation/daily_labor_demand.csv` — daily labor output
- Helper functions for farm profile labor smoothing

---

## Problem Statement

### Monocropping Labor Spikes

When multiple fields plant or harvest the same crop on the same date, labor
demand concentrates into sharp peaks. The baseline farm profile
(`farm_profile_base.yaml`) has 4 fields across 2 farms:

| Field | Area | Plantings |
|---|---|---|
| north_field | 1 ha | kale (oct01), tomato (feb15) |
| south_field | 1 ha | potato (sep15), onion (jan15) |
| east_field | 1 ha | cucumber (feb15), cucumber (sep01) |
| west_field | 1 ha | tomato (apr01), kale (dec01) |

Two tomato plantings (north feb15, west apr01) and two kale plantings (north
oct01, west dec01) create overlapping harvest-labor periods. If fields were
configured with identical planting dates, peaks would double.

### Harvest Labor Dominance

Harvesting is the most labor-intensive field operation by a wide margin:

| Crop | Harvest (hrs/ha) | Planting (hrs/ha) | Weeding (hrs/ha) |
|---|---|---|---|
| cucumber | 370 | 50 | 100 |
| tomato | 350 | 210 | 125 |
| kale | 300 | 180 | 100 |
| onion | 175 | 200 | 150 |
| potato | 120 | 70 | 100 |

Cucumber and tomato harvest require 3–7x more labor than their planting. A
single 1-ha cucumber field at harvest demands 370 hours of seasonal_harvester
labor — roughly 46 person-days at 8 hours/day, compressed into 15 days (the
late growth stage for cucumber). This is ~3 seasonal harvesters working full
time for the entire late stage.

### Summer Heat Constraint

Sinai summer temperatures exceed 35°C. Outdoor field labor productivity drops
and heat-related illness risk rises. The labor module must flag days when
ambient temperature limits safe working hours, and the helper functions should
enable testing planting schedules that shift harvest labor away from Jun–Aug.

---

## Architecture

### Module Position

```
farm_profile_base.yaml ──────────→ src/farm_profile.py ──→ planting schedule
                                                                │
crop_coefficients-research.csv ──→ stage durations (arithmetic) │
                                                                ▼
                                                          src/labor.py
                                                          (daily labor)
                                                                │
labor_requirements-research.csv ──→ activity rates              │
labor_wages-research.csv ──────→ cost rates                     │
labor_policy_base.yaml ────────→ policy config                  │
                                                                ▼
                                                  daily_labor_demand.csv
```

The labor module sits downstream of farm profile decisions. It does not call
`compute_irrigation_demand()` or `compute_water_supply()`. It computes growth
stage timing arithmetically from planting dates + stage durations in
`crop_coefficients-research.csv`, then maps stages to labor activities. This
arithmetic approach decouples labor from the pre-computed crop daily growth
CSVs, enabling the helper functions to test arbitrary planting date offsets.

### Functional Programming

No classes, no stateful objects. State is passed as plain dicts. Internal
helpers prefixed with `_`. Public API uses keyword arguments with defaults.
Follows the pattern of `src/irrigation_demand.py` and `src/water.py`.

---

## Labor Activity Model

### Growth Stage to Activity Mapping

Each day of each field's growing season falls into one of four FAO growth
stages. Labor activities are assigned to stages based on agronomic practice:

| Growth Stage | Duration (varies by crop) | Labor Activities |
|---|---|---|
| initial | 20–30 days | land_preparation (first 5 days only), planting, fertilizer_application (days 1–7) |
| development | 30–40 days | weeding (spread across stage), pest_scouting (weekly), irrigation_management |
| mid | 30–70 days | irrigation_management, pest_scouting (weekly), fertilizer_application (at stage start) |
| late | 15–30 days | harvesting (spread across stage), irrigation_management |

### Activity Spreading Rules

Per-hectare seasonal labor totals from `labor_requirements-research.csv` must
be spread across the days within their assigned growth stage. The spreading
method depends on the activity:

| Activity | Spreading Method | Rationale |
|---|---|---|
| land_preparation | Uniform over first 5 days of initial stage | Equipment-limited; done before planting |
| planting_transplant / planting_direct_seed | Uniform over initial stage days 6–end | Follows land prep |
| weeding_manual | Uniform over development stage | Continuous during rapid vegetative growth |
| fertilizer_application | Two pulses: 50% over days 1–7 of initial, 50% over days 1–7 of mid | Split application is standard practice |
| pest_scouting | One day per week during development + mid stages | Weekly scouting rounds |
| irrigation_management | Uniform over entire season | Daily system checks proportional to area |
| harvesting | Uniform over late stage | Continuous picking/digging during maturation |

**Spreading formula** (uniform case):

```
daily_hours = (total_hours_per_ha × field_area_ha) / days_in_activity_window
```

### Fallow Period Labor

When a field has no active crop (between harvest of one planting and the start
of the next), it still incurs minimal labor:

- `irrigation_management`: 0 (no crop to irrigate)
- `pest_scouting`: 0
- Equipment maintenance continues (see below)

### Non-Field Labor (Fixed Daily)

These activities run year-round regardless of crop schedules:

| Activity | Hours/Day | Worker Category |
|---|---|---|
| management_planning | 5 | manager_administrator |
| management_coordination | 5 | field_supervisor |
| management_sales | 3 | manager_administrator |
| management_administration | 5 | manager_administrator |
| logistics_transport | 4 | logistics_driver |
| logistics_inventory | 3 | field_supervisor |

### Equipment Maintenance (Annualized Daily)

Annual maintenance hours from `labor_requirements-research.csv` are spread
uniformly across 365 days. The labor module reads energy system and water
system configurations to determine equipment counts:

| Equipment | Annual Hours | Per-Unit Basis | Source Config |
|---|---|---|---|
| PV systems | 40 hrs/100 kW/yr | total community + agri-PV kW | energy_system_base.yaml + farm profiles |
| Wind turbines | 50 hrs/100 kW/yr | total wind kW | energy_system_base.yaml |
| BWRO treatment | 300 hrs/unit/yr | treatment unit count | water_systems_base.yaml |
| Wells | 100 hrs/well/yr | well count | water_systems_base.yaml |
| Batteries | 25 hrs/unit/yr | battery count (0 or 1) | energy_system_base.yaml |
| Generators | 35 hrs/unit/yr | generator count (0 or 1) | energy_system_base.yaml |
| Irrigation systems | 7 hrs/ha/yr | irrigated area | farm_profile_base.yaml |

### Irrigation System Labor Modifier

The `irrigation_management` activity rate (40 hrs/ha/year from
`labor_requirements-research.csv`) is a baseline for drip irrigation. Different
irrigation systems require substantially different labor. The module applies a
per-field multiplier based on the field's `irrigation_system` value from the
farm profile:

| Irrigation System | Labor Multiplier | Rationale |
|---|---|---|
| drip | 1.0 | Baseline — automated, low daily labor |
| sprinkler | 1.8 | Manual repositioning, nozzle checks, pressure monitoring |
| furrow | 3.0 | Manual gate/siphon management, leveling, higher frequency |

The multiplier is applied to the `irrigation_management` hours for that field:
`daily_irrigation_hours = (40 × multiplier × field_area_ha) / season_days`.

The multipliers are defined in the labor policy file under
`irrigation_labor_multipliers`. This allows testing the labor impact of
switching a field's irrigation system without changing the base data.

### Agrivoltaic Labor Adjustments

Fields with `condition: underpv_*` incur labor multipliers from
`labor_requirements-research.csv`:

| Condition | Multiplier | Applies To |
|---|---|---|
| underpv_low, underpv_medium | 1.07 (elevated panels) | All field operations except weeding |
| underpv_high | 1.22 (low clearance) | All field operations except weeding |
| All underpv_* | 0.85 (weeding reduction) | Weeding only — shade suppresses weed growth |

The module determines which multiplier to apply based on the `condition` value
in the field definition. `openfield` fields receive no adjustment (1.0).

---

## Configuration

### Labor Policy File

**New file: `settings/labor_policy_base.yaml`**

```yaml
# Labor demand estimation policy.
# Paired with a scenario file via the labor_policy key.

labor_policy_name: baseline_labor_policy

# --- Working Conditions ---
working_hours:
  standard_day_hours: 8          # hours per standard working day

# --- Heat Stress Tracking ---
# Track days when outdoor temperatures exceed safe working thresholds.
# The module reports these as flags in the output — it does NOT reduce
# labor hours or block work. The output shows how many days workers
# are exposed to unsafe conditions, for planning and risk assessment.
heat_stress:
  threshold_temp_c: 35           # flag days above this as heat stress
  extreme_temp_c: 42             # flag days above this as extreme heat
  weather_condition: openfield   # which weather file to use for temperature

# --- Irrigation Labor Multipliers ---
# Multiplier on base irrigation_management hours (40 hrs/ha/year) by system.
# Drip is the baseline (1.0). Higher values reflect more manual labor.
irrigation_labor_multipliers:
  drip: 1.0
  sprinkler: 1.8
  furrow: 3.0

# --- Harvest Labor Window ---
# Harvesting can extend beyond the late growth stage by this many days
# to reflect real-world flexibility in harvest timing.
harvest_flex_days: 0             # additional days beyond late stage end

# --- Cost Reporting ---
# Currency for cost columns. Wages are stored in USD; EGP conversion
# uses the exchange rate from labor_wages-research.csv.
cost_currency: usd
```

### Data Registry Additions

**Add to `settings/data_registry_base.yaml`:**

```yaml
labor:
  requirements: data/labor/labor_requirements-research.csv
  wages: data/labor/labor_wages-research.csv
  worker_mapping: data/labor/worker_category_mapping-research.csv
```

### Scenario File Addition

**Add to `scenarios/scenario_base.yaml`:**

```yaml
labor_policy: settings/labor_policy_base.yaml
```

---

## Daily Output Columns

### Demand by Activity (hours/day)

| Column | Description |
|---|---|
| `day` | Calendar date |
| `land_preparation_hours` | Total land prep hours across all active fields |
| `planting_hours` | Total planting/transplant/direct-seed hours |
| `weeding_hours` | Total manual weeding hours |
| `fertilizer_hours` | Total fertilizer application hours |
| `pest_scouting_hours` | Total pest scouting hours |
| `irrigation_mgmt_hours` | Total irrigation management hours |
| `harvesting_hours` | Total harvesting hours |
| `total_field_hours` | Sum of all field operation hours |
| `management_hours` | Sum of all management/admin hours (fixed daily) |
| `maintenance_hours` | Sum of all equipment maintenance hours (annualized daily) |
| `logistics_hours` | Sum of logistics hours (fixed daily) |
| `total_labor_hours` | Grand total: field + management + maintenance + logistics |

### Demand by Worker Category (hours/day)

| Column | Description |
|---|---|
| `field_worker_hours` | Hours for field_worker category |
| `field_supervisor_hours` | Hours for field_supervisor category |
| `seasonal_harvester_hours` | Hours for seasonal_harvester category |
| `equipment_operator_hours` | Hours for equipment_operator category |
| `irrigation_technician_hours` | Hours for irrigation_technician category |
| `maintenance_technician_hours` | Hours for maintenance_technician category |
| `manager_administrator_hours` | Hours for manager_administrator category |
| `quality_inspector_hours` | Hours for quality_inspector category |
| `logistics_driver_hours` | Hours for logistics_driver category |

### Workforce (headcount/day)

| Column | Description |
|---|---|
| `field_worker_count` | `ceil(field_worker_hours / standard_day_hours)` |
| `seasonal_harvester_count` | `ceil(seasonal_harvester_hours / standard_day_hours)` |
| `equipment_operator_count` | `ceil(equipment_operator_hours / standard_day_hours)` |
| `total_workforce_count` | Sum of all category counts |

Headcount uses `standard_day_hours` (8 hours) as the denominator. The module
does not reduce labor on heat stress days — it reports the full demand and
flags the unsafe conditions separately.

### Cost (per day)

| Column | Description |
|---|---|
| `field_labor_cost` | Sum of (hours × wage) for field operation categories |
| `management_labor_cost` | Sum of (hours × wage) for management categories |
| `maintenance_labor_cost` | Sum of (hours × wage) for maintenance categories |
| `total_labor_cost` | Grand total daily labor cost |

### Per-Field Detail (hours/day)

| Column | Description |
|---|---|
| `{field}_labor_hours` | Total labor hours for this field |
| `{field}_crop` | Active crop name (`none` if fallow) |
| `{field}_growth_stage` | Current growth stage (`fallow` if no crop) |

### Metrics

| Column | Description |
|---|---|
| `daily_max_temp_c` | Daily maximum temperature from weather data |
| `heat_stress_flag` | 1 if daily max temp exceeds `threshold_temp_c` (35°C), 0 otherwise |
| `extreme_heat_flag` | 1 if daily max temp exceeds `extreme_temp_c` (42°C), 0 otherwise |
| `peak_ratio` | `total_field_hours / annual_mean_field_hours` — spikiness indicator |

---

## Internal Helper Functions

### Data Loading

- `_load_yaml(path)` — Load YAML config. Identical to other modules.
- `_load_csv(path)` — Load CSV with `comment='#'`. Identical to other modules.

### Schedule Building

- `_build_field_schedule(field, stage_lookup, season_lookup, sim_year)` — For
  one field, produce a DataFrame with columns `[day, crop, growth_stage,
  day_of_season]` covering the simulation year. Computes stage boundaries
  arithmetically from planting date + stage durations in
  `crop_coefficients-research.csv`. Uses `planting_code_to_mmdd()` from
  `src/farm_profile.py` for date conversion. Fallow days between plantings
  get `crop='none'`, `growth_stage='fallow'`. Handles year-boundary wrapping
  for plantings that start late in the calendar year (e.g., dec01 kale
  harvests in February).

  **Stage-duration vs. season-length reconciliation:** The sum of stage
  durations from `crop_coefficients-research.csv` does not always match the
  `expected_season_length_days` from `planting_windows-research.csv`. For
  example, cucumber stages sum to 100 days but the fall window is 95 days;
  kale stages sum to 95 days but the spring window is 75 days. The
  authoritative season length is `expected_season_length_days` from the
  planting windows file. When they differ, the **late stage is adjusted**
  (truncated or extended) so the total season matches. All other stages
  keep their standard durations. This means harvest labor intensity scales
  inversely with late-stage length — a shorter late stage concentrates the
  same total harvest hours into fewer days, requiring more harvesters.

- `_build_all_field_schedules(farm_config, season_lookup, stage_lookup, sim_year, *, water_system_name)` —
  Iterate all fields across all farms, call `_build_field_schedule` for each,
  return a dict of `{field_name: schedule_df}`.

### Activity Spreading

- `_spread_activity(total_hours, stage_days, field_area, *, method='uniform')` —
  Distribute `total_hours × field_area` across `stage_days` according to the
  specified spreading method. Returns a Series indexed by day_of_season.

- `_compute_field_daily_labor(field_name, field_config, schedule_df, requirements, avs_multipliers)` —
  For one field, apply all activity-to-stage mappings (Section: Growth Stage to
  Activity Mapping), apply agrivoltaic multipliers if `condition` is `underpv_*`,
  return a DataFrame with columns for each activity's daily hours and worker
  category assignment.

### Assembly

- `_compute_fixed_daily_labor(requirements)` — Sum management + logistics
  fixed daily hours. Returns a dict of `{activity: hours}` and a dict of
  `{worker_category: hours}`.

- `_compute_maintenance_daily_labor(requirements, energy_config, water_config, farm_config)` —
  Compute annualized daily equipment maintenance hours from infrastructure
  counts. Returns a dict of `{equipment_type: daily_hours}`.

- `_aggregate_by_worker_category(field_labor_df, fixed_labor, maintenance_labor, wages)` —
  Map all labor hours to worker categories using the `worker_category` column
  from `labor_requirements-research.csv`, sum by category, multiply by wage
  rate.

- `_compute_workforce_counts(category_hours, effective_day_hours)` — Divide
  each category's hours by `effective_day_hours`, apply `math.ceil`.

### Heat Stress Tracking

- `_load_daily_temperatures(registry, root_dir, *, condition='openfield')` —
  Load the daily weather CSV matching the specified condition. Extract the
  daily max temperature column. Return a Series indexed by date.

- `_compute_heat_flags(temp_c, policy)` — Given the day's max temperature
  and heat stress policy config, return a dict with `heat_stress_flag` (0/1)
  and `extreme_heat_flag` (0/1). Does not modify labor hours — tracking only.

### Column Ordering

- `_order_labor_columns(df)` — Groups columns in the order listed in the Daily
  Output Columns section: day, activity hours, worker category hours, workforce
  counts, cost, per-field detail, metrics, policy.

---

## Public API

### `compute_daily_labor_demand()`

Top-level orchestrator. Signature:

```python
def compute_daily_labor_demand(
    farm_profiles_path,
    registry_path,
    *,
    labor_policy_path=None,
    energy_system_path=None,
    water_systems_path=None,
    water_system_name='main_irrigation',
    sim_year=2023,
    root_dir=None,
):
```

**Orchestration steps:**

1. Load farm profile config, data registry, labor policy (or defaults).
2. Load labor requirements and wages from registry.
3. Load crop coefficient stage durations → `stage_lookup` dict.
4. Load planting windows → `season_lookup` dict (reuses `_load_season_lengths`
   from `src/farm_profile.py`).
5. Build field schedules for the simulation year — one DataFrame per field with
   daily growth stages.
6. For each field, compute daily labor hours by activity using
   `_compute_field_daily_labor`.
7. Compute fixed daily labor (management, logistics).
8. Compute maintenance daily labor (equipment — requires energy system and
   water systems configs if provided; omit equipment categories when config
   paths are None).
9. Load daily temperatures and compute heat stress flags (tracking only —
   does not reduce labor hours).
10. Assemble all labor sources into a single DataFrame indexed by day.
11. Aggregate by worker category, compute costs, compute workforce counts.
12. Order columns via `_order_labor_columns`.
13. Return the DataFrame.

**Returns:** DataFrame with one row per day of the simulation year.

### `save_labor_demand()`

```python
def save_labor_demand(df, output_dir, *, filename='daily_labor_demand.csv', decimals=2):
```

Identical pattern to `save_energy` in `src/energy_supply.py`.

### `load_labor_demand()`

```python
def load_labor_demand(path):
```

Identical pattern to `load_energy`.

---

## Labor Smoothing Helper Functions

These functions are **analysis tools**, not part of the simulation loop. They
test how changes to the farm profile affect daily labor demand curves.

### Design Principle

The labor module is an observer — it does not modify farm profiles. The helper
functions work by:

1. Creating modified copies of the farm profile configuration (in-memory dicts)
2. Calling `compute_daily_labor_demand()` with each modified config
3. Comparing the resulting labor demand curves
4. Reporting metrics that quantify smoothness and peak reduction

### `compute_labor_profile()`

Convenience wrapper that takes a farm profile dict (not file path) and returns
the daily labor demand DataFrame. Allows helper functions to pass modified
configs without writing temporary YAML files.

```python
def compute_labor_profile(
    farm_config,
    registry_path,
    *,
    labor_policy_path=None,
    energy_system_path=None,
    water_systems_path=None,
    water_system_name='main_irrigation',
    sim_year=2023,
    root_dir=None,
):
```

Identical to `compute_daily_labor_demand` except it accepts a parsed dict
instead of a file path for the farm profile.

### `summarize_labor_profile()`

Compute summary statistics from a daily labor DataFrame:

```python
def summarize_labor_profile(labor_df):
```

**Returns** a dict with:

| Key | Description |
|---|---|
| `total_hours` | Sum of `total_labor_hours` across year |
| `mean_daily_hours` | Mean of `total_field_hours` |
| `peak_daily_hours` | Max of `total_field_hours` |
| `peak_ratio` | `peak / mean` — lower is smoother |
| `cv` | Coefficient of variation of `total_field_hours` |
| `summer_hours` | Sum of `total_field_hours` for Jun–Aug |
| `summer_share` | `summer_hours / total_hours` |
| `heat_stress_days` | Count of days where `heat_stress_flag == 1` |
| `peak_harvester_count` | Max of `seasonal_harvester_count` |
| `peak_field_worker_count` | Max of `field_worker_count` |
| `seasonal_harvester_person_days` | Sum of `seasonal_harvester_hours / standard_day_hours` — sizes contracts and housing |

### `test_staggered_plantings()`

Test the effect of staggering planting dates across all fields growing a given
crop. This addresses the primary smoothing scenario: when multiple fields plant
the same crop on the same (or similar) dates, harvest labor concentrates into
sharp peaks. Staggering across fields spreads the peak.

```python
def test_staggered_plantings(
    farm_config,
    registry_path,
    *,
    crop,
    offsets_days=None,
    labor_policy_path=None,
    sim_year=2023,
    root_dir=None,
):
```

**Parameters:**
- `crop` — which crop to stagger across all fields that grow it
- `offsets_days` — list of day offsets to test (default: `[0, 3, 5, 7, 10, 14]`).
  The function finds all fields growing `crop`, then for each offset generates
  a modified config where successive fields are staggered by that increment.
  For example, with offset 7 and 3 fields growing tomato: field 1 keeps its
  original date, field 2 shifts +7 days, field 3 shifts +14 days. Skips
  offsets that push any field outside its valid planting window (±14 days of
  a registered window in `planting_windows-research.csv`) or cause overlap
  with other plantings in the same field.

**Returns:** DataFrame with one row per offset, columns from
`summarize_labor_profile()` plus the `offset_days` value. Sorted by
`peak_ratio` ascending (smoothest first).

**Mechanism:** For each offset value, creates a modified farm config dict where
each field's planting code for the specified crop is shifted by
`field_index × offset` days (e.g., `feb15` + 7 → `feb22`). Validates window
bounds and overlap per field. Calls `compute_labor_profile()` and
`summarize_labor_profile()`.

Because growth stage timing is computed arithmetically from planting date +
stage durations (not read from pre-computed CSVs), arbitrary day offsets are
feasible. The only constraints are window validity and overlap.

### `test_crop_mix()`

Test how replacing one crop with another affects labor demand.

```python
def test_crop_mix(
    farm_config,
    registry_path,
    *,
    field_name,
    original_crop,
    replacement_crops=None,
    labor_policy_path=None,
    sim_year=2023,
    root_dir=None,
):
```

**Parameters:**
- `field_name` — which field to modify
- `original_crop` — which crop to replace
- `replacement_crops` — list of crop names to try (default: all 5 crops).
  For each replacement, the function finds valid planting dates from
  `planting_windows-research.csv` that fit in the field's available calendar
  window (no overlap with other plantings in the same field).

**Returns:** DataFrame with one row per (replacement_crop, planting_date)
combination, columns from `summarize_labor_profile()`. Sorted by `peak_ratio`.

### `compare_farm_profiles()`

Compare two full farm profile configs side by side.

```python
def compare_farm_profiles(
    baseline_config,
    alternative_config,
    registry_path,
    *,
    labor_policy_path=None,
    sim_year=2023,
    root_dir=None,
):
```

**Returns:** dict with keys `baseline` and `alternative`, each containing the
output of `summarize_labor_profile()`, plus a `delta` dict showing the
difference (alternative − baseline) for each numeric metric.

---

## Data Requirements

### Already Exists — No Changes Needed

| File | Used For |
|---|---|
| `data/labor/labor_requirements-research.csv` | Activity hours per hectare, per day, per unit |
| `data/labor/labor_wages-research.csv` | Wage rates by worker category |
| `data/labor/worker_category_mapping-research.csv` | Worker category → skill level bridge |
| `data/crops/crop_params/crop_coefficients-research.csv` | Growth stage durations (arithmetic stage dating) |
| `data/crops/crop_params/planting_windows-research.csv` | Season lengths and valid planting date windows |
| `data/weather/daily_weather_openfield-research.csv` | Daily max temperature for heat stress |
| `settings/farm_profile_base.yaml` | Field definitions and crop schedules |
| `settings/energy_system_base.yaml` | Equipment counts for maintenance labor |
| `settings/water_systems_base.yaml` | Well/treatment counts for maintenance labor |
| `src/farm_profile.py` | `planting_code_to_mmdd()`, `normalize_plantings()` |

### New Files Required

| File | Action | Description |
|---|---|---|
| `src/labor.py` | **Create** | Daily labor demand computation module |
| `settings/labor_policy_base.yaml` | **Create** | Labor policy configuration |

### Existing Files Modified

| File | Change |
|---|---|
| `settings/data_registry_base.yaml` | Add `labor:` section with 3 entries |
| `scenarios/scenario_base.yaml` | Add `labor_policy:` key |

---

## Standalone Verification

### Entry Point

```python
if __name__ == '__main__':
    from pathlib import Path

    root = Path(__file__).parent.parent
    df = compute_daily_labor_demand(
        farm_profiles_path=root / 'settings' / 'farm_profile_base.yaml',
        registry_path=root / 'settings' / 'data_registry_base.yaml',
        labor_policy_path=root / 'settings' / 'labor_policy_base.yaml',
        energy_system_path=root / 'settings' / 'energy_system_base.yaml',
        water_systems_path=root / 'settings' / 'water_systems_base.yaml',
    )
    out = save_labor_demand(df, output_dir=root / 'simulation')
    print(f'Saved {len(df)} rows to {out}')
    print(f'Total labor hours: {df["total_labor_hours"].sum():.0f}')
    print(f'Peak daily field hours: {df["total_field_hours"].max():.1f}')
    print(f'Mean daily field hours: {df["total_field_hours"].mean():.1f}')
    print(f'Peak ratio: {df["total_field_hours"].max() / df["total_field_hours"].mean():.2f}')
    print(f'Heat stress days: {df["heat_stress_flag"].sum()}')
    print(f'Peak harvesters needed: {df["seasonal_harvester_count"].max():.0f}')
```

### Validation Checks

1. **Conservation:** For each field and each planting, the sum of daily hours
   for each activity across the growing season should equal
   `hours_per_unit × field_area_ha` (within rounding tolerance). This confirms
   that spreading distributes the full labor budget.

2. **Fallow zeros:** On fallow days, field operation hours for that field
   should be 0 (management and maintenance continue).

3. **Stage alignment:** The `{field}_growth_stage` column should match the
   growth stage from `crop_coefficients-research.csv` stage durations, starting
   from the planting date.

4. **Heat stress flags:** On days where max temperature exceeds
   `threshold_temp_c`, `heat_stress_flag` should be 1. On days exceeding
   `extreme_temp_c`, `extreme_heat_flag` should be 1. Labor hours are not
   reduced — flags are tracking-only.

5. **Worker category totals:** The sum of all `{category}_hours` columns should
   equal `total_labor_hours` for every row.

6. **Cost identity:** `total_labor_cost` should equal the sum of
   `(hours × wage_rate)` across all worker categories.

7. **Existing tests pass:** `python -m pytest tests/` should show no regressions.

---

## Assumptions

- Labor hours from `labor_requirements-research.csv` are **seasonal totals per
  hectare** for field operations. The module must distribute these across the
  appropriate growth stage days. They are not daily rates (except for
  management/logistics entries marked `per_day`).
- All fields in the farm profile connected to the specified `water_system_name`
  are included. Fields on other water systems are excluded.
- The simulation year is a single calendar year (matching the scenario's
  `start_date` / `end_date` year). Plantings that straddle the year boundary
  are handled by computing their full season and clipping to the simulation
  window.
- Processing, storage, and distribution labor (`processing_labor-research.csv`,
  `storage_labor-research.csv`, `distribution_labor-research.csv`) are **out
  of scope** for this module. They depend on post-harvest yield volumes and
  processing decisions that are not yet modeled at the daily timestep. The
  field operations, management, maintenance, and basic logistics covered here
  represent the primary labor demand drivers.
- Weather data for heat stress uses the `openfield` condition weather file
  regardless of field condition, because outdoor temperature affects all
  workers equally.

---

## Deferred Features

The following are explicitly excluded from the initial implementation. They are
noted here for future reference but should **not** be implemented until
specifically requested.

- **Processing/storage/distribution labor** — requires post-harvest pipeline
  modeling (yield → processing → storage → sales). The data exists
  (`processing_labor-research.csv`, `storage_labor-research.csv`,
  `distribution_labor-research.csv`) but the daily yield volumes needed to
  drive it are not yet modeled. Add when `src/crop_yield.py` produces daily
  yield volumes.
- **Hourly labor scheduling** — the daily timestep is sufficient for workforce
  planning. Intra-day scheduling (morning vs. afternoon shifts) is a future
  refinement.
- **Labor supply constraints** — the module reports demand only. It does not
  model labor availability, hiring, or training. A future extension could add
  supply-side constraints and flag days where demand exceeds available
  workforce.
- **Overtime and wage premiums** — hours beyond `standard_day_hours` are
  reported but not costed at a premium rate. Add overtime multipliers when
  wage modeling is refined.
- **Learning curves** — labor efficiency does not change over the season or
  across years. Workers are assumed experienced from day one.
- **Multi-year crop rotation optimization** — the helper functions test
  single-year modifications. Multi-year rotation planning is a higher-level
  planning tool.
- **Ramadan productivity adjustment** — Ramadan shifts ~11 days/year across
  the Gregorian calendar and significantly affects labor capacity when it
  falls in summer (fasting during daylight in hot conditions). Could be
  modeled as a reduced-hours period with configurable dates. Relevant for
  Egyptian community farm context but not critical for initial implementation.
- **Post-harvest field cleanup** — residue removal between sequential plantings
  (estimated ~15 hrs/ha over 3–5 days). Small magnitude relative to harvest
  labor. Add when fallow-period labor becomes important for planning.
- **Water supply interaction** — the labor module reports irrigation management
  labor even on days when no water is actually delivered (deficit days). This
  is a known simplification. The module reports demand, not actual activity.
- **Harvest spreading into mid-stage** — for continuous-harvest crops (cucumber,
  tomato, kale), real-world picking begins during mid-stage. The current model
  assigns all harvest labor to the late stage, which concentrates hours into
  fewer days but correctly reflects the peak workforce needed. If peak
  harvester counts prove unrealistic, a per-crop `harvest_start_stage`
  parameter could spread harvest across mid + late.
- **Equipment maintenance seasonality** — annualized daily averages obscure
  real maintenance patterns (PV cleaning heavier during khamsin dust season,
  BWRO membrane cleaning every 2–4 weeks). Uniform spreading is a reasonable
  first pass.
