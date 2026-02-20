# Community Farm Model Calculation Methodologies

## 1. Overview

This document defines HOW configuration parameters from `structure.md` are used in calculations throughout the simulation. It provides formulas, data sources, units, and references to scientific literature. Sections marked **TBD** have conceptual formulas but require further research or design decisions before implementation.

For WHAT parameters exist and their valid options, see `structure.md`. For the full list of output metrics these calculations feed into, see `metrics_and_reporting.md`.

> **Implementation status:** Most sections are fully implemented. Two documented features are pending code implementation: **Aquifer Drawdown Feedback** (see `calculations_water.md` Section 11) and **Crop Diversity Index — revenue weighting** (see `calculations_crop.md` Section 7). See `future_improvements.md` for tracked deferred features.

For implementation code, see `src/settings/calculations.py` and respective policy modules.

## 2. Domain Calculation Files

Calculation methodologies are organized into four domain-specific files:

| File | Contents |
| --- | --- |
| [calculations_water.md](calculations_water.md) | Water system calculations: groundwater pumping energy, desalination energy (BWRO), conveyance energy, irrigation pressurization, irrigation water demand, storage dynamics, water use efficiency, self-sufficiency, allocation policy notes, aquifer depletion, aquifer drawdown feedback, days without municipal, storage utilization, demand vs delivery |
| [calculations_energy.md](calculations_energy.md) | Energy system calculations: PV power generation, wind power generation, battery storage dynamics, backup generator fuel consumption, energy dispatch (load balance), total energy demand, total renewable generation, grid import/export, battery throughput, energy self-sufficiency, days without grid, curtailment, blended electricity cost, grid electricity pricing regimes |
| [calculations_crop.md](calculations_crop.md) | Crop growth and yield calculations: crop yield estimation (FAO-33), soil salinity yield reduction (FAO-29), crop growth stages, post-harvest handling losses, processed product output, processing utilization, crop diversity index (Shannon), PV microclimate yield protection (TBD) |
| [calculations_economic.md](calculations_economic.md) | Economic, food processing, and labor calculations: infrastructure financing costs, equipment replacement costs, water cost calculation, tiered municipal water pricing, crop revenue, daily storage cost, debt service, diesel fuel cost, fertilizer/input cost (TBD), processed product revenue, grid export revenue, total gross revenue, total operating expense, operating margin, cost volatility, revenue concentration, net farm income, payback period, ROI, IRR, NPV, inflation/real-vs-nominal, debt-to-revenue ratio, cash reserves, cash reserve adequacy, processing capacity, processing energy requirements, labor event model, wage rates, FTE calculation, peak labor demand |

## 3. Resilience and Monte Carlo Calculations

> **Status: Implemented** — `src/simulation/monte_carlo.py` provides a full Monte Carlo runner. `src/simulation/sensitivity.py` provides one-at-a-time sensitivity analysis. Both use the simulation engine and metrics pipeline. Some resilience metrics (Gini, maximum drawdown, crop failure probability) are defined conceptually below but not yet computed.

### Monte Carlo Simulation Framework

> **Implemented:** `src/simulation/monte_carlo.py:run_monte_carlo()`. Supports configurable N runs, random seed, and per-parameter coefficient of variation overrides. CLI: `python -m src.simulation.monte_carlo <scenario.yaml> [n_runs]`

**Purpose:** Evaluate community survivability under stochastic conditions by running many simulation instances with randomized parameters

**Algorithm (as implemented):**

```
For run = 1 to N_runs:
  1. Sample price multipliers from N(1.0, CV) for each parameter, floored at 0.5
  2. Sample yield_factor from N(base, base × CV) per farm, floored at 0.1
  3. Deep-copy scenario, apply sampled yield factors
  4. Create SimulationDataLoader with sampled price_multipliers
  5. Run full simulation: run_simulation(scenario, data_loader)
  6. Compute all metrics: compute_all_metrics(state, data_loader, scenario)
  7. Extract outcomes: total revenue, yield, water cost, net income, NPV, cash reserves, self-sufficiency

Aggregate via compute_monte_carlo_summary():
  - Survival rate, income percentiles, NPV percentiles, P(negative income)
```

**Default stochastic parameters (coefficient of variation):**

