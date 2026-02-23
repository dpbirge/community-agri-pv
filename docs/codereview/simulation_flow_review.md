# Simulation Flow Specification Review

**File reviewed:** `specs/simulation_flow.md`
**Date:** 2026-02-21
**Scope:** Logic completeness and implementation readiness. Assumes all referenced specs (data, policies, calculations, structure) are correct.

## Summary

The document is well-structured and close to implementation-ready. Step ordering is logical, cross-references are consistent, and supporting reference sections (pricing, food processing, revenue attribution, cost allocation) are thorough.

**Pass 1** found 6 issues — 2 require spec changes, 4 are clarifications.
**Pass 2** (assuming Pass 1 issues resolved) found 7 additional items — mostly implementation friction points and minor gaps.
**Pass 3** found 4 items — 1 modeling design choice affecting microgrid scenarios, 2 state/guard gaps, 1 minor omission.
**Pass 4** found 2 items — 1 pricing inconsistency between water and energy systems, 1 pseudocode error.

---

## Issue 1: Water Storage Never Refills (Spec Change Required)

**Location:** Phase 3, lines ~391-396

**Problem:** `treatment_output_m3 = min(total_treatment_capacity, total_farm_gw_m3)` means treatment only processes what farms demand, never more. On unconstrained days, inflow exactly equals outflow (net delta = 0). On constrained days, storage drains. Result: storage monotonically decreases from 50% initial and never recovers.

**Math proof:**
- Unconstrained day: treatment_output = farm_gw = farm_demand (no municipal needed). Storage delta = treatment_output + municipal(0) - delivered(= farm_demand) = 0.
- Constrained day: after Phase 2 scaling, total allocated GW = available_supply = storage + capacity. Storage delta = capacity + municipal - total_demand = capacity - available_supply = -storage. Storage drains to zero.

**Resolution needed:** Define when/how storage refills. Options:
1. Treatment runs at capacity regardless of demand; excess fills storage.
2. Explicit "storage refill" sub-step when demand < capacity.
3. State that storage is intentionally a one-way emergency buffer (and document this).

---

## Issue 2: Deferred Planting Has No Pseudocode (Spec Change Required)

**Location:** Crop State Machine, lines ~234-247 vs. rules at line ~268

**Problem:** Rules state: "If a crop is not DORMANT on its planting date, planting defers to the day after the current harvest." But the state machine pseudocode only checks `IF today matches a planting_date`. No mechanism exists for the deferred case — no flag set when a planting date is missed, no check for "day after harvest for a crop that missed its window."

**Resolution needed:** Add pseudocode for deferred planting. Likely requires:
- A `deferred_planting` flag on CropState, set when planting date passes while crop is not DORMANT.
- A check after HARVEST_READY → DORMANT transition: if `deferred_planting`, start new cycle next day.

---

## Issue 3: Zero-Demand Division Guards Missing (Clarification)

**Location:** Phase 3 line ~402, Step 6c line ~664

**Problem:** Two pro-rata divisions lack zero guards:
- `crop_adjusted_demand / farm_total_demand` — zero if farm has no active crops.
- `farm_demand_kwh_i / total_demand_kwh` — zero if no energy demand exists.

These are simulation-engine mechanics, not policy logic, so the existing "zero-demand guards in policies" note (Error Handling section) doesn't cover them.

**Resolution needed:** Add explicit zero guards or note that these divisions are skipped when denominator = 0.

---

## Issue 4: Economic Policies Never Invoked (Clarification)

**Location:** Daily loop steps 0-7

**Problem:** Five of six policy domains have clear invocation points in the daily loop (crop, water, food, energy, market). Economic policies (4 strategies per CLAUDE.md) have no step. `cost_allocation_method` appears as a static config parameter, not a daily decision.

**Resolution needed:** Either:
1. Add a step where economic policy is invoked (if it makes daily decisions).
2. State explicitly that economic policies are configuration-time only and don't execute in the daily loop.

---

## Issue 5: Farm Insolvency Behavior Undefined (Clarification)

