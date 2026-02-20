# Simulation Flow Specification

## 1. Overview

This document specifies the complete order of operations, decision flows, and calculation pipelines for the Layer 3 daily simulation loop. It serves as the authoritative reference for how the simulation proceeds from day to day, how policies integrate with physical calculations, and how data flows between subsystems.

The `structure.md`, `policies.md`, and `calculations.md` documents define WHAT exists (structure), WHY decisions are made (policies), and HOW calculations work (calculations), this document defines the SEQUENCE and INTEGRATION of those elements during execution.

**Source documents:**

- `structure.md` -- Configuration schema and parameter definitions
- `policies.md` -- Policy decision logic and pseudocode
- `calculations.md` -- Calculation methodologies and formulas (see also calculations_crop.md, calculations_economic.md, calculations_energy.md, and calculations_water.md)

### Simulation Logic at a Glance

The simulation has four phases: **initialization**, a **daily loop**, **boundary operations** at month and year transitions, and **post-loop reporting**.

**Phase 1: Initialization** (runs once):

- Load the scenario configuration and precomputed physical data (weather, PV/wind output, crop irrigation demand). Calculate infrastructure capacities, financing costs, and community demand baselines. Initialize all state — water storage and battery SOC start at 50% of capacity.

**Phase 2: Daily loop** (for each day in the simulation period):

1. **Crop policy** — For each farm, look up base irrigation demand from precomputed data and let the crop policy adjust it (e.g., deficit irrigation, weather-adaptive scheduling).
2. **Water policy** — For each farm, allocate water between groundwater and municipal sources. Pro-rata scale if aggregate demand exceeds supply. Then allocate community (non-farm) water separately.
3. **Energy dispatch** — Sum all energy demands (water treatment, irrigation pumping, food processing from the previous day, households, community buildings) and dispatch through a merit-order algorithm: PV → wind → battery → grid → generator.
4. **Food processing** — On harvest days, pool farm harvests, apply the food processing policy (fresh/packaged/canned/dried split), clip to equipment capacity, apply weight loss, and create storage tranches with per-farm ownership shares.
5. **Market policy** — Check forced sales (expiry and storage overflow via FIFO), then let the market policy decide sell/store fractions for remaining inventory. Attribute revenue back to farms by tranche ownership.
6. **Economic policy** (monthly) — On the first day of each month, evaluate cash reserves and operating cost trends to set flags (e.g., sell inventory) that influence other policies.
7. **Daily accounting** — For each farm, aggregate costs (water, energy, labor, inputs, storage, replacement reserve) and revenue (crop sales, grid export). Update cash position and deduct debt service.

**Phase 3: Boundary operations**:

- *Monthly* — Snapshot monthly metrics from daily records, then reset monthly accumulators (groundwater tracking, tiered-pricing consumption counters).
- *Yearly* — Snapshot yearly metrics, update aquifer drawdown and pumping energy, apply equipment degradation (PV output, battery capacity), reinitialize crop planting schedules for dormant crops, reset yearly accumulators, and compute IRR/NPV.

**Phase 4: Post-loop reporting** (runs once after the final simulation day):

1. **Finalize partial periods** — The daily loop only triggers boundary snapshots on the first day of a new period, so the final month and year are never closed out during the loop. The post-loop phase flushes these incomplete periods, flagging them as partial.
2. **Value terminal inventory** — Remaining unsold storage tranches are valued at end-of-simulation market prices. This is not a sale — no revenue transaction occurs. The terminal value enters the NPV calculation as a salvage inflow.
3. **Compute metrics bottom-up** — Four stages, each depending on the previous: (1) per-farm yearly metrics (water, energy, crop, revenue, costs, financials), (2) community yearly metrics (cross-farm aggregation, distributional stats like Gini coefficient, resource depletion), (3) simulation-lifetime metrics (totals, averages over complete years, trends, volatility), (4) financial summary metrics (NPV, IRR, payback period, ROI, cost savings vs. government-purchased baseline).
4. **Resilience metrics** (Monte Carlo only) — Survivability statistics (survival rate, insolvency and crop failure probabilities), distributional outcomes (income percentiles, worst-case farmer), and sensitivity rankings with breakeven thresholds.
5. **Generate outputs** — Daily CSVs, monthly and yearly summaries, lifetime JSON, scenario echo for reproducibility, 6 plots and 2 tables per `metrics_and_reporting.md`, and Monte Carlo ensemble files when applicable.

---

## 2. Pre-Loop Initialization

Before the daily loop begins, the simulation performs a one-time setup. These steps execute exactly once, establishing the data environment, initial system state, and financial baseline from which daily simulation proceeds.

**Step 1.** Validate all required data files exist via registry.

**Step 2.** Load scenario configuration (Layer 2 output) via `load_scenario()`.

**Step 3.** Apply collective_farm_override policies to all farms:

```
# Stamp collective policies into each farm's policy slot
IF scenario.collective_farm_override exists:
    FOR each domain in collective_farm_override.policies:
        FOR each farm in scenario.farms:
            farm.policies[domain] = collective_farm_override.policies[domain]
            # Policy name AND parameters come from the collective level
            # Any per-farm setting for this domain is overwritten
```

This step ensures that when the community has agreed on a shared policy for a domain, every farm uses it regardless of what was specified at the farm level. Crop plans (crops, areas, planting dates) are never overwritten -- they are always per-farm. See `policies.md` (Policy levels) for the full three-tier hierarchy.

**Step 4.** Load all precomputed data libraries (Layer 1 output) via `SimulationDataLoader`.

**Step 5.** Calculate per-farm system constraints (e.g. well capacity, treatment throughput) via `calculate_system_constraints()`.

**Step 6.** Calculate processing capacities from equipment data files:

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

**Step 7.** Calculate community demand (daily constants):

- Household energy and water demand via `calculate_household_demand()`
- Community building energy and water demand (per-m² rates × configured areas from `community_structure.community_buildings` in settings)
- These daily baselines are loaded once and reused in every simulation day

**Step 8.** Initialize `SimulationState` with farm states, aquifer state, energy state, economic state.

**Step 9.** Set initial water storage to 50% of capacity.

**Step 10.** Set initial battery SOC to 50% of capacity.

**Step 11.** Compute infrastructure annual costs from financing profiles.

**Step 12.** Record initial CAPEX outflow for financial metrics. total_capex = SUM over all subsystems: capital_cost × capex_cost_multiplier (only for financing_status with capex_cost_multiplier > 0: purchased_cash).

```
# For loan-financed systems, CAPEX is not a cash outflow at time zero
# (the loan provides the capital). Instead, debt service payments are
# the cash outflows over the loan term. But for NPV/IRR calculation,
# the TOTAL capital cost (regardless of financing method) should be
# recorded as the "investment" being evaluated.

# Two perspectives:
# (a) Community cash flow perspective: Only record cash actually spent
#     at time zero (purchased_cash systems only). Loan-financed systems
#     show up as monthly debt service.
# (b) Investment analysis perspective: Record total capital deployed
#     regardless of financing source, to evaluate whether the investment
#     creates value.
#
# Record BOTH for different metrics:
economic_state.total_capex_invested = SUM(capital_cost) for all subsystems
economic_state.capex_cash_outflow = SUM(capital_cost * capex_cost_multiplier)

# For IRR/NPV: Use total_capex_invested as Initial_CAPEX
# For cash flow tracking: Deduct capex_cash_outflow from initial cash reserves
economic_state.initial_cash = SUM(farm.starting_capital_usd) - capex_cash_outflow
```

**Step 12b.** Allocate cash CAPEX to individual farms:

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

**Step 12c.** Validate starting capital covers cash CAPEX:

```
FOR each farm:
    IF farm.capex_share > farm.starting_capital_usd:
        RAISE ConfigurationError(
            f"Farm {farm.id}: insufficient starting capital ({farm.starting_capital_usd}) "
            f"to cover CAPEX share ({farm.capex_share})."
        )
```

**Step 13.** Compute annual equipment replacement reserve:

```
FOR each component in equipment_lifespans data:
    component_capex = lookup capital cost for this component
    annual_reserve_i = component_capex * (replacement_cost_pct / 100) / lifespan_years
total_annual_replacement_reserve = SUM(annual_reserve_i)
daily_replacement_reserve = total_annual_replacement_reserve / 365
```

**Step 14.** Set E_processing = 0 for Day 1 (no previous-day processing energy to dispatch).

**Step 15.** Initialize monthly accumulators:

```
cumulative_gw_month_m3 = 0
cumulative_monthly_community_water_m3 = 0
```

**Step 16.** Initialize per-crop contribution trackers:

```
FOR each farm:
    FOR each crop:
        contribution_kg[crop] = 0
```

**Step 17.** Economic policy first-month guard:

```
# On the first day of month 1, Step 6 has no prior month data.
# Skip economic policy execution when months_elapsed == 0.
# The first economic policy execution occurs on the first day of month 2.
```

---

## 3. Daily Simulation Loop: Order of Operations

Each simulation day executes the following steps in strict order. Steps are numbered to match the execution sequence defined in `policies.md`. Every step lists its inputs, the operation performed, and its outputs.

### Daily Loop (For Each Day in Simulation Period)