| Parameter | CV | Notes |
| --- | --- | --- |
| municipal_water | 0.15 | ±15% water price volatility |
| electricity | 0.20 | ±20% electricity price volatility |
| diesel | 0.25 | ±25% diesel price volatility (global oil) |
| fertilizer | 0.15 | ±15% fertilizer cost volatility |
| crop_tomato | 0.25 | ±25% crop price volatility |
| crop_potato | 0.20 |  |
| crop_onion | 0.20 |  |
| crop_kale | 0.15 |  |
| crop_cucumber | 0.25 |  |
| yield_factor | 0.10 | ±10% yield variation (weather, pests) |

**Sampling method:** Normal distribution with mean 1.0 and standard deviation = CV. Multipliers floored at 0.5 to prevent unrealistically low values. Yield factors floored at 0.1.

**Output from \****`compute_monte_carlo_summary()`**\*\*:**

- `n_runs`: Number of runs executed
- `survival_rate_pct`: % of runs with final cash reserves >= 0
- `probability_of_negative_income_pct`: % of runs with negative average annual income
- `avg_net_income_usd`, `std_net_income_usd`: Mean and std of annual net income across runs
- `worst_case_income_usd`: 5th percentile annual income
- `net_income_percentiles`: {p5, p25, p50, p75, p95}
- `npv_percentiles`: {p5, p25, p50, p75, p95}
- `elapsed_seconds`: Total computation time

**Not yet implemented:**

- Weather scenario variation (currently all runs use the same weather time-series; price and yield are varied)
- Equipment failure events (random outage days)
- Correlation structure between parameters (all sampled independently)
- Convergence testing (no automatic check for statistical stability)

### Survival Rate

**Formula:**

```
Survival_rate = count(runs where Cash(t) ≥ 0 for all t) / N_runs × 100
```

### Probability of Crop Failure

**Formula:**

```
P_crop_failure = count(runs with at least one season where yield_loss > 50%) / N_runs × 100
```

### Probability of Insolvency

**Formula:**

```
P_insolvency = count(runs where Cash(t) < 0 for any t) / N_runs × 100
P_insolvency = 100 - Survival_rate
```

### Median Years to Insolvency

**Formula:**

```
Among runs where insolvency occurs:
  Years_to_insolvency(run) = min(t) such that Cash(t) < 0
  Median_years = median(Years_to_insolvency)
```

### Worst-Case Net Income

**Formula:**

```
Worst_case_income = percentile_5(annual_net_income)  across all runs
```

### Net Income Distribution

**Formula:**

```
Income_percentiles = percentile([5, 25, 50, 75, 95], annual_net_income)  across all runs
```

### Income Inequality (Gini Coefficient)

**Purpose:** Measure spread of outcomes across farms within a single run

**Formula:**

```
Gini = (Σ_i Σ_j |income_i - income_j|) / (2 × n² × μ_income)
```

**Where:**

- n: Number of farms
- income_i: Net income of farm i
- μ_income: Mean farm income

**Output:** Gini coefficient (0 = perfect equality, 1 = maximum inequality)

### Maximum Drawdown

**Formula:**

```
Drawdown = max(Peak_cash - Trough_cash)  over all peak-to-trough sequences
```

**Where:**

- Peak: Local maximum of cumulative cash reserves
- Trough: Subsequent local minimum before cash exceeds previous peak

### Sensitivity Analysis

> **Status: Implemented** — `src/simulation/sensitivity.py:run_sensitivity_analysis()`. One-at-a-time price perturbation of 10 parameters at ±20%. Full tornado charts are generated in `results.py` plotting. Breakeven thresholds are future work.

**Purpose:** Identify which input prices have the greatest impact on net farm income

**Algorithm (as implemented):**

```
1. Run base case simulation (no perturbation) → base_income
2. For each parameter P in [10 parameters]:
   a. Run simulation with P × 0.80 → low_income
   b. Run simulation with P × 1.20 → high_income
   c. Record: low_delta = low_income - base_income
              high_delta = high_income - base_income
              total_swing = |high_delta| + |low_delta|
3. Rank parameters by total_swing
```

**Parameters tested:**

| Parameter | Label |
| --- | --- |
| `municipal_water` | Municipal Water Price |
| `electricity` | Grid Electricity Price |
| `diesel` | Diesel Fuel Price |
| `fertilizer` | Fertilizer Cost |
| `labor` | Labor Cost |
| `crop_tomato` | Tomato Price |
| `crop_potato` | Potato Price |
| `crop_onion` | Onion Price |
| `crop_kale` | Kale Price |
| `crop_cucumber` | Cucumber Price |

