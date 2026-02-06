# Implementation Plan: Inputs-to-Outputs Plots & Tables

## Overview

Build the 6 plots and 2 tables defined in `docs/architecture/mvp-structure.md` Section 5 ("Plots + Tables → Inputs to outputs"). Each phase is one task, executed sequentially. Each task produces a test script in `scripts/` that validates success.

**Ordering rationale:** Phases are sequenced by dependency — each phase builds on data/functions from the previous one. Plot 4 comes first because it's already buildable; Plot 6 comes last because it depends on everything.

**File conventions:**
- New plot/table functions → `src/notebook_plotting.py` (interactive, `plt.show()`)
- New data loading → `src/simulation/data_loader.py`
- New metric computations → `src/simulation/metrics.py`
- New simulation tracking → `src/simulation/simulation.py` and `src/simulation/state.py`
- Test scripts → `scripts/test_plot*.py` (standalone, runnable via `python scripts/test_plotX.py`)
- Test plot output → `notebooks/exports/` (gitignored)

---

## Phase 1: Plot 4 + Table 2 — Crop Prices & Revenue Diversification

**Status:** All data and metrics exist. Only needs new plot functions and one derived metric.

### Task 1 scope

**Data changes:** None

**Code changes:**

1. `src/notebook_plotting.py` — add 3 new functions:
   - `plot_crop_price_history(data_loader, start_year, end_year)` — Line chart of farmgate $/kg for all 5 crops (tomato, potato, onion, kale, cucumber) over the simulation date range. Read directly from crop price CSVs via `data_loader.get_crop_price_usd_kg()`. One line per crop. X: year, Y: $/kg.
   - `plot_monthly_revenue_by_crop(all_metrics)` — Stacked area chart of monthly revenue per crop. Uses `MonthlyFarmMetrics.crop_revenues_usd` dict. X: month, Y: USD. Stacked by crop with same color palette as existing crop yield plot.
   - `create_revenue_diversification_table(all_metrics, data_loader, scenario)` — Returns a DataFrame with columns: crop, area_fraction, annual_yield_kg, fresh_revenue_usd, revenue_share_pct, price_cv. Revenue share = crop revenue / total revenue × 100. Price CV = std(annual prices) / mean(annual prices) from crop price CSVs.

2. `src/simulation/metrics.py` — add:
   - `compute_revenue_concentration(yearly_farm_metrics)` — Returns max(crop_revenue) / sum(crop_revenue) × 100 for each year. Lower = more diversified.

### Success criteria

- Test script loads scenario, runs simulation, and generates:
  - `notebooks/exports/plot4a_crop_prices.png` — 5 lines, one per crop, correct $/kg range
  - `notebooks/exports/plot4b_revenue_by_crop.png` — stacked area, all crops visible
  - Printed Table 2 DataFrame with all columns populated, revenue shares summing to ~100%
  - Printed revenue concentration metric per year
- Script exits 0 with no errors

### Test script

`scripts/test_plot4_table2.py`

---

## Phase 2: Plot 1 — Input Price Index

**Status:** Water and electricity price data loaded. Diesel data file exists but has no loader. Fertilizer data does not exist.

### Task 2 scope

**Data changes:**

1. Create `data/prices/inputs/historical_fertilizer_costs-toy.csv`
   - Columns: `date, usd_per_ha, egp_per_ha_original, usd_egp_exchange_rate, notes`
   - Date range: 2015-2024 (annual, matching other price files)
   - Values: Derive from typical Egyptian fertilizer costs (~$200-400/ha, trending upward with currency devaluation). Use metadata header format matching other research CSVs.
   - Suffix: `-toy` since this is synthetic/estimated data

**Code changes:**

1. `src/simulation/data_loader.py` — add 2 new methods:
   - `_load_diesel_prices()` + `get_diesel_price_usd_liter(target_date)` — Load `data/prices/diesel/historical_diesel_prices-research.csv`, index by date, interpolate/forward-fill for lookup by arbitrary date. Return USD/liter.
   - `_load_fertilizer_costs()` + `get_fertilizer_cost_usd_ha(target_date)` — Load the new fertilizer CSV, same pattern as diesel.

2. `src/notebook_plotting.py` — add:
   - `plot_input_price_index(data_loader, base_year=2015)` — Line chart with 4 series (water, electricity, diesel, fertilizer) normalized to base_year = 100. For each input, get the price at each available year, divide by base_year price, multiply by 100. X: year, Y: price index. Include a horizontal dashed line at 100 for reference.

### Success criteria

- Test script instantiates `SimulationDataLoader`, calls all 3 new methods:
  - Prints diesel prices for 2015-2024 (should be $0.07-0.40/L range based on research data)
  - Prints fertilizer costs for 2015-2024
  - Prints water and electricity prices for 2015-2024
  - Generates `notebooks/exports/plot1_input_price_index.png` with 4 lines diverging from 100
