# Inflation and Price Year Alignment Analysis

**Date**: 2026-02-06
**Author**: Code Review
**Status**: Analysis Complete - Recommendations Provided

## Executive Summary

The model currently operates in **real (constant-year) terms** with no inflation adjustment. This creates a temporal mismatch problem:

- **Historical price data** (2015-2024): Tomato prices, diesel, electricity, water - all in nominal USD at historical exchange rates
- **Infrastructure costs** (2024 basis): CAPEX and OPEX from NREL ATB 2024, IRENA 2024, BNEF 2024
- **Simulation period**: Runs from 2015-2020 (configurable)
- **NPV calculations**: Use a discount rate assumed to be "real" (net of inflation)

**The Problem**: When you mix 2015 nominal crop prices with 2024 infrastructure costs and simulate 2015-2020, the economic metrics (NPV, IRR, net income) are distorted because you're comparing values from different price years without adjustment.

## Current Implementation

### 1. Price Data Structure

**Historical crop prices** ([tomato_prices-research.csv](../../data/prices/crops/tomato_prices-research.csv)):
```csv
date,usd_per_kg_farmgate,usd_per_kg_wholesale,usd_per_kg_retail,egp_per_kg_original,usd_egp_exchange_rate
2015-01-01,0.32,0.52,0.91,4.00,7.70
...
2024-01-01,0.33,0.55,0.96,24.95,45.36
```

**Capital costs** ([capital_costs-research.csv](../../data/parameters/costs/capital_costs-research.csv)):
```csv
equipment_type,cost_metric,usd_per_unit,source,year_basis
pv_system_utility_scale,per_kw_ac,1150,NREL Q1 2024,2024
battery_storage_lfp_utility,per_kwh_capacity,165,BNEF 2024,2024
```

### 2. Current Approach (per [calculations.md:1916-1964](../../docs/architecture/calculations.md))

From the documentation:

> **Current assumption:** The model uses **real (constant-year) terms**. All prices in data files are base-year values and are not escalated. The discount rate in `economics.discount_rate` should be interpreted as a real rate (typically 3-8% for infrastructure projects in developing economies, vs 8-15% nominal).

The documentation acknowledges two approaches:

**Option A: Real (Constant-Year) Terms**
- All prices held constant at base-year values
- Discount rate is real (net of inflation): `r_real = (1 + r_nominal) / (1 + inflation_rate) - 1`
- Simple but masks temporal trends

**Option B: Nominal Terms**
- Prices escalate with inflation: `Price(t) = Price(0) × (1 + inflation)^t`
- Discount rate is nominal
- More realistic but requires inflation assumptions

### 3. Implementation Reality

The code **does not implement either option correctly**:

1. **Price data is nominal** (historical values at historical exchange rates)
2. **Infrastructure costs are 2024 values** (single year snapshot)
3. **No inflation adjustment** occurs during simulation
4. **Discount rate treatment unclear** (assumed real but not documented in scenario)

**Simulation flow** ([simulation.py](../../src/simulation/simulation.py)):
```python
# Prices are looked up by date
crop_price = data_loader.get_crop_price(crop_name, harvest_date)
revenue = yield_kg * crop_price  # Uses nominal historical price

# Costs use static 2024 values
infrastructure_costs = estimate_infrastructure_costs(scenario)  # 2024 basis
```

**NPV calculation** ([metrics.py](../../src/simulation/metrics.py)):
```python
# No price adjustment, just discounting
npv = sum(net_income[t] / (1 + discount_rate)**t for t in years)
```

## The Temporal Mismatch Problem

### Scenario: 2015-2020 Simulation

**What happens:**
1. Simulation starts 2015-01-01
2. Farm sells tomatoes at **$0.52/kg wholesale** (2015 price)
3. Farm pays debt service on BWRO system at **$850/m³/day installed** (2024 cost)
4. Net income appears artificially low because:
   - Revenues use 2015 prices (lower)
   - Capital costs use 2024 prices (higher due to 9 years of inflation)

**The distortion:**
- If general inflation averaged 3% from 2015-2024, the 2024 dollar is worth ~1.30× a 2015 dollar
- A BWRO system that cost $650/m³/day in 2015 might cost $850/m³/day in 2024
- But you're comparing 2015 revenue ($0.52/kg tomatoes) against 2024 capital costs ($850/m³/day)

### Egypt-Specific Complication

Egyptian pound devaluation adds complexity:

