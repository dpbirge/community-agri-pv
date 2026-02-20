# Spec Audit Fix Plan

Fixes for all issues identified in the audit of `specs/structure.md`, `specs/simulation_flow.md`, `specs/policies.md`, and `specs/metrics_and_reporting.md`. Organized by file, with the recommended resolution for each issue.

**Scope:** Only the four audited spec files are modified. References to `calculations_*.md` are added as stubs where formulas are needed but live in other spec files.

---

## Fix 1 — CRITICAL: Water Energy Cost Double-Counting

**Problem:** `WaterAllocation.cost_usd` includes groundwater energy cost (`gw_cost_per_m3` uses `energy_price_per_kwh`). The energy dispatch also charges for the same energy via `E_water_system` flowing into `total_demand_kwh`. Step 7 sums both `water_cost` and `energy_cost`, double-counting the energy component of groundwater treatment.

**Recommendation:** Split water cost into two components: an **economic cost** (used inside the policy for source comparison) and a **cash cost** (used in accounting). The cash cost excludes the energy component because that cost is captured by the energy dispatch.

**File:** `specs/policies.md` — Water Policies, Decision (outputs) table

Add a new output field and clarify `cost_usd`:

```
| Field | Description |
| --- | --- |
| `groundwater_m3` | Volume allocated from treated groundwater |
| `municipal_m3` | Volume allocated from municipal supply |
| `energy_used_kwh` | Energy consumed for groundwater pumping + conveyance + treatment |
| `cost_usd` | Water cost excluding energy (municipal purchase + GW maintenance only). Used in daily accounting. |
| `economic_cost_usd` | Full economic cost including energy (for policy comparison logging only, NOT used in accounting) |
| `decision_reason` | Why this allocation was chosen |
| `constraint_hit` | Which physical constraint limited groundwater |
```

**File:** `specs/policies.md` — Shared logic: energy consumed and total cost

Replace:

```
cost_usd = (groundwater_m3 * gw_cost_per_m3) + (municipal_m3 * municipal_price_per_m3)
```

With:

```
# Economic cost (for policy source-comparison logic — NOT used in accounting)
economic_cost_usd = (groundwater_m3 * gw_cost_per_m3) + (municipal_m3 * municipal_price_per_m3)

# Cash cost (for daily accounting — excludes energy, which flows through dispatch)
cash_cost_per_m3 = gw_maintenance_per_m3
cost_usd = (groundwater_m3 * cash_cost_per_m3) + (municipal_m3 * municipal_price_per_m3)
```

**File:** `specs/simulation_flow.md` — Step 7, water_cost line

Replace:

```
water_cost = SUM(allocation.cost_usd) across all farms + community water cost
```

With:

```
water_cost_i = farm_allocations[farm].cost_usd  # maintenance + municipal only; energy is in dispatch
```

**Rationale:** The water policy still computes `economic_cost_usd` internally for cost-comparison logic (e.g., `cheapest_source` compares `gw_cost_per_m3` vs `municipal_price_per_m3`). But the accounting line uses `cost_usd` which excludes energy. All energy costs flow through the dispatch, eliminating double-counting. No policy logic changes — only what enters accounting.

---

## Fix 2 — CRITICAL: Rewrite Step 7 Daily Accounting as Per-Farm

**Problem:** Step 7 says `FOR each farm:` but the formulas compute community-wide totals (`SUM across all farms`, `dispatch_result.total_energy_cost`). These are not per-farm numbers.

**Recommendation:** Rewrite Step 7 to clearly separate **farm-specific costs**, **shared cost allocation**, and **per-farm totals**.

**File:** `specs/simulation_flow.md` — Step 7

Replace the entire Step 7 block with:

