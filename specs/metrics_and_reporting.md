# Metrics, Plots, and Reporting Specifications

This document was extracted from `structure.md` and defines all model output metrics, visualization specifications, and reporting tables. For configuration schema and system design parameters, see [structure.md](structure.md). For policy decision rules and pseudocode, see [policies.md](policies.md). For calculation methodologies and formulas, see [calculations.md](calculations.md).

## 1. Metrics

Metrics are computed at daily, monthly, and yearly granularity. Farm-level and community-level aggregations are provided separately. Units shown in brackets. Metrics tagged *(resilience)* are also used as inputs to the resilience and survivability analysis suite (see Resilience metrics). See `calculations.md` for formulas.

### Water metrics

- Total water use [m³/yr]
- Groundwater use [m³/yr, m³/kg-yield]
- Municipal water use [m³/yr, m³/kg-yield]
- Water use efficiency [m³/kg-yield] — total water per kg crop output
- Water self-sufficiency [%] — groundwater / total water × 100 *(resilience)*
- Aquifer depletion rate [m³/yr drawdown, estimated years remaining] *(resilience)* — Tracked for reporting only; does not trigger allocation changes in MVP.
- Days without municipal water [days/yr] — days farm operated on groundwater only *(resilience)*
- Water treatment energy [kWh/yr, kWh/m³]
- Water storage utilization [%] — average storage level / capacity
- Irrigation demand vs delivery [m³/day] — requested vs actually allocated

### Energy metrics

- PV generation [kWh/yr, kWh/kWp-installed]
- Wind generation [kWh/yr, kWh/kW-installed]
- Total renewable generation [kWh/yr]
- Grid electricity import [kWh/yr]
- Grid electricity export [kWh/yr] — if export enabled
- Backup generator output [kWh/yr, L-fuel/yr]
- Battery throughput [kWh/yr] — total charge + discharge cycles
- Energy self-sufficiency [%] — renewable generation / total consumption × 100 *(resilience)*
- Days without grid electricity [days/yr] — days community operated off-grid *(resilience)*
- Curtailment [kWh/yr] — excess generation that cannot be used or stored
- Blended electricity cost [$/kWh] — weighted average across all sources

### Crop production metrics

- Total crop yield [kg/yr, kg/ha]
- Crop yield by type [kg/yr per crop]
- Crop revenue by type [$/yr per crop]
- Post-harvest losses [kg/yr, % of harvest]
- Processed product output [kg/yr by processing type]
- Processing utilization [%] — actual throughput / processing capacity
- Crop diversity index [count of crops, Shannon index] *(resilience)*
- PV microclimate yield protection [%] — fraction of yield shielded from extreme heat *(resilience)*

### Unit cost metrics (normalized)

- Water cost [$/m³, $/kg-yield]
- Electricity cost [$/kWh] — blended across sources
- Labor cost [$/ha, $/kg-yield]
- Fertilizer and input cost [$/ha]
- Diesel fuel cost [$/L, $/kWh-generated]

### Revenue metrics

- Fresh crop revenue [$/yr, $/kg by crop]
- Processed product revenue [$/yr, $/kg by product type]
- Grid electricity export revenue [$/yr]
- Total gross revenue [$/yr]

### Operational cost metrics

- Infrastructure O&M cost [$/yr by system: water, energy, processing]
- Debt service payments [$/yr]
- Labor costs [$/yr]
- Input costs [$/yr] — fertilizer, seed, chemicals
- Total operating expense [$/yr]
- Operating margin [%] — (revenue − operating costs) / revenue
- Cost volatility [CV] — coefficient of variation of monthly operating costs *(resilience)*

### Financial performance metrics

- Net farm income [$/yr] — revenue minus all costs
- Payback period [years] — for infrastructure investments
- Return on investment [%]
- Net present value [$] — of community operations over simulation period
- Debt-to-revenue ratio [ratio]
- Cash reserves [$] — community bank balance at end of period
- Cash reserve adequacy [months] — reserves / average monthly operating expense *(resilience)*

### Labor metrics

- Total employment [person-hours/yr]
- Employment by activity [hours/yr] — field work, transport, processing, maintenance, admin
- Peak labor demand [person-hours/month]
- Community vs external labor ratio [%]
- Jobs supported [FTE/yr]

### Resilience metrics (survivability & sensitivity)

Resilience metrics evaluate community survivability under stress. They are computed across Monte Carlo ensembles and sensitivity sweeps, using the *(resilience)*-tagged metrics above as inputs.

**Monte Carlo survivability:**

- Survival rate [%] — fraction of runs completing full simulation without insolvency
- Probability of crop failure [% of runs] — at least one season with >50% yield loss
- Probability of insolvency [% of runs] — cash reserves fall below zero
- Median years to insolvency [years] — among runs that fail, median time before default
- Worst-case net income [$/yr] — 5th percentile annual net income across runs

**Distributional outcomes:**