```
FOR each day in simulation_period:

    # --- Step 0: Retrieve Daily Conditions ---
    Retrieve weather data (temperature, irradiance, wind speed, ET0)
    Retrieve crop growth stages for all active crops
    Retrieve current prices (crop, energy, water, diesel)
    Retrieve 12-month rolling average price per crop/product_type from historical price data
        # Required by adaptive and hold_for_peak market policies (avg_price_per_kg).
        # Computed from price data files in data/prices/ (rolling 12-month mean),
        # not from runtime sales records. See policies.md Market Policy Context.
    Retrieve daily household energy demand (E_household) from precomputed `household.energy`
    Retrieve daily community building energy demand (E_community_bldg) from precomputed `community_buildings.energy`
    Retrieve daily household water demand from precomputed `household.water`
    Retrieve daily community building water demand from precomputed `community_buildings.water`
    Determine if today is a harvest day for any farm/crop
    Determine if today is the first day of a new month
    Determine if today is the first day of a new year

    # --- Step 1: Crop Policy (Per Farm) ---
    FOR each farm:
        FOR each active crop:
            Lookup base_demand_m3 from precomputed irrigation data
            Assemble CropPolicyContext
            Call crop_policy.decide(ctx) -> CropDecision
            adjusted_demand_m3 = CropDecision.adjusted_demand_m3
        Sum adjusted demands across crops -> farm_total_demand_m3

    # --- Step 2: Water Policy (Per Farm, Two-Phase) ---
    # Phase 1: Compute each farm's allocation independently
    farm_allocations = {}
    FOR each farm:
        Resolve municipal_price_per_m3 (see Section 4: Pricing Resolution)
        Resolve energy_price_per_kwh (see Section 4: Pricing Resolution)
        Assemble WaterPolicyContext with farm_total_demand_m3
        Call water_policy.allocate_water(ctx) -> WaterAllocation
        farm_allocations[farm] = allocation

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
        # Pro-rata scaling: each consumer receives a proportional share of available supply
        scale_factor = available_supply / total_gw_demand
        # Apply pro-rata to ALL consumers (farms AND community)
        FOR each farm:
            original_gw = farm_allocations[farm].groundwater_m3
            farm_allocations[farm].groundwater_m3 *= scale_factor
            farm_allocations[farm].energy_used_kwh *= scale_factor
            # Redirect groundwater shortfall to municipal so crops still get watered
            shortfall_m3 = original_gw - farm_allocations[farm].groundwater_m3
            farm_allocations[farm].municipal_m3 += shortfall_m3
            # Recalculate cost with scaled allocation using the shared cost formula:
            alloc = farm_allocations[farm]
            alloc.cost_usd = (alloc.groundwater_m3 * gw_cost_per_m3) + (alloc.municipal_m3 * municipal_price_per_m3)
            alloc.energy_used_kwh = alloc.groundwater_m3 * (pumping_kwh_per_m3 + conveyance_kwh_per_m3 + treatment_kwh_per_m3)
        community_water_allocation_est.groundwater_m3 *= scale_factor
        # Redirect community shortfall to municipal
        community_shortfall = community_water_demand_m3 - community_water_allocation_est.groundwater_m3
        community_water_allocation_est.municipal_m3 += community_shortfall

    # Phase 3: Apply allocations and update state (single storage update)
    total_gw_drawn_m3 = 0
    FOR each farm:
        allocation = farm_allocations[farm]
        Record water allocation (groundwater_m3, municipal_m3, cost_usd, energy_used_kwh)
        total_gw_drawn_m3 += allocation.groundwater_m3
        Update aquifer cumulative extraction tracking
        cumulative_gw_month_m3 += allocation.groundwater_m3
        cumulative_gw_year_m3 += allocation.groundwater_m3
        Append DailyWaterRecord

    # Treatment output: how much groundwater the treatment plant processes today.
    # Treatment runs at capacity when demand exists, producing water into storage.
    # When aggregate demand <= treatment capacity, treatment produces exactly
    # what was allocated. When demand > treatment capacity (pro-rata scenario),
    # treatment runs at full capacity and the excess draw comes from stored water.
    treatment_output_m3 = min(total_treatment_capacity, total_gw_drawn_m3)

    # Single community storage update (eliminates farm-order bias)
    # Inflow = today's treated groundwater output
    # Outflow = groundwater drawn by all farms from storage
    # Municipal water is delivered directly and does NOT pass through storage.
    water_storage_m3 = clamp(
        water_storage_m3 + treatment_output_m3 - total_gw_drawn_m3,
        0, water_storage_capacity_m3
    )
    # Storage CAN increase above its initial 50% fill level if treatment output
    # exceeds farm demand on low-demand days. The clamp ensures it never exceeds
    # total capacity. This is physically correct: the treatment plant may run at
    # capacity even when farm demand is low (e.g., rainy day with no irrigation),
    # filling storage for future high-demand days.

    # --- Step 2b: Community Water (Non-Farm) ---
    # Community water demand includes all non-farm users: households and community buildings.
    # Both are loaded from precomputed daily time-series (see Section 10.1).
    household_water_m3 = lookup from registry `household.water` for current_date
    community_bldg_water_m3 = SUM over building_types:
        lookup per-m² rate from registry `community_buildings.water` for current_date
        × configured area from community_structure.community_buildings in settings
    total_community_water_demand_m3 = household_water_m3 + community_bldg_water_m3
    Resolve community municipal_price_per_m3 (community pricing regime)
    Resolve community energy_price_per_kwh (community pricing regime)
    Assemble WaterPolicyContext with total_community_water_demand_m3
    Call community_water_policy.allocate_water(ctx) -> WaterAllocation
    Record community water allocation and costs

    # --- Step 3: Energy Policy and Dispatch (Community-Level) ---
    Aggregate all energy demand components:
        # Water-system energy: extracted from water policy outputs (already computed in Steps 2 and 2b)
        E_water_system = sum of allocation.energy_used_kwh across all farms + community water
            # This includes E_desal + E_pump + E_convey per farm (no double-counting)
            # For reporting decomposition:
            #   E_desal = groundwater_m3 * treatment_kwh_per_m3
            #   E_pump = groundwater_m3 * pumping_kwh_per_m3
            #   E_convey = groundwater_m3 * conveyance_kwh_per_m3
            # These sub-components are computed for metrics only, not re-added to demand
        E_irrigation_pump = sum of irrigation pressurization energy
            # irrigation_pressure_kwh_per_m3 * total_irrigation_m3 (all sources, not just GW)
        E_processing = sum of food processing energy (from Step 4, previous day)
        E_household = daily household electricity demand (from precomputed `household.energy`)
        E_community_bldg = daily community building electricity demand (from precomputed `community_buildings.energy`, scaled by building areas in settings)
        total_demand_kwh = E_water_system + E_irrigation_pump
                         + E_processing + E_household + E_community_bldg

    # Collect energy policy flags from all sources
    farm_allocations_energy = []
    FOR each farm:
        Assemble EnergyPolicyContext
        Call energy_policy.allocate_energy(ctx) -> EnergyAllocation
        farm_allocations_energy.append(EnergyAllocation)

    # Community energy policy (households + community buildings)
    Assemble EnergyPolicyContext for community demand
    Call community_energy_policy.allocate_energy(ctx) -> community_energy_allocation
    farm_allocations_energy.append(community_energy_allocation)

    # Combine flags: since dispatch is community-level, merge all allocation flags.
    # When collective_farm_override is set, all farms return identical flags and
    # this merge is a no-op. When policies differ, use MOST PERMISSIVE combination:
    combined_allocation = EnergyAllocation(
        use_renewables  = ANY(a.use_renewables for a in farm_allocations_energy),
        use_battery     = ANY(a.use_battery for a in farm_allocations_energy),
        grid_import     = ANY(a.grid_import for a in farm_allocations_energy),
        grid_export     = ANY(a.grid_export for a in farm_allocations_energy),
        use_generator   = ANY(a.use_generator for a in farm_allocations_energy),
        sell_renewables_to_grid = ALL(a.sell_renewables_to_grid for a in farm_allocations_energy),
        # sell_renewables_to_grid requires ALL sources to agree (if any wants self-consumption, don't export all)
        battery_reserve_pct = MIN(a.battery_reserve_pct for a in farm_allocations_energy),
        # Use lowest reserve to maximize battery availability for the community
        decision_reason = "combined_from_{n}_policies"
    )

    Call dispatch_energy(total_demand_kwh, combined_allocation, ...) -> DispatchResult
        (See Section 7: Energy Policy Integration)
    Record energy dispatch results (PV, wind, battery, grid, generator, curtailment)
    Update battery SOC
    Update battery EFC accumulator:
        daily_throughput_kwh = battery_charged_kwh + battery_discharged_kwh
        daily_efc = daily_throughput_kwh / (2 * battery_capacity_kwh)
        energy_state.efc_cumulative += daily_efc
    Apply battery self-discharge (after dispatch SOC update):
        IF allocation.use_battery:
            battery_soc -= battery_soc * self_discharge_rate_daily
            battery_soc = max(battery_soc, SOC_min)
            # self_discharge_rate_daily = 0.0005 (0.05%/day) for LFP
    Append DailyEnergyRecord

    # --- Step 3b: Per-Farm Energy Cost Attribution ---
    # Energy dispatch is community-level, but daily accounting (Step 7) needs
    # per-farm energy costs. Attribute dispatch costs proportional to each
    # consumer's share of total demand.
    #
    # Farm energy demand = farm's water_system_energy + farm's irrigation_pump_energy
    #                    + farm's share of processing energy (by harvest contribution)
    # Community energy demand = E_household + E_community_bldg + community water energy
    #
    # Attribution formula:
    #   farm_energy_cost_i = dispatch_result.total_energy_cost
    #                        * (farm_demand_kwh_i / total_demand_kwh)
    #   community_energy_cost = dispatch_result.total_energy_cost
    #                           * (community_demand_kwh / total_demand_kwh)
    #
    # Grid export revenue is attributed the same way:
    #   farm_export_revenue_i = dispatch_result.export_revenue
    #                           * (farm_demand_kwh_i / total_demand_kwh)
    #
    # Community energy cost flows into Total_shared_opex (see Section 8).

    # --- Step 4: Food Processing (Harvest Days Only) ---
    # Harvest yield is tracked per farm, but processing operates on the
    # pooled community harvest. Processing capacity and storage are shared
    # community resources (see policies.md, Food Processing Policies).
    IF any farm has a harvest today:
        # Step 4.1: Collect per-farm harvest contributions
        # Initialize fresh per-batch trackers (NOT the persistent contribution_kg)
        community_harvest_pool = {}  # {crop_name: total_kg} — reset each day
        batch_contributions = {}     # {crop_name: {farm_id: kg}} — per-batch only
        FOR each farm:
            FOR each crop with harvest today:
                Calculate harvest yield (see calculations_crop.md)
                IF harvest_yield_kg == 0: SKIP (zero-demand guard)
                Record farm.contribution_kg[crop] += harvest_yield_kg  # persistent lifetime tracker (for metrics only)
                community_harvest_pool.setdefault(crop, 0)
                community_harvest_pool[crop] += harvest_yield_kg
                batch_contributions.setdefault(crop, {})
                batch_contributions[crop][farm.id] = batch_contributions[crop].get(farm.id, 0) + harvest_yield_kg

        # Step 4.2: Apply food processing policy to pooled harvest per crop
        # Initialize remaining capacity for today (resets each harvest day)
        remaining_capacity = copy(processing_throughput_kg_per_day)  # {pathway: kg/day}

        FOR each crop in community_harvest_pool:
            pooled_kg = community_harvest_pool[crop]
            IF pooled_kg == 0: SKIP
            Assemble FoodProcessingContext with pooled_kg
            Call food_policy.decide(ctx) -> ProcessingAllocation
            Apply capacity clipping against remaining_capacity (see Section 5.4)
            # After clipping, reduce remaining_capacity by actual allocated kg
            FOR each pathway in [packaged, canned, dried]:
                remaining_capacity[pathway] -= clipped_allocation_kg[pathway]
            Apply weight loss per pathway
            Compute farm_shares = {farm_id: kg / pooled_kg for farm_id, kg in batch_contributions[crop].items()}
            Create StorageTranches for each product type with farm_shares (community-level)
            Calculate E_processing for today's throughput
            Add tranches to community storage inventory

    # --- Step 4.3: Forced Sales / Umbrella Rule (RUNS EVERY DAY) ---
    # Steps 4.3 and 5 execute every simulation day regardless of whether a harvest occurs.
    # Only Steps 4.1 and 4.2 (harvest intake and processing) are conditional on a harvest day.

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
                sell_fraction = MarketDecision.sell_fraction
                sold_kg = available_kg * sell_fraction
                sale_revenue = sold_kg * current_price_per_kg
                Update community storage inventory

                # Revenue attribution: tranche-level ownership
                FOR each tranche being sold:
                    FOR each farm_id, fraction in tranche.farm_shares:
                        farm.revenue += tranche_sale_revenue * fraction
                Record revenue by crop and product type

    # --- Step 6: Economic Policy (Per Farm, Monthly) ---
    IF today is first day of month AND months_elapsed > 0:
        FOR each farm:
            Compute months_of_reserves (trailing 12-month average opex)
            # Aggregate previous month's data directly from daily records
            # (no dependency on Step 8's monthly snapshot — see Fix 1.5)
            prev_month_revenue = SUM(daily_records where date.month == last_month).revenue
            prev_month_costs = SUM(daily_records where date.month == last_month).costs
            Assemble EconomicPolicyContext with prev_month_revenue, prev_month_costs
            Call economic_policy.decide(ctx) -> EconomicDecision
            Store sell_inventory flag in farm_state.pending_inventory_liquidation
            # This flag persists in simulation state across daily loop iterations.
            # Step 4.3 checks farm_state.pending_inventory_liquidation on harvest days.
            # When True: sell all inventory, then reset flag to False.

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

        # Append DailyRecord (see Section 12.13 for dataclass definition)

    # --- Step 8: Boundary Operations ---
    IF today is first day of new month:
        # Order matters: snapshot before reset to capture completed month's data
        1. Snapshot monthly metrics (aggregate from daily records for completed month)
        2. Reset monthly cumulative groundwater tracking
        3. Reset monthly community water consumption (for tiered pricing)

    IF today is first day of new year:
        Compute yearly metrics snapshot (see Section 9)
        Reset yearly cumulative groundwater tracking
        Update aquifer drawdown and effective pumping head
        Update PV degradation factor
        Update battery capacity degradation
        Reinitialize farm crops for new year planting schedule
```

### Processing Energy Timing Note

`E_processing` for today's harvest is computed during Step 4 but enters the energy dispatch in Step 3 of the NEXT day. This one-day lag is acceptable at a daily time-step and avoids circular dependency between food processing and energy dispatch within the same day.

---

## 4. Pricing Resolution Pipeline

This section documents the complete end-to-end chain for how prices are resolved before they reach policy contexts. This addresses the dual agricultural/community pricing regimes defined in `structure.md` and clarifies currency handling.

### 4.1 Currency Handling

All internal calculations use USD. All prices stored in data files may be in either USD or EGP. A configurable base-year exchange rate converts all EGP values to USD at data load time.

```
Value_USD = Value_EGP / exchange_rate_EGP_per_USD
```

The exchange rate is fixed for the simulation run (constant-year, real terms). It is set in the scenario configuration under `economics.exchange_rate_egp_per_usd`. This avoids mixing currencies during arithmetic and ensures all cost comparisons are consistent.

Data files containing EGP values (notably tiered water pricing and grid electricity tariffs) must be converted to USD during loading, not at each daily calculation.

### 4.2 Consumer Type Classification

Every water and energy demand is classified by consumer type before price resolution:


| Consumer Type  | Applies To                                              | Water Regime                 | Energy Regime                 |
| -------------- | ------------------------------------------------------- | ---------------------------- | ----------------------------- |
| `agricultural` | Farm irrigation, groundwater treatment, food processing | `water_pricing.agricultural` | `energy_pricing.agricultural` |
| `community`    | Households, community buildings, shared facilities      | `water_pricing.community`    | `energy_pricing.community`    |


The simulation loop determines consumer type based on the source of demand, not the policy. Farm water demand is always agricultural. All non-farm demand (households, community buildings) is always community.

### 4.3 Water Price Resolution

```
resolve_water_price(consumer_type, cumulative_monthly_m3):

    IF consumer_type == "agricultural":
        config = water_pricing.agricultural
        IF config.pricing_regime == "subsidized":
            base = config.subsidized.price_usd_per_m3
            escalation = config.subsidized.annual_escalation_pct  # 0 = flat
            years_elapsed = current_year - simulation.start_date.year
            RETURN base * (1 + escalation / 100) ^ years_elapsed
        ELSE:  # unsubsidized
            base = config.unsubsidized.base_price_usd_m3
            years_elapsed = current_year - simulation.start_date.year
            RETURN base * (1 + config.unsubsidized.annual_escalation_pct / 100) ^ years_elapsed

    IF consumer_type == "community":
        config = water_pricing.community
        IF config.pricing_regime == "subsidized":
            # Tiered pricing with monthly consumption tracking
            RETURN get_marginal_tier_price(cumulative_monthly_m3, config.subsidized.tier_pricing)
        ELSE:  # unsubsidized
            base = config.unsubsidized.base_price_usd_m3
            years_elapsed = current_year - simulation.start_date.year
            RETURN base * (1 + config.unsubsidized.annual_escalation_pct / 100) ^ years_elapsed
```