| Year | EGP/USD | Note |
|------|---------|------|
| 2015 | 7.70 | Pre-float stable period |
| 2017 | 17.83 | Post-float adjustment |
| 2023 | 30.67 | Major devaluation |
| 2024 | 45.36 | Continued devaluation |

**Crop prices in USD** reflect this currency shock - they're NOT purely real prices, they're nominal USD converted at historical exchange rates. The 2024 tomato price ($0.55/kg) is only 6% higher than 2015 ($0.52/kg) in USD terms, but in EGP terms it's 6× higher (4.00 → 24.95).

## Impact on Economic Metrics

### Current Settings ([settings.yaml](../../settings/settings.yaml))

```yaml
simulation:
  start_date: "2015-01-01"
  end_date: "2020-12-31"

economics:
  discount_rate: 0.06  # Assumed to be "real" but not specified
```

### Broken Metrics

1. **NPV**: Underestimated if early-year revenues are nominal (low) but CAPEX is 2024 basis (high)
2. **IRR**: Distorted comparison of cash flows from different price years
3. **Payback period**: Artificially long
4. **Net income**: Year-1 appears worse than Year-6 even if conditions identical
5. **Operating margin**: Meaningless when costs and revenues are in different price years

## Recommended Solutions

### Short-Term: Single Reference Year Approach

**Convert all prices to a common reference year** (recommend 2024 as infrastructure baseline)

1. **Inflate historical prices to 2024**:
   ```python
   # For US-based costs (PV, batteries)
   us_cpi = {2015: 237.0, 2016: 240.0, ..., 2024: 314.0}  # US CPI-U
   price_2024 = price_nominal * (us_cpi[2024] / us_cpi[year])
   ```

2. **For Egyptian crop prices**:
   - Either use EGP-denominated prices + project forward in EGP + convert at current rate
   - OR adjust USD prices using US inflation AND purchasing power parity
   - This is genuinely tricky due to currency devaluation

3. **Simulation operates in 2024-equivalent terms**:
   - All prices expressed as "2024 USD"
   - Discount rate is REAL (net of inflation)
   - Scenario defines: `price_basis_year: 2024`

**Implementation**:
- Create [price_inflation_adjustments.csv](../../data/parameters/economic/price_inflation_adjustments.csv) with year-to-year inflation factors
- Add `adjust_prices_to_reference_year()` in data_loader
- Set `economics.price_basis_year: 2024` in scenarios
- Document assumption clearly

### Medium-Term: Proper Nominal Approach

**Model inflation explicitly during simulation**

1. **Project prices forward with category-specific inflation**:
   ```yaml
   economics:
     inflation:
       general: 0.03  # 3% general inflation
       food_commodities: 0.04  # Food price inflation
       energy: 0.05  # Energy/fuel inflation
       water_utility: 0.035  # Utility inflation
       egp_devaluation: 0.12  # Egyptian pound expected devaluation
   ```

2. **Escalate prices during simulation**:
   ```python
   # At each timestep
   crop_price_t = crop_price_base * (1 + food_inflation)**(year - base_year)
   diesel_price_t = diesel_price_base * (1 + energy_inflation)**(year - base_year)
   ```

3. **Use nominal discount rate for NPV**:
   ```python
   r_nominal = (1 + r_real) * (1 + general_inflation) - 1
   npv = sum(net_income_t / (1 + r_nominal)**t)
   ```

**Advantages**:
- Captures differential inflation across sectors
- Allows scenario analysis of inflation shocks
- More realistic multi-year projections

**Disadvantages**:
- Requires inflation assumptions
- More complex to implement and explain
- Adds uncertainty

### Long-Term: Real Price Projections

**Model real (inflation-adjusted) price trends separately**

For a 2040 simulation:
1. Start with 2024 baseline prices (all in 2024 USD)
2. Project REAL price changes based on structural factors:
   - Renewable energy: -2%/yr (technology learning curves)
   - Fossil fuels: +1%/yr real (depletion, carbon pricing)
   - Food: 0%/yr real (assume productivity offsets demand)
   - Water: +1%/yr real (scarcity)
3. Add general inflation on top for nominal analysis if needed

## Specific Recommendations for This Model

### Phase 1: Fix Current Issues (Immediate)

1. **Document price year assumptions**:
   - Add `price_basis_year: 2024` to scenario metadata
   - Add warning in README: "All costs and prices expressed in 2024 USD"

