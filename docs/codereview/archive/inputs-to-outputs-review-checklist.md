# Code Review Checklist: Inputs-to-Outputs Plots Implementation

Covers the 6-phase implementation of plots and tables defined in `docs/architecture/mvp-structure.md` Section 5 ("Plots + Tables → Inputs to outputs").

**Files modified:** `state.py`, `simulation.py`, `data_loader.py`, `metrics.py`, `notebook_plotting.py`
**Files created:** `sensitivity.py`, `historical_fertilizer_costs-toy.csv`, 6 test scripts in `scripts/`

---

## 1. Data Integrity

- [ ] **Fertilizer CSV values are reasonable** — `data/prices/inputs/historical_fertilizer_costs-toy.csv` uses $220-380/ha range. Cross-check against Egyptian agricultural benchmarks. Verify EGP values = USD × exchange rate for each row.
- [ ] **Labor cost computation is correct** — `_load_labor_costs()` in data_loader.py matches skill levels to wages correctly (unskilled→field_worker, semi-skilled→field_supervisor, skilled→equipment_operator). Verify the computed $2,098/ha/year is plausible.
- [ ] **Diesel price forward-fill behavior** — Diesel CSV has irregular dates (not annual). Verify `get_diesel_price_usd_liter()` correctly forward-fills or selects nearest date rather than erroring on dates between entries.
- [ ] **Crop price lookup at date boundaries** — Crop price CSVs are annual (2015-2024). Verify `get_crop_price_usd_kg()` handles lookups at the exact boundary dates and doesn't off-by-one.

## 2. Double-Counting & Accounting

- [ ] **Energy cost is not double-counted** — `allocation.cost_usd` already includes treatment energy cost. Phase 4 added `energy_cost_usd` as a separate field. Verify that `plot_monthly_cost_breakdown()` uses `total_water_cost_usd - energy_cost_usd` for the water layer (not `total_water_cost_usd`), so water + energy + diesel + fertilizer + labor = `total_operating_cost_usd`.
- [ ] **total_operating_cost_usd sums correctly** — In `compute_monthly_metrics()`, verify the formula: `total_operating = water_cost_net + energy_cost + diesel + fertilizer + labor` where `water_cost_net = water_cost - energy_cost`.
- [ ] **Counterfactual uses same pricing logic as simulation** — `compute_counterfactual_water_cost()` should use the same unsubsidized escalation formula (`base × (1 + pct)^years`) as `build_water_policy_context()` in simulation.py. Compare the two code paths.

## 3. Backward Compatibility

- [ ] **compute_monthly_metrics() with no data_loader** — New signature adds `data_loader=None, scenario=None`. When called without them (old code paths), fertilizer/labor/energy costs should default to 0.0, not error.
- [ ] **compute_all_metrics() with no data_loader** — Same backward compatibility check.
- [ ] **SimulationDataLoader with no price_multipliers** — Default `None` should result in all multipliers being 1.0. Verify no `NoneType` errors when `price_multipliers` is not passed.
- [ ] **run_simulation() with no data_loader** — The `data_loader=None` parameter should create one internally as before.
- [ ] **Existing notebook still works** — `notebooks/run_simulation.ipynb` imports from `notebook_plotting.py`. Verify the old imports still resolve and existing functions aren't broken.

## 4. Price Multiplier Correctness (Sensitivity)

- [ ] **Multiplier applied at return, not during computation** — Each getter should multiply the final value, not intermediate calculations. Especially check `get_municipal_price_usd_m3()` which has multiple code paths (subsidized tiers, unsubsidized escalation).
- [ ] **get_electricity_price_usd_kwh() tuple return** — This method can return a tuple `(offpeak, peak)` when `use_average=False`. Verify the multiplier is applied correctly in both the scalar and tuple return paths.
- [ ] **Municipal water sensitivity shows zero swing** — The tornado chart shows $0 swing for municipal water. This is because the simulation uses unsubsidized pricing computed in `build_water_policy_context()` from scenario config, not from `get_municipal_price_usd_m3()`. Verify this is documented/expected, not a bug in multiplier application.
- [ ] **Diesel sensitivity shows zero swing** — Generator capacity is 0 in mvp-settings.yaml, so diesel is never used. Verify this is documented/expected.