- Script exits 0

### Test script

`scripts/test_plot1.py`

---

## Phase 3: Plot 2 + Table 1 — Effective vs. Market Input Cost

**Status:** Simulation tracks actual water costs. Need counterfactual "what if all government" computation. Energy side deferred (policy stubbed).

### Task 3 scope

**Data changes:** None

**Code changes:**

1. `src/simulation/metrics.py` — add:
   - `compute_counterfactual_water_cost(simulation_state, data_loader)` — For each farm, for each daily water record: compute `demand_m3 × municipal_price_per_m3(date)`. Sum by year. Returns dict: `{year: {farm_id: counterfactual_cost_usd}}`. This represents what the farm would have paid if it purchased ALL water from the municipal source at the government rate.
   - `compute_blended_water_cost_per_m3(simulation_state)` — For each farm, for each year: `total_water_cost / total_water_m3`. Returns dict: `{year: {farm_id: blended_usd_per_m3}}`. This is the actual effective cost per cubic meter.
   - `compute_market_water_price_per_m3(data_loader, years)` — For each year, return the municipal price per m³. Returns dict: `{year: usd_per_m3}`. This is what the government charges.

2. `src/notebook_plotting.py` — add:
   - `plot_effective_vs_market_cost(all_metrics, counterfactual, blended, market_prices)` — 2-panel figure. Panel 1 (water): dual lines — blended $/m³ (blue, "Self-owned") vs. municipal $/m³ (red, "Government"). Panel 2 (energy): text annotation "Energy policy not yet implemented — coming in Phase 4+". X: year, Y: $/m³.
   - `create_cost_comparison_table(all_metrics, counterfactual)` — DataFrame with columns: year, self_owned_water_cost_usd, government_water_cost_usd, water_savings_pct, energy columns as "N/A". Water savings = (government - self_owned) / government × 100.

### Success criteria

- Test script runs simulation, computes counterfactual, and:
  - Prints actual vs. counterfactual water cost per year (counterfactual should be higher if groundwater is cheaper)
  - Generates `notebooks/exports/plot2_effective_vs_market.png` with 2 panels
  - Prints Table 1 DataFrame showing savings percentages
- Script exits 0

### Test script

`scripts/test_plot2_table1.py`

---

## Phase 4: Plot 3 — Monthly Input Cost Breakdown

**Status:** Only water costs tracked in simulation. Need to add energy cost USD, and proxy costs for diesel, fertilizer, and labor.

### Task 4 scope

**Data changes:** None (fertilizer data created in Phase 2)

**Code changes:**

1. `src/simulation/state.py`:
   - Add to `DailyWaterRecord`: `energy_cost_usd: float = 0.0` (energy USD cost for water treatment that day)
   - Add to `MonthlyFarmMetrics`: `energy_cost_usd: float = 0.0`, `diesel_cost_usd: float = 0.0`, `fertilizer_cost_usd: float = 0.0`, `labor_cost_usd: float = 0.0`, `total_operating_cost_usd: float = 0.0`
   - Add to `YearlyFarmMetrics`: same 5 new fields

2. `src/simulation/simulation.py`:
   - After water allocation: compute `energy_cost_usd = allocation.energy_used_kwh × electricity_price_per_kwh` and store in `DailyWaterRecord.energy_cost_usd`
   - Note: diesel cost is 0 when generator capacity is 0 (current mvp-settings). Add the field for future use but don't compute unless generator capacity > 0.

3. `src/simulation/metrics.py`:
   - Update `compute_monthly_metrics()`: aggregate `energy_cost_usd` from daily records (sum of `energy_cost_usd` per month). Compute monthly `fertilizer_cost_usd` as `(annual_fertilizer_usd_per_ha × farm_area_ha) / 12` using `data_loader.get_fertilizer_cost_usd_ha()`. Compute monthly `labor_cost_usd` from labor parameter files (load `labor_requirements-toy.csv` and `labor_wages-toy.csv`, compute per-ha monthly cost). Set `total_operating_cost_usd = water + energy + diesel + fertilizer + labor`.
   - Update `compute_yearly_metrics()`: same aggregation at yearly level.
   - Add: `compute_cost_volatility(monthly_metrics)` — CV of `total_operating_cost_usd` across months. Returns float.

4. `src/simulation/data_loader.py`:
   - Add `_load_labor_costs()` + `get_labor_cost_usd_ha_month(target_date)` — Load labor requirements and wages, compute composite monthly labor cost per hectare. Simplified: use average labor hours/ha/month × wage rate.

5. `src/notebook_plotting.py` — add:
   - `plot_monthly_cost_breakdown(all_metrics)` — Stacked area chart with 5 layers: water (blue), energy (yellow), diesel (gray), fertilizer (green), labor (orange). X: month, Y: USD. Legend. Shows which inputs dominate cost structure.

