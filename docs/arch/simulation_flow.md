# Simulation Flow Specification

## 1. Overview

This document specifies the complete order of operations, decision flows, and calculation pipelines for the Layer 3 daily simulation loop. It serves as the authoritative reference for how the simulation proceeds from day to day, how policies integrate with physical calculations, and how data flows between subsystems.

This specification was created to consolidate information that was previously distributed across `structure.md`, `policies.md`, and `calculations.md`. Where those documents define WHAT exists (structure), WHY decisions are made (policies), and HOW calculations work (calculations), this document defines the SEQUENCE and INTEGRATION of those elements during execution.

**Source documents:**

- `structure.md` -- Configuration schema and parameter definitions
- `policies.md` -- Policy decision logic and pseudocode
- `calculations.md` -- Calculation methodologies and formulas
- `overview.md` -- Model architecture and domain specifications

---

## 2. Daily Simulation Loop: Order of Operations

Each simulation day executes the following steps in strict order. Steps are numbered to match the execution sequence defined in `policies.md`. Every step lists its inputs, the operation performed, and its outputs.

### Pre-Loop Initialization (Once, Before Day 1)

Before the daily loop begins, the simulation performs one-time setup:

1. Load scenario configuration (Layer 2 output)
2. Load all precomputed data libraries (Layer 1 output) via `SimulationDataLoader`
3. Calculate per-farm system constraints (well capacity, treatment throughput) via `calculate_system_constraints()`
4. Calculate processing capacities from equipment configuration (once at scenario load)
5. Calculate household demand (daily constant) via `calculate_household_demand()`
6. Initialize `SimulationState` with farm states, aquifer state, energy state, economic state
7. Validate all required data files exist via registry
8. Set initial water storage to 50% of capacity
9. Set initial battery SOC to 50% of capacity
10. Compute infrastructure annual costs from financing profiles

### Daily Loop (For Each Day in Simulation Period)