```
# --- Step 7: Daily Accounting ---

# 7a: Compute daily shared costs (community-level)
daily_shared_water_om = daily_infrastructure_om("water")  # water system O&M / 365
daily_shared_energy_om = daily_infrastructure_om("energy")
daily_shared_processing_om = daily_infrastructure_om("processing")
daily_admin_labor = annual_admin_labor_cost / 365
daily_debt_service = monthly_debt_service / days_in_current_month
daily_replacement = daily_replacement_reserve  # from pre-loop Step 13
daily_community_water_cost = community_water_allocation.cost_usd  # from Step 2b
daily_community_energy_cost = community_energy_cost  # from Step 3b

Total_daily_shared_opex = daily_shared_water_om + daily_shared_energy_om
                        + daily_shared_processing_om + daily_admin_labor
                        + daily_debt_service + daily_replacement
                        + daily_community_water_cost + daily_community_energy_cost

# 7b: Allocate shared costs to farms
FOR each farm:
    IF cost_allocation_method == "equal":
        allocated_shared_i = Total_daily_shared_opex / num_farms
    ELSE IF cost_allocation_method == "area_proportional":
        allocated_shared_i = Total_daily_shared_opex * (farm.plantable_area_ha / total_farming_area)
    ELSE IF cost_allocation_method == "usage_proportional":
        # Usage = farm's water_m3 + energy_kwh + processing_kg today,
        # normalized by community total
        farm_usage_i = (farm_water_m3_i / total_farm_water_m3)  # weighted average across resources
                     # Simplification for MVP: use water volume as the usage metric
        allocated_shared_i = Total_daily_shared_opex * farm_usage_i

# 7c: Compute per-farm costs and revenue
FOR each farm:
    # Farm-specific costs (NOT shared)
    water_cost_i = farm_allocations[farm].cost_usd  # maintenance + municipal (Fix 1)
    energy_cost_i = dispatch_result.total_energy_cost
                    * (farm_demand_kwh_i / total_demand_kwh)  # from Step 3b
    field_labor_cost_i = labor_hours_per_ha_per_day * wage_per_hour * farm.active_ha
    harvest_labor_cost_i = harvest_labor_hours_per_kg * wage_per_hour * farm_harvest_kg_today
    processing_labor_cost_i = processing_labor_hours_per_kg * wage_per_hour
                              * farm_processed_kg_today  # pro-rata by farm_shares
    input_cost_i = (annual_input_cost_per_ha * farm.active_ha) / 365
    storage_cost_i = SUM(
        tranche.kg * tranche.farm_shares[farm.id] * storage_cost_per_kg_per_day(tranche.product_type)
        for tranche in community_storage
    )

    farm_specific_cost_i = water_cost_i + energy_cost_i + field_labor_cost_i
                         + harvest_labor_cost_i + processing_labor_cost_i
                         + input_cost_i + storage_cost_i

    total_daily_cost_i = farm_specific_cost_i + allocated_shared_i

    # Revenue
    crop_revenue_i = farm's attributed share from pooled sales (Step 5)
    export_revenue_i = dispatch_result.export_revenue
                       * (farm_demand_kwh_i / total_demand_kwh)
    total_daily_revenue_i = crop_revenue_i + export_revenue_i

    # Update cash
    farm.current_capital_usd += total_daily_revenue_i - total_daily_cost_i
    IF farm.current_capital_usd < 0: Record warning in daily log

    # Append DailyRecord (see Fix 5 for dataclass definition)
```

---

## Fix 3 — CRITICAL: Multi-Crop Same-Day Capacity Sharing

**Problem:** Capacity clipping runs per crop independently, so two crops harvesting on the same day can each consume the full daily capacity.

**Recommendation:** Track remaining capacity across crops within the same harvest day.

**File:** `specs/simulation_flow.md` — Step 4.2 and Section 5.4

Replace the per-crop capacity clipping with a shared-capacity approach. In the daily loop Step 4.2, change:

```
FOR each crop in community_harvest_pool:
    ...
    Apply capacity clipping (shared post-processing, see Section 5.4)
```

To:

```
# Initialize remaining capacity for today (resets each harvest day)
remaining_capacity = copy(processing_capacities)  # {pathway: kg/day}

FOR each crop in community_harvest_pool:
    ...
    Apply capacity clipping against remaining_capacity (see Section 5.4)
    # After clipping, reduce remaining_capacity by actual allocated kg
    FOR each pathway in [packaged, canned, dried]:
        remaining_capacity[pathway] -= clipped_allocation_kg[pathway]
```

In Section 5.4, update the `clip_to_capacity` function signature and logic:

```
clip_to_capacity(harvest_yield_kg, allocation, remaining_capacities):
    FOR each pathway in [packaged, canned, dried]:
        allocated_kg = harvest_yield_kg * allocation[pathway]
        IF allocated_kg > remaining_capacities[pathway]:
            excess_kg = allocated_kg - remaining_capacities[pathway]
            allocation[pathway] = remaining_capacities[pathway] / harvest_yield_kg
            allocation.fresh += excess_kg / harvest_yield_kg
            allocation.decision_reason += "_capacity_clipped"
    RETURN allocation
```

