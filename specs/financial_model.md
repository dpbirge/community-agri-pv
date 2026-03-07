# Financial Model Specification

Community Agri-PV Project — Comprehensive Cash Flow Analysis

## Overview

This specification defines a unified financial model that aggregates all capital expenditures,
operating costs, revenues, and financing structures into a multi-year cash flow projection for
the community agri-PV project. The model consumes outputs from existing simulation modules
(energy balance, water balance, crop yield, food processing, labor) and layers on capital
budgeting, debt service, and standard investment metrics.

**Position in architecture:** Post-simulation analysis layer. Reads daily simulation outputs
and system configuration; produces annual and project-lifetime financial summaries.

**Module:** `src/financial_model.py`
**Settings:** `settings/financial_model_base.yaml`
**Output:** `simulation/financial_summary.csv`, `simulation/annual_cash_flows.csv`


## 1. Capital Expenditures (CAPEX)

All upfront and replacement costs for physical infrastructure. Sourced from
`data/economics/capital_costs-research.csv` and equipment spec CSVs.

### 1.1 Energy System

| Component | Cost Basis | Source |
|-----------|-----------|--------|
| PV arrays | $/kW × installed capacity | capital_costs-research.csv |
| Wind turbines | $/kW × installed capacity | capital_costs-research.csv |
| Battery storage | $/kWh × installed capacity | capital_costs-research.csv, batteries-toy.csv |
| Diesel generator | $/kW × rated capacity | capital_costs-research.csv, generators-toy.csv |
| Inverters | $/kW × system capacity | capital_costs-research.csv |
| Electrical BOS | $/kW (mounting, wiring, grid connection) | capital_costs-research.csv |

**Installation labor:** Percentage of equipment CAPEX per `installation_labor_pct` column.

### 1.2 Water System

| Component | Cost Basis | Source |
|-----------|-----------|--------|
| Wells (drilling + casing) | Per-well from depth/config | wells-toy.csv |
| Submersible pumps | Per-pump from model | pump_systems-toy.csv |
| BWRO treatment plant | $/m³/day × rated throughput | water_treatment-research.csv |
| Storage tanks | $/m³ × tank capacity | storage_systems-toy.csv |
| Irrigation systems | $/ha × irrigated area | capital_costs-research.csv |

**Already partially computed** by `src/water_sizing.py` — this spec formalizes and extends it.

### 1.3 Food Processing & Storage

| Component | Cost Basis | Source |
|-----------|-----------|--------|
| Washing/sorting line | Per unit | processing_equipment-toy.csv |
| Drying equipment | Per unit (solar rack, tunnel, cabinet) | processing_equipment-toy.csv |
| Canning line | Per unit (retort, pressure, autoclave) | processing_equipment-toy.csv |
| Packaging equipment | Per unit | processing_equipment-toy.csv |
| Cold storage facility | $/m³ × storage volume | capital_costs-research.csv |

### 1.4 Farm Infrastructure

| Component | Cost Basis | Source |
|-----------|-----------|--------|
| Land preparation (one-time) | $/ha | TBD — not yet in data files |
| Fencing / access roads | Lump sum or $/ha | TBD |
| Tools and hand equipment | Lump sum | TBD |

### 1.5 Equipment Replacement Schedule

Components with lifespans shorter than the project horizon require mid-life replacement.
Sourced from `data/economics/equipment_lifespans-toy.csv`.

| Component | Lifespan (yr) | Replacement Cost (% of original) |
|-----------|---------------|-----------------------------------|
| RO membranes | 6 | 35% |
| Submersible pumps | 12 | 70% |
| Drip irrigation emitters | 7 | 25% |
| Battery pack | 12 | 60% |
| PV inverters | 12 | 18% |
| Diesel generator | 15 | 50% |
| PV panels | 27 | 0% (outlasts typical horizon) |
| Wind turbines | 22 | 0% (outlasts typical horizon) |

Replacement costs are placed in the year they occur. No salvage value assumed at project end
unless explicitly configured.


## 2. Operating Expenditures (OPEX)

### 2.1 Energy Operations (Already Computed)

Daily costs produced by `src/energy_balance.py`:

