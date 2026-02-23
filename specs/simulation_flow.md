# Simulation Flow Specification

## Overview

This document specifies the **order of operations** for the Layer 3 daily simulation. It defines when things happen, what feeds what, and where state changes occur. It does not redefine policy logic, dataclass schemas, or calculation formulas — those live in their authoritative sources:

- `structure.md` — Configuration schema, dataclass definitions, data file schemas
- `policies.md` — Policy decision logic and pseudocode for all 6 domains
- `calculations.md` — Index and cross-references to domain-specific calculation files
- `calculations_water.md` — Water system formulas (pumping, desalination, storage)
- `calculations_energy.md` — Energy system formulas (PV, wind, battery, dispatch, demand)
- `calculations_economic.md` — Economic formulas (financing, costs, revenue, labor, financial metrics)

**Cross-reference convention:** Pointers to other specs use the format `→ spec_file.md § Section_Number`. For example, `→ policies.md § 3` means "see policies.md, Section 3." References within this document name the target section by title (e.g., `→ Crop Tracking below`).

### Simulation at a Glance

The simulation has three phases: **initialization**, a **daily loop**, and **post-loop reporting**.

**Initialization** (runs once):

Load scenario configuration and precomputed data. Validate crop schedules. Calculate infrastructure capacities, financing costs, and demand baselines. Initialize all state: battery SOC [state of charge, fraction 0–1] starts at 50% of capacity. Record initial CAPEX.

**Daily loop** (for each day in the simulation period):

Each day is self-contained: all activities, costs, and revenue resolve within the day. Each step produces explicit outputs consumed by later steps — no mutable accumulators cross step boundaries. Physical state (battery SOC, crop progress, food inventory, cash balances) carries forward.


| Step | Name                  | Scope     | Key Action                                                          |
| ---- | --------------------- | --------- | ------------------------------------------------------------------- |
| 0    | Daily setup           | Community | Retrieve weather, prices, advance crop days. Monthly/yearly resets. |
| 1    | Crop policy           | Per farm  | Adjust base irrigation demand per crop policy.                      |
| 2    | Water allocation      | Community | Single policy: allocate GW/municipal, pro-rata to farms.            |
| 3    | Pre-harvest clearance | Community | Sell expired storage tranches (shelf-life FIFO).                    |
| 4    | Food processing       | Community | Pool harvests, apply food policy, create storage tranches.          |
| 5    | Sales                 | Community | Market policy voluntary sales.                                      |
| 6    | Energy dispatch       | Community | Aggregate demand, dispatch merit-order, update battery.             |
| 7    | Daily accounting      | Per farm  | Collect step outputs, compute costs, update cash, append records.   |


**Post-loop reporting** (runs once):

Log in-progress crops. Value terminal inventory. Compute all metrics from daily records in four stages: per-farm yearly → community yearly → lifetime → financial summary. Generate output files.

---

## Initialization

Before the daily loop begins, these steps execute exactly once. They establish the data environment, initial state, and financial baseline.

### Data Loading and Scenario Setup

```
Step 1.  Validate all required data files exist via registry.
Step 2.  Load scenario configuration via load_scenario().
         → structure.md § 2 for full scenario schema
Step 3.  Apply collective_farm_override policies to all farms if present.
         # collective_farm_override allows a community-level policy selection to replace
         # individual farm selections across one or more policy domains.
         IF scenario.community_structure.collective_farm_override exists:
             FOR each domain in collective_farm_override.policies:
                 FOR each farm in scenario.community_structure.farms:
                     farm.policies[domain] = collective_farm_override.policies[domain]
         → policies.md § 2 for policy hierarchy and override rules
Step 4.  Validate crop schedules — no overlapping seasons per crop per farm.
         FOR each farm:
             FOR each crop:
                 Resolve planting_dates (MM-DD strings) to absolute dates over simulation period.
                 FOR each pair of resolved planting dates:
                     IF planting_date_A + season_length_days > planting_date_B:
                         RAISE ConfigurationError(
                             "Overlapping crop seasons: {crop} on {farm}, "
                             "{planting_date_A} season ends after {planting_date_B}")
         # This replaces runtime overlap detection. All crop timing conflicts are
         # caught before simulation begins.
Step 5.  Load all precomputed data libraries (Layer 1 output) via SimulationDataLoader.
Step 6.  Calculate community infrastructure constraints:
         max_groundwater_m3_day = well_flow_rate_m3_day × number_of_wells
         max_treatment_m3_day  = water_treatment.system_capacity_m3_day
         # These are community-level hard limits — the well field and treatment plant
         # serve all farms collectively.
         → calculations_water.md § 1 for pumping energy, § 2 for treatment energy
```

### Infrastructure and Demand Setup

```
Step 7.  Note on processing and storage:
         # Processing throughput is unlimited. Equipment data is used
         # for cost and energy calculations only, not capacity constraints.
         # Storage capacity is unlimited. All harvested and processed product
         # can always be stored. Shelf-life expiry (Step 3) and farm ownership
         # shares (tranche.farm_shares) are still tracked.

Step 8.  Calculate community demand baselines (daily constants):
         - Household energy/water: lookup from precomputed registry files
         - Community buildings: per-m² rate × aggregate community_buildings_m2
           (building-type breakdown in YAML is informational only;
           the loader reads the single aggregate field)
         → structure.md § 2.4 for community building configuration
```

### System State Setup

```
Step 9.   Initialize SimulationState with farm states, energy state, economic state.
          → structure.md § 3 for all dataclass definitions
Step 10.  # Water storage initialization deferred — storage tracking is not active.
          # See Step 2c note on future buffer design.
Step 11.  Set initial battery SOC = 50% of capacity.
          energy_state.cumulative_diesel_L = 0
```

### Financial Baseline