**Key behaviors:**

- Price escalation uses `years_elapsed = current_year - simulation.start_date.year`. No separate `base_year` parameter.
- `annual_escalation_pct = 0` means government-fixed flat pricing (no escalation). `annual_escalation_pct > 0` models inflation-adjusted price increases. This applies consistently to both water and energy pricing.
- Agricultural water: Flat rate with optional escalation (subsidized or unsubsidized). No tiered pricing.
- Community water (subsidized): Uses Egyptian-style progressive tiered brackets with monthly consumption tracking. The `cumulative_monthly_m3` counter resets on the first day of each month. The `get_marginal_tier_price()` function returns the price of the NEXT unit of consumption, which is the relevant price for policy cost comparisons.

```text
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

- Community water (unsubsidized): Flat rate with annual escalation.
- Wastewater surcharge applies to community tiered pricing only: `total_cost *= (1 + wastewater_surcharge_pct / 100)`.
- Agricultural and community pricing regimes are independent -- one can be subsidized while the other is not.

### 4.4 Energy Price Resolution

```
resolve_energy_price(consumer_type):

    IF consumer_type == "agricultural":
        config = energy_pricing.agricultural
        IF config.pricing_regime == "subsidized":
            base = config.subsidized.price_usd_per_kwh
            escalation = config.subsidized.annual_escalation_pct  # 0 = flat
        ELSE:
            base = config.unsubsidized.price_usd_per_kwh
            escalation = config.unsubsidized.annual_escalation_pct

    IF consumer_type == "community":
        config = energy_pricing.community
        IF config.pricing_regime == "subsidized":
            base = config.subsidized.price_usd_per_kwh
            escalation = config.subsidized.annual_escalation_pct
        ELSE:
            base = config.unsubsidized.price_usd_per_kwh
            escalation = config.unsubsidized.annual_escalation_pct

    years_elapsed = current_year - simulation.start_date.year
    RETURN base * (1 + escalation / 100) ^ years_elapsed
```

**Key behaviors:**

- Energy pricing follows the same escalation pattern as water pricing: `annual_escalation_pct = 0` for government-fixed flat rates, `> 0` for inflation-adjusted increases.
- Both agricultural and community energy pricing are flat base rates with optional annual escalation.
- Agricultural and community pricing regimes are independent.
- The energy price passed to the water policy context is always the agricultural rate (since farm water treatment is an agricultural activity).
- The energy price used for community demand is the community rate.

### 4.5 Grid Export Pricing

Grid export revenue uses a net metering ratio applied to the grid import price:

```
export_price_per_kwh = grid_import_price * net_metering_ratio
```

- `net_metering_ratio`: Configurable, default 0.70 (reflecting Egypt's evolving net metering policy where export is compensated below retail import price).
- `grid_import_price`: The applicable energy price for the consumer type generating the export. For community-owned renewables serving agricultural load, use the agricultural energy price.
- Configuration: `energy_pricing.net_metering_ratio` (new parameter in scenario YAML).

### 4.6 Diesel Price Resolution

```
diesel_price_per_L = lookup from historical_diesel_prices data for current_date
```

Diesel is not split by consumer type. A single price applies to all generator fuel consumption.

---

## 5. Food Processing, Market, and Revenue Chain

This section documents the complete end-to-end flow from harvest to revenue, consolidating logic from `policies.md` Food Processing Policies and Market Policies, `calculations_crop.md`, and `calculations_economic.md`. The chain must be followed exactly to avoid double-counting revenue or mishandling weight loss.

### 5.1 Chain Overview

```
raw_yield_kg
    -> post-harvest handling loss (bruising, transport, rejected product)
    -> harvest_available_kg
    -> food policy split (fractions by pathway)
    -> capacity clipping (shared post-processing)
    -> weight loss per pathway (physical transformation)
    -> processed_output_kg per product type
    -> create StorageTranches
    -> check forced sales (umbrella rule: expiry + overflow)
    -> market policy decision (sell/store remaining)
    -> revenue calculation (sold_kg * price_per_kg per product type)
```

### 5.2 Harvest Yield Calculation

On harvest days, the raw yield is computed:

```
raw_yield_kg = Y_potential * water_stress_factor * yield_factor * effective_area_ha

water_stress_factor = 1 - K_y * (1 - water_ratio)
# K_y (yield response factor) is crop-specific, loaded from
# data/parameters/crops/crop_coefficients-toy.csv, column: yield_response_factor
# Typical values: tomato 1.05, potato 1.10, onion 1.0, kale 0.95, cucumber 1.10
# Source: FAO Irrigation and Drainage Paper 33, Table 1
water_ratio = clamp(cumulative_water_received / expected_total_water, 0, 1)
effective_area_ha = plantable_area_ha * area_fraction * percent_planted

# Post-harvest handling loss (bruising, transport damage, rejected product)
# Applied BEFORE the food processing split -- this is physical loss from
# harvesting and handling, not a processing transformation.
# On-site processing reduces transport losses compared to typical supply chains.
handling_loss_rate = post_harvest_handling_loss_rate  # from settings.yaml, default 0.05 (5%)
harvest_available_kg = raw_yield_kg * (1 - handling_loss_rate)
```

`harvest_available_kg` enters the food processing pipeline. The handling loss represents physical damage and rejection during harvesting, transport to the processing facility, and initial intake inspection. The default rate of 5% reflects reduced losses from on-site processing (FAO estimates 10-15% for typical developing-economy supply chains with external transport; the community's co-located processing facility eliminates most transport-related losses).

**Salinity yield reduction (configurable, off by default):**

The combined yield model in calculations_crop.md includes a `salinity_factor` for progressive salt accumulation in the root zone:

```
Y_actual = Y_potential * water_stress_factor * salinity_factor * yield_factor * effective_area_ha
```

By default, the salinity_factor is omitted (treated as 1.0). The user can enable salinity modeling by setting `enable_salinity_model: true` in `settings.yaml`. When disabled, the harvest yield formula above is used as-is. When enabled, the simulation must:

1. Track cumulative irrigation EC per crop across seasons (ECe accumulation model in calculations_crop.md)
2. Lookup crop salinity tolerance parameters from `crop_salinity_tolerance-toy.csv`
3. Compute salinity_factor = max(0, 1 - b * max(0, ECe - ECe_threshold) / 100)
4. Multiply into the harvest yield formula

The data file `data/parameters/crops/crop_salinity_tolerance-toy.csv` already exists with FAO-29 parameters for all 5 crops. This feature is deferred by default because the current data infrastructure does not yet support validated, site-specific salinity accumulation rates. For simulations exceeding 5 years with brackish groundwater sources, enabling the salinity model is recommended as salt accumulation becomes a first-order yield effect.

### 5.3 Food Policy Split

The food processing policy returns fractions that sum to 1.0:

```
ProcessingAllocation:
    fresh_fraction      # e.g., 0.50
    packaged_fraction   # e.g., 0.20
    canned_fraction     # e.g., 0.15
    dried_fraction      # e.g., 0.15
    decision_reason     # e.g., "balanced_mix_default"
```

### 5.4 Capacity Clipping (Shared Post-Processing)

After every food policy returns its target fractions, capacity clipping runs as a shared step. This is NOT part of any individual policy -- it is applied universally.

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

Fresh has no practical throughput limit. Processing throughput limits are calculated once at scenario load time from equipment configuration:

```
capacity_kg_per_day = sum(equipment.throughput_kg_per_day * equipment.availability_factor)
    for each equipment item in the pathway
```

`availability_factor` defaults to 0.90 (accounting for maintenance downtime).

### 5.5 Weight Loss and Processed Output

Each pathway has a crop-specific weight loss factor from `processing_specs-toy.csv`:

```
FOR each pathway:
    input_kg = harvest_yield_kg * clipped_fraction
    output_kg = input_kg * (1 - weight_loss_pct / 100)
```

Weight loss values (examples from data):


| Crop   | Fresh | Packaged | Canned | Dried |
| ------ | ----- | -------- | ------ | ----- |
| Tomato | 0%    | 3%       | 15%    | 88%   |
| Potato | 0%    | 3%       | 15%    | 78%   |


The `output_kg` is what enters storage and is eventually sold. Revenue is always based on `output_kg`, not `input_kg`.

Note: Weight loss here is the PROCESSING transformation (water removal, trimming).  
Post-harvest HANDLING losses (bruising, transport damage) are applied upstream in  
Section 5.2 before the food policy split. Fresh weight_loss_pct = 0% is correct  
because fresh produce undergoes no processing transformation.

### 5.6 Processing Energy Calculation

Processing energy is computed from actual throughput:

```
E_processing_today = SUM over pathways:
    input_kg[pathway] * energy_per_kg[pathway]
```

Where `energy_per_kg` is loaded from equipment parameter files (kWh/kg by processing type). This value feeds into the NEXT day's energy dispatch (see Section 3, Processing Energy Timing Note).

### 5.7 StorageTranche Dataclass

Each processed batch is tracked as a discrete tranche for FIFO inventory management:

```
StorageTranche:
    product_type: str       # "fresh", "packaged", "canned", "dried"
    crop_name: str          # e.g., "tomato"
    kg: float               # output_kg (after weight loss)
    harvest_date: date      # date of harvest
    expiry_date: date       # harvest_date + shelf_life_days
    sell_price_at_entry: float  # price at time of storage (for tracking, not for sale)
    farm_shares: dict       # {farm_id: fraction} ownership at creation time (sums to 1.0)
```

- `shelf_life_days` is loaded from `storage_spoilage_rates-toy.csv` (per crop, per product type).
- Tranches are stored in a list per farm, ordered by `harvest_date` (oldest first = FIFO).
- `expiry_date = harvest_date + timedelta(days=shelf_life_days)`

### 5.8 FIFO Forced Sales (Umbrella Rule)

The umbrella rule runs AFTER food processing updates storage for the day (Step 4.2), BEFORE the market policy runs (Step 5). It handles two conditions:

```
check_forced_sales(community_storage, current_date, storage_capacities_kg):
    forced_sales = []

    # 1. Expiry check: sell anything at or past expiry
    FOR tranche in community_storage (oldest first):
        IF current_date >= tranche.expiry_date:
            forced_sales.append(tranche)
            remove tranche from community_storage

    # 2. Overflow check: if total stored kg exceeds STORAGE CAPACITY, sell oldest first
    FOR product_type in ["fresh", "packaged", "canned", "dried"]:
        total_stored = sum(t.kg for t in community_storage if t.product_type == product_type)
        capacity = storage_capacities_kg[product_type]
        WHILE total_stored > capacity:
            oldest = first tranche of this product_type in community_storage
            overflow_kg = total_stored - capacity
            IF oldest.kg <= overflow_kg:
                forced_sales.append(oldest)
                total_stored -= oldest.kg
                remove oldest from community_storage
            ELSE:
                # Partial sale: split the tranche
                sold_portion = copy(oldest)
                sold_portion.kg = overflow_kg
                oldest.kg -= overflow_kg
                forced_sales.append(sold_portion)
                total_stored = capacity

    RETURN forced_sales
```

**Forced sale pricing:** Forced sales execute at the current market price for the crop+product_type combination. No discount is applied. The rationale is that the product is still within its usable window (expiry forces sale on the last day, not after spoilage).

### 5.9 Revenue Calculation

Revenue is calculated per sale event (both forced and voluntary):

```
sale_revenue = sold_kg * current_price_per_kg(crop_name, product_type)
```

Where `current_price_per_kg` is looked up from the appropriate price data file:

- Fresh: `data/prices/crops/` (farmgate prices)
- Packaged/Canned/Dried: `data/prices/processed/` (processed product prices)

Revenue is recorded by farm, by crop, and by product type. This enables separate reporting of fresh vs. processed revenue without double-counting, because each kg of harvest enters exactly one pathway and is sold exactly once.

**Tranche-level revenue attribution:** Because processing and selling operate on the pooled community inventory, revenue must be attributed back to individual farms. Each `StorageTranche` carries a `farm_shares` dict recording ownership at creation time:

```
# Revenue attribution: reads directly from the tranche being sold
FOR each farm_id, fraction in tranche.farm_shares:
    farm.revenue += sale_revenue * fraction
```

Attribution happens at the point of sale, not at harvest. The `farm_shares` dict is computed in Step 4.2 when the tranche is created, using the per-farm `contribution_kg` for that harvest batch (not a running lifetime accumulator). This ensures that ownership accurately reflects each batch's actual contributors, even if farm crop plans change between years.

### 5.10 Daily Storage Costs

Holding inventory incurs a daily storage cost:

```
# Storage is community-level. Each farm's storage cost is computed from
# its ownership share across all community tranches.
daily_storage_cost_farm_i = SUM over all tranches in community_storage:
    tranche.kg * tranche.farm_shares[farm_i.id] * storage_cost_per_kg_per_day(tranche.product_type)