---

## Fix 4 — CRITICAL: Forced Sales and Market Policy Must Run Daily

**Problem:** Steps 4.3 (forced sales, economic liquidation) and 5 (market policy) are nested under "Step 4: Food Processing (Harvest Days Only)," implying they only run on harvest days. Tranches can expire any day.

**Recommendation:** Split the daily loop into harvest-dependent and harvest-independent sections.

**File:** `specs/simulation_flow.md` — Daily Loop (Section 3)

Restructure:

```
# --- Step 4: Food Processing (Harvest Days Only) ---
IF any farm has a harvest today:
    Step 4.1: Collect per-farm harvest contributions
    Step 4.2: Apply food processing policy, capacity clipping, weight loss, create tranches
    Calculate E_processing for today's throughput

# --- Step 4.3: Forced Sales / Umbrella Rule (RUNS EVERY DAY) ---
# Economic policy liquidation check (runs daily, not just harvest days)
IF ANY(farm.pending_inventory_liquidation for farm in farms) == True:
    Sell all tranches in community_storage at current market prices
    Attribute revenue per tranche.farm_shares
    Clear community_storage
    Reset pending_inventory_liquidation flags

# Expiry and overflow forced sales (runs daily)
Call check_forced_sales(community_storage, current_date) -> forced_sale_list
FOR each forced sale:
    Sell at current market price
    Attribute revenue per crop to farms
    Remove tranche from community storage

# --- Step 5: Market Policy (RUNS EVERY DAY on existing inventory) ---
IF community_storage is not empty:
    FOR each product_type in community storage (after forced sales):
        FOR each crop with inventory of this product_type:
            Assemble MarketPolicyContext
            Call market_policy.decide(ctx) -> MarketDecision
            ...
```

Add a note clarifying: "Steps 4.3 and 5 execute every simulation day regardless of whether a harvest occurs. Only Steps 4.1 and 4.2 (harvest intake and processing) are conditional on a harvest day."

---

## Fix 5 — MAJOR: Define DailyRecord Dataclass

**Problem:** `DailyRecord` is referenced but never defined.

**Recommendation:** Add Section 12.13 to simulation_flow.md.

**File:** `specs/simulation_flow.md` — new Section 12.13

```
### 12.13 DailyRecord

DailyRecord:
    date: date
    farm_id: str

    # Water (from Step 2)
    groundwater_m3: float
    municipal_m3: float
    water_cost_usd: float           # Cash cost only (maintenance + municipal; Fix 1)
    water_energy_kwh: float         # Energy consumed for GW treatment

    # Energy (from Step 3, attributed per Step 3b)
    energy_demand_kwh: float        # This farm's share of total demand
    energy_cost_usd: float          # Attributed share of dispatch cost
    export_revenue_usd: float       # Attributed share of grid export revenue

    # Crop (from Steps 1, 4)
    irrigation_demand_m3: float     # Adjusted demand from crop policy
    harvest_kg: float               # Raw harvest yield (0 on non-harvest days)
    processed_kg: float             # Output kg after weight loss (0 on non-harvest days)

    # Revenue (from Step 5)
    crop_revenue_usd: float         # Farm's attributed sales revenue today

    # Costs (from Step 7)
    farm_specific_cost_usd: float   # Water + energy + labor + inputs + storage
    allocated_shared_cost_usd: float # Farm's share of community shared OPEX
    total_cost_usd: float           # farm_specific + allocated_shared
    total_revenue_usd: float        # crop_revenue + export_revenue
    net_income_usd: float           # total_revenue - total_cost
    cash_position_usd: float        # Farm cash after today's transactions
```

---

## Fix 6 — MAJOR: Cost Allocation Timing and Integration

**Problem:** Section 8 defines allocation methods but doesn't specify when they run or how they integrate with Step 7.

**Recommendation:** Shared cost allocation runs **daily** as part of Step 7, using the day's actual costs and the configured allocation method.

**File:** `specs/simulation_flow.md` — Section 8

Add a new subsection:

```
### 8.4 Allocation Timing

Shared cost allocation executes daily as part of Step 7 (see Step 7a and 7b).
Each day's Total_daily_shared_opex is computed and allocated to farms using the
configured cost_allocation_method. This produces a daily per-farm
`allocated_shared_cost_usd` that enters the DailyRecord.

For usage-proportional allocation, the usage metric is the farm's share of
today's total farm water consumption (groundwater_m3 + municipal_m3). This is
the simplest per-day usage proxy. Monthly or yearly usage-proportional
allocation would require accumulation periods, which adds complexity without
meaningful accuracy improvement at the daily time step.

For equal and area-proportional allocation, the allocation is deterministic
and does not depend on daily usage.
```