| Cost Item | Computation | Output Column |
|-----------|------------|---------------|
| Grid electricity import | grid_import_kwh × tariff_usd_per_kwh | `grid_import_cost` |
| Generator diesel fuel | fuel_liters × diesel_price_usd_per_liter | `generator_fuel_cost` |
| Grid export revenue (offset) | export_kwh × export_rate | `grid_export_revenue` |

**Not yet computed — to add:**

| Cost Item | Computation | Source |
|-----------|------------|--------|
| PV annual O&M | $/kW/yr × installed kW | operating_costs-research.csv (to be extended) |
| Wind annual O&M | $/kW/yr × installed kW | operating_costs-research.csv |
| Battery O&M | % of CAPEX/yr | TBD |
| Generator O&M (non-fuel) | $/kW/yr or $/hr runtime | TBD |

### 2.2 Water Operations (Already Computed)

Daily costs produced by `src/water_balance.py`:

| Cost Item | Computation | Output Column |
|-----------|------------|---------------|
| Municipal water purchases | volume_m3 × cost_per_m3 | `municipal_irrigation_cost`, `municipal_community_cost` |
| Groundwater O&M | well_om_per_year / 365 + treatment_maintenance_per_m3 | `groundwater_cost` |

**Not yet computed — to add:**

| Cost Item | Computation | Source |
|-----------|------------|--------|
| Membrane replacement | Amortized from lifespan/cost schedule | equipment_lifespans-toy.csv |
| Storage tank O&M | $/m³/yr × capacity | storage_systems-toy.csv |

### 2.3 Farm Operations

| Cost Item | Computation | Source |
|-----------|------------|--------|
| Seeds / seedlings | $/ha/season × planted area | TBD — not yet in data files |
| Fertilizer | $/ha/season × planted area | historical_fertilizer_costs-toy.csv |
| Pesticides / IPM | $/ha/season × planted area | TBD |
| Field labor | hours × wage_rate, by worker category | labor_wages-research.csv, labor_requirements-research.csv |
| Harvest labor | hours × wage_rate (seasonal harvesters) | labor_wages-research.csv, labor_requirements-research.csv |
| Equipment operator labor | hours × wage_rate | labor_wages-research.csv |

**Dependency:** Requires labor spec implementation (`src/labor.py`) to produce daily hours.
Until then, annual estimates from labor_requirements × wage rates can be used.

### 2.4 Food Processing Operations

| Cost Item | Computation | Source |
|-----------|------------|--------|
| Processing energy | processed_kg × energy_kwh_per_kg × energy_cost | processing_specs-research.csv |
| Processing labor | processed_kg × labor_hrs_per_kg × wage_rate | processing_specs-research.csv, labor_wages-research.csv |
| Packaging materials | processed_kg × material_cost_per_kg | fresh_packaging-toy.csv, processed_packaging-toy.csv |
| Equipment maintenance | $/yr per equipment unit | processing_equipment-toy.csv |
| Cold storage energy | inventory_m3 × kwh_per_m3_per_day × energy_cost | storage_spoilage_rates-toy.csv |

**Dependency:** Requires food processing spec implementation (`src/food_processing.py`).

### 2.5 Management & Overhead

| Cost Item | Computation | Source |
|-----------|------------|--------|
| Management labor | fixed daily hours × manager wage | labor_requirements-research.csv |
| Administration | fixed daily hours × admin wage | labor_requirements-research.csv |
| Equipment maintenance labor | annualized hours × technician wage | labor_requirements-research.csv |

### 2.6 Losses as Economic Cost

| Loss Type | Computation | Source |
|-----------|------------|--------|
| Handling losses | harvest_kg × handling_loss_pct × farmgate_price | handling_loss_rates-research.csv |
| Storage spoilage | inventory_kg × daily_spoilage_pct × product_price | storage_spoilage_rates-toy.csv |
| Queue spoilage | waiting_kg × fresh_spoilage_rate × farmgate_price | storage_spoilage_rates-toy.csv |


## 3. Revenues

### 3.1 Crop Sales

Revenue = saleable_kg × price_per_kg, computed per crop and product type.

**Saleable quantity** flows through:
```
harvest_kg
  → minus handling_loss (sorting, bruising, spillage)
  → allocated to processing pathways (fresh, packaged, canned, dried)
  → minus processing weight change (dehydration, trimming)
  → minus storage spoilage
  = saleable_kg per product type
```

