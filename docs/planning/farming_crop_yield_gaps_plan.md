# Farming and Crop Yield Gaps: Resolution Plan

Date: 2026-03-03

Source: `specs/farming_crop_yield_specification.md` -- Gaps and Issues section (10 items)

Scope: Farming, crop growth, and yield logic only. Water supply dispatch, energy balance,
and community demand modules are out of scope.

---

## Priority Summary

| Gap | Title                                          | Priority    | Complexity |
|-----|------------------------------------------------|-------------|------------|
| 1   | Harvest yield logic not in a source module     | P1 Fix Now  | Medium     |
| 8   | No tests for farming subsystem                 | P1 Fix Now  | Medium     |
| 9   | Planting windows file not in data registry     | P1 Fix Now  | Low        |
| 10  | Weather year range determines simulation scope | P1 Fix Now  | Medium     |
| 7   | Column name inconsistency in yield factors CSV | P2 Fix Soon | Low        |
| 5   | No explicit salt stress in yield computation   | P2 Fix Soon | Medium     |
| 6   | Cross-year planting season handling            | P2 Fix Soon | Low        |
| 2   | Proportional per-field delivery allocation     | P3 Future   | High       |
| 3   | Biomass tracking is decorative in yield model  | Defer       | N/A        |
| 4   | Temperature stress coefficient source mismatch | Defer       | N/A        |

---

## Priority 1 -- Fix Now

These gaps affect simulation correctness, violate project conventions, or block testability.

### Gap 1: Harvest Yield Logic Not in a Source Module

Status: Real problem. The harvest yield assembly loop (iterating over farms, fields, plantings,
years; extracting delivery/demand series from the water balance DataFrame; calling
`compute_harvest_yield()`; building the daily harvest CSV) lives entirely in
`notebooks/simulation.ipynb` (cell `pz8fbnsfyd` and cell `yrpe8zqgz8`). Every other subsystem
has a `compute_*()` / `save_*()` / `load_*()` triplet in `src/`.

Impact:
- Cannot test harvest assembly with pytest.
- Any new notebook or script that needs harvest data must duplicate 60+ lines of loop logic.
- Violates the project convention where `src/` modules own all computation and `notebooks/`
  are thin consumers.

Proposed Resolution:

Add three public functions to `src/crop_yield.py`:

```python
def compute_community_harvest(
    water_balance_df,
    *,
    farm_profiles_path,
    registry_path,
    root_dir=None,
):
    """Compute harvest yields for all fields, crops, plantings, and years.

    Iterates over every (farm, field, crop, planting_code, year) combination
    in the farm profile. For each, extracts the delivered and demand series
    from the water balance DataFrame and calls compute_harvest_yield().

    Args:
        water_balance_df: DataFrame from compute_daily_water_balance() with
            per-field delivered_m3 and demand_m3 columns plus a 'day' column.
        farm_profiles_path: Path to farm_profile YAML.
        registry_path: Path to data_registry YAML.
        root_dir: Repository root. Defaults to parent of settings/.

    Returns:
        Tuple of (daily_df, harvests_df) where:
            daily_df: DataFrame with 'day' column plus per-field-crop harvest_kg
                columns and total_harvest_kg. One row per calendar day; non-harvest
                days are zero.
            harvests_df: DataFrame with one row per harvest event containing
                harvest_date, field, crop, planting, condition, yield_kg_per_ha,
                area_ha, harvest_kg.
    """
```

```python
def save_harvest_yields(daily_df, output_dir, *, filename='daily_harvest_yields.csv', decimals=1):
    """Save daily harvest yields DataFrame to CSV.

    Args:
        daily_df: DataFrame from compute_community_harvest (first element).
        output_dir: Directory to write. Created if needed.
        filename: Output file name.
        decimals: Decimal places for numeric columns.

    Returns:
        Path to the saved CSV file.
    """
```

```python
def load_harvest_yields(path):
    """Load a saved harvest yields CSV.

    Args:
        path: Path to the daily_harvest_yields CSV file.

    Returns:
        DataFrame with 'day' as DatetimeIndex.
    """
```

Internal helpers to add in `src/crop_yield.py`:

- `_build_daily_harvest_df(harvests, sim_start, sim_end)` -- pivots harvest records into the
  daily DataFrame with per-field-crop columns and total_harvest_kg.
- Reuse `_load_season_lengths()` from `src/farm_profile.py` (already exists as a module-level
  function; import it directly).

Changes to `notebooks/simulation.ipynb`:
- Replace the harvest loop cells (`pz8fbnsfyd`, `yrpe8zqgz8`) with a call to
  `compute_community_harvest()` followed by `save_harvest_yields()`.
- Print summary from the returned `harvests_df`.

Dependencies: None. This is a pure extraction refactor.

Complexity: Medium (2-3 hours). The logic already exists in the notebook; this is extracting,
parameterizing, and testing it.

---

### Gap 8: No Tests for Farming Subsystem

Status: Real problem. The only test file is `tests/test_farm_profile.py` which covers
`planting_code_to_mmdd()`, `normalize_plantings()`, and `validate_no_overlap()`. There are
no tests for `src/crop_yield.py` or `src/irrigation_demand.py`.

Impact:
- Yield formula correctness is unverified beyond the `__main__` block.
- Irrigation demand scaling (the `etc_mm * area_ha * 10 / efficiency` formula) is untested.
- Refactoring any of these modules (including Gap 1) is risky without regression tests.

Proposed Resolution:

Create two new test files:

**`tests/test_crop_yield.py`**:

```python
# Tests for crop yield computation.

def test_compute_harvest_yield_full_delivery():
    """When delivered == demand, f=1.0, yield should equal potential * avg_Kt."""

def test_compute_harvest_yield_zero_delivery():
    """When delivered == 0, f=0.0, yield should be 0."""

def test_compute_harvest_yield_partial_delivery():
    """50% delivery should produce yield between 0 and full via concave response."""

def test_compute_harvest_yield_over_delivery_capped():
    """Delivery > demand should clamp f to 1.0, not produce super-optimal yield."""

def test_alpha_computation():
    """Verify alpha = max(1.0, 1 + wue_curvature * (1.15 - ky)) for each crop."""

def test_compute_community_harvest_returns_expected_columns():
    """Verify daily_df has day + field_crop_harvest_kg + total_harvest_kg."""

def test_compute_community_harvest_event_count():
    """Verify the number of harvest events matches expected from farm profile."""
```

**`tests/test_irrigation_demand.py`**:

```python
# Tests for irrigation demand computation.

def test_compute_irrigation_demand_returns_expected_columns():
    """Output should have day, per-field etc/demand/crop cols, total, tds."""

def test_demand_scaling_formula():
    """Verify demand_m3 = etc_mm * area_ha * 10 / efficiency for a known field."""

def test_fallow_days_are_zero():
    """Days with no active crop should have 0 demand and 'none' crop label."""

def test_total_demand_equals_sum_of_fields():
    """total_demand_m3 should equal sum of all field _demand_m3 columns."""

def test_tds_requirement_is_min_across_active_crops():
    """On days with multiple active crops, TDS should be the minimum threshold."""

def test_get_field_irrigation_specs_returns_all_fields():
    """Should return one entry per field linked to the water system."""
```

Run with: `python -m pytest tests/ -v`

Dependencies: Gap 1 should be completed first so that `test_crop_yield.py` can test
`compute_community_harvest()`. Tests for `compute_harvest_yield()` (singular) can be
written immediately.

Complexity: Medium (2-3 hours). Tests use the existing baseline YAML and data files for
integration-style tests, plus synthetic data for unit tests of the formulas.

---

### Gap 9: Planting Windows File Not in Data Registry

Status: Real problem. `planting_windows-research.csv` is resolved by `_load_season_lengths()`
in `src/farm_profile.py` via path inference: it takes the parent directory of the
`growth_params` CSV path and appends `planting_windows-research.csv`. This breaks the
registry convention used by every other data file.

Impact:
- If `growth_params` is moved to a different directory in the registry, the planting windows
  lookup silently breaks.
- The file is invisible in the registry, making it harder to audit which data files the
  simulation depends on.
- Minor but creates a maintenance trap.

Proposed Resolution:

1. Add to `settings/data_registry_base.yaml` under the `crops:` section:

```yaml
crops:
  growth_params:           data/crops/crop_params/crop_growth_params-research.csv
  yield_response_factors:  data/crops/crop_params/yield_response_factors-research.csv
  planting_windows:        data/crops/crop_params/planting_windows-research.csv
  daily_growth_dir:        data/crops/crop_daily_growth
```

2. Update `_load_season_lengths()` in `src/farm_profile.py` to accept and use the registry
   path directly:

```python
def _load_season_lengths(registry, root_dir):
    """Load (crop, mmdd) -> expected_season_length_days from planting_windows."""
    windows_path = root_dir / registry['crops']['planting_windows']
    df = pd.read_csv(windows_path, comment='#')
    lookup = {}
    for _, row in df.iterrows():
        lookup[(row['crop'], row['planting_date_mmdd'])] = int(row['expected_season_length_days'])
    return lookup
```

3. Update any callers that import `_load_season_lengths` directly (the notebook cell
   `pz8fbnsfyd` imports it). After Gap 1 is resolved, the notebook will no longer call
   this function directly.

Dependencies: Should be done before or alongside Gap 1, since the refactored
`compute_community_harvest()` will need to call `_load_season_lengths()`.

Complexity: Low (< 30 minutes). One line in the YAML, one line change in Python, verify
with existing tests.

---

### Gap 10: Weather Year Range Determines Simulation Scope

Status: Real problem. The `scenario_base.yaml` file defines `simulation.start_date` and
`simulation.end_date` (currently 2023-01-01 to 2023-12-31), but these values are never
consumed by any module. The irrigation demand module generates a date axis spanning all
weather years found in the crop daily growth CSVs (2010-01-01 to 2024-12-31). The notebook
then computes 118 harvest events across 15 years.

This means:
- The scenario file's simulation period is misleading -- it suggests a 1-year run but the
  actual simulation covers 15 years.
- There is no way to run a quick single-year simulation for testing or scenario comparison
  without modifying the data files.
- The 15-year run takes significant compute time (118 calls to `compute_harvest_yield()`,
  each loading a CSV from disk).

Impact: Correctness is not affected (the 15-year run produces valid results), but usability
and scenario composability are impaired. A user who sets `start_date: "2020-01-01"` and
`end_date: "2022-12-31"` expects a 3-year simulation.

Proposed Resolution:

1. Add `start_date` and `end_date` keyword arguments to `compute_irrigation_demand()`:

```python
def compute_irrigation_demand(farm_profiles_path, registry_path, *,
                              water_system_name='main_irrigation',
                              irrigation_policy='full_eto',
                              water_policy_path=None,
                              start_date=None,
                              end_date=None,
                              root_dir=None):
```

When `start_date` / `end_date` are provided, the date axis is clipped to that range instead
of spanning all years in the data. When `None`, the current behavior is preserved (full
data range).

2. Thread `start_date` / `end_date` through `compute_daily_water_balance()`:

```python
def compute_daily_water_balance(farm_profiles_path, water_systems_path,
                                water_policy_path, community_config_path,
                                registry_path, *,
                                water_system_name='main_irrigation',
                                start_date=None,
                                end_date=None,
                                root_dir=None):
```

Pass these to `compute_irrigation_demand()` and also clip the community demand DataFrame
to the same range.

3. In `notebooks/simulation.ipynb`, read `start_date` / `end_date` from the scenario YAML
and pass them to `compute_daily_water_balance()`:

```python
start_date = scenario['simulation'].get('start_date')
end_date = scenario['simulation'].get('end_date')
```

When the scenario has `null` for these values, the full data range is used (backward
compatible).

4. Similarly, `compute_community_harvest()` (from Gap 1) should accept and respect
`start_date` / `end_date` to skip plantings outside the simulation window.

Dependencies: Should be coordinated with Gap 1. The `compute_community_harvest()` function
needs to respect the simulation date range.

Complexity: Medium (2-3 hours). The date clipping logic is straightforward, but it must be
threaded through multiple function signatures and tested for edge cases (plantings that
start before the window but harvest within it; plantings that start within but harvest after).

---

## Priority 2 -- Fix Soon

These gaps affect maintainability, data consistency, or represent missing features that should
be addressed after the P1 items.

### Gap 7: Column Name Inconsistency in Yield Response Factors CSV

