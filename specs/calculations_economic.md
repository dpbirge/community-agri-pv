# Economic, Food Processing, and Labor Calculations

Extracted from the consolidated calculations specification. For other domain calculations see: [calculations_water.md](calculations_water.md), [calculations_energy.md](calculations_energy.md), [calculations_crop.md](calculations_crop.md). For the index, units, references, and resilience/Monte Carlo calculations see: [calculations.md](calculations.md).

## 1. Infrastructure Financing Costs

**Purpose:** Calculate annual costs to community for infrastructure based on financing category

**Formula:**

```
Annual_cost = CAPEX_component + OPEX_component

CAPEX_component =
  if has_debt_service:
    Monthly_payment × 12
  else if capex_cost_multiplier > 0:
    (capital_cost × capex_cost_multiplier) / depreciation_years
  else:
    0

OPEX_component = annual_om_cost × opex_cost_multiplier

Monthly_payment = P × [r(1 + r)^n] / [(1 + r)^n - 1]
  where P = capital_cost, r = monthly interest rate, n = months
```

**Parameters by Financing Category:**

| Category | CAPEX Mult. | Debt? | Term (yrs) | Rate | OPEX Mult. |
| --- | --- | --- | --- | --- | --- |
| existing_owned | 0.0 | No | 0 | 0.000 | 1.0 |
| grant_full | 0.0 | No | 0 | 0.000 | 0.0 |
| grant_capex | 0.0 | No | 0 | 0.000 | 1.0 |
| purchased_cash | 1.0 | No | 0 | 0.000 | 1.0 |
| loan_standard | 0.0 | Yes | 10 | 0.060 | 1.0 |
| loan_concessional | 0.0 | Yes | 15 | 0.035 | 1.0 |

**Output:** Annual cost in USD per infrastructure subsystem

**Dependencies:**

- Configuration:`[system].[subsystem].financing_status`
- Parameter file:`data/parameters/economic/financing_profiles-toy.csv`
- Capital costs: From equipment parameter files or capital_costs.csv
- O&M costs: From operating_costs.csv

## 2. Equipment Replacement Costs

**Purpose:** Account for mid-simulation replacement of components with shorter lifespans than the simulation horizon. Critical for any simulation longer than ~5 years.

**Component lifespans and replacement costs:**

| Component | Typical Lifespan | Replacement Cost (% of original CAPEX) | Replacements in 15-yr Sim |
| --- | --- | --- | --- |
| RO membranes | 5-7 years | 30-40% | 2-3 |
| Pumps (submersible) | 10-15 years | 60-80% | 0-1 |
| Drip emitters/lines | 5-10 years | 20-30% of irrigation CAPEX | 1-2 |
| Battery pack | 10-15 years | 50-70% (declining with technology cost curves) | 0-1 |
| PV panels | 25-30 years | N/A (outlasts simulation) | 0 |
| PV inverters | 10-15 years | 15-20% of PV CAPEX | 0-1 |
| Wind turbines | 20-25 years | N/A (outlasts simulation) | 0 |

**Formula:**

```
Replacement_cost(year) = Σ replacement_cost_i   for each component i due for replacement in that year

Annual_replacement_reserve = Σ (replacement_cost_i / lifespan_i)   across all components
                           (sinking fund approach — smooth annual provision)
```

**Sinking fund approach (recommended for planning):**

Rather than modeling lumpy replacement events, provision an annual reserve fund:

```
Annual_reserve_i = replacement_cost_i / lifespan_years_i
Total_annual_reserve = Σ Annual_reserve_i
```

This provides a realistic annual cost that smooths replacement shocks and should be included in Total Operating Expense.

**Dependencies:**

- Parameter file: `data/parameters/economic/equipment_lifespans-toy.csv`
- Capital costs from equipment parameter files
- Replacement cost ratios by component type

**Notes:**

- RO membrane replacement is the most frequent and impactful — at 30-40% of BWRO CAPEX every 5-7 years, it can equal or exceed annual O&M costs
- Battery replacement cost is declining ~8-10%/yr with technology improvements; use year-of-replacement projected cost for accuracy
- For MVP: Use the sinking fund approach as a fixed annual cost adder; for later phases, model discrete replacement events

**Sources:**

- Standard financial amortization formulas
- Typical commercial loan rates: 5-7% annual
- Typical concessional loans (development banks): 2-4% annual
- Equipment depreciation: 10-20 years typical
- RO membrane replacement: Voutchkov (2018); typical BWRO plant operating data
- Battery replacement: BloombergNEF Lithium-Ion Battery Price Survey (annual)

## 3. Water Cost Calculation

**Purpose:** Calculate daily water costs based on source and pricing regime

**Groundwater Cost (full system):**

```
Cost_gw [USD/day] = (E_pump [kWh/m3] + E_convey [kWh/m3] + E_desal [kWh/m3])
                  × electricity_price [USD/kWh] × volume_m3 [m3]
                  + O&M_cost [USD/day]
```

**Municipal Water Cost:**

