# Simulation Flow Spec Fix Plan

> Addresses issues identified in `docs/codereview/gemini_review.md` and `docs/codereview/simulation_flow_order_of_operations_audit.md`, verified against `specs/simulation_flow.md` and current code (`src/simulation/simulation.py`, `src/simulation/state.py`).

---

## Section 1: Architect Decision Required

These issues have multiple defensible solutions. Each includes context, a suggested fix, and alternatives.

---

### 1.1 Revenue Attribution and `contribution_kg` Reset Policy

**Sources:** Gemini 1A, Audit G-3

**The problem:** `contribution_kg` "accumulates across the simulation" per Section 5.9. Over a multi-year run, a farm that grew tomatoes in Years 1-3 but switched crops retains its historic tomato share. In Year 10 it still receives a percentage of tomato revenue it no longer contributes to.

**Why it matters:** This is a fairness mechanism — it determines how pooled revenue flows back to individual farms. Getting it wrong means farms are over- or under-paid relative to their actual contributions.

**Options:**


| Option                     | Behavior                                                                                                                                                              | Pros                                                                                                                      | Cons                                                                                                                                       |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| A. Reset yearly            | `contribution_kg` resets at year boundary. Revenue shares reflect only the current year's contributions.                                                              | Simple, intuitive. Aligns with annual accounting cycles.                                                                  | A farm that harvests early in January and another in December get attributed in the same year even if their storage inventory spans years. |
| B. Reset per crop cycle    | `contribution_kg` resets when all inventory of that crop is sold (community storage reaches 0 for that crop).                                                         | Perfectly tracks actual inventory ownership.                                                                              | Complex implementation — requires monitoring when all tranches of a crop are depleted.                                                     |
| C. Tranche-level ownership | Attach per-farm ownership fractions to each `StorageTranche` at creation time (Step 4.2). Revenue attribution reads directly from the tranche, not a running counter. | Eliminates the accumulator problem entirely. Revenue is always attributed to the farms that produced each specific batch. | Requires modifying `StorageTranche` to carry a `farm_shares: dict` field. Slightly more storage per tranche.                               |


**Suggested fix:** Option C (tranche-level ownership). It eliminates the entire class of accumulation bugs and is the standard approach in pooled-inventory models. The `StorageTranche` dataclass already exists in the spec (Section 5.7) — adding a `farm_shares` field is a minimal change. Revenue attribution in Step 5 then becomes `sale_revenue * tranche.farm_shares[farm_id]` with no running counters needed.

---

### 1.2 Water Storage Farm-Order Bias

**Source:** Gemini 1B

**The problem:** In Section 3, Step 2, `water_storage_m3` is updated inside the `FOR each farm` loop. Farm 1 draws from community storage before Farm 2, creating index-order priority. If storage runs low, later farms get nothing.

**Current state:** The MVP code treats inflow == outflow same-day, so storage never actually depletes from this ordering. But the spec defines this pattern for the full model where storage acts as a real buffer across days.

**Options:**


| Option                      | Behavior                                                                                                  | Pros                                                                                        | Cons                                                                                                                                        |
| --------------------------- | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| A. Two-phase allocation     | Phase 1: sum all farm demands. Phase 2: if demand > supply, allocate proportionally. Update storage once. | Eliminates ordering bias. Standard resource-sharing approach.                               | Slightly more complex loop structure.                                                                                                       |
| B. Randomize farm order     | Shuffle farm processing order each day.                                                                   | Simple to implement. Eliminates systematic bias (though any single day still has ordering). | Introduces stochasticity into what should be deterministic. Harder to debug/reproduce.                                                      |
| C. Accept bias, document it | Note in spec that farms are processed in configuration order and that ordering affects priority.          | Zero implementation cost.                                                                   | Creates a hidden parameter (farm ordering) that affects outcomes. Difficult to explain to community members why Farm 1 always fares better. |


**Suggested fix:** Option A (two-phase allocation). This is standard practice in resource allocation models with shared capacity. Minimal additional complexity and eliminates a class of subtle bugs. Implementation: calculate all demands first, compare total demand to available supply (storage + treatment capacity), then allocate proportionally if constrained.