Also add to Section 8.2 a note: "Infrastructure O&M costs (`water_system_om`, `energy_system_om`, `processing_system_om`) are annual values from financing profiles. They are divided by 365 to produce daily rates."

---

## Fix 7 — MAJOR: Storage Cost Attribution

**Problem:** Section 5.10 references `farm_storage` but storage is community-level.

**File:** `specs/simulation_flow.md` — Section 5.10

Replace:

```
daily_storage_cost = SUM over all tranches in farm_storage:
    tranche.kg * storage_cost_per_kg_per_day(tranche.product_type)
```

With:

```
# Storage is community-level. Each farm's storage cost is computed from
# its ownership share across all community tranches.
daily_storage_cost_farm_i = SUM over all tranches in community_storage:
    tranche.kg * tranche.farm_shares[farm_i.id] * storage_cost_per_kg_per_day(tranche.product_type)

# If farm_i.id is not in tranche.farm_shares (farm didn't contribute to this tranche),
# its share is 0 and contributes nothing to the sum.
```

Add a note: "Storage cost rates are loaded from `data/parameters/costs/storage_costs-toy.csv` with schema: `product_type, cost_usd_per_kg_per_day`."

---

## Fix 8 — MAJOR: Community Water Capacity Sharing

**Problem:** Community water demand (Step 2b) draws from the same wells/treatment as farms but isn't included in the Phase 2 pro-rata check.

**Recommendation:** Include community demand in the Phase 2 capacity check by treating it as an additional allocation.

**File:** `specs/simulation_flow.md` — Step 2, Phase 2

Replace the Phase 2 check with:

```
# Phase 2: Check aggregate demand (farms + community) against available supply
total_gw_demand_farms = sum(alloc.groundwater_m3 for alloc in farm_allocations.values())

# Pre-compute community GW demand (simplified: run community water policy early
# to estimate its GW request, then include in the capacity check)
community_water_demand_m3 = household_water_m3 + community_bldg_water_m3
community_water_allocation_est = community_water_policy.allocate_water(
    WaterPolicyContext(demand_m3=community_water_demand_m3, ...)
)
total_gw_demand = total_gw_demand_farms + community_water_allocation_est.groundwater_m3

available_supply = water_storage_m3 + total_treatment_capacity
IF total_gw_demand > available_supply:
    scale_factor = available_supply / total_gw_demand
    # Apply pro-rata to ALL consumers (farms AND community)
    FOR each farm:
        # ... existing scaling logic ...
    community_water_allocation_est.groundwater_m3 *= scale_factor
    # Redirect community shortfall to municipal
    ...
```

Then Step 2b uses the (possibly scaled) community allocation rather than re-computing independently.

---

## Fix 9 — MAJOR: Economic Policy Liquidation Runs Daily

**Problem:** The `pending_inventory_liquidation` flag is only checked inside the harvest-day block.

**Resolution:** Already addressed by Fix 4 (restructuring Steps 4.3 and 5 to run daily). No additional changes needed beyond Fix 4.

---

## Fix 10 — MAJOR: Quota Policy Scope Clarification

**Problem:** Unclear whether `annual_quota_m3` and cumulative trackers are per-farm or community-wide.

**Recommendation:** Per-farm quotas, with community-level tracking for reporting.

**File:** `specs/policies.md` — `quota_enforced` policy

Add before the pseudocode:

```
**Scope:** `annual_quota_m3` is the per-farm extraction limit. Each farm tracks its own
`cumulative_gw_year_m3` and `cumulative_gw_month_m3` against its own quota. The community
total is the sum of all farm quotas (annual_quota_m3 * num_farms) but is not enforced
as a separate constraint — farm-level enforcement is sufficient because all farms use
the same quota when set via collective_farm_override.
```

**File:** `specs/simulation_flow.md` — AquiferState (12.4)

Add clarification:

```
# cumulative_gw_month_m3 and cumulative_gw_year_m3 are COMMUNITY-LEVEL totals
# (sum of all farm extractions). Used for aquifer depletion tracking and reporting.
# The quota_enforced policy uses PER-FARM trackers stored in each farm's water
# policy context, not these community-level fields.
```

