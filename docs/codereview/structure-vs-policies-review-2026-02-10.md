# Structure vs. Policies Alignment Review

**Date:** 2026-02-10
**Status:** RESOLVED (all 11 issues addressed 2026-02-10)
**Files reviewed:** `docs/arch/structure.md`, `docs/arch/policies.md`
**Cross-referenced:** `docs/arch/calculations.md`

## Purpose

Identify areas where `structure.md` (canonical configuration schema) is too broad or ambiguous, and where `policies.md` (policy decision logic) fails to fully unpack or contradicts the structure spec. Issues ordered by impact and lack of clarity.

---

## 1. Economic policy spending cap has no enforcement mechanism

**Impact: Critical | Clarity: Low**

`structure.md` (lines 282-286) and `policies.md` (Section 7) define economic policies that output `max_spending_usd` and `spending_priority`, but neither document explains what spending gets capped. The daily execution order (`policies.md` line 38-46) runs economic policy last (monthly/yearly), after all costs have already been incurred by water, energy, crop, and food processing policies.

**Open questions:**
- If a farm has already spent money on water and energy, what does a spending cap retroactively constrain?
- Does it reduce next month's water treatment? Prevent equipment repairs? Gate only discretionary investment?
- What mechanism propagates `max_spending_usd` into the next period's policy decisions?

**Consequence:** Without answers, the economic policies produce output fields that nothing consumes. They are decorative.

**Resolution options:**
- (a) Make `max_spending` a forward-looking budget that constrains the *next* period's operating decisions
- (b) Limit `max_spending` to discretionary/investment spending only, with operating costs (water, energy) always paid
- (c) Define a feedback loop where economic policy output feeds into next-day crop/water policy contexts as a constraint

---

## 2. Market policy parameters undetermined (hold_for_peak, adaptive)

**Impact: Critical | Clarity: Low**

`policies.md` (lines 481-482, 515-516) explicitly marks these as TODOs:
- `price_threshold_multiplier` for `hold_for_peak` -- no default, no range, no guidance
- Sigmoid midpoint, steepness, min/max band for `adaptive` -- no default, no range

**Consequence:** These policies cannot be implemented as specified. Only `sell_all_immediately` has complete logic.

**Resolution:** Determine reasonable defaults. Suggested starting points:
- `hold_for_peak`: `price_threshold_multiplier = 1.2` (sell when price is 20% above average)
- `adaptive` sigmoid: midpoint = 1.0 (price ratio), steepness = 5.0, min_sell = 0.2, max_sell = 1.0

---

## 3. Market context lacks product type differentiation

**Impact: High | Clarity: Medium**

The `MarketPolicyContext` (`policies.md` lines 444-454) has `crop_name` and `current_price_per_kg`, but doesn't distinguish between fresh, packaged, canned, and dried versions of the same crop. A dried tomato and a fresh tomato have very different prices, storage lives, and market dynamics.

**Missing field:** `product_type` (fresh / packaged / canned / dried)

**Evidence:** `structure.md` (line 249) shows the output has `target_price_per_kg`, but the context provides no way to look up per-product-type pricing. The food processing umbrella rule (`policies.md` lines 332-339) tracks tranches by product type, but the market policy context discards this information.

**Resolution:** Add `product_type` to `MarketPolicyContext`. Price lookups and storage life should be product-type-specific.

---

## 4. `max_municipal` policy references nonexistent municipal quota

**Impact: High | Clarity: Low**

`policies.md` (line 151) references `remaining_municipal_quota` and `municipal_quota_exists`, but:
- The `WaterPolicyContext` (`policies.md` lines 70-85) has no `municipal_quota` field
- `structure.md` defines no municipal quota parameter in the water system or pricing configuration
- No mechanism exists to set or track a municipal quota in the scenario YAML

**Consequence:** This policy is unimplementable as written.

**Additional ambiguity:** The description says "If no quota is set, behaves as 100% municipal with fallback to groundwater only if municipal supply is physically unavailable." But the operational independence principle (`policies.md` line 49) states municipal water is always available. So without a quota, this policy has no fallback trigger and is functionally "100% municipal, always."

**Resolution options:**
- (a) Add `municipal_quota_m3_year` to `WaterPolicyContext` and scenario config, with tracking fields similar to `quota_enforced`
- (b) Simplify the policy: remove the quota mechanism entirely and make `max_municipal` a straightforward "prefer municipal, groundwater only if municipal is more expensive" policy
- (c) Define municipal supply constraints (daily delivery limits, seasonal availability) that create a meaningful fallback trigger

