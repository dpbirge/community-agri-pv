# Community Farm Modeling Specifications

## 1. Overview

### Primary goal

This document defines the configuration schema and policy structure for the community farm simulation model. It serves as the single source of truth for what parameters exist, their valid options, and how they organize into a complete simulation scenario.

There are two main sections: system configurations (static initial conditions) and policies (rule-sets governing simulation behavior). For calculation methodologies and formulas, see `mvp-calculations.md`.

## 2. System configurations

System configurations are static settings that describe initial conditions of a given simulation.

### System Financing

All community-owned systems include a `financing_status` parameter that indicates the financial profile for capital costs (CAPEX) and operating costs (OPEX).

**Financing status options:** [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

**Profiles:**
- `existing_owned`: Already owned/depreciated assets, O&M costs only
- `grant_full`: Grant covers CAPEX and O&M, no community cost
- `grant_capex`: Grant covers CAPEX, community pays O&M
- `purchased_cash`: Community paid cash for CAPEX, pays O&M
- `loan_standard`: Standard commercial loan, community pays debt service + O&M
- `loan_concessional`: Below-market development loan, pays debt service + O&M

**Note:** Financial parameters (interest rates, loan terms, cost multipliers) for each profile are defined in `data/parameters/economic/financing_profiles.csv`.

**Configuration sections use `_system` suffix:** In YAML files, use `water_system`, `energy_system`, and `food_processing_system` as section names.

### Water system

**Groundwater wells:**
- well_depth_m
- salinity_level: [low, moderate, high, very_high]
- well_flow_rate_m3_day
- number_of_wells
- aquifer_exploitable_volume_m3
- aquifer_recharge_rate_m3_yr
- financing_status: [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

**Water treatment:**
- treatment_type: [bwro, swro, ro, none]
- system_capacity_m3_day
- number_of_units
- tds_ppm
- financing_status: [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

**Irrigation water storage:**
- capacity_m3
- type: [reservoir, tank, pond]
- financing_status: [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

**Irrigation system:**
- type: [drip_irrigation, sprinkler, surface, subsurface_drip]
- financing_status: [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

### Energy system

**PV (agri-PV):**
- sys_capacity_kw
- type: [fixed_tilt, single_axis_tracking, dual_axis_tracking]
- tilt_angle
- percent_over_crops
- density: [low, medium, high]
- height_m
- financing_status: [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

**Wind:**
- sys_capacity_kw
- type: [small, medium, large]
- hub_height_m
- financing_status: [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

**Battery:**
- sys_capacity_kwh
- units
- chemistry: [LFP, NMC, lead_acid]
- financing_status: [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

**Backup generator:**
- capacity_kw
- type: [diesel, natural_gas, biodiesel]
- financing_status: [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

**Grid:**
- pricing_regime: [subsidized, unsubsidized]

### Food processing system

**Fresh food packaging:**
- equipment: list of {type, fraction}
  - type: [washing_sorting_line, simple_wash_station]
- storage_capacity_kg_total
- shelf_life_days
- financing_status: [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

**Drying:**
- equipment: list of {type, fraction}
  - type: [solar_tunnel_dryer, simple_dehydrator, electric_dryer]
- storage_capacity_kg_total
- shelf_life_days
- financing_status: [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

**Canning:**
- equipment: list of {type, fraction}
  - type: [simple_retort, pressure_canner, industrial_retort]
- storage_capacity_kg_total
- shelf_life_days
- financing_status: [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

**Packaging:**
- equipment: list of {type, fraction}
  - type: [packaged, vacuum_sealed, modified_atmosphere]
- storage_capacity_kg_total
- shelf_life_days
- financing_status: [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

### Community structure

- community_area_km2
- total_farms
- total_farming_area_ha
- community_population
- houses
- industrial_buildings_m2
- community_buildings_m2

### Farm configuration

**Per farm:**
- id
- name
- area_ha
- yield_factor
- starting_capital_usd

**Crops (per farm):**
- name: [tomato, potato, onion, kale, cucumber]
- area_fraction
- planting_date
- percent_planted

### Economic configuration

- currency: [USD, EGP, EUR]
- discount_rate

**Note:** Infrastructure-specific debt is tracked via `financing_status` in each system configuration. The economics section captures only community-level financial parameters.

### Pricing configuration

**Water pricing:**
- municipal_source: [seawater_desalination, piped_nile, piped_groundwater]
- pricing_regime: [subsidized, unsubsidized]
- subsidized.use_tier: [1, 2, 3]
- unsubsidized.base_price_usd_m3
- unsubsidized.annual_escalation_pct

**Energy pricing:**
- grid.pricing_regime: [subsidized, unsubsidized]
- renewable.lcoe_pv_usd_kwh
- renewable.lcoe_wind_usd_kwh

## 3. Policies

Policies are rule-sets that govern actions within the simulation. Policies can be set by the community or by each farm individually. Community policies override or limit farm policies.

All policy modules follow the same pattern: a context dataclass (input), a decision/allocation dataclass (output), a base class with a `decide()` or `allocate()` method, concrete policy classes, and a registry with a `get_*_policy(name)` factory function. Policy source code is in `src/policies/`.

### Implementation status

| Policy Domain | Policies Defined | Integrated in Simulation | Code Location |
|---|---|---|---|
| Water | 5 | **Yes** — active in daily loop | `src/policies/water_policies.py` |
| Food processing | 4 | **Yes** — active in `process_harvests()` | `src/policies/food_policies.py` |
| Energy | 3 | **No** — dispatch is hardcoded merit-order | `src/policies/energy_policies.py` |
| Crop (irrigation) | 3 | **No** — demand used directly from precomputed | `src/policies/crop_policies.py` |
| Economic | 4 | **No** — cash update is simple aggregate | `src/policies/economic_policies.py` |
| Market (sales) | 4 | **No** — crops sold immediately at harvest | `src/policies/market_policies.py` |

> **Integration note:** Energy, crop, economic, and market policies are fully coded with decision logic and registered in `src/policies/__init__.py`, but the simulation loop in `src/simulation/simulation.py` does not call them. Integrating each requires: (1) instantiate the policy object during scenario loading, (2) build the appropriate context in the simulation loop, (3) use the policy's decision output to drive behavior. The water and food processing policies demonstrate this pattern.

### Community policies

**Water conservation policies:**
- conserve_groundwater:
  - price_threshold_multiplier
  - max_gw_ratio
- quota_enforced:
  - annual_quota_m3
  - monthly_variance_pct

### Water policies — integrated

Each farm selects a water source allocation strategy. The policy is instantiated during scenario loading and called daily in the simulation loop via `execute_water_policy()`.

> **Detailed documentation:** See `mvp-policies.md` Section 2 for complete implementation details including context/output dataclass fields, helper methods, pseudocode, and usage examples.

**Options:** [always_groundwater, always_municipal, cheapest_source, conserve_groundwater, quota_enforced]

| Policy | Behavior |
|---|---|
| `always_groundwater` | 100% groundwater with onsite desalination; municipal fallback if physically constrained |
| `always_municipal` | 100% municipal water; no treatment energy needed |
| `cheapest_source` | Daily cost comparison: groundwater (pumping + treatment energy cost) vs municipal (marginal tier price) |
| `conserve_groundwater` | Prefers municipal; uses groundwater only when municipal price exceeds a configurable threshold multiplier |
| `quota_enforced` | Hard annual groundwater limit with monthly variance controls; forces 100% municipal when quota exhausted |

**Context → Decision:** `WaterPolicyContext` → `WaterAllocation` (groundwater_m3, municipal_m3, cost_usd, energy_used_kwh)

### Food processing policies — integrated

Determines how harvested crop is split across processing pathways. Called in `process_harvests()` during the simulation loop.

**Options:** [all_fresh, maximize_storage, balanced, market_responsive]

| Policy | Fresh | Packaged | Canned | Dried |
|---|---|---|---|---|
| `all_fresh` | 100% | 0% | 0% | 0% |
| `maximize_storage` | 20% | 10% | 35% | 35% |
| `balanced` | 50% | 20% | 15% | 15% |
| `market_responsive` | 30-65% | 15-20% | 10-25% | 10-25% |

`market_responsive` shifts toward processing when fresh prices fall below 80% of reference farmgate prices.

**Context → Decision:** `FoodProcessingContext` → `ProcessingAllocation` (fresh_fraction, packaged_fraction, canned_fraction, dried_fraction)

### Energy policies — implemented, not yet integrated

Three dispatch strategies are defined. Currently, `dispatch_energy()` in `simulation.py` uses a hardcoded renewable-first merit-order. These policies return `EnergyAllocation` flags that could parameterize the dispatch function.

**Options:** [all_renewable, hybrid, all_grid, cost_minimize]

**Context → Decision:** `EnergyPolicyContext` → `EnergyAllocation`

> See **`mvp-policies.md` Section 3** for complete policy specifications, dataclass definitions, pseudocode, implementation status, and integration requirements.

### Crop (irrigation) policies — implemented, not yet integrated

**Options:** [fixed_schedule, deficit_irrigation, weather_adaptive]

**Context → Decision:** `CropPolicyContext` → `CropDecision`

See `mvp-policies.md` Section 5 for full policy specifications, pseudocode, and integration requirements.

### Economic policies — implemented, not yet integrated

**Options:** [balanced, aggressive_growth, conservative, risk_averse]

**Context → Decision:** `EconomicPolicyContext` → `EconomicDecision`

> See **`mvp-policies.md` Section 6** for complete policy specifications, dataclass definitions, pseudocode, and integration requirements.

### Market (sales) policies — implemented, not yet integrated

Four sale timing strategies are defined. Currently, crops are sold immediately at harvest within `process_harvests()`.

**Options:** [sell_immediately, hold_for_peak, process_when_low, adaptive_marketing]

**Context → Decision:** `MarketPolicyContext` → `MarketDecision` (sell_fraction, store_fraction, process_fraction, target_price_per_kg)

> See **`mvp-policies.md` Section 7** for complete policy specifications, dataclass definitions, pseudocode, and integration requirements.

### Not yet implemented

The following policy-related features from the model plan have no code:

- **Community pooling mechanism** — configurable pooling percentages, distribution rules, mutual aid fund
- **Per-farm cost allocation** — rules for splitting shared infrastructure costs (proportional to area, equal, usage-based)
- **Working capital advances** — pre-harvest cash advances to farmers, recouped at sale
- **Insurance options** — crop insurance, equipment insurance, comparison with self-insurance reserves
- **Price correlation structure** — correlated stochastic shocks across crop prices, energy prices, and weather


## 4. Metrics

Metrics are computed at daily, monthly, and yearly granularity. Farm-level and community-level aggregations are provided separately. Units shown in brackets. Metrics tagged *(resilience)* are also used as inputs to the resilience and survivability analysis suite (see Resilience metrics). See `mvp-calculations.md` for formulas.

### Water metrics

- Total water use [m³/yr]
- Groundwater use [m³/yr, m³/kg-yield]
- Municipal water use [m³/yr, m³/kg-yield]
- Water use efficiency [m³/kg-yield] — total water per kg crop output
- Water self-sufficiency [%] — groundwater / total water × 100 *(resilience)*
- Aquifer depletion rate [m³/yr drawdown, estimated years remaining] *(resilience)*
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


## 5. Plots + Tables

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

**Table 2 — Revenue Diversification Summary**
One row per crop. Columns: crop, area fraction, annual yield (kg), fresh revenue ($), processed revenue ($), total revenue ($), revenue share (%), price CV. Shows contribution of each crop and product type to total revenue and highlights which crops are most volatile.