**File:** `specs/simulation_flow.md` — FarmState (12.2)

Add new fields:

```
cumulative_gw_month_m3: float   # This farm's monthly extraction; init = 0; reset monthly
cumulative_gw_year_m3: float    # This farm's yearly extraction; init = 0; reset yearly
```

---

## Fix 11 — MAJOR: MarketPolicyContext Clarification for Multiple Tranches

**Problem:** When multiple tranches exist for the same crop+product_type, `days_in_storage` and `storage_capacity_kg` are ambiguous.

**File:** `specs/policies.md` — Market Policies, Context (inputs) table

Update field descriptions:

```
| Field | Description |
| --- | --- |
| `days_in_storage` | Age of the OLDEST tranche of this crop+product_type (days since harvest). Represents the most urgent inventory. |
| `storage_life_days` | Maximum storage duration for this crop+product_type (from storage_spoilage_rates CSV) |
| `available_kg` | Total kg across ALL tranches of this crop+product_type in community storage |
| `storage_capacity_kg` | REMAINING storage capacity for this product_type: capacity - currently_stored_kg (across all crops of this product_type) |
```

---

## Fix 12 — MAJOR: Per-Farm CAPEX Share

**Problem:** `capex_share` per farm is referenced but never defined.

**Recommendation:** CAPEX is allocated using the same `cost_allocation_method` as OPEX.

**File:** `specs/simulation_flow.md` — Pre-Loop Step 12

Add after the existing Step 12 pseudocode:

```
# Allocate cash CAPEX to individual farms
FOR each farm:
    IF cost_allocation_method == "equal":
        farm.capex_share = capex_cash_outflow / num_farms
    ELSE IF cost_allocation_method == "area_proportional":
        farm.capex_share = capex_cash_outflow * (farm.plantable_area_ha / total_farming_area)
    ELSE IF cost_allocation_method == "usage_proportional":
        # At initialization, no usage data exists yet. Fall back to area-proportional.
        farm.capex_share = capex_cash_outflow * (farm.plantable_area_ha / total_farming_area)

    farm.current_capital_usd = farm.starting_capital_usd - farm.capex_share
```

Update Step 12b validation to be per-farm:

```
FOR each farm:
    IF farm.capex_share > farm.starting_capital_usd:
        RAISE ConfigurationError(
            f"Farm {farm.id}: insufficient starting capital ({farm.starting_capital_usd}) "
            f"to cover CAPEX share ({farm.capex_share})."
        )
```

---

## Fix 13 — MAJOR: Debt Tracking

**Problem:** No mechanism for tracking outstanding principal, remaining terms, or principal reduction over time.

**Recommendation:** Add a `DebtSchedule` dataclass and compute amortization at initialization.

**File:** `specs/simulation_flow.md` — New Section 12.14

```
### 12.14 DebtSchedule

DebtSchedule:
    subsystem: str                  # e.g., "water_treatment", "pv", "battery"
    principal: float                # Original loan amount (capital_cost for this subsystem)
    annual_interest_rate: float     # From financing_profiles CSV
    loan_term_months: int           # From financing_profiles CSV
    monthly_payment: float          # Fixed payment (standard amortization formula)
    remaining_principal: float      # Init = principal; decremented monthly
    remaining_months: int           # Init = loan_term_months; decremented monthly
    start_date: date                # Simulation start date
```

**File:** `specs/simulation_flow.md` — EconomicState (12.7)

Add:

```
    debt_schedules: list[DebtSchedule]  # One per loan-financed subsystem
    total_debt_usd: float               # SUM(ds.remaining_principal for ds in debt_schedules)
                                        # Updated monthly when payments are made
```

**File:** `specs/simulation_flow.md` — Step 9.1 (Monthly Boundaries)

Add to monthly operations:

```
# Update debt schedules
FOR each debt_schedule in economic_state.debt_schedules:
    IF debt_schedule.remaining_months > 0:
        interest_portion = debt_schedule.remaining_principal * (debt_schedule.annual_interest_rate / 12)
        principal_portion = debt_schedule.monthly_payment - interest_portion
        debt_schedule.remaining_principal -= principal_portion
        debt_schedule.remaining_months -= 1
economic_state.total_debt_usd = SUM(ds.remaining_principal for ds in debt_schedules)
```

---