**Location:** Step 7c, line ~747

**Problem:** `farm.current_capital_usd` can go arbitrarily negative. Post-loop references "insolvency probability" as a Monte Carlo metric, but the daily loop doesn't define:
- Whether negative-cash farms continue operating normally.
- Whether a flag is recorded in DailyFarmRecord.
- Whether any debt/bailout mechanism exists.

**Resolution needed:** Add a brief statement on insolvency behavior. Even "farms continue operating with negative cash; insolvency is reported in metrics only" is sufficient.

---

## Issue 6: Overview Contradicts Post-Loop on Yearly Metrics (Documentation Fix)

**Location:** Line ~27 vs. line ~965

**Problem:** Overview says "yearly metrics snapshotted at year boundaries." Post-loop section says "All metrics are computed from DailyFarmRecord and DailyCommunityRecord tables. No in-loop snapshots are needed." These contradict — the post-loop statement is correct.

**Resolution needed:** Reword line 27 to match the post-loop approach (e.g., "yearly metrics computed from daily records after simulation completes").

---

## Pass 2: Additional Findings

Assuming Issues 1-6 above are resolved. These are smaller but would cause friction during implementation.

---

## Issue 7: Harvest-Day Input Cost Exclusion (Ordering Side-Effect)

**Location:** Step 4 (line ~508-514) vs. Step 7c (line ~728-731)

**Problem:** Step 4 transitions harvested crops to DORMANT. Step 7 computes `active_ha = SUM(crop.effective_area_ha for active crops)`. Since DORMANT crops are excluded, a crop that was active all day (HARVEST_READY through Steps 0-3) contributes zero input cost on its harvest day. Over a 15-year simulation with ~5 crops across 20 farms, this creates a systematic undercount of approximately one day's input cost per harvest event.

**Resolution needed:** Either:

1. Compute `active_ha` before Step 4 transitions (snapshot crop states for accounting).
2. Document this as an acceptable approximation (one day per cycle is ~0.5-1% of a typical 120-day season).

---

## Issue 8: Energy Flag Combination Creates Hybrid Dispatch (Clarification)

**Location:** Step 6b, line ~621-623

**Problem:** When farms choose different energy policies, the ANY/ALL/MIN flag combination produces dispatch configurations not represented by any individual policy. Example: Farm A selects `microgrid` (generator, no grid) while Farm B selects `renewable_first` (grid, no generator). Combined flags: `use_generator=true AND grid_import=true`, giving the community access to *both* backstops — a configuration none of the three defined policies intends.

