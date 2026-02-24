# Simulation Flow Specification

## Overview

This document specifies the **order of operations** for the Layer 3 daily simulation. It defines when things happen, what feeds what, and where state changes occur. It assumes all necessary data (weather, prices, baseline crop demands) is precomputed and available.

### Simulation at a Glance

The simulation has three phases: **initialization**, a **daily loop**, and **post-loop reporting**.

The daily loop includes the following steps:


| Step | Name                 | Scope     | Key Action                                                          |
| ---- | -------------------- | --------- | ------------------------------------------------------------------- |
| 0    | Daily setup          | Community | Retrieve weather/prices, advance crops, trigger plantings.          |
| 1    | Crop policy          | Per farm  | Adjust precomputed base irrigation demand per crop policy.          |
| 2    | Water allocation     | Community | Allocate GW/municipal supply pro-rata; calculate municipal costs.   |
| 3    | Harvest & Processing | Community | Pool harvests, calculate labor, apply food policy, store tranches.  |
| 4    | Sales                | Community | Market policy voluntary sales (generates revenue).                  |
| 5    | Energy dispatch      | Community | Aggregate physical demand, dispatch merit-order, return total bill. |
| 6    | Daily accounting     | Per farm  | Split shared OPEX, attribute energy bills, update cash, cleanup.    |


---

## Initialization

Before the daily loop begins, establish the data environment, absolute timelines, and financial baseline.

### Data Loading and Scenario Setup

1. Validate all required data files exist via registry.
2. Load scenario configuration via `load_scenario()`.
3. Precompute Absolute Planting Schedules:
  - Instead of calculating crop seasons dynamically at year boundaries, resolve ALL planting dates to absolute dates for the entire simulation timeframe.
  - For each farm and each crop:
    - Resolve planting_dates (MM-DD) to absolute YYYY-MM-DD dates.
    - Verify no overlapping seasons per crop per farm.
    - Precompute `expected_total_water` (sum of precomputed daily irrigation demands).
    - Precompute `labor_schedule` (array of daily labor costs per crop_day).
    - Push into `farm.planting_queue`.
4. Load all precomputed data libraries (weather, baseline irrigation, prices, etc.).
5. Calculate community infrastructure constraints:
  - `max_groundwater_m3_day = well_flow_rate_m3_day × number_of_wells`
  - `max_treatment_m3_day  = water_treatment.system_capacity_m3_day`
6. Consolidate non-farm baseline demands:
  - Read predefined household and community building profiles.
  - `daily_community_water_demand = hw_demand_array + cw_demand_array`
  - `daily_community_energy_demand = E_household_array + E_community_bldg_array`

### System & Financial Baseline Setup

1. Initialize SimulationState with farm, energy, and economic states.
  - Set initial battery SOC = 50% of capacity.
  - `energy_state.cumulative_diesel_L = 0`
  - For each farm: `farm.cumulative_water_used_m3 = 0`