## Fix 14 — MAJOR: Add Simulation Period to Configuration Schema

**Problem:** `start_date` and `end_date` appear in SimulationState but are not in structure.md.

**File:** `specs/structure.md` — Section 2 (System configurations)

Add a new subsection after Economic configuration:

```
### Simulation period

- start_date: YYYY-MM-DD (first simulation day)
- end_date: YYYY-MM-DD (last simulation day, inclusive)
- time_step: [daily] (MVP supports daily only; reserved for future sub-daily resolution)

**Note:** The simulation period determines how many years of precomputed data are needed.
Price data, weather data, and PV/wind output data must cover the full simulation period.
If data is shorter than the simulation period, the last available value is used for
extrapolation (see Section 11.4 NaN Propagation Prevention).
```

---

## Fix 15 — MINOR: Stub Formulas for Cross-Referenced Calculations

**Problem:** Several formulas reference `calculations_*.md` which are outside audit scope.

**Recommendation:** Add stubs to `specs/simulation_flow.md` Section 7.4 and `specs/metrics_and_reporting.md` so the four files are self-contained for code generation.

**File:** `specs/simulation_flow.md` — Section 7.4, after `calculate_fuel` call

Add inline stub:

```
# Generator fuel consumption (from calculations_energy.md):
# Fuel consumption follows a linear model based on load fraction:
#   fuel_L_per_hr = a * P_rated_kw + b * P_output_kw
# Where a = 0.0246 L/kW/hr (no-load coefficient), b = 0.0845 L/kW/hr (load coefficient)
# Source: Typical diesel genset fuel curves (Caterpillar/Cummins data sheets)
#   runtime_hours = generator_used_kwh / generator_capacity_kw  (assumes constant output)
#   fuel_L = (a * generator_capacity_kw + b * generator_used_kwh / runtime_hours) * runtime_hours
```

**File:** `specs/simulation_flow.md` — Section 7.4, battery SOC update

Add explicit formulas after the dispatch algorithm:

```
# Battery SOC update (after dispatch):
# Discharge: soc -= (battery_discharged_kwh / eta_discharge) / battery_capacity_kwh
# Charge:    soc += (battery_charged_kwh * eta_charge) / battery_capacity_kwh
# Clamp:     soc = clamp(soc, SOC_min, SOC_max)
```

**File:** `specs/simulation_flow.md` — Section 5.2, after `water_stress_factor`

Add:

```
# K_y (yield response factor) is crop-specific, loaded from
# data/parameters/crops/crop_coefficients-toy.csv, column: yield_response_factor
# Typical values: tomato 1.05, potato 1.10, onion 1.0, kale 0.95, cucumber 1.10
# Source: FAO Irrigation and Drainage Paper 33, Table 1
```

**File:** `specs/simulation_flow.md` — Section 4.3, after `get_marginal_tier_price` call

Add:

```
# get_marginal_tier_price(cumulative_m3, tiers):
#   FOR each tier in tiers (sorted by tier number ascending):
#       IF cumulative_m3 < tier.max_m3_per_month:
#           RETURN tier.price_egp_per_m3 / exchange_rate_egp_per_usd
#   # If consumption exceeds all tiers, use the highest tier's price
#   RETURN tiers[-1].price_egp_per_m3 / exchange_rate_egp_per_usd
#
# Wastewater surcharge is applied OUTSIDE this function:
#   total_water_bill *= (1 + wastewater_surcharge_pct / 100)
```

---

## Fix 16 — MINOR: Data File Schema Stubs

**Problem:** Data file column schemas are not provided for many referenced files.

**Recommendation:** Add a new subsection to `specs/structure.md` listing the minimum required schemas.

**File:** `specs/structure.md` — New Section 4: Data File Schemas (Minimum Required)

