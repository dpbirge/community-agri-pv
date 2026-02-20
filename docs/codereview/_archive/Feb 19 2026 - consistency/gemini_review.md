Based on a thorough review of the `simulation_flow.md` document alongside the provided context, the architecture is highly robust and well-structured. The separation of daily conditions, per-farm policies, community dispatch, and boundary operations is logically sound.

However, there are a few **critical logical gaps, order-of-operation issues, and state management inconsistencies** that will cause incorrect outputs or false crashes if implemented exactly as written.

Here is a breakdown of the issues and how to resolve them:

### 1. Major Logical Gaps

**A. Revenue Attribution Bug (Accumulating Forever)**

- **The Issue:** In Section 5.9, revenue is attributed using: `farm_share = farm.contribution_kg / total_kg_crop`. The text states: *"The contribution_kg tracker accumulates across the simulation and is used as the denominator for all sales of that crop."*
- **Why it fails:** If this accumulates across a 20-year simulation without resetting, it will cause massive distortion. For example, if Farm A grows tomatoes in Years 1–5 and then switches to potatoes, their historic tomato contributions remain in the denominator. In Year 10, Farm A will still receive a percentage of Farm B's tomato revenue.
- **The Fix:** Do not use a running lifetime total. Instead, either:

  1. Attach the farm ownership breakdown directly to the `StorageTranche` dataclass at the time of creation (Step 4.2).
  2. Reset `farm.contribution_kg` and `total_kg_crop` at the yearly boundary (Section 9.2) or when a crop lifecycle completely finishes.

**B. Water Storage Updates (Farm Order Bias)**

- **The Issue:** In Section 3 (Step 2), `water_storage_m3` is updated *inside* the `FOR each farm:` loop.
- **Why it fails:** Community water storage is a shared resource. If Farm 1 and Farm 2 both need water, updating the tank sequentially means Farm 1 has priority simply because of its index in the array. If the tank empties, Farm 2 gets nothing, creating an artificial order bias.
- **The Fix:** Split Step 2 into two phases. First, sum up all physical water inflow (treated groundwater) and all irrigation demand. Then, update the community storage tank once. If demand exceeds available storage + inflow, allocate the shortfall proportionally across the farms so they share the water stress equally (or according to a defined priority).

**C. Unmet Water Demand vs. Assertion Crash**

- **The Issue:** In Section 11.5, there is a material balance assertion: `assert abs(total_water_allocated - total_water_demand) < 0.01`. In Section 3 (Step 2), it assumes `outflow_m3 = farm_total_demand_m3` unconditionally.
- **Why it fails:** The model explicitly supports water quotas and physical capacity limits (Step 5.4, policies). It also explicitly supports crop water stress (Section 5.2: `water_ratio = clamp(cumulative_water_received / expected_total_water)`). If a quota is hit and municipal water is unavailable, allocation *will* be less than demand. The assertion in 11.5 will trigger and crash the simulation during a legitimate drought/shortage scenario.
- **The Fix:** Change the assertion to check `water_in == water_out + change_in_storage` rather than `allocation == demand`. Additionally, in Step 2, capture `water_actually_delivered_m3` and pass *that* value to the crop's cumulative tracker in Step 6.7, rather than assuming 100% of demand was met.

### 2. Traceability and Cost Allocation Gaps

**A. Usage-Proportional Energy Tracking**

- **The Issue:** Section 8.1 states that shared OPEX can be allocated "usage-proportionally... For energy infrastructure: based on energy consumption."
- **Why it fails:** In Step 3, all energy demand is aggregated into a single `total_demand_kwh` before dispatch. The dispatch module outputs total costs, but nowhere does the daily loop record how much of that total energy was consumed by Farm A vs. Farm B.
- **The Fix:** In Step 3 or Step 7, introduce a per-farm energy accumulator. `farm.daily_energy_demand_kwh = farm.E_water_system + farm.E_irrigation_pump + farm.E_processing_share`. Use this exact tracker at the end of the month to calculate the usage-proportional split.

### 3. State Management & Lifecycle Inconsistencies

**A. Community vs. Farm Storage Terminology**

- **The Issue:** Section 4.2 correctly places processed food into `community_storage`. However, Section 5.8 (FIFO Forced Sales) repeatedly references `check_forced_sales(farm_storage...)` and iterating through `farm_storage`.
- **The Fix:** Standardize the terminology to `community_storage` throughout Section 5 to reflect that processing and storage are pooled.

**B. Handling Negative Cash Flow**

- **The Issue:** Step 7 (Daily Accounting) updates the farm cash position: `cash += total_daily_revenue - total_daily_cost`. It lacks a check for negative cash.
- **Why it matters:** If cash goes negative, what happens? Are operations halted for that farm? Is short-term debt automatically assumed? The Economic Metrics (Section 4 of `overview.md`) mention "default probability" and "solvency."
- **The Fix:** Explicitly define the behavior in Step 7. For example: "If `cash < 0`, flag farm as 'in default' (or accumulate negative balance as emergency debt with a penalty interest rate) to be tracked by yearly metrics."

**C. Initial CAPEX vs Starting Capital**

- **The Issue:** In Section 2 (Step 12), `initial_cash = SUM(farm.starting_capital_usd) - capex_cash_outflow`.
- **Why it matters:** If the scenario is configured with a high-cost cash-purchased system (`purchased_cash`), `capex_cash_outflow` could exceed the sum of the farmers' starting capital, resulting in the simulation starting on Day 1 with negative cash.
- **The Fix:** Add a pre-loop validation check: `IF capex_cash_outflow > SUM(starting_capital_usd): RAISE ConfigurationError("Insufficient starting capital to cover cash CAPEX")`.

### Summary of Order of Operations

The overall sequence is excellent, particularly:

- The 1-day lag for processing energy (prevents circular dependency between today's harvest, today's processing energy, and today's dispatch).
- The execution sequence of Crop → Water → Energy → Food processing → Market (perfectly follows the physical flow of causal dependencies).
- Boundary operations executing *before* the daily loop (first day of month/year) rather than at the end, which aligns perfectly with standard time-series data handling.