# If farm_i.id is not in tranche.farm_shares (farm didn't contribute to this tranche),
# its share is 0 and contributes nothing to the sum.
```

Storage cost rates are loaded from `data/parameters/costs/storage_costs-toy.csv` with schema: `product_type, cost_usd_per_kg_per_day`. These costs are deducted daily in Step 7 (Daily Accounting).

---

## 6. Crop Lifecycle State Machine

This section specifies the complete algorithm for crop planting, growth stage tracking, harvest triggering, and replanting. This state machine is consulted in Step 0 (retrieve crop growth stages, determine harvest day) and drives Step 1 (crop policy irrigation demand).

### 6.1 Crop States

Each crop on each farm has exactly one active state at any time:

```
DORMANT -> INITIAL -> DEVELOPMENT -> MID_SEASON -> LATE_SEASON -> HARVEST_READY -> DORMANT
```

State definitions:

- **DORMANT:** No active growth cycle. No water demand. Waiting for next planting date.
- **INITIAL:** Seedling establishment. Kc = kc_initial (from crop_coefficients).
- **DEVELOPMENT:** Vegetative growth. Kc transitions linearly from kc_initial to kc_mid.
- **MID_SEASON:** Full canopy. Kc = kc_mid (peak water demand).
- **LATE_SEASON:** Maturation/senescence. Kc transitions linearly from kc_mid to kc_end.
- **HARVEST_READY:** Crop is mature. Harvest occurs on this day.

### 6.2 Growth Stage Duration

Stage durations are derived from the total `season_length_days` (from `crop_coefficients-toy.csv`) using FAO-56 standard proportions:

```
initial_days     = round(season_length_days * 0.15)
development_days = round(season_length_days * 0.25)
mid_season_days  = round(season_length_days * 0.40)
late_season_days = season_length_days - initial_days - development_days - mid_season_days
```

Example for tomato (season_length_days = 135):

- initial = 20, development = 34, mid_season = 54, late_season = 27

These proportions can be overridden per crop if a crop-specific stage duration file is provided. For MVP, the 15/25/40/20 split is adequate for all 5 crops.

### 6.3 Planting Date Resolution

Planting dates are specified per crop per farm as a list of MM-DD strings (e.g., `["02-15", "11-01"]`). Resolution rules:

1. On simulation start, resolve all planting dates to absolute dates within the simulation period.
2. For each crop, `planting_dates` are interpreted as SEQUENTIAL plantings on the SAME field area. Only one growth cycle is active at a time per crop per farm (see resolved flag 10.10).
3. A planting occurs on the specified date IF the crop is currently DORMANT. If the previous cycle has not completed (still in LATE_SEASON), the planting is DEFERRED to the day after harvest of the current cycle.
4. Mid-simulation start: If the simulation `start_date` falls between two planting dates, the crop begins in DORMANT state and waits for its next planting date. No partial-cycle initialization.
5. `percent_planted` applies to all plantings for that crop uniformly.

### 6.4 Daily State Transition Algorithm

```
FOR each farm:
    FOR each crop:
        IF crop.state == DORMANT:
            IF today matches a planting_date for this crop:
                crop.state = INITIAL
                crop.days_in_stage = 0
                crop.cycle_start_date = today
                crop.cumulative_water_received = 0
                crop.expected_total_water = precomputed irrigation total for this cycle
            CONTINUE to next crop

        # Advance day counter
        crop.days_in_stage += 1

        # Check for state transition
        IF crop.state == INITIAL AND crop.days_in_stage > initial_days:
            crop.state = DEVELOPMENT
            crop.days_in_stage = 0
        ELSE IF crop.state == DEVELOPMENT AND crop.days_in_stage > development_days:
            crop.state = MID_SEASON
            crop.days_in_stage = 0
        ELSE IF crop.state == MID_SEASON AND crop.days_in_stage > mid_season_days:
            crop.state = LATE_SEASON
            crop.days_in_stage = 0
        ELSE IF crop.state == LATE_SEASON AND crop.days_in_stage > late_season_days:
            crop.state = HARVEST_READY

        # Compute daily Kc for this crop
        IF crop.state == INITIAL:
            crop.kc = kc_initial
        ELSE IF crop.state == DEVELOPMENT:
            progress = crop.days_in_stage / development_days
            crop.kc = kc_initial + progress * (kc_mid - kc_initial)
        ELSE IF crop.state == MID_SEASON:
            crop.kc = kc_mid
        ELSE IF crop.state == LATE_SEASON:
            progress = crop.days_in_stage / late_season_days
            crop.kc = kc_mid + progress * (kc_end - kc_mid)
        ELSE IF crop.state == HARVEST_READY:
            crop.kc = 0  # No water demand on harvest day
```

### 6.5 Harvest Trigger

Harvest occurs when `crop.state` transitions to HARVEST_READY:

```
IF crop.state == HARVEST_READY:
    Execute harvest yield calculation (Section 5.2)
    Execute food processing pipeline (Section 5.3-5.9)
    crop.state = DORMANT
    crop.days_in_stage = 0
```

**Step 0 / Step 4 hand-off:** Step 0 only advances `crop.state` to `HARVEST_READY`. It does NOT execute the harvest yield calculation or food processing pipeline. Step 4 queries all farms for crops in `HARVEST_READY` state, executes the yield calculation and processing pipeline (Sections 5.2-5.6), then transitions those crops to `DORMANT`. This separation preserves the one-day lag for `E_processing` (see Processing Energy Timing Note in Section 3).

Harvest is deterministic: it occurs exactly `season_length_days` after planting. There is no early harvest or delayed harvest mechanism in MVP.

### 6.6 Year-Boundary Handling

Crops do NOT reset at year boundaries. A crop planted in November with a 135-day season will be harvested in March of the following year. The yearly boundary operations (Section 9.2, item 5 "Crop reinitialization") apply only to resetting the planting schedule for the NEW year:

```
At year boundary:
    FOR each farm:
        FOR each crop:
            IF crop.state == DORMANT:
                # Ready for new year planting dates -- no action needed,
                # daily transition algorithm will pick up the next planting date
                PASS
            ELSE:
                # Crop is mid-cycle from previous year -- let it complete
                # Do NOT interrupt or reset
                PASS

    Reset cumulative_water_received only for DORMANT crops (active crops
    retain their running total for the current growth cycle)
```

This ensures crops spanning year boundaries are tracked correctly for yield calculation and water stress accounting.

### 6.7 Irrigation Demand During Crop Lifecycle

Only crops in states INITIAL through LATE_SEASON generate irrigation demand. DORMANT and HARVEST_READY states produce zero demand.

```
base_demand_m3 = ET0 * crop.kc * effective_area_ha * 10 / eta_irrigation
```

This value is passed to the crop policy (Step 1) which may adjust it based on the selected policy (`fixed_schedule`, `deficit_irrigation`, `weather_adaptive`). The adjusted demand then flows to the water policy (Step 2).

Cumulative water tracking:

```
# Per-crop water distribution within a farm:
# The water policy allocates water at the FARM level (total m3 for the farm).
# This farm-level allocation is distributed to individual crops pro-rata
# by each crop's adjusted demand:
#
#   crop_water_delivered_m3 = farm_total_water_delivered_m3
#                             * (crop_adjusted_demand_m3 / farm_total_demand_m3)
#
# If farm_total_demand_m3 == 0, all crops receive 0 (zero-demand guard).
# The sum of all crop deliveries equals the farm's total allocation exactly.

crop.cumulative_water_received += crop_water_delivered_m3
```

This is used at harvest for the water stress factor:

```
water_ratio = clamp(cumulative_water_received / expected_total_water, 0, 1)
```

---

## 7. Energy Policy Integration with dispatch_energy()

This section specifies how energy policies connect to the dispatch function. Energy policies return configuration flags; the dispatch function consumes those flags to determine the merit order and source availability.

### 7.1 Integration Contract

The simulation loop calls the energy policy to get dispatch parameters, then passes them to the dispatch function:

```
# In simulation loop (Step 3):
energy_allocation = energy_policy.allocate_energy(ctx)
dispatch_result = dispatch_energy(
    total_demand_kwh=total_demand_kwh,
    pv_available_kwh=pv_available_kwh,
    wind_available_kwh=wind_available_kwh,
    battery_soc=battery_soc,
    battery_capacity_kwh=battery_capacity_kwh,
    generator_capacity_kw=generator_capacity_kw,
    grid_price_per_kwh=grid_price_per_kwh,
    diesel_price_per_L=diesel_price_per_L,
    allocation=energy_allocation,   # <-- Policy output consumed here
)
```

### 7.2 EnergyAllocation Flags

The policy returns:

```
EnergyAllocation:
    use_renewables: bool           # Use PV/wind for self-consumption
    use_battery: bool              # Use battery for charge/discharge
    grid_import: bool              # Import from grid when needed
    grid_export: bool              # Export surplus to grid
    use_generator: bool            # Backup generator available
    sell_renewables_to_grid: bool  # Route all renewables to export (net metering)
    battery_reserve_pct: float     # Minimum battery SOC to maintain (0-1)
    decision_reason: str           # Dispatch strategy explanation
```

### 7.3 dispatch_energy() Behavior by Policy

The dispatch function MUST respect the allocation flags. The merit order is determined by the combination of flags:

`**microgrid**`** (userenewables=T, usebattery=T, gridimport=F, gridexport=F, usegenerator=T):**

```
Merit order: PV -> Wind -> Battery discharge -> Generator
Surplus: Battery charge -> Curtailment (no grid export)
Unmet after generator: Record as unmet_demand_kwh
```

`**renewable_first**`** (userenewables=T, usebattery=T, gridimport=T, gridexport=T, usegenerator=F):**

```
Merit order: PV -> Wind -> Battery discharge -> Grid import
Surplus: Battery charge -> Grid export
Generator: Not dispatched (grid_import=T makes it unnecessary)
```

`**all_grid**`** (userenewables=F, usebattery=F, gridimport=T, gridexport=T, sellrenewablestogrid=T):**

```
All demand met from grid import
All PV/wind generation exported to grid (revenue = generation * export_price)
Battery: Not used
```

### 7.4 Dispatch Algorithm (Pseudocode)

```
dispatch_energy(total_demand_kwh, ..., allocation):

    remaining_demand = total_demand_kwh
    pv_used = 0, wind_used = 0, battery_discharged = 0
    grid_imported = 0, generator_used = 0
    pv_exported = 0, wind_exported = 0, curtailed = 0

    # --- Self-consumption of renewables ---
    IF allocation.use_renewables:
        pv_used = min(pv_available_kwh, remaining_demand)
        remaining_demand -= pv_used
        wind_used = min(wind_available_kwh, remaining_demand)
        remaining_demand -= wind_used
        surplus_renewable = (pv_available_kwh - pv_used) + (wind_available_kwh - wind_used)
    ELSE:
        surplus_renewable = pv_available_kwh + wind_available_kwh

    # --- Battery discharge ---
    IF allocation.use_battery AND remaining_demand > 0:
        effective_soc_floor = max(SOC_min, allocation.battery_reserve_pct)
        stored_energy_above_reserve = (battery_soc - effective_soc_floor) * battery_capacity_kwh
        stored_energy_above_reserve = max(0, stored_energy_above_reserve)
        max_deliverable_kwh = stored_energy_above_reserve * eta_discharge  # Energy available at the load
        battery_discharged = min(max_deliverable_kwh, remaining_demand)   # Energy delivered to load
        remaining_demand -= battery_discharged
        # Note: SOC update uses battery_discharged / eta_discharge to get energy removed from battery

    # --- Grid import ---
    IF allocation.grid_import AND remaining_demand > 0:
        grid_imported = remaining_demand
        remaining_demand = 0

    # --- Generator ---
    IF allocation.use_generator AND remaining_demand > 0:
        max_runtime_hours = scenario.energy_system.backup_generator.max_runtime_hours  # default 18
        generator_capacity_kwh = generator_capacity_kw * max_runtime_hours
        min_load_kwh = generator_capacity_kw * 0.30 * max_runtime_hours
        gen_output = min(remaining_demand, generator_capacity_kwh)
        # Minimum load constraint: run at 30% minimum if demand is below threshold
        IF gen_output < min_load_kwh AND gen_output > 0:
            gen_output = min_load_kwh  # Run at minimum load; excess is curtailed
        generator_used = gen_output
        # Compute curtailment BEFORE reducing remaining_demand
        generator_curtailed = max(0, generator_used - remaining_demand)  # Fuel burned but not useful
        remaining_demand = max(0, remaining_demand - generator_used)

    # --- Surplus handling ---
    IF allocation.sell_renewables_to_grid:
        # all_grid policy: export everything
        grid_exported = pv_available_kwh + wind_available_kwh
    ELSE IF surplus_renewable > 0:
        # Charge battery first
        IF allocation.use_battery:
            available_room = (SOC_max - battery_soc) * battery_capacity_kwh / eta_charge
            battery_charged = min(surplus_renewable, available_room)
            surplus_renewable -= battery_charged
        # Export remainder
        IF allocation.grid_export AND surplus_renewable > 0:
            grid_exported = surplus_renewable
            surplus_renewable = 0
        # Anything left is curtailed
        curtailed = surplus_renewable

    # --- Unmet demand ---
    unmet_demand_kwh = remaining_demand

    # --- Cost calculation ---
    grid_cost = grid_imported * grid_price_per_kwh
    # Generator fuel consumption (from calculations_energy.md):
    # Fuel consumption follows a linear model based on load fraction:
    #   fuel_L_per_hr = a * P_rated_kw + b * P_output_kw
    # Where a = 0.0246 L/kW/hr (no-load coefficient), b = 0.0845 L/kW/hr (load coefficient)
    # Source: Typical diesel genset fuel curves (Caterpillar/Cummins data sheets)
    #   runtime_hours = generator_used_kwh / generator_capacity_kw  (assumes constant output)
    #   fuel_L = (a * generator_capacity_kw + b * generator_used_kwh / runtime_hours) * runtime_hours
    generator_fuel_L = calculate_fuel(generator_used, generator_capacity_kw)
    generator_cost = generator_fuel_L * diesel_price_per_L
    export_revenue = grid_exported * export_price_per_kwh
    total_energy_cost = grid_cost + generator_cost - export_revenue

    RETURN DispatchResult(...)