```
## 4. Data File Schemas (Minimum Required)

These schemas define the minimum columns needed by the simulation engine. Actual data
files may contain additional columns for documentation or analysis purposes.

### Equipment and infrastructure

**`data/parameters/equipment/processing_equipment-toy.csv`:**
`pathway, equipment_type, throughput_kg_per_day, energy_kwh_per_kg, availability_factor`

**`data/parameters/equipment/equipment_lifespans-toy.csv`:**
`component, lifespan_years, replacement_cost_pct`

**`data/parameters/equipment/wells-toy.csv`:**
`parameter, value` (key-value pairs: pump_efficiency, specific_yield, etc.)

### Costs

**`data/parameters/costs/storage_costs-toy.csv`:**
`product_type, cost_usd_per_kg_per_day`

**`data/parameters/costs/operating_costs-toy.csv`:**
`system, annual_om_usd` (water_treatment, pv, wind, battery, generator, processing)

**`data/parameters/costs/input_costs-toy.csv`:**
`crop, annual_cost_usd_per_ha`

### Economic

**`data/parameters/economic/financing_profiles-toy.csv`:**
`financing_status, capex_cost_multiplier, annual_interest_rate, loan_term_years, om_included`

### Crops

**`data/parameters/crops/crop_coefficients-toy.csv`:**
`crop, kc_initial, kc_mid, kc_end, season_length_days, yield_response_factor`

**`data/parameters/crops/processing_specs-toy.csv`:**
`crop, product_type, weight_loss_pct`

**`data/parameters/crops/storage_spoilage_rates-toy.csv`:**
`crop_name, product_type, shelf_life_days`

### Labor

**`data/parameters/labor/labor_rates-toy.csv`:**
`activity, hours_per_unit, unit, wage_usd_per_hour`
Activities: field_work (unit: ha/day), harvest (unit: kg), processing (unit: kg),
admin (unit: year, representing annual overhead hours)

### Prices

**`data/prices/crops/<crop>-toy.csv`:**
`date, price_usd_per_kg` (daily farmgate price; also used as fresh product price)

**`data/prices/processed/<crop>_<product_type>-toy.csv`:**
`date, price_usd_per_kg` (daily processed product price)

**`data/prices/diesel/diesel-toy.csv`:**
`date, price_usd_per_L`

### Water treatment

**`data/parameters/water/treatment_kwh_per_m3-toy.csv`:**
`salinity_level, treatment_kwh_per_m3` (rows: low, moderate, high)
```

---

## Fix 17 — MINOR: Reference Farmgate Price Definition

**Problem:** `market_responsive` food policy uses "reference farmgate price" without specifying how to derive a single number from a price time series.

**File:** `specs/policies.md` — `market_responsive` policy

Replace:

```
reference_price = lookup crop reference price from data file
```

With:

```
# Reference farmgate price: the MEAN of the crop's fresh price time series
# across the full simulation period. Computed once at scenario load time and
# cached per crop.
reference_price = MEAN(all prices in data/prices/crops/<crop>-toy.csv)
```

---

## Fix 18 — MINOR: avg_price_per_kg Rolling Window Edge Case

**File:** `specs/policies.md` — Market Policies, Context (inputs) table, `avg_price_per_kg` row

Append to description:

```
When fewer than 12 months of price data precede the current date, use all
available months as the window. For the very first simulation day, use the
full time series mean as the initial average.
```

---

## Fix 19 — MINOR: Aquifer Depletion Effect on Extraction

**File:** `specs/simulation_flow.md` — Section 9.2 (Yearly Boundaries), item 2

Add after the drawdown computation:

```
# If aquifer is fully depleted, disable groundwater extraction
IF remaining_volume_m3 <= 0:
    remaining_volume_m3 = 0
    max_groundwater_m3 = 0  # No extraction possible; all demand goes to municipal
    LOG warning: "Aquifer fully depleted. All water demand shifted to municipal."
```

---

## Fix 20 — MINOR: Water Storage Clarification

**Problem:** Comment says storage never increases above initial fill, but formula allows it.

**File:** `specs/simulation_flow.md` — Step 2 Phase 3

Replace the contradictory comment:

```
# Storage CAN increase above its initial 50% fill level if treatment output
# exceeds farm demand on low-demand days. The clamp ensures it never exceeds
# total capacity. This is physically correct: the treatment plant may run at
# capacity even when farm demand is low (e.g., rainy day with no irrigation),
# filling storage for future high-demand days.
```

---

## Fix 21 — MINOR: Distinguish Processing Throughput from Storage Capacity for Fresh

**Problem:** Pre-loop Step 6 sets `capacities["fresh"] = float('inf')` (processing throughput — fresh requires only washing/sorting, so throughput is unlimited). But `structure.md` Section 2 maps `fresh_food_packaging.storage_capacity_kg_total` to `storage_capacities["fresh"]` (finite storage limit). Both use similar dict structures and the key `"fresh"`, but represent fundamentally different constraints: rate (kg/day throughput) vs inventory (kg total stored). An implementer could easily confuse or merge them.