**Price sources:**

| Product Type | Price Source |
|-------------|-------------|
| Fresh crops | data/prices/crops/historical_{crop}_prices-toy.csv (farmgate column) |
| Packaged crops | data/prices/processed_food_products/historical_packaged_{crop}_prices-toy.csv |
| Canned crops | data/prices/processed_food_products/historical_canned_{crop}_prices-toy.csv |
| Dried crops | data/prices/processed_food_products/historical_dried_{crop}_prices-toy.csv |

### 3.2 Market Tiers

Sales allocated across three market tiers with different pricing and logistics:

| Market Tier | Description | Price Basis | Transport Cost |
|-------------|------------|-------------|----------------|
| Local (Eastern Sinai) | Direct farmgate sales to nearby communities | Farmgate price (≈45% of wholesale) | Minimal |
| Regional (Egypt) | Wholesale to urban markets (Cairo, Alexandria) | Wholesale price | Significant |
| Export (Global) | Processed products to international markets | Export FOB price | Substantial |

**Not yet defined:** Market tier allocation rules, transport costs, export logistics,
quality/certification requirements, minimum volumes for regional/export access.

### 3.3 Energy Revenue

| Revenue Type | Computation | Status |
|-------------|------------|--------|
| Grid export (net metering) | Surplus kWh × export rate | Already in energy_balance.py |
| Feed-in tariff | kWh × FIT rate (if contract exists) | Data exists; program closed to new applicants |

### 3.4 Other Potential Revenue Streams

| Stream | Description | Status |
|--------|------------|--------|
| Carbon credits | PV/wind offset vs diesel/grid baseline | Not modeled |
| Water sales to neighbors | Surplus treated water | Not modeled |
| Agritourism | Educational/demonstration farm visits | Not modeled |
| Compost / byproducts | Processing waste valorization | Not modeled |


## 4. Financing Structure

### 4.1 Financing Profiles

Six profiles defined in `data/economics/financing_profiles-toy.csv`:

| Profile | CAPEX Borne | Debt Service | OPEX Borne | Use Case |
|---------|------------|-------------|-----------|----------|
| existing_owned | 0% | None | 100% | Pre-existing community assets |
| grant_full | 0% | None | 0% | Full NGO/donor coverage |
| grant_capex | 0% | None | 100% | Equipment donated, community operates |
| purchased_cash | 100% | None | 100% | Community self-funded |
| loan_standard | Financed | 10 yr @ 6.0% | 100% | Commercial bank |
| loan_concessional | Financed | 15 yr @ 3.5% | 100% | Development bank |

### 4.2 Per-Component Financing Assignment

Each major subsystem (PV, wind, water treatment, processing equipment, etc.) can be assigned
a different financing profile. This enables mixed financing — e.g., PV via concessional loan,
processing equipment via grant, irrigation purchased with cash.

```yaml
# Example: settings/financial_model_base.yaml
financing:
  pv_system: loan_concessional
  wind_system: loan_concessional
  battery_system: loan_standard
  water_treatment: grant_capex
  wells_and_pumps: purchased_cash
  irrigation: grant_capex
  processing_equipment: loan_standard
  cold_storage: loan_standard
  generator: purchased_cash
```

### 4.3 Loan Amortization

For loan-financed components:
- **Amortization method:** Equal annual payments (standard annuity)
- **Annual payment:** `CAPEX × [r(1+r)^n] / [(1+r)^n - 1]` where r = annual rate, n = term years
- **Interest/principal split:** Tracked per year for reporting
- **Grace period:** Configurable (0-2 years, interest-only during grace)

### 4.4 Equity and Grants

- **Grant-funded CAPEX:** Year 0 inflow matching equipment cost; no repayment
- **Community equity:** Cash contribution in Year 0; tracked for ROI calculation
- **Retained earnings:** Net operating cash flow after debt service; accumulates annually


## 5. Financial Projections

### 5.1 Annual Cash Flow Statement

For each year of the project horizon:

```
(+) Crop sales revenue (fresh + processed, by market tier)
(+) Energy export revenue (grid sales)
(=) Total Revenue

(-) Energy operating costs (grid import, fuel, equipment O&M)
(-) Water operating costs (municipal, groundwater O&M)
(-) Farm operating costs (seed, fertilizer, labor)
(-) Processing & storage costs (energy, labor, packaging, maintenance)
(-) Management & overhead labor
(-) Economic losses (handling, spoilage)
(=) Operating Income (EBITDA)

(-) Equipment replacement costs (scheduled mid-life replacements)
(-) Loan interest payments
(-) Loan principal payments
(=) Net Cash Flow

(+) Grant inflows (Year 0 or scheduled disbursements)
(-) Equity contributions (Year 0)
(=) Free Cash Flow to Community
```

### 5.2 Project-Level Metrics

| Metric | Definition | Notes |
|--------|-----------|-------|
| NPV | Net present value of all cash flows at discount rate | Discount rate configurable (default 8%) |
| IRR | Internal rate of return | Rate at which NPV = 0 |
| Payback Period | Years until cumulative net cash flow turns positive | Simple (undiscounted) |
| Discounted Payback | Years until cumulative discounted cash flow turns positive | |
| LCOE | Levelized cost of energy ($/kWh) | Total energy system cost / total kWh produced |
| LCOW | Levelized cost of water ($/m³) | Total water system cost / total m³ delivered |
| Cost per kg produced | Total farm cost / total harvest kg | By crop |
| Profit margin | (Revenue - Total Cost) / Revenue | By product type |
| DSCR | Debt service coverage ratio: EBITDA / debt payments | For loan-financed scenarios |
| Benefit-Cost Ratio | PV(benefits) / PV(costs) | For grant-funded scenarios |

### 5.3 Sensitivity Parameters

The model should support single-variable sensitivity analysis on:

- Discount rate
- Crop prices (±20%, ±50%)
- Electricity tariff escalation rate
- Municipal water price escalation
- Diesel price trajectory
- Equipment cost reduction (learning curve)
- Yield variability (drought/optimal scenarios)
- Processing allocation splits (fresh vs dried vs canned)
- Financing terms (interest rate, loan tenor)


## 6. Configuration Schema

### 6.1 Settings File: `settings/financial_model_base.yaml`

```yaml
project_horizon_years: 15
discount_rate: 0.08
currency: USD
inflation_rate: 0.03

financing:
  default_profile: loan_concessional
  overrides:
    # per-subsystem financing profile overrides
    water_treatment: grant_capex
    irrigation: grant_capex

market_allocation:
  default:
    local: 0.60
    regional: 0.30
    export: 0.10
  overrides:
    # per-product overrides
    dried_tomato:
      local: 0.10
      regional: 0.30
      export: 0.60

price_escalation:
  electricity: 0.05        # annual real escalation rate
  diesel: 0.03
  municipal_water: 0.04
  crop_prices: 0.02
  labor_wages: 0.03

salvage_value:
  method: linear_depreciation  # or none, or percentage_of_original
```

### 6.2 Data Registry Additions

New entries needed in `settings/data_registry_base.yaml`:

```yaml
economics:
  capital_costs: data/economics/capital_costs-research.csv
  operating_costs: data/economics/operating_costs-research.csv
  financing_profiles: data/economics/financing_profiles-toy.csv
  equipment_lifespans: data/economics/equipment_lifespans-toy.csv
  reference_costs: data/economics/reference_costs-toy.csv

prices:
  fertilizer: data/prices/inputs/historical_fertilizer_costs-toy.csv
  # crop and processed food prices already partially registered
```


## 7. Module API

```python
# Public API
def compute_financial_summary(
    *,
    scenario_path,
    energy_balance_path=None,     # simulation/daily_energy_balance.csv
    water_balance_path=None,      # simulation/daily_water_balance.csv
    harvest_yields_path=None,     # simulation/daily_harvest_yields.csv
    food_processing_path=None,    # simulation/daily_food_processing.csv (when available)
    labor_summary_path=None,      # simulation/daily_labor.csv (when available)
):
    """Compute multi-year financial projections from simulation outputs.

    Aggregates daily simulation costs to annual totals, layers on CAPEX,
    financing, and revenue to produce project-lifetime cash flow analysis.

    Returns:
        dict with keys: annual_cash_flows (DataFrame), summary_metrics (dict),
        capex_schedule (DataFrame), debt_service (DataFrame)
    """

def save_financial_summary(result, output_dir):
    """Save financial summary DataFrames to simulation/ directory."""

def load_financial_summary(output_dir):
    """Load previously saved financial summary."""
```