```
Cost_municipal [USD/day] = volume_m3 [m3] × price_per_m3 [USD/m3] (tier, regime)
```

**Parameters:**

- `electricity_price [USD/kWh]`: Grid electricity price from pricing data
- `price_per_m3 [USD/m3]`: Municipal water price from configuration (resolved by consumer type)
- O&M costs [USD/day] from parameter files

**Output:** Daily water cost in USD

**Dependencies:**

- Configuration: `water_pricing.municipal_source`
- Configuration: `water_pricing.agricultural.pricing_regime` [subsidized, unsubsidized] (for farm water demands)
- Configuration: `water_pricing.community.pricing_regime` [subsidized, unsubsidized] (for household/facility water demands)
- Price data: `data/prices/electricity/historical_grid_electricity_prices-research.csv`
- Price data: `data/prices/water/historical_municipal_water_prices-research.csv`

**Note:** Water pricing uses dual agricultural/community regimes configured independently. The simulation resolves the applicable regime based on consumer type before passing the price to the water policy. See `structure.md` Pricing Configuration for the canonical schema.

**Sources:**

- Egyptian HCWW tiered water pricing (Egyptian HCWW tariff documentation — research file pending)
- Desalination cost studies for Egypt (Ettouney & Wilf, 2009)

## 4. Tiered Municipal Water Pricing

**Purpose:** Calculate municipal water costs under Egyptian-style progressive bracket pricing, where the per-unit price increases with cumulative monthly consumption

> **MVP implementation note:** This feature is fully implemented in `data_loader.py` (`calculate_tiered_cost`, `get_marginal_tier_price`) but not yet documented in the original calculations spec. The implementation follows the Egyptian HCWW (Holding Company for Water and Wastewater) tiered pricing structure.

**Methodology:**

Each unit of consumption is charged at the rate for the bracket it falls into, based on cumulative monthly consumption:

```
For each consumption event within a billing period:
  1. Determine current position = cumulative_consumption
  2. For each tier bracket [min_units, max_units, price_per_unit]:
     - Calculate units falling in this bracket
     - Add units × price_per_unit to total cost
  3. Apply wastewater surcharge if configured:
     total_cost += total_cost × (wastewater_surcharge_pct / 100)
```

**Key functions:**

- `calculate_tiered_cost(consumption, cumulative_consumption, tier_config)` — Returns total cost, effective average cost per unit, tier breakdown, and marginal tier number
- `get_marginal_tier_price(cumulative_consumption, tier_config)` — Returns the price for the *next* unit of consumption. Used by water allocation policies for cost comparison decisions (e.g., `cheapest_source` comparing GW cost vs marginal municipal cost)

**Example (Egyptian-style tiers):**

```
Tier 1:  0-10 m³/month  → 0.65 EGP/m³
Tier 2: 11-20 m³/month  → 1.60 EGP/m³
Tier 3: 21-40 m³/month  → 2.75 EGP/m³
Tier 4:   >40 m³/month  → 4.50 EGP/m³

If cumulative = 8 m³ and new consumption = 5 m³:
  - 2 m³ at Tier 1 (0.65) = 1.30 EGP
  - 3 m³ at Tier 2 (1.60) = 4.80 EGP
  - Total: 6.10 EGP, effective rate: 1.22 EGP/m³
  - Marginal tier: 2
```

**Wastewater surcharge:** An additional percentage surcharge applied to the total water cost, representing wastewater treatment fees collected by HCWW alongside water tariffs.

**Dependencies:**

- Configuration: `water_pricing.community.subsidized.tier_pricing` (bracket definitions for community consumers only)
- Configuration: `water_pricing.community.subsidized.wastewater_surcharge_pct` (surcharge on community tiered water bills)

> **Note:** Tiered pricing applies to community water consumption only (households and community buildings). Agricultural water uses flat-rate pricing (subsidized or unsubsidized) with optional annual escalation. See simulation_flow.md Section 4.3 for the full price resolution logic by consumer type.

**Sources:**

- Egyptian HCWW official tariff schedules (Egyptian HCWW tariff documentation — research file pending)

## 5. Crop Revenue Calculation

**Purpose:** Calculate revenue from crop sales across all product types

**Fresh Crop Revenue:**

```
Fresh_revenue [USD] = fresh_output_kg [kg] × fresh_price_per_kg [USD/kg]
```

`fresh_output_kg` already reflects both the upstream handling loss (see [calculations_crop.md](calculations_crop.md) Post-Harvest Handling Losses) and the processing weight loss (0% for fresh). No further loss deduction at the revenue stage.

**Total Crop Revenue (unified formula across all product types):**

```
Total_revenue [USD] = Σ (product_kg(product_type) × price_per_kg(product_type))
```

Where `product_type` is one of [fresh, packaged, canned, dried], and `product_kg` is the output quantity AFTER both the upstream handling loss and the processing weight loss (see [calculations_crop.md](calculations_crop.md) Processed Product Output). This avoids double counting: the handling loss is applied once before the food policy split, then each fraction undergoes processing weight loss, and the resulting product weight is multiplied by the product-type-specific price.