## 5. Sensitivity Analysis Logic

- [ ] **Fresh scenario per run** — `run_sensitivity_analysis()` must call `load_scenario()` fresh for each simulation run, since `run_simulation()` mutates the state objects. Verify no state leakage between runs.
- [ ] **Correct multiplier direction** — For input costs: price increase should decrease income (negative delta). For crop prices: price increase should increase income (positive delta). Check that the signs in the test output match this expectation.
- [ ] **Base case reproducibility** — Base income should match the standalone simulation. Verify $8,597,064.12 matches what `test_plot5.py` reports.

## 6. Dataclass Field Ordering

- [ ] **Fields with defaults after fields without** — Python dataclasses require this. Verify `DailyWaterRecord.energy_cost_usd: float = 0.0` comes after the non-default fields but before the `Optional` fields (which also have defaults). Check `MonthlyFarmMetrics` and `YearlyFarmMetrics` similarly.
- [ ] **No ordering conflicts after additions** — If a non-default field was accidentally placed after a default field, it would cause a TypeError at import time. All test scripts passing is a good sign, but verify visually.

## 7. Plot Quality

- [ ] **Plot 1 (Price Index)** — All 4 lines start at 100 in base year. Lines diverge over time. Legend and axis labels present.
- [ ] **Plot 2 (Effective vs Market)** — Blue line (self-owned) below red line (government) in water panel. Green fill between them. Energy panel shows placeholder text.
- [ ] **Plot 3 (Cost Breakdown)** — 5 stacked layers sum to total. Water dominates during irrigation months. No negative values. Fertilizer and labor are constant monthly.
- [ ] **Plot 4a (Crop Prices)** — 5 crop lines with correct farmgate price ranges ($0.30-1.50/kg typical). 4b shows stacked revenue with all crops visible.
- [ ] **Plot 5 (Net Income)** — Green/red shading appears in correct regions. Revenue spikes at harvest months. Cost line is smooth-ish.
- [ ] **Plot 6 (Tornado)** — Bars sorted widest-to-narrowest top-to-bottom. Red for negative deltas, green for positive. Symmetric bars for crop prices (±20% should give equal and opposite impact).

## 8. Edge Cases

- [ ] **Zero-revenue months** — Most months have $0 crop revenue (harvests are seasonal). Verify operating margin is handled (no division by zero) — should be 0% not NaN/error.
- [ ] **Zero-water months** — July-August may have no irrigation if no crops are in season. Verify blended cost per m³ handles zero water (no division by zero).
- [ ] **Year boundary metrics** — Yearly metrics snapshot at year boundaries. Verify the final year (2020) is captured correctly in both Phase 3 counterfactual and Phase 4 cost breakdown.
- [ ] **Revenue concentration with single crop** — If only one crop has revenue in a year, concentration should be 100%. Verify the metric handles this.

## 9. Code Style & Documentation

- [ ] **Docstrings on all new functions** — Each of the ~15 new functions should have a docstring explaining args, returns, and purpose.
- [ ] **Consistent naming** — New fields follow existing conventions (e.g., `_usd` suffix for dollar amounts, `_m3` for water volumes).
- [ ] **No hardcoded paths** — Test scripts should resolve paths relative to project root, not use absolute paths.
- [ ] **Comment header on new CSV** — `historical_fertilizer_costs-toy.csv` should have `# SOURCE`, `# DATE`, `# DESCRIPTION`, etc. matching the project's metadata header convention.

## 10. Missing/Deferred Items

- [ ] **Processed product revenue** — Table 2 was planned to include "processed revenue" column but market policy is stubbed. Verify column is omitted or shows "N/A", not zero.
- [ ] **Energy panel in Plot 2** — Should show placeholder text, not an empty panel or error.
- [ ] **Plan document updated** — `docs/planning/inputs_to_outputs_plots_plan.md` reflects what was actually built, not just what was planned.
