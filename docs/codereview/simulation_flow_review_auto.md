# Simulation Flow Spec Review

**Reviewer:** Auto  
**Date:** February 22, 2025  
**Document reviewed:** `specs/simulation_flow.md`

---

## 1. Gaps and Ambiguities

### 1.1 State and Data Contracts

- **`allocate()` signature** — Steps 12, 7b, and 6c call `allocate(capex_cash_outflow, cost_allocation_method)` or `allocate(Total_daily_shared_opex, cost_allocation_method)`. The spec never defines the function signature: required inputs (e.g., for usage-proportional, does it need daily water/usage at this call site?), return shape (per-farm dict? list ordered by farm?), or whether the same function is used for CAPEX, shared opex, debt service, and export revenue and how "usage" is defined for each.

- **Where revenue is written** — Steps 3, 5a, 5b say "Attribute revenue to farms via tranche.farm_shares" but never explicitly state that this means writing to `farm.daily_revenue`. Step 7 reads `farm.daily_revenue` for crop_revenue; the spec should state that attribution is `farm.daily_revenue += sale_revenue * tranche.farm_shares[farm_id]` (or equivalent) so implementers don't have to infer it.

- **Location of cumulative_gw_extraction_m3** — Step 2c updates `cumulative_gw_extraction_m3` but doesn't say which dataclass/state object holds it (e.g. SimulationState, AquiferState, EconomicState). Same for "per-crop contribution trackers" in init Step 14.

### 1.2 Step 0 and Crop State Machine

- **"Reset planting schedules" at year start** — The phrase "Reinitialize planting schedules for DORMANT crops only" is vague. Does it mean only "next planting_date = first occurrence of MM-DD in the new year," or are there other fields (e.g. crop mix, area) re-initialized? A developer needs to know exactly what "reset" means.

- **expected_total_water indexing** — The formula `expected_total_water = SUM(irrigation_m3_per_ha_per_day(planting_date, day) for day in range(season_length_days)) * effective_area_ha` doesn't specify whether `day` is 0-based crop_day or 1-based; the precomputed file schema (structure.md § 4) must be consistent with this. Unclear if "day" aligns with the same indexing used in Irrigation Demand Lookup and Step 1.

- **Debt schedules** — "FOR each debt_schedule" (monthly amortization) doesn't say where these live (economic_state, scenario, or derived at init). Section reference for "amortization formula" is given but not the data source.

### 1.3 Step 2 (Water)

- **Scope of water_storage** — Step 1 uses `water_storage.current_m3` in CropPolicyContext. The spec doesn't explicitly state that this is the single community irrigation storage tank (shared), so a developer might assume per-farm tanks unless they read Phase 3 carefully.

- **Phase 2 scaling and cost/energy** — Phase 2 says "Recalculate allocation.cost_usd and allocation.energy_used_kwh" after scaling but doesn't point to the shared cost/energy logic (policies.md § 4) or say whether the same formulas apply with the new gw/municipal split. A one-line pointer would remove ambiguity.

### 1.4 Step 5 (Sales and Inventory)

- **"Oldest first" for overflow (5a)** — "Oldest tranche" isn't defined: sort by harvest_date, expiry_date, or insertion order? Same choice affects Step 3 (expiry) and 5b FIFO. One explicit rule (e.g. "by harvest_date, then expiry_date") would standardize behavior.

- **5b: when is remaining_capacity / total_stored_kg taken?** — For a given product_type there are multiple crops. It's unclear whether `storage_capacity_kg` and `total_stored_kg` in MarketPolicyContext are a snapshot at the start of the product_type loop or updated after each crop's sales within that product_type. That affects whether the policy sees stale capacity.

### 1.5 Step 7 (Accounting)

- **Negative cash** — `farm.current_capital_usd += total_revenue - total_cost` can go negative. The spec doesn't say whether to allow negative (and flag in metrics), enforce non-negative and fail, or treat as "technical insolvency" with defined behavior. Important for survivability and error-handling.

- **Input cost and "active_ha"** — `input_cost = ... annual_cost_usd_per_ha * active_ha / 365` — it's not stated whether "active" means only crops in growth stages (INITIAL..LATE_SEASON) or also HARVEST_READY, and whether "annual" is per crop or per farm. Affects daily cost.

- **Labor and "active crop"** — Labor is driven by "active crop" and growth stage. Unclear if "active" here means "not DORMANT" (so HARVEST_READY counts until harvest) or "has water demand" (INITIAL..LATE_SEASON). Affects whether harvest-day labor is included and activity lookup.

### 1.6 Post-Loop and Metrics

- **Terminal inventory and cash** — "Added to the final year's net income for NPV/IRR only" — it's not explicit that this value is *not* added to `farm.current_capital_usd` or any balance sheet; it's only used in the NPV formula. A developer might mistakenly add it to cash.

- **Metric stages and tables** — Stages 1–4 reference several calculation and metrics docs. It's not explicit which metrics consume which tables (e.g. only daily farm/community records, or also final_state / scenario). A short "inputs per stage" would help.

---

## 2. Inconsistencies and Edge Cases

### 2.1 Naming and Terminology

- **"Step 2b" and "Step 2c"** — The main loop table lists Steps 0–7; Steps 2b and 2c are sub-steps of Step 2. The high-level table doesn't mention community water or GW extraction; a developer could miss them. Adding one line each (e.g. "2b Community water", "2c GW tracking") would align table and body.