**Parameters:**

- `fresh_output_kg [kg]`: Fresh fraction of harvest after handling loss and processing weight loss (0% for fresh)
- `product_kg [kg]`: Output kg per product type after handling loss and processing weight loss
- `price_per_kg [USD/kg]`: Per-product-type price from historical price data

**Output:** Revenue in USD per crop per season (fresh and processed combined)

**Dependencies:**

- Price data: `data/prices/crops/historical_{crop}_prices-research.csv` (per-crop fresh prices, e.g., `historical_tomato_prices-research.csv`)
- Processing data: `data/prices/processed/historical_{product}_prices-toy.csv` (per-product processed prices, e.g., `historical_dried_tomato_prices-toy.csv`)
- Processing specs: `data/parameters/crops/processing_specs-toy.csv` (weight loss, value multipliers)

**Assumptions:**

- For MVP: No inventory or storage costs
- Future: Add processing costs, storage costs, market timing strategies

## 6. Daily Storage Cost

**Purpose:** Calculate the daily cost of holding processed food inventory in storage. Inventory holding cost is a material operating expense that accrues every day a product remains unsold.

**Formula:**

```
daily_storage_cost [USD/day] = SUM over all tranches in farm_storage:
    tranche.kg x storage_cost_per_kg_per_day(tranche.product_type)
```

Where each tranche is a StorageTranche as defined in simulation_flow.md Section 4.7. The storage cost rate is looked up by product_type from the parameter file.

**Storage cost rates (from `food_storage_costs-toy.csv`):**

| Product Type | Ambient (USD/kg/day) | Climate Controlled (USD/kg/day) |
|---|---|---|
| fresh | 0.008 | 0.015 |
| packaged | 0.004 | 0.008 |
| canned | 0.001 | 0.002 |
| dried | 0.001 | 0.002 |

For MVP, use ambient storage rates for all product types. Climate-controlled rates apply to fresh produce in future scenarios with cold chain infrastructure.

**Integration with daily accounting:**

Daily storage cost is deducted in Step 7 of the simulation loop (Daily Accounting) as part of the daily cost aggregation:

```
daily_costs = water_cost + energy_cost + daily_storage_cost + daily_labor_cost + daily_debt_service
```

**Integration with Total OPEX:**

```
Annual_storage_cost = SUM(daily_storage_cost) over all days in year
Total_OPEX += Annual_storage_cost
```

**Output:** daily_storage_cost in USD/day per farm; annual_storage_cost in USD/yr per farm

**Dependencies:**

- Parameter file: `data/parameters/crops/food_storage_costs-toy.csv` (via registry `crops.storage_costs`)
- Simulation state: farm_storage inventory (list of StorageTranches per farm)

**Notes:**

- Fresh produce has the highest daily holding cost because it requires rapid turnover or cold chain
- Shelf-stable products (canned, dried) are cheap to store, which is part of their economic value proposition
- Storage costs incentivize timely sales and penalize excessive hoarding

## 7. Debt Service Calculation

**Purpose:** Calculate monthly loan payments

> **MVP simplification:** Debt service is fixed monthly payments per financing profile. No accelerated repayment or debt pay-down policies in MVP.

**Formula (fixed-rate amortization):**

```
Payment = P × [r(1 + r)^n] / [(1 + r)^n - 1]
```

**Parameters:**

- P: Principal amount
- r: Monthly interest rate = annual_rate / 12
- n: Number of payments = term_years × 12

**Output:** Monthly payment in USD

**Dependencies:**

- Configuration: `[system].[subsystem].financing_status` — per-subsystem financing category (determines whether debt service applies)
- Parameter file: `data/parameters/economic/financing_profiles-toy.csv` — contains principal amounts, loan terms, and interest rates per financing profile

> **MVP simplification:** Debt service is fixed monthly payments per financing profile. No accelerated repayment or debt pay-down policies in MVP. There is no single `economics.debt` configuration — debt parameters are resolved per subsystem from `financing_status` and `financing_profiles-toy.csv`.

## 8. Diesel Fuel Cost

**Purpose:** Calculate cost of diesel fuel for backup generator operation

**Formula:**

```
Diesel_cost(t) = Fuel(t) × diesel_price_per_L(t)
Diesel_cost_yr = Σ Diesel_cost(t)
Diesel_cost_per_kwh = Diesel_cost_yr / Generator_output_yr
```

**Dependencies:**

- Fuel consumption from backup generator calculation (see [calculations_energy.md](calculations_energy.md) Backup Generator Fuel Consumption)
- Price data:`data/prices/diesel/historical_diesel_prices-research.csv`

**Output:** $/yr total; $/L effective price; $/kWh marginal generation cost

## 9. Fertilizer and Input Cost

> **Status: TBD** — Input cost model and data sources not yet defined.

**Purpose:** Calculate cost of agricultural inputs (fertilizer, seed, chemicals) per hectare

