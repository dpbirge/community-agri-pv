# Architecture Specification Cross-Document Review

**Date:** 2026-02-12
**Scope:** structure.md, policies.md, simulation_flow.md (calculations.md excluded by design)
**Method:** Four parallel deep-analysis agents examining parameter consistency, policy coverage, simulation flow completeness, and implementability
**Canonical source of truth:** structure.md

---

## How to Read This Review

Issues are organized into three tiers: CRITICAL (blocks implementation or produces silently wrong results), IMPORTANT (slows a developer significantly or causes confusion), and MINOR (cosmetic or easily resolved with reasonable assumptions). Within each tier, issues are ordered by impact.

Each issue includes enough context that you should not need to re-read the source files.

---

## CRITICAL Issues

### C1. Post-Harvest Loss vs Processing Weight Loss Contradiction

**The problem:** Two separate mechanisms exist for applying losses to harvested produce, and they contradict each other for the fresh pathway.

- `simulation_flow.md` Section 4.5 applies weight loss per processing pathway from `processing_specs-toy.csv`. Fresh tomato weight loss = 0%, dried = 88%.
- `simulation_flow.md` Section 4.2 says "Post-harvest handling losses are applied per pathway, NOT as a separate pre-processing step" to prevent double-counting.
- But calculations.md defines a separate `loss_rate = 0.10` for fresh and `0.04` for processed, applied to the revenue formula.

If a developer follows simulation_flow.md (0% fresh loss from processing specs), fresh produce has no losses at all. If they follow calculations.md (10% fresh loss), revenue differs by 10%. Both cannot be correct.

**Suggested fix:** Decide one mechanism. The cleanest approach: set fresh weight_loss to 10% in `processing_specs-toy.csv` and remove the separate post-harvest loss rate from calculations.md. This keeps all loss application in one place (the processing pipeline).

> **Owner response:**
>
> ___

---

### C2. No Complete State Dataclass Definitions

**The problem:** The simulation references `SimulationState`, `FarmState`, `CropState`, `AquiferState`, `EnergyState`, `EconomicState`, `DailyWaterRecord`, `DailyEnergyRecord`, `DispatchResult`, and `YearlyFarmMetrics` -- but none of these are formally defined with field names, types, and initial values. A developer must reverse-engineer the fields from scattered references across three documents.

For example, `FarmState` would need (inferred): farm_id, name, cash_reserves_usd, current_capital_usd, crop_states list, storage_inventory list (StorageTranche), sell_inventory_flag, cumulative_gw_year_m3, cumulative_gw_month_m3, water_storage_m3, plus daily/monthly/yearly record lists. But nowhere is this written down.

`StorageTranche` is the one exception -- it IS defined in simulation_flow.md Section 4.7.

**Suggested fix:** Create a `state.md` or a new section in structure.md that formally defines every state dataclass with fields, types, initial values, and update points.

> **Owner response:**
>
> ___

---

### C3. `avg_price_per_kg` Computation Undefined

**The problem:** Both the `adaptive` and `hold_for_peak` market policies require `avg_price_per_kg` (policies.md line 457), described only as "Average price for this crop+product_type over recent history." No document specifies:

- Window length (30 days? 90 days? rolling year? since simulation start?)
- Source (historical price data file or observed simulation-day prices?)
- Method (simple mean? exponentially weighted?)

A 30-day window vs. a 365-day window produces materially different sell_fraction outputs from the sigmoid, directly affecting farm revenue. On Day 1 of the simulation, there is no simulation price history at all.

**Suggested fix:** Define explicitly. Recommended: use a trailing 90-day rolling mean from the historical price data file (which extends before the simulation start date), ensuring Day 1 has a valid value.

> **Owner response:**
>
> ___

---

### C4. `reference_price` for market_responsive Food Policy Undefined

**The problem:** The `market_responsive` food processing policy (policies.md Section 3.4) compares `fresh_price_per_kg` against `reference_price`, which is described as "lookup crop reference price from data file" with example values. But:

- The `reference_price` is NOT listed as a field in the `FoodProcessingContext` input table
- No document specifies which column in the price CSV contains the reference price
- It is unclear whether this is a static value (e.g., long-term mean) or a dynamic value

A developer must decide both the data source and the mechanism (context field vs. direct file lookup), and the choice affects when the policy switches behavior.

**Suggested fix:** Either (a) add `reference_price_per_kg` to the FoodProcessingContext and compute it as the mean of the full historical price series for each crop, or (b) define it as a policy parameter set at instantiation from a reference data file.

> **Owner response:**
>
> ___

---

### ~~C5. Price Data CSV Schemas Not Specified~~ PARTIALLY RESOLVED