```
FOR each day in simulation_period:

    # --- Step 0: Retrieve Daily Conditions ---
    Retrieve weather data (temperature, irradiance, wind speed, ET0)
    Retrieve crop growth stages for all active crops
    Retrieve current prices (crop, energy, water, diesel)
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

    # --- Step 2: Water Policy (Per Farm) ---
    FOR each farm:
        Resolve municipal_price_per_m3 (see Section 3: Pricing Resolution)
        Resolve energy_price_per_kwh (see Section 3: Pricing Resolution)
        Assemble WaterPolicyContext with farm_total_demand_m3
        Call water_policy.allocate_water(ctx) -> WaterAllocation
        Record water allocation (groundwater_m3, municipal_m3, cost_usd, energy_used_kwh)
        Update water storage state
        Update aquifer cumulative extraction tracking
        Append DailyWaterRecord

    # --- Step 2b: Household Water (Community-Level) ---
    Calculate household water demand (population * per_capita_L_day / 1000)
    Resolve domestic municipal_price_per_m3 (domestic pricing regime)
    Resolve domestic energy_price_per_kwh (domestic pricing regime)
    Assemble WaterPolicyContext with household demand
    Call household_water_policy.allocate_water(ctx) -> WaterAllocation
    Record household water allocation and costs

    # --- Step 3: Energy Policy and Dispatch (Community-Level) ---
    Aggregate all energy demand components:
        E_desal = sum of treatment energy across all farms
        E_pump = sum of pumping energy across all farms
        E_convey = sum of conveyance energy across all farms
        E_irrigation_pump = sum of irrigation pressurization energy
        E_processing = sum of food processing energy (from Step 4, previous day)
        E_household = daily household electricity demand
        E_other = community buildings, industrial
        total_demand_kwh = E_desal + E_pump + E_convey + E_irrigation_pump
                         + E_processing + E_household + E_other

    FOR each farm (or community if override):
        Assemble EnergyPolicyContext
        Call energy_policy.allocate_energy(ctx) -> EnergyAllocation

    Call dispatch_energy(total_demand_kwh, EnergyAllocation, ...) -> DispatchResult
        (See Section 5: Energy Policy Integration)
    Record energy dispatch results (PV, wind, battery, grid, generator, curtailment)
    Update battery SOC
    Append DailyEnergyRecord

    # --- Step 4: Food Processing Policy (Per Farm, Harvest Days Only) ---
    FOR each farm:
        FOR each crop with harvest today:
            Calculate harvest yield (see calculations.md Section 4)
            IF harvest_yield_kg == 0: SKIP (zero-demand guard)

            Assemble FoodProcessingContext
            Call food_policy.decide(ctx) -> ProcessingAllocation
            Apply capacity clipping (shared post-processing, see Section 4)
            Apply weight loss per pathway
            Create StorageTranches for each product type
            Calculate E_processing for today's throughput
            Add tranches to farm storage inventory

    # --- Step 4b: Forced Sales / Umbrella Rule (Per Farm) ---
    FOR each farm:
        Call check_forced_sales(farm_storage, current_date) -> forced_sale_list
            (See Section 4: FIFO and Umbrella Rule)
        FOR each forced sale:
            Sell at current market price
            Record revenue by product type
            Remove tranche from storage

    # --- Step 5: Market Policy (Per Farm) ---
    FOR each farm:
        FOR each product_type in storage (after forced sales):
            IF economic_policy.sell_inventory == true:
                sell_fraction = 1.0  (economic override)
            ELSE:
                Assemble MarketPolicyContext
                Call market_policy.decide(ctx) -> MarketDecision
                sell_fraction = MarketDecision.sell_fraction
            Execute sale: revenue = sell_kg * current_price_per_kg
            Update storage inventory
            Record revenue by crop and product type

    # --- Step 6: Economic Policy (Per Farm, Monthly) ---
    IF today is first day of month:
        FOR each farm:
            Compute months_of_reserves (trailing 12-month average opex)
            Assemble EconomicPolicyContext with previous month's data
            Call economic_policy.decide(ctx) -> EconomicDecision
            Store sell_inventory flag for use in Step 5 next month
            Store investment_allowed flag (reserved for future use)

    # --- Step 7: Daily Accounting ---
    FOR each farm:
        Aggregate daily costs (water, energy, labor, inputs, storage)
        Aggregate daily revenue (crop sales, grid export)
        Update farm cash position: cash += revenue - costs
        Deduct daily debt service allocation (monthly_payment / days_in_month)
        Deduct daily storage costs for held inventory

    # --- Step 8: Boundary Operations ---
    IF today is first day of new month:
        Reset monthly cumulative groundwater tracking
        Reset monthly household water consumption (for tiered pricing)
        Snapshot monthly metrics

    IF today is first day of new year:
        Compute yearly metrics snapshot (see Section 7)
        Reset yearly cumulative groundwater tracking
        Update aquifer drawdown and effective pumping head
        Update PV degradation factor
        Update battery capacity degradation
        Reinitialize farm crops for new year planting schedule
```

### Processing Energy Timing Note

`E_processing` for today's harvest is computed during Step 4 but enters the energy dispatch in Step 3 of the NEXT day. This one-day lag is acceptable at a daily time-step and avoids circular dependency between food processing and energy dispatch within the same day.

---

## 3. Pricing Resolution Pipeline

This section documents the complete end-to-end chain for how prices are resolved before they reach policy contexts. This addresses the dual agricultural/domestic pricing regimes defined in `structure.md` and clarifies currency handling.

### 3.1 Currency Handling

All internal calculations use USD. All prices stored in data files may be in either USD or EGP. A configurable base-year exchange rate converts all EGP values to USD at data load time.

```
Value_USD = Value_EGP / exchange_rate_EGP_per_USD
```

The exchange rate is fixed for the simulation run (constant-year, real terms). It is set in the scenario configuration under `economics.exchange_rate_egp_per_usd`. This avoids mixing currencies during arithmetic and ensures all cost comparisons are consistent.

Data files containing EGP values (notably tiered water pricing and grid electricity tariffs) must be converted to USD during loading, not at each daily calculation.

### 3.2 Consumer Type Classification

Every water and energy demand is classified by consumer type before price resolution:

| Consumer Type | Applies To | Water Regime | Energy Regime |
|---|---|---|---|
| `agricultural` | Farm irrigation, groundwater treatment, food processing | `water_pricing.agricultural` | `energy_pricing.agricultural` |
| `domestic` | Households, community buildings, shared facilities | `water_pricing.domestic` | `energy_pricing.domestic` |