```
Step 12.  Compute infrastructure annual costs from financing profiles.
          economic_state.infrastructure_annual_opex = SUM(
              subsystem.annual_om_cost_usd for each infrastructure subsystem)
          # Annual O&M costs per subsystem (water treatment, PV, wind, battery,
          # irrigation, processing equipment) from equipment parameter files.
          # Distinct from replacement reserve (Step 14) and debt service (Step 12a).
          → calculations_economic.md § 1 for financing cost formulas

Step 12a. Precompute full amortization schedule for each loan.
          FOR each financing profile with type = loan:
              Generate month-by-month table of (payment, interest, principal, remaining_balance).
          This table is read-only during simulation; Step 0 monthly operations
          advance a pointer rather than recomputing interest/principal splits.

Step 13.  Record initial CAPEX:
          economic_state.total_capex_invested = SUM(capital_cost) for all subsystems
          economic_state.capex_cash_outflow = SUM(capital_cost * capex_cost_multiplier)
              # capex_cost_multiplier > 0 only for purchased_cash financing.
              # Loan-financed systems enter as monthly debt service, not upfront cash.
          economic_state.initial_cash = SUM(farm.starting_capital_usd) - capex_cash_outflow

          # Allocate cash CAPEX to individual farms.
          # At initialization, usage_proportional falls back to area_proportional
          # because no usage data exists yet.
          FOR each farm:
              farm.capex_share = allocate(capex_cash_outflow, cost_allocation_method)
              farm.current_capital_usd = farm.starting_capital_usd - farm.capex_share
              IF farm.capex_share > farm.starting_capital_usd:
                  RAISE ConfigurationError("Insufficient starting capital")
          → structure.md § 2.8 for cost_allocation_method options

Step 14.  Compute daily equipment replacement reserve:
          Flat annual percentage of total CAPEX (default 2.5%).
          daily_replacement_reserve = total_capex_invested * annual_reserve_pct / 365

Step 15.  Initialize per-crop trackers:
          FOR each farm:
              FOR each crop:
                  crop.active = false
                  crop.crop_day = 0
                  crop.cumulative_water_received = 0
                  crop.expected_total_water = 0
          Initialize community groundwater trackers:
          cumulative_gw_month_m3 = 0
          cumulative_gw_year_m3 = 0
          cumulative_gw_extraction_m3 = 0
```

---

## Daily Loop

Each step lists inputs, actions, outputs, and state changes. Steps execute in strict order. Each step produces explicit return values — no mutable accumulators are shared across steps.

```
FOR each day in simulation_period:
```

### Step 0: Daily Setup

Retrieve daily conditions, advance crop day counters, and handle monthly and yearly resets.

```
    # Retrieve from precomputed data and price files
    weather       = (temp_max_c, temp_min_c, solar_irradiance_kwh_m2, wind_speed_ms) for today
                    → structure.md § 4 (Precomputed / Weather)
    prices        = (crop prices, processed product prices, energy prices, water prices, diesel price) for today
    avg_prices    = trailing 12-month average price per crop/product_type, looked up from the preloaded price series.
                    # Toy price files are monthly (one row per month); research crop price files are annual
                    # (one row per year). The trailing average is the mean of up to 12 prior monthly entries
                    # for toy data, or up to 12 prior annual entries (i.e., up to 12 prior years) for research data.
                    # If fewer than 12 prior entries exist (early simulation years), average all available entries.
    E_household   = daily household energy demand from precomputed registry file
    E_community   = daily community building energy demand per m² × community_buildings_m2
                    → structure.md § 4 (Precomputed / Community buildings)
    hw_demand     = daily household water demand from precomputed registry file
    cw_demand     = daily community building water demand per m² × community_buildings_m2

    # Advance crop tracking — see Crop Tracking below
    # Updates crop_day counters, triggers planting, identifies harvest events.
    is_harvest    = {farm_id: [crop_names]}  # crops where crop_day > season_length_days

    is_month_start = true if first day of new month
    is_year_start  = true if first day of new year

    # When both monthly and yearly trigger on the same day, monthly executes first.

    # Monthly operations (first day of each month)
    IF is_month_start:
        cumulative_gw_month_m3 = 0
        # Loan amortization: advance schedule pointer
        FOR each debt_schedule:
            IF schedule_month_index < total_months:
                schedule_month_index += 1
                # Monthly payment, interest, and principal components
                # are read from the precomputed schedule table.
        → calculations_economic.md § 7 for amortization formula

    # Yearly operations (first day of each year)
    IF is_year_start:
        cumulative_gw_year_m3 = 0
        # Only inactive crops get new planting schedules; active crops continue.
        FOR each farm:
            FOR each crop WHERE crop.active == false:
                Re-resolve planting_dates (MM-DD strings) to the new calendar year.
                # Same resolution logic as Initialization Step 4, but for one year only.
                # Active crops (spanning the year boundary) are untouched.
        → Planting and Year-Boundary Rules below
```

---

### Crop Tracking

This section details the crop lifecycle tracking that runs inside Step 0. All growth stage information and irrigation demands are looked up from precomputed CSV files — the simulation does not recompute crop coefficients (Kc) or ET values.

#### Per-Crop State

Each crop on each farm tracks a minimal set of values:

- **active:** Is this crop currently in a growth cycle?
- **crop_day:** Days since planting (1-indexed). Incremented daily for active crops.
- **planting_date:** The resolved planting date for the current cycle (YYYY-MM-DD).
- **cumulative_water_received:** Total irrigation water delivered this cycle (m³).
- **expected_total_water:** Full-season water requirement under no supply constraint (m³). Computed once at planting.

Growth stage and Kc are not tracked in simulation state. They are available in the precomputed irrigation demand CSV indexed by `(planting_date, crop_day)` and can be looked up on demand (e.g., for crop policy context or diagnostic output).

#### Daily Crop Advancement

Runs during Step 0 for every farm and crop:

```
FOR each farm:
    FOR each crop:
        IF crop.active:
            crop.crop_day += 1
            IF crop.crop_day > season_length_days:
                # Flag for harvest — processed in Step 4, not here
                is_harvest[farm.id].append(crop.name)
        ELSE:
            IF today matches a resolved planting_date for this crop:
                crop.active = true
                crop.planting_date = today
                crop.crop_day = 1
                crop.cumulative_water_received = 0
                crop.expected_total_water = SUM(
                    irrigation_m3_per_ha_per_day(planting_date, day)
                    for day in 1..season_length_days
                ) * effective_area_ha
                    # Sum of daily demands from the precomputed irrigation CSV.
                    # Represents full-season requirement under no supply constraint.
                    # Used at harvest to compute water stress yield penalty.
                crop.labor_schedule = precompute_daily_labor(crop_name, season_length_days)
                    # Build array of daily labor costs from activity lookup table.
                    # → calculations_economic.md § 27
```