2. Compute infrastructure annual costs (O&M) and full loan amortization schedules (read-only during simulation).
3. Record initial CAPEX, allocate out-of-pocket CAPEX shares to farms based on starting configuration (using `area_proportional` as usage history doesn't exist yet).
4. Compute daily equipment replacement reserve (`Total CAPEX * annual_pct / 365`).

---

## Daily Loop

Each step produces explicit return values consumed by later steps. Mutable accumulators are avoided across step boundaries to prevent side effects.

For each day in simulation_period:

### Step 0: Daily Setup

Retrieve daily conditions, advance crop counters, and check planting queues.

- Retrieve precomputed daily data: `weather` and `prices` for today, plus trailing 12-month `avg_prices`.
- Month/Year trackers: 
  - If day 1 of month -> reset `cumulative_gw_month_m3`, advance loan pointer.
  - If day 1 of year -> reset `cumulative_gw_year_m3`.
- For each farm and each crop:
  - If `crop.active`:
    - `crop.crop_day += 1`
  - Else:
    - If today matches the next absolute date in `farm.planting_queue[crop]`:
      - `crop.active = true`
      - `crop.harvested_today = false`
      - `crop.planting_date = today`
      - `crop.crop_day = 1`
      - `crop.cumulative_water_received = 0`
      - Pop date from queue.

### Step 1: Crop Policy

Adjust base irrigation demand. Base demand comes from precomputed files (net of rainfall).

- For each farm and each active crop:
  - `base_demand_m3 = lookup_irrigation(planting_date, crop_day) * effective_area_ha`
  - `ctx = CropPolicyContext(crop_name, growth_stage, base_demand_m3, weather)`
  - `adjusted_demand_m3 = crop_policy.decide(ctx).adjusted_demand_m3`
- `farm_total_demand_m3 = SUM(adjusted_demand_m3)` across active crops.

### Step 2: Water Allocation

Allocate community water. **Crucial rule:** This step calculates the *financial cost of municipal water* only. Pumping and treatment energy costs are deferred to Step 5 to prevent double counting.

- `total_irrigation_demand = SUM(farm_total_demand_m3)` for all farms.
- `allocation = water_policy.allocate_water(ctx)`
  - Returns: `groundwater_m3`, `municipal_m3`, `energy_used_kwh`, `municipal_cost_usd`.
- For each farm:
  - `farm_share = farm_total_demand_m3 / total_irrigation_demand`
  - `farm_irrigation_delivered_m3 = (allocation.groundwater_m3 + allocation.municipal_m3) * farm_share`
  - `farm.cumulative_water_used_m3 += farm_irrigation_delivered_m3`
  - `farm_water_purchase_cost_usd = allocation.municipal_cost_usd * farm_share`
  - `farm_water_energy_kwh = allocation.energy_used_kwh * farm_share`
  - For each active crop:
    - `crop_water_delivered = farm_irrigation_delivered_m3 * (crop_adjusted_demand / farm_total_demand)`
    - `crop.cumulative_water_received += crop_water_delivered`
- Outputs passed forward: `farm_water_purchase_cost_usd`, `farm_water_energy_kwh`.

### Step 3: Harvest & Food Processing

Runs only on harvest days. Pool yields, calculate harvest labor, apply food policy, and store tranches.
*Note: Crops are flagged but NOT deactivated here, preserving their data for Step 6 logging.*

- `E_processing_today = 0`, `harvest_kg_by_farm = {}`, `daily_harvest_labor = {}`
- For each farm and each crop:
  - If `crop.active` AND `crop.crop_day > season_length_days`:
    - `crop.harvested_today = true`
    - `water_ratio = clamp(crop.cumulative_water_received / expected_total_water, 0, 1)`
    - `raw_yield_kg = Y_potential * water_stress_penalty(water_ratio) * yield_factor * area`
    - `harvest_available_kg = raw_yield_kg * (1 - handling_loss_rate)`
    - `harvest_kg_by_farm[farm.id] += harvest_available_kg`
    - `daily_harvest_labor[farm.id] += calculate_harvest_labor(harvest_available_kg)`
    - Pool `harvest_available_kg` into `community_harvest_pool[crop_name]`.
- Process community pool per crop:
  - Apply `food_policy` to pool -> split into product_types.
  - Create `StorageTranches` (kg post weight-loss, retain farm_shares).
  - Add to `shared_food_product_storage`.
  - `E_processing_today += SUM(input_kg * energy_kwh_per_kg)` for each pathway.
- Outputs passed forward: `E_processing_today`, `harvest_kg_by_farm`, `daily_harvest_labor`.

### Step 4: Sales

Market policy voluntary sales. Evaluates all available storage (including today's fresh harvest and older stock).

- `voluntary_revenue = {}`
- For each product_type in storage:
  - `ctx = MarketPolicyContext(available_kg, current_price, avg_price)`
  - `decision = market_policy.decide(ctx)`
  - Execute FIFO sell loop:
    - `sell_remaining_kg = available_kg * decision.sell_fraction`
    - For each tranche (oldest first):
      - If `sell_remaining_kg <= 0`: Break.
      - `kg_to_sell = MIN(tranche.kg, sell_remaining_kg)`
      - `sale_revenue = kg_to_sell * current_price`
      - For each farm's fraction in tranche:
        - `voluntary_revenue[farm_id][tranche.crop_name] += sale_revenue * fraction`
      - `tranche.kg -= kg_to_sell`
      - `sell_remaining_kg -= kg_to_sell`
      - If `tranche.kg == 0`: Remove tranche.
- Outputs passed forward: `voluntary_revenue`.

### Step 5: Energy Dispatch

Strictly physical simulation. Aggregate total demand, run merit-order dispatch, update battery, and return the total community energy bill and export revenue.

- Aggregate Demands:
  - `E_water_system = allocation.energy_used_kwh`
  - `E_irrigation_pump = total_irrigation_demand * irrigation_pressure_kwh_per_m3`
  - `E_processing = E_processing_today`
  - `E_community_total = daily_community_energy_demand[today]`
  - `total_demand_kwh = E_water + E_pump + E_processing + E_community`
- Dispatch:
  - `dispatch_result = dispatch_energy(total_demand_kwh, pv_avail, wind_avail, battery_soc, flags, prices)`
  - `energy.battery_soc = dispatch_result.battery_soc_after`
- Outputs passed forward: `dispatch_result` (contains `total_energy_cost_usd`, `export_revenue_usd`).

### Step 6: Daily Accounting

The authoritative financial step. Split shared OPEX, attribute energy bills based on farm activities, update cash balances, append daily records, and finally clean up harvested crops.

- **A. Community Costs:**
  - `daily_debt_service = monthly_debt_service_total / days_in_current_month`
  - `community_water_cost = daily_community_water_demand[today] * municipal_water_price`
  - `community_energy_cost = dispatch_result.total_energy_cost * (E_community_total / total_demand_kwh)`
  - `Total_daily_shared_opex = daily_infrastructure_om + daily_management_labor + daily_replacement_reserve + community_water_cost + community_energy_cost`
- **B. Farm Attribution & Accounting (For each farm):**
  - `total_harvest_kg = SUM(harvest_kg_by_farm)`
  - `total_cumulative_water = SUM(farm.cumulative_water_used_m3)`
  - **Cost Allocations (Stabilized usage_proportional):**
    - `usage_ratio = farm.cumulative_water_used_m3 / total_cumulative_water` (Falls back to area_ratio on day 1).
    - `allocated_shared_i = Total_daily_shared_opex * allocation_factor`
    - `debt_service_share_i = daily_debt_service * allocation_factor`
  - **Energy Bill Attribution:**
    - `farm_demand_kwh = farm_water_energy_kwh + (farm_irrigation_delivered * pump_kwh) + (E_processing * farm_harvest_share)`
    - `farm_energy_cost_i = dispatch_result.total_energy_cost_usd * (farm_demand_kwh / total_demand_kwh)`
    - `farm_export_revenue_i = dispatch_result.export_revenue_usd * allocation_factor`
  - **Farm Specific OPEX:**
    - `water_cost = farm_water_purchase_cost_usd`
    - `energy_cost = farm_energy_cost_i`
    - `labor_cost = SUM(crop.labor_schedule[crop.crop_day]) + daily_harvest_labor`
    - `input_cost = SUM(annual_input_cost / 365)`
    - `total_cost = water_cost + energy_cost + labor_cost + input_cost + allocated_shared_i + debt_service_share_i`
  - **Revenues & Cash Update:**
    - `crop_revenue = SUM(voluntary_revenue.values())`
    - `total_revenue = crop_revenue + farm_export_revenue_i`
    - `farm.current_capital_usd += total_revenue - total_cost`
  - **Record Keeping:**
    - Append `DailyFarmRecord(revenue=total_revenue, opex=total_cost, ...)`
  - **Crop Cleanup:**
    - For each crop:
      - If `crop.harvested_today`:
        - `crop.active = false`
        - `crop.harvested_today = false`
        - `crop.crop_day = 0`
        - `crop.cumulative_water_received = 0`
- Append `DailyCommunityRecord(...)`.

---

## Post-Loop Reporting

After the final simulation day, these steps run once.

1. **Value terminal inventory:**
  - `terminal_inventory_value = SUM(tranche.kg * prices[crop_name][product_type])`
  - Added to final year net income for NPV/IRR calculations only (not actual cash).
2. **Compute Metrics:**
  - Stage 1: Per-farm yearly aggregation (sum daily records).
  - Stage 2: Community yearly aggregation (distribution, Gini).
  - Stage 3: Lifetime metrics (trend slopes, CV).
  - Stage 4: Financial metrics (NPV, IRR, ROI).
3. **Output Generation:**
  - Write daily, monthly, and yearly CSVs.
  - Write `simulation_summary.json`.
  - Write `final_state.json`.