The simulation loop determines consumer type based on the source of demand, not the policy. Farm water demand is always agricultural. Household water demand is always domestic.

### 3.3 Water Price Resolution

```
resolve_water_price(consumer_type, cumulative_monthly_m3):

    IF consumer_type == "agricultural":
        config = water_pricing.agricultural
        IF config.pricing_regime == "subsidized":
            RETURN config.subsidized.price_usd_per_m3  (flat rate)
        ELSE:  # unsubsidized
            base = config.unsubsidized.base_price_usd_m3
            years_elapsed = current_year - base_year
            RETURN base * (1 + config.unsubsidized.annual_escalation_pct / 100) ^ years_elapsed

    IF consumer_type == "domestic":
        config = water_pricing.domestic
        IF config.pricing_regime == "subsidized":
            # Tiered pricing with monthly consumption tracking
            RETURN get_marginal_tier_price(cumulative_monthly_m3, config.subsidized.tier_pricing)
        ELSE:  # unsubsidized
            base = config.unsubsidized.base_price_usd_m3
            years_elapsed = current_year - base_year
            RETURN base * (1 + config.unsubsidized.annual_escalation_pct / 100) ^ years_elapsed
```

**Key behaviors:**

- Agricultural water: Always a flat rate (subsidized or unsubsidized with escalation). No tiered pricing.
- Domestic water (subsidized): Uses Egyptian-style progressive tiered brackets with monthly consumption tracking. The `cumulative_monthly_m3` counter resets on the first day of each month. The `get_marginal_tier_price()` function returns the price of the NEXT unit of consumption, which is the relevant price for policy cost comparisons.
- Domestic water (unsubsidized): Flat rate with annual escalation.
- Wastewater surcharge applies to domestic tiered pricing only: `total_cost *= (1 + wastewater_surcharge_pct / 100)`.
- Agricultural and domestic pricing regimes are independent -- one can be subsidized while the other is not.

### 3.4 Energy Price Resolution

```
resolve_energy_price(consumer_type):

    IF consumer_type == "agricultural":
        config = energy_pricing.agricultural
        IF config.pricing_regime == "subsidized":
            RETURN config.subsidized.price_usd_per_kwh
        ELSE:
            RETURN config.unsubsidized.price_usd_per_kwh

    IF consumer_type == "domestic":
        config = energy_pricing.domestic
        IF config.pricing_regime == "subsidized":
            RETURN config.subsidized.price_usd_per_kwh
        ELSE:
            RETURN config.unsubsidized.price_usd_per_kwh
```

**Key behaviors:**

- Both agricultural and domestic energy pricing are flat rates (subsidized or unsubsidized).
- Agricultural and domestic pricing regimes are independent.
- The energy price passed to the water policy context is always the agricultural rate (since farm water treatment is an agricultural activity).
- The energy price used for household demand is the domestic rate.

### 3.5 Grid Export Pricing

Grid export revenue uses a net metering ratio applied to the grid import price:

```
export_price_per_kwh = grid_import_price * net_metering_ratio
```

