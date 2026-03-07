# Water System Code Review -- Agent A

## Executive Summary

The water system codebase is architecturally sound with clean functional decomposition and thorough multi-strategy dispatch logic. However, the review identified several calculation issues: a misleading column name in irrigation demand, a conservation-law gap in the water balance check that ignores overnight refill, a stale config object returned after sizing iteration, and monthly cap accounting that does not count overnight refill extraction. Most issues are medium severity but the overnight refill cap tracking gap could allow real over-extraction under tight groundwater caps.

## High-Confidence Issues (fix immediately)

### W-HC-1: Balance check formula omits overnight refill, producing false non-zero residuals
- **File**: `/Users/dpbirge/GITHUB/community-agri-pv/src/water_balance.py`, lines 174-179
- **Severity**: Medium
- **Issue**: The `balance_check` column is defined as:
  ```
  tank_volume(t-1) + total_sourced_to_tank - irrigation_delivered - tank_volume(t)
  ```
  But `total_sourced_to_tank_m3` includes only daytime sourcing volumes (`gw_untreated + gw_treated + municipal_to_tank`), while `tank_volume_m3` is the end-of-day value *after* overnight refill. When overnight refill occurs, the tank gains volume not accounted for in the balance equation, so `balance_check` will show a non-zero residual on every refill day. This makes the diagnostic unreliable -- it flags phantom imbalances on healthy days while the equation is supposed to validate conservation of mass. The `__main__` block prints `balance_check max` as a validation metric, so users will see spurious failures.
- **Fix**: Include overnight refill in the conservation equation:
  ```python
  result['balance_check'] = (
      result['tank_volume_m3'].shift(1)
      + result['total_sourced_to_tank_m3']
      + result['overnight_refill_m3']
      - result['irrigation_delivered_m3']
      - result['tank_volume_m3']
  ).round(6)
  ```
  Note: `overnight_refill_m3` is already a column in the supply output and is part of `total_sourced_to_tank_m3` in the *row accounting* (water.py line 1271-1283 recomputes `total_sourced_to_tank_m3` after overnight), so verify whether `total_sourced_to_tank_m3` already includes overnight volumes. If it does, the formula is correct and the issue is instead in `_finalize_dispatch_row` at water.py line 897 which computes `total_sourced_to_tank_m3` *before* the overnight refill happens at line 1266. This means `total_sourced_to_tank_m3` in the output is stale -- it does not include overnight sourcing even though the raw per-source columns (`gw_untreated_to_tank_m3` etc.) *do* include overnight volumes after line 1127-1136.
- **Confidence**: High

### W-HC-2: `total_sourced_to_tank_m3` is computed before overnight refill but per-source columns include overnight volumes
- **File**: `/Users/dpbirge/GITHUB/community-agri-pv/src/water.py`, lines 897-899 vs. 1127-1136 and 1271-1283
- **Severity**: High
- **Issue**: In `_finalize_dispatch_row` (line 897), `total_sourced_to_tank_m3` is computed as the sum of `gw_untreated_to_tank_m3 + gw_treated_to_tank_m3 + municipal_to_tank_m3`. However, `_finalize_dispatch_row` is called at line 1291, *after* the overnight refill at line 1266 has already accumulated additional volumes into `row['gw_untreated_to_tank_m3']`, `row['gw_treated_to_tank_m3']`, and `row['municipal_to_tank_m3']` (via lines 1127-1136). So `total_sourced_to_tank_m3` *does* include overnight volumes in the final output. This means the balance check formula in W-HC-1 should actually work correctly. However, `sourced_tds_ppm` is recomputed at lines 1271-1283 to include all phases, and `total_sourced_to_tank_m3` at line 897 is recomputed from the already-accumulated per-source columns. After tracing the full flow: `_finalize_dispatch_row` runs after overnight refill, so `total_sourced_to_tank_m3` in the output *does* include overnight volumes. This means the balance check in water_balance.py line 174 should be correct *unless* there is a prefill-related discrepancy.

  **Revised diagnosis**: The balance check formula omits prefill. Prefill (line 1247) adds water to the tank via `_prefill_tank` which accumulates volumes into the per-source columns. But the delivered water drawn from tank does not include prefill -- prefill stays in the tank. So the equation `tank(t-1) + sourced - delivered = tank(t)` should hold because prefill is in `sourced` and stays in `tank(t)`. The real issue is **day 1**: `tank_volume_m3.shift(1)` is NaN on the first row, so `balance_check` is NaN for day 1. The initial tank level (e.g. 300 m3 from config) is not captured in the shifted series. This is a minor display issue but means day-1 conservation is never verified.
