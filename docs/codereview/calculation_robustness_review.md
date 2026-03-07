# Calculation Robustness Review — Water & Energy Systems

Generated: 2025-03-06
Reviewers: Agent A (water), Agent B (energy)

## Summary

The codebase is architecturally sound with clean functional decomposition across both
water and energy systems. This review identified 9 high-confidence issues (6 water,
3 energy) and 10 complex issues (5 water, 5 energy) focused on calculation robustness.

---

## HIGH-CONFIDENCE ISSUES

### W-HC-1: Balance check NaN on day 1

- **File**: src/water_balance.py:174-179
- **Severity**: Medium
- **Status**: FIXED
- **Issue**: `tank_volume_m3.shift(1)` produces NaN on row 0 because the initial
  tank level from config is never injected. Day-1 conservation is never verified.
- **Fix**: Fill shifted series row 0 with initial tank level from water_systems config.
  Requires passing initial_tank_level into the balance diagnostics section.

### W-HC-2: total_sourced_to_tank_m3 accounting verified correct

- **File**: src/water.py:897 vs 1127-1136 and 1271-1283
- **Severity**: N/A (resolved during review)
- **Status**: CLOSED — no fix needed
- **Note**: `_finalize_dispatch_row` runs after overnight refill accumulation,
  so `total_sourced_to_tank_m3` in output does include overnight volumes. Confirmed
  by tracing call order.

### W-HC-3: Column name `{field}_etc_mm_per_ha` stores irrigation_mm, not ETc

- **File**: src/irrigation_demand.py:130
- **Severity**: Medium
- **Status**: FIXED
- **Issue**: Column named as ETc but contains policy-adjusted irrigation application.
  Misleading for downstream consumers.
- **Fix**: Rename to `{field}_irrigation_mm_per_ha`. Update downstream references in
  water_balance.py column ordering.

### W-HC-4: Stale config returned by size_water_system after deficit iteration

- **File**: src/water_sizing.py:898 and 1086
- **Severity**: High
- **Status**: FIXED
- **Issue**: Both `size_water_system()` and `optimize_water_system()` return the
  pre-iteration config object. When deficit iterations fire, the returned config
  does not match the returned metrics.
- **Fix**: After `_iterate_until_target`, rebuild config from final values.

### W-HC-5: Overnight refill cap accounting ignores current day's extraction

- **File**: src/water.py:1409-1410
- **Severity**: High
- **Status**: FIXED
- **Issue**: `_overnight_tds_refill` passes original `gw_cap_state` without adjusting
  for the current day's daytime extraction. Can exceed monthly cap by up to one day's
  extraction under tight caps.
- **Fix**: Create adjusted cap states in `_dispatch_day` before calling overnight refill:
  `on_gw_cap['used'] = gw_cap_state['used'] + row['total_groundwater_extracted_m3']`

### W-HC-6: `{field}_etc_m3` divides by efficiency (semantic mislabeling)

- **File**: src/irrigation_demand.py:132
- **Severity**: Medium
- **Status**: FIXED
- **Issue**: Column divides ETc by irrigation efficiency, making it delivery-equivalent.
  Yield model ratio cancels out so results are correct, but reuse hazard.
- **Fix**: Rename to `{field}_etc_delivery_m3` and update docstring. (Safer than
  changing the value, which would require yield model adjustment.)

### E-HC-1: Self-consumption ratio — confirmed safe

- **File**: src/energy_balance.py:731-733, 804-805
- **Severity**: N/A (resolved during review)
- **Status**: CLOSED — no fix needed
- **Note**: Accounting traced and confirmed correct across all code paths.

### E-HC-2: Test suite hardcoded constants mismatch config

- **File**: tests/test_energy_balance.py:17-19
- **Severity**: Medium
- **Status**: FIXED
- **Issue**: Tests hardcode BATTERY_CAPACITY_KWH=200 and BATTERY_SOC_MAX=0.95.
  Config has capacity_kwh=1000 and soc_max=0.8. Tests pass vacuously or fail
  for wrong reasons.
- **Fix**: Load constants from YAML config files at test time.

### E-HC-3: Generator 24-hour spread for power sizing