Status: Real problem, minor. The `yield_response_factors-research.csv` file uses `crop_name`
as its crop identifier column. Every other crop data file uses `crop`. This forces
`_load_yield_params()` in `src/crop_yield.py` to filter with `yrf_df['crop_name'] == crop`
instead of the standard `yrf_df['crop'] == crop`.

Impact: Low. The code works, but the inconsistency is a maintenance trap. If someone
standardizes column names across CSVs without updating `crop_yield.py`, it breaks.

Proposed Resolution:

1. Rename the column in `data/crops/crop_params/yield_response_factors-research.csv`
from `crop_name` to `crop`. Update the CSV header comment accordingly.

2. Update `_load_yield_params()` in `src/crop_yield.py` line 60:

```python
# Before:
yrf_row = yrf_df[yrf_df['crop_name'] == crop].iloc[0]

# After:
yrf_row = yrf_df[yrf_df['crop'] == crop].iloc[0]
```

3. Check if `crop_name` is referenced anywhere else in the codebase. The
`microclimate_yield_effects-research.csv` also uses `crop_name` -- that file is documented
as not used by the simulation engine, so it can be left as-is or updated for consistency.

Dependencies: None.

Complexity: Low (< 30 minutes). One CSV column rename, one Python line change, run tests.

---

### Gap 5: No Explicit Salt Stress in Yield Computation

Status: Real gap. The crop growth parameters file has detailed TDS tolerance data
(`tds_no_penalty_ppm`, `tds_lethal_ppm`, `tds_yield_decline_pct_per_100ppm`), and the
irrigation demand module computes `crop_tds_requirement_ppm` per day. The water balance
tracks `delivered_tds_ppm`. But `compute_harvest_yield()` does not apply any TDS-based
yield penalty. Currently, TDS only influences the water supply dispatch system (blending
to meet crop thresholds), not the yield outcome.

Impact: When the water supply system delivers water with TDS above the crop threshold
(which can happen under deficit conditions or when the dispatch strategy does not achieve
the blending target), the yield model does not capture the resulting salt stress. This
under-penalizes poor water quality scenarios.

Proposed Resolution:

Add an optional `delivered_tds_series` parameter to `compute_harvest_yield()`:

```python
def compute_harvest_yield(crop, planting, condition, weather_year,
                          delivered_m3_series, demand_m3_series,
                          *, registry_path, root_dir=None,
                          delivered_tds_series=None):
```

When `delivered_tds_series` is provided (a pd.Series of daily TDS values indexed by date):

1. Load the crop's salt tolerance parameters from `crop_growth_params-research.csv`:
   `tds_no_penalty_ppm`, `tds_lethal_ppm`, `tds_yield_decline_pct_per_100ppm`.

2. Compute a daily salt stress coefficient `Ks_salt`:
   - When TDS <= `tds_no_penalty_ppm`: `Ks_salt = 1.0`
   - When TDS >= `tds_lethal_ppm`: `Ks_salt = 0.0`
   - Otherwise: `Ks_salt = 1.0 - (TDS - tds_no_penalty_ppm) / 100 * tds_yield_decline_pct_per_100ppm / 100`
   - Clamp to [0, 1].

3. Compute season-average `avg_Ks_salt = mean(Ks_salt)` over the growing season.

4. Multiply into the yield formula:
   `yield_kg_ha = potential_yield * f^(1/alpha) * avg_Kt * avg_Ks_salt`

When `delivered_tds_series` is `None`, the behavior is unchanged (no salt penalty, backward
compatible).

The `compute_community_harvest()` function (from Gap 1) should extract the
`delivered_tds_ppm` column from the water balance DataFrame and pass it along.

Dependencies: Gap 1 (so the orchestrator can thread TDS through). Can be implemented
independently in `compute_harvest_yield()` first.

Complexity: Medium (1-2 hours). The salt stress formula is documented in the CSV header
comments. Implementation is straightforward linear interpolation. Requires adding
salt tolerance parameters to `_load_yield_params()`.

---

### Gap 6: Cross-Year Planting Season Handling in Overlap Validator