**Conceptual formula:**

```
Input_cost_ha = fertilizer_cost_ha + seed_cost_ha + chemical_cost_ha
Input_cost_total = Σ (Input_cost_ha × farm_area_ha)  across all farms
```

**Missing parameters:**

- Per-crop fertilizer requirements (kg/ha by nutrient: N, P, K)
- Fertilizer prices ($/kg by type)
- Seed costs per hectare per crop
- Pesticide/herbicide costs per hectare per crop

**Notes:**

- For MVP, may use a flat per-hectare input cost rate from literature
- Future: Itemized input tracking with seasonal price variation

## 10. Processed Product Revenue

**Purpose:** Calculate revenue from processed crop products

**Formula:**

```
Processed_revenue = Σ (processed_output_kg × processed_price_per_kg)  by product type

processed_price_per_kg = fresh_price_per_kg × value_add_multiplier
```

**Where:**

- `processed_output_kg`: From processed product output calculation (see [calculations_crop.md](calculations_crop.md) Processed Product Output)
- `fresh_price_per_kg`: From historical crop price data
- `value_add_multiplier`: From`data/parameters/crops/processing_specs-toy.csv`

**Dependencies:**

- Processed product output (see [calculations_crop.md](calculations_crop.md))
- Price data: `data/prices/crops/historical_{crop}_prices-research.csv` (per-crop base fresh prices)
- Price data: `data/prices/processed/historical_{product}_prices-toy.csv` (per-product processed prices, or derived from value_add_multiplier)
- Parameter file:`data/parameters/crops/processing_specs-toy.csv`

**Notes:**

- Processed products command higher per-kg prices but have lower yield-to-product weight ratios
- Net revenue effect:`value_add_multiplier × (1 - weight_loss_pct/100)` relative to selling fresh
  - Packaged: 1.25 × 0.97 = 1.21× (21% more revenue per kg harvested)
  - Canned: 1.80 × 0.85 = 1.53× (53% more revenue)
  - Dried: 3.50 × 0.12 = 0.42× for tomato (58%*less* revenue per kg harvested, but much longer shelf life)
- Revenue timing differs from fresh sales (processed products can be stored and sold strategically)

## 11. Grid Electricity Export Revenue

**Purpose:** Calculate revenue from selling surplus electricity to the grid

**Formula:**

```
Export_revenue_yr = Σ Grid_export(t) × export_price(t) × Δt  [$/yr]
```

**Dependencies:**

- Grid export volume from energy dispatch (see [calculations_energy.md](calculations_energy.md) Energy Dispatch)
- Export price: may differ from import price (feed-in tariff or wholesale rate)
- Configuration: whether grid export is enabled

**Notes:**

- Export may not be available in all scenarios (depends on grid connection and regulatory regime)
- Egyptian net metering policies are evolving; export price is often below retail import price

## 12. Total Gross Revenue

**Purpose:** Aggregate all revenue streams

**Formula:**

```
Total_gross_revenue = Fresh_crop_revenue + Processed_product_revenue + Grid_export_revenue
```

**Output:** $/yr

## 13. Total Operating Expense

**Purpose:** Aggregate all operating costs

**Formula:**

```
Total_opex = Infrastructure_OM + Debt_service + Equipment_replacement_reserve
           + Labor_costs + Input_costs + Water_costs + Energy_costs + Diesel_costs

Infrastructure_OM = Σ OPEX_component  across all subsystems (water, energy, processing)
Equipment_replacement_reserve = Σ Annual_reserve_i  (see Equipment Replacement Costs)
```

**Output:** $/yr

**Notes:**

- Water and energy costs that are internally produced (groundwater, renewables) include only O&M and debt service — not market price
- Purchased water (municipal) and purchased energy (grid) are at market price

## 14. Operating Margin

**Purpose:** Measure profitability as a fraction of revenue

**Formula:**

```
Operating_margin_pct = ((Total_gross_revenue - Total_opex) / Total_gross_revenue) × 100
```

**Output:** Percentage (can be negative if costs exceed revenue)

## 15. Cost Volatility

**Purpose:** Measure month-to-month variability in operating costs as a resilience indicator

**Formula:**

```
CV = σ(monthly_opex) / μ(monthly_opex)
```

**Where:**

- σ: Standard deviation of monthly operating expenses over the year
- μ: Mean monthly operating expense over the year

**Output:** Coefficient of variation (dimensionless, lower = more stable)

**Notes:**

- This is a*(resilience)* metric
- High CV indicates unpredictable cost structure, making budgeting difficult
- Infrastructure ownership typically reduces CV by converting variable energy/water costs into fixed debt service + O&M

## 16. Revenue Concentration

**Purpose:** Measure how dependent the farm's revenue is on a single dominant crop. High concentration indicates vulnerability to price or yield shocks for that crop.

**Formula:**

```
Revenue_concentration_pct = (max(crop_revenue_i) / Σ crop_revenue_i) × 100
```

**Output:** Percentage (0–100%). Lower values indicate more diversified revenue.