**Resolution needed:** Add a note that combined flags intentionally produce a permissive union (community gets the most flexible dispatch available from any member's policy choice). Without this note, an implementer might assume the combination is a bug.

---

## Issue 9: Food Processing Has No Water Demand (Possible Gap)

**Location:** Step 4 (lines ~465-518), Step 6a (lines ~586-601)

**Problem:** Processing energy is computed (`E_processing_today`) and fed into energy dispatch. But processing water demand (washing, canning liquid, etc.) is absent from the daily loop. The consumer type table (line ~767) lists food processing under "agricultural" water pricing, implying processing water was anticipated, but no volume calculation exists.

**Resolution needed:** Either:

1. Add processing water demand (input_kg * water_per_kg from processing specs) to the water allocation step or as a separate community water draw.
2. State explicitly that processing water is negligible relative to irrigation and omitted by design.

---

## Issue 10: `sell_price_at_entry` Stored but Never Used (Dead Field)

**Location:** Step 4 line ~500 (StorageTranche creation)

**Problem:** Each StorageTranche records `sell_price_at_entry=fresh_price` at harvest time. But all sale steps (3, 5a, 5b) price tranches using `prices[crop_name][product_type]` at the time of sale. The MarketPolicyContext receives `current_price_per_kg` and `avg_price_per_kg` but not entry price. No code path reads `sell_price_at_entry`.

**Resolution needed:** Either:

1. Remove the field if it serves no purpose.
2. Document it as informational (for reporting/debugging only).
3. Add it to MarketPolicyContext if market policies should consider entry price vs. current price.

---

## Issue 11: Aquifer State is a Passive Counter (Design Limitation)

**Location:** Step 2c (lines ~430-438)

**Problem:** `cumulative_gw_extraction_m3` is incremented daily but never feeds back into:

- Pumping energy (deeper water table = more lift energy)
- Extraction capacity limits (drawdown reducing well yield)
- Water quality (salinity increase with over-extraction)

The state dataclass is called `AquiferState` (per CLAUDE.md), which implies dynamic modeling. An implementer might expect extraction-dependent behavior.

**Resolution needed:** Add a note that aquifer dynamics are not modeled in this phase — extraction tracking is for reporting only. This prevents implementers from wiring up feedback loops that aren't specified.

---

## Issue 12: Monthly Summary Aggregation Undefined (Missing Computation)

**Location:** Output Generation step 3 (line ~1008-1009)

**Problem:** The output pipeline produces `monthly_summary.csv` (referencing structure.md § 3.14 for schema), but the four-stage metric computation pipeline (Stages 1-4, lines ~967-988) only defines yearly, lifetime, and financial metrics. No monthly aggregation step is specified. An implementer wouldn't know the aggregation rules (SUM vs. AVG vs. last-day-of-month for each field).

**Resolution needed:** Add a brief note before Stage 1 specifying that monthly summaries are computed by aggregating daily records per calendar month (with SUM for flows like revenue/cost/volume, AVG for rates/ratios, and last-day for stock values like cash and storage). Or reference the schema in structure.md if aggregation rules live there.

---

## Issue 13: Initialization Step 14 "Per-Crop Contribution Trackers" Undefined

**Location:** Initialization, line ~127

**Problem:** "Initialize per-crop contribution trackers (all zero)" is listed as an initialization step but is not referenced anywhere in the daily loop, post-loop reporting, or supporting references. It's unclear what these trackers are, what they track, or where they're used. Possible interpretations:

- `crop.cumulative_water_received` (but this is initialized per-cycle in the state machine, not at simulation start)
- Revenue contribution per crop (but revenue is tracked via tranche.farm_shares at point of sale)

**Resolution needed:** Either remove this step (if it's vestigial) or define what the trackers are and where they're consumed.

---

## Pass 3: Final Findings

Third pass looking for anything the first 13 issues missed.

---

## Issue 14: Energy-Water Temporal Decoupling (Modeling Design Choice)

**Location:** Step 2 (lines ~323-438) vs. Step 6 (lines ~574-677)

**Problem:** Water is fully allocated and delivered in Step 2 (consuming energy for pumping, treatment, and conveyance). Energy is dispatched in Step 6. This means water delivery is never physically constrained by energy availability — only by water infrastructure capacity and treatment capacity.

For `renewable_first` and `all_grid` policies this is fine because the grid provides an unlimited energy backstop. But for `microgrid` (no grid connection), the simulation could deliver water requiring more energy than the community can generate. The energy shortfall appears as `unmet_kwh` in the dispatch result — tracked but with no physical consequence. The water was already delivered.

In reality, you cannot pump water without electricity. A microgrid community with insufficient generation would face water delivery cuts, not just an energy accounting shortfall.

**Impact:** Microgrid scenarios could show unrealistically high water delivery and correspondingly understated water stress, overstating crop yields.

**Resolution needed:** Either:

1. Add an energy pre-check in Step 2 that estimates available energy and constrains water delivery when the energy policy is `microgrid`.
2. Document this as a known simplification: "Water delivery assumes sufficient energy is available. For microgrid scenarios, check dispatch_result.unmet_kwh to assess whether delivery was physically feasible."
3. Accept the current design — the energy system is sized in Layer 2, so a well-configured scenario wouldn't produce large unmet demand.

---

## Issue 15: Zero-Yield Harvest Creates Division by Zero in farm_shares (Zero Guard)

**Location:** Step 4, line ~496

**Problem:** `farm_shares = {farm_id: farm_kg / pooled_kg}`. If severe water stress or `yield_factor = 0` produces zero raw yield for ALL contributing farms, then `pooled_kg = 0` and the division fails. The pool entry would exist (the crop was harvested) but contain zero kilograms.

The Step 4 loop enters "FOR each crop in pool" without checking if `pooled_kg > 0`. A zero-kg pool would propagate through:

- food_policy.allocate() receiving `harvest_available_kg=0`
- `input_kg = 0 * fraction = 0` (fine)
- `farm_shares = farm_kg / 0` (division by zero)

**Resolution needed:** Add a zero guard: skip tranche creation when pooled_kg = 0 for a crop. The crop still transitions to DORMANT, but no tranche is created and no revenue flows.

---

## Issue 16: Debt Service Does Not Update When Loans Expire (State Update Gap)

**Location:** Step 0 monthly operations (lines ~178-184) vs. Step 7a (line ~686)

**Problem:** Step 7a uses `economic_state.monthly_debt_service / days_in_current_month` for daily debt allocation. Step 0 advances each loan's amortization schedule monthly, decrementing `remaining_months`. When `remaining_months` reaches 0, the loan is fully repaid. But nothing in the spec updates `monthly_debt_service` to exclude the repaid loan's payment.

If `monthly_debt_service` is a static value computed at initialization (sum of all loan payments), it would continue accruing after loans are paid off. For a 15-year simulation with a 10-year loan, the last 5 years would have phantom debt service costs.

**Resolution needed:** Either:

1. Specify that `monthly_debt_service` is recomputed each month as `SUM(monthly_payment for loans where remaining_months > 0)`.
2. Clarify that all loans span the full simulation period (so this can't happen).

---

## Issue 17: community_storage Not Explicitly Initialized (Minor Omission)

**Location:** Initialization Steps 8-10 vs. Steps 3-5 usage

**Problem:** Water storage (Step 9) and battery SOC (Step 10) are explicitly initialized. But `community_storage` (the list of StorageTranches used in Steps 3, 4, 5) is never mentioned in initialization. It's presumably empty at start, but this is implicit rather than explicit — inconsistent with the level of detail elsewhere.

**Resolution needed:** Add a line to initialization: "Initialize community_storage as empty (no inventory)." One sentence.

---

## Pass 4: Final Findings

Fourth pass with focus on data flow tracing, pricing consistency, and pseudocode accuracy.

---

## Issue 18: Dual Energy Pricing Regimes Not Carried Through to Dispatch (Pricing Inconsistency)

**Location:** Step 6b (line ~629-638) vs. Pricing Resolution (lines ~787-797)

**Problem:** The spec defines two energy pricing regimes (agricultural and community) with potentially different electricity prices — different CSV files, different tariff structures. Water allocation correctly differentiates: Step 2 Phase 1 uses `resolve_energy_price("agricultural")` for farm water treatment; Step 2b uses `resolve_water_price("community")` for household/building water.

But energy dispatch (Step 6b) receives a single `grid_price_per_kwh` without specifying which regime resolves it. The spec never shows the resolution for this parameter. Cost attribution (Step 6c) then pro-rates the total dispatch cost proportionally across farms and community demand.

If agricultural and community electricity prices differ (which Egyptian tariff structures allow — agricultural rates differ from residential/commercial), the blended approach produces incorrect cost allocation:

- Farms consuming 80% of energy at $0.05/kWh and community consuming 20% at $0.10/kWh should yield different per-kWh costs for each.
- The current flow computes one total cost and splits 80/20, effectively charging farms the community rate and vice versa.

Contrast with water, where this is handled correctly: farm irrigation uses agricultural water pricing (Step 2), community water uses community pricing (Step 2b), and the costs are tracked separately.

**Resolution needed:** Either:

1. Compute two dispatch sub-totals (farm energy at agricultural rate, community energy at community rate) in Step 6c, analogous to how water costs are split.
2. Resolve `grid_price_per_kwh` explicitly (e.g., "use agricultural rate for dispatch; community energy cost is adjusted post-dispatch").
3. Document that the model uses a single blended electricity price and note the approximation.

---

## Issue 19: Input Cost Pseudocode Missing Per-Crop Loop (Ambiguous)

**Location:** Step 7c, lines ~728-731

**Problem:** The input cost pseudocode reads:

```
input_cost = lookup(input_costs-toy.csv, crop_name).annual_cost_usd_per_ha
             * active_ha / 365
             # active_ha = SUM(crop.effective_area_ha for active crops on this farm)
```

This appears to look up a single `crop_name` and multiply by total farm active area. For a farm with two active crops (tomatoes at 10 ha with $500/ha/yr and potatoes at 5 ha with $300/ha/yr), this would use one crop's rate applied to all 15 ha — producing an incorrect result.

Compare with the labor cost pseudocode directly above it, which explicitly says "for each active crop on this farm, look up activities." Input cost lacks this per-crop iteration.

**Correct formulation** (should sum per-crop, not use total active_ha with a single rate):

`input_cost = SUM over active crops: lookup(crop.name).annual_cost_usd_per_ha * crop.effective_area_ha / 365`

**Resolution needed:** Rewrite the input cost pseudocode with an explicit per-crop loop, matching the pattern used for labor cost.

---

## Verification Pass: Issue Status Updates

Second reviewer verified all 19 issues against source specs on 2026-02-22. Summary of status changes:

- **Issue 10 — ALREADY ADDRESSED.** `structure.md § 3.7` explicitly documents `sell_price_at_entry` as `"tracking only, not for sale"`. No spec change needed.
- **Issue 11 — ALREADY ADDRESSED.** `structure.md` (line 451) and `calculations_water.md` (line 369) both document that AquiferState was removed and aquifer dynamics are deferred. No spec change needed.
- **Issue 6 — RETARGETED.** The contradiction is NOT within `simulation_flow.md` — its overview and post-loop sections are consistent. The contradiction is between **CLAUDE.md** (Conventions: "yearly metrics snapshotted at year boundaries") and `simulation_flow.md`'s post-loop section. Fix CLAUDE.md, not `simulation_flow.md`.
- **Issue 5 — CROSS-REFERENCE ONLY.** Insolvency behavior IS defined in `calculations_economic.md § 24`: "Cash can go negative without penalty." `simulation_flow.md` just needs a cross-reference at Step 7c.
- **Issue 4 — CROSS-REFERENCE ONLY.** Economic policies are explicitly deferred in `policies.md § 9` and `calculations_economic.md` header. `simulation_flow.md` just needs a note.
- **Issue 13 — CLARIFIED.** The trackers are `FarmState.contribution_kg` (`structure.md § 3.2`). The actual gap is that Step 4 never updates them — no `farm.contribution_kg[crop_name] += farm_kg` line exists.

All other issues (1, 2, 3, 7, 8, 9, 12, 14, 15, 16, 17, 18, 19) confirmed valid as written.

---

## Pass 5: Additional Findings

Fifth pass tracing calculation formulas, edge-case arithmetic, and attribution logic through all referenced specs.

---

## Issue 20: Negative Yield from Water Stress Factor When K_y > 1 (Computation Bug)

**Location:** Step 4, line ~472; `calculations_crop.md § 1`

**Problem:** The FAO-33 water stress formula is:

```
water_stress_factor = 1 - K_y × (1 - water_ratio)
```

Where `water_ratio = clamp(cumulative_water_received / expected_total_water, 0, 1)`.

For crops with K_y > 1 (tomato 1.05, potato 1.10, onion 1.10), severe water deficit produces negative yield:

- water_ratio = 0 (no water delivered): `water_stress_factor = 1 - 1.05 = -0.05` (tomato)
- water_ratio = 0.05: `water_stress_factor = 1 - 1.05 × 0.95 = 0.0025` (barely positive)

Negative `water_stress_factor` propagates to `raw_yield_kg = Y_potential × (-0.05) × yield_factor × effective_area_ha`, producing negative kilograms. This negative yield would then enter the harvest pool, corrupt `farm_shares`, and produce negative revenue.

The FAO-33 formula physically means "complete crop failure" when water deficit exceeds `1/K_y` — the yield should floor at zero, not go negative.

**Resolution needed:** Add `water_stress_factor = max(0, water_stress_factor)` to the yield formula, or equivalently floor `raw_yield_kg` at 0. This should be stated in both `calculations_crop.md § 1` and `simulation_flow.md` Step 4.

---

## Issue 21: Processing Labor Attribution Unspecified for Pooled Harvests (Ambiguity)

**Location:** Step 4 (lines ~465-518) vs. Step 7c (lines ~719-727)

**Problem:** Step 4 pools farm harvests into a community harvest pool and processes them collectively. Step 7c computes per-farm labor cost including "processing labor (labor_hours_per_kg × harvested_kg × wage)." But processing operates on the pooled quantity — the community's processing equipment processes the combined harvest, not individual farm batches.

The spec doesn't say how processing labor hours are attributed to individual farms. Two reasonable approaches:

1. **Pro-rata by harvest contribution:** `farm_processing_hours = total_processing_hours × (farm_kg / pooled_kg)`. Consistent with `farm_shares` on StorageTranches.
2. **Per-farm input quantity:** `farm_processing_hours = farm_kg × hours_per_kg`. Same result as #1 if the per-kg rate is uniform.

Both produce the same number, but the spec should state this explicitly since labor cost is per-farm and processing is community-pooled. Without this, an implementer might compute processing labor only for the farm that "owns" the equipment, or skip it entirely because the harvest is pooled.

**Resolution needed:** Add a note in Step 7c labor cost pseudocode: "Processing labor attributed pro-rata by farm harvest contribution (farm_kg / pooled_kg), consistent with tranche farm_shares."

---

## Issue 22: contribution_kg Tracker Never Updated in Daily Loop (Dead State)

**Location:** Initialization Step 14 (line ~127), `structure.md § 3.2` (line ~423), Step 4 (lines ~465-518)

**Problem:** `FarmState.contribution_kg` is defined as `{crop_name: cumulative_kg} — lifetime harvest tracker` in `structure.md § 3.2`. Initialization Step 14 says "Initialize per-crop contribution trackers (all zero)." But Step 4, where farm harvests are computed (`farm_kg` per farm per crop), never includes a line like:

```
farm.contribution_kg[crop_name] += farm_kg
```

The tracker exists in the dataclass, is initialized, but is never written to during the simulation. It will remain all-zeros at the end of any run.

**Note:** This supersedes Issue 13, which identified the tracker as "undefined." The tracker IS defined in `structure.md § 3.2`; the gap is the missing update in the daily loop.

**Resolution needed:** Add to Step 4, inside the harvest loop: `farm.contribution_kg[crop_name] += farm_kg`. One line.

---

## Issue 23: Planting Schedule Reinitialization Undefined (Ambiguity)

**Location:** Step 0, line ~190-191

**Problem:** Yearly operations state: "Reinitialize planting schedules for DORMANT crops only." But the spec never defines what "reinitialize" means mechanistically.

Planting dates are MM-DD strings (e.g., "02-15"). During the simulation, these are resolved to absolute dates within the current year. At year boundary, "reinitialize" presumably means resolving the same MM-DD strings to the new year. But:

- Is this a simple date resolution (`"02-15"` → `2012-02-15`)?
- Does it reset any per-crop state beyond `planting_dates`?
- What if a DORMANT crop's first planting date in the new year has already passed by the time the yearly reset runs (e.g., January 1 reset, but a planting date was January 1)?

The state machine pseudocode checks `IF today matches a planting_date` daily, so the reinitialization presumably just makes the new year's dates available for matching. But this is implicit.

**Resolution needed:** Replace "Reinitialize planting schedules for DORMANT crops only" with: "Resolve planting_dates MM-DD strings to absolute dates in the new calendar year for DORMANT crops. Active (non-DORMANT) crops retain their current cycle and are not affected."