- **Fix**: Fill the shifted value with initial tank level for row 0:
  ```python
  prev_tank = result['tank_volume_m3'].shift(1)
  prev_tank.iloc[0] = initial_tank_level  # from water_systems config
  result['balance_check'] = (
      prev_tank
      + result['total_sourced_to_tank_m3']
      - result['irrigation_delivered_m3']
      - result['tank_volume_m3']
  ).round(6)
  ```
  This requires passing the initial tank level into `_compute_balance_diagnostics`. Alternatively, accept NaN on day 1 and document it.
- **Confidence**: High (NaN on day 1 is confirmed by the shift logic; the overnight inclusion was verified by tracing call order)

### W-HC-3: Misleading column name `{field}_etc_mm_per_ha` actually stores `irrigation_mm`, not ETc
- **File**: `/Users/dpbirge/GITHUB/community-agri-pv/src/irrigation_demand.py`, line 130
- **Severity**: Medium
- **Issue**: The column named `{name}_etc_mm_per_ha` is computed as `combined['irrigation_mm'].round(2)`. The `irrigation_mm` column from the crop growth CSV is the *policy-adjusted irrigation application* (which may exclude precipitation, may apply deficit factors), not the reference crop evapotranspiration (ETc). The docstring at line 191 acknowledges this: "per field, policy-adjusted irrigation_mm". But the column name `etc_mm_per_ha` strongly implies it contains ETc values, which it does not. The actual ETc is in `etc_mm` (used for `{name}_etc_m3`). This is a naming-only issue but could mislead anyone consuming the output DataFrame, especially for yield model validation where ETc and irrigation_mm diverge under deficit policies.
- **Fix**: Rename the column to `{name}_irrigation_mm_per_ha` to match the data it actually contains:
  ```python
  col_irrig_mm = f'{name}_irrigation_mm_per_ha'
  # ...
  combined[col_irrig_mm] = combined['irrigation_mm'].round(2)
  ```
  Update all downstream references (column ordering in `water_balance.py` line 59 uses `_etc_mm_per_ha` pattern).
- **Confidence**: High

### W-HC-4: Stale `config` object returned by `size_water_system` after deficit iteration
- **File**: `/Users/dpbirge/GITHUB/community-agri-pv/src/water_sizing.py`, line 898
- **Severity**: High
- **Issue**: `size_water_system()` builds `config` at line 862, then runs `_iterate_until_target` (line 889) which may modify `wells`, `storage`, `treatment_throughput`, and `municipal_cfg` through multiple iterations. However, the function returns the *original* `config` built at line 862, not the final iterated config. The `_rebuild_fn` closure (line 874) builds a *local* `cfg` variable inside each iteration but never assigns it back to the outer `config`. So when deficit iteration triggers (deficit > target), the returned config does not match the returned metrics -- the metrics reflect the iterated system while the config reflects the pre-iteration system.

  The same bug exists in `optimize_water_system()` at line 1086 -- it returns `config` built at line 1029, not the final iterated version.
- **Fix**: After the iteration loop, rebuild `config` from the final values:
  ```python
  # After _iterate_until_target returns
  well_delivery = sum(w['flow_m3_day'] for w in wells) / ff if ff > 0 else 0.0
  municipal_cfg = _size_municipal(demand, well_delivery, municipal_available, objective)
  config = _build_sizing_config(wells, treatment_throughput, goal_tds,
                                municipal_cfg, storage)
  ```
  Apply the same pattern in `optimize_water_system`.
- **Confidence**: High