### 2.2 avg_prices and Data Frequency

- **Trailing average** — "Up to 12 prior monthly entries" (toy) vs "up to 12 prior annual entries" (research) means very different windows (12 months vs 12 years). The spec might mean "12 data points" in both cases, but for research that's 12 years of history. If the intent is "recent" (e.g. 1–2 years), the research case may need different wording or a cap.

### 2.3 Water Phase 2 and Storage Semantics

- **available_supply** — `available_supply = water_storage.current_m3 + total_treatment_capacity` assumes we can use all of current storage plus full treatment capacity in one day. If there's a physical ordering (e.g. use storage first, then treat), that's consistent, but the spec doesn't state the rule. A single sentence (e.g. "Delivery in a day is limited by current storage plus today's treatment output.") would make the constraint explicit.

### 2.4 Development Checks vs Production

- **Balance checks** — "Water balance" and "Energy balance" are "disabled for production Monte Carlo." It's not said whether they're optional in normal (non–Monte Carlo) runs or always on when not in "production MC." Clarifying when to run them avoids divergent behavior across run types.

---

## 3. Questions a Developer Would Likely Ask

### Data and Configuration

1. **Simulation period** — Is the date range inclusive on both ends, and how are leap years and month lengths handled (e.g. for "days_in_current_month" and monthly debt service)?

2. **Precomputed indexing** — For irrigation and yield lookups: are precomputed series indexed by (planting_date, crop_day) with crop_day 0 = planting day, and are dates in the CSV timezone-naive (e.g. local simulation calendar)?

3. **Price lookups** — When "current_date is outside the CSV date range," is "nearest available value" always the first or last row, or do we need separate rules for "before first date" vs "after last date"?

4. **collective_farm_override** — If a farm has no policy for a domain and override supplies one, is that the exact rule, or are there fallbacks (e.g. default policy name per domain)?

### Order and Determinism

5. **Farm order** — Should "FOR each farm" be a fixed order (e.g. by farm.id) everywhere so results are deterministic and reproducible?

6. **Tranche order** — For "oldest first" in Steps 3 and 5, is the iteration order over `community_storage` defined (e.g. sort by harvest_date then expiry_date before iterating), or is it "whatever order they're stored"?

### Numerics and Units

7. **Rounding** — Are there rounding rules for currency (e.g. 2 decimals), for volumes (m³) and energy (kWh), and for kg (integer vs decimal)? When are they applied (per step vs only on output)?

8. **Zero and near-zero** — Beyond the documented zero-demand guards, should very small positive demands (e.g. 1e-10) be treated as zero to avoid numerical noise in ratios and allocations?

### Policies and Allocation

9. **Usage-proportional inputs** — For "usage-proportional" cost allocation: is the usage metric always "daily water consumption" (as in § 2.8), and for which steps (CAPEX init, shared opex, debt, export revenue)? Same metric for all?

10. **Processing energy when no harvest** — Step 6a uses `E_processing_today` from Step 4; when there's no harvest it's 0. Should the code path "no harvest → E_processing = 0" be stated explicitly in Step 6 to avoid doubt?

### Edge Cases

11. **Multiple harvests same day** — If the same crop on the same farm has multiple plantings (e.g. staggered), the spec says "only one growth cycle per crop per farm." So only one harvest per crop per farm per day. Worth confirming that "harvest today" means at most one harvest event per (farm, crop) per day.

12. **Storage at capacity at day start** — If `total_stored_kg[product_type]` already equals `storage_capacities_kg[product_type]` at the start of Step 5a (e.g. no expiry sales in Step 3), do we still run the overflow loop (and potentially sell), or is overflow only when we're strictly over after Step 4?

13. **Battery and dispatch** — If `dispatch_energy` returns a result that doesn't exactly match the documented merit order (e.g. due to rounding or curtailment), should the code treat "supply = demand + export + storage + curtailment + unmet" as the authoritative balance definition for the development check?

### Output and Reporting

14. **Final state vs daily records** — Should `final_state.json` be derivable from the last day's daily records plus terminal inventory valuation, or can it contain extra fields that are only in state (e.g. in_progress_crops)? That determines whether reporting can be implemented as "replay last day + finalization" or must read live state.

15. **Monthly summary** — "Aggregated from daily" for monthly_summary: which quantities are summed (e.g. revenue, cost, water), which averaged (e.g. prices, SOC), and which are end-of-month snapshots (e.g. storage, cash)?

---

## 4. Summary

- **Strengths:** The three-phase structure (init, daily loop, post-loop) is clear; the ordering of water (allocate → constrain → apply) and the separation of community vs farm water and energy are well specified. The "water energy term boundaries" table and the harvest-to-revenue chain are helpful.
- **Main gaps:** The exact semantics of `allocate()`, where attributed revenue and GW extraction live in state, definition of "oldest" tranche, and when `remaining_capacity` is sampled in Step 5b. Negative cash and terminal inventory handling also need one-line rules.
- **Developer friction:** Without the referenced structure/policies/calculations docs, implementers would have to guess dataclass fields, policy I/O, and formula details. A short "implementation checklist" (e.g. "Before coding Step X, resolve: allocate signature, state location of Y") would reduce back-and-forth.
