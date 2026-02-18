# Architecture Document Deep Review

**Date:** 2026-02-12
**Documents reviewed:**

- `docs/arch/structure.md` — Configuration schema and policy structure
- `docs/arch/policies.md` — Policy specifications and pseudocode
- `docs/arch/calculations.md` — Calculation methodologies and formulas

**Reviewer:** Claude Opus 4.6

---

## Table of Contents

1. [Document Disconnects (Logic, Terminology, Labeling, Calculations)](#1-document-disconnects)
2. [Missing Policies](#2-missing-policies)
3. [Missing Implementation Details for Junior Coders](#3-missing-implementation-details)
4. [Missing Formulas and Equations](#4-missing-formulas-and-equations)
5. [Cross-Cutting Issues](#5-cross-cutting-issues)

---

## 1. Document Disconnects

### 1.1 Water Policy Count: 5 vs 6

**Disconnect:** calculations.md states "five water allocation policies" (line 313) and lists only 5. structure.md and policies.md both define 6. The `min_water_quality` policy is fully specified in policies.md (Section 2.3) but entirely absent from calculations.md.

**Affected:** calculations.md

**Suggested resolution:** Update calculations.md to say "six" and add a `min_water_quality` entry.

**Owner response:** Remove any mention of the number of policies (which will always be changing). Ensure that each policy outlined in structure.md is represented in both policies.md and calculations.md (as needed). Add the missing min_water_quality policy where missing and add logic and equations in-line with the policy goal. If there is any question about the right equation, flag it for me as you implement.

---

---

### 1.2 Water Policy Name Mismatch

**Disconnect:** calculations.md uses PascalCase class names (`AlwaysGroundwater`, `AlwaysMunicipal`) that differ semantically from the canonical policy names in structure.md/policies.md (`max_groundwater`, `max_municipal`). "Always" implies unconditional use; "max" implies preferential use with fallback — the behavior described matches "max."

**Affected:** calculations.md

**Suggested resolution:** Use canonical snake_case names (`max_groundwater`, `max_municipal`, etc.) throughout calculations.md. Mention class names parenthetically if needed for code reference.

**Owner response:** Agree, use one single naming convention across all files and in turn in the code when written.

---

---

### 1.3 Energy Policy Names Completely Mismatched

**Disconnect:** structure.md and policies.md define `microgrid`, `renewable_first`, `all_grid`. calculations.md (line 850) references `PvFirstBatteryGridDiesel`, `GridFirst`, `CheapestEnergy` — entirely different names. `CheapestEnergy` has no counterpart in the specification documents at all. The mapping between spec names and code names is unclear.

**Affected:** All three documents

**Suggested resolution:** Align calculations.md to use canonical names. Decide whether `CheapestEnergy` is a real policy (add to spec) or stale code (deprecate).

**Owner response:** Agree on naming, see 1.2. Remove any policies not in the structure.md doc throughout.

---

---

### 1.4 Market Policy Count: 4 in CLAUDE.md vs 3 in Specs

**Disconnect:** CLAUDE.md claims "4 market timing policies." Both structure.md and policies.md define only 3: `sell_all_immediately`, `hold_for_peak`, `adaptive`.

**Affected:** CLAUDE.md

**Suggested resolution:** Update CLAUDE.md to say 3 market policies, or add the 4th to the spec if planned.

**Owner response:** Agree

---

---

### 1.5 Energy Pricing Schema: Dual Regime vs Single

**Disconnect:** structure.md (lines 170-178) defines energy pricing with separate agricultural and domestic regimes, each independently subsidized/unsubsidized. calculations.md (lines 1003, 1021-1024) defines a single global `energy_pricing.grid.pricing_regime`. Parameter names also differ: `price_usd_per_kwh` (structure) vs `base_price_usd_kwh` (calculations — missing `per_`). Additionally, calculations.md includes `use_peak_offpeak` and `annual_escalation_pct` sub-parameters not in structure.md.

**Affected:** structure.md and calculations.md

**Suggested resolution:** Adopt the dual-regime structure from structure.md in calculations.md. Standardize parameter names. Add `use_peak_offpeak` and `annual_escalation_pct` to structure.md if intended.

**Owner response:** Agree

### 1.6 Water Pricing Schema: Dual Regime vs Flat

**Disconnect:** structure.md (lines 157-168) defines water pricing with separate agricultural and domestic regimes. calculations.md (lines 1511-1512) references a flat `water_pricing.pricing_regime` without the split. policies.md (line 90) confirms the dual-regime model is intended.

**Affected:** calculations.md

**Suggested resolution:** Update calculations.md water cost dependencies to reference the dual-regime structure.

**Owner response:** Agree

---

---

### 1.7 Missing `max_drawdown_m` in structure.md

**Disconnect:** calculations.md (line 403) references `water_system.groundwater_wells.max_drawdown_m` annotated as "(new parameter)." This parameter does not exist in structure.md's groundwater wells configuration.

**Affected:** structure.md

**Suggested resolution:** Add `max_drawdown_m` to the groundwater wells section in structure.md.

**Owner response:** Agree

---

---

### 1.8 Missing `hub_height_m` in Wind Configuration

**Disconnect:** calculations.md (line 617) references `energy_system.wind.hub_height_m`. structure.md's wind section lists only `sys_capacity_kw`, `type`, and `financing_status` — no `hub_height_m`.

**Affected:** structure.md

**Suggested resolution:** Add `hub_height_m` to the wind system configuration in structure.md.

**Owner response:** Review the data files -- the hub height is specified there I believe. Hub height should not be set by user, they should select a type of wind turbine.

---

---

### 1.9 Salinity Level Categories: 4 vs 3

**Disconnect:** structure.md (line 43) defines 4 salinity levels: `[low, moderate, high, very_high]`. calculations.md (line 135) lists only 3: `(low / moderate / high)`. If the treatment energy CSV has no `very_high` row, selecting it in the scenario would fail.

**Affected:** calculations.md or structure.md

**Suggested resolution:** Either add `very_high` to calculations.md and the data CSV, or remove it from structure.md.

**Owner response:** Agree

---

---

### 1.10 Debt Service References Nonexistent Config Section

**Disconnect:** calculations.md (lines 1620-1622) references `economics.debt.principal_usd`, `economics.debt.term_years`, `economics.debt.interest_rate`. No such section exists in structure.md. The actual debt mechanism is per-subsystem via `financing_status` and `financing_profiles.csv` (structure.md line 35).

**Affected:** calculations.md

**Suggested resolution:** Rewrite calculations.md debt service dependencies to reference the per-subsystem `financing_status` mechanism.

**Owner response:** Agree

---

---

### 1.11 `market_responsive` Food Processing: Different Logic in Two Documents

**Disconnect:** policies.md (line 410) compares `fresh_price_per_kg < reference_price * 0.80` with fixed two-state allocation tables. calculations.md (lines 1256-1263) describes a completely different approach: comparing fresh price to a "processed price equivalent" and dynamically selecting the highest net-value pathway.

**Affected:** calculations.md

**Suggested resolution:** Replace the calculations.md conceptual version with a cross-reference to policies.md Section 3.4 as the authoritative logic.

**Owner response:** Agree

---

---

### 1.12 `market_responsive` in structure.md: Range Notation vs Binary States

**Disconnect:** structure.md (line 229) shows `30-65%` range notation for fresh fraction, implying continuous adjustment. policies.md pseudocode (lines 410-415) reveals it is a binary switch between exactly 30% and exactly 65%.

**Affected:** structure.md

**Suggested resolution:** Update structure.md table to show two rows (one per price condition), or add a note that ranges are endpoints of a binary switch.

**Owner response:** Agree

---

---

### 1.13 Energy Dispatch Ignores Policy Output Flags

**Disconnect:** policies.md defines energy policies returning boolean flags (`use_renewables`, `use_battery`, `grid_import`, `use_generator`, etc.). The dispatch algorithm in calculations.md uses a hardcoded renewable-first merit order regardless of policy selection. calculations.md (line 850) explicitly states "Energy policy objects are not consumed by the dispatch function."

**Affected:** calculations.md and policies.md

**Suggested resolution:** Either update the dispatch algorithm to be conditioned on policy flags, or add an explicit note that dispatch is a hardcoded MVP approximation equivalent to `renewable_first`.

**Owner response:** Udpate calculation file to implement proper equations for each of the policy types outlined in structure/policies file. 

---

---

### 1.14 Missing Output Fields from structure.md

**Disconnect:** structure.md declares "a `decision_reason` string in every output" (line 203), but 3 of 6 domain output specs in structure.md omit it (Water, Energy, Food Processing). Energy output lists no fields at all. `constraint_hit` is also absent from the Water output spec in structure.md despite being defined in policies.md.

**Affected:** structure.md

**Suggested resolution:** Add complete output field lists to all 6 domains in structure.md, matching policies.md definitions.

**Owner response:** Agree

---

---

### 1.15 Execution Order Missing from structure.md

**Disconnect:** policies.md defines a specific daily execution order (Crop → Water → Energy → Food → Forced sales → Market → Economic). structure.md says policies are "called daily" but does not specify order or dependencies.

**Affected:** structure.md

**Suggested resolution:** Add the execution order to structure.md Section 3.

**Owner response:** Agree

---

---

### 1.16 `planting_dates` (Plural) vs `planting_date` (Singular)

**Disconnect:** structure.md (line 145) uses `planting_dates` (plural, list). calculations.md (line 1182) references `planting_date` (singular).

**Affected:** calculations.md

**Suggested resolution:** Use `planting_dates` (plural) in calculations.md.

**Owner response:** Agree

---

---

### 1.17 Total Energy Demand: 6-Component Formula vs 3-Component Dispatch

**Disconnect:** calculations.md defines the full demand with 6 components (line 861) but the dispatch section uses only 3 (line 805), missing `E_convey`, `E_processing`, and `E_irrigation_pump`. No explicit cross-reference links the two.

**Affected:** calculations.md (internal)

**Suggested resolution:** Add a forward reference in the dispatch section noting it is the MVP subset of the full demand formula.

**Owner response:** The 6 components should be updated everywhere... no subsets

---

---

### 1.18 Groundwater Cost Formula Variable Naming

**Disconnect:** policies.md uses explicit per-unit names (`pumping_kwh_per_m3`, `energy_price_per_kwh`). calculations.md uses ambiguous names (`E_pump`, `electricity_price`) that don't specify whether they're per-m3 or total daily values.

**Affected:** calculations.md

**Suggested resolution:** Add unit annotations to calculations.md variables (e.g., `E_pump [kWh/m3]`).

**Owner response:** Agree

---

---

### 1.19 `tds_ppm` Data Flow Unclear Across Documents

**Disconnect:** structure.md defines `tds_ppm` on water treatment. policies.md passes `groundwater_tds_ppm` and `municipal_tds_ppm` in context. calculations.md says `tds_ppm` is "used for reference, not directly in MVP lookup." The relationship between these is undocumented, and `municipal_tds_ppm` has no source in structure.md.

**Affected:** All three documents

**Suggested resolution:** Add `municipal_tds_ppm` to structure.md. Clarify whether `groundwater_tds_ppm` is the static config value or a dynamic measurement. Document the data flow.

**Owner response:** Groundwater tds will be static for the MVP. All files need to properly deal with groundwater, treated groundwater, munipical, and mixed salinty values. The mixed results from adding munipical water to either direct groundwater (if no treatment is available in the community) or the treated groundwater.

---

---

### 1.20 `fresh_packaging_capacity_kg` Contradicts "No Capacity Limit"

**Disconnect:** Food processing context in policies.md provides `fresh_packaging_capacity_kg` as a finite input. The capacity clipping logic (line 356) states fresh "has no practical capacity limit" and excludes fresh from the clipping loop.

**Affected:** policies.md

**Suggested resolution:** Either remove `fresh_packaging_capacity_kg` from context, or add fresh to the clipping loop when finite.

**Owner response:** Update all files to remove any capacity limits for fresh packaging (or set the default extremely high)

---

---

### 1.21 `current_capital_usd` Is Runtime State Listed as Static Config

**Disconnect:** structure.md (line 140) lists `current_capital_usd (tracked capital year-to-year)` alongside static configuration parameters. Section 2 of structure.md defines configurations as "static settings that describe initial conditions."

**Affected:** structure.md

**Suggested resolution:** Annotate as "initial value; updated at runtime" or move to a state management section.

**Owner response:** Move to state management system

---

---

### 1.22 `microgrid` Excluded from Household Policies Without Rationale

**Disconnect:** Both structure.md and policies.md restrict household energy to `renewable_first` or `all_grid`, excluding `microgrid`. No explanation is given for why a community choosing `microgrid` for farms could not also use it for households.

**Affected:** structure.md and policies.md

**Suggested resolution:** Add a note explaining the exclusion (e.g., "microgrid permits unmet demand, which is unacceptable for residential electricity").

**Owner response:** You're right. Household energy should qualify for the microgrid. Update docs as needed to reflect.

---

---

### 1.23 `hold_for_peak` Storage Checks Overlap with Umbrella Rule

**Disconnect:** policies.md (line 472) states "Storage-life expiry and storage overflow are handled by the umbrella rule, not by this policy." Yet the `hold_for_peak` pseudocode (lines 486-497) includes storage capacity checks and a "no storage space: sell everything" branch.

**Affected:** policies.md

**Suggested resolution:** Add a clarifying note explaining that these checks handle the case where the market policy's own "hold" decision would exceed remaining capacity — distinct from the umbrella rule's pre-existing tranche overflow.

**Owner response:** Too unclear to answer. Read the structure file again and determine the right edits to make within the context.

---

---

### 1.24 Food Processing Labeled "TBD" Despite Being Fully Specified

**Disconnect:** calculations.md (line 1245) marks food processing allocation as "Partially TBD" and says policies "need allocation rules." policies.md provides complete rules for all 4 policies.

**Affected:** calculations.md

**Suggested resolution:** Remove the "Partially TBD" status and replace with cross-reference to policies.md Section 3.

**Owner response:** Agree

---

---

### 1.25 Crop Revenue Formula Ignores Processing Split

**Disconnect:** calculations.md "Crop Revenue Calculation" (line 1577) uses a fresh-sale-only formula: `Revenue = yield_kg * price_per_kg * (1 - loss_rate)`. The processing split from food policies is not accounted for in this section.

**Affected:** calculations.md

**Suggested resolution:** Rename to "Fresh Crop Revenue Calculation" and add a unified "Total Crop Revenue" formula combining fresh and processed revenue.

**Owner response:** Agree, all food products need to be calculated based on their weight after yields have been split. Fresh food is gathered at harvest and then designated into different food product channels for processing. Fresh is one product, canned, etc. Ensure the formulas do not double count. 

---

---

### 1.26 `limiting_factor` vs `constraint_hit` Overlap

**Disconnect:** structure.md mentions `limiting_factor` for `conserve_groundwater`. policies.md defines both `constraint_hit` (shared output) and `limiting_factor` (policy-specific). The `limiting_factor` field adds `"ratio_cap"` alongside infrastructure constraint values. The relationship between these two fields is undocumented.

**Affected:** structure.md, policies.md

**Suggested resolution:** Document whether `limiting_factor` is a superset of `constraint_hit` for this policy, or a separate field entirely.

**Owner response:** Unclear problem. Use the structure document to ensure the logic in policies and calculations coincides with it. 

---

---

### 1.27 Minor Disconnects (Batch)


| # | Disconnect                                                              | Location  | Suggested Fix                                        |
| --- | ------------------------------------------------------------------------- | ----------- | ------------------------------------------------------ |
| a | `degradation_rate` in calculations.md not in structure.md PV config     | struct    | Clarify if from parameter file only or add to config |
| b | Battery SOC formula: inconsistent`dt` treatment between sections        | calc      | Note that dispatch uses kWh (dt absorbed)            |
| c | Post-harvest loss rate: narrative says 10-15%, default hardcoded at 10% | calc      | Use single default with range as background          |
| d | `balanced` food fractions duplicated in calculations.md and policies.md | calc      | Replace with cross-reference to policies.md          |
| e | Policy count 23 achieved by different per-domain routes in CLAUDE.md    | CLAUDE.md | Fix: 6 water, 3 market                               |

**Owner response:** Agree

---

---

## 2. Missing Policies

### HIGH PRIORITY

### 2.1 Crop: `combined_deficit_weather`

**Behavior:** Combines deficit irrigation with weather-responsive adjustments. During mid/late season, applies deficit fraction as baseline then adjusts for temperature. During initial/development stages, applies weather adjustments on top of 100% demand.

**Why important:** The existing 3 crop policies (`fixed_schedule`, `deficit_irrigation`, `weather_adaptive`) are orthogonal strategies. In practice, every competent irrigator in a hot arid environment combines both growth-stage awareness and temperature response. Without this, users conclude they must choose one or the other.

**Gap filled:** No existing policy uses both growth stage and temperature simultaneously.

**Owner response:** 

---

---

### 2.2 Energy: `microgrid` (Missing from Code)

**Behavior:** As specified in policies.md Section 5.1: PV, wind, battery, generator only. No grid import, no grid export. The spec defines this policy, but the code does not implement it. `PvFirstBatteryGridDiesel` allows grid import/export, making it `renewable_first`, not `microgrid`.

**Why important:** Off-grid vs. grid-connected is one of the most fundamental infrastructure decisions for a remote community.

**Gap filled:** No code policy disables both grid import and grid export.

**Owner response:** Ignore for now...

---

---

### 2.3 Crop: `water_stress_responsive`

**Behavior:** Adjusts irrigation based on cumulative water stress ratio. When severely stressed (`<0.60`), reduces to 70% (survival mode). When moderately stressed (`0.60-0.85`), boosts +10% (recovery). When well-watered (`>0.85`), standard demand.

**Why important:** `CropPolicyContext` already provides `water_stress_ratio` as an input, but no existing policy uses it. The FAO-33 yield response function (already in calculations) shows timing of water stress matters enormously.

**Gap filled:** No existing policy uses `water_stress_ratio` or responds to actual crop water status.

**Owner response:** Remove water stress completetly from all code and docs. This is not an issue we want to deal with in the MVP. 

---

---

### 2.4 Water: `seasonal_blend`

**Behavior:** Adjusts groundwater vs. municipal mix by season. During peak irrigation months (summer, May-Sep), limits groundwater to e.g. 40% to protect aquifer. During cooler months with lower demand, allows higher groundwater fractions (e.g., 80%).

**Why important:** Seasonal groundwater management is the single most important real-world aquifer sustainability strategy for irrigated agriculture in arid regions. All 6 existing water policies make the same decision logic every day regardless of time of year.

**Gap filled:** No existing water policy varies behavior by season.

**Owner response:** Remove seasonal water draw completely from all code and docs. Not a detail we want to worry about for MVP.

---

---

### 2.5 Energy: `battery_priority`

**Behavior:** Aggressive battery cycling strategy maximizing self-consumption via battery. Lower reserve (10% vs 20%), prioritizes battery discharge over grid import. Key distinction from `renewable_first`: actively optimizes battery utilization, not just buffering.

**Why important:** Battery is the most expensive infrastructure component. Without a policy exploring cycling trade-offs, users cannot explore the trade-off between aggressive cycling (lower grid costs, faster degradation) vs. conservative cycling (longer battery life, more grid dependence).

**Gap filled:** No existing policy optimizes battery dispatch as a primary strategy.

**Owner response:** Ignore... 

---

---

### MEDIUM PRIORITY

### 2.6 Food Processing: `crop_specific`

**Behavior:** Applies different processing splits per crop based on suitability. E.g., cucumbers get 0% dried (92% weight loss makes it uneconomical), potatoes get 30% packaged (well-suited). Uses crop-specific allocation tables.

**Why important:** All 4 existing food processing policies apply the same fractions regardless of crop. The processing_specs data shows dramatically different economics by crop (dried cucumber = 0.28x revenue vs dried potato = 0.77x).

**Gap filled:** No existing policy differentiates processing by crop.

**Owner response:** Add a note in the TODO.md file in root to add a policy that processes food by profitability of each resulting product BY CROP.

---

---

### 2.7 Market: `seasonal`

**Behavior:** Adjusts sell/store based on known seasonal price patterns. Uses historical monthly price averages to identify cheap vs. expensive months per crop. Stores during cheap months, sells during expensive months.

**Why important:** Seasonal price patterns are the most predictable and exploitable market signal available to smallholder farmers. The existing `adaptive` policy responds to recent history but does not incorporate seasonal knowledge.

**Gap filled:** No existing market policy uses seasonal price patterns.

**Owner response:** Update adaptive policy to include seasonal pricing patterns.

---

---

### 2.8 Economic: `debt_first`

**Behavior:** Prioritizes aggressive debt repayment. Directs all cash above 1.5 months reserve toward principal prepayment. Investments blocked until debt is retired. Inventory sold to accelerate repayment.

**Why important:** The financing model includes two loan types (standard at 6%, concessional at 3.5%). None of the 4 existing economic policies explicitly address debt management. "Pay down debt faster or maintain larger reserves?" is one of the most consequential community financial decisions.

**Gap filled:** No existing economic policy addresses debt reduction strategy.

**Owner response:** Let's remove all debt pay down policies throughout for now. Assume loans are paid down at the per month rate.

---

---

### 2.9 Crop: `leaching_schedule`

**Behavior:** Periodically applies extra irrigation water to flush accumulated salts from root zone. Adds 10-15% extra water at configurable intervals during mid-season, plus heavier 25% leaching events between crop cycles.

**Why important:** calculations.md explicitly identifies soil salinity accumulation as "a critical long-range concern." The leaching requirement formula (FAO-29) is documented but no crop policy implements deliberate leaching. For 15-year simulations with BWRO water, salt accumulation without leaching progressively reduces yields.

**Gap filled:** No existing policy addresses soil salinity management.

**Owner response:** The leaching_schedule should apply to all watering policies if it is critical to preventing salt build up. 

---

---

### 2.10 Water: `aquifer_responsive`

**Behavior:** Dynamically adjusts groundwater extraction based on aquifer depletion status. As remaining exploitable volume drops, progressively reduces groundwater fraction (e.g., 90% when >70% remaining, down to 10% when <15% remaining).

**Why important:** calculations.md describes aquifer drawdown as a "critical positive feedback loop." The simulation tracks depletion, but no water policy responds to aquifer state.

**Gap filled:** No existing water policy responds to aquifer depletion. `conserve_groundwater` conserves by price; `quota_enforced` uses a fixed quota — neither responds to actual aquifer health.

**Owner response:** Remove aquifer depletion based water policies completely. The aquifer state should be tracked for resilience purposes, but not used to lower groundwater withdrawal at this point. 

---

---

### 2.11 Market: `product_type_aware`

**Behavior:** Applies different sell/store strategies by product type. Fresh: sell immediately (perishable). Dried/canned: hold strategically using adaptive sigmoid (long shelf life). Packaged: intermediate strategy.

**Why important:** `MarketPolicyContext` provides `product_type` but all 3 existing policies apply the same logic regardless. The entire point of processing food into shelf-stable forms is to decouple selling from harvest timing.

**Gap filled:** No existing market policy differentiates strategy by product type.

**Owner response:** Update hold_for_peak and adaptive policies to apply the logic per product type (but apply across all crops for now). Use blended prices for each product type. Add a note to TODO.md to improve the policy with crop and product specific dynamic selling behavior.

---

---

### LOW PRIORITY

### 2.12 Energy: `net_metering_optimized`

**Behavior:** Dynamically decides between self-consumption and grid export based on relative pricing. When export price > import price, routes renewables to grid and buys grid for own use.

**Gap filled:** Niche but relevant for evolving Egyptian feed-in tariff structures.

**Owner response:** Don't understand the issue here... this is proper arbitrage behavior (which will likely never happen). Feed-in tariffs should really be applied when the community produces more energy than it needs (solar peak in afternoon, wind turbines at night, etc.). This will happen in the summer when the community is not farming as much. 

---

---

### 2.13 Food Processing: `maximize_revenue`

**Behavior:** Allocates harvest to the pathway with highest effective revenue multiplier (`value_add * (1 - weight_loss)`), subject to capacity constraints.

**Gap filled:** No policy optimizes processing by net revenue. Teaches that highest price multiplier (dried 3.50x) isn't always best due to weight loss.

**Owner response:** Ok, implement this.

---

---

### 2.14 Economic: `seasonal_cash_flow`

**Behavior:** Adjusts reserve targets by agricultural calendar. Higher reserves pre-planting (costs spike), lower post-harvest (revenue arrives).

**Gap filled:** Refinement of `balanced` — all 4 existing policies use static reserve targets.

**Owner response:** Don't implement yet.

---

---

### 2.15 Crop: `maturity_based_harvest`

**Behavior:** Adjusts harvest timing based on water stress and market conditions. Early harvest under severe stress, delayed harvest when prices rising.

**Gap filled:** No existing policy addresses harvest timing. Would require expanding `CropDecision` output.

**Owner response:** Not yet. Add to TODO.md file

---

---

## 3. Missing Implementation Details

### CRITICAL (Blocks Implementation)

### 3.1 `min_water_quality` Policy Not Implemented in Code

**Policy:** Water — `min_water_quality` (policies.md Section 2.3)

**What's missing:** The spec defines 6 water policies. Code implements only 5 — `min_water_quality` has no corresponding class. Additionally, `groundwater_tds_ppm` and `municipal_tds_ppm` are not in the implemented `WaterPolicyContext` dataclass.

**Resolution:** Implement `MinWaterQuality(BaseWaterPolicy)` with `target_tds_ppm` parameter. Add TDS fields to the context dataclass.

**Owner response:** Agree

---

---

### 3.2 Food Processing Capacity Clipping Not Implemented

**Policy:** Food Processing — all 4 policies (policies.md Section 3, "Shared logic: capacity clipping")

**What's missing:** The spec defines a shared capacity clipping algorithm that runs AFTER every policy computes target fractions. If allocated kg for packaged/canned/dried exceeds daily capacity, excess redistributes to fresh. None of the 4 implemented policies perform this clipping despite capacities being in the context.

**Resolution:** Implement as a method on `BaseFoodPolicy` or as a post-processing step. The pseudocode is directly implementable.

**Owner response:** Agree

---

---

### 3.3 Umbrella Rule (FIFO Tranche Tracking) Insufficiently Specified

**Policy:** Food Processing / Market integration (policies.md Section 3)

**What's missing:** The umbrella rule describes tranche tracking, expiry, and overflow conceptually but provides no data structure definition, no pseudocode function, and no clear integration point. Specifically:

- What does a `StorageTranche` dataclass contain?
- Where is the tranche list stored? (FarmState? Separate manager?)
- How does FIFO work across multiple product types with different shelf lives?
- Are forced sales at current market price or a discount?

**Resolution:** Add a `StorageTranche` dataclass definition, a `check_forced_sales()` pseudocode function, and specify forced sales use current market prices.

**Owner response:** Agree

---

---

### 3.4 Energy Policies Not Consumed by `dispatch_energy()`

**Policy:** Energy — all 3 policies

**What's missing:** calculations.md explicitly states "Energy policy objects are not consumed by the dispatch function." The dispatch function uses a hardcoded merit order. Energy policies exist but have zero effect on simulation behavior.

**Resolution:** Define the integration contract: simulation loop calls `policy.allocate_energy(ctx)` then passes `EnergyAllocation` flags to `dispatch_energy()`.

**Owner response:** Agree. This must be fixed so energy policies are correctly implemented. 

---

---

### 3.5 Energy Policy Spec/Code Mismatch

**Policy:** Energy — all 3

**What's missing:** Spec defines `microgrid`, `renewable_first`, `all_grid`. Code implements `PvFirstBatteryGridDiesel` (mapped to "all_renewable"/"hybrid"), `GridFirst` (mapped to "all_grid"), `CheapestEnergy` (mapped to "cost_minimize"). `microgrid` has no code. Output fields also differ significantly between spec and code (e.g., spec has `grid_import`/`grid_export` as separate bools; code has `use_grid` + `allow_grid_export`).

**Resolution:** Reconcile names, fields, and registry. Implement `microgrid` or remove from spec.

**Owner response:** Agree

---

---

### 3.6 Economic↔Market Policy Interaction Undefined

**Policy:** Economic — `sell_inventory` output (policies.md Section 7)

**What's missing:** When `sell_inventory = true`, what happens? Economic policy says "sell stored inventory." Market policy says it "entirely determines WHEN food is sold." These conflict. Does `sell_inventory` override market policy? Set it to `sell_all_immediately`? Trigger forced sales?

**Resolution:** Define the integration: "When `sell_inventory = true`, simulation overrides market policy for that month, setting `sell_fraction = 1.0` for all stored inventory."

**Owner response:** Agree

---

---

### MAJOR (Could Cause Bugs)

### 3.7 Policy Name Registry Mismatches

**Policy:** Water, Energy, Market (cross-cutting)

**What's missing:** Spec policy names differ from code registry keys:

- Water: spec `max_groundwater` / code `always_groundwater`
- Water: spec `max_municipal` / code `always_municipal`
- Energy: spec `microgrid` / code missing entirely
- Energy: spec `renewable_first` / code `all_renewable` or `hybrid`
- Market: spec `sell_all_immediately` / code `sell_immediately`

A developer writing YAML scenarios from the spec would get lookup errors.

**Resolution:** Update code registries to accept spec names as primary keys with backward-compatible aliases.

**Owner response:** Agree, but we don't need backward compatability

---

---

### 3.8 Water Policy Registry Missing

**Policy:** Water — all 6

**What's missing:** All other policy modules have a registry dict and `get_*_policy(name, **kwargs)` factory function. Water policies do not, despite the spec's "Common patterns" section stating "Each domain provides a factory function."

**Resolution:** Add `WATER_POLICIES = {...}` and `get_water_policy(name, **kwargs)`.

**Owner response:** Agree

---

---

### 3.9 `decision_reason` Missing from `ProcessingAllocation`

**Policy:** Food Processing — all 4

**What's missing:** Spec defines `decision_reason` as a required output field. Code's `ProcessingAllocation` has `policy_name` but no `decision_reason`. None of the 4 implementations return a reason string, breaking the universal contract.

**Resolution:** Add `decision_reason: str = ""` to `ProcessingAllocation`. Populate in each policy.

**Owner response:** Agree

---

---

### 3.10 Reference Farmgate Prices Hardcoded

**Policy:** Food Processing — `market_responsive` (policies.md Section 3.4)

**What's missing:** Spec says "Reference farmgate prices are loaded from crop price data files." Code hardcodes them as `REFERENCE_PRICES = {"tomato": 0.30, ...}`. The spec explicitly says "Example values for illustration only — actual values come from data files."

**Resolution:** Load from data files at instantiation or pass through context.

**Owner response:** Agree

---

---

### 3.11 `avg_price_per_kg` Averaging Window Unspecified

**Policy:** Market — `hold_for_peak`, `adaptive` (policies.md Section 4)

**What's missing:** Context includes `avg_price_per_kg` described as "over recent history." No definition of time window (30-day rolling? 90-day? Year-to-date?). Different windows produce materially different sell/store decisions.

**Resolution:** Specify 90-day rolling average as default, configurable via YAML.

**Owner response:** Agree

---

---

### 3.12 Growth Stage Mapping Not Defined

**Policy:** Crop — all 3 (policies.md Section 6)

**What's missing:** Policies use `growth_stage` values ("initial", "development", "mid_season", "late_season") but no document defines the mapping from `days_since_planting` to stage. calculations.md says "Duration: Crop and climate-specific (from parameter files)" but provides no formula or lookup.

**Resolution:** Add a formula or specify that growth stage is pre-computed in Layer 1 and passed through.

**Owner response:** Research and update data files to include missing data as needed for policys and simulations.

---

---

### 3.13 Crop Policy / Water Policy Demand Boundary Ambiguous

**Policy:** Crop → Water handoff

**What's missing:** Context includes `available_water_m3` but no policy uses it. Spec doesn't clarify whether crop policy clips demand to available water, or water policy handles shortfall. Execution order says crop runs first (step 1), water second (step 2).

**Resolution:** Clarify: "Crop policy outputs a demand REQUEST. Water policy and simulation loop handle allocation against supply."

**Owner response:** Agree

---

---

### 3.14 Economic Policy Call Timing Unspecified

**Policy:** Economic — all 4 (policies.md Section 7)

**What's missing:** "Called monthly or at year boundaries" — but when exactly within the daily loop? Day 1 of each month? End of month? Using which period's revenue/costs?

**Resolution:** Specify: "Called on first simulation day of each month, using previous month's aggregated revenue and costs."

**Owner response:** Agree

---

---

### 3.15 `months_of_reserves` Computation Undefined

**Policy:** Economic — all 4

**What's missing:** `months_of_reserves` is a pre-computed context input. No specification of who computes it or what averaging period for `avg_monthly_opex` (trailing 12 months? Year-to-date? Lifetime?).

**Resolution:** Specify trailing 12 months, computed by simulation loop before calling economic policy.

**Owner response:** Agree

---

---

### 3.16 Zero-Demand Edge Cases Unspecified

**Policy:** Water (all), Food Processing (all)

**What's missing:** No policy pseudocode addresses `demand_m3 = 0` (water) or `harvest_yield_kg = 0` (food). Capacity clipping divides by `harvest_yield_kg`, which would crash on zero. Cost calculations on zero volume may produce division-by-zero.

**Resolution:** Add early return guards for zero inputs.

**Owner response:** Agree

---

---

### 3.17 `hold_for_peak` Code Handles Spoilage, Contradicting Umbrella Rule

**Policy:** Market — `hold_for_peak`

**What's missing in spec clarity:** Spec says umbrella rule handles spoilage BEFORE market policy runs. But the code implementation checks `days_in_storage >= storage_life_days - 1` and forces a sale, duplicating the umbrella rule's job.

**Resolution:** Remove spoilage check from `HoldForPeak.decide()`. Umbrella rule should handle all forced sales.

**Owner response:** Agree

---

---

### 3.18 Processing Capacity Pipeline Undefined

**Policy:** Food Processing — context assembly

**What's missing:** Context receives `drying_capacity_kg`, `canning_capacity_kg`, etc. as floats. calculations.md defines processing capacity formula, but there's no specification of who performs this calculation, when, or whether equipment availability (90%) is applied.

**Resolution:** Specify that processing capacities are calculated once at scenario load time in `calculations.py`.

**Owner response:** Agree

---

---

### 3.19 Household Policy Integration Unspecified

**Policy:** Water and Energy — household scope

**What's missing:** The spec defines household policies as restricted subsets, but no specification for: how household demand is calculated/split, how it enters the dispatch function, whether household policies are separate instances or shared, or YAML schema for `household_policies`.

**Resolution:** Add a "Household Policy Integration" subsection to policies.md.

**Owner response:** Agree, and fill out as best you can

---

---

### 3.20 Municipal Water Price Resolution Logic Unspecified

**Policy:** Water — all policies that compare groundwater vs municipal cost

**What's missing:** Spec says "resolved upstream based on consumer type." No pseudocode for this resolution. Does it call `get_marginal_tier_price()`? For agricultural use, always flat rate? For domestic, always tiered?

**Resolution:** Add "Price Resolution" section: agricultural uses flat rate; domestic uses tiered with monthly tracking.

**Owner response:** Agree, and fill out as best you can

---

---

### 3.21 `investment_allowed` Has No Consumer

**Policy:** Economic — all 4

**What's missing:** Output includes `investment_allowed: bool` but no investment mechanism exists in the simulation. What investments are gated? Equipment upgrades? Additional PV? How much do they cost?

**Resolution:** Mark as reserved for future Phase 7 equipment upgrade decisions, or define the mechanism.

**Owner response:** Assume opex covers all upgrades, repairs, etc. 

---

---

### MINOR (Inconvenience / Naming)

### 3.22 Minor Implementation Gaps (Batch)


| # | Gap                                                                         | Policy        | Fix                                                                 |
| --- | ----------------------------------------------------------------------------- | --------------- | --------------------------------------------------------------------- |
| a | `weather_adaptive` temperature thresholds not configurable via YAML         | Crop          | Add constructor parameters with defaults                            |
| b | `soil_moisture_estimate` field in code but not in spec                      | Crop          | Remove or document as reserved                                      |
| c | `price_trend` field in market code but not in spec                          | Market        | Add to spec or remove from code                                     |
| d | `sell_all_immediately` doesn't explicitly set `target_price_per_kg = 0`     | Market        | Add to pseudocode                                                   |
| e | `storage_capacity_kg` ambiguous — remaining or total?                      | Market        | Rename to`available_storage_capacity_kg`                            |
| f | `configured_minimum` in `risk_averse` pseudocode undefined                  | Economic      | Replace with`min_cash_months`                                       |
| g | Sigmoid function referenced but never formally defined                      | Market shared | Define in Common Patterns:`min + (max-min) / (1 + exp(-k*(x-mid)))` |
| h | `policy_name` field in all code outputs but not in spec outputs             | All           | Add to spec's common output pattern                                 |
| i | Spoilage rates CSV schema not specified                                     | Food/Market   | Document:`crop_name, product_type, shelf_life_days`                 |
| j | `available_energy_kwh` in water code contradicts "operational independence" | Water         | Decide: remove energy constraint or update spec                     |
| k | No error handling specification for any policy                              | All           | Add "Error Handling" to common patterns                             |
| l | No test vectors provided for boundary conditions                            | All           | Add 3-5 input/output pairs per policy                               |
| m | Community-override YAML schema not specified                                | All           | Define resolution logic                                             |

**Owner response:** Resolve as you see best

---

---

## 4. Missing Formulas and Equations

### CRITICAL

### 4.1 Food Processing Energy → Energy Dispatch Not Connected

**What's missing:** A formula to compute daily `E_processing(t)` from food policy output and integrate it into `dispatch_energy()`. calculations.md lists it as a demand component and provides kWh/kg ranges, but no daily aggregation formula links actual processing throughput to the energy dispatch. Processing 1,000 kg of tomato could add 500-2,000 kWh of unseen demand.

**Suggested formula:**

```
E_processing(t) = Σ (throughput_kg(t, pathway) * energy_per_kg(pathway))
```

**Owner response:** Agree

---

---

### 4.2 Grid Electricity Export Price Not Defined

**What's missing:** The `Grid_export_revenue` and `Blended_cost` formulas reference `export_price(t)`, but there is no configuration parameter, data source, or formula for determining this price. The `all_grid` policy specifically sells all renewable output to the grid.

**Suggested formula:**

```
export_price_per_kwh = grid_import_price * net_metering_ratio
# net_metering_ratio configurable, default 0.70 (Egypt's evolving policy)
```

**Owner response:** Agree

---

---

### 4.3 Per-Farm Cost Allocation Formula Missing

**What's missing:** The per-farm net income formula references `allocated_opex_farm_i` but provides no allocation method. Shared infrastructure costs must be split across 20 farms. No formula = no per-farm economics, no Gini coefficient, no worst-case farmer outcome.

**Suggested options:**

```
A) Equal: allocated_opex_i = Total_shared_opex / num_farms
B) Area-proportional: allocated_opex_i = Total_shared_opex * (farm_area_i / total_area)
C) Usage-proportional: allocated_opex_i = Total_shared * (farm_water_use_i / total_water_use)
```

**Owner response:** Provide options for all three -- this is a configuration in the community setting (update all files as needed)

---

---

### HIGH

### 4.4 Fertilizer, Seed, and Chemical Input Costs (TBD)

**What's missing:** The entire `Input_cost_ha` calculation is marked TBD. Agricultural input costs typically represent 15-30% of operating expenses. The sensitivity analysis already tests fertilizer perturbation but has no base case cost to perturb.

**Suggested formula:**

```
Input_cost_farm_i = Σ (fert_usd/ha + seed_usd/ha + chem_usd/ha) * crop_area_ha
# Typical: Tomato $2,000-3,500/ha, Potato $1,500-2,500/ha, Onion $800-1,200/ha
```

**Owner response:** Agree, but check data files first and add csv files as needed to parameterize and expose thse values

---

---

### 4.5 Food Storage Cost Missing

**What's missing:** Market policies that favor holding inventory appear cost-free. No formula for the real cost of storing food (facility depreciation, energy, pest control). calculations.md (line 1597) explicitly states "For MVP: No inventory or storage costs."

**Suggested formula:**

```
Storage_cost_daily = Σ (tranche_kg * cost_per_kg_per_day(product_type))
# fresh: $0.005/kg/day, packaged: $0.003, canned: $0.001, dried: $0.001
```

**Owner response:** Agree... but add csv files for each cost parameter as needed (research best guesses)

---

---

### 4.6 Currency Conversion (USD/EGP) Missing

**What's missing:** Configuration allows `currency: [USD, EGP, EUR]`. Tiered water pricing example uses EGP. Grid electricity data may be in EGP piasters. No conversion function is specified. If arithmetic mixes USD and EGP without conversion, results are wrong by ~50x.

**Suggested formula:**

```
Value_USD = Value_EGP / exchange_rate_EGP_per_USD
# For constant-year terms: fixed base-year exchange rate
```

**Owner response:** Agree... have an agent look through all specs and code to ensure this is handled correctly. 

---

---

### 4.7 Drip Irrigation Pressurization Energy

**What's missing:** Total Energy Demand lists `E_irrigation_pump(t)` but notes it is "not separately tracked." For 500 ha at ~2,500 m3/day peak, pressurization adds 125-375 kWh/day — not trivial.

**Suggested formula:**

```
E_irrigation [kWh/m3] = (P_bar * 100,000) / (eta * 3,600,000)
# At 1.5 bar, eta=0.75: ~0.056 kWh/m3
```

**Owner response:** Agree

---

---

### 4.8 `percent_planted` Parameter Has No Calculation

**What's missing:** structure.md defines `percent_planted` per crop per farm, but calculations.md never uses it. Irrigation demand and yield calculations should account for partial planting.

**Suggested formula:**

```
effective_area_ha = plantable_area_ha * area_fraction * percent_planted
# Use this everywhere that currently uses plantable_area_ha * area_fraction
```

**Owner response:** Agree

---

---

### 4.9 Transport Cost Formula Missing

**What's missing:** structure.md lists transport as a labor activity. Post-harvest losses include "handling, transport." No transport cost formula exists. For a remote Sinai community, transport to market can be 5-15% of operating expense.

**Suggested formula:**

```
# Simplified flat rate:
Transport_cost_yr = total_sold_kg * transport_cost_per_kg
# transport_cost_per_kg: $0.02-0.05/kg (Sinai to regional market)
```

**Owner response:** Agree, add csv file for transport costs and research as best as possible

---

---

### 4.10 `gw_maintenance_per_m3` Derivation Undocumented

**What's missing:** Every water policy uses `gw_maintenance_per_m3` for cost comparison. Neither calculations.md nor any other document shows how this value is derived from the financing model or equipment data.

**Suggested formula:**

```
gw_maintenance_per_m3 = annual_om_cost_bwro / (capacity_m3_day * 365 * utilization_factor)
# utilization_factor ~0.70
```

**Owner response:** There should be a single opex cost per m3 for ground water extraction (from well to treatment). Treatment and irrigation also need opex costs per m3. Add csv files as needed and research values. 

---

---

### MEDIUM

### 4.11 Blended Water Cost Metric

**What's missing:** Plots and tables reference "Blended water cost [$/m3]" but calculations.md only has the daily formula, not the aggregated metric.

**Suggested formula:**

```
Blended_water_cost = (total_gw_cost_yr + total_muni_cost_yr) / total_water_yr
```

**Owner response:** Agree

---

---

### 4.12 LCOE Intermediate for Blended Energy Cost

**What's missing:** Blended electricity cost references `LCOE_renewable` but doesn't show how to compute `annual_infrastructure_cost_pv/wind/battery` from the financing model.

**Suggested formula:**

```
LCOE_renewable = (Annual_cost(pv) + Annual_cost(wind) + Annual_cost(battery)) / E_renewable_yr
```

**Owner response:** Agree

---

---

### 4.13 Processing Materials Cost Per Kg

**What's missing:** Non-energy operating costs of processing (packaging materials, chemicals, cans). Only energy is documented.

**Suggested formula:**

```
# fresh: $0.02-0.05/kg, packaged: $0.05-0.10/kg, canned: $0.10-0.20/kg, dried: $0.03-0.08/kg
```

**Owner response:** Agree, research for each and add csv files (if not already there)

---

---

### 4.14 Water Storage CAPEX/OPEX by Type

**What's missing:** Storage capacity and type are configured, but no cost formula connects them to the financing model.

**Suggested formula:**

```
capex_per_m3: reservoir $15-30, tank $50-100, pond $5-15
annual_om: 1-3% of CAPEX
```

**Owner response:** Agree, research for each and add csv files (if not already there)

---

---

### 4.15 Household Water Demand

**What's missing:** Total energy demand references household demand from `calculate_household_demand()`, but calculations.md has no section on household water demand.

**Suggested formula:**

```
Household_water_m3_day = population * per_capita_L_day / 1000
# per_capita: 100-200 L/day (hot arid)
```

**Owner response:** Agree, research for each and add csv files (if not already there)

---

---

### 4.16 PV Temperature Derating Not in Dispatch Formula

**What's missing:** Temperature derating is documented (12-16% penalty on peak Sinai summer days) with a full formula, but the Energy Dispatch section's PV calculation omits `temp_derate(t)`.

**Note:** If precomputed PV data already includes temperature effects, this is handled at Layer 1 and the omission is correct — but this should be clarified.

**Owner response:** Ignore, handled.

---

---

### 4.17 Monte Carlo Resilience Metrics Not Yet Computed

**What's missing (formulas exist, no implementation):**

- Probability of crop failure
- Median years to insolvency
- Worst-case farmer outcome
- Income inequality (Gini coefficient)
- Maximum drawdown

**Owner response:** All of the above.

---

---

### LOW

### 4.18 Low Priority Formula Gaps (Batch)


| # | Missing Calculation                 | Priority | Notes                                                         |
| --- | ------------------------------------- | ---------- | --------------------------------------------------------------- |
| a | Multiple planting dates interaction | Low      | How do staggered plantings share area and overlap irrigation? |
| b | Breakeven thresholds (sensitivity)  | Low      | Binary search algorithm needed                                |
| c | Revenue concentration price CV      | Low      | `std(price) / mean(price)` per crop                           |
| d | Scenario stress tests construction  | Low      | Drought, price spike, equipment failure parameters            |
| e | Battery self-discharge integration  | Low      | Deferred for MVP                                              |
| f | Community vs external labor ratio   | Low      | Needs community available labor supply data                   |

**Owner response:** Add detailed explanation to TODO.md file.

---

---

## 5. Cross-Cutting Issues

These issues span multiple categories above and require coordinated resolution across documents.

### 5.1 `calculations.md` Appears Less Recently Updated Than `policies.md` and `structure.md`

Many disconnects (1.1, 1.2, 1.3, 1.10, 1.11, 1.24, 1.25) stem from calculations.md referencing older implementation-level names, simpler schemas, or stale TBD statuses that have been resolved in the other two documents. A systematic pass through calculations.md to align it with the current spec would resolve most Section 1 issues.

**Owner response:**  Agree, start with that. Naming conventions should start from structure file and then be used to match all other files. Anything not present in the structure file (or part of the conceptual unpacking of a category or parameter in the structure file) should be flagged for the user.

---

---

### 5.2 Pricing Resolution Pipeline Undocumented

The dual agricultural/domestic pricing regime (structure.md) → price resolution by consumer type (policies.md) → actual cost calculations (calculations.md) chain is described piecemeal and never assembled end-to-end. This affects water policies, energy policies, and household policies. A "Price Resolution" section documenting the complete pipeline would address disconnects 1.5, 1.6, 3.20, and 4.6.

**Owner response:** Yes, write this out in a new file that outlines how calculations should proceed and the order of operations for the simulation. Give it is proper name and add specifications for all critical decision flows and calculation orders. If anything is missing or unclear as a result, flag for the user. Do not assume the code has the proper flow or structrue. It is a first pass and may be incorrect or overly complicated. 

---

---

### 5.3 Food Processing → Market → Revenue Chain Fragmented

The flow from harvest → food policy split → weight loss → processed output → storage → market policy → forced sales → revenue is described across three documents and seven sections. No single place shows the end-to-end chain. This affects disconnects 1.11, 1.24, 1.25, and implementation gaps 3.3, 3.6, 3.17, 3.18.

**Owner response:** See 5.2 response and implement here... 

---

---

### 5.4 Energy Policy Integration Is the Largest Single Gap

The energy policy domain has the most issues across all 4 analysis dimensions: name mismatches (1.3), missing code implementation (2.2, 3.4, 3.5), dispatch not consuming policy flags (1.13), processing energy not connected (4.1), output field differences (1.14). Resolving the energy policy integration end-to-end would address ~8 individual issues.

**Owner response:** See 5.2 response and implement here... 

---

---

### 5.5 Error Handling and Edge Cases Are Systematically Missing

No policy specifies behavior for zero/negative/NaN inputs, division by zero, or invalid parameter combinations. This is a cross-cutting gap (3.16, 3.22k) that should be addressed with a single "Error Handling" section in the common patterns of policies.md.

**Owner response:** Add note to the new simulation behavior spec file that addresses how this should be halnded. 

---

---

*End of review.*