~~**The problem:** The simulation loads prices from files in `data/prices/crops/`, `data/prices/processed/`, `data/prices/electricity/`, `data/prices/water/`, and `data/prices/diesel/`. No document specifies column schemas, date formats, or currency units for any of these files. A developer cannot write data loading code without knowing columns like: is it `date, price_usd_per_kg`? Or `date, crop_name, product_type, price`?~~

~~The data registry (`data_registry.yaml`) lists file paths but not schemas.~~

~~**Suggested fix:** Add a data specification document (e.g., `data.md` in docs/arch/) or add column schemas to the data registry comments. At minimum, document columns and units for each file category.~~

> **Resolution (2026-02-12):** `docs/arch/data.md` v2.0 now serves as the data specification document. It includes:
>
> - Crop price CSV format example with explicit column schema (`date, usd_per_kg, season, market_condition`)
> - Format examples for 5 other file categories (weather, PV power, irrigation demand, crop coefficients, equipment failure rates)
> - Metadata standards requiring every CSV to embed SOURCE, UNITS, LOGIC, DEPENDENCIES in header comments
> - Registry key mappings for all price categories
> - "Data Requirements by Simulation Subsystem" section tracing files to simulation steps
>
> **Remaining gap:** Explicit column schemas for processed product prices, electricity prices, water prices, and diesel prices are not yet provided (only crop prices have an example). These follow a similar pattern but should be documented individually.

---

### C6. Crop Growth Stage Determination Algorithm Missing

**The problem:** Every simulation day must determine the current `growth_stage` ("initial", "development", "mid_season", "late_season") for each active crop. The crop policy context requires it. Calculations.md lists the four stages and says durations are "crop and climate-specific (from parameter files)." But no document provides the algorithm for mapping `days_since_planting` to a growth stage using cumulative duration thresholds.

For example: if tomato has stage durations [30, 40, 50, 30] days, a developer must figure out that day 71 maps to "mid_season" (30+40=70, so day 71 is 1 day into mid_season). While conceptually simple, this is a key algorithm that connects the crop parameter data to the policy system.

**Suggested fix:** Add pseudocode in simulation_flow.md Step 0 or Step 1 showing how to map days_since_planting to growth_stage using cumulative stage durations from the crop parameters file.

> **Owner response:**
>
> ___

---

### C7. No Acceptance Criteria or Worked Examples

**The problem:** No specification document provides expected output values for a test scenario. A developer cannot verify their implementation is correct. The state consistency checks (simulation_flow.md Section 9.5) verify internal balance (water in = water out), but not correctness of outputs.

Without a worked example like "1 farm, 1 crop (tomato), 1 year, `all_fresh` policy, `cheapest_source` water policy: expect approximately X kg yield, Y USD revenue, Z m3 groundwater", a developer has no way to validate their build.

**Suggested fix:** Add an appendix with one minimal scenario and expected outputs at each major step. This is the single highest-impact addition for implementability.

> **Owner response:**
>
> ___

---

### C8. Labor System Entirely Missing from Simulation Flow

**The problem:** structure.md Section 4 defines 5 labor metrics (total employment, employment by activity, peak demand, community vs external ratio, jobs supported). overview.md Section 3 defines labor profiles, hourly rates, and activity categories. The data registry includes `labor_requirements-toy.csv` and `labor_wages-toy.csv`.

But simulation_flow.md never computes labor. There is no step that tracks labor hours, assigns labor costs, or computes labor metrics. Step 7 (Daily Accounting) aggregates "labor" as a cost category but never explains where the labor hours or costs come from.

A developer following only the simulation flow would produce a simulation with zero labor tracking and zero labor costs.

**Suggested fix:** Add a labor tracking sub-step (e.g., after Step 4 or within Step 7) that computes daily labor hours by activity profile from the labor requirements data, applies wage rates, and accumulates for metric computation.

> **Owner response:**
>
> ___

---

## IMPORTANT Issues

### I1. Settings YAML Missing Multiple Required Fields

**The problem:** The current `settings.yaml` is missing several fields and sections that the spec documents require:

| Missing from YAML | Required by |
|---|---|
| `market` policy per farm | structure.md (market policy per farm) |
| `crop` policy per farm | structure.md (crop policy per farm) |
| `household_policies` section | structure.md (household water + energy policies) |
| `municipal_tds_ppm` | structure.md water treatment params |
| `current_capital_usd` per farm | structure.md farm configurations |
| `cost_allocation_method` | simulation_flow.md Section 6 |
| `net_metering_ratio` | simulation_flow.md Section 3.5 |
| `exchange_rate_egp_per_usd` | simulation_flow.md Section 3.1 |