**Notes:**

- This is a *(resilience)* metric — complements the Crop Diversity Index (see [calculations_crop.md](calculations_crop.md)) which measures area-based diversity
- Implemented in `src/simulation/metrics.py` as `compute_revenue_concentration()`
- Also reports `dominant_crop`: the crop name with the highest revenue
- 100% concentration = monoculture revenue; for 5 equal crops, minimum concentration = 20%

## 17. Net Farm Income

**Purpose:** Calculate bottom-line profitability

**Formula:**

```
Net_income = Total_gross_revenue - Total_opex
```

**Per-farm variant:**

```
Net_income_farm_i = Revenue_farm_i - (allocated_opex_farm_i)
```

**Output:** $/yr (can be negative)

**Notes:**

- Cost allocation to individual farms depends on the community cost-sharing policy (e.g., proportional to area, equal split, usage-based)
- Community-level net income = sum of all farm net incomes

## 18. Payback Period

**Purpose:** Time required for cumulative net cash flow to recover infrastructure investment

**Formula:**

```
Payback_years = min(t) such that Σ(Net_income(y), y=1..t) ≥ Total_CAPEX
```

**Simplified (uniform income):**

```
Payback_years ≈ Total_CAPEX / avg_annual_net_income
```

**Output:** Years (fractional)

**Notes:**

- Only meaningful for scenarios with significant capital investment
- For grant-funded infrastructure, payback is effectively zero

## 19. Return on Investment

**Purpose:** Annualized return relative to total investment

**Formula (simple ROI):**

```
ROI_pct = (avg_annual_net_income / Total_CAPEX) × 100
```

**Output:** Percentage per year

**Limitation:** Simple ROI does not account for the time value of money — a project returning $100K/year starting in year 1 scores identically to one starting in year 5. Use IRR (below) for time-sensitive investment comparison.

## 20. Internal Rate of Return (IRR)

**Purpose:** The discount rate at which the net present value of all cash flows equals zero — provides a single rate-of-return metric that accounts for the timing of cash flows

**Formula:**

```
0 = -Initial_CAPEX + Σ (Net_income(t) / (1 + IRR)^t)  for t = 1 to N
```

Solved numerically (no closed-form solution). Standard implementation uses Newton-Raphson or bisection method.

**Interpretation:**

- IRR > discount_rate → Project creates value (NPV > 0)
- IRR < discount_rate → Project destroys value (NPV < 0)
- IRR = discount_rate → Breakeven (NPV = 0)
- Typical thresholds: IRR > 8-12% for commercial viability in developing economies; lower thresholds (5-8%) acceptable for community/development projects

**Output:** Percentage (annualized)

**Notes:**

- IRR may not exist or may have multiple solutions if cash flows change sign more than once (e.g., major replacement cost in mid-simulation). In such cases, use Modified IRR (MIRR) or rely on NPV
- For grant-funded projects with zero CAPEX, IRR is undefined (infinite return on zero investment) — use NPV and ROI instead
- IRR and NPV should always be reported together; IRR provides intuitive comparison across project sizes while NPV gives absolute value

## 21. Net Present Value

**Purpose:** Discounted value of all future cash flows from community operations

**Formula:**

```
NPV = Σ (Net_income(t) / (1 + r)^t)  for t = 1 to N
     - Initial_CAPEX
```

**Parameters:**

- `r`: Discount rate (from config:`economics.discount_rate`)
- `N`: Number of simulation years
- `Net_income(t)`: Net income in year t

**Output:** NPV in USD (positive = value-creating investment)

## 22. Inflation and Real vs Nominal Values

**Purpose:** Ensure economic projections over multi-year simulations are not distorted by ignoring the time-value of money in prices and costs

**Approach:** The simulation should operate in one of two consistent frameworks:

**Option A — Real (constant-year) terms (recommended for MVP):**

All prices, costs, and revenues are held constant at base-year values. The discount rate used in NPV must be a *real* discount rate (net of inflation):

```
r_real = (1 + r_nominal) / (1 + inflation_rate) - 1
```

Approximate: `r_real ≈ r_nominal - inflation_rate`

This is the simpler approach and is appropriate when the goal is to compare infrastructure configurations rather than forecast nominal cash flows.

**Option B — Nominal terms (future implementation):**

Prices and costs escalate annually at category-specific rates:

```
Price(year) = Price_base × (1 + escalation_rate) ^ year
```

Typical escalation rates for Egypt:

- General inflation: 5-15%/yr (historically volatile; 10-30% in 2022-2024)
- Electricity tariffs: May increase faster than general inflation due to subsidy reform
- Diesel prices: Tied to global oil markets plus subsidy removal
- Agricultural input costs: Roughly track general inflation
- Crop prices: May lag or lead inflation depending on market dynamics
- Labor costs: Roughly track inflation in the medium term

With nominal prices, use the nominal discount rate for NPV.