```

**Battery SOC update (after dispatch):**

```text
# Discharge: soc -= (battery_discharged_kwh / eta_discharge) / battery_capacity_kwh
# Charge:    soc += (battery_charged_kwh * eta_charge) / battery_capacity_kwh
# Clamp:     soc = clamp(soc, SOC_min, SOC_max)
```

**Self-discharge note:** Self-discharge is applied AFTER dispatch completes, not within the dispatch algorithm. This prevents self-discharge from affecting the dispatch merit-order logic (which should see the battery as it was at start of day). Self-discharge loss is small (~0.05%/day for LFP) but accumulates during idle periods. See calculations_energy.md Battery Storage Dynamics.

### 7.5 Total Energy Demand Components

All demand components MUST flow into the dispatch. To prevent double-counting, water-system energy is taken directly from the water policy output (Step 2), not re-computed independently.

```
total_demand_kwh = E_water_system + E_irrigation_pump
                 + E_processing + E_household + E_community_bldg

WHERE:
    E_water_system = SUM(allocation.energy_used_kwh) across all farms + community water
        Decomposed for reporting (not re-summed into demand):
        E_desal = groundwater_m3 * treatment_kwh_per_m3
        E_pump = groundwater_m3 * pumping_kwh_per_m3
        E_convey = groundwater_m3 * conveyance_kwh_per_m3
    E_irrigation_pump = total_irrigation_m3 * irrigation_pressure_kwh_per_m3
        # irrigation_pressure_kwh_per_m3: Fixed constant for MVP, value depends on irrigation type:
        #   drip_irrigation:    0.056 kWh/m3 (1.5 bar operating pressure, pump eta=0.75)
        #   subsurface_drip:    0.056 kWh/m3 (same as drip)
        #   sprinkler:          0.112 kWh/m3 (3.0 bar operating pressure, pump eta=0.75)
        #   surface:            0.019 kWh/m3 (0.5 bar minimal lift, pump eta=0.75)
        # Looked up from scenario's irrigation_system.type at initialization (Step 5).
        # Applied to ALL irrigation water regardless of source (GW + municipal).
    E_processing = sum(throughput_kg * energy_per_kg) by pathway (from previous day)
    E_household = from precomputed data: registry `household.energy`
    E_community_bldg = from precomputed data: registry `community_buildings.energy`
```

**Water Energy Term Reference Table:**

The following table clarifies what each water-related energy term covers in the chain of water use. This is critical for preventing double-counting, since the water policy's `energy_used_kwh` output already aggregates the first three terms.


| Term                | Physical Process     | What It Covers                                                                                                                                                | Formula                                                            | Applies To                            |
| ------------------- | -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------- |
| `E_pump`            | Vertical lift        | Lifting water from aquifer to surface via submersible pump. Includes static head + drawdown. Does NOT include horizontal transport.                           | `groundwater_m3 * (rho * g * h) / (eta_pump * 3.6e6)`              | Groundwater only                      |
| `E_convey`          | Horizontal transport | Moving water through pipes from well to treatment plant, and from treatment plant to storage. Friction losses only (no significant elevation change assumed). | `groundwater_m3 * 0.2 kWh/m3` (fixed MVP estimate)                 | Groundwater only                      |
| `E_desal`           | Water treatment      | Brackish water reverse osmosis desalination. Energy depends on feed water salinity (TDS).                                                                     | `groundwater_m3 * treatment_kwh_per_m3` (lookup by salinity level) | Groundwater only                      |
| `E_irrigation_pump` | Field pressurization | Pressurizing treated water at the field header for drip emitter delivery. Separate physical pump from the well pump.                                          | `total_irrigation_m3 * 0.056 kWh/m3` (1.5 bar, eta=0.75)           | ALL irrigation water (GW + municipal) |


**Key clarifications:**

- **Groundwater path:** Aquifer -> E_pump (lift to surface) -> E_convey (pipe to treatment) -> E_desal (desalination) -> storage -> E_irrigation_pump (pressurize for drip)
- **Municipal path:** Municipal supply (already treated, arrives at low pressure) -> E_irrigation_pump (pressurize for drip). Municipal water bypasses the community's wells, treatment, and storage.
- **E_irrigation_pump** is the only water energy term that applies to municipal water. All other terms apply exclusively to groundwater.
- The water policy's `energy_used_kwh` output = E_pump + E_convey + E_desal (for that farm's groundwater allocation). E_irrigation_pump is computed separately because it applies to ALL irrigation water, not just groundwater.

**Community building types** (configured in `community_structure.community_buildings` in settings YAML):

- `office_admin_m2` -- administration, management offices
- `storage_warehouse_m2` -- equipment and supply storage
- `meeting_hall_m2` -- community gathering space
- `workshop_maintenance_m2` -- equipment repair and maintenance

Precomputed data files provide energy (kWh/m2/day) and water (m3/m2/day) per building type with temperature-adjusted seasonal variation. The simulation multiplies these per-m2 rates by the configured building areas to get daily totals.

---

## 8. Per-Farm Cost Allocation

Shared infrastructure costs (water treatment, energy systems, processing facilities) must be allocated across farms. The allocation method is a community-level configuration parameter.

### 8.1 Allocation Methods

Three methods are available, configurable via `community.cost_allocation_method` in the scenario YAML:

**Equal allocation:**

```
allocated_opex_i = Total_shared_opex / num_farms
```

Simple and transparent. Every farm pays the same regardless of size or usage. Appropriate when farms are similar in size and the community values simplicity.

**Area-proportional allocation:**

```
allocated_opex_i = Total_shared_opex * (farm_area_i / total_farming_area)
```

Larger farms pay more. Reflects that larger farms consume proportionally more infrastructure capacity. Uses `plantable_area_ha` from farm configuration.

**Usage-proportional allocation:**

```
allocated_opex_i = Total_shared_opex * (farm_usage_i / total_usage)
```

Where `farm_usage_i` is the farm's actual consumption of the shared resource during the billing period. For water infrastructure: based on water volume. For energy infrastructure: based on energy consumption. For processing: based on throughput kg.

Usage-proportional allocation requires tracking per-farm resource consumption, which is already recorded in daily records.

### 8.2 What Counts as Shared OPEX

```
Total_shared_opex = water_system_om + energy_system_om + processing_system_om
                  + debt_service (all infrastructure loans)
                  + equipment_replacement_reserve
                  + administrative_labor_costs
                  + community_water_cost   # from Step 2b: household + building water
                  + community_energy_cost  # from Step 3b: household + building energy share
```

Farm-specific costs (seeds, fertilizer, field labor) are NOT shared and are charged directly to the farm that incurs them.

**Infrastructure O&M rates:** Infrastructure O&M costs (`water_system_om`, `energy_system_om`, `processing_system_om`) are annual values from financing profiles. They are divided by 365 to produce daily rates.

**Community demand costs:** Water and energy costs for non-farm operations (households, community buildings) are community-level expenses included in `Total_shared_opex`. These are computed in Steps 2b and 3b of the daily loop and allocated to farms via the same `cost_allocation_method` as other shared infrastructure costs.

### 8.3 Allocation Timing

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

### 8.4 Per-Farm Net Income

```
Net_income_farm_i = Revenue_farm_i - farm_specific_costs_i - allocated_shared_opex_i
```

Community-level net income = sum of all farm net incomes.

---

## 9. Monthly and Yearly Boundary Operations

### 9.1 Monthly Boundaries (First Day of Each Month)

Operations triggered on the first simulation day of each month:

**1. Economic policy execution:**

- Compute `months_of_reserves` using trailing 12-month average operating costs:

```
      avg_monthly_opex = sum(opex for last 12 months) / min(12, months_elapsed)
      months_of_reserves = cash_reserves_usd / avg_monthly_opex
```

- For the first year (months_elapsed < 12), use the available months as the denominator.
- Assemble `EconomicPolicyContext` with PREVIOUS month's aggregated revenue and costs.
- Call `economic_policy.decide(ctx)` and store the resulting flags.

Note: This is a conceptual description of Step 6 in the daily loop — not a separate execution trigger. The economic policy executes exactly once on the first day of each month, as specified in Step 6.

**2. Monthly resets:**

- Monthly accumulators (`cumulative_gw_month_m3`, `cumulative_monthly_community_water_m3`) reset automatically on first access when the month changes (reset-on-read pattern). This means the reset occurs implicitly before Step 1 when any step first reads the accumulator for a new month.
- The monthly metrics snapshot (item 3 below) must be captured before the reset — either by snapshotting at the end of the last day of the month, or by aggregating from daily records for the completed month.
- Note: `cumulative_gw_year_m3` is NOT reset at monthly boundaries -- it accumulates across the entire year and is reset only at yearly boundaries.

**3. Monthly metrics snapshot:**

- Aggregate daily records for the completed month.
- Compute monthly totals for water, energy, revenue, and costs.

**4. Update debt schedules:**

```text
# Update debt schedules
FOR each debt_schedule in economic_state.debt_schedules:
    IF debt_schedule.remaining_months > 0:
        interest_portion = debt_schedule.remaining_principal * (debt_schedule.annual_interest_rate / 12)
        principal_portion = debt_schedule.monthly_payment - interest_portion
        debt_schedule.remaining_principal -= principal_portion
        debt_schedule.remaining_months -= 1
economic_state.total_debt_usd = SUM(ds.remaining_principal for ds in debt_schedules)
```

### 9.2 Yearly Boundaries (First Day of Each Year)

Operations triggered on the first simulation day of each new year:

**Ordering on January 1:** When both monthly and yearly boundaries trigger on the same day, execute in this order: (1) monthly snapshot, (2) monthly reset, (3) yearly snapshot, (4) yearly resets, (5) yearly updates (degradation, aquifer, crop reinitialization). Monthly operations complete first so that the yearly snapshot includes the finalized December data.

**1. Yearly metrics snapshot:**

- Compute all metrics defined in `metrics_and_reporting.md` (water, energy, crop, economic, resilience).
- Store as `YearlyFarmMetrics` per farm and community-level aggregates.

**2. Aquifer state update:**

- Compute net annual depletion:

```text
      net_depletion = annual_gw_extraction - aquifer_recharge_rate_m3_yr
      remaining_volume -= net_depletion
```

- Update effective pumping head (drawdown feedback):

```text
      fraction_depleted = cumulative_extraction / aquifer_exploitable_volume_m3
      drawdown_m = max_drawdown_m * fraction_depleted
      effective_head_m = well_depth_m + drawdown_m
```

- Recompute `pumping_kwh_per_m3` with new effective head.

```text
# If aquifer is fully depleted, disable groundwater extraction
IF remaining_volume_m3 <= 0:
    remaining_volume_m3 = 0
    max_groundwater_m3 = 0  # No extraction possible; all demand goes to municipal
    LOG warning: "Aquifer fully depleted. All water demand shifted to municipal."
