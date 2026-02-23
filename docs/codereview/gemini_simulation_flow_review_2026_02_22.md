# Simulation Flow Specification Review

**Reviewer:** Gemini
**Date:** February 22, 2026
**File Reviewed:** `specs/simulation_flow.md`

Based on a careful review of the `specs/simulation_flow.md` document, here are the logical gaps, inconsistencies, and edge cases a developer would likely raise when attempting to translate this specification into code.

## 1. Logical Errors & Financial Accounting Gaps

### Double-Counting of Water Energy Costs
* **The Gap:** In Step 2 (Water Allocation), the water policy receives `energy_price_per_kwh` and calculates a `cost_usd` for the `WaterAllocation`. In Step 7c (Daily Accounting), the farm is charged `water_cost = farm_allocations[farm].cost_usd` AND `energy_cost = farm_energy_cost_i`. However, `farm_energy_cost_i` is computed in Step 6c based directly on `farm_allocation.energy_used_kwh`. 
* **Developer Question:** *Does `allocation.cost_usd` include the cost of energy used to pump/treat the water? If so, the farm is being double-charged for energy in Step 7c. Should the water policy's `cost_usd` only reflect the municipal water purchase price?*

### Expired Inventory Yields Full Market Revenue
* **The Gap:** In Step 3 (Pre-Harvest Clearance), expired storage tranches are removed, and revenue is calculated using `price = prices[tranche.crop_name][tranche.product_type]`. 
* **Developer Question:** *Does spoiled inventory really sell at the prevailing fresh/processed market price? The spec implies expired food is sold at full value unless the historical price CSV literally drops to zero. Shouldn't expired tranches yield $0 (or a heavy salvage discount) to actually penalize spoilage?*

### Input Cost Formula Misalignment
* **The Gap:** In Step 7c, `input_cost` is calculated as `lookup(..., crop_name).annual_cost_usd_per_ha * active_ha / 365`, where `active_ha` is defined as the sum of areas for *all* active crops on the farm. 
* **Developer Question:** *If a farm grows multiple different crops simultaneously, which `crop_name` is used for the lookup? Shouldn't this be a `SUM()` over each individual active crop, multiplying its specific input cost by its specific `effective_area_ha`?*

## 2. Physical Flow & State Machine Issues

### The Water Storage Tank Never Refills
* **The Gap:** In Step 2 Phase 3, the treated output is defined as `treatment_output_m3 = min(total_treatment_capacity, total_farm_gw_m3)`. Because `total_farm_gw_m3` strictly equals today's demand, the system *only* treats exactly what the farms ask for. Consequently, the equation `Inflow - Outflow` simplifies to `0` (or negative if demand exceeds capacity). 
* **Developer Question:** *Where is the logic to refill the water storage tank? If we only treat water on-demand, the tank acts as a pure pass-through and will never increase its stored volume. Should we run the treatment system at full capacity using excess renewables to buffer the tank when daily demand is low?*

### Deferred Planting Implementation is Broken
* **The Gap:** Under "Planting Rules", the spec says: "If a crop is not DORMANT on its planting date, planting defers to the day after the current harvest." However, the daily loop in Step 0 checks for planting via `IF today matches a planting_date` (which is an exact `MM-DD` match). 
* **Developer Question:** *If a crop misses its exact `MM-DD` planting date, the `IF` condition will evaluate to false on all subsequent days. How should deferred planting be tracked? Do we need a `planting_deferred` boolean queue on the `CropState` so the loop knows to initiate planting immediately once the crop becomes DORMANT again?*

### Harvest State Lifespan
* **The Gap:** In Step 0, the crop state machine advances crops to `HARVEST_READY`. In Step 4 (Food Processing), it says "Transition harvested crops back to DORMANT". 
* **Developer Question:** *Does a crop stay in `HARVEST_READY` for exactly zero days (since Step 4 executes on the same day as Step 0), or is it possible for a crop to sit unharvested for multiple days if processing capacity was constrained? (The spec notes processing is "unlimited", so it implies immediate transition, but confirmation is needed).*

## 3. Ambiguities & Missing Variables

### Farm Revenue Variable Naming
* **The Gap:** Steps 3 and 5 say "Attribute revenue... `farm.revenue += sale_revenue * fraction`". But Step 0 resets `farm.daily_revenue = 0`, and Step 7c consumes `crop_revenue = farm.daily_revenue`.
* **Developer Question:** *Are `farm.revenue` and `farm.daily_revenue` the same variable? I assume I should accumulate intra-day sales into `daily_revenue` and flush it at the end of Step 7c.*

### Processing Labor Attribution
* **The Gap:** In Step 7c, Farm-specific costs dictate adding processing labor: `labor_hours_per_kg × harvested_kg × wage`. However, Step 4 pools all harvests into a community pool before processing.
* **Developer Question:** *What exactly is `harvested_kg` for the farm's labor cost? Is it the farm's raw yield, or its post-handling-loss contribution to the community pool?*

## 4. Division-by-Zero Risks

While the spec mentions "Zero-Demand Guards", a developer implementing this would immediately flag these specific formulas that lack explicit denominator guards in the pseudocode:

* **Step 2 Phase 3 (Water Delivery):** `crop_adjusted_demand / farm_total_demand`. If `farm_total_demand` is 0, this crashes. (A farm with 0 demand shouldn't get delivery, so this block should be bypassed).
* **Step 6c (Energy Attribution):** `farm_demand_kwh_i / total_demand_kwh`. If the entire community has zero energy demand for a day, this crashes.
* **Step 0 (Yield Water Stress):** `cumulative_water_received / expected_total_water`. If a crop's expected water is 0 (e.g., zero area or a crop that requires no irrigation), this calculation faults.