### Success criteria

- Test script runs simulation and:
  - Prints monthly breakdown showing water > 0, energy > 0 (should be non-zero since water treatment uses energy), diesel = 0 (generator off), fertilizer > 0, labor > 0
  - Prints total_operating_cost = sum of all 5 categories (verified programmatically)
  - Prints cost volatility CV
  - Generates `notebooks/exports/plot3_cost_breakdown.png` with stacked area
- Script exits 0

### Test script

`scripts/test_plot3.py`

---

## Phase 5: Plot 5 — Net Farm Income

**Status:** After Phase 4, both revenue and total operating costs are tracked monthly. This becomes straightforward.

### Task 5 scope

**Data changes:** None

**Code changes:**

1. `src/simulation/metrics.py` — add:
   - `compute_net_income(monthly_metrics)` — For each month: `net_income = total_crop_revenue_usd - total_operating_cost_usd`. Also compute `operating_margin_pct = net_income / total_crop_revenue_usd × 100` (guarded against zero revenue). Returns list of dicts with month, revenue, cost, net_income, margin.

2. `src/notebook_plotting.py` — add:
   - `plot_net_farm_income(all_metrics)` — Dual-line chart: revenue (green) and total operating cost (red) as lines. Shade the gap: green where revenue > cost (profit), red where cost > revenue (loss). Horizontal dashed line at y=0 for break-even. X: month, Y: USD.

### Success criteria

- Test script runs simulation and:
  - Prints monthly net income, verifies it equals revenue minus cost
  - Prints operating margin for each month
  - Identifies months with negative income (if any)
  - Generates `notebooks/exports/plot5_net_income.png` with dual lines and shaded gap
- Script exits 0

### Test script

`scripts/test_plot5.py`

---

## Phase 6: Plot 6 — Profit Margin Sensitivity (Tornado Chart)

**Status:** Requires a new sensitivity analysis harness that re-runs the simulation with perturbed prices.

### Task 6 scope

**Data changes:** None

**Code changes:**

1. `src/simulation/sensitivity.py` (new file):
   - `run_sensitivity_analysis(scenario_path, parameters, variation_pct=0.20)` — For each parameter in the list (e.g., "water_price", "electricity_price", "diesel_price", "fertilizer_cost", "tomato_price", "potato_price", etc.):
     - Run simulation with parameter at -variation_pct (80% of base)
     - Run simulation with parameter at +variation_pct (120% of base)
     - Record net farm income for each
   - Returns dict: `{param_name: {"low": income_at_minus, "base": income_at_base, "high": income_at_plus}}`
   - Implementation: Modify `SimulationDataLoader` to accept price multipliers (a dict of `{price_type: multiplier}` that scales returned prices). This avoids modifying scenario files.

2. `src/simulation/data_loader.py`:
   - Add `price_multipliers: dict` parameter to `SimulationDataLoader.__init__()` (default empty dict)
   - In each `get_*_price_*()` method, apply multiplier if present: `return base_price × multipliers.get(key, 1.0)`

3. `src/notebook_plotting.py` — add:
   - `plot_tornado_sensitivity(sensitivity_results, base_income)` — Horizontal bar chart. One bar per parameter. Each bar extends from `income_at_minus - base` (left) to `income_at_plus - base` (right). Sorted by total swing (widest at top). Color: red for negative impact, green for positive. X: change in net income (USD), Y: parameter names.

### Success criteria

- Test script runs full sensitivity analysis (will take ~12-20 simulation runs) and:
  - Prints sensitivity results for each parameter
  - Identifies the top 3 most impactful parameters
  - Generates `notebooks/exports/plot6_tornado.png` with bars sorted by impact
  - Total runtime reported (should be under 2 minutes for the full sweep)
- Script exits 0

### Test script

`scripts/test_plot6.py`

---

## Dependency Graph

```
Phase 1 (Plot 4 + Table 2) — no dependencies
  ↓
Phase 2 (Plot 1) — adds diesel loader + fertilizer data
  ↓
Phase 3 (Plot 2 + Table 1) — adds counterfactual function
  ↓
Phase 4 (Plot 3) — adds energy/fertilizer/labor cost tracking to simulation
  ↓
Phase 5 (Plot 5) — adds net income metric
  ↓
Phase 6 (Plot 6) — adds sensitivity harness + tornado plot
```

## Estimated Scope

| Phase | New functions | Files modified | Data files | Complexity |
|-------|--------------|----------------|------------|------------|
| 1     | 4            | 2              | 0          | Low        |
| 2     | 4            | 2              | 1 new CSV  | Low-Medium |
| 3     | 5            | 2              | 0          | Medium     |
| 4     | 4            | 5              | 0          | High       |
| 5     | 2            | 2              | 0          | Low        |
| 6     | 3            | 3 (1 new)      | 0          | High       |