#### Planting and Year-Boundary Rules

- Planting dates are MM-DD strings, resolved to absolute dates within the simulation period.
- Only one growth cycle is active per crop per farm at a time. Overlapping seasons are rejected at settings load time (Initialization Step 4).
- Crops spanning year boundaries continue uninterrupted. Only inactive crops receive new planting schedules at year start.
- `percent_planted` applies uniformly to all plantings for that crop.

#### Irrigation Demand Lookup

Only active crops with `crop_day` in `1..season_length_days` generate demand. Inactive crops and crops flagged for harvest (`crop_day > season_length_days`) produce zero.

```
base_demand_m3 = lookup irrigation_m3_per_ha_per_day from precomputed file
                 × effective_area_ha
                 (indexed by planting_date and crop_day)
```

→ structure.md § 4 (Precomputed / irrigation_demand) for file schema

The precomputed CSV contains columns for `growth_stage` and `kc` alongside `irrigation_m3_per_ha_per_day`. These are available for crop policy decisions (e.g., `deficit_irrigation` checks growth stage to decide its multiplier) without requiring the simulation to compute or track them.

This feeds into Step 1, where the crop policy may adjust the demand. Once water is delivered in Step 2, per-crop water receipt is tracked pro-rata by adjusted demand:

```
crop_water_delivered = farm_irrigation_delivered_m3 * (crop_adjusted_demand / farm_total_demand)
crop.cumulative_water_received += crop_water_delivered
```

At harvest, cumulative water received relative to expected total drives the water stress yield penalty:

```
water_ratio = clamp(cumulative_water_received / expected_total_water, 0, 1)
→ calculations_crop.md § 1 for water stress and yield formulas
```

---

### Step 1: Crop Policy

Adjust base irrigation demand for each farm's active crops.

```
    FOR each farm:
        FOR each active crop (crop_day in 1..season_length_days):
            base_demand_m3 = lookup_irrigation_m3_per_ha(planting_date, crop_day) * effective_area_ha
                             # → Irrigation Demand Lookup above
            growth_stage = lookup_growth_stage(planting_date, crop_day)
                           # from precomputed CSV column
            ctx = CropPolicyContext(
                crop_name,
                growth_stage,
                crop_day,
                season_length_days=crop_params.season_length_days,
                base_demand_m3,
                temperature_c=weather.temp_max_c)
            adjusted_demand_m3 = crop_policy.decide(ctx).adjusted_demand_m3
            → policies.md § 3
        farm_total_demand_m3 = SUM(adjusted_demand_m3 across active crops)

    Outputs: farm_total_demand_m3 per farm, crop_adjusted_demand per crop
```

### Step 2: Water Allocation

Water allocation uses a single community-level policy. All farms share one water policy that decides the groundwater/municipal split for the community's total irrigation demand. The result is distributed to farms pro-rata by their demand share.

**Step 2a — Community irrigation allocation:**

```
    total_irrigation_demand = SUM(farm_total_demand_m3 for all farms)

    # Resolve prices
    municipal_price = resolve_water_price("agricultural", current_date)
                      → Water Price Resolution below
    energy_price = resolve_energy_price("agricultural", current_date)
                   → Energy Price Resolution below

    ctx = WaterPolicyContext(
        demand_m3=total_irrigation_demand,
        treatment_kwh_per_m3=water_system.treatment_kwh_per_m3,
        pumping_kwh_per_m3=water_system.pumping_kwh_per_m3,
        conveyance_kwh_per_m3=water_system.conveyance_kwh_per_m3,
        gw_maintenance_per_m3=water_system.gw_maintenance_per_m3,
        municipal_price_per_m3=municipal_price,
        energy_price_per_kwh=energy_price,
        max_groundwater_m3=max_groundwater_m3_day,
        max_treatment_m3=max_treatment_m3_day,
        cumulative_gw_year_m3=cumulative_gw_year_m3,
        cumulative_gw_month_m3=cumulative_gw_month_m3,
        current_month=current_date.month,
        groundwater_tds_ppm=water_system.groundwater_tds_ppm,
        municipal_tds_ppm=water_system.municipal_tds_ppm)
    allocation = water_policy.allocate_water(ctx)
    → policies.md § 4

    # Municipal water is an unlimited backstop: any groundwater shortfall from
    # infrastructure constraints is shifted to municipal purchase. Total irrigation
    # delivery always equals demand — farms are never short-supplied.
```

**Step 2b — Pro-rata distribution to farms:**

```
    FOR each farm:
        IF total_irrigation_demand > 0:
            farm_share = farm_total_demand_m3 / total_irrigation_demand
        ELSE:
            farm_share = 0
        farm_gw_m3            = allocation.groundwater_m3 * farm_share
        farm_municipal_m3     = allocation.municipal_m3 * farm_share
        farm_irrigation_delivered_m3 = farm_gw_m3 + farm_municipal_m3
        farm_water_cost_usd   = allocation.cost_usd * farm_share
        farm_water_energy_kwh = allocation.energy_used_kwh * farm_share

        # Blended irrigation water quality
        IF farm_irrigation_delivered_m3 > 0:
            farm_blended_tds_ppm = (farm_gw_m3 * water_system.groundwater_tds_ppm
                                   + farm_municipal_m3 * water_system.municipal_tds_ppm)
                                   / farm_irrigation_delivered_m3
        ELSE:
            farm_blended_tds_ppm = 0
        # Feeds into salinity yield reduction when enabled → calculations_crop.md § 2

    # Distribute delivered water to per-crop cumulative trackers
    FOR each farm:
        FOR each active crop (crop_day in 1..season_length_days):
            IF farm_total_demand_m3 > 0:
                crop_water_delivered = farm_irrigation_delivered_m3
                                      * (crop_adjusted_demand / farm_total_demand_m3)
            ELSE:
                crop_water_delivered = 0
            crop.cumulative_water_received += crop_water_delivered

    Outputs: per-farm water cost, water energy, irrigation delivered, farm_blended_tds_ppm;
             per-crop cumulative_water_received updated
```