---

### 1.3 Negative Cash Flow Handling

**Source:** Gemini 3B

**The problem:** Step 7 updates `cash += revenue - cost` without defining what happens when cash goes negative. The spec mentions "default probability" and "solvency" in metrics but never specifies the behavioral rule.

**Why it matters:** Without a rule, the simulation silently allows unlimited negative cash — effectively unlimited free credit — which distorts economic metrics and makes solvency metrics meaningless.

**Options:**


| Option                                       | Behavior                                                                                                       | Pros                                                                                                         | Cons                                                                                  |
| -------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------- |
| A. Allow negative cash, flag as "in default" | Track negative balance. Set `farm.in_default = True`. Apply penalty interest rate to negative balance.         | Simulation continues running. Shows how bad it gets. Penalty interest models real-world emergency borrowing. | Need to decide on penalty rate.                                                       |
| B. Emergency credit line with limit          | Allow negative up to a configurable limit (e.g., 6 months of average opex). If exceeded, halt farm operations. | Models real-world credit constraints. Forces the simulation to show consequences.                            | More complex. Need to define "halt operations" behavior.                              |
| C. Allow unlimited negative, report only     | Let cash go arbitrarily negative. Report it in metrics. No behavioral consequences.                            | Simplest. Good for MVP.                                                                                      | Unrealistic — no entity has unlimited credit. Distorts long-run economic comparisons. |


**Suggested fix:** Option A for the full model. Option C is acceptable for MVP only. The penalty interest rate can default to a standard emerging-market microfinance rate (~15-25% APR) and be configurable in the scenario YAML.

---

### 1.4 `sell_inventory` Flag Integration Point

**Source:** Audit G-7

**The problem:** Step 6 produces `EconomicDecision.sell_inventory` and says it is used "in Step 5 next month." But Step 5's `MarketPolicyContext` and `market_policy.decide()` interface have no mechanism to receive or act on this flag. The economic decision is computed but never consumed.

**Options:**


| Option                                | Behavior                                                                                                                                                     | Pros                                                                                | Cons                                                                                                                   |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| A. Pre-Step-5 override                | When `sell_inventory = True`, insert a forced sell-all step before Step 5. All community inventory is sold at market price before normal market policy runs. | Clean separation — economic policy sets strategy, market policy handles day-to-day. | Forced sell-all may not be the right granularity. Maybe the economic policy wants to sell only specific product types. |
| B. Pass flag into MarketPolicyContext | Add `economic_sell_override: bool` to `MarketPolicyContext`. Market policy checks this flag and returns `sell_fraction = 1.0` when set.                      | Market policy retains control over execution.                                       | Muddies the market policy interface with economic concerns.                                                            |
| C. Expand EconomicDecision            | Return a richer decision: `sell_inventory_types: list[str]` (e.g., `["fresh", "canned"]`). Pre-Step-5 sells only those types.                                | More nuanced control.                                                               | More complex for uncertain payoff at this stage.                                                                       |


**Suggested fix:** Option A. It's the simplest approach that closes the gap. The economic policy fires monthly and sets a flag; on each day of the following month, if the flag is set, Step 4.3 (forced sales) executes a sell-all before the normal market policy runs. Once sold, the flag auto-clears (inventory is now empty).

---

### 1.5 Economic Policy Monthly Data Source

**Source:** Audit O-2

**The problem:** Step 6 fires on the first day of month M and needs "previous month's aggregated revenue and costs." But the monthly snapshot that produces that data is defined as part of Step 8 — which runs after Step 6. On day 1 of month M, the month M-1 snapshot doesn't exist yet.

**Options:**


