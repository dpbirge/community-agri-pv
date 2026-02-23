### 1. Logic Errors, Gaps, or Inconsistencies Across Files

While the logic is very tight, there are a few edge cases and gaps where an LLM will either hallucinate a solution or write buggy code because the instructions are slightly incomplete.

- **Gap in Water Policy Scaling (The "Missing Municipal" Bug):**
  - *Where:* `simulation_flow.md` Section 3, Step 2, Phase 2.
  - *Issue:* If aggregate groundwater demand exceeds physical supply, you pro-rata scale down the groundwater allocations (`groundwater_m3 *= scale_factor`). However, the specification *forgets to add the shortfall to the municipal allocation*. If a farm needs 100m³ total, asks for 100m³ of groundwater, but is scaled down to 80m³, its `municipal_m3` must be increased by 20m³ so the crop still gets watered.
  - *Fix:* Add explicit logic in Phase 2: `shortfall = original_groundwater_m3 - scaled_groundwater_m3; allocation.municipal_m3 += shortfall`.
- **Gap in Market Policy Historical Price Data:**
  - *Where:* `policies.md` `adaptive` market policy requires `avg_price_per_kg`.
  - *Issue:* `simulation_flow.md` Step 0 (Retrieve Daily Conditions) retrieves "current prices" but completely omits the retrieval or calculation of the 12-month rolling `avg_price_per_kg`. If it's not in Step 0, the LLM won't pass it into the `MarketPolicyContext`.
  - *Fix:* Add to Step 0: "Retrieve 12-month historical average price for all crops/product types."
- **Inconsistency in Salinity Tracking (If Enabled):**
  - *Where:* `simulation_flow.md` Section 5.2 mentions tracking `cumulative_irrigation_EC` if the salinity model is enabled.
  - *Issue:* The Daily Simulation Loop (Step 2 or 7) never actually calculates or tracks this daily addition. An LLM will implement the formula in 5.2 at harvest time, but will find `cumulative_irrigation_EC` is equal to 0 because no step tells the LLM to update it daily.
  - *Fix:* Add a line in Step 2 Phase 3 (or Step 7 Accounting): `IF salinity_model_enabled: update cumulative_irrigation_EC based on mixed_tds_ppm`.
- **Economic Policy State Persistence:**
  - *Where:* `simulation_flow.md` Step 6 (Monthly) and Step 4.3 (Daily Umbrella Rule).
  - *Issue:* Step 6 runs on Day 1 of the month and evaluates `EconomicDecision.sell_inventory`. Step 4.3 checks this flag *on harvest days*. If a harvest happens on Day 14, how does the system remember the flag? The spec implies saving it to simulation state, but LLMs take loop scopes literally.
  - *Fix:* Explicitly state in Step 6: "Store `sell_inventory` flag in `farm_state.pending_inventory_liquidation`." And in Step 4.3: "Check `farm_state.pending_inventory_liquidation`... if True, execute sale and reset to False."

---

### 2. Ways to Clarify and Simplify for LLM Coders

LLMs perform best when data types, interfaces, and architectural boundaries are mathematically rigid.

- **Enforce Enums / Literals over "Magic Strings":**
  - *Observation:* The specs use many string literals (`"initial"`, `"development"`, `"fresh"`, `"well_limit"`). An LLM might accidentally type `"Initial"` or `"mid-season"` causing silent logic failures.
  - *Improvement:* Instruct the LLM in your prompt (or add a tiny section to `structure.md`) to create Python `Enum` or `Literal` types for:
    - `CropStage`: `DORMANT`, `INITIAL`, `DEVELOPMENT`, `MID_SEASON`, `LATE_SEASON`, `HARVEST_READY`
    - `ProductType`: `FRESH`, `PACKAGED`, `CANNED`, `DRIED`
    - `ConstraintHit`: `WELL_LIMIT`, `TREATMENT_LIMIT`, `NONE`
- **Clarify "Capacity Clipping" Ownership:**
  - *Observation:* In `policies.md` (Food Processing), it says "Capacity clipping is applied by the simulation loop... not inside the policy class itself." But then it immediately provides pseudocode for capacity clipping *inside* the policy spec document. An LLM might get confused and put the clipping logic inside the Policy class anyway.
  - *Improvement:* Frame it strictly as a Contract: *"The Policy Class MUST return mathematically pure fractions summing to 1.0, ignorant of constraints. The Simulation Loop Module takes those fractions and executes the capacity clipping function."*
- **Address Floating Point Equality:**
  - *Observation:* The food processing policy specifies: "Constraint: Fractions must sum to 1.0". The error handling says `IF abs(fresh + packaged + canned + dried - 1.0) > 0.001: RAISE ValueError`.
  - *Improvement:* This is excellent. Make sure the LLM applies this `math.isclose()` logic to *all* fraction checks, including the Market policy (`sell_fraction + store_fraction == 1.0`) and Crop planting (`area_fraction`).
- **Clarify "FIFO Tranche" Data Structures:**
  - *Observation:* `simulation_flow.md` 5.7 defines `StorageTranche` as a list per farm, ordered by `harvest_date` (oldest first).
  - *Improvement:* To prevent the LLM from over-engineering a complex PriorityQueue, add a note: *"Because simulation time moves strictly forward, simply appending new `StorageTranche` objects to a standard Python list natively guarantees FIFO ordering. Popping from index 0 processes the oldest."*

---

### 3. General Audit & Architectural Suggestions

- **Daily Accounting Step (Step 7) Efficiency:**
  - In Step 7, the code requires summing `tranche.kg * storage_cost_per_kg_per_day` across all tranches every single day. If a simulation runs for 20 years with daily harvests, iterating over thousands of tranches every day will cause a massive Python performance bottleneck (O(N^2) over time).
  - *Suggestion:* Tell the LLM to track `total_stored_kg_by_type` as an aggregate state variable that gets updated +/– only when food enters or leaves storage, so daily storage costs can be calculated via O(1) multiplication rather than an O(N) loop.
- **Double-Counting Revenue in Tranches:**
  - In `simulation_flow.md` 5.9, Revenue calculation: "Revenue attribution reads directly from the tranche being sold." This is very smart. However, ensure the LLM understands that partial tranche sales (forced overflow sales, Section 5.8) must correctly decrement the `kg` of the original tranche without destroying the `farm_shares` dictionary, so the remaining `kg` can be sold later using the same ratios. (The logic in 5.8 `sold_portion = copy(oldest)` handles this, but emphasize deep copying or field-specific copying to the LLM so it doesn't accidentally link object references).