- Net income distribution [$/yr] — percentiles (5th, 25th, 50th, 75th, 95th) across runs
- Worst-case farmer outcome [$/yr] — minimum net income across farms within a run
- Income inequality across farms [Gini coefficient] — spread of outcomes within community
- Maximum drawdown [$/peak-to-trough] — largest cumulative loss from peak cash reserves

**Sensitivity analysis:**

- Parameter sensitivity ranking — which inputs most affect survival rate and net income
- Breakeven thresholds — critical values where survival rate drops below target (e.g., minimum PV capacity, maximum water price)
- Scenario stress tests — outcomes under specific adverse conditions (drought, price spike, equipment failure)

### Metric calculation references

Metrics listed above that require non-trivial formulas are defined in `calculations_economic.md` and `calculations_crop.md`. For implementers building from these four spec files alone, the following stubs provide the essential formulas:

**Net Present Value (NPV):**

```text
NPV = -Initial_CAPEX + SUM over years t=1..N: net_income_t / (1 + discount_rate)^t
```

Where `Initial_CAPEX` = `economic_state.total_capex_invested` and `discount_rate` from scenario config.

**Internal Rate of Return (IRR):**

```text
Solve for r: 0 = -Initial_CAPEX + SUM over years t=1..N: net_income_t / (1 + r)^t
```

Use `numpy.irr()` or equivalent root-finding method. If no real solution exists, report as NaN.

**Payback Period:**

```text
payback_years = first year t where cumulative_net_income[1..t] >= Initial_CAPEX
```

If cumulative net income never exceeds CAPEX within the simulation, report as "> N years".

**Return on Investment (ROI):**

```text
ROI = (total_net_income - Initial_CAPEX) / Initial_CAPEX * 100
```

**Gini Coefficient (income inequality across farms):**

```text
sorted_incomes = sort(farm_net_incomes)  # ascending
n = len(sorted_incomes)
gini = (2 * SUM(i * sorted_incomes[i] for i in 1..n)) / (n * SUM(sorted_incomes)) - (n + 1) / n
```

**Shannon Diversity Index (crop diversity):**

```text
H = -SUM(p_i * ln(p_i) for each crop i where p_i > 0)
```

Where `p_i` = fraction of total farming area allocated to crop i.

**Coefficient of Variation (CV):**

```text
CV = std_dev(values) / mean(values)
```

Used for cost volatility and price volatility metrics.

**Debt service (monthly payment per financing profile):**

```text
IF financing_status in [loan_standard, loan_concessional]:
    monthly_payment = capital_cost * (r * (1+r)^n) / ((1+r)^n - 1)
    WHERE r = annual_interest_rate / 12, n = loan_term_years * 12
ELSE:
    monthly_payment = 0
```

Interest rates and loan terms come from `financing_profiles-toy.csv`.

**Labor cost components (daily):**

```text
daily_overhead_cost = annual_admin_labor_cost / 365  # management, bookkeeping
daily_field_cost = labor_hours_per_ha_per_day * wage_per_hour * total_active_ha
daily_harvest_cost = harvest_labor_hours_per_kg * wage_per_hour * harvest_kg_today
daily_processing_cost = processing_labor_hours_per_kg * wage_per_hour * processed_kg_today
```

Labor rates loaded from `data/parameters/labor/` CSV files (see data registry).

**Input costs (fertilizer, seeds, chemicals):**

```text
daily_input_cost = (annual_input_cost_per_ha * total_active_ha) / 365
```

MVP uses a fixed annual rate per hectare from `data/parameters/costs/` CSV files. Default: ~$800/ha/yr (representative for irrigated vegetable production in arid regions).

## 2. Plots + Tables

### Inputs to outputs

Goal: Show the causal chain from volatile input prices to farm profitability, and demonstrate two key protective strategies — (1) self-owning water/energy infrastructure to stabilize input costs, and (2) crop and product diversification to stabilize revenues.

#### Metrics to track

**Input price metrics (from price data):**

- Municipal water price [$/m³] — government-supplied water price over time
- Grid electricity price [$/kWh] — government grid tariff over time
- Diesel price [$/L] — fuel price for backup generation and transport
- Fertilizer cost [$/ha] — aggregate input cost per hectare

**Effective cost metrics (computed, infrastructure-dependent):**

- Blended water cost [$/m³] — weighted average of self-produced (BWRO) and municipal water
- Blended energy cost [$/kWh] — weighted average of PV/wind, battery, grid, and diesel
- Total input cost [$/ha/month] — sum of water + energy + diesel + fertilizer + labor per hectare

**Revenue metrics (computed, diversification-dependent):**

- Crop price by type [$/kg] — farmgate price per crop (tomato, potato, onion, kale, cucumber)
- Revenue by crop [$/month] — monthly revenue per crop from fresh and processed sales
- Revenue concentration [%] — share of total revenue from single largest crop (lower = more diversified)

**Bottom-line metrics:**