- **File**: src/energy_balance.py:559
- **Severity**: Medium
- **Status**: FIXED
- **Issue**: `deficit_kwh / 24.0` means any deficit under 360 kWh triggers minimum-load
  mode with 3-4x excess output. Models real behavior but 24h spread is unusual.
- **Fix**: Add configurable `reference_hours` parameter (default 24 for backward compat,
  recommend 8 for realistic operation).

### E-HC-4: Solar degradation applied after totals, then totals recomputed

- **File**: src/energy_supply.py:283-289
- **Severity**: Low
- **Status**: FIXED
- **Issue**: Totals computed, then degradation applied, then solar/renewable totals
  recomputed. Fragile ordering. Wind totals not recomputed (correct but brittle).
- **Fix**: Apply degradation before computing totals (single pass).

---

## COMPLEX ISSUES

### W-CX-1: TDS exceedance has no yield penalty

- **File**: src/water.py:520-548, src/crop_yield.py
- **Severity**: Medium
- **Status**: NEEDS REVIEW
- **Issue**: Delivered TDS can exceed crop threshold but yield model uses only volume
  ratios (ETa/ETc), ignoring TDS entirely. Design gap — elevated TDS damages crops.
- **Analysis needed**: Determine if FAO 29 TDS penalty function should be added to
  `compute_harvest_yield`. This is an enhancement, not a bugfix.

### W-CX-2: Second source pass has same cap-state staleness as overnight

- **File**: src/water.py:1231-1239
- **Severity**: Medium
- **Status**: FIXED
- **Issue**: `_second_source_pass` passes original cap states without first-pass
  extraction adjustment. Same pattern as W-HC-5 but for second source pass.
- **Fix**: Create adjusted `p1_gw_cap` and `p1_muni_cap` dicts in `_dispatch_day`
  that include first-pass extraction before calling `_second_source_pass`. Uses the
  same pattern as the W-HC-5 overnight refill fix (shallow-copy + add row totals).

### W-CX-3: compute_community_harvest skips seasons planted before sim_start

- **File**: src/crop_yield.py:267-286
- **Severity**: Medium
- **Status**: FIXED
- **Issue**: Condition `planting_date < sim_start` skips early-planted crops even if
  they harvest within the simulation window. Year loop also started at sim_start.year,
  missing prior-year plantings that harvest within the window.
- **Analysis**: sim_start is always Jan 1 with current weather data (2010-01-01 to
  2024-12-31), so the bug was latent. Two crops cross year boundaries in the base
  config: kale dec01 (85 days, harvests Feb 24) and potato sep15 (120 days, harvests
  Jan 13). Both planted in 2009 would harvest within the sim window but were missed.
- **Fix**: (1) Extended year range to `sim_start.year - 1` to catch prior-year
  plantings. (2) Changed skip condition from `planting_date < sim_start` to
  `harvest_date <= sim_start` so seasons planted before sim_start but harvested
  within it are considered. (3) Added zero-demand guard to skip seasons where the
  upstream irrigation demand module has no data (planted before sim_start with no
  water delivery tracking), preventing NaN yields.

### W-CX-4: Treatment maintenance cost multiplier missing from dispatch path

- **File**: src/water.py:1249-1259 vs src/water_sizing.py:540-557
- **Severity**: Low
- **Status**: NEEDS REVIEW
- **Issue**: Sizing module applies maintenance_multiplier but dispatch path does not.
  Same config produces different costs depending on entry point.
- **Analysis needed**: Determine if asymmetry is intentional (sizing approximation
  vs dispatch precision).

### W-CX-5: Unbounded TDS look-ahead causes unnecessary overnight refills in fallow

- **File**: src/water.py:1373-1378
- **Severity**: Low
- **Status**: FIXED
- **Issue**: Look-ahead scans to end of simulation for next non-NaN TDS requirement.
  During long fallow gaps, overnight refill prepares for a crop weeks away.
- **Analysis**: Fallow days return early from `_dispatch_day` (line 1180), so overnight
  refill only fires on the last active day before fallow. During the fallow gap, no
  water enters or leaves the tank. The existing guard at `_overnight_tds_refill` line
  1079 (`math.isnan(next_tds_req)`) would suppress refill if `next_tds_req` were NaN,
  but the unbounded scan always finds a future value. With a 7-day cap, day 1 of a new
  season may draw from a stale-TDS tank, but the system already tolerates 1-day TDS
  transition overshoot (comment at line 1184-1185), and overnight refill on day 1
  corrects for day 2+.