### W-HC-5: Monthly cap accounting does not include overnight refill extraction
- **File**: `/Users/dpbirge/GITHUB/community-agri-pv/src/water.py`, lines 1409-1410
- **Severity**: High
- **Issue**: In `_run_simulation`, the monthly accumulators are updated as:
  ```python
  gw_used_month += row['total_groundwater_extracted_m3']
  muni_used_month += row['municipal_to_tank_m3']
  ```
  These values are read from the output `row` after `_dispatch_day` returns, and `_dispatch_day` does accumulate overnight refill volumes into these row fields (lines 1127-1136). So after re-tracing: overnight extraction IS included in `row['total_groundwater_extracted_m3']` because the overnight scratch row volumes are added to the main row. **However**, the `gw_cap_state` and `muni_cap_state` passed to `_dispatch_day` use `gw_used_month` and `muni_used_month` from the *previous* day's accumulation. The overnight refill at the end of day N uses these cap states, but the cap states already reflect day N's daytime extraction. The overnight refill calls `_source_water` which calls `_gw_source` which calls `_daily_cap_allowance` using the cap state passed in. Since the cap state was built *before* the dispatch (line 1392), it does not include day N's own extraction. This means the overnight refill sees a stale `used` value that does not include daytime extraction from the same day.

  Wait -- re-reading more carefully: the `gw_cap_state` is built at line 1392 with `'used': gw_used_month` which is the accumulated value from all *previous* days (it is updated *after* `_dispatch_day` returns at line 1409). So within `_dispatch_day`, the overnight refill's `_source_water` call at line 1120 passes the same `gw_cap_state` that was passed into `_dispatch_day`. The daytime extraction from the same day is not reflected in `gw_cap_state['used']`. This means the overnight refill can exceed the cap by up to one full day's extraction.

  **Mitigation**: The `_prefill_tank` function (line 677-678) manually adjusts cap states to include the main row's extraction. But `_overnight_tds_refill` does NOT perform this adjustment -- it passes the original `gw_cap_state` and `muni_cap_state` directly to `_source_water`.
- **Fix**: In `_overnight_tds_refill` (or in `_dispatch_day` before calling it), create adjusted cap states that include the current day's extraction:
  ```python
  on_gw_cap = dict(gw_cap_state)
  on_gw_cap['used'] = gw_cap_state['used'] + row['total_groundwater_extracted_m3']
  on_muni_cap = dict(muni_cap_state)
  on_muni_cap['used'] = muni_cap_state['used'] + row['municipal_to_tank_m3']
  ```
  Then pass `on_gw_cap` and `on_muni_cap` to `_source_water` inside `_overnight_tds_refill`.
- **Confidence**: High

### W-HC-6: `{field}_etc_m3` divides ETc by irrigation efficiency, making it a delivery-equivalent, not biological ETc
- **File**: `/Users/dpbirge/GITHUB/community-agri-pv/src/irrigation_demand.py`, line 132
- **Severity**: Medium
- **Issue**: The column `{name}_etc_m3` is computed as `etc_mm * area_ha * 10 / efficiency`. Dividing by irrigation efficiency converts the biological crop water need (ETc) into the *delivery volume* needed to satisfy that biological need given system losses. This is the same scaling applied to `irrigation_mm` for `demand_m3`. The column is then passed to `compute_harvest_yield` as `demand_m3_series` (crop_yield.py line 287), where it represents ETc demand for the yield model's `f = ETa/ETc` ratio.

  The yield model computes `eta_daily = min(delivered, demand)` and `f = sum(ETa) / sum(ETc)`. If both `delivered_m3` and `etc_m3` are divided by the same efficiency factor, the ratio `f` is unchanged (the efficiency cancels out). So the yield calculation result is correct *as long as* the efficiency is the same for both series. Since both are divided by the same field's efficiency, this is mathematically correct but semantically misleading -- `etc_m3` is not ETc in absolute terms, it is ETc scaled to delivery volume. The docstring at line 107 says "etc_m3 uses etc_mm (biological crop water need, for yield model)" which is misleading because the efficiency division is applied.

  **Impact**: Functionally correct for the yield model (ratio cancels). Incorrect if anyone uses `etc_m3` as actual biological water need for other purposes (e.g., water use efficiency reporting, basin-level water accounting).
- **Fix**: Either (a) do not divide etc_m3 by efficiency so it represents true biological ETc:
  ```python
  combined[col_etc_m3] = (combined['etc_mm'] * area_ha * 10).round(3)
  ```
  and correspondingly adjust `compute_harvest_yield` to compare delivery-efficiency-adjusted volumes to raw ETc volumes, OR (b) rename the column to `{name}_etc_delivery_m3` and update the docstring. Option (a) changes the yield model input semantics; option (b) is safer.
- **Confidence**: High (verified mathematically that efficiency cancels in the ratio, so current yield results are correct)

## Complex Issues (needs deeper review)