Status: Minor edge case, not currently triggered. The overlap validator uses a fixed
reference year (2020) to check season intervals. A planting that crosses the year boundary
(e.g., November planting harvesting in March) is handled correctly via `timedelta` arithmetic
-- the end date simply falls in 2021.

However, the validator checks all plantings against a single reference year. This means it
can miss overlaps between a late-year planting (e.g., `nov01` tomato ending ~March 16) and
an early-year planting (e.g., `feb15` tomato starting Feb 15) because they are both computed
relative to 2020, and the first ends at 2021-03-16 while the second starts at 2020-02-15.
These do not overlap in the reference year, but in a multi-year simulation where both
plantings occur annually, they would overlap in the transition from one year to the next.

In the current baseline farm profile, no field has both a late-year and early-year planting
of the same crop, so this edge case does not arise. But a user who adds `nov01` and `feb15`
tomato plantings to the same field would not get an overlap warning.

Impact: Low for the current configuration. Could produce silent schedule conflicts in future
farm profiles.

Proposed Resolution:

Modify `validate_no_overlap()` to check plantings across two consecutive reference years.
For each planting, compute intervals for both `ref_year` and `ref_year + 1`, then check all
cross-year pairs in addition to same-year pairs:

```python
def validate_no_overlap(farm_config, registry, root_dir):
    season_lookup = _load_season_lengths(registry, root_dir)
    ref_year = 2020

    def date_ranges(crop, planting_code):
        """Return intervals for two consecutive years to catch cross-year overlap."""
        mmdd = planting_code_to_mmdd(planting_code)
        key = (crop, mmdd)
        length = season_lookup[key]
        intervals = []
        for y in [ref_year, ref_year + 1]:
            start = datetime.strptime(f"{y}-{mmdd}", "%Y-%m-%d")
            end = start + timedelta(days=length)
            intervals.append((start, end))
        return intervals

    # For each field, collect all intervals (2 per planting) and check all pairs.
```

This catches the case where year-N's late planting overlaps with year-(N+1)'s early planting
on the same field.

Dependencies: None.

Complexity: Low (< 1 hour). Small modification to the existing validator, plus a test case
in `tests/test_farm_profile.py` for the cross-year scenario.

---

## Priority 3 -- Future Enhancement

### Gap 2: Proportional Per-Field Delivery Allocation

Status: Known simplification, acceptable for now. In `src/water_balance.py` (lines 218-226),
when the water supply system delivers less than the total irrigation demand, every field
receives the same proportional reduction:

```python
delivery_ratio = irrigation_delivered / irrigation_demand
field_delivered = field_demand * delivery_ratio
```

In reality, a dispatch optimizer could prioritize water to crops with higher Ky values
(more sensitive to deficit) or to crops closer to harvest (where deficit has maximum yield
impact). The uniform proportional allocation is a first-order approximation.

Impact: Under deficit conditions (currently 0 deficit days in the baseline), this simplification
has no effect. It would matter only in scenarios with constrained water supply. Even then, the
error is bounded by the spread in Ky values across active crops (range 0.95 to 1.10 in
current data -- a narrow band).

Proposed Resolution (Future):

1. Add an `allocation_strategy` parameter to `compute_daily_water_balance()`:
   - `proportional` (default, current behavior)
   - `priority_by_ky` (allocate to highest-Ky crops first)
   - `priority_by_stage` (allocate to crops in mid-season / flowering stage first)

2. Implement priority allocation as a separate internal function that receives the list of
   field demands, their crop metadata, and the total available delivery, then returns
   per-field allocations.

3. This requires crop metadata (Ky, current growth stage) to be available in the water
   balance module, which would need to be passed through from the irrigation demand or farm
   profile modules.

Dependencies: Would benefit from having crop growth stage information in the water balance
DataFrame, which is not currently tracked.

Complexity: High (4+ hours). Requires architectural changes to pass crop metadata through
the water balance pipeline, plus a new allocation algorithm, plus tests covering deficit
scenarios.

---

## Defer / Needs Discussion

### Gap 3: Biomass Tracking is Decorative in the Yield Model

Status: Acceptable as-is. The specification explicitly documents this as intentional:
"Yield is decoupled from cumulative biomass to avoid the dm_frac amplification problem
(crops with >95% water content produce unrealistic fresh yields from any reasonable dry
biomass)."