**Current assumption:** The model uses **real (constant-year) terms**. All prices in data files are base-year values and are not escalated. The discount rate in `economics.discount_rate` should be interpreted as a real rate (typically 3-8% for infrastructure projects in developing economies, vs 8-15% nominal).

**Parameters:**

- Configuration: `economics.discount_rate` — must be real rate if using Option A
- Configuration (future): `economics.inflation_rate`, per-category escalation rates

**Notes:**

- Failing to specify real-vs-nominal is one of the most common errors in long-range infrastructure planning models — it can distort NPV by 30-50% over a 15-year horizon
- Even in real terms, *relative* price changes matter (e.g., electricity prices rising faster than crop prices) — these can be modeled as real escalation differentials without full nominal modeling

## 23. Debt-to-Revenue Ratio

**Purpose:** Measure financial leverage relative to income

**Formula:**

```
Debt_to_revenue = Total_annual_debt_service / Total_gross_revenue
```

**Output:** Ratio (dimensionless). Values > 0.30 typically indicate high financial stress.

## 24. Cash Reserves

**Purpose:** Track community bank balance over time

**Formula:**

```
Cash(t+1) = Cash(t) + Revenue(t) - Expenses(t)
Cash(0) = Σ starting_capital_usd  across all farms
```

**Output:** USD balance at end of each period

**Notes:**

- Insolvency occurs when Cash(t) < 0
- Used as input to Monte Carlo survivability analysis

## 25. Cash Reserve Adequacy

**Purpose:** Measure how many months of expenses the community can cover from reserves

**Formula:**

```
Adequacy_months = Cash_reserves / avg_monthly_opex
```

**Output:** Months of runway

**Notes:**

- This is a*(resilience)* metric
- Values < 3 months indicate high vulnerability to income disruption
- Values > 12 months indicate strong financial buffer

---

## 26. Processing Capacity

**Purpose:** Calculate daily processing throughput

**Formula:**

```
Capacity = Σ(equipment_capacity_i × fraction_i × availability)
```

**Parameters:**

- equipment_capacity_i: From equipment parameter files
- fraction_i: Equipment mix fraction (from config)
- availability: Equipment uptime = 0.90 (90%)

**Output:** Daily processing capacity in kg/day

**Dependencies:**

- Configuration:`food_processing_system.[type].equipment`
- Parameter file:`data/parameters/equipment/processing_equipment-toy.csv`

## 27. Processing Energy Requirements

**Purpose:** Calculate energy needed for food processing operations

**Energy by Processing Type:**

- Fresh packaging: 0.05-0.10 kWh/kg (washing, sorting, packaging)
- Drying: 0.5-2.0 kWh/kg (depends on solar vs electric dryer)
- Canning: 0.3-0.5 kWh/kg (retort processing)
- Packaging: 0.02-0.05 kWh/kg (vacuum sealing, labeling)

**Dependencies:**

- Parameter file:`data/parameters/equipment/processing_equipment-toy.csv`
- Configuration:`food_processing_system.[type].equipment`

**Sources:**

- Industrial food processing energy benchmarks
- Solar dryer performance studies for arid climates

---

## 28. Labor Calculations

**Purpose:** Calculate daily labor costs using a per-event model. Labor hours are assigned to discrete agricultural events tied to the crop lifecycle, infrastructure maintenance, and management activities. This provides physically accurate daily labor demand and cost allocation rather than smoothing annual estimates across all days.

### 28.1 Per-Event Labor Cost Model

Labor demand is driven by events that occur at specific times relative to the crop calendar and operational schedule. Each event has an hours-per-unit requirement, a skill level (which determines wage rate), and a trigger condition that determines when the event occurs.

**Daily labor cost formula:**

```
daily_labor_cost [USD/day] = SUM over all active events on this day:
    event_hours(event, farm) x wage_rate(event.skill_level)
```

### 28.2 Labor Event Categories

Events are organized into five categories: field operations, processing operations, management, infrastructure maintenance, and logistics. All per-unit hours are sourced from `labor_requirements-toy.csv`.

#### 28.2.1 Field Operations (Per Farm, Per Crop)

Field labor events are tied to the crop lifecycle. Each event occurs at a specific time relative to the planting date and spans a defined number of days.

**Labor event timing table (days relative to planting date):**

| Event | Trigger | Duration (days) | Hours/ha | Skill Level | Notes |
| --- | --- | --- | --- | --- | --- |
| field_preparation | planting_date - 14 | 5 | 20 | skilled | Tillage, bed forming, drip line installation |
| planting | planting_date | 3-5 | 80-210 | unskilled | Direct seed (80) or transplant (210); crop-dependent |
| fertilizer_application | planting + 21, +42, +63 | 1 each | 35 | semi-skilled | 3 applications at 3-week intervals |
| irrigation_management | planting through harvest | continuous | 40/season | semi-skilled | Drip system checks, scheduling adjustments |
| pest_scouting | planting + 14 through harvest | weekly | 25/season | semi-skilled | Weekly field walks; hours spread across season |
| weeding | planting + 14, +35, +56 | 2 each | 150/season | unskilled | 3 rounds of manual weeding |
| harvesting | harvest_date | 3-5 | see table | unskilled | Spread over multiple days; crop-specific hours |
| processing | harvest_date + 1 | 1-3 | per-kg rate | semi-skilled | Immediately follows harvest |
| packing_storage | harvest_date + 1 | 1 | per-kg rate | unskilled | Sorting, grading, boxing into storage |