---

## 5. Household/shared facility policy application undefined

**Impact: High | Clarity: Low**

Both documents state that households and shared facilities use "a subset of water and energy policies" (`structure.md` line 194, `policies.md` lines 10-11), but provide no further specification.

**Open questions:**
- Which policies apply to households? All six water policies? Only a subset?
- Where in the scenario YAML are household/facility policies configured?
- How is household water demand calculated and fed into the policy context?
- What is `demand_m3` for a household vs. a farm?
- `structure.md` (lines 127-130) defines community buildings and houses as counts but has no configuration for their policy selection

**Resolution:** Either:
- (a) Define a `household_policies` section in the scenario YAML with explicit water/energy policy selections
- (b) Specify that household/facility operations always use a fixed default policy (e.g., `max_municipal` for water, `all_grid` for energy) and remove the "subset of policies" language
- (c) Defer household policy selection to a later development phase and mark this as out-of-scope in both documents

---

## 6. Energy policy outputs don't connect to dispatch function

**Impact: Medium | Clarity: Medium**

`policies.md` (line 559) acknowledges: "These policies return allocation flags that should parameterize the dispatch function." But the spec doesn't define how.

**Specific gaps:**
- How should `dispatch_energy()` read and apply the boolean flags?
- What does `battery_reserve_pct` control -- minimum SOC before discharge begins? Before grid import triggers?
- Do `sell_renewables_to_grid` and `grid_export` overlap or are they distinct? The `all_grid` policy sets both to `true`.
- What happens if `all_grid` is selected but no renewables are configured? Is export revenue zero, or is this an error state?

**Resolution:** Define a dispatch function interface that accepts the `EnergyAllocation` output and maps each flag to a dispatch behavior. Clarify the distinction between `grid_export` (surplus after self-consumption) and `sell_renewables_to_grid` (deliberate routing of all renewable output to export).

---

## 7. Food processing umbrella rule execution timing ambiguous

**Impact: Medium | Clarity: Medium**

The umbrella rule (`policies.md` lines 332-339) says forced sales from expiry/overflow "take precedence over all market policy decisions." But the execution order (`policies.md` lines 38-46) runs food processing at step 4 and market at step 5. The umbrella rule operates on existing stored inventory, not just today's harvest.

**Open questions:**
- Does the umbrella rule run as part of step 4 (food processing) or as a pre-check before step 5 (market)?
- If a tranche expires today AND the market policy says hold -- does the umbrella rule force the sale, then the market policy runs on remaining inventory?
- Does forced-sale revenue use `current_price_per_kg` or a discounted distress price?

**Resolution:** Define explicit sub-steps:
1. Step 4a: Check inventory for expiry and overflow, execute forced sales
2. Step 4b: Process today's harvest according to food processing policy
3. Step 5: Market policy evaluates remaining inventory (excluding forced sales)

---

## 8. `conserve_groundwater` ratio cap not tracked in decision

**Impact: Medium | Clarity: Medium**

`policies.md` (line 268) says `max_gw_ratio` caps groundwater at 30% of demand, then the constraint check applies. If 30% of demand exceeds well capacity, the constraint clips further.

**Gap:** The `decision_reason` only tracks the constraint hit, not the ratio cap. A farm might request 30% of demand (30 m3), get clipped to 20 m3 by well capacity, and the reason says `"threshold_exceeded_but_well_limit"` -- but there's no tracking that the ratio cap was the primary limiter.

**Consequence:** In analysis, it's impossible to distinguish whether a farm was conservation-limited or infrastructure-limited.

**Resolution:** Add a secondary field (e.g., `limiting_factor: "ratio_cap" | "well_limit" | "treatment_limit"`) or encode both in the reason string (e.g., `"threshold_exceeded_ratio_capped_and_well_limit"`).

---

## 9. Crop policy `priority` output field has no producer or consumer

**Impact: Medium | Clarity: Low**

The crop policy output (`policies.md` line 684) includes `priority` -- "Crop priority; higher values mean more important to water." But:
- None of the three crop policies (fixed_schedule, deficit_irrigation, weather_adaptive) set or return a priority value in their pseudocode
- Nothing in the water policy context or logic consumes a priority value
- No multi-crop water rationing logic exists in the water policy spec