**Output:** Dict with `base_income` and per-parameter `{label, low_income, high_income, low_delta, high_delta, total_swing}`. Results visualized as a tornado chart (Plot 6 in `metrics_and_reporting.md`).

**Implementation detail:** Price perturbation is applied via the `SimulationDataLoader(price_multipliers={param: multiplier})` mechanism, which scales the relevant price series before the simulation consumes them. Each perturbation requires a full simulation run (21 total: 1 base + 2 × 10 parameters).

**Not yet implemented:**

- Breakeven thresholds (binary search for critical parameter values)
- Multi-parameter interaction effects
- Non-price parameter sensitivity (infrastructure sizing, policy selection)
- Monte Carlo-based sensitivity ranking (Sobol indices or similar)

## 4. Units and Conversions

### Water

- Volume: m³ (cubic meters)
- Flow rate: m³/day
- Pressure: Pa (Pascals) or bar
- TDS: ppm (parts per million) or mg/L
- Conversion: 1 m³ = 1,000 liters

### Energy

- Power: kW (kilowatts)
- Energy: kWh (kilowatt-hours)
- Capacity: kWh (battery), kW (generation/load)
- Conversion: 1 kWh = 3.6 MJ

### Agriculture

- Area: ha (hectares)
- Yield: kg/ha or tonnes/ha
- Water use: m³/ha
- Conversion: 1 ha = 10,000 m²

### Currency

- Primary: USD
- Alternative: EGP (Egyptian Pounds)
- Conversion: Use historical exchange rates from data files

## 5. References

### Water and Irrigation

- Allen, R.G., Pereira, L.S., Raes, D., & Smith, M. (1998). Crop evapotranspiration: Guidelines for computing crop water requirements. FAO Irrigation and Drainage Paper 56.
- Ayers, R.S., & Westcot, D.W. (1985). Water quality for agriculture. FAO Irrigation and Drainage Paper 29 Rev.1.
- Doorenbos, J., & Kassam, A.H. (1979). Yield response to water. FAO Irrigation and Drainage Paper 33.
- Maas, E.V., & Hoffman, G.J. (1977). Crop salt tolerance — current assessment. Journal of the Irrigation and Drainage Division, 103(2), 115-134.

### Desalination

- Voutchkov, N. (2018). Energy use for membrane seawater desalination – current status and trends. Desalination, 431, 2-14.
- Ettouney, H., & Wilf, M. (2009). Commercial desalination technologies. In Desalination: Water from Water (pp. 77-144).

### Agri-PV

- Barron-Gafford, G.A., et al. (2019). Agrivoltaics provide mutual benefits across the food-energy-water nexus in drylands. Nature Sustainability, 2, 848-855.
- Dupraz, C., et al. (2011). Combining solar photovoltaic panels and food crops for optimising land use: Towards new agrivoltaic schemes. Renewable Energy, 36(10), 2725-2732.
- Marrou, H., et al. (2013). Productivity and radiation use efficiency of lettuces grown in the partial shade of photovoltaic panels. European Journal of Agronomy, 44, 54-66.
- Weselek, A., et al. (2019). Agrophotovoltaic systems: Applications, challenges, and opportunities. A review. Agronomy for Sustainable Development, 39, 35.

### Energy Systems

- IEC 61400-1: Wind turbines design standards
- IEC 61215: Crystalline silicon terrestrial photovoltaic modules — Design qualification and type approval
- Jordan, D.C., & Kurtz, S.R. (2013). Photovoltaic degradation rates — An analytical review. Progress in Photovoltaics, 21(1), 12-29.
- NREL PVWatts Calculator documentation
- Stull, R.B. (1988). An Introduction to Boundary Layer Meteorology. Kluwer Academic Publishers.
- System Advisor Model (SAM) technical documentation

### Diesel Generators

- Barley, C.D., & Winn, C.B. (1996). Optimal dispatch strategy in remote hybrid power systems. Solar Energy, 58(4-6), 165-179.
- HOMER Energy documentation — Generator fuel curve modeling

### Battery Storage

- BloombergNEF Lithium-Ion Battery Price Survey (annual)
- LFP calendar and cycle aging data from manufacturer datasheets (CATL, BYD)

### Economic Methods

- Standard financial formulas for NPV, IRR, amortization
- Egyptian water pricing: HCWW (Holding Company for Water and Wastewater) official tariffs