```

**3. Equipment degradation:**

- PV: `degradation_factor *= (1 - 0.005)` (0.5%/yr)
- Battery: Update effective capacity using dual aging model:
  - `fade_calendar = alpha_cal * years_elapsed` (alpha_cal = 0.018/yr for LFP in hot arid climate)
  - `fade_cycle = alpha_cyc * efc_cumulative / EFC_rated` (alpha_cyc = 0.20, EFC_rated = 5000 for LFP)
  - `effective_capacity = nameplate_capacity_kwh * (1 - fade_calendar) * (1 - fade_cycle)`
  - Update `battery_capacity_kwh` used in dispatch with `effective_capacity`.
  - Log warning if `effective_capacity < 0.80 * nameplate` (end-of-life threshold).

Note: Equipment degradation updates apply from the second day of the new year onward (Day 1 of the new year dispatches with the previous year's parameters). This one-day lag is acceptable: annual degradation rates are small (0.5% PV, ~1.8% battery calendar fade) so a single day's error is negligible relative to daily weather variance.

**4. Equipment replacement reserve tracking:**

- Record cumulative replacement reserve contributions for the year.
- Log `annual_replacement_reserve` in yearly metrics.
- Note: For MVP, the sinking fund is a cost provision only (no discrete replacement events). The reserve is deducted from cash flow but does not trigger equipment state changes. Future enhancement: model discrete replacement events when cumulative reserve exceeds component replacement cost.

**5. Crop reinitialization:**

- Reset planting schedule index for new year dates (dormant crops only).
- Reset cumulative water tracking for dormant crops only.
- Active crops (mid-cycle spanning year boundary) continue uninterrupted; their cumulative water tracking is retained for the current growth cycle.
- See Section 6 (Crop Lifecycle State Machine) for full year-boundary handling.

**6. Reset yearly accumulators:**

- Reset `cumulative_gw_year_m3` to 0.
- Reset yearly energy accumulators (PV, wind, grid, generator, curtailment).
- Note: `cumulative_gw_month_m3` is NOT reset at yearly boundaries -- it follows its own monthly reset cycle (Section 9.1). On January 1, the monthly accumulator was already reset when the December-to-January month boundary triggered.

**7. Financial metrics update:**

- Compute IRR and NPV using `economic_state.total_capex_invested` as the year-0 outflow and yearly `net_income` as the annual cash flows. See calculations_economic.md (IRR, NPV) for formulas.

---

## 10. Community Demand Integration

### 10.1 Community Demand Calculation

Household and community building demands are loaded from precomputed daily time-series:

```
E_household(date) = lookup from registry `household.energy` for date
    (provides per-household-type kWh/day and total_community_kwh)

E_community_bldg(date) = SUM over building_types:
    lookup per-m² rate from registry `community_buildings.energy` for date
    × configured area from settings (e.g., office_admin_m2, storage_warehouse_m2, etc.)

household_water_m3_day(date) = lookup from registry `household.water` for date
community_bldg_water_m3_day(date) = SUM over building_types:
    lookup per-m² rate from registry `community_buildings.water` for date
    × configured area from settings
```

Both demand categories are loaded as daily time-series with temperature-adjusted seasonal variation. Community building data is stored as per-m² rates so building sizes can be adjusted through the settings YAML without regenerating data files. The two categories are aggregated in Step 2b (community water) and Step 3 (community energy) of the daily loop.

### 10.2 Community Water Policy

Community water demand (households + community buildings) uses the community pricing regime and a restricted set of water policies:

- **Available policies:** `max_groundwater`, `max_municipal`
- **Configured in:** `community_policies.water_policy` in scenario YAML
- **Pricing:** Community water pricing regime (tiered if subsidized, flat if unsubsidized)
- **Infrastructure:** Shares the same wells and treatment infrastructure as farms (capacity is shared via area-proportional allocation, with community demand treated as a single "virtual farm" for allocation purposes)

### 10.3 Community Energy Policy

Community energy demand (households + community buildings) uses the community pricing regime and any energy policy:

- **Available policies:** `microgrid`, `renewable_first`, `all_grid`
- **Configured in:** `community_policies.energy_policy` in scenario YAML
- **Pricing:** Community energy pricing regime

### 10.4 Integration with Dispatch

Community energy demand is included in the community-level `total_demand_kwh` that flows into `dispatch_energy()`. It is NOT dispatched separately. The energy policy for community demand determines whether that demand should draw from renewables, battery, grid, or generator -- but since dispatch is community-level, the community policy flags are combined with farm policy flags.

When farm and community energy policies differ:

- The dispatch function uses the MOST PERMISSIVE combination of flags. For example, if farms use `microgrid` (no grid) but community uses `renewable_first` (grid allowed), grid import is enabled for the community.
- Energy costs are then allocated back to farm vs. community based on their respective demand shares and applicable pricing regimes.

---

## 11. Error Handling Specification

This section defines how the simulation handles edge cases, invalid inputs, and arithmetic hazards. The guiding principle is: **fail explicitly rather than inject default values**. Silent fallbacks hide bugs; explicit failures surface them during development.

### 11.1 Zero-Demand Guards

Policies and calculations that receive zero-valued inputs must return early with zero-valued outputs rather than proceeding with calculations that would produce division-by-zero or meaningless results.

```
# Water policy
IF demand_m3 == 0:
    RETURN WaterAllocation(groundwater_m3=0, municipal_m3=0, cost_usd=0,
                           energy_used_kwh=0, decision_reason="zero_demand")

# Food processing policy
IF harvest_yield_kg == 0:
    RETURN ProcessingAllocation(fresh_fraction=1.0, packaged_fraction=0,
                                canned_fraction=0, dried_fraction=0,
                                decision_reason="zero_harvest")

# Capacity clipping
IF harvest_yield_kg == 0:
    SKIP clipping (division by harvest_yield_kg would crash)

# Market policy
IF available_kg == 0:
    RETURN MarketDecision(sell_fraction=0, store_fraction=0,
                          target_price_per_kg=0, decision_reason="zero_inventory")
```

### 11.2 Division-by-Zero Prevention

Specific calculations that involve division must guard against zero denominators:

```
# Water use efficiency
IF total_yield_kg == 0:
    WUE = float('inf')  # or skip metric

# Operating margin
IF total_revenue == 0:
    operating_margin_pct = -100.0 if total_opex > 0 else 0.0

# Price ratio (adaptive market policy)
IF avg_price_per_kg == 0:
    price_ratio = 1.0  # treat as neutral, sell at min_sell fraction

# Months of reserves
IF avg_monthly_opex == 0:
    months_of_reserves = float('inf')  # no costs means infinite reserves

# Capacity utilization
IF processing_capacity_kg_day == 0:
    processing_utilization_pct = 0.0  # no capacity means no utilization
```

### 11.3 Invalid Parameter Handling

The simulation should validate parameters at scenario load time (Layer 2), not during execution (Layer 3). Invalid parameters that slip through to runtime should raise explicit errors.

```
# Fraction validation
IF any fraction < 0 or any fraction > 1:
    RAISE ValueError("Fraction out of range [0, 1]")

IF abs(fresh + packaged + canned + dried - 1.0) > 0.001:
    RAISE ValueError("Processing fractions do not sum to 1.0")

# Negative price check
IF price_per_m3 < 0 or price_per_kwh < 0:
    RAISE ValueError("Negative price detected")

# Battery SOC bounds
battery_soc = clamp(battery_soc, 0.0, 1.0)

# Aquifer volume
IF remaining_volume < 0:
    remaining_volume = 0  # Physical constraint: cannot extract more than exists
    LOG warning: "Aquifer fully depleted"
```

### 11.4 NaN Propagation Prevention

NaN values must not propagate through calculations. Key insertion points where NaN can enter:

1. **Price lookups:** If a date falls outside the price data range, the lookup must return the nearest available value (extrapolation by last known value), not NaN.
2. **Division results:** All division operations listed in Section 11.2 must guard against producing NaN.
3. **Cumulative sums:** If any daily record contains NaN, the yearly aggregation will be NaN. Daily records must be validated before appending.

Guard pattern:

```
IF isnan(value):
    RAISE RuntimeError(f"NaN detected in {variable_name} on {current_date}")
```

This is intentionally aggressive. During development, NaN should crash the simulation immediately so the source can be traced. Production runs can relax this to logging + substitution if needed.

### 11.5 State Consistency Checks

At the end of each simulation day, verify:

```
# Material balance: water in = water out + change in storage
water_in = total_groundwater_extracted + total_municipal_delivered
water_out = total_water_distributed_to_farms + total_community_water
delta_storage = water_storage_end_of_day - water_storage_start_of_day
assert abs(water_in - water_out - delta_storage) < 0.01

# Energy balance: generation + import = demand + export + storage + curtailment + unmet
total_supply = pv_used + wind_used + grid_imported + generator_used + battery_discharged
total_sink = total_demand_kwh + grid_exported + battery_charged + curtailed + unmet_demand
assert abs(total_supply - total_sink) < 0.01

# Cash balance: no negative inventory
FOR each farm:
    assert all(tranche.kg >= 0 for tranche in community_storage)
```

These checks run every day during development. They can be disabled for production Monte Carlo runs where performance matters, but should be re-enabled when investigating anomalous results.

---

## 12. State Dataclass Definitions

This section provides the authoritative, consolidated field definitions for all simulation state dataclasses. Each field lists its type, initial value, and the spec section where its semantics are defined. This replaces scattered field references throughout the document.

### 12.1 SimulationState (top-level container)

```text
SimulationState:
    scenario: Scenario              # Loaded scenario configuration (from load_scenario())
    farms: list[FarmState]          # One per farm in scenario
    aquifer: AquiferState           # Shared aquifer state
    water_storage: WaterStorageState # Shared water storage
    energy: EnergyState             # Shared energy system state
    economic: EconomicState         # Community-level financial state
    community_storage: list[StorageTranche]  # Pooled food inventory (FIFO ordered)
    processing_throughput_kg_per_day: dict[str, float]  # {pathway: kg/day} from pre-loop Step 6
    storage_capacities_kg: dict[str, float]             # {product_type: kg total} from pre-loop Step 6
    daily_records: list[DailyRecord]         # Appended each day
    monthly_snapshots: list[MonthlySnapshot] # Appended at month boundaries
    yearly_snapshots: list[YearlySnapshot]   # Appended at year boundaries
    start_date: date                # Simulation start date
    end_date: date                  # Simulation end date
    current_date: date              # Advances each loop iteration
```

### 12.2 FarmState

```text
FarmState:
    id: str                         # Farm identifier from scenario
    name: str                       # Farm name from scenario
    plantable_area_ha: float        # Total plantable area (structure.md § 2)
    yield_factor: float             # Relative yield factor (structure.md § 2)
    starting_capital_usd: float     # Initial capital from scenario YAML
    current_capital_usd: float      # Runtime cash position; init = starting_capital_usd - capex_share
                                    # Updated daily in Step 7 (daily accounting)
    crops: list[CropState]          # One per crop configured for this farm
    policy_instances: dict[str, Policy]  # {domain: policy_object} — stamped during pre-loop Step 3
    contribution_kg: dict[str, float]    # {crop_name: cumulative_kg} — lifetime harvest tracker (metrics only)
                                         # Init = 0 for all crops (pre-loop Step 16)
    cumulative_gw_month_m3: float   # This farm's monthly extraction; init = 0; reset monthly
    cumulative_gw_year_m3: float    # This farm's yearly extraction; init = 0; reset yearly
    pending_inventory_liquidation: bool  # Set by economic policy (Step 6), read by Step 4.3
                                         # Init = False
    daily_water_records: list[DailyWaterRecord]  # Appended in Step 2
    daily_revenue: float            # Accumulated from market sales (Step 5), reset not needed (daily append)
    daily_costs: float              # Accumulated from Step 7, reset not needed
```

### 12.3 CropState

```text
CropState:
    crop_name: str                  # e.g., "tomato", "potato"
    area_fraction: float            # Fraction of farm area for this crop
    planting_dates: list[str]       # MM-DD strings from scenario
    percent_planted: float          # Fraction actually planted (0-1)
    state: CropStage                # Current lifecycle stage; init = DORMANT
                                    # Values: DORMANT, INITIAL, DEVELOPMENT, MID_SEASON,
                                    #         LATE_SEASON, HARVEST_READY (§ 6.1)
    days_in_stage: int              # Days in current stage; init = 0; reset on transition (§ 6.4)
    kc: float                       # Current crop coefficient; computed daily (§ 6.4)
                                    # Init = 0 (DORMANT has no Kc)
    cycle_start_date: date | None   # Set when transitioning DORMANT -> INITIAL (§ 6.4)
    cumulative_water_received: float # m3 received this growth cycle; init = 0
                                     # Reset when crop enters DORMANT (§ 6.5, § 6.6)
    expected_total_water: float     # Total m3 expected for this cycle; set at planting
                                    # = SUM of precomputed daily irrigation demand from
                                    #   planting_date to planting_date + season_length_days (§ 6.4)
    effective_area_ha: float        # = plantable_area_ha * area_fraction * percent_planted
                                    # Computed once at planting, cached for the cycle
```

### 12.4 AquiferState

```text
AquiferState:
    exploitable_volume_m3: float    # From scenario: aquifer_exploitable_volume_m3
    remaining_volume_m3: float      # Init = exploitable_volume_m3; reduced yearly (§ 9.2)
    recharge_rate_m3_yr: float      # From scenario: aquifer_recharge_rate_m3_yr
    cumulative_extraction_m3: float # Lifetime total; init = 0
    cumulative_gw_month_m3: float   # Current month extraction; init = 0; reset monthly (§ 9.1)
                                    # cumulative_gw_month_m3 and cumulative_gw_year_m3 are COMMUNITY-LEVEL totals
                                    # (sum of all farm extractions). Used for aquifer depletion tracking and reporting.
                                    # The quota_enforced policy uses PER-FARM trackers stored in each farm's water
                                    # policy context, not these community-level fields.
    cumulative_gw_year_m3: float    # Current year extraction; init = 0; reset yearly (§ 9.2)
    fraction_depleted: float        # cumulative_extraction / exploitable_volume; updated yearly
    drawdown_m: float               # max_drawdown_m * fraction_depleted; updated yearly (§ 9.2)
    effective_head_m: float         # well_depth_m + drawdown_m; updated yearly (§ 9.2)
    pumping_kwh_per_m3: float       # Recomputed yearly from effective_head_m (§ 9.2)