2. **Create inflation adjustment tool**:
   ```bash
   python data/scripts/adjust_historical_prices_to_2024.py
   ```
   Output: `*_prices-research-real2024.csv` files

3. **Validate consistency**:
   - Verify CAPEX/OPEX all stated as 2024 basis
   - Verify all price CSVs have `year_basis` metadata
   - Create validation test: `test_price_year_consistency()`

### Phase 2: Enable Scenario Comparisons (Next sprint)

4. **Add inflation scenarios**:
   ```yaml
   inflation_scenario: historical  # Options: none, historical, projected
   ```

5. **Support multiple reference years**:
   - Maintain both `*-real2015.csv` and `*-real2024.csv`
   - Let scenarios choose: `price_basis_year: 2024`

### Phase 3: Full Inflation Modeling (Future)

6. **Implement escalation during simulation**:
   - Add `economics.inflation_rates` dict
   - Add `escalate_price(base_price, category, year)` helper
   - Switch to nominal cash flows + nominal discount rate

7. **Separate real vs nominal reporting**:
   - Output both nominal and real metrics
   - Document: "Real values expressed in YYYY USD"

## Data Quality Gaps

### Missing Information

1. **US CPI series 2015-2024**: Need for adjusting US-sourced costs
2. **Egypt CPI series 2015-2024**: Need for Egyptian-sourced prices (if using EGP)
3. **PPP adjustments**: Egypt/US purchasing power parity for cross-country costs
4. **Food price indices**: FAO food price index or Egypt-specific commodity indices

### Data Sources to Add

- **[data/parameters/economic/inflation_indices.csv](../../data/parameters/economic/inflation_indices.csv)**:
  ```csv
  year,us_cpi,egypt_cpi,usd_egp_rate,food_price_index,energy_price_index
  2015,237.0,89.2,7.70,100.0,100.0
  ...
  2024,314.0,412.5,45.36,145.2,189.3
  ```

- **[data/parameters/economic/projected_inflation_rates.csv](../../data/parameters/economic/projected_inflation_rates.csv)**:
  ```csv
  category,annual_rate_pct,source,notes
  general,3.0,IMF Egypt projection 2025-2030,Post-stabilization assumption
  food,4.0,FAO commodity outlook,Higher than general due to climate
  energy,5.0,IEA WEO 2024,Carbon pricing trajectory
  water_utility,3.5,Utility sector analysis,Cost recovery + scarcity
  ```

## Implementation Checklist

- [ ] Create `data/parameters/economic/inflation_indices.csv`
- [ ] Write `data/scripts/adjust_prices_to_reference_year.py`
- [ ] Add `price_basis_year` to scenario schema
- [ ] Add price adjustment to `SimulationDataLoader.__init__()`
- [ ] Add validation: `test_price_year_consistency()`
- [ ] Document approach in [calculations.md](../../docs/architecture/calculations.md) Section 5
- [ ] Update all research price files with `year_basis` metadata
- [ ] Test: run 2015-2020 simulation with 2024-adjusted prices vs nominal
- [ ] Compare NPV difference to quantify the distortion

## References

- **Calculations methodology**: [docs/architecture/calculations.md](../../docs/architecture/calculations.md) Section 5.16
- **Current price files**: [data/prices/](../../data/prices/)
- **Capital costs**: [data/parameters/costs/capital_costs-research.csv](../../data/parameters/costs/capital_costs-research.csv)
- **Scenario config**: [settings/settings.yaml](../../settings/settings.yaml)
- **NPV implementation**: [src/simulation/metrics.py](../../src/simulation/metrics.py)

## Key Insights

1. **The model is internally inconsistent** - it claims to use "real terms" but actually uses nominal historical prices
2. **The 2015-2020 simulation is comparing apples to oranges** - 2015 revenues vs 2024 costs
3. **Quick fix: adjust all prices to 2024 basis** and run in real terms with real discount rate
4. **Better solution: model inflation explicitly** for multi-year forward-looking scenarios
5. **Egypt currency devaluation makes this especially tricky** - need to decide whether to model in USD or EGP

## Next Steps

**Recommended prioritization**:

1. **Immediate** (this sprint): Document current assumptions, add price_basis_year metadata
2. **Short-term** (next sprint): Create price adjustment scripts, convert to 2024 basis
3. **Medium-term** (Q2): Implement proper inflation escalation for forward scenarios
4. **Long-term** (Q3): Add real price trend projections for 2030-2040 scenarios