**Step 2c — Groundwater tracking:**  
*(Formerly Step 2d.)*

```
    # Water storage tracking is deferred pending a future design where the irrigation
    # storage tank serves as a real buffer (e.g., decoupled treatment scheduling).
    # Currently, irrigation_delivered = groundwater + municipal and treatment_output =
    # groundwater, so the storage delta is always zero.

    # Community-level groundwater tracking
    cumulative_gw_month_m3     += allocation.groundwater_m3
    cumulative_gw_year_m3      += allocation.groundwater_m3
    cumulative_gw_extraction_m3 += allocation.groundwater_m3

    State changes: crop.cumulative_water_received,
                   cumulative_gw_month_m3, cumulative_gw_year_m3, cumulative_gw_extraction_m3
```

### Step 3: Pre-Harvest Inventory Clearance

Sell expired storage tranches [batches of stored crop product, each carrying its origin farm shares, product type, and shelf-life expiry] before new harvest arrives. Returns revenue per farm — does not mutate any farm accumulator.

```
    expiry_revenue = {farm_id: {crop_name: 0} for each farm, crop}
    expiry_kg = {farm_id: {crop_name: 0} for each farm, crop}

    FOR tranche in shared_food_product_storage (oldest first):
        IF current_date >= tranche.expiry_date:
            price = prices[tranche.crop_name][tranche.product_type]
                    # Same daily price resolved in Step 0; fresh produce → crop price CSV,
                    # processed products → processed price CSV. See Pricing Resolution below.
                    # If price = 0: log warning and remove tranche with zero revenue
                    #   (treats expired zero-value stock as disposal, not a sale)
            sale_revenue = tranche.kg * price
            FOR each farm_id, fraction in tranche.farm_shares:
                expiry_revenue[farm_id][tranche.crop_name] += sale_revenue * fraction
                expiry_kg[farm_id][tranche.crop_name] += tranche.kg * fraction
            Remove tranche from storage

    → structure.md § 3.7 for expiry_date field (harvest_date + shelf_life_days from storage_spoilage_rates-toy.csv)
    → policies.md § 7 for forced sales rules (FIFO, pricing, attribution)
    Outputs: expiry_revenue (dict {farm_id: {crop_name: usd}}),
             expiry_kg (dict {farm_id: {crop_name: kg}})
```

### Step 4: Food Processing

Runs only on harvest days. Pool farm harvests and run through the processing pipeline.

```
    E_processing_today = 0
    harvest_kg_by_farm = {farm_id: 0 for each farm}
    IF any farm has a harvest today (from is_harvest in Step 0):

        # Collect per-farm harvest contributions
        FOR each farm with harvest:
            FOR each crop harvested:
                raw_yield_kg = Y_potential * water_stress_factor * yield_factor * effective_area_ha
                    # yield_factor = FarmState.yield_factor → structure.md § 3.2
                    # Y_potential from precomputed yield file; water_stress_factor from cumulative water ratio
                harvest_available_kg = raw_yield_kg * (1 - handling_loss_rate)
                → calculations_crop.md § 1 for yield and water stress formulas
                → structure.md § 2.5 for handling_loss_rate (default 5%)
                Pool into community_harvest_pool[crop]
                Track farm_kg per farm (post-handling-loss contribution to this crop's pool)
                harvest_kg_by_farm[farm.id] += harvest_available_kg

        # Apply food processing policy per crop
        FOR each crop in pool:
            fresh_price = prices.crop_prices[crop_name]
            ctx = FoodProcessingContext(
                harvest_available_kg=pooled_kg, crop_name=crop_name,
                fresh_price_per_kg=fresh_price)
            fractions = food_policy.allocate(ctx) → policies.md § 6
            # Create one StorageTranche per (crop, product_type) pathway with non-zero fraction:
            FOR each product_type with fraction > 0:
                input_kg = pooled_kg * fraction
                output_kg = input_kg * (1 - weight_loss_pct)
                    # weight_loss_pct from processing_specs-toy.csv keyed by (crop_name, product_type)
                shelf_life_days = lookup(storage_spoilage_rates-toy.csv, crop_name, product_type)
                expiry_date = harvest_date + shelf_life_days
                    # harvest_date = current_date (today)
                farm_shares = {farm_id: farm_kg / pooled_kg for each contributing farm}
                    # farm_kg is each farm's post-handling-loss contribution to this crop's pool
                    # → Revenue Attribution below for full attribution algorithm
                Append StorageTranche(product_type, crop_name, kg=output_kg,
                    harvest_date, expiry_date, sell_price_at_entry=fresh_price,
                    farm_shares) → structure.md § 3.7
            Add tranches to shared_food_product_storage

            # Processing energy: sum across all active pathways for this crop
            E_processing_today += SUM(input_kg * energy_kwh_per_kg_input for each pathway)
                # energy_kwh_per_kg_input: energy per kg of raw input (pre-weight-loss).
                # Sourced from processing_specs-toy.csv keyed by (crop_name, product_type).
                → calculations_economic.md § 26

        # Deactivate harvested crops
        FOR each farm with harvest:
            FOR each crop harvested:
                crop.active = false
                crop.crop_day = 0

    State changes: shared_food_product_storage updated with new tranches; harvested crops deactivated
    Outputs: E_processing_today, harvest_kg_by_farm
```

### Step 5: Sales

Market policy voluntary sales. No storage overflow check — storage capacity is unlimited.