```

### 12.5 WaterStorageState

```text
WaterStorageState:
    capacity_m3: float              # From scenario: water_storage.capacity_m3
    current_m3: float               # Init = capacity_m3 * 0.50 (pre-loop Step 9)
                                    # Updated daily in Step 2 Phase 3
```

### 12.6 EnergyState

```text
EnergyState:
    # PV system
    pv_capacity_kw: float           # From scenario; nameplate
    pv_degradation_factor: float    # Init = 1.0; multiplied by (1 - 0.005) yearly (§ 9.2)

    # Wind system
    wind_capacity_kw: float         # From scenario; nameplate

    # Battery system
    battery_nameplate_kwh: float    # From scenario; does not change
    battery_capacity_kwh: float     # Effective capacity after degradation; init = nameplate
                                    # Updated yearly via dual aging model (§ 9.2)
    battery_soc: float              # State of charge (0-1); init = 0.50 (pre-loop Step 10)
                                    # Updated daily in dispatch (§ 7.4) and self-discharge
    efc_cumulative: float           # Equivalent full cycles; init = 0
                                    # Incremented daily: += daily_throughput / (2 * capacity) (Step 3)

    # Generator
    generator_capacity_kw: float    # From scenario
    max_runtime_hours: float        # From scenario; default 18

    # Battery parameters (from chemistry lookup)
    SOC_min: float                  # Hardware minimum SOC (0.10 for LFP)
    SOC_max: float                  # Hardware maximum SOC (0.95 for LFP)
    eta_charge: float               # Charge efficiency (0.95 for LFP)
    eta_discharge: float            # Discharge efficiency (0.95 for LFP)
    self_discharge_rate_daily: float # Daily self-discharge (0.0005 for LFP)
    alpha_cal: float                # Calendar fade rate (0.018/yr for LFP hot arid)
    alpha_cyc: float                # Cycle fade rate (0.20 for LFP)
    EFC_rated: float                # Rated cycle life (5000 for LFP)
```

### 12.7 EconomicState

```text
EconomicState:
    total_capex_invested: float     # SUM(capital_cost) all subsystems; for IRR/NPV (pre-loop Step 12)
    capex_cash_outflow: float       # SUM(capital_cost * capex_cost_multiplier) for cash systems only
    initial_cash: float             # SUM(starting_capital) - capex_cash_outflow (pre-loop Step 12)
    daily_replacement_reserve: float # From pre-loop Step 13
    monthly_debt_service: float     # Total across all loan-financed subsystems
                                    # = SUM of monthly_payment per financing profile
    infrastructure_annual_opex: float # Total infrastructure O&M per year (pre-loop Step 11)
    discount_rate: float            # From scenario economics configuration
    debt_schedules: list[DebtSchedule]  # One per loan-financed subsystem
    total_debt_usd: float               # SUM(ds.remaining_principal for ds in debt_schedules)
                                        # Updated monthly when payments are made
```

### 12.8 StorageTranche

```text
StorageTranche:
    product_type: str               # "fresh", "packaged", "canned", "dried" (ProductType enum)
    crop_name: str                  # e.g., "tomato"
    kg: float                       # Output kg after weight loss; decremented on partial sales
    harvest_date: date              # Date of harvest
    expiry_date: date               # harvest_date + shelf_life_days (from storage_spoilage_rates CSV)
    sell_price_at_entry: float      # Market price at time of storage (tracking only, not used for sale)
    farm_shares: dict[str, float]   # {farm_id: fraction} — ownership at creation; sums to 1.0
                                    # Computed from batch_contributions in Step 4.2
```

### 12.9 DailyWaterRecord

```text
DailyWaterRecord:
    date: date
    farm_id: str
    groundwater_m3: float           # From water policy allocation
    municipal_m3: float             # From water policy allocation
    energy_used_kwh: float          # Groundwater pumping + conveyance + treatment energy
    cost_usd: float                 # Cash water cost (GW maintenance + municipal purchase; excludes energy)
    decision_reason: str            # From water policy
    constraint_hit: str | None      # "well_limit", "treatment_limit", or None
```

### 12.10 DailyEnergyRecord / DispatchResult

```text
DispatchResult:
    pv_used_kwh: float              # PV generation consumed on-site
    wind_used_kwh: float            # Wind generation consumed on-site
    battery_discharged_kwh: float   # Energy delivered from battery to load
    battery_charged_kwh: float      # Energy stored into battery from surplus
    grid_imported_kwh: float        # Energy purchased from grid
    grid_exported_kwh: float        # Energy sold to grid
    generator_used_kwh: float       # Generator output (includes min-load curtailment)
    generator_curtailed_kwh: float  # Generator output wasted due to min-load constraint
    curtailed_kwh: float            # Renewable surplus that could not be used, stored, or exported
    unmet_demand_kwh: float         # Demand not met by any source (microgrid mode only)
    grid_cost_usd: float            # grid_imported * grid_price
    generator_cost_usd: float       # fuel_L * diesel_price
    generator_fuel_L: float         # Fuel consumed by generator
    export_revenue_usd: float       # grid_exported * export_price
    total_energy_cost_usd: float    # grid_cost + generator_cost - export_revenue
    battery_soc_after: float        # SOC after dispatch + self-discharge
```

### 12.11 MonthlySnapshot

```text
MonthlySnapshot:
    year: int
    month: int
    is_partial: bool                # True if month was not complete (final month)
    # Aggregated from daily records for the completed month:
    total_water_m3: float
    total_groundwater_m3: float
    total_municipal_m3: float
    total_water_cost_usd: float
    total_energy_kwh: float
    total_energy_cost_usd: float
    total_revenue_usd: float
    total_costs_usd: float
    net_income_usd: float
    # Per-farm breakdowns stored as dicts: {farm_id: value}
```

### 12.12 YearlySnapshot / YearlyFarmMetrics

```text
YearlySnapshot:
    year: int
    is_partial: bool                # True if year was not complete (final year)
    farm_metrics: dict[str, YearlyFarmMetrics]  # {farm_id: metrics}
    community_metrics: CommunityYearlyMetrics   # Cross-farm aggregation

YearlyFarmMetrics:
    # All metrics defined in metrics_and_reporting.md, computed per farm per year.
    # Key fields (see metrics_and_reporting.md for the full list):
    total_water_m3: float
    groundwater_m3: float
    municipal_m3: float
    water_self_sufficiency_pct: float
    total_energy_kwh: float
    renewable_energy_kwh: float
    grid_import_kwh: float
    energy_self_sufficiency_pct: float
    total_yield_kg: float
    yield_per_ha: float
    total_revenue_usd: float
    total_costs_usd: float
    net_income_usd: float
    cash_reserves_usd: float
    operating_margin_pct: float

CommunityYearlyMetrics:
    # Aggregations across all farms:
    total_community_water_m3: float
    total_community_energy_kwh: float
    total_community_revenue_usd: float
    total_community_net_income_usd: float
    gini_coefficient: float         # Income inequality (metrics_and_reporting.md)
    aquifer_remaining_volume_m3: float
    aquifer_depletion_rate_m3_yr: float
    npv_usd: float                  # Computed at yearly boundary (§ 9.2)
    irr_pct: float                  # Computed at yearly boundary (§ 9.2)
```

### 12.13 DailyRecord

```text
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

### 12.14 DebtSchedule

```text
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

---

## 13. End-of-Simulation Reporting

After the daily loop completes its final day, the simulation enters a post-loop reporting phase. This section specifies the complete sequence for finalizing state, computing summary metrics, and generating outputs. No policy decisions occur in this phase — it is purely aggregation and output.

### 13.1 Post-Loop Finalization

These steps execute exactly once, immediately after the last simulation day exits the daily loop.

**Step 1. Final period boundary flush:**

The daily loop triggers monthly and yearly boundary operations only on the FIRST day of a new period (Section 9). This means the final month and final year of the simulation are never snapshotted during the loop. The post-loop phase must explicitly close them out:

```
# Close final month
IF last_simulation_day is NOT the last day of its month:
    Snapshot monthly metrics for the partial final month
    (aggregate from daily records for days in this incomplete month)

# Close final year
IF last_simulation_day is NOT December 31:
    Snapshot yearly metrics for the partial final year
    (aggregate from daily records for days in this incomplete year)
    Compute IRR/NPV with the partial-year cash flow included
```

Partial periods are flagged in the output so downstream consumers can distinguish complete from incomplete periods. The flag is a boolean `is_partial` on each monthly and yearly snapshot.

**Step 2. Liquidate remaining inventory:**

All unsold storage tranches are valued at end-of-simulation market prices and recorded as terminal inventory value. This is NOT a forced sale — the inventory is not "sold" and no revenue transaction occurs. Instead, the terminal value is reported separately for financial analysis:

```
terminal_inventory_value = 0
FOR each tranche in community_storage:
    value = tranche.kg * current_price_per_kg(tranche.crop_name, tranche.product_type)
    terminal_inventory_value += value
    # Attribute to farms for per-farm terminal value
    FOR each farm_id, fraction in tranche.farm_shares:
        farm.terminal_inventory_value += value * fraction
```

This terminal value enters the NPV calculation as a final-period salvage inflow (Section 13.3, Step 4).

**Step 3. Record final state snapshot:**

Capture end-state for all systems:

```
final_state.water_storage_m3 = current water storage level
final_state.battery_soc = current battery SOC
final_state.aquifer_remaining_m3 = current aquifer volume
final_state.pv_degradation_factor = current PV degradation
final_state.battery_effective_capacity_kwh = current battery capacity
final_state.cash_position = {farm_id: farm.cash for each farm}
final_state.total_debt_remaining = SUM(outstanding principal across all loans)
```

### 13.2 Metric Computation: Order of Operations

Metrics are computed bottom-up: daily records aggregate to monthly, monthly to yearly, yearly to simulation-lifetime. Each level depends on the previous one being complete.

The full computation proceeds in four stages:

```
Stage 1: Per-farm yearly metrics     (one YearlyFarmMetrics per farm per year)
Stage 2: Community yearly metrics    (aggregate across farms for each year)
Stage 3: Simulation-lifetime metrics (aggregate across all years)
Stage 4: Financial summary metrics   (IRR, NPV, payback — require complete cash flow series)
```

### 13.3 Stage 1: Per-Farm Yearly Metrics

For each farm, for each simulation year (including the partial final year from Step 1):

**Water metrics:**

```
total_water_m3 = SUM(daily groundwater_m3 + municipal_m3)
groundwater_m3 = SUM(daily groundwater_m3)
municipal_m3 = SUM(daily municipal_m3)
water_cost_usd = SUM(daily water cost_usd)
water_treatment_energy_kwh = SUM(daily water energy_used_kwh)
water_self_sufficiency_pct = groundwater_m3 / total_water_m3 * 100
    # Guard: if total_water_m3 == 0, water_self_sufficiency_pct = 0
water_use_efficiency_m3_per_kg = total_water_m3 / total_yield_kg
    # Guard: if total_yield_kg == 0, water_use_efficiency = inf
water_storage_utilization_pct = AVG(daily water_storage_m3) / water_storage_capacity_m3 * 100
```

**Energy metrics (community-level, allocated to farms by demand share):**

```
pv_generation_kwh = SUM(daily pv_used + pv_exported)
wind_generation_kwh = SUM(daily wind_used + wind_exported)
total_renewable_kwh = pv_generation_kwh + wind_generation_kwh
grid_import_kwh = SUM(daily grid_imported)
grid_export_kwh = SUM(daily grid_exported)
generator_kwh = SUM(daily generator_used)
battery_throughput_kwh = SUM(daily battery_charged + battery_discharged)
curtailment_kwh = SUM(daily curtailed)
total_consumption_kwh = SUM(daily total_demand_kwh)
energy_self_sufficiency_pct = total_renewable_kwh / total_consumption_kwh * 100
    # Guard: if total_consumption_kwh == 0, energy_self_sufficiency_pct = 0
blended_energy_cost = total_energy_cost / total_consumption_kwh
    # Guard: if total_consumption_kwh == 0, blended_energy_cost = 0
```

**Crop production metrics:**

```
FOR each crop:
    total_yield_kg[crop] = SUM(harvest_yield_kg across all harvests this year)
    fresh_revenue[crop] = SUM(fresh sale revenue attributed to this farm for this crop)
    processed_revenue[crop] = SUM(packaged + canned + dried sale revenue)
    post_harvest_loss_kg[crop] = SUM(raw_yield_kg - harvest_available_kg)

total_yield_kg = SUM(total_yield_kg[crop] for all crops)
yield_per_ha = total_yield_kg / farm.plantable_area_ha
processing_utilization_pct = actual_throughput_kg / (processing_capacity_kg_day * harvest_days) * 100
    # Guard: if processing_capacity_kg_day == 0, processing_utilization_pct = 0