**Recommendation:** Rename the processing throughput dict to `processing_throughput_kg_per_day` and keep the storage dict as `storage_capacities_kg`. Use distinct names everywhere these are referenced.

**File:** `specs/simulation_flow.md` — Pre-Loop Step 6

Replace:

```
FOR each pathway in [packaged, canned, dried]:
    equipment_items = load equipment data for this pathway
    capacities[pathway] = SUM(
        item.throughput_kg_per_day * item.availability_factor
        for item in equipment_items
    )
# Fresh has no practical capacity limit (Section 5.4)
capacities["fresh"] = float('inf')
```

With:

```
# Processing THROUGHPUT limits (kg/day — how much can be processed per day)
# This is distinct from storage capacity (kg total — how much can be stored at once)
processing_throughput_kg_per_day = {}
FOR each pathway in [packaged, canned, dried]:
    equipment_items = load equipment data for this pathway
    processing_throughput_kg_per_day[pathway] = SUM(
        item.throughput_kg_per_day * item.availability_factor
        for item in equipment_items
    )
# Fresh has no practical throughput limit (washing/sorting is not a bottleneck)
processing_throughput_kg_per_day["fresh"] = float('inf')

# Storage CAPACITY limits (kg total — how much can be held in inventory at once)
# Loaded from food processing system configuration in structure.md
storage_capacities_kg = {
    "fresh": scenario.food_processing_system.fresh_food_packaging.storage_capacity_kg_total,
    "packaged": scenario.food_processing_system.packaging.storage_capacity_kg_total,
    "canned": scenario.food_processing_system.canning.storage_capacity_kg_total,
    "dried": scenario.food_processing_system.drying.storage_capacity_kg_total,
}
```

**File:** `specs/simulation_flow.md` — Section 5.4 (Capacity Clipping)

Replace all references to `capacities` with `processing_throughput_kg_per_day`:

```
clip_to_capacity(harvest_yield_kg, allocation, remaining_throughput):
    # Clips against daily PROCESSING THROUGHPUT, not storage capacity.
    # Storage overflow is handled separately in Section 5.8 (FIFO forced sales).
    FOR each pathway in [packaged, canned, dried]:
        allocated_kg = harvest_yield_kg * allocation[pathway]
        IF allocated_kg > remaining_throughput[pathway]:
            excess_kg = allocated_kg - remaining_throughput[pathway]
            allocation[pathway] = remaining_throughput[pathway] / harvest_yield_kg
            allocation.fresh += excess_kg / harvest_yield_kg
            allocation.decision_reason += "_capacity_clipped"
    RETURN allocation
```

**File:** `specs/simulation_flow.md` — Section 5.8 (FIFO Forced Sales)

Ensure the overflow check uses `storage_capacities_kg`, not the throughput dict:

```
check_forced_sales(community_storage, current_date, storage_capacities_kg):
    ...
    # 2. Overflow check: if total stored kg exceeds STORAGE CAPACITY, sell oldest first
    FOR product_type in ["fresh", "packaged", "canned", "dried"]:
        total_stored = sum(t.kg for t in community_storage if t.product_type == product_type)
        capacity = storage_capacities_kg[product_type]
        ...
```

**File:** `specs/simulation_flow.md` — SimulationState (Section 12.1)

Replace:

```
processing_capacities: dict[str, float]  # {pathway: kg/day} from pre-loop Step 6
```

With:

```
processing_throughput_kg_per_day: dict[str, float]  # {pathway: kg/day} from pre-loop Step 6
storage_capacities_kg: dict[str, float]             # {product_type: kg total} from pre-loop Step 6
```

---

## Summary of Changes by File

| File | Fixes Applied |
|------|--------------|
| `specs/policies.md` | 1 (water cost split), 10 (quota scope), 11 (market context), 17 (reference price), 18 (avg_price edge case) |
| `specs/simulation_flow.md` | 1 (accounting line), 2 (Step 7 rewrite), 3 (capacity sharing), 4 (daily execution), 5 (DailyRecord), 6 (allocation timing), 7 (storage cost), 8 (community capacity), 10 (per-farm trackers), 12 (CAPEX share), 13 (debt tracking), 14 (sim period), 15 (formula stubs), 19 (aquifer depletion), 20 (storage comment), 21 (throughput vs storage naming) |
| `specs/structure.md` | 14 (simulation period), 16 (data schemas) |
| `specs/metrics_and_reporting.md` | No changes needed |