Additionally, three existing fields use non-canonical names:

| YAML field | Canonical name (structure.md) |
|---|---|
| `water_treatment.tds_ppm` | `groundwater_tds_ppm` |
| `farms[].area_ha` | `plantable_area_ha` |
| `farms[].policies.food` | Should be `food_processing` (or standardize the short name) |

And the YAML has `total_area_ha` which is NOT in structure.md.

**Suggested fix:** Update settings.yaml to match structure.md parameter names. Add missing sections/fields. Note: the YAML will need to expand as implementation proceeds, but the canonical names should be used from the start.

> **Owner response:**
>
> ___

---

### I2. simulation_flow.md Introduces Parameters Not in structure.md

**The problem:** simulation_flow.md introduces several new parameters that are not ratified in the canonical structure.md:

- `E_irrigation_pump` and `irrigation_pressure_kwh_per_m3` (Section 5.5) -- irrigation pressurization energy
- `E_other` (Section 5.5) -- community buildings and industrial energy
- `net_metering_ratio` (Section 3.5) -- grid export pricing ratio
- `cost_allocation_method` (Section 6.1) -- equal/area/usage-proportional
- `exchange_rate_egp_per_usd` (Section 3.1) -- currency conversion
- Tiered domestic water pricing with `wastewater_surcharge_pct` (Section 3.3) -- structure.md domestic subsidized pricing is flat rate only
- `storage_cost_per_kg_per_day` (Section 4.10) -- no CSV file exists for this data

These represent design decisions documented in the flow spec that haven't been added to the canonical parameter spec.

**Suggested fix:** Review each parameter. If approved, add to structure.md. If not yet needed, mark as "future" in simulation_flow.md. The domestic water tiered pricing is the biggest divergence -- structure.md says flat `price_usd_per_m3`, simulation_flow.md says progressive tiered brackets with monthly tracking.

> **Owner response:**
>
> ___

---

### I3. Multiple Planting Dates: Area Split and Overlap Unspecified

**The problem:** structure.md allows `planting_dates` as a list (e.g., `["02-15", "11-01"]`). The settings YAML uses this for all 5 crops. But no document specifies:

- How area is split across plantings (50/50? first planting gets full area, second replants?)
- Whether harvests can overlap (a November planting might not harvest before February's next planting)
- How water tracking works for concurrent growth cycles of the same crop on the same farm

simulation_flow.md Section 10.10 explicitly flags this as unspecified.

**Suggested fix:** Define the semantics. Simplest approach: each planting gets the full `area_fraction`, they are independent growth cycles, and water/yield are tracked separately per planting cycle. Document this in structure.md's farm configuration section.

> **Owner response:**
>
> ___

---

### I4. Financial Performance Metrics Have No Computation Trigger

**The problem:** structure.md Section 4 defines NPV, ROI, payback period, and debt-to-revenue ratio as key financial metrics. These are primary outputs for evaluating infrastructure investment decisions. But simulation_flow.md never specifies when or how they are computed. They don't appear in the yearly boundary operations (Section 7.2) or anywhere in the daily loop.

Similarly, unit cost metrics ($/m3 water, $/kWh electricity, $/kg-yield) are listed in structure.md but have no computation point in the flow.

**Suggested fix:** Add a computation step to the yearly boundary operations (Section 7.2) that explicitly computes all metrics from structure.md Section 4 that aren't already covered by daily accumulation. Add a "final metrics" step at simulation end for NPV and payback period.

> **Owner response:**
>
> ___

---

### I5. Farm Insolvency Has No Operational Consequences

**The problem:** Step 7 updates farm cash as `cash += revenue - costs`. The resilience metrics reference "probability of insolvency" as "cash reserves fall below zero." But no document specifies what happens operationally when cash goes negative:

- Can farms continue operating at negative cash? (unlimited credit?)
- Do they stop purchasing municipal water? Processing food?
- Does the collective pooling mechanism intervene?
- Is there a bankruptcy threshold?

A developer must decide, and the choice materially affects simulation outcomes and the meaning of the insolvency metric.

**Suggested fix:** Specify the operational consequences. Simplest MVP approach: farms can operate at negative cash (treated as debt to the community), insolvency is purely a reporting metric. Document this explicitly.

> **Owner response:**
>
> ___

---

### I6. Water Storage Dynamics Not Integrated into Daily Loop

**The problem:** The crop policy context includes `available_water_m3` (water in storage at start of day). Step 2 says "Update water storage state" after water allocation. But the flow doesn't specify the update formula or whether water goes INTO storage first and is then drawn OUT for irrigation, or whether the water allocation directly satisfies irrigation demand, bypassing storage.

Calculations.md defines storage dynamics (`Storage(t+1) = Storage(t) + Inflow(t) - Outflow(t)`) but the simulation flow doesn't show how this integrates with the daily water policy output.

**Suggested fix:** Add explicit pseudocode in Step 2 showing: (1) water policy allocates groundwater + municipal, (2) water goes into storage, (3) irrigation draws from storage up to demand, (4) storage balance updates.

> **Owner response:**
>
> ___

---

### I7. Aquifer Depletion Not Connected to Daily Extraction Limits

**The problem:** The yearly boundary updates aquifer state (drawdown, remaining volume). Error handling says `remaining_volume = 0` if depleted. But the daily `max_groundwater_m3` context field is computed from well capacity, NOT from remaining aquifer volume. A developer must decide whether aquifer depletion should reduce the daily extraction limit or whether the simulation keeps pumping from a depleted aquifer.

**Suggested fix:** Specify explicitly. Recommended: add `min(well_daily_capacity, remaining_volume / days_remaining_in_year)` as an aquifer constraint on `max_groundwater_m3`, or simply state that aquifer depletion is tracked for reporting only and does not constrain extraction in MVP.

> **Owner response:**
>
> ___

---

### I8. Harvest Day Determination Algorithm Missing

**The problem:** simulation_flow.md Step 0 says "Determine if today is a harvest day for any farm/crop" but provides no algorithm. Is it when `days_since_planting >= total_growing_days`? When `growth_stage` transitions past `late_season`? What about multiple planting dates -- each planting has its own harvest day?

**Suggested fix:** Add pseudocode: `is_harvest_day = (days_since_planting == total_growing_days)` for each active planting cycle.

> **Owner response:**
>
> ___

---

### I9. `expected_total_water_m3` for Water Stress Undefined

**The problem:** The harvest yield formula uses `water_ratio = cumulative_water_received / expected_total_water_m3`. No document defines how `expected_total_water_m3` is computed. Is it the sum of `base_demand_m3` from precomputed irrigation data across all growing days? A precomputed total? A developer must figure out how to accumulate this value.

**Suggested fix:** Define explicitly: `expected_total_water_m3 = sum(base_demand_m3[day] for day in growing_period)`, precomputed at planting time from the irrigation demand data.

> **Owner response:**
>
> ___

---

### I10. Cost Allocation Timing Undefined

**The problem:** simulation_flow.md Section 6 defines three cost allocation methods (equal, area-proportional, usage-proportional). Step 7 (Daily Accounting) aggregates costs per farm. But Step 7 doesn't reference Section 6 or specify when/how shared costs are allocated. Is allocation daily? Monthly? The distinction between farm-specific costs and shared OPEX isn't made in the daily accounting step.

**Suggested fix:** Add explicit cost classification in Step 7: farm-specific costs (seeds, fertilizer, field labor) are charged directly; shared OPEX (infrastructure O&M, debt service) is allocated per the configured method. Specify frequency (daily or monthly allocation).

> **Owner response:**
>
> ___

---

### I11. Yearly Boundary Crop Reinitialization vs Active Crops

**The problem:** Step 8 says "Reinitialize farm crops for new year planting schedule" on January 1. But crops planted in November (e.g., onion with planting_date "12-01") may not have been harvested by January 1. The spec doesn't say whether reinitializing crops:

- Forces an early harvest of currently-growing crops
- Discards unharvested crops
- Only resets crops that have completed their cycle

**Suggested fix:** Specify that reinitialization only applies to new planting cycles for the new year; active crops from the previous year continue their growth cycle until harvest. Planting for the new year is triggered by `planting_dates`, not by the calendar reset.

> **Owner response:**
>
> ___

---

### I12. Household Water Treatment Energy Not Aggregated Into Dispatch

**The problem:** Step 2b computes household water allocation (including groundwater treatment energy). Step 3 aggregates energy demand components, listing `E_desal`, `E_pump`, `E_convey` as "sum across all farms." But household groundwater treatment energy from Step 2b is not explicitly included in the Step 3 aggregation. The list says "sum of treatment energy across all farms" -- households are not farms.

**Suggested fix:** Update Step 3 aggregation to explicitly include household water treatment energy: `E_desal = sum across farms + household_treatment_energy`.

> **Owner response:**
>
> ___

---

## MINOR Issues

### M1. `min_cash_months` Undefined in risk_averse Economic Policy

policies.md Section 7.4 uses `reserve_target = MAX(6.0, min_cash_months)` but `min_cash_months` is never defined in the context inputs or parameter list. A developer cannot implement this without guessing.

**Suggested fix:** Replace with `reserve_target = 6.0` (simplest) or add `min_cash_months` as a configurable parameter with a default value.

> **Owner response:** ___

### M2. renewable_first Generator Behavior Misleading in structure.md

structure.md says "Generator only used if grid goes down." policies.md clarifies grid failure is never modeled, so the generator is functionally never dispatched. An implementer reading only structure.md might build a grid-failure code path that never executes.

**Suggested fix:** Update structure.md to: "Generator is not dispatched (grid failure is not simulated in MVP)."

> **Owner response:** ___

### M3. `limiting_factor` Missing from Water Decision Output Table

The `conserve_groundwater` policy returns a `limiting_factor` field (values: "ratio_cap", "well_limit", "treatment_limit", None). This is extensively documented in policies.md Section 2.5 but missing from the Water Decision output table in Section 2.

**Suggested fix:** Add `limiting_factor` to the Water Decision outputs table with a note that it is only returned by `conserve_groundwater`.

> **Owner response:** ___

### M4. `policy_name` Field Not Listed in Any Decision Table

policies.md Section 1 says "Every policy output includes a `policy_name: str` field." But no individual policy domain's decision output table lists it.

**Suggested fix:** Add a note to each domain's decision table: "All outputs also include `policy_name` (see Common Patterns)."

> **Owner response:** ___

### M5. Execution Order Step Numbering Differs Between Documents

structure.md numbers steps 1-7 (forced sales = step 5). policies.md and simulation_flow.md use 1, 2, 3, 4, 4b, 5, 6 (forced sales = step 4b). Logical order is identical.

**Suggested fix:** Standardize on 4b convention. Update structure.md.

> **Owner response:** ___

### M6. "Farm-level only" Label Misleading in policies.md

Food processing, market, crop, and economic domains say "Farm-level only" but then immediately say "Community-override policies are supported." The label means "no household applicability" but reads as "no community override."

**Suggested fix:** Change to "Farm-level (no household applicability)."

> **Owner response:** ___

### M7. Capacity Clipping Not Mentioned in structure.md

policies.md describes a shared post-processing step where excess allocated to a constrained processing pathway is redistributed to fresh. structure.md's food processing section doesn't mention this behavior.

**Suggested fix:** Add a one-line note in structure.md: "If allocated kg exceeds daily equipment capacity, excess is redirected to fresh (see policies.md)."

> **Owner response:** ___

### M8. Domestic Water Pricing Regime Divergence

structure.md specifies domestic subsidized water as a flat `price_usd_per_m3`. simulation_flow.md Section 3.3 specifies Egyptian-style progressive tiered brackets with monthly consumption tracking and a wastewater surcharge. The settings YAML uses the flat rate.

**Suggested fix:** Decide which is correct. If tiered pricing is desired, add to structure.md. If flat rate for MVP, remove tiered logic from simulation_flow.md.

> **Owner response:** ___

### M9. `base_year` for Price Escalation Not Defined

simulation_flow.md uses `current_year - base_year` for unsubsidized price escalation. No document defines `base_year`. Is it the simulation start year? A fixed reference year?

**Suggested fix:** Define in structure.md economic configuration. Simplest: `base_year = simulation start year`.

> **Owner response:** ___

### M10. Processing Capacity Calculation Requires Undocumented Equipment Data

simulation_flow.md Section 4.4 says `capacity_kg_per_day = sum(equipment.throughput_kg_per_day * equipment.availability_factor)`. But structure.md defines equipment as `list of {type, fraction}` -- no `throughput_kg_per_day` field. This value must come from an equipment parameter CSV, but which file and column is not specified.

**Suggested fix:** Document the mapping: equipment `type` is looked up in `data/parameters/equipment/processing_equipment-toy.csv` to get `throughput_kg_per_day`. Add expected column schema.

> **Owner response:** ___

---

## Summary Counts

| Severity | Count |
|---|---|
| CRITICAL | 8 |
| IMPORTANT | 12 |
| MINOR | 10 |
| **Total** | **30** |

The most impactful cluster: **C1-C4** (post-harvest losses, state definitions, price computation, reference price) would each produce silently wrong results if a developer guesses wrong. **C5-C7** (CSV schemas, growth stage algorithm, acceptance criteria) would block implementation entirely.

The second cluster: **I1-I2** (settings YAML and simulation_flow.md parameter divergence from structure.md) are the housekeeping items that should be resolved before coding begins so the canonical source of truth actually IS the source of truth.

---

*Review generated by Claude Code (4 parallel analysis agents, 2026-02-12)*