- **Fix**: Added configurable `tds_look_ahead_days` (default 7) to water policy.
  Scan capped to `min(i + 1 + tds_look_ahead, n_days)`. Set to `null` for unbounded
  (original behavior). Parameter documented in `settings/water_policy_base.yaml`
  and `_run_simulation` docstring.

### E-CX-1: Generator type/capacity mismatch — Willans line a-coefficient

- **File**: settings/energy_system_base.yaml:32-33, src/energy_balance.py:577
- **Severity**: Medium
- **Status**: FIXED
- **Issue**: Config uses diesel_100kw type but overrides rated_capacity_kw to 50.
  Willans `a * rated_kw` underestimates idle fuel by 50% because `a` is physically
  tied to engine size (100 kW), not the policy override (50 kW).
- **Fix**: Split `engine_capacity_kw` (from equipment CSV) from `rated_capacity_kw`
  (config override) in `_build_generator_specs`. Willans formula now uses
  `engine_capacity_kw` for the idle loss `a` term, while `rated_capacity_kw` remains
  the operational power limit. YAML comments clarified to document derated operation.

### E-CX-2: Battery type/capacity override mismatch

- **File**: settings/energy_system_base.yaml:38-39
- **Severity**: Low
- **Status**: FIXED
- **Issue**: Uses lithium_iron_phosphate_medium (200 kWh specs) but overrides to
  1000 kWh. Efficiency characteristics may not scale.
- **Fix**: Added `lithium_iron_phosphate_community` (1000 kWh) catalog entry to
  batteries-toy.csv. Updated config to reference the new entry, eliminating the
  type/capacity mismatch. Comment now accurately reflects the catalog specs.

### E-CX-3: No internal energy conservation assertion in dispatch loop

- **File**: src/energy_balance.py:951-973
- **Severity**: Medium
- **Status**: FIXED
- **Issue**: Conservation only validated by external tests, not within dispatch.
  A new action or accounting error would only be caught by test runs.
- **Fix**: Added two conservation assertions at the end of `_dispatch_day` (tolerance
  0.01 kWh). Demand balance: `total_demand = renewable_consumed + battery_discharge +
  grid_import + generator_kwh + deficit_kwh`. Generation balance: `total_renewable +
  generator_excess = renewable_consumed + battery_charge + grid_export + curtailed`.
  Verified passing on full 15-year simulation (5479 days).

### E-CX-4: Floating-point accumulation in daily cap allowance

- **File**: src/energy_balance.py:383-405
- **Severity**: Low
- **Status**: NEEDS REVIEW — likely no fix needed
- **Issue**: Repeated division across month days can accumulate float error.
  Existing clamp prevents practical overshoot (error ~1e-10 kWh).

### E-CX-5: community_demand.py positional concat without date validation

- **File**: src/community_demand.py:171-174
- **Severity**: Medium
- **Status**: FIXED
- **Issue**: Uses pd.concat(axis=1) without verifying date alignment across four CSVs.
  Currently safe because all CSVs share same date range, but latent fragility.
- **Fix**: Added date alignment assertions after loading the four building demand CSVs.
  Validates row count and date column equality against household_energy as reference
  before the positional concat.

---

## OBSERVATIONS (no fix needed)

### Water
- Clean functional decomposition with explicit state via dict parameters
- Three demand-matching strategies consistently implemented
- Well distribution algorithm correctly handles capacity redistribution
- Robust zero-demand and fallow day handling
- Sizing iteration bounded (3 max, 2000 m3 storage cap)
- Float precision guards (1e-9 comparisons, round(3) output)

### Energy
- Surplus dispatch order intentionally identical across all three strategies
- Battery renewable fraction tracking well-implemented (weighted average)
- Net metering incremental billing correctly implemented
- Battery charge efficiency accounting correct (accepted vs stored)
- Generator 10 Wh threshold prevents micro-startups from numerical noise
- Price lookup forward-fill correct for monthly-to-daily mapping