```
    voluntary_revenue = {farm_id: {crop_name: 0} for each farm, crop}

    FOR each product_type in storage:
        FOR each crop with inventory of this product_type:
            available_kg = SUM(tranche.kg for tranches where product_type and crop_name match)
            price = prices[crop_name][product_type]
            ctx = MarketPolicyContext(
                crop_name=crop_name, product_type=product_type,
                available_kg=available_kg,
                current_price_per_kg=price,
                avg_price_per_kg=avg_prices[crop_name][product_type])
            decision = market_policy.decide(ctx) → policies.md § 8
            # Execute FIFO sell loop (simulation mechanics, not policy logic):
            sell_remaining_kg = available_kg * decision.sell_fraction
            FOR each tranche (oldest first, matching product_type and crop_name):
                IF sell_remaining_kg <= 0: BREAK
                IF tranche.kg <= sell_remaining_kg:
                    sale_revenue = tranche.kg * price
                    FOR each farm_id, fraction in tranche.farm_shares:
                        voluntary_revenue[farm_id][tranche.crop_name] += sale_revenue * fraction
                    Remove tranche from storage
                    sell_remaining_kg -= tranche.kg
                ELSE:
                    sale_revenue = sell_remaining_kg * price
                    FOR each farm_id, fraction in tranche.farm_shares:
                        voluntary_revenue[farm_id][tranche.crop_name] += sale_revenue * fraction
                    tranche.kg -= sell_remaining_kg
                    sell_remaining_kg = 0

    Outputs: voluntary_revenue (dict {farm_id: {crop_name: usd}})
```

### Step 6: Energy Dispatch

All energy demands for the day are known. Dispatch through merit-order [priority-ranked source dispatch]. The specific source sequence is determined by the active energy policy — see Energy Policies in policies.md § 5:


| Policy            | Merit Order                                               |
| ----------------- | --------------------------------------------------------- |
| `microgrid`       | PV → Wind → Battery → Generator (no grid)                 |
| `renewable_first` | PV → Wind → Battery → Grid (no generator)                 |
| `all_grid`        | Grid for all demand; all renewables exported (no battery) |


**Step 6a — Aggregate demand:**

```
    E_water_system      = allocation.energy_used_kwh
                          # allocation.energy_used_kwh = community total from Step 2a
    E_irrigation_pump   = total_irrigation_demand * irrigation_pressure_kwh_per_m3
                          # total_irrigation_demand from Step 2a
                          # irrigation_pressure_kwh_per_m3 → calculations_water.md § 4
    E_processing        = E_processing_today (from Step 4, same day)
    E_household         = from precomputed data
    E_community_bldg    = from precomputed data
    total_demand_kwh    = E_water_system + E_irrigation_pump
                        + E_processing + E_household + E_community_bldg

    # Note: pv_generated_kwh and wind_generated_kwh for DailyCommunityRecord
    # come from precomputed PV/wind data, not from DispatchResult.

    # curtailment_kwh = (pv_available + wind_available) - (pv_used + wind_used + exported + battery_charged)
    # Computed inside dispatch_energy() and returned in DispatchResult.
```

**Water energy term boundaries** (to prevent double-counting):


| Term                               | Applies to           | Included in                  |
| ---------------------------------- | -------------------- | ---------------------------- |
| E_pump (vertical lift)             | Groundwater only     | water policy energy_used_kwh |
| E_convey (horizontal transport)    | Groundwater only     | water policy energy_used_kwh |
| E_desal (treatment)                | Groundwater only     | water policy energy_used_kwh |
| E_irrigation_pump (field pressure) | ALL irrigation water | Computed separately          |


The water policy's `energy_used_kwh` already aggregates pump + convey + desal. `E_irrigation_pump` is separate because it applies to both groundwater and municipal water.

**Step 6b — Dispatch:**

```
    Collect energy policy flags from community → policies.md § 5
    # Energy policy is set at the community level (collective_farm_override).
    Combine flags: use_renewables, use_battery, grid_import,
                   grid_export, use_generator,
                   sell_renewables_to_grid, battery_reserve_pct

    # Compute available generation from precomputed data × nameplate capacity
    pv_available_kwh   = pv_kwh_per_kw(date, density) * pv_capacity_kw
    wind_available_kwh = wind_kwh_per_kw(date) * wind_capacity_kw

    dispatch_result = dispatch_energy(
        total_demand_kwh, combined_flags,
        pv_available_kwh, wind_available_kwh,
        battery_soc=energy.battery_soc,
        battery_capacity_kwh=energy.battery_capacity_kwh,
        soc_min=energy.soc_min, soc_max=energy.soc_max,
        eta_charge=energy.eta_charge, eta_discharge=energy.eta_discharge,
        generator_capacity_kw=energy.generator_capacity_kw,
        max_runtime_hours=energy.max_runtime_hours,
        grid_price_per_kwh, diesel_price_per_L, export_price_per_kwh)
        → calculations_energy.md § 5 for dispatch algorithm
        Generator fuel consumption uses the Willans line model → calculations_energy.md § 4

    # dispatch_result.battery_soc_after includes charge/discharge efficiency losses and self-discharge.
    energy.battery_soc = dispatch_result.battery_soc_after
        → calculations_energy.md § 3 for battery dynamics and self-discharge formula

    # dispatch_result includes curtailment_kwh: renewable generation that could not be
    # consumed, stored, or exported. Occurs when generation exceeds demand + battery
    # capacity + export capacity. Tracked for renewable sizing analysis.

    State changes: energy.battery_soc, energy_state.cumulative_diesel_L
    Outputs: dispatch_result (DispatchResult — PV, wind, battery, grid, generator,
             diesel_consumed_L, curtailment_kwh, costs)
             → structure.md § 3.12 for DispatchResult field list

    # Cumulative diesel tracking:
    # energy_state.cumulative_diesel_L += dispatch_result.diesel_consumed_L
    # Recorded in DailyCommunityRecord for emissions and fuel logistics metrics.
```

**Step 6c — Per-farm energy cost attribution:**