**Consequence:** Orphaned field. Either it should be removed, or a rationing mechanism should be designed.

**Resolution options:**
- (a) Remove `priority` from the crop policy output until multi-crop water rationing is designed
- (b) Define how priority feeds into water allocation when total demand exceeds supply (e.g., high-priority crops get water first, low-priority crops get deficit)
- (c) Assign default priorities by growth stage (e.g., initial/development = high, late_season = low) and add a priority-aware allocation step to the water policy

---

## 10. `min_water_quality` quality check after constraint clip

**Impact: Low | Clarity: Medium**

`policies.md` (lines 219-224) handles the case where groundwater gets clipped by constraints, increasing the municipal fraction. But the resulting mix quality isn't verified against the target TDS.

**Analysis:**
- If constraints reduce groundwater, the municipal fraction increases, which typically *improves* quality (municipal water is cleaner). This is fine.
- The reverse case -- where municipal water is also moderately salty -- could result in a mix that still exceeds the target even with more municipal water. The pseudocode at lines 200-204 handles `required_municipal_fraction >= 1.0` for this case, but doesn't address the scenario where constraints shift the blend away from the computed ratio.

**Resolution:** Add a post-allocation quality check. If `mixed_tds_ppm > target_tds_ppm` after constraint clipping, log a warning in `decision_reason` (e.g., `"quality_target_not_met"`). No behavioral change needed -- the farm still gets water -- but the tracking enables analysis.

---

## 11. `storage_life_days` data source unspecified

**Impact: Low | Clarity: Medium**

`structure.md` (lines 98, 105, 113, 119) gives example ranges for storage life by processing type:
- Fresh: 3-7 days
- Dried: 6-12 months
- Canned: 1-3 years
- Packaged: 2-8 weeks

But the spec doesn't clarify whether these are:
- Per-crop values (dried tomatoes vs. dried kale)
- Single values per processing type
- Scenario-configurable parameters

The market policy context (`policies.md` line 453) uses `storage_life_days` as a single value per tranche, but the data source for this value is unspecified.

**Resolution:** Define a data source. Options:
- (a) Per-crop, per-product-type matrix in a CSV file (e.g., `data/parameters/food_processing/storage_life.csv`)
- (b) Single value per processing type from the system configuration (simpler, less accurate)
- (c) Crop-specific values in the crop parameters file, with a column per processing type

---

## Summary Table

| # | Issue | Resolution | Files changed |
|---|---|---|---|
| 1 | Economic policy spending cap unused | Removed `max_spending_usd` and `spending_priority` from spec and code | structure.md, policies.md, economic_policies.py |
| 2 | Market policy parameters undetermined | Added defaults: hold_for_peak `price_threshold_multiplier=1.2`, adaptive sigmoid `midpoint=1.0, steepness=5.0, min_sell=0.2, max_sell=1.0` | policies.md, structure.md, market_policies.py |
| 3 | Market context lacks product type | Added `product_type` field to `MarketPolicyContext`; pointed to per-product price files and spoilage_rates CSV | policies.md, structure.md, market_policies.py |
| 4 | `max_municipal` references nonexistent quota | Removed municipal quota entirely; policy is now simple 100% municipal | policies.md, structure.md |
| 5 | Household/facility policy undefined | Limited to `max_groundwater` or `max_municipal` (water) and `renewable_first` or `all_grid` (energy); configured via `household_policies` in scenario YAML | policies.md, structure.md |
| 6 | Energy dispatch note about gaps | Removed the "current status" note | policies.md, structure.md |
| 7 | Umbrella rule timing ambiguous | Clarified: process harvest → update storage → check expiry/overflow (forced sales) → market policy runs on remaining inventory | policies.md, structure.md |
| 8 | `conserve_groundwater` ratio cap not tracked | Added `limiting_factor` field to `WaterDecisionMetadata` (values: "ratio_cap", "well_limit", "treatment_limit") | policies.md, structure.md, water_policies.py |
| 9 | Crop policy `priority` orphaned | Removed from spec and code | policies.md, structure.md, crop_policies.py |
| 10 | `min_water_quality` quality after clip | Clarified: municipal is always highest quality; constraint clip increases municipal fraction, improving quality above target | policies.md, structure.md |
| 11 | `storage_life_days` data source unspecified | Added `storage_life_days` column to both processing_specs CSV files; pointed docs to spoilage_rates CSV | policies.md, structure.md, processing_specs-research.csv, processing_specs-toy.csv |
