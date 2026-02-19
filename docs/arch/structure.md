# Community Farm Modeling Specifications

## 1. Overview

### Primary goal

This document defines the configuration schema and policy structure for the community farm simulation model. It serves as the single source of truth for what parameters exist, their valid options, and how they organize into a complete simulation scenario.

There are two main sections: system configurations (static initial conditions) and policies (rule-sets governing simulation behavior). For detailed policy rule-sets and pseudocode, see `policies.md`. For calculation methodologies and formulas, see `calculations.md`.

## 2. System configurations

System configurations are static settings that describe initial conditions for a given simulation.

Configuration parameters are in the form:
**Category**
- parameter_name [list of options] (clarifying notes) TODO: Notes to guide refactoring or new functionality

When units are obvious, they should be appended to the end of the parameter. E.g. community_area_km2

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

**Note:** Financial parameters (interest rates, loan terms, cost multipliers) for each profile are defined in `data/parameters/economic/financing_profiles-toy.csv`.

**Configuration sections use \****`_system`**\*\* suffix:** In YAML files, use `water_system`, `energy_system`, and `food_processing_system` as section names.

### Water system

**Groundwater wells:**
- well_depth_m
- salinity_level: [low, moderate, high] (must match rows in `treatment_kwh_per_m3-toy.csv`; add a `very_high` row to that file if very-high-salinity scenarios are needed)
- well_flow_rate_m3_day
- number_of_wells
- aquifer_exploitable_volume_m3
- aquifer_recharge_rate_m3_yr
- max_drawdown_m (maximum allowable drawdown at full depletion, in meters; used in aquifer drawdown feedback — see `calculations.md` Section 2)
- financing_status: [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

**Water treatment:**
- treatment_type: [bwro, swro, ro, none]
- system_capacity_m3_day
- number_of_units
- groundwater_tds_ppm (static config value for raw groundwater TDS from scenario YAML)
- municipal_tds_ppm (static config value for municipal supply TDS from scenario YAML)
- financing_status: [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

**TDS data flow:**

- `groundwater_tds_ppm`: Raw groundwater salinity, set in scenario YAML. Used to determine treatment energy (via `salinity_level` lookup) and as input to `min_water_quality` blending calculations.
- `municipal_tds_ppm`: Municipal supply salinity, set in scenario YAML. Used in `min_water_quality` blending calculations. Municipal water is assumed to be pre-treated and always cleaner than raw groundwater.
- Treated groundwater TDS: Computed from treatment efficiency and raw `groundwater_tds_ppm`. Post-treatment TDS is used when calculating mixed water quality.
- Mixed water TDS: Weighted average when blending sources — `(gw_m3 * gw_tds + muni_m3 * muni_tds) / (gw_m3 + muni_m3)`. See `policies.md` `min_water_quality` policy for the mixing formula.

**Water conveyance:**
- conveyance_kwh_per_m3 (fixed energy estimate for pipe conveyance: well→treatment→storage. Default 0.2 kWh/m³. See `calculations.md` Section 2.)

**Irrigation water storage:**
- capacity_m3
- type: [reservoir, tank, pond]
- financing_status: [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

**Irrigation system:**
- type: [drip_irrigation, sprinkler, surface, subsurface_drip]
- financing_status: [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

### Energy system

**PV (agri-PV, fixed-tilt):**
- sys_capacity_kw
- tilt_angle
- percent_over_crops
- density: [low, medium, high]
- height_m
- financing_status: [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

**Wind:**
- sys_capacity_kw
- type: [small, medium, large]
- financing_status: [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

**Battery:**
- sys_capacity_kwh
- units
- chemistry: [LFP, NMC, lead_acid]
- financing_status: [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

**Backup generator:**
- capacity_kw
- type: [diesel]
- max_runtime_hours (maximum daily generator runtime in hours; reserves remaining hours for maintenance/cooling. Default 18.)
- financing_status: [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

### Food processing system

**Fresh food packaging:**
- equipment: list of {type, fraction}
  - type: [washing_sorting_line, simple_wash_station]
- storage_capacity_kg_total
- storage_life_days (e.g., 3-7 days; short duration accounting for on-farm storage + transit + retail shelf time)
- financing_status: [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

**Drying:**
- equipment: list of {type, fraction}
  - type: [solar_tunnel_dryer, simple_dehydrator, electric_dryer]
- storage_capacity_kg_total
- storage_life_days (e.g., 6-12 months; long duration for shelf-stable dried products)
- financing_status: [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

**Canning:**
- equipment: list of {type, fraction}
  - type: [simple_retort, pressure_canner, industrial_retort]
- storage_capacity_kg_total
- storage_life_days (e.g., 1-3 years; very long duration for shelf-stable canned products)
- financing_status: [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

**Packaging:**
- equipment: list of {type, fraction}
  - type: [packaged, vacuum_sealed, modified_atmosphere]
- storage_capacity_kg_total
- storage_life_days (e.g., 2-8 weeks; moderate duration depending on packaging technology)
- financing_status: [existing_owned, grant_full, grant_capex, purchased_cash, loan_standard, loan_concessional]

### Community structure

- community_area_km2
- total_farms
- total_farming_area_ha
- total_area_ha
- community_population
- houses
- community_buildings: structured map of building types with areas in m²
  - office_admin_m2 (administrative offices)
  - storage_warehouse_m2 (shared storage and warehousing)
  - meeting_hall_m2 (community meetings, training)
  - workshop_maintenance_m2 (equipment repair, maintenance)
- cost_allocation_method: [equal, area_proportional, usage_proportional] (how shared infrastructure OPEX is split across farms; see `simulation_flow.md` Section 6)

**Community building energy and water demands** are loaded from precomputed files as per-m² daily rates, then scaled by the configured building areas. See `simulation_flow.md` Section 8.1 for the scaling formula.

### Farm configurations

**Per farm:**
- id
- name
- plantable_area_ha TODO: Update code to match updated parameter name
- yield_factor (relative to soil profile)
- starting_capital_usd (initial working capital from scenario YAML; runtime state `current_capital_usd` is initialized from this value and updated each time step to track capital accumulation/depletion)

**Crops (per farm):**
- name: [tomato, potato, onion, kale, cucumber]
- area_fraction
- planting_dates: list of MM-DD strings (e.g., ["02-15", "11-01"])
- percent_planted

### Economic configuration

- currency: [USD, EGP, EUR]
- exchange_rate_egp_per_usd (fixed for simulation run; all EGP values converted to USD at data load time)
- discount_rate

**Note:** Infrastructure-specific debt is tracked via `financing_status` in each system configuration. The economics section captures only community-level financial parameters.

### Pricing configuration

**Water pricing:**
- municipal_source: [seawater_desalination, piped_groundwater]
- agricultural:
  - pricing_regime: [subsidized, unsubsidized] (independent from domestic pricing)
  - subsidized.price_usd_per_m3 (flat rate for subsidized agricultural water)
  - subsidized.annual_escalation_pct (0 = flat government-fixed rate; >0 = inflation-adjusted annual increase)
  - unsubsidized.base_price_usd_m3 (base price with annual escalation)
  - unsubsidized.annual_escalation_pct
- domestic:
  - pricing_regime: [subsidized, unsubsidized] (independent from agricultural pricing)
  - subsidized.tier_pricing: list of {tier, max_m3_per_month, price_egp_per_m3} (Egyptian progressive 5-tier IBT system; prices in EGP, converted to USD at load time via `exchange_rate_egp_per_usd`)
  - subsidized.wastewater_surcharge_pct (percentage added to water bill for sewage; Egyptian standard: 75%)
  - unsubsidized.base_price_usd_m3 (base price with annual escalation)
  - unsubsidized.annual_escalation_pct

**Energy pricing:**
- agricultural:
  - pricing_regime: [subsidized, unsubsidized] (independent from domestic pricing)
  - subsidized.price_usd_per_kwh (flat rate for agricultural electricity - water pumping, processing)
  - subsidized.annual_escalation_pct (0 = flat government-fixed rate; >0 = inflation-adjusted annual increase)
  - unsubsidized.price_usd_per_kwh (flat rate for unsubsidized agricultural electricity)
  - unsubsidized.annual_escalation_pct (annual price escalation rate)
- domestic:
  - pricing_regime: [subsidized, unsubsidized] (independent from agricultural pricing)
  - subsidized.price_usd_per_kwh (flat rate for domestic electricity - households, community buildings)
  - subsidized.annual_escalation_pct (0 = flat government-fixed rate; >0 = inflation-adjusted annual increase)
  - unsubsidized.price_usd_per_kwh (flat rate for unsubsidized domestic electricity)
  - unsubsidized.annual_escalation_pct (annual price escalation rate)
- net_metering_ratio (default 0.70; fraction of grid import price paid for exported renewable energy. Export price = grid_import_price × net_metering_ratio)

**Price escalation convention:** All pricing sections (water and energy, both subsidized and unsubsidized) support `annual_escalation_pct`. Set to 0 for flat government-fixed pricing. Set >0 for inflation-adjusted annual escalation. Escalation is applied relative to `simulation.start_date.year` — see `simulation_flow.md` Section 3.3/3.4 for the resolution formula.

## 3. Policies

See `policies.md` Water Policies for complete implementation details including context/output dataclass fields, helper methods, pseudocode, and usage examples.

Policy source code is in `src/policies/`

### Policy scope and hierarchy

Policies operate at three levels:

1. **Farm-level policies** (default) — Each farm independently selects its own policy for each domain (water, energy, crop, food processing, market, economic). Policies are set via the `scenarios/` YAML configuration file under each farm's entry.

2. **Community-override policies** (optional) — If all farms agree to a universal policy, a community-level override can be set in the scenario YAML. When set, the community policy automatically applies to all farms, overriding individual farm selections. Useful for shared infrastructure decisions that require uniform behavior.

3. **Household and shared facility policies** — Non-farm operations (residential households and shared community buildings) use water and energy policies for their operational needs. These apply only to water and energy demands of non-farm operations, not to crop production or food processing. Household/facility policies are limited to: water policy `max_groundwater` or `max_municipal`; energy policy `microgrid`, `renewable_first`, or `all_grid`. Configured in the scenario YAML under `household_policies`.

### Policy characteristics

Policies are rule-sets that govern actions within the simulation. All policy modules follow the same pattern:
- a context dataclass (input)
- a decision/allocation dataclass (output)
- a base class with a `decide()` or `allocate()` method, concrete policy classes
- a registry with a `get_*_policy(name)` factory function
- a `decision_reason` string in every output — explains why the decision was made (e.g., `"gw_cheaper"`, `"quota_exhausted"`), enabling filtering and grouping in analysis

### Daily execution order

Policies execute in this order each simulation day:

1. **Crop policy** → irrigation demand request (adjusted_demand_m3)
2. **Water policy** → water allocation (groundwater/municipal source split)
3. **Energy policy** → energy dispatch flags
4. **Food processing policy** → harvest allocation (runs only on harvest days)
5. **Forced sales (umbrella rule)** → expired/overflow inventory sold
6. **Market policy** → sell/store decisions on remaining inventory
7. **Economic policy** → monthly/yearly financial decisions

See `policies.md` Overview (Execution order) for details on timing and dependencies.

### Water policies

Each farm selects a water source allocation strategy. The policy is instantiated during scenario loading and called daily in the simulation loop via `water_policy.allocate_water(ctx)`.

| Policy name | Behavior |
| --- | --- |
| `max_groundwater` | Maximize groundwater extraction up to physical limits (well capacity, treatment throughput); municipal fallback when constrained |
| `max_municipal` | Maximize municipal water; groundwater used only when municipal is physically unavailable |
| `min_water_quality` | Mix groundwater and municipal water to achieve target salinity/TDS. Municipal water is always highest quality. If groundwater is constrained, the municipal fraction increases, improving quality above target |
| `cheapest_source` | Daily cost comparison: groundwater (pumping + treatment energy cost) vs municipal (marginal tier price) |
| `conserve_groundwater` | Prefers municipal; uses groundwater only when municipal price exceeds a configurable threshold multiplier. Decision output includes `limiting_factor` to distinguish ratio-cap vs infrastructure constraints |
| `quota_enforced` | Hard annual groundwater limit with monthly variance controls; forces 100% municipal when quota exhausted |

**Context → Decision:** `WaterPolicyContext` → `WaterAllocation` (groundwater_m3, municipal_m3, cost_usd, energy_used_kwh, decision_reason, constraint_hit)

### Food processing policies

Each farm selects a food processing policy strategy. Determines how harvested crop is split across processing pathways. Called daily via `food_policy.allocate(ctx)` during the simulation loop (harvest days only).

| Policy | Fresh | Packaged | Canned | Dried | Behavior |
| --- | --- | --- | --- | --- | --- |
| `all_fresh` | 100% | 0% | 0% | 0% | Fixed split according to table |
| `maximize_storage` | 20% | 10% | 35% | 35% | Fixed split according to table |
| `balanced_mix` | 50% | 20% | 15% | 15% | Fixed split according to table |
| `market_responsive` | 30% or 65% | 20% or 15% | 25% or 10% | 25% or 10% | Binary switch: 65% fresh when price >= 80% reference, 30% fresh when price < 80% reference (see `policies.md` `market_responsive` policy) |

**Note**: All policies have an umbrella rule that forces the sale of food if storage becomes full OR food has reached its storage-life limit. Each harvest is tracked as a discrete tranche (FIFO) to ensure no food stays past its storage-life deadline. Execution order: (1) process today's harvest and update total storage, (2) check all tranches for expiry and overflow — forced sales happen here, (3) market policy runs on remaining inventory without forced-sale constraints. Storage life data is sourced from `data/parameters/crops/storage_spoilage_rates-toy.csv` (per crop, per product type).

**Context → Decision:** `FoodProcessingContext` → `ProcessingAllocation` (fresh_fraction, packaged_fraction, canned_fraction, dried_fraction, decision_reason)

### Market policies (selling)

Each farm selects a sales policy. Food processing policies entirely determine how food is processed (even when based on food prices). Market policies entirely determine when food is sold. The only exception is when food storage runs out and older stored food must be sold to make room for new food.

| Policy name | Behavior |
| --- | --- |
| `sell_all_immediately` | Once crops are processed into their final state (fresh, canned, etc.) they are immediately sold to market. Storage is only used to hold products before they are sold to market. This allows minimal storage space |
| `hold_for_peak` | Crops are processed according to food processing policy and the max amount is stored until prices are above a threshold. Default `price_threshold_multiplier = 1.2` (sell when price is 20% above average); configurable via scenario YAML |
| `adaptive` | Use sigmoid to determine portion of processed food to sell based on current price relative to historic prices. Default sigmoid: midpoint = 1.0 (price ratio), steepness = 5.0, min_sell = 0.2, max_sell = 1.0; configurable via scenario YAML |

**Context → Decision:** `MarketPolicyContext` → `MarketDecision` (sell_fraction, store_fraction, target_price_per_kg, decision_reason)

**Note:** Market policy context includes `product_type` (fresh, packaged, canned, dried) alongside `crop_name`, since each product type has distinct pricing and storage characteristics. Price data is loaded from per-product price files in `data/prices/`. Storage life data is loaded from `data/parameters/crops/storage_spoilage_rates-toy.csv` (or research variant), which provides `shelf_life_days` per crop-product-type combination.

### Energy policies

Each farm selects an energy source allocation strategy. The policy is instantiated during scenario loading and called daily in the simulation loop via `energy_policy.allocate_energy(ctx)`.

| Policy name | Behavior |
| --- | --- |
| `microgrid` | Uses wind and solar sources first with battery buffering, then uses generator. Behaves as if no grid connection. |
| `renewable_first` | Uses wind and solar sources first with battery buffering, then uses grid. Generator only used if grid goes down. |
| `all_grid` | All energy from grid. If renewable sources specified in configuration, solar or wind energy is sold directly to the grid (net metering) |

**Context → Decision:** `EnergyPolicyContext` → `EnergyAllocation` (use_renewables, use_battery, grid_import, grid_export, use_generator, sell_renewables_to_grid, battery_reserve_pct, decision_reason)

### Crop policies

Each farm selects a crop management strategy (irrigation adjustment). The policy is instantiated during scenario loading and called daily in the simulation loop via `crop_policy.decide(ctx)`. Controls how much water is requested based on crop conditions and environmental factors.

| Policy name | Behavior |
| --- | --- |
| `fixed_schedule` | Apply 100% of standard irrigation demand every day regardless of weather, crop stage, or water availability |
| `deficit_irrigation` | Controlled deficit strategy: full irrigation during initial/development stages, 80% during mid-season, 72% during late-season to conserve water while managing yield impacts |
| `weather_adaptive` | Temperature-responsive irrigation: +15% water on extreme heat days (>40°C), +5% on hot days (>35°C), -15% on cool days (<20°C) |

**Context → Decision:** `CropPolicyContext` → `CropDecision` (adjusted_demand_m3, demand_multiplier, decision_reason)

### Economic policies

Each farm selects a financial management strategy. The policy is instantiated during scenario loading and governs cash reserve targets and spending limits. Called monthly or when financial decisions are triggered.

> **MVP simplification — debt service:** Debt service is fixed monthly payments per financing profile. No accelerated repayment or debt pay-down policies in MVP.

| Policy name | Reserve target | Behavior |
| --- | --- | --- |
| `balanced_finance` | 3 months | Adaptive: sell inventory if <1 month reserves, hold otherwise |
| `aggressive_growth` | 1 month | Minimize cash reserves, sell inventory immediately |
| `conservative` | 6 months | Maintain high safety buffer, hold inventory |
| `risk_averse` | 6+ months | Maximize reserves, sell inventory immediately to lock in revenue |

> **MVP simplification:** Equipment maintenance and upgrades are included in annual OPEX. No separate investment mechanism in MVP.

**Configurable parameter:** `min_cash_months` — minimum months of operating costs to maintain as cash reserves. Set per-policy in scenario YAML under `community_policy_parameters`. Defaults: `aggressive_growth` = 1, `conservative` = 6, `risk_averse` = 3. Not applicable to `balanced_finance` (hardcoded 3-month target).

**Context → Decision:** `EconomicPolicyContext` → `EconomicDecision` (reserve_target_months, sell_inventory, decision_reason)


## 4. Metrics

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