## 8. Implementation Phases

### Phase 1: CAPEX Aggregation + Simple Revenue
- Load capital costs for all configured subsystems
- Compute total CAPEX with installation labor
- Apply financing profiles (loan amortization, grants)
- Compute crop revenue from harvest yields × farmgate prices
- Produce basic annual cash flow (OPEX from existing simulation + CAPEX + revenue)
- Calculate NPV, IRR, payback

### Phase 2: Full Operating Cost Integration
- Integrate energy system O&M (currently missing from simulation)
- Integrate equipment replacement schedule
- Add fertilizer costs from historical data
- Add management/overhead labor costs (fixed daily)
- Add price escalation over project horizon

### Phase 3: Food Processing Economics
- Depends on `src/food_processing.py` implementation
- Processing costs (energy, labor, packaging materials)
- Storage costs (cold storage energy, spoilage losses)
- Processed product revenue (canned, dried, packaged at higher prices)
- Market tier allocation

### Phase 4: Sensitivity & Scenario Analysis
- Parameterized sensitivity sweeps
- Monte Carlo on price/yield uncertainty
- Scenario comparison (financing structures, crop mixes, processing allocations)
- Break-even analysis (minimum viable price, minimum yield)


## 9. Dependencies and Prerequisites

| Dependency | Status | Impact on Financial Model |
|-----------|--------|--------------------------|
| Energy balance simulation | Implemented | Provides daily energy OPEX |
| Water balance simulation | Implemented | Provides daily water OPEX |
| Crop yield computation | Implemented | Provides harvest quantities for revenue |
| Labor system (`src/labor.py`) | NOT implemented | Phase 2 can use annual estimates as fallback |
| Food processing (`src/food_processing.py`) | NOT implemented | Phase 3 deferred; fresh-only revenue in Phase 1 |
| Equipment failure model | NOT implemented | Not required; can add risk premium later |


## 10. What Is Explicitly Out of Scope

- **Tax modeling:** No corporate tax, VAT, or import duty calculations
- **Currency risk:** All calculations in USD; no EGP conversion dynamics
- **Inflation indexing:** Real terms only (inflation applied as constant escalation rate)
- **Supply chain logistics:** No transport routing, warehousing beyond farm gate
- **Market demand modeling:** Assumes all production is sold (no demand elasticity)
- **Insurance:** No crop insurance or equipment insurance premiums
- **Opportunity cost of land:** Land assumed community-owned, no rental value
- **Household economics:** No modeling of individual household income/expenditure
- **Environmental externalities:** No carbon pricing, ecosystem service valuation
- **Construction timeline:** CAPEX assumed Year 0; no multi-year build-out phasing

---

## Clarifying Questions for Discussion

The following questions are meant to drive a socratic conversation to refine this spec
before implementation. They are grouped by theme.

### Revenue & Market Model

1. **Market access assumptions:** The spec proposes three market tiers (local, regional,
   export). Is this the right segmentation? Should we model specific buyer types (e.g.,
   local restaurants, wholesale aggregators, export brokers) or keep it at the tier level?

2. **Price selection:** Crop price data spans 2015-2024. Should the financial model use
   (a) the most recent year's prices, (b) a multi-year average, (c) the full time series
   matched to simulation weather years, or (d) user-specified fixed prices?

3. **Demand constraints:** The current spec assumes all production is sold. Should we model
   demand limits — e.g., the local market can absorb at most X tons/month of tomatoes before
   prices drop? Or is unlimited demand a reasonable simplification for a community-scale farm?

4. **Processed product pricing:** The value-add multipliers in processing_specs (e.g., 24x for
   dried tomato) are applied to fresh weight prices. Should we validate these against the
   actual processed product price data in `data/prices/processed_food_products/`? The two
   data sources may not agree.

5. **Seasonality of sales:** Should revenue be computed annually or should we track monthly/
   seasonal revenue to capture the mismatch between harvest periods and year-round costs?

### Cost Structure

6. **Seed and input costs:** The data files include fertilizer costs ($/ha/season) but not
   seed costs, pesticide costs, or other farm inputs. Should we (a) create placeholder data
   files for these, (b) bundle them into a single "farm inputs" $/ha rate, or (c) defer
   until research-grade data is available?