```

**Revenue metrics:**

```
fresh_crop_revenue = SUM(fresh_revenue[crop] for all crops)
processed_product_revenue = SUM(processed_revenue[crop] for all crops)
grid_export_revenue = farm's share of SUM(daily grid_exported * export_price)
total_gross_revenue = fresh_crop_revenue + processed_product_revenue + grid_export_revenue
```

**Cost metrics:**

```
water_cost = SUM(daily water_cost)
energy_cost = farm's allocated share of SUM(daily total_energy_cost)
labor_cost = SUM(daily labor_cost)
input_cost = SUM(daily input_cost)
storage_cost = SUM(daily storage_cost)
replacement_reserve = SUM(daily replacement_reserve)
debt_service = SUM(daily debt_service)
infrastructure_om = farm's allocated share of total O&M (per cost_allocation_method)
total_opex = water_cost + energy_cost + labor_cost + input_cost
           + storage_cost + replacement_reserve + debt_service + infrastructure_om
```

**Financial metrics:**

```
net_income = total_gross_revenue - total_opex
operating_margin_pct = (total_gross_revenue - total_opex) / total_gross_revenue * 100
    # Guard: if total_gross_revenue == 0, operating_margin_pct = -100 if total_opex > 0 else 0
debt_to_revenue = debt_service / total_gross_revenue
    # Guard: if total_gross_revenue == 0, debt_to_revenue = inf if debt_service > 0 else 0
cash_reserves = farm.cash at year end
months_of_reserves = cash_reserves / (total_opex / 12)
    # Guard: if total_opex == 0, months_of_reserves = inf
```

**Unit cost metrics (normalized):**

```
water_cost_per_m3 = water_cost / total_water_m3
water_cost_per_kg = water_cost / total_yield_kg
energy_cost_per_kwh = blended_energy_cost  # already computed above
labor_cost_per_ha = labor_cost / farm.plantable_area_ha
labor_cost_per_kg = labor_cost / total_yield_kg
    # Guards: division-by-zero per Section 11.2
```

### 13.4 Stage 2: Community Yearly Metrics

For each simulation year, aggregate farm-level metrics to the community level:

```
FOR each year:
    community.total_water_m3 = SUM(farm.total_water_m3 for all farms)
    community.total_yield_kg = SUM(farm.total_yield_kg for all farms)
    community.total_gross_revenue = SUM(farm.total_gross_revenue for all farms)
    community.total_opex = SUM(farm.total_opex for all farms)
    community.net_income = SUM(farm.net_income for all farms)

    # Add community (non-farm) water and energy costs
    community.total_water_m3 += community_water_m3  # households + buildings
    community.total_opex += community_water_cost + community_energy_cost

    # Distributional metrics (across farms within this year)
    farm_incomes = [farm.net_income for all farms]
    community.median_farm_income = MEDIAN(farm_incomes)
    community.min_farm_income = MIN(farm_incomes)
    community.max_farm_income = MAX(farm_incomes)
    community.income_gini = gini_coefficient(farm_incomes)

    # Resource depletion
    community.aquifer_depletion_m3 = yearly groundwater extraction - recharge
    community.aquifer_years_remaining = aquifer_remaining_m3 / community.aquifer_depletion_m3
        # Guard: if depletion <= 0, years_remaining = inf (aquifer stable or recovering)
    community.pv_capacity_remaining_pct = pv_degradation_factor * 100
    community.battery_capacity_remaining_pct = effective_capacity / nameplate_capacity * 100
```

**Labor metrics (community-level only):**

```
    community.total_employment_hours = SUM(daily labor hours across all activities)
    community.jobs_supported_fte = total_employment_hours / (8 * 250)  # 8hr days, 250 work days/yr
    community.peak_labor_month = MAX(monthly labor hours)
```

### 13.5 Stage 3: Simulation-Lifetime Metrics

Aggregate across all simulation years to produce summary statistics:

```
# Totals
lifetime.total_water_m3 = SUM(yearly community.total_water_m3)
lifetime.total_energy_kwh = SUM(yearly community.total_consumption_kwh)
lifetime.total_yield_kg = SUM(yearly community.total_yield_kg)
lifetime.total_revenue = SUM(yearly community.total_gross_revenue)
lifetime.total_opex = SUM(yearly community.total_opex)
lifetime.total_net_income = SUM(yearly community.net_income)

# Averages (using complete years only; exclude partial final year)
complete_years = [y for y in yearly_metrics if not y.is_partial]
num_complete_years = LEN(complete_years)
IF num_complete_years > 0:
    lifetime.avg_annual_revenue = AVG(y.total_gross_revenue for y in complete_years)
    lifetime.avg_annual_opex = AVG(y.total_opex for y in complete_years)
    lifetime.avg_annual_net_income = AVG(y.net_income for y in complete_years)
    lifetime.avg_water_self_sufficiency = AVG(y.water_self_sufficiency_pct for y in complete_years)
    lifetime.avg_energy_self_sufficiency = AVG(y.energy_self_sufficiency_pct for y in complete_years)

# Trends (year-over-year changes, complete years only)
IF num_complete_years >= 2:
    lifetime.revenue_trend = linear_slope(year, revenue for complete_years)
    lifetime.cost_trend = linear_slope(year, opex for complete_years)
    lifetime.net_income_trend = linear_slope(year, net_income for complete_years)

# Volatility
lifetime.cost_volatility_cv = STDEV(monthly_opex) / MEAN(monthly_opex)
    # Guard: if MEAN == 0, cv = 0
lifetime.revenue_volatility_cv = STDEV(monthly_revenue) / MEAN(monthly_revenue)
```

### 13.6 Stage 4: Financial Summary Metrics

These metrics require the complete cash flow time series and are computed last.

**Net Present Value (NPV):**

```
# Cash flow series: year 0 is the initial investment, years 1..N are annual net cash flows
CF_0 = -economic_state.total_capex_invested  # Total capital deployed (all financing methods)
CF_t = yearly community.net_income for year t  # Net operating cash flow
CF_N += terminal_inventory_value              # Add salvage value to final year

NPV = CF_0 + SUM(CF_t / (1 + discount_rate)^t for t = 1..N)

# discount_rate from scenario economics.discount_rate
```

**Internal Rate of Return (IRR):**

```
# IRR is the discount rate r that makes NPV = 0:
# 0 = CF_0 + SUM(CF_t / (1 + r)^t for t = 1..N)
# Solved numerically (Newton-Raphson or scipy.optimize.brentq)

# Edge cases:
# - All CF_t <= 0 (never profitable): IRR = undefined, report as None
# - CF_0 == 0 (no investment): IRR = undefined, report as None
# - Multiple sign changes: report the smallest positive root
```

**Payback Period:**

```
cumulative_cf = CF_0
FOR t = 1 to N:
    cumulative_cf += CF_t
    IF cumulative_cf >= 0:
        # Interpolate within the year for fractional payback
        shortfall = cumulative_cf - CF_t  # cumulative at start of year t (still negative)
        payback_years = (t - 1) + abs(shortfall) / CF_t
        BREAK

IF cumulative_cf < 0 after all years:
    payback_years = None  # Investment not recovered within simulation period
```

**Return on Investment (ROI):**

```
ROI_pct = (lifetime.total_net_income + terminal_inventory_value) / total_capex_invested * 100
    # Guard: if total_capex_invested == 0, ROI = inf if net_income > 0 else 0
```

**Cost savings vs. government-purchased baseline:**

```
# Counterfactual: what would the community pay buying all water and energy from government?
FOR each year:
    counterfactual_water_cost = total_water_m3 * government_water_price_per_m3(year)
    counterfactual_energy_cost = total_energy_kwh * government_energy_price_per_kwh(year)
    actual_water_cost = community water_cost (blended self-produced + municipal)
    actual_energy_cost = community energy_cost (blended renewable + grid + generator)
    water_savings[year] = counterfactual_water_cost - actual_water_cost
    energy_savings[year] = counterfactual_energy_cost - actual_energy_cost

lifetime.total_water_savings = SUM(water_savings)
lifetime.total_energy_savings = SUM(energy_savings)
```

The government price for the counterfactual uses the UNSUBSIDIZED rate with the configured `annual_escalation_pct` applied. If the community's actual pricing regime is already unsubsidized, this comparison shows the benefit of infrastructure ownership alone (lower blended cost from self-production). If subsidized, it shows what would happen if subsidies were removed.

### 13.7 Resilience Metrics

Resilience metrics are computed ONLY when the simulation is run as part of a Monte Carlo ensemble or sensitivity sweep. A single deterministic run does not produce resilience metrics (it produces a single trajectory, not a distribution).

**Monte Carlo survivability (computed by `run_monte_carlo()` after all runs complete):**

```
# Input: list of SimulationState results from N Monte Carlo runs
runs = [run_1_state, run_2_state, ..., run_N_state]

# Survival: a run "survives" if no farm's cash goes below zero
survived = [r for r in runs if ALL(farm.cash >= 0 for all days, all farms)]
survival_rate_pct = LEN(survived) / LEN(runs) * 100

# Crop failure: at least one season with >50% yield loss vs expected
crop_failures = [r for r in runs
    if ANY(season_yield < 0.50 * expected_yield for any farm, any season)]
crop_failure_prob_pct = LEN(crop_failures) / LEN(runs) * 100

# Insolvency: cash reserves fall below zero at any point
insolvent = [r for r in runs if ANY(farm.cash < 0 for any day, any farm)]
insolvency_prob_pct = LEN(insolvent) / LEN(runs) * 100

# Time to insolvency (among failed runs)
IF LEN(insolvent) > 0:
    times_to_insolvency = [first day where farm.cash < 0 for r in insolvent]
    median_years_to_insolvency = MEDIAN(times_to_insolvency) / 365

# Net income distribution across runs (using final-year net income)
all_net_incomes = [r.community.net_income for last complete year in each r]
p5, p25, p50, p75, p95 = PERCENTILES(all_net_incomes, [5, 25, 50, 75, 95])
worst_case_net_income = p5
```

**Distributional outcomes (across farms within each run):**

```
FOR each run:
    farm_incomes = [farm.net_income for last complete year]
    worst_farmer = MIN(farm_incomes)
    gini = gini_coefficient(farm_incomes)
    max_drawdown = MAX(peak_to_trough(farm.cumulative_cash) for each farm)

# Aggregate across runs
worst_farmer_p5 = PERCENTILE([run.worst_farmer for all runs], 5)
median_gini = MEDIAN([run.gini for all runs])
```

**Sensitivity analysis (computed by `run_sensitivity()`):**

```
# One-at-a-time parameter sweep: vary each parameter ±20% from baseline
FOR each parameter in sensitivity_parameters:
    result_low = run_simulation(parameter * 0.80)
    result_high = run_simulation(parameter * 1.20)
    sensitivity[parameter] = (result_high.net_income - result_low.net_income) / baseline.net_income

# Rank parameters by absolute sensitivity magnitude
sensitivity_ranking = SORT(sensitivity.items(), key=abs(value), descending=True)

# Breakeven thresholds: binary search for critical parameter values
FOR each parameter:
    Find value where survival_rate drops below target (e.g., 80%)
    breakeven[parameter] = critical_value
```

### 13.8 Output Generation

After all metrics are computed, the simulation generates output files. Output generation is orchestrated by `write_results(state, scenario)`.

**Execution order:**

```
Step 1. Create timestamped output directory: results/YYYY-MM-DD_HHMMSS/
Step 2. Write daily records to CSV (one file per record type):
    - daily_water.csv    (per farm per day)
    - daily_energy.csv   (community-level per day)
    - daily_accounting.csv (per farm per day: costs, revenue, cash)
Step 3. Write monthly summaries to CSV:
    - monthly_summary.csv (per farm per month: aggregated daily records)
Step 4. Write yearly metrics to CSV:
    - yearly_farm_metrics.csv (per farm per year: all Stage 1 metrics)
    - yearly_community_metrics.csv (per year: all Stage 2 metrics)
Step 5. Write lifetime summary to JSON:
    - simulation_summary.json (Stage 3 + Stage 4 metrics, scenario metadata)
Step 6. Write scenario echo (copy of input configuration for reproducibility):
    - scenario.yaml (exact copy of input scenario)
    - data_registry.yaml (exact copy of data registry used)
Step 7. Generate plots (see metrics_and_reporting.md § 2 for plot specifications):
    - Plot 1: input_price_index.png
    - Plot 2: effective_vs_market_cost.png
    - Plot 3: monthly_cost_breakdown.png
    - Plot 4: crop_prices_and_revenue.png
    - Plot 5: net_farm_income.png
    - Plot 6: profit_margin_sensitivity.png
Step 8. Generate tables (written as CSV for import into notebooks or reports):
    - table_annual_cost_summary.csv   (Table 1)
    - table_revenue_diversification.csv (Table 2)
Step 9. Write final state snapshot to JSON:
    - final_state.json (end-state of all systems from Section 13.1 Step 3)
```

**Monte Carlo output (additional files when run via `run_monte_carlo()`):**

```
Step 10. Write ensemble summary:
    - monte_carlo_summary.json (survival rate, percentiles, resilience metrics)
    - monte_carlo_distributions.csv (per-run final metrics for histogram plotting)
Step 11. Write sensitivity results (if sensitivity sweep was run):
    - sensitivity_ranking.csv (parameter, low_result, high_result, sensitivity)
    - sensitivity_breakevens.csv (parameter, breakeven_value, baseline_value)
```

---

*End of specification.*