| Option                                           | Behavior                                                                                 | Pros                                            | Cons                                                                                                                                            |
| ------------------------------------------------ | ---------------------------------------------------------------------------------------- | ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| A. Move Step 6 after Step 8's snapshot           | Step 8 runs first (snapshot + reset), then Step 6 reads the snapshot.                    | Step 6 reads clean, finalized data.             | Changes the spec's step ordering. Step 6 must be renumbered or explicitly stated as "runs after boundary operations on the first day of month." |
| B. Step 6 aggregates from daily records directly | Step 6 sums daily records for days where `date.month == M-1`. No dependency on snapshot. | No reordering needed. Simpler dependency chain. | Slightly more computation (summing daily records vs. reading snapshot).                                                                         |


**Suggested fix:** Option B. Daily records are already being kept. Having Step 6 aggregate directly from them eliminates the ordering dependency entirely. The monthly snapshot in Step 8 then serves reporting/metrics only, not as an input to other steps. This reduces coupling between steps.

---

### 1.6 Processing Capacity Model (Pre-Loop Step 6)

**Source:** Audit G-1

**The problem:** Pre-Loop Step 6 is marked TBD. Step 4.2's `clip_to_capacity()` needs a `capacities` dict keyed by processing pathway, but no computation is defined to produce it.

**Decision needed:** What equipment data structure maps to processing capacities?

**Context from the spec:** Section 5.4 says:

```
capacity_kg_per_day = sum(equipment.throughput_kg_per_day * equipment.availability_factor)
    for each equipment item in the pathway
```

This implies an equipment registry with per-pathway throughput values. The data file `processing_specs-toy.csv` exists but contains weight loss and value multiplier data — not throughput capacities.

**Suggested approach:** Define a new CSV file (or add columns to `processing_specs-toy.csv`) containing:

- `pathway` (packaged, canned, dried)
- `throughput_kg_per_day` (per equipment unit)
- `num_units` (from scenario config or fixed)
- `availability_factor` (default 0.90)

The pre-loop calculation becomes:

```
capacities[pathway] = throughput_kg_per_day * num_units * availability_factor
```

Fresh has no capacity limit (Section 5.4 states this explicitly).

**Architect needs to decide:** Where do equipment counts come from — scenario YAML (community_infrastructure section) or a separate equipment inventory CSV? The scenario YAML approach is consistent with how other infrastructure is configured.

**Suggested fix by architect**: The capacities are defined in data/equipment/processed_packaging-toy.csv and processing_equipment-toy.csv files. If any processing capacities are missing, add additional rows to existing files are add new files as needed.

---

## Section 2: High-Confidence Fixes

These issues have clear solutions. Each includes a brief summary and the fix.

---

### 2.1 Monthly Accumulator Reset Timing (Spec-Code Mismatch)

**Source:** Audit O-1