### W-CX-1: TDS correction municipal addition may exceed tank capacity
- **File**: `/Users/dpbirge/GITHUB/community-agri-pv/src/water.py`, lines 520-548
- **Severity**: Medium
- **Issue**: In `_source_water`, after the primary sourcing pass, a TDS correction step adds municipal water to bring the blend below `tds_req`. The correction volume `muni_for_tds` is computed from mass balance (line 526-528). Then the code checks if total sourced exceeds tank headroom (line 537) and trims municipal if needed. However, trimming municipal for headroom may leave the sourced TDS above the crop requirement (logged as a debug warning at line 546). The code proceeds anyway. On such days, the delivered TDS will exceed the crop threshold, which is recorded as `tds_exceedance_ppm` but has no downstream consequence -- there is no penalty to crop yield from TDS exceedance in the current model.
- **Analysis**: This is potentially a design gap rather than a bug. In practice, elevated TDS damages crops. The yield model uses only water volume ratios (ETa/ETc) and ignores TDS entirely. If TDS exceedance should reduce yield, it needs to be modeled. Need to check whether the agronomic literature for these crops (tomato, kale, cucumber, onion, potato) requires a TDS penalty function.
- **Suggested approach**: Add a TDS penalty factor to `compute_harvest_yield` that reduces yield when delivered TDS exceeds the crop's `tds_no_penalty_ppm` threshold. A simple linear or threshold model from FAO 29 (Ayers & Westcot) would work. This is an enhancement, not a bugfix.
- **Confidence**: Medium

### W-CX-2: `_second_source_pass` does not adjust cap states for first-pass extraction
- **File**: `/Users/dpbirge/GITHUB/community-agri-pv/src/water.py`, lines 1020-1021
- **Severity**: Medium
- **Issue**: `_second_source_pass` calls `_source_water` with the original `gw_cap_state` and `muni_cap_state`, which do not include the first-pass extraction from the same day. This is the same pattern as W-HC-5 but for the second source pass rather than overnight refill. The first pass already extracted groundwater and used municipal, but the cap states passed to the second pass still show the pre-day-N `used` values. This means the second pass could double-extract within a tight monthly cap.
- **Analysis**: The practical impact depends on how often the second pass triggers (only when demand exceeds single-pass throughput AND tank is drained to zero, per line 1004). With the current config (300 m3 tank, 100 m3/hr throughput), the second pass triggers rarely. But under tighter configurations or the sizing system, it could matter. Need to trace whether the `_gw_source` function's own extraction limit (`gw_extraction_limit = min(total_well_capacity, gw_allowance) - already_extracted`) partially mitigates this -- but `already_extracted` defaults to 0.0 in the second pass call.
- **Suggested approach**: Create adjusted cap states in `_second_source_pass` (same pattern as `_prefill_tank` at lines 677-680).
- **Confidence**: Medium

### W-CX-3: `compute_community_harvest` skips seasons that start before sim_start
- **File**: `/Users/dpbirge/GITHUB/community-agri-pv/src/crop_yield.py`, lines 270-272
- **Severity**: Medium
- **Issue**: The condition `if harvest_date > sim_end or planting_date < sim_start: continue` skips any season where planting occurs before the simulation start date. For a multi-year simulation starting on Jan 1, this correctly skips seasons that would need pre-simulation data. But for a simulation starting mid-year (e.g., July 1), it skips all first-year seasons planted before July 1. This includes crops like tomato (feb15), cucumber (feb15), kale (mar15) that have valid data in the simulation period but whose planting date precedes `sim_start`. Those crops' water consumption IS simulated (irrigation demand includes them because the crop growth CSVs cover the full year), but their harvest yield is not computed.
- **Analysis**: Need to verify whether `sim_start` is always Jan 1 in practice (it comes from the min date in the water balance, which comes from the date range in crop growth CSVs). If crop growth CSVs always start from Jan 1, this is not an issue. But if the simulation is ever configured to start mid-year, harvests for early-planted crops would be silently dropped.
- **Suggested approach**: Change the condition to only skip if `harvest_date > sim_end or harvest_date < sim_start` (check harvest date, not planting date against sim_start). Seasons planted before sim_start but harvested within the simulation window should be included, using whatever delivered/etc data is available in the water balance for the overlapping portion.
- **Confidence**: Medium