```
    # farm_demand_kwh_i: each farm's attributable energy demand (water + irrigation pump + processing)
    # community_demand_kwh: non-farm demand = E_household + E_community_bldg
    # total_demand_kwh: already computed in Step 6a

    total_harvest_kg_today = SUM(harvest_kg_by_farm.values())

    FOR each farm:
        farm_demand_kwh_i = farm_water_energy_kwh
                          + (farm_irrigation_delivered_m3 * irrigation_pressure_kwh_per_m3)
                          + (E_processing_today * harvest_kg_by_farm[farm.id] / total_harvest_kg_today)
                          # E_processing_today pro-rated by farm harvest contribution (0 on non-harvest days)
                          # If total_harvest_kg_today = 0: farm processing share = 0 (zero guard)
        farm_energy_cost_i = dispatch_result.total_energy_cost_usd * (farm_demand_kwh_i / total_demand_kwh)

    # Export revenue is attributed to farms using cost_allocation_method — the same method used for
    # shared infrastructure costs (Step 7b). Renewable capacity is community infrastructure; revenue
    # flows to farms only, not to community demand. Community energy costs are borne as a shared
    # operating expense, not an entitlement to export proceeds.
    FOR each farm:
        farm_export_revenue_i = allocate(dispatch_result.export_revenue_usd, cost_allocation_method)[farm]
        → structure.md § 2.8 for allocation methods (equal, area, usage-proportional)
        # Usage-proportional uses the same daily water consumption metric as Step 7b.

    community_demand_kwh = E_household + E_community_bldg
    community_energy_cost = dispatch_result.total_energy_cost_usd * (community_demand_kwh / total_demand_kwh)

    # Per-farm energy quantities for daily records:
    # farm_grid_import_kwh = dispatch_result.grid_import_kwh * (farm_demand_kwh_i / total_demand_kwh)
    # farm_renewable_used_kwh = (dispatch_result.pv_used_kwh + dispatch_result.wind_used_kwh)
    #                           * (farm_demand_kwh_i / total_demand_kwh)
    # grid_export_kwh is community-level (recorded in DailyCommunityRecord, not per-farm).
    # These quantities enable energy self-sufficiency and renewable fraction metrics.
```

### Step 7: Daily Accounting

Collect outputs from all preceding steps, compute costs, revenue, cash position, and append daily records. This is the single point where all financial flows roll up — no mutable accumulators from earlier steps.

**Step 7a — Shared costs (community-level):**

```
    daily_debt_service = monthly_debt_service_total / days_in_current_month
        # monthly_debt_service_total = SUM of monthly_payment for all loans where
        # schedule_month_index < total_months (i.e., not yet fully repaid).
        # Decreases as individual loans reach maturity. Read from the precomputed
        # amortization schedule (Init Step 12a) at the current month index.
        → calculations_economic.md § 7 for amortization formula

    # Community water (non-farm): households and community buildings use 100% municipal supply.
    # No on-site energy cost — municipal delivery does not flow through the treatment plant.
    community_water_demand = hw_demand + cw_demand
    community_water_cost = community_water_demand * resolve_water_price("community", current_date)

    Total_daily_shared_opex =
        daily_infrastructure_om (economic_state.infrastructure_annual_opex / 365)
      + daily_management_labor (13 hrs/day × blended wage)
          → calculations_economic.md § 27.2.3
      + daily_maintenance_labor (annual_maintenance_hours / 365 × blended wage)
          → calculations_economic.md § 27.2.4
      + daily_replacement_reserve (from Financial Baseline above)
      + community_water_cost (computed above)
      + community_energy_cost (from Step 6c)
      # Debt service is tracked separately below; do NOT include here.
```

**Step 7b — Allocate shared costs to farms:**

```
    FOR each farm:
        allocated_shared_i = allocate(Total_daily_shared_opex, cost_allocation_method)
        debt_service_share_i = allocate(daily_debt_service, cost_allocation_method)
        → structure.md § 2.8 for allocation methods (equal, area, usage-proportional)
```

**Step 7c — Per-farm cost and revenue rollup:**

```
    FOR each farm:
        # Farm-specific costs
        water_cost    = farm_water_cost_usd
                        # pro-rata share from Step 2b
        energy_cost   = farm_energy_cost_i
                        # attributed energy cost from Step 6c
        labor_cost    = SUM(crop_labor_schedule[crop.crop_day] for each active crop on this farm)
                        + harvest_labor_today
            # crop_labor_schedule: precomputed at planting for each crop cycle.
            # A 1D array indexed by crop_day containing the daily labor cost for
            # scheduled agricultural activities (land prep, transplanting, fertilization,
            # pest management, irrigation checks) based on growth stage timing.
            # Precomputed from the activity lookup table at crop activation.
            # harvest_labor_today: on harvest days, processing labor
            # (labor_hours_per_kg × harvested_kg × wage) + logistics labor.
            # Zero on non-harvest days.
            # Management and maintenance labor are in shared costs (Step 7a); do NOT include here.
            → calculations_economic.md § 27 for activity lookup table, rates, and wage categories
        labor_hours   = {category: hours for category in [agricultural, processing, logistics]}
            # agricultural: sum of activity hours across active crops for today
            # processing: labor_hours_per_kg × harvested_kg (harvest days only)
            # logistics: transport hours for sales/deliveries (harvest/sale days only)
            # Recorded in DailyFarmRecord for workforce planning metrics.
        input_cost    = SUM(
                            lookup(input_costs-toy.csv, crop_name).annual_cost_usd_per_ha
                            * crop.effective_area_ha / 365
                            for each active crop on this farm)
                        # Per-crop rate × per-crop area, summed across active crops.
                        # Each crop has its own annual_cost_usd_per_ha from the CSV.
                        → structure.md § 4 for input_costs-toy.csv schema
        storage_cost  = SUM over tranches remaining after Steps 3-5:
                            tranche.kg * tranche.farm_shares[farm_i]
                            * storage_cost_per_kg_per_day
                        # storage_cost_per_kg_per_day: looked up from storage_spoilage_rates-toy.csv
                        # keyed by (crop_name, product_type). Covers cold storage energy,
                        # facility overhead, and handling. Only inventory still in storage
                        # at end of day incurs cost.
                        → calculations_economic.md § 6 for storage cost rates

        farm_specific_costs = water_cost + energy_cost + labor_cost + input_cost + storage_cost
        total_cost = farm_specific_costs + allocated_shared_i + debt_service_share_i

        # Revenue (collected from Step 3 and Step 5 return values)
        crop_revenue_by_crop = {crop: expiry_revenue[farm.id][crop] + voluntary_revenue[farm.id][crop]
                                for each crop}
        crop_revenue   = SUM(crop_revenue_by_crop.values())
        export_revenue = farm_export_revenue_i  # from Step 6c
        total_revenue  = crop_revenue + export_revenue

        # Cash update
        farm.current_capital_usd += total_revenue - total_cost

        # Spoilage quantity (from Step 3 expiry_kg)
        spoilage_kg = SUM(expiry_kg[farm.id].values())
            # Total kg of expired product attributed to this farm today.

        # Append DailyFarmRecord → structure.md § 3.10
        # DailyFarmRecord includes both crop_revenue (total) and crop_revenue_by_crop (dict),
        # plus spoilage_kg (total kg expired, summed from expiry_kg).

    # Append DailyCommunityRecord → structure.md § 3.11
```