**Crop-specific harvesting hours (per hectare, spread over harvest duration):**

| Crop | Hours/ha | Harvest Duration (days) | Hours/ha/day | Planting Type |
| --- | --- | --- | --- | --- |
| Tomato | 320 | 5 | 64 | transplant |
| Potato | 180 | 3 | 60 | direct_seed |
| Onion | 160 | 3 | 53 | transplant |
| Kale | 280 | 4 | 70 | transplant |
| Cucumber | 350 | 5 | 70 | direct_seed |

**Harvest date** is determined by the crop planting date plus the season length:

```
harvest_date = planting_date + season_length_days

Season lengths (from crop_coefficients-toy.csv):
  tomato:   135 days
  potato:   120 days
  onion:    150 days
  kale:      85 days
  cucumber:  95 days
```

**Daily field labor hours for a given farm on a given day:**

```
daily_field_hours(farm, date) = SUM over all active crops on farm:
    SUM over all events active for that crop on this date:
        event_hours_per_ha / event_duration_days x crop_area_ha
```

Where `crop_area_ha = plantable_area_ha x area_fraction x percent_planted`.

#### 28.2.2 Processing Operations (Per Farm, Harvest Days Only)

Processing labor is event-driven: it occurs only on days when food processing takes place (harvest day + 1 through completion). Hours are calculated from actual throughput.

**Processing labor rates (from `labor_requirements-toy.csv`):**

| Processing Activity | Hours/kg | Skill Level |
| --- | --- | --- |
| canning_preparation | 0.015 | semi-skilled |
| canning_processing | 0.020 | semi-skilled |
| canning_quality_control | 0.005 | skilled |
| packaging_sorting | 0.008 | unskilled |
| packaging_grading | 0.006 | semi-skilled |
| packaging_boxing | 0.004 | unskilled |
| drying_preparation | 0.012 | semi-skilled |
| drying_processing | 0.008 | semi-skilled |

**Total processing hours per pathway:**

```
canning_hours = input_kg x (0.015 + 0.020 + 0.005) = input_kg x 0.040 hrs/kg
packaging_hours = input_kg x (0.008 + 0.006 + 0.004) = input_kg x 0.018 hrs/kg
drying_hours = input_kg x (0.012 + 0.008) = input_kg x 0.020 hrs/kg
fresh_handling_hours = input_kg x 0.018 hrs/kg  (sorting + boxing, no processing step)
```

**Packing/storage labor** applies to all product types entering storage:

```
packing_storage_hours = total_output_kg x 0.018 hrs/kg  (sorting + grading + boxing)
```

#### 28.2.3 Management (Daily, Year-Round)

Management labor occurs every working day regardless of field activity:

| Activity | Hours/day | Skill Level |
| --- | --- | --- |
| management_planning | 4 | skilled |
| management_coordination | 2 | semi-skilled |
| management_sales | 3 | skilled |
| management_administration | 4 | skilled |
| **Total management** | **13** | |

```
daily_management_hours = 13 hrs/day (on working days only; 280 working days/yr)
```

#### 28.2.4 Infrastructure Maintenance (Continuous, Year-Round)

Maintenance labor is distributed evenly across working days:

| Infrastructure | Hours/yr | Unit | Skill Level |
| --- | --- | --- | --- |
| PV systems | 4 hrs/equipment | per panel array | skilled |
| Water treatment (BWRO) | 8 hrs/equipment | per unit | skilled |
| Irrigation systems | 6 hrs/equipment | per zone | semi-skilled |
| Processing equipment | 12 hrs/equipment | per machine | skilled |
| Vehicles | 8 hrs/equipment | per vehicle | skilled |

```
daily_maintenance_hours = total_annual_maintenance_hours / working_days
```

Annual maintenance hours are computed from infrastructure configuration at scenario load time. See `labor_requirements-toy.csv` for aggregate model parameters (`maint_pv`, `maint_wind`, `maint_bwro`, `maint_well`, `maint_battery`, `maint_generator`).

#### 28.2.5 Logistics (Per Event and Continuous)

| Activity | Rate | Unit | Skill Level |
| --- | --- | --- | --- |
| Loading | 0.002 hrs/kg | per kg moved | unskilled |
| Unloading | 0.002 hrs/kg | per kg moved | unskilled |
| Transport | 8 hrs/day | per trip day | semi-skilled |
| Inventory management | 3 hrs/day | daily | semi-skilled |

Logistics loading/unloading labor is triggered on harvest days and sale days. Transport labor is triggered when product is sold (market delivery). Inventory management runs daily when storage is non-empty.