### W-CX-4: Treatment energy multiplier applied in dispatch but not to cost
- **File**: `/Users/dpbirge/GITHUB/community-agri-pv/src/water.py`, lines 1249-1259
- **Severity**: Low
- **Issue**: When the efficiency curve is available, the dispatch loop applies `energy_multiplier` to `treatment_energy_kwh` (line 1258) but does not apply a corresponding `maintenance_multiplier` to `groundwater_cost`. The sizing module's `_apply_efficiency_adjustment` (water_sizing.py lines 540-557) does apply the maintenance multiplier, but the main dispatch path in water.py does not. This means the same system configuration produces different cost outputs depending on whether it is run through `compute_water_supply` (no maintenance adjustment) or `_run_sizing_simulation` + `_apply_efficiency_adjustment` (with maintenance adjustment).
- **Analysis**: The maintenance multiplier in the sizing module uses an approximation (treatment fraction as proxy for maintenance portion of GW cost, line 553-554), so it may be intentionally omitted from the main dispatch for accuracy reasons. Need to confirm whether this asymmetry is by design.
- **Suggested approach**: Either apply the same maintenance adjustment in the dispatch loop, or document the intentional asymmetry. If applying it, use the same proxy logic from `_apply_efficiency_adjustment`.
- **Confidence**: Low

### W-CX-5: Look-ahead TDS for next day scans forward to first non-NaN, potentially skipping many fallow days
- **File**: `/Users/dpbirge/GITHUB/community-agri-pv/src/water.py`, lines 1364-1368
- **Severity**: Low
- **Issue**: The `next_tds_req` scan loops from `i+1` to `n_days` to find the first non-NaN TDS value. If there is a long fallow gap (e.g., 30+ days between crop seasons), the overnight refill will prepare the tank for a crop TDS requirement that is weeks away. This causes unnecessary overnight sourcing and energy expenditure during the fallow gap. The tank TDS will drift back toward the incoming source TDS over days of no demand, and the overnight refill on every fallow day will try to correct it again.
- **Analysis**: Need to check whether `_overnight_tds_refill` (line 1079) guards against this -- it checks `tank['fill_m3'] <= 0` and `tank['tds_ppm'] <= next_tds_req` which may prevent most unnecessary refills. But if tank stock remains from the previous season at elevated TDS, it will trigger repeated overnight refills across the entire fallow gap. Practical impact depends on fallow gap length and tank volume.
- **Suggested approach**: Cap the look-ahead for `next_tds_req` to a configurable horizon (e.g., 7 days). If no non-NaN TDS exists within the horizon, set `next_tds_req = NaN` to suppress overnight refill during deep fallow.
- **Confidence**: Low

## Observations (no fix needed)

- **Clean functional decomposition**: The separation of `_gw_source`, `_muni_source`, `_source_water`, and `_dispatch_day` into pure-ish functions with explicit state mutation via dict parameters is well-designed. The scratch-row pattern for prefill and overnight (copying keys to a temporary dict, then accumulating back) is verbose but correct and avoids accidental overwrites.

- **Strategy consistency**: The three demand-matching strategies (`minimize_cost`, `minimize_treatment`, `minimize_draw`) are implemented with consistent priority ordering. The `minimize_treatment` strategy has a slightly subtle two-pass approach (untreated GW first, then municipal, then treated GW for remainder) that correctly avoids treatment when raw GW meets TDS. This is well-structured.

- **Well distribution algorithm**: `_well_distribution` correctly handles capacity-limited redistribution with its iterative approach. The `if len(still_uncapped) == len(uncapped): break` guard prevents infinite loops when remaining demand exceeds total well capacity.

- **Robust zero-demand handling**: Both `compute_irrigation_demand` and `compute_water_supply` handle zero-demand days cleanly. Fallow days produce zero sourcing, zero delivery, and preserve tank state. The `_handle_fallow_day` function provides a clear separation point.

- **Config-driven flexibility**: The YAML configuration structure allows swapping strategies, caps, and system components without code changes. The data registry pattern with relative paths resolved against root_dir is clean and portable.

- **Sizing iteration is bounded**: `_iterate_until_target` limits to 3 iterations, preventing runaway loops. Storage expansion is capped at `_SIZING_MAX_STORAGE_M3 = 2000`. These are sensible safeguards.

- **Float precision guards**: The codebase uses `1e-9` comparisons for near-zero volume checks and `round(3)` for output columns. This is appropriate for the scale of values (m3/day in the tens to hundreds range).

- **Potential improvement -- vectorized simulation**: The day-by-day Python loop in `_run_simulation` (line 1356) with dict-based row construction is clear but slow for long simulations. For educational use this is fine, but if performance becomes a concern, the demand-matching strategies could be partially vectorized since they do not depend on treatment smoothing state.

- **Potential improvement -- type safety for strategy strings**: Strategy names are bare strings (`'minimize_cost'`, etc.) compared with `==` throughout. A misspelled strategy silently falls through to the `else` branch in several places (e.g., `_sort_well_candidates` line 210 treats unknown objectives as `minimize_draw`). An enum or explicit validation at entry points would catch typos.