End of daily loop.

---

## Supporting Reference: Pricing Resolution

All prices come from **historical time-series CSV files**. The scenario YAML contains only regime selectors (`pricing_regime: subsidized | unsubsidized`) that determine which CSV file to load. No price values or escalation rates are stored in the YAML — the CSV data already encodes real-world tariff changes over time.

All price lookups are precomputed into a single daily price table at data load time. For each simulation day, the table contains resolved values for all water, energy, diesel, crop, and processed product prices. The forward-fill logic (find the most recent CSV entry whose date <= current_date) executes once during initialization, not per day. The `resolve_*_price()` functions described below document the resolution logic; at runtime they are simple table lookups by date.

Two consumer types determine which pricing regime applies:


| Consumer Type | Applies To                                     | Water Regime | Energy Regime |
| ------------- | ---------------------------------------------- | ------------ | ------------- |
| agricultural  | Farm irrigation, GW treatment, food processing | agricultural | agricultural  |
| community     | Households, community buildings                | community    | community     |


→ structure.md § 2.7 for pricing configuration schema

### Water Price Resolution

```
resolve_water_price(consumer_type, current_date):
    regime = water_pricing[consumer_type].pricing_regime
    RETURN lookup_csv_price("water", regime, current_date)
```

- Price data: `data/prices/water/historical_municipal_water_prices-research.csv`
- If `current_date` is outside the CSV date range, use the nearest available value.
- Agricultural water: flat rate from CSV (no tiers).
- Community water: same flat rate pattern. Tiered pricing is a future enhancement.
- All EGP values are converted to USD at data load time using a fixed exchange rate.

### Energy Price Resolution

```
resolve_energy_price(consumer_type, current_date):
    regime = energy_pricing[consumer_type].pricing_regime
    RETURN lookup_csv_price("electricity", regime, current_date)
```

- Price data (subsidized): `data/prices/electricity/historical_grid_electricity_prices-research.csv`
- Price data (unsubsidized): `data/prices/electricity/historical_grid_electricity_prices_unsubsidized-research.csv`
- Energy price for farm water treatment always uses the agricultural rate.

### Grid Export and Diesel Pricing

```
export_price_per_kwh = grid_import_price * net_metering_ratio
    # net_metering_ratio: configured in scenario YAML under energy_system.net_metering_ratio
    # (default 0.70). Represents the fraction of the import price paid for exported kWh.
    → structure.md § 2.6 for energy_system configuration
diesel_price_per_L = lookup_csv_price("diesel", current_date)
```

- Diesel data: `data/prices/diesel/historical_diesel_prices-research.csv`

### Crop and Processed Product Price Resolution

Fresh crop and processed product prices use the same forward-fill lookup as water and energy: find the most recent CSV entry whose date ≤ `current_date`. If `current_date` precedes the earliest entry, use the earliest value.

```
resolve_crop_price(crop_name, current_date):
    RETURN lookup_csv_price("crops", crop_name, current_date, column="usd_per_kg_farmgate")
    # Fallback: if usd_per_kg_farmgate column is absent (toy data), use usd_per_kg.

resolve_processed_price(crop_name, product_type, current_date):
    RETURN lookup_csv_price("processed", crop_name + "_" + product_type, current_date,
                            column="usd_per_kg")
```

- **Fresh crop data (research, annual):** `data/prices/crops/historical_{crop}_prices-research.csv`  
Columns: `date, usd_per_kg_farmgate, usd_per_kg_wholesale, usd_per_kg_retail, egp_per_kg_original, usd_egp_exchange_rate, season, notes`  
The simulation uses `usd_per_kg_farmgate`.
- **Fresh crop data (toy, monthly):** `data/prices/crops/historical_{crop}_prices-toy.csv`  
Columns: `date, usd_per_kg, season, market_condition, usd_per_kg_farmgate`  
Fallback to `usd_per_kg` if `usd_per_kg_farmgate` is absent.
- **Processed product data (toy, monthly):** `data/prices/processed/historical_{product_type}_{crop}_prices-toy.csv`  
Columns: `date, usd_per_kg, season, market_condition`  
Product types: `dried`, `canned`, `packaged`, `pickled`. Not all crops have all types.
- All CSVs contain metadata comment lines (`#`) that are skipped at load time.
- All prices are in USD per kilogram.

---

## Supporting Reference: Food Processing and Revenue Chain

This section documents the harvest-to-revenue data flow sequence and the revenue attribution algorithm. Calculation formulas follow the pointers given.

### Harvest-to-Revenue Chain

```
raw_yield_kg                                → calculations_crop.md § 1
  × (1 - handling_loss_rate)                → structure.md § 2.5 (default 5%)
  = harvest_available_kg
  → food policy split (fractions)           → policies.md § 6
  (Optional salinity yield reduction can be enabled — see calculations_crop.md § 2, deferred)
  → weight loss per pathway                 → structure.md § 2.5
  = processed_output_kg per product type
  → create StorageTranches                  → structure.md § 3.7
  → forced sales (shelf-life expiry)        → policies.md § 7
  → market policy (sell/store)              → policies.md § 8
  → revenue = sold_kg × price
```

### Revenue Attribution

Processing and selling operate on pooled community inventory. Revenue is attributed to individual farms through `farm_shares` on each StorageTranche:

```
# At tranche creation (Step 4):
# farm_kg = each farm's post-handling-loss contribution to this crop's pool
# pooled_kg = SUM(farm_kg) across all contributing farms
farm_shares = {farm_id: farm_kg / pooled_kg for each contributing farm}

# At sale (Steps 3, 5):
# Each step returns a nested revenue dict {farm_id: {crop_name: usd}} built by iterating farm_shares:
FOR each farm_id, fraction in tranche.farm_shares:
    step_revenue[farm_id][tranche.crop_name] += sale_revenue * fraction

# Step 7 collects the returned dicts and computes per-crop and total revenue:
crop_revenue_by_crop = {crop: expiry_revenue[farm_id][crop] + voluntary_revenue[farm_id][crop]
                        for each crop}
crop_revenue = SUM(crop_revenue_by_crop.values())
```

Attribution happens at point of sale, not at harvest. Each tranche's `farm_shares` reflects that specific batch's contributors. Revenue dicts are returned from each step and collected in Step 7 — no mutable accumulator on FarmState.

---

## Supporting Reference: Cost Allocation

Shared infrastructure costs are allocated across farms. The method is a community-level configuration parameter.

→ structure.md § 2.8 for `cost_allocation_method` options

### Allocation Methods

→ structure.md § 2.8 for the full method table and formulas.

Usage-proportional allocation uses daily farm water consumption as the usage metric.

### Shared Operating Costs

```
Total_shared_opex = infrastructure_om (water + energy + processing)
                  + management_labor (planning, coordination, sales, admin)
                  + maintenance_labor (PV, water treatment, irrigation, processing equipment)
                  + equipment_replacement_reserve
                  + community_water_cost (from Step 7a)
                  + community_energy_cost (from Step 6c)
```

Debt service is allocated separately in Step 7b and tracked as its own line in DailyFarmRecord. Farm-specific costs (seeds, fertilizer, field labor, logistics) are not shared.

---

## Error Handling

Guiding principle: **fail explicitly rather than inject defaults**.

### Zero-Demand Guards

Policies receiving zero-valued inputs return early with zero-valued outputs. No division by zero, no meaningless calculations.

→ policies.md § 2.3 for per-policy zero-demand behavior

### Division-by-Zero Prevention

All division operations guard against zero denominators:

- `water_use_efficiency`: if yield = 0, return inf
- `operating_margin`: if revenue = 0, return -100% if costs > 0, else 0%
- `price_ratio`: if avg_price = 0, treat as 1.0
- `farm_share`: if total_irrigation_demand = 0, farm_share = 0

### NaN Prevention

- Price lookups outside data range: return nearest available value (no NaN).
- All daily record fields validated before appending.
- During development: `IF isnan(value): RAISE RuntimeError`.

### Development-Only Consistency Checks

Run at the end of each simulation day. Disabled for production Monte Carlo runs.

```
# Energy balance: supply = demand + export + storage + curtailment + unmet (tolerance: 0.01 kWh)
# Inventory: all tranche.kg >= 0
```

---

## Post-Loop Reporting

After the final simulation day, these steps run once.

### Finalization

```
Step 1.  Record in-progress crops as part of the final state snapshot (Step 3 below).
         No financial adjustment — daily records already captured all costs.

Step 2.  Value terminal inventory at the last simulation day's prices (the same
         prices dict resolved in Step 0 on the final day):
         terminal_inventory_value = SUM(tranche.kg * prices[crop_name][product_type]
                                        for each remaining tranche)
         This is not a sale. It is added to the final year's net income for NPV/IRR only.
         → calculations_economic.md § 21 for NPV formula

Step 3.  Record final state snapshot → structure.md § 3.13 for schema.
         Fields: battery_soc,
                 per-farm cash_position_usd, total_debt_remaining_usd,
                 terminal_inventory_value_usd, cumulative_gw_extraction_m3,
                 in_progress_crops (list of {farm_id, crop_name, crop_day,
                 cumulative_water_received_m3}).
```

### Metric Computation

All metrics are computed from DailyFarmRecord and DailyCommunityRecord tables. Monthly and yearly totals are produced by summing daily record fields for the period — no in-loop snapshots or accumulators are needed.

```
Stage 1: Per-farm yearly metrics
         (water, energy, crop, revenue, costs, financial ratios)
         → calculations_water.md § 8-14 for water metrics
         → calculations_energy.md § 7-13 for energy metrics
         → calculations_economic.md § 12-25 for economic metrics

Stage 2: Community yearly metrics
         (cross-farm aggregation, distributional stats: median, min, max, Gini coefficient)
         → calculations_economic.md § 15 for CV [coefficient of variation], § 16 for revenue concentration;
           Gini formula in metrics_and_reporting.md § 1

Stage 3: Simulation-lifetime metrics
         (totals, averages, trends via linear slope [least-squares slope of the yearly
         metric series over the simulation years], volatility via CV)

Stage 4: Financial summary metrics
         (NPV, IRR, payback period, ROI)
         terminal_inventory_value (from Finalization above) added to final year net income
         before computing NPV and IRR.
         → calculations_economic.md § 18-21 for formulas
```

### Output Generation

Orchestrated by `write_results(state, scenario)`:

```
1. Create timestamped output directory: results/YYYY-MM-DD_HHMMSS/
2. Write daily_farm_records.csv and daily_community_records.csv
   → structure.md § 3.10-3.11 for field schemas
3. Compute and write monthly_summary.csv (aggregated from daily by summing fields per month)
   → structure.md § 3.14 for schema
4. Compute and write yearly_farm_metrics.csv and yearly_community_metrics.csv
5. Write simulation_summary.json (lifetime + financial metrics from Stages 3-4)
   → structure.md § 3.15 for schema
6. Write scenario echo (scenario.yaml + data_registry.yaml copies)
7. Generate plots → metrics_and_reporting.md § 2 for plot specifications
8. Generate summary tables → metrics_and_reporting.md § 2 for table specifications
9. Write final_state.json → structure.md § 3.13 for schema
```

For ensemble execution (Monte Carlo, sensitivity analysis), see `calculations.md § 3` and the `monte_carlo.py` / `sensitivity.py` modules. Ensemble runs wrap the single-simulation flow defined here and produce additional output files (monte_carlo_summary.json, sensitivity_ranking.csv).

---

*End of specification.*