7. **Energy system O&M:** The operating_costs-research.csv only has wind turbine O&M rates.
   PV, battery, and generator non-fuel O&M are missing. Should we (a) add research-grade
   entries to the CSV, (b) use percentage-of-CAPEX rules of thumb (e.g., PV O&M = 1% of
   CAPEX/yr), or (c) treat this as a data gap to fill before implementation?

8. **Labor costing approach:** The labor spec defines 85+ activities with per-hectare or
   per-kg hour requirements. Since `src/labor.py` is not yet implemented, should the
   financial model (a) wait for labor module implementation, (b) use simplified annual
   labor cost estimates (total hours × average wage), or (c) implement a minimal labor
   cost calculator within the financial module itself?

9. **Cold storage capital vs operating:** Cold storage appears in both CAPEX (facility
   construction) and OPEX (daily energy). The processing_equipment-toy.csv has capital
   costs for processing lines but cold storage facility cost is only in
   capital_costs-research.csv. Should cold storage be sized from harvest volume, or
   configured as a fixed capacity in settings?

### Financing

10. **Financing granularity:** The spec allows per-subsystem financing profiles. Is this
    level of granularity useful, or would it be simpler to have 2-3 financing buckets
    (e.g., "infrastructure" vs "equipment" vs "operating capital")? What financing
    structures are realistic for a Sinai community farm?

11. **Grant timing:** Should grants be modeled as Year 0 lump sums, or can they arrive in
    tranches over multiple years? Some development programs disburse in phases tied to
    milestones.

12. **Working capital:** The spec doesn't address working capital needs — the community
    needs cash to pay labor and buy inputs before harvest revenue arrives. Should we model
    a working capital facility (short-term credit line) or assume the community has
    sufficient reserves?

13. **Community ownership model:** How are costs and revenues shared among community
    members? Is this a cooperative, a shared enterprise, individual farm plots with shared
    infrastructure? This affects how financial metrics should be reported (per-household
    vs project-level).

### Project Horizon & Timing

14. **Project horizon:** The spec defaults to 15 years. Is this appropriate? PV panels last
    25-30 years; wind turbines 20-22 years. Should the horizon match the longest-lived
    asset, or is 15 years a standard development-project evaluation window?

15. **Construction period:** All CAPEX is placed in Year 0. Should we model a 1-2 year
    construction period where costs are incurred but no revenue is generated? This
    significantly affects IRR and payback calculations.

16. **Ramp-up period:** Should the model account for a learning curve in the first 1-2 years
    where yields are lower, processing efficiency is reduced, and market relationships are
    being established?

17. **Simulation years vs financial years:** The daily simulation runs for a configurable
    number of years using historical weather data (2010-2025). Should the financial model
    project forward from a start date, or use the simulation period as-is? How should
    multi-year weather variability map to financial projections?

### Metrics & Reporting

18. **Primary audience:** Who will consume the financial model outputs? Investors need IRR
    and DSCR. NGO donors need benefit-cost ratios and cost-per-beneficiary. Community
    members need "what will my monthly costs/income be?" The output format should match
    the audience.

19. **Comparison baseline:** Should the model compute a "without project" baseline (e.g.,
    community buys all food and energy at market prices) to show the net benefit of the
    agri-PV project? This is standard for development project appraisals.

20. **Risk reporting:** Should the financial summary include a risk-adjusted NPV or
    probability distribution, or is deterministic analysis sufficient for this stage?
    The equipment failure rates data exists but is toy-quality.

### Data Quality

21. **Toy vs research data:** Several critical economic data files are tagged as "toy"
    (synthetic): financing profiles, equipment lifespans, crop prices, processing equipment.
    Should we (a) proceed with toy data and flag results as indicative, (b) prioritize
    upgrading specific files to research-grade, or (c) implement the model with configurable
    data quality tiers that clearly label which inputs are validated?

22. **Exchange rate handling:** All costs are in 2024 USD. Egyptian pound has devalued
    dramatically (5.5 to 48.5 EGP/USD over 2015-2024). Labor wages are anchored in EGP.
    Should the financial model (a) stay purely in USD, (b) model EGP costs separately
    and convert at a projected exchange rate, or (c) use purchasing power parity adjustments?