- Net farm income [$/month] — total revenue minus total operating costs
- Operating margin [%] — (revenue - operating costs) / revenue
- Cost volatility [CV] — coefficient of variation of monthly total input costs (lower = more stable)

#### Plots (minimal set, 6 plots)

**Plot 1 — Input Price Index (time series, line chart)**  
All four input prices (water, electricity, diesel, fertilizer) normalized to a base-year index = 100. Single chart, 4 lines. Establishes the problem: external prices are volatile and driven by government policy, currency devaluation, and global commodity markets. X: year, Y: price index.

**Data sources and normalization:**

- Municipal water price: `resolve_water_price("agricultural", 0)` for each year (see `simulation_flow.md` Section 4.3)
- Grid electricity price: `resolve_energy_price("agricultural")` for each year (see `simulation_flow.md` Section 4.4)
- Diesel price: historical diesel price from `data/prices/diesel/` for each year
- Fertilizer cost: annual input cost from `data/parameters/costs/` for each year
- Normalization: base-year index = 100, where base year = `simulation.start_date.year`. Index for year t = `price_t / price_base_year * 100`.

**Plot 2 — Effective vs. Market Input Cost (paired bar or dual-line chart)**  
Compares what the farm actually pays (blended cost from self-produced + purchased) vs. what it would pay buying everything from the government, for both water ($/m³) and energy ($/kWh). Two panels or two pairs of lines. Key insight: self-owned infrastructure costs are dominated by fixed O&M and debt service, so they flatten out relative to market price swings. X: year, Y: cost per unit.

**Plot 3 — Monthly Input Cost Breakdown (stacked area chart)**  
Total monthly operating costs decomposed by category: water, energy, diesel, fertilizer, labor. Shows which inputs dominate the cost structure and which introduce the most month-to-month variability. X: month, Y: cost (USD).

**Plot 4 — Crop Prices and Revenue Diversification (2-panel chart)**

- Panel A: Crop price time series (5 lines, one per crop) showing different seasonal patterns and volatility. Establishes that any single crop is risky.
- Panel B: Monthly revenue stacked by crop, showing how shortfalls in one crop are offset by others. Demonstrates the diversification benefit.  
X: month, Y: $/kg (panel A), USD (panel B).

**Plot 5 — Net Farm Income: Revenue vs. Costs (dual-line with fill)**  
Revenue line and cost line over time, with the gap (net income) shaded. Optionally overlay a horizontal break-even line. Directly shows whether the farm is profitable and how stable that profit is. X: month, Y: USD.

**Plot 6 — Profit Margin Sensitivity (tornado chart)**  
Shows the impact on net farm income of a ±20% swing in each input price (water, electricity, diesel, fertilizer) and each crop price. Bars extend left (negative impact) and right (positive impact) from the baseline. Directly answers: "which price change hurts (or helps) the most?" — guiding infrastructure and diversification priorities.

#### Tables (minimal set, 2 tables)

**Table 1 — Annual Cost Summary: Self-Owned vs. Government-Purchased**  
One row per year. Columns: year, self-owned water cost, government water cost, savings (%), self-owned energy cost, government energy cost, savings (%), total input cost, net income. Shows cumulative economic advantage of infrastructure ownership.

**Counterfactual calculation:** The "government-purchased" baseline represents what the community would pay if it had no self-owned infrastructure and purchased all water and energy from external suppliers:

```text
government_water_cost = total_water_m3 * resolve_water_price("agricultural", cumulative_m3)
government_energy_cost = total_energy_kwh * resolve_energy_price("agricultural")
savings_water_pct = (government_water_cost - actual_water_cost) / government_water_cost * 100
savings_energy_pct = (government_energy_cost - actual_energy_cost) / government_energy_cost * 100
```

"Actual" costs include infrastructure O&M, debt service, and any residual grid/municipal purchases. The comparison uses the same pricing regime (subsidized or unsubsidized) for both actual and counterfactual to isolate the infrastructure ownership effect.

**Table 2 — Revenue Diversification Summary**  
One row per crop. Columns: crop, area fraction, annual yield (kg), fresh revenue ($), processed revenue ($), total revenue ($), revenue share (%), price CV. Shows contribution of each crop and product type to total revenue and highlights which crops are most volatile.

## 3. Post-Loop Terminal Valuation

Remaining unsold storage tranches at the end of the simulation are valued for NPV calculation purposes. This is NOT a sale — no revenue transaction occurs and no cash changes hands. The terminal value enters the NPV calculation as a salvage inflow in the final period.

**Valuation method:**

```text
terminal_value = SUM over all remaining tranches:
    tranche.kg * last_day_price(tranche.crop_name, tranche.product_type)
```

Where `last_day_price` is the market price on the final simulation day for the given crop and product type, loaded from the same price data files used during the simulation. No discount or premium is applied — the assumption is that remaining inventory could be liquidated at prevailing market prices.

Terminal value is reported separately from operating revenue in financial metrics and is added to the final year's cash flow for NPV/IRR calculation only.