**Issue:** Spec says monthly accumulators reset in Step 8 (after the daily loop). Code resets on first access when the month changes via `update_monthly_consumption()` (auto-reset pattern in [state.py:269-293](src/simulation/state.py#L269-L293)).

**Fix:** Update spec Section 3 Step 8 and Section 9.1 to say: "Monthly accumulators reset automatically on first access when the month changes (reset-on-read pattern). The reset occurs implicitly before Step 1 when any step first reads the accumulator for a new month. The monthly metrics snapshot must be captured before the reset — either by snapshotting at the end of the last day of the month, or by reading from daily records for the completed month."

---

### 2.2 Yearly Degradation One-Day Lag

**Source:** Audit O-3

**Issue:** On day 1 of year Y+1, dispatch uses year Y's battery/PV parameters. Degradation updates happen in Step 8, after dispatch.

**Fix:** Add a note to Section 9.2: "Equipment degradation updates apply from the second day of the new year onward. The one-day lag is acceptable: annual degradation rates are small (0.5% PV, ~1.8% battery calendar fade) so a single day's error is negligible relative to daily weather variance."

---

### 2.3 Economic Policy Duplicate Reference

**Source:** Audit O-4

**Issue:** Step 6 (daily loop) and Section 9.1 item 1 (monthly boundaries) both describe economic policy execution, creating ambiguity about whether it fires twice.

**Fix:** Add to Section 9.1 item 1: "This is a conceptual description of Step 6 in the daily loop — not a separate execution trigger. The economic policy executes exactly once on the first day of each month, as specified in Step 6. See Step 6 for the implementation."

---

### 2.4 `E_processing` State Field Missing

**Source:** Audit G-2

**Issue:** The spec defines one-day lag behavior for `E_processing` and initializes it to 0 in Pre-Loop Step 14, but no state field exists to carry the value between days. `EnergyState` has no `e_processing` field.

**Fix:** Add to `EnergyState` in [state.py](src/simulation/state.py):

```python
e_processing_kwh: float = 0.0  # Previous day's food processing energy (one-day lag)
```

Add to Section 12.1 cross-reference: map `E_processing` to `EnergyState.e_processing_kwh`.

---

### 2.5 Harvest Hand-Off Clarification

**Source:** Audit G-4, Audit A-2

**Issue:** The spec doesn't explicitly state that Step 0 only advances crop state while Step 4 executes the actual harvest and processing. An implementer could read Section 6.5 as executing entirely within Step 0, breaking the processing energy one-day lag.

**Fix:** Add to Section 6.5 after the harvest trigger pseudocode: "Step 0 only advances `crop.state` to `HARVEST_READY`. It does NOT execute the harvest yield calculation or food processing pipeline. Step 4 queries all farms for crops in `HARVEST_READY` state, executes the yield calculation and processing pipeline (Sections 5.2-5.6), then transitions those crops to `DORMANT`. This separation preserves the one-day lag for `E_processing`."

---

### 2.6 Monthly Snapshot Order vs. Resets

**Source:** Audit G-5

**Issue:** Step 8 lists snapshot and reset operations but does not specify their order. If resets happen before snapshot, the snapshot captures zeroed data.

**Fix:** Add explicit ordering to Section 3 Step 8:

```
IF today is first day of new month:
    1. Snapshot monthly metrics (aggregate from daily records for completed month)
    2. Reset monthly cumulative groundwater tracking
    3. Reset monthly community water consumption
```

---

### 2.7 Missing Energy Demand Retrieval in Step 0

**Source:** Audit G-6

**Issue:** Step 3 uses `E_household` and `E_community_bldg` but Step 0 does not list retrieving these values from precomputed data. The code already does this correctly ([simulation.py:945-948](src/simulation/simulation.py#L945-L948)) but the spec omits it.

**Fix:** Add to Step 0's retrieval list:

```
Retrieve daily household energy demand (E_household) from precomputed `household.energy`
Retrieve daily community building energy demand (E_community_bldg) from precomputed `community_buildings.energy`
Retrieve daily household water demand from precomputed `household.water`
Retrieve daily community building water demand from precomputed `community_buildings.water`
```

---

### 2.8 Community vs. Farm Storage Terminology

**Source:** Gemini 2A

**Issue:** Section 4.2 correctly places processed food into `community_storage`, but Section 5.8 references `check_forced_sales(farm_storage...)` and iterates `farm_storage`. Since processing and storage are pooled at the community level, this is inconsistent.

**Fix:** Replace all instances of `farm_storage` in Section 5.8 with `community_storage`. The function signature becomes `check_forced_sales(community_storage, current_date, storage_capacities)`.

---

### 2.9 Water Balance Assertion Fix

**Source:** Gemini 1C

**Issue:** Section 11.5 asserts `total_water_allocated == total_water_demand`. But the model explicitly supports water quotas, capacity limits, and crop water stress (Section 5.2). Under drought or quota enforcement, allocation will be less than demand. This assertion would crash the simulation during legitimate shortage scenarios.

**Fix:** Replace the water material balance assertion in Section 11.5:

```
# OLD (wrong): asserts allocation == demand
# assert abs(total_water_allocated - total_water_demand) < 0.01

# NEW: material balance — water in == water out + change in storage
water_in = total_groundwater_extracted + total_municipal_delivered
water_out = total_water_distributed_to_farms + total_community_water
delta_storage = water_storage_end - water_storage_start
assert abs(water_in - water_out - delta_storage) < 0.01
```

Also update Step 2 to track `water_actually_delivered_m3` rather than assuming `outflow_m3 = farm_total_demand_m3`:

```
outflow_m3 = allocation.groundwater_m3 + allocation.municipal_m3  # actual delivery
```

---

### 2.10 Per-Farm Energy Tracking for Cost Allocation

**Source:** Gemini 2 (Usage-Proportional Energy)

**Issue:** Section 8.1 says shared OPEX can be allocated usage-proportionally based on energy consumption. But Step 3 aggregates all energy into a single `total_demand_kwh` before dispatch — per-farm energy demand is never recorded.

**Fix:** Add per-farm energy accumulator. In Step 2 (or after), record each farm's energy demand components:

```python
farm.daily_energy_demand_kwh = allocation.energy_used_kwh  # water treatment energy
```

Add to `FarmState`:

```python
cumulative_energy_demand_kwh: float = 0.0  # for usage-proportional cost allocation
```

Accumulate daily, reset yearly. This provides the denominator for usage-proportional energy cost allocation in Section 8.1.

---

### 2.11 CAPEX vs. Starting Capital Validation

**Source:** Gemini 3C

**Issue:** Pre-Loop Step 12 computes `initial_cash = SUM(starting_capital) - capex_cash_outflow`. If a high-cost cash-purchased system is configured, the simulation could start with negative cash on day 1.

**Fix:** Add validation after Pre-Loop Step 12:

```
IF capex_cash_outflow > SUM(farm.starting_capital_usd):
    RAISE ConfigurationError(
        f"Insufficient starting capital ({SUM(starting_capital)}) "
        f"to cover cash CAPEX ({capex_cash_outflow}). "
        f"Consider loan financing or increasing starting_capital_usd."
    )
```

---

### 2.12 January 1 Dual Boundary Ordering

**Source:** Audit A-3

**Issue:** January 1 triggers both monthly and yearly boundary operations. The ordering within Step 8 is not defined, which could cause data inconsistencies.

**Fix:** Define explicit ordering in Section 9 for January 1:

```
1. Monthly snapshot (captures December data)
2. Monthly reset (clear monthly accumulators)
3. Yearly snapshot (captures full-year data)
4. Yearly resets (clear yearly accumulators)
5. Yearly updates (degradation, aquifer, crop reinitialization)
```

---

### 2.13 First-Day Initialization Gaps

**Source:** Audit Section 3 (edge cases)

**Issue:** Several values needed on day 1 are not explicitly initialized in the pre-loop:

- `cumulative_gw_month_m3 = 0` (implicit but not stated)
- `cumulative_monthly_community_water_m3 = 0` (not mentioned)
- `contribution_kg = 0` for all crops (tied to 1.1 above)
- Economic policy behavior when `months_elapsed == 0`

**Fix:** Add to Pre-Loop initialization:

```
Step 14b. Initialize monthly accumulators:
    cumulative_gw_month_m3 = 0
    cumulative_monthly_community_water_m3 = 0

Step 14c. Initialize per-crop contribution trackers:
    FOR each farm: FOR each crop: contribution_kg[crop] = 0

Step 14d. Economic policy guard:
    IF simulation starts on first day of month:
        Skip Step 6 for the first month (no prior data exists)
        OR set months_of_reserves = initial_cash / estimated_monthly_opex
```

---

## Implementation Order

The fixes are ordered by dependency — later items may depend on earlier ones:

1. Spec-only fixes (2.1-2.3, 2.5-2.8, 2.12): Update `simulation_flow.md` text. No code changes.
2. State field additions (2.4, 2.10): Add fields to `state.py`. Minimal code impact.
3. Assertion fix (2.9): Update spec and adjust Step 2 outflow calculation.
4. Validation addition (2.11, 2.13): Add pre-loop checks to spec and code.
5. Architect decisions (1.1-1.6): Once decided, update spec and implement.

Items in Section 2 can proceed immediately. Items in Section 1 should be decided before implementing Steps 4-5 (food processing / market chain) and Step 6-7 (economic policy / accounting).