### 28.3 Daily Labor Cost Aggregation

```
daily_labor_hours = daily_field_hours + daily_processing_hours
                  + daily_management_hours + daily_maintenance_hours
                  + daily_logistics_hours

daily_labor_hours *= (1 + admin_overhead)    # admin_overhead = 0.05 (5%)

daily_labor_cost [USD/day] = SUM over all hours by skill level:
    hours_at_skill_level x wage_rate(skill_level)
```

**Wage rates by skill level (from `labor_wages-toy.csv`):**

| Skill Level | Representative Category | USD/hr |
| --- | --- | --- |
| unskilled | field_worker, seasonal_harvester | 1.00-1.10 |
| semi-skilled | field_supervisor, processing_worker | 1.43-1.66 |
| skilled | equipment_operator, manager | 1.99-2.65 |
| blended | weighted average (all categories) | 3.50 |

For MVP, use the blended wage rate of $3.50/hr for all labor categories to simplify daily cost calculation. Per-skill-level costing is a future enhancement for detailed labor reporting.

```
daily_labor_cost_mvp [USD/day] = daily_labor_hours x 3.50
```

### 28.4 FTE and Annual Totals

```
annual_labor_hours = SUM(daily_labor_hours) over all days in year
FTE = annual_labor_hours / 2,240    (8 hrs/day x 280 working days/yr)
annual_labor_cost = SUM(daily_labor_cost) over all days in year
```

**Output:** daily_labor_cost in USD/day per farm; annual_labor_cost in USD/yr per farm; FTE count per year

### 28.5 Peak Labor Demand

**Purpose:** Identify peak daily labor demand for workforce planning.

With the per-event model, peak labor demand is directly observable from the daily labor time series rather than estimated from a multiplier:

```
peak_daily_hours = max(daily_labor_hours) across all days in year
peak_date = date of peak_daily_hours
peak_fte = peak_daily_hours / 8
```

Peak demand typically occurs when harvesting overlaps across multiple crops. Staggered planting dates reduce peak demand by spreading harvest events across the calendar.

### 28.6 Community vs External Labor

**Purpose:** Measure local employment benefit.

**Conceptual formula:**

```
Community_labor_ratio = community_labor_hrs / total_labor_hrs x 100
```

**Missing parameters:**

- Community available labor supply (working-age population x available hours)
- Skill requirements vs community skill profile

### 28.7 Dependencies

- Parameter file: `data/parameters/labor/labor_requirements-toy.csv` (via registry `labor.requirements`)
- Parameter file: `data/parameters/labor/labor_wages-toy.csv` (via registry `labor.wages`)
- Configuration: `farms[].plantable_area_ha` (farm size)
- Configuration: `farms[].crops[].name`, `farms[].crops[].planting_dates` (for event timing)
- Parameter file: `data/parameters/crops/crop_coefficients-toy.csv` (season lengths for harvest date calculation)
- Simulation state: harvest day flag, processing throughput, storage inventory, sale events

### 28.8 Notes

1. The per-event model provides physically accurate daily labor demand. On non-event days (no field work, no processing, no sales), only management, maintenance, and inventory labor are incurred. On harvest days, labor demand spikes due to simultaneous harvesting, processing, packing, and logistics.

2. **CSV gap: storage management labor.** The current `labor_requirements-toy.csv` does not have a dedicated `storage_management` activity row for ongoing labor associated with stored inventory (inspecting product condition, rotating stock, managing climate control). The `logistics_inventory` row (3 hrs/day) partially covers this, but a separate `storage_management` row at approximately 0.001 hrs/kg/day would more accurately model the ongoing labor cost of holding inventory. This should be added to the CSV.

3. **CSV gap: fresh produce handling.** Fresh produce that is not processed still requires washing, sorting, and packing labor. The current CSV has `packaging_sorting`, `packaging_grading`, and `packaging_boxing` rows which apply to all product types including fresh. This is adequate for MVP but a dedicated `fresh_handling` aggregate row (summing to ~0.018 hrs/kg) would improve clarity.

4. **Blended wage rate.** The blended rate of $3.50/hr from `labor_wages-toy.csv` is significantly higher than any individual worker category rate (max $2.65/hr for manager). This suggests the blended rate may include non-wage costs (benefits, insurance, equipment). The per-skill-level rates should be used for future detailed labor reporting; the blended rate is appropriate for MVP total cost estimation.

5. **Harvest spreading.** Harvesting is spread over 3-5 days per crop rather than concentrated on a single day. This reflects the physical reality that manual harvesting of a 5-25 ha crop field requires multiple days of work. The harvest duration per crop is defined in the timing table above.

**Sources:**

- FAO agricultural labor benchmarks for irrigated agriculture in developing countries
- Requirements of Manual Labor for Farm Operations (Gezira, Sudan, 2025) -- adapted for Egyptian conditions
- University of Florida IFAS Extension -- small-farm vegetable production labor studies
- Egyptian Ministry of Manpower minimum wage decrees (2024-2025) for wage rates