The crop daily growth CSVs contain `biomass_kg_ha` and `cumulative_biomass_kg_ha` columns
from the RUE model, but the yield calculation uses the FAO Paper 33 water-yield response
function exclusively. The biomass columns serve as diagnostic and educational tracking.

Impact: None on correctness. The biomass columns are useful for visualizing daily crop
growth dynamics in notebooks, even though they do not feed into the yield formula.

Proposed Resolution: No code changes needed. The specification already documents this
clearly. Optionally, add a comment in `compute_harvest_yield()` noting that the biomass
columns are intentionally not used:

```python
# NOTE: Yield uses FAO Paper 33 water-response formula, not cumulative biomass.
# The biomass columns in crop daily growth CSVs are diagnostic only.
```

Dependencies: None.

Complexity: N/A.

---

### Gap 4: Temperature Stress Coefficient Source Mismatch

Status: Not a bug. The specification correctly identifies that `compute_harvest_yield()`
loads `temp_stress_coeff` filtered to `irrigation_policy='full_eto'`. Since `temp_stress_coeff`
(Kt) depends only on daily temperature and cardinal temperature thresholds -- not on water
application -- it is identical across all irrigation policies for the same weather year. The
`full_eto` filter is arbitrary but correct.

Impact: None on correctness. Potential confusion for future maintainers.

Proposed Resolution: Add a clarifying comment in `_load_season_kt()` in `src/crop_yield.py`:

```python
def _load_season_kt(growth_dir, crop, planting, condition, weather_year):
    """Load daily temp_stress_coeff from crop growth CSV for one season.

    Filters to irrigation_policy='full_eto' and the given weather_year.
    The choice of 'full_eto' is arbitrary -- temp_stress_coeff depends only
    on daily temperature, not water application, so it is identical across
    all irrigation policies for the same weather_year.
    ...
    """
```

Dependencies: None.

Complexity: N/A.

---

## Implementation Order

The recommended implementation sequence, accounting for dependencies:

1. **Gap 9** (registry entry for planting windows) -- 30 min. Quick fix that unblocks
   cleaner path resolution in the Gap 1 refactor.

2. **Gap 7** (column name fix in yield response factors CSV) -- 30 min. Quick fix that
   simplifies Gap 1 and Gap 8 code.

3. **Gap 1** (extract harvest logic to `src/crop_yield.py`) -- 2-3 hours. Core refactor.
   Produces `compute_community_harvest()`, `save_harvest_yields()`, `load_harvest_yields()`.

4. **Gap 10** (simulation date range from scenario) -- 2-3 hours. Thread `start_date`/`end_date`
   through `compute_irrigation_demand()` and `compute_daily_water_balance()`.

5. **Gap 8** (tests for farming subsystem) -- 2-3 hours. Write `tests/test_crop_yield.py` and
   `tests/test_irrigation_demand.py`. Should be written after Gaps 1 and 10 so the tests
   cover the new functions.

6. **Gap 6** (cross-year overlap validation) -- 1 hour. Small validator enhancement plus test.

7. **Gap 5** (salt stress in yield) -- 1-2 hours. Add optional TDS penalty to yield formula.

8. **Gaps 3 and 4** (documentation comments) -- 15 min. Add clarifying comments.

9. **Gap 2** (priority-based allocation) -- defer to a future sprint. Requires architectural
   discussion about what crop metadata should flow through the water balance pipeline.

Total estimated effort for P1 + P2 items: 10-13 hours.

---

## Files Modified Summary

| File                                          | Gaps Addressed |
|-----------------------------------------------|----------------|
| `src/crop_yield.py`                           | 1, 4, 5        |
| `src/farm_profile.py`                         | 6, 9           |
| `src/irrigation_demand.py`                    | 10             |
| `src/water_balance.py`                        | 10             |
| `settings/data_registry_base.yaml`            | 9              |
| `data/crops/crop_params/yield_response_factors-research.csv` | 7  |
| `notebooks/simulation.ipynb`                  | 1, 10          |
| `tests/test_crop_yield.py` (new)              | 8              |
| `tests/test_irrigation_demand.py` (new)       | 8              |
| `tests/test_farm_profile.py` (existing)       | 6              |