- `net_metering_ratio`: Configurable, default 0.70 (reflecting Egypt's evolving net metering policy where export is compensated below retail import price).
- `grid_import_price`: The applicable energy price for the consumer type generating the export. For community-owned renewables serving agricultural load, use the agricultural energy price.
- Configuration: `energy_pricing.net_metering_ratio` (new parameter in scenario YAML).

### 3.6 Diesel Price Resolution

```
diesel_price_per_L = lookup from historical_diesel_prices data for current_date
```

Diesel is not split by consumer type. A single price applies to all generator fuel consumption.

---

## 4. Food Processing, Market, and Revenue Chain

This section documents the complete end-to-end flow from harvest to revenue, consolidating logic from `policies.md` Sections 3-4 and `calculations.md` Sections 4-5. The chain must be followed exactly to avoid double-counting revenue or mishandling weight loss.

### 4.1 Chain Overview

```
harvest_yield_kg
    -> food policy split (fractions by pathway)
    -> capacity clipping (shared post-processing)
    -> weight loss per pathway (physical transformation)
    -> processed_output_kg per product type
    -> create StorageTranches
    -> check forced sales (umbrella rule: expiry + overflow)
    -> market policy decision (sell/store remaining)
    -> revenue calculation (sold_kg * price_per_kg per product type)
```

### 4.2 Harvest Yield Calculation

On harvest days, the raw yield is computed:

```
raw_yield_kg = Y_potential * water_stress_factor * yield_factor * effective_area_ha

water_stress_factor = 1 - K_y * (1 - water_ratio)
water_ratio = clamp(cumulative_water_received / expected_total_water, 0, 1)
effective_area_ha = plantable_area_ha * area_fraction * percent_planted
```

`raw_yield_kg` enters the food processing pipeline. Post-harvest handling losses are applied per pathway (see weight loss below), NOT as a separate pre-processing step. This prevents double-counting.

### 4.3 Food Policy Split

The food processing policy returns fractions that sum to 1.0:

```
ProcessingAllocation:
    fresh_fraction      # e.g., 0.50
    packaged_fraction   # e.g., 0.20
    canned_fraction     # e.g., 0.15
    dried_fraction      # e.g., 0.15
    decision_reason     # e.g., "balanced_default"
```

### 4.4 Capacity Clipping (Shared Post-Processing)

After every food policy returns its target fractions, capacity clipping runs as a shared step. This is NOT part of any individual policy -- it is applied universally.

```
clip_to_capacity(harvest_yield_kg, allocation, capacities):
    FOR each pathway in [packaged, canned, dried]:
        allocated_kg = harvest_yield_kg * allocation[pathway]
        IF allocated_kg > capacities[pathway]:
            excess_kg = allocated_kg - capacities[pathway]
            allocation[pathway] = capacities[pathway] / harvest_yield_kg
            allocation.fresh += excess_kg / harvest_yield_kg
            allocation.decision_reason += "_capacity_clipped"
    RETURN allocation
```

Fresh has no practical capacity limit. Processing capacities are calculated once at scenario load time from equipment configuration:

```
capacity_kg_per_day = sum(equipment.throughput_kg_per_day * equipment.availability_factor)
    for each equipment item in the pathway
```

`availability_factor` defaults to 0.90 (accounting for maintenance downtime).

### 4.5 Weight Loss and Processed Output

Each pathway has a crop-specific weight loss factor from `processing_specs-toy.csv`:

```
FOR each pathway:
    input_kg = harvest_yield_kg * clipped_fraction
    output_kg = input_kg * (1 - weight_loss_pct / 100)
```

Weight loss values (examples from data):

| Crop | Fresh | Packaged | Canned | Dried |
|---|---|---|---|---|
| Tomato | 0% | 3% | 15% | 88% |
| Potato | 0% | 3% | 15% | 78% |

The `output_kg` is what enters storage and is eventually sold. Revenue is always based on `output_kg`, not `input_kg`.

### 4.6 Processing Energy Calculation

Processing energy is computed from actual throughput:

```
E_processing_today = SUM over pathways:
    input_kg[pathway] * energy_per_kg[pathway]
```

Where `energy_per_kg` is loaded from equipment parameter files (kWh/kg by processing type). This value feeds into the NEXT day's energy dispatch (see Section 2, Processing Energy Timing Note).

### 4.7 StorageTranche Dataclass

Each processed batch is tracked as a discrete tranche for FIFO inventory management:

```
StorageTranche:
    product_type: str       # "fresh", "packaged", "canned", "dried"
    crop_name: str          # e.g., "tomato"
    kg: float               # output_kg (after weight loss)
    harvest_date: date      # date of harvest
    expiry_date: date       # harvest_date + shelf_life_days
    sell_price_at_entry: float  # price at time of storage (for tracking, not for sale)
```

- `shelf_life_days` is loaded from `spoilage_rates-toy.csv` (per crop, per product type).
- Tranches are stored in a list per farm, ordered by `harvest_date` (oldest first = FIFO).
- `expiry_date = harvest_date + timedelta(days=shelf_life_days)`

### 4.8 FIFO Forced Sales (Umbrella Rule)

The umbrella rule runs AFTER food processing updates storage for the day (Step 4b), BEFORE the market policy runs (Step 5). It handles two conditions:

```
check_forced_sales(farm_storage, current_date, storage_capacities):
    forced_sales = []

    # 1. Expiry check: sell anything at or past expiry
    FOR tranche in farm_storage (oldest first):
        IF current_date >= tranche.expiry_date:
            forced_sales.append(tranche)
            remove tranche from farm_storage

    # 2. Overflow check: if total storage exceeds capacity, sell oldest first
    FOR product_type in ["fresh", "packaged", "canned", "dried"]:
        total_stored = sum(t.kg for t in farm_storage if t.product_type == product_type)
        capacity = storage_capacities[product_type]
        WHILE total_stored > capacity:
            oldest = first tranche of this product_type in farm_storage
            overflow_kg = total_stored - capacity
            IF oldest.kg <= overflow_kg:
                forced_sales.append(oldest)
                total_stored -= oldest.kg
                remove oldest from farm_storage
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

### 4.9 Revenue Calculation

Revenue is calculated per sale event (both forced and voluntary):

```
sale_revenue = sold_kg * current_price_per_kg(crop_name, product_type)
```

Where `current_price_per_kg` is looked up from the appropriate price data file:

- Fresh: `data/prices/crops/` (farmgate prices)
- Packaged/Canned/Dried: `data/prices/processed/` (processed product prices)

Revenue is recorded by farm, by crop, and by product type. This enables separate reporting of fresh vs. processed revenue without double-counting, because each kg of harvest enters exactly one pathway and is sold exactly once.

### 4.10 Daily Storage Costs

Holding inventory incurs a daily storage cost:

```
daily_storage_cost = SUM over all tranches in farm_storage:
    tranche.kg * storage_cost_per_kg_per_day(tranche.product_type)
```

Storage cost rates are loaded from a parameter CSV file (per product type). These costs are deducted daily in Step 7 (Daily Accounting).

---

## 5. Energy Policy Integration with dispatch_energy()

This section specifies how energy policies connect to the dispatch function. Energy policies return configuration flags; the dispatch function consumes those flags to determine the merit order and source availability.

### 5.1 Integration Contract

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

### 5.2 EnergyAllocation Flags

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

### 5.3 dispatch_energy() Behavior by Policy

The dispatch function MUST respect the allocation flags. The merit order is determined by the combination of flags:

**`microgrid` (use_renewables=T, use_battery=T, grid_import=F, grid_export=F, use_generator=T):**

```
Merit order: PV -> Wind -> Battery discharge -> Generator
Surplus: Battery charge -> Curtailment (no grid export)
Unmet after generator: Record as unmet_demand_kwh
```

**`renewable_first` (use_renewables=T, use_battery=T, grid_import=T, grid_export=T, use_generator=F):**

```
Merit order: PV -> Wind -> Battery discharge -> Grid import
Surplus: Battery charge -> Grid export
Generator: Not dispatched (grid_import=T makes it unnecessary)
```

**`all_grid` (use_renewables=F, use_battery=F, grid_import=T, grid_export=T, sell_renewables_to_grid=T):**

```
All demand met from grid import
All PV/wind generation exported to grid (revenue = generation * export_price)
Battery: Not used
```

### 5.4 Dispatch Algorithm (Pseudocode)

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
        available_discharge = (battery_soc - allocation.battery_reserve_pct) * battery_capacity_kwh
        available_discharge = max(0, available_discharge) * eta_discharge
        battery_discharged = min(available_discharge, remaining_demand)
        remaining_demand -= battery_discharged

    # --- Grid import ---
    IF allocation.grid_import AND remaining_demand > 0:
        grid_imported = remaining_demand
        remaining_demand = 0

    # --- Generator ---
    IF allocation.use_generator AND remaining_demand > 0:
        generator_capacity_kwh = generator_capacity_kw * hours_per_day
        gen_output = min(remaining_demand, generator_capacity_kwh)
        # Enforce minimum load constraint
        IF gen_output < generator_capacity_kw * 0.30 * hours_per_day:
            gen_output = 0  # Too small to run generator efficiently
        generator_used = gen_output
        remaining_demand -= generator_used

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
    generator_fuel_L = calculate_fuel(generator_used, generator_capacity_kw)
    generator_cost = generator_fuel_L * diesel_price_per_L
    export_revenue = grid_exported * export_price_per_kwh
    total_energy_cost = grid_cost + generator_cost - export_revenue

    RETURN DispatchResult(...)
```

### 5.5 Total Energy Demand Components

All six demand components MUST flow into the dispatch:

```
total_demand_kwh = E_desal + E_convey + E_pump + E_irrigation_pump
                 + E_processing + E_household + E_other

WHERE:
    E_desal = groundwater_m3 * treatment_kwh_per_m3
    E_pump = groundwater_m3 * pumping_kwh_per_m3
    E_convey = groundwater_m3 * conveyance_kwh_per_m3  (default 0.2 kWh/m3)
    E_irrigation_pump = total_irrigation_m3 * irrigation_pressure_kwh_per_m3
        irrigation_pressure_kwh_per_m3 = (P_bar * 100000) / (eta_pump * 3600000)
        # At 1.5 bar, eta=0.75: ~0.056 kWh/m3
    E_processing = sum(throughput_kg * energy_per_kg) by pathway (from previous day)
    E_household = daily_household_kwh (constant, computed pre-loop)
    E_other = community_buildings + industrial (from precomputed data or scenario config)
```

---

## 6. Per-Farm Cost Allocation

Shared infrastructure costs (water treatment, energy systems, processing facilities) must be allocated across farms. The allocation method is a community-level configuration parameter.

### 6.1 Allocation Methods

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

### 6.2 What Counts as Shared OPEX

```
Total_shared_opex = water_system_om + energy_system_om + processing_system_om
                  + debt_service (all infrastructure loans)
                  + equipment_replacement_reserve
                  + administrative_labor_costs
```

Farm-specific costs (seeds, fertilizer, field labor) are NOT shared and are charged directly to the farm that incurs them.

### 6.3 Per-Farm Net Income

```
Net_income_farm_i = Revenue_farm_i - farm_specific_costs_i - allocated_shared_opex_i
```

Community-level net income = sum of all farm net incomes.

---

## 7. Monthly and Yearly Boundary Operations

### 7.1 Monthly Boundaries (First Day of Each Month)

Operations triggered on the first simulation day of each month:

1. **Economic policy execution:**
    - Compute `months_of_reserves` using trailing 12-month average operating costs:
      ```
      avg_monthly_opex = sum(opex for last 12 months) / min(12, months_elapsed)
      months_of_reserves = cash_reserves_usd / avg_monthly_opex
      ```
    - For the first year (months_elapsed < 12), use the available months as the denominator.
    - Assemble `EconomicPolicyContext` with PREVIOUS month's aggregated revenue and costs.
    - Call `economic_policy.decide(ctx)` and store the resulting flags.

2. **Domestic water tier reset:**
    - Reset `cumulative_monthly_domestic_water_m3` to 0 for tiered pricing calculation.

3. **Monthly metrics snapshot:**
    - Aggregate daily records for the completed month.
    - Compute monthly totals for water, energy, revenue, and costs.

### 7.2 Yearly Boundaries (First Day of Each Year)

Operations triggered on the first simulation day of each new year:

1. **Yearly metrics snapshot:**
    - Compute all metrics defined in `structure.md` Section 4 (water, energy, crop, economic, resilience).
    - Store as `YearlyFarmMetrics` per farm and community-level aggregates.

2. **Aquifer state update:**
    - Compute net annual depletion:
      ```
      net_depletion = annual_gw_extraction - aquifer_recharge_rate_m3_yr
      remaining_volume -= net_depletion
      ```
    - Update effective pumping head (drawdown feedback):
      ```
      fraction_depleted = cumulative_extraction / aquifer_exploitable_volume_m3
      drawdown_m = max_drawdown_m * fraction_depleted
      effective_head_m = well_depth_m + drawdown_m
      ```
    - Recompute `pumping_kwh_per_m3` with new effective head.

3. **Equipment degradation:**
    - PV: `degradation_factor *= (1 - 0.005)` (0.5%/yr)
    - Battery: Update effective capacity per calendar + cycle aging model.

4. **Crop reinitialization:**
    - Reset crop states for new planting schedule.
    - Reset cumulative water tracking per crop.

5. **Reset yearly accumulators:**
    - Reset `cumulative_gw_year_m3` to 0.
    - Reset yearly energy accumulators (PV, wind, grid, generator, curtailment).

---

## 8. Household Policy Integration

### 8.1 Household Demand Calculation

Household demand is computed once before the simulation loop and treated as a daily constant:

```
household_water_m3_day = community_population * per_capita_water_L_day / 1000
household_energy_kwh_day = community_population * per_capita_energy_kwh_day
    + community_buildings_m2 * energy_per_m2_day
    + industrial_buildings_m2 * energy_per_m2_day
```

Per-capita values are loaded from `data/precomputed/household/household_demand-toy.csv` (or research variant). These values account for seasonal variation if the data file includes monthly profiles.

### 8.2 Household Water Policy

Household water demand uses the domestic pricing regime and a restricted set of water policies:

- **Available policies:** `max_groundwater`, `max_municipal`, `microgrid`
- **Configured in:** `household_policies.water_policy` in scenario YAML
- **Pricing:** Domestic water pricing regime (tiered if subsidized, flat if unsubsidized)
- **Infrastructure:** Shares the same wells and treatment infrastructure as farms (capacity is shared via area-proportional allocation, with households treated as a single "virtual farm" for allocation purposes)

### 8.3 Household Energy Policy

Household energy demand uses the domestic pricing regime and any energy policy:

- **Available policies:** `microgrid`, `renewable_first`, `all_grid`
- **Configured in:** `household_policies.energy_policy` in scenario YAML
- **Pricing:** Domestic energy pricing regime

### 8.4 Integration with Dispatch

Household energy demand is included in the community-level `total_demand_kwh` that flows into `dispatch_energy()`. It is NOT dispatched separately. The energy policy for households determines whether household demand should draw from renewables, battery, grid, or generator -- but since dispatch is community-level, the household policy flags are combined with farm policy flags.

When farm and household energy policies differ:

- The dispatch function uses the MOST PERMISSIVE combination of flags. For example, if farms use `microgrid` (no grid) but households use `renewable_first` (grid allowed), grid import is enabled for the community.
- Energy costs are then allocated back to farm vs. household based on their respective demand shares and applicable pricing regimes.

---

## 9. Error Handling Specification

This section defines how the simulation handles edge cases, invalid inputs, and arithmetic hazards. The guiding principle is: **fail explicitly rather than inject default values**. Silent fallbacks hide bugs; explicit failures surface them during development.

### 9.1 Zero-Demand Guards

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

### 9.2 Division-by-Zero Prevention

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

### 9.3 Invalid Parameter Handling

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

### 9.4 NaN Propagation Prevention

NaN values must not propagate through calculations. Key insertion points where NaN can enter:

1. **Price lookups:** If a date falls outside the price data range, the lookup must return the nearest available value (extrapolation by last known value), not NaN.
2. **Division results:** All division operations listed in Section 9.2 must guard against producing NaN.
3. **Cumulative sums:** If any daily record contains NaN, the yearly aggregation will be NaN. Daily records must be validated before appending.

Guard pattern:

```
IF isnan(value):
    RAISE RuntimeError(f"NaN detected in {variable_name} on {current_date}")
```

This is intentionally aggressive. During development, NaN should crash the simulation immediately so the source can be traced. Production runs can relax this to logging + substitution if needed.

### 9.5 State Consistency Checks

At the end of each simulation day, verify:

```
# Material balance: water in = water out
total_water_allocated = sum(farm.gw_m3 + farm.muni_m3 for all farms) + household_water
total_water_demand = sum(farm.demand_m3 for all farms) + household_demand
assert abs(total_water_allocated - total_water_demand) < 0.01

# Energy balance: generation + import = demand + export + storage + curtailment + unmet
total_supply = pv_used + wind_used + grid_imported + generator_used + battery_discharged
total_sink = total_demand_kwh + grid_exported + battery_charged + curtailed + unmet_demand
assert abs(total_supply - total_sink) < 0.01

# Cash balance: no negative inventory
FOR each farm:
    assert all(tranche.kg >= 0 for tranche in farm_storage)
```

These checks run every day during development. They can be disabled for production Monte Carlo runs where performance matters, but should be re-enabled when investigating anomalous results.

---

## 10. Flags for Owner Review

The following items were unclear, potentially inconsistent, or require decisions that fall outside the scope of the source documents. Each is marked for owner input.

### [NEEDS OWNER INPUT] 10.1 Processing Energy Timing

E_processing is computed during food processing (Step 4) but enters energy dispatch in Step 3. This specification uses a one-day lag (today's processing energy is dispatched tomorrow). Alternative: compute E_processing from the market policy's storage decisions and add it to today's demand. The one-day lag is simpler and adequate at a daily time-step, but the owner should confirm this is acceptable.

### [NEEDS OWNER INPUT] 10.2 Household Infrastructure Capacity Share

Section 8.2 proposes treating households as a "virtual farm" for infrastructure sharing. This means household water demand competes with farm water demand for well and treatment capacity. Alternative: reserve a fixed fraction of capacity for households (e.g., 10%). The owner should decide whether households share the same capacity pool as farms or have a dedicated allocation.

### [NEEDS OWNER INPUT] 10.3 Energy Policy Conflict Resolution

Section 8.4 proposes that when farm and household energy policies differ, the dispatch uses the most permissive combination of flags. This means a single household choosing `all_grid` could enable grid import for the entire community even if all farms chose `microgrid`. Alternative: dispatch farm and household energy demand separately. The owner should decide whether energy dispatch is truly community-wide or can be split.

### [NEEDS OWNER INPUT] 10.4 Economic Policy sell_inventory Override Scope

Section 2 (Step 5) specifies that when `economic_policy.sell_inventory == true`, the market policy is overridden with `sell_fraction = 1.0`. Two open questions:

1. Does this apply to ALL stored inventory across all product types and crops, or only to specific product types?
2. Does the override last for one month (until the next economic policy evaluation) or until the economic policy revokes it?

This specification assumes: all inventory, lasting one month. Owner should confirm.

### [NEEDS OWNER INPUT] 10.5 Forced Sales vs. Market Policy on Same Day

On harvest days, new tranches are added (Step 4), forced sales execute (Step 4b), then market policy runs (Step 5). If both forced sales and market policy sell inventory on the same day, should forced sales revenue be counted separately from voluntary sales for metrics and reporting purposes? This specification assumes yes (tagged with `decision_reason = "forced_expiry"` or `"forced_overflow"`), but the owner should confirm.

### [NEEDS OWNER INPUT] 10.6 Community-Override Policy vs. Farm-Level Policy YAML Schema

The specification references community-override policies but the YAML schema for how overrides are expressed is not defined in any source document. Proposed schema:

```yaml
community_policies:
    water_policy: cheapest_source    # overrides all farm water policies
    energy_policy: null              # no override, farms use individual
    food_policy: null
    market_policy: null
    crop_policy: null
    economic_policy: null
```

If `community_policies.<domain>` is non-null, it overrides all individual farm selections for that domain. Owner should confirm this schema.

### [NEEDS OWNER INPUT] 10.7 Storage Cost Data Source

Section 4.10 references `storage_cost_per_kg_per_day` by product type, but no CSV file currently exists for this data. The review (issue 4.5) recommends creating one. Values need to be researched and added to the data registry. Suggested file: `data/parameters/crops/storage_costs-toy.csv` with columns: `product_type, cost_per_kg_per_day_usd`.

### [NEEDS OWNER INPUT] 10.8 E_other Demand Component

Section 5.5 includes `E_other` (community buildings, industrial) as an energy demand component. No source document specifies how this is calculated or where the data comes from. It may be bundled into `E_household` via `calculate_household_demand()`, or it may need its own calculation. Owner should clarify whether community/industrial building energy is part of household demand or a separate category.

### [NEEDS OWNER INPUT] 10.9 Generator Minimum Load Behavior

The dispatch algorithm (Section 5.4) skips the generator entirely if the remaining demand is below the 30% minimum load threshold. This means small deficits go unmet under the `microgrid` policy. Alternative: run the generator at minimum load and curtail the excess. The owner should decide which behavior is correct. The current specification uses skip-if-too-small, which means `microgrid` policy may report non-zero `unmet_demand_kwh`.

### [NEEDS OWNER INPUT] 10.10 Multiple Planting Dates per Crop

`structure.md` allows `planting_dates` as a list of MM-DD strings (e.g., `["02-15", "11-01"]`). This implies multiple plantings of the same crop per year on the same farm. No source document specifies how area is split across plantings, whether harvests overlap, or how water tracking works across concurrent growth cycles of the same crop. This specification does not address multi-planting logic. The owner should clarify the intended behavior before implementation.

---

*End of specification.*
