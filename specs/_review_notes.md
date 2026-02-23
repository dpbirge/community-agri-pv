# Spec Review Notes

Maintained during sequential subagent spec review. Short entries only.

---

## Legend
- **Decision:** choice made during review and rationale
- **Uncertain:** area where right answer wasn't clear; needs user input
- **Flagged:** mismatch or gap noted but not fixed (cross-file conflict or out of scope)

---

## Initialization

- **Decision:** `simulation_flow.md § 2.1 Step 3` — Fixed `scenario.collective_farm_override` → `scenario.community_structure.collective_farm_override` (and `scenario.farms` → `scenario.community_structure.farms`). YAML nests both under `community_structure`; the old path was wrong.
- **Decision:** `structure.md § 2.4` — Added `community_buildings_m2` and `industrial_buildings_m2` as explicit loader-consumed aggregate fields. Removed `total_area_ha` (it is a fallback, not a primary field; added parenthetical note on `total_farming_area_ha` instead). Clarified `community_buildings` sub-map is informational only. Updated scaling sentence to name the field.
- **Decision:** `structure.md § 2.2 water_treatment` — Renamed `groundwater_tds_ppm` to `tds_ppm` as loader-consumed field name (matching YAML `tds_ppm`). Added alias note. Marked `municipal_tds_ppm` as informational (not parsed by loader). Updated TDS data flow accordingly.
- **Decision:** `structure.md § 3.1 SimulationState` — Added `system_constraints: dict` field. It is computed at initialization Step 5 and referenced by key throughout Step 2 (`max_gw_per_farm`, `max_treatment_per_farm`); had no defined home in the dataclass.
- **Decision:** `structure.md § 3.6 EnergyState` — Fixed `SOC_min`/`SOC_max` to `soc_min`/`soc_max` (snake_case consistency; YAML uses lowercase).
- **Flagged:** `policies.md § 11` references `overview.md` which has been deleted. Out of scope for initialization phase; deferred content only.
- **Flagged:** `simulation_flow.md § 2.4 Step 13` `annual_reserve_pct` has no YAML entry — it is a hardcoded default (2.5%) defined in `calculations_economic.md § 2`. Not a config parameter. No change needed; behavior is correctly documented in calculations file.

---

## Daily Setup (Step 0)

- **Decision:** `simulation_flow.md § 3 Step 0` — Fixed weather field names: `temperature_c` → `temp_max_c, temp_min_c`, `irradiance` → `solar_irradiance_kwh_m2`, `wind_speed` → `wind_speed_ms`. These match actual column names in `data/precomputed/weather/daily_weather_scenario_001-*.csv`. Added schema cross-reference.
- **Decision:** `simulation_flow.md § 3 Step 0` — Removed `ET0` from Step 0 weather retrieval block. ET0 is not a column in the weather file. It appears in the irrigation demand precomputed files (per planting_date, crop_day). See Flagged item below on the Step 1/Section 4.4 inconsistency.
- **Decision:** `simulation_flow.md § 3 Step 0` — `avg_prices` was described as "from price files" implying a direct lookup. Corrected to "trailing 12-month average price ... computed from price time-series files."
- **Decision:** `simulation_flow.md § 3 Step 0` — `crop_stages` and `is_harvest` were listed as data retrieval operations with a vague `(→ Section 4)` annotation. They are computed results of the Section 4.2 state machine, which runs during Step 0. Added explanatory comment and corrected the source annotation. Fixed `is_harvest` definition to `crop.state == HARVEST_READY` (not "transitioned today").
- **Decision:** `simulation_flow.md § 3 Step 0` and `§ 7.1` — `cumulative_gw_month_m3` (FarmState) was never reset anywhere in the spec despite being a monthly accumulator. Added `FOR each farm: farm.cumulative_gw_month_m3 = 0` to both Step 0 monthly resets and Section 7.1.
- **Decision:** `simulation_flow.md § 3 Step 0` and `§ 7.2` — `cumulative_gw_year_m3` (FarmState) was never reset anywhere in the spec despite being a yearly accumulator. Added `FOR each farm: farm.cumulative_gw_year_m3 = 0` to both Step 0 yearly resets and Section 7.2.
- **Decision:** `structure.md § 4` — Added missing precomputed data file schemas for files consumed in Step 0 and Step 6a: weather, irrigation demand, household energy, household water, community building energy, community building water, PV normalized output, wind normalized output, microclimate shade adjustments. Also added water price and electricity price schemas (column names were referenced by path in § 2.7 but schemas were absent from § 4).
- **Flagged:** `simulation_flow.md § 4.4` vs. `§ 3 Step 1` — Section 4.4 gives the formula `base_demand_m3 = ET0 * crop.kc * effective_area_ha * 10 / eta_irrigation`, implying ET0 is computed from weather each day. Step 1 says `base_demand_m3 = lookup from precomputed irrigation data`, implying the precomputed `irrigation_m3_per_ha_per_day` value is used directly. These are contradictory: if the precomputed lookup is used, ET0 does not need to be derived at runtime; if the formula is used, ET0 source and microclimate adjustment application need to be specified. Out of scope for Step 0 phase — deferred to Step 1 reviewer.

---

## Crop Policy (Step 1)

- **Decision:** `simulation_flow.md § 4.4` — Replaced ETc formula (`ET0 * kc * area / eta`) with the precomputed lookup it contradicted. Step 1 (canonical) says "lookup from precomputed irrigation data"; § 4.4 was specifying the generation formula not the simulation runtime operation. New text: `lookup irrigation_m3_per_ha_per_day × effective_area_ha` with file schema cross-reference. The ETc formula belongs in `calculations_crop.md`, not here.
- **Decision:** `simulation_flow.md § 3 Step 1` — Made base_demand_m3 lookup explicit: `lookup_irrigation_m3_per_ha(planting_date, crop_day) * effective_area_ha` with `→ Section 4.4` cross-reference. Previous "lookup from precomputed irrigation data" was missing the `× effective_area_ha` scaling step.
- **Decision:** `simulation_flow.md § 4.2` — Added `crop.cycle_start_date = today` to the DORMANT → INITIAL transition block. The field is defined in `CropState` and consumed in Step 1 (`days_since_planting = (current_date - cycle_start_date).days`), but was never set in the state machine pseudocode. This was a genuine implementation gap.
- **Decision:** `simulation_flow.md § 4.4` — Relabelled the `crop.cumulative_water_received` update to "executes in Step 2, Phase 3" and added the same update block to Step 2 Phase 3 where it actually executes. The update requires `irrigation_delivered_m3` (a Step 2 output), so it cannot live in Step 1 or § 4.
- **Decision:** `simulation_flow.md § 3 Step 4` — Added subsection 4.3 to Step 4 pseudocode: explicit DORMANT transition (`crop.state = DORMANT`, `days_in_stage = 0`, `kc = 0`, `cycle_start_date = None`) after harvest is processed. § 4.2 referenced this transition in a comment ("Step 4 transitions crop back to DORMANT after processing") but Step 4 itself never executed it.
- **Decision:** `structure.md § 3.3 CropState` — Added `init = 0` annotation to `kc` field. All crops start DORMANT; kc must initialize to 0.

---

## Water Allocation (Step 2)

- **Decision:** `simulation_flow.md § 3 Step 2 Phase 1` — Fixed `system_constraints.max_gw_per_farm` → `system_constraints[farm.id].max_gw_per_farm` (and same for `max_treatment_per_farm`). `system_constraints` is a per-farm dict keyed by `farm.id` per structure.md § 3.1; flat-attribute access was wrong.
- **Decision:** `simulation_flow.md § 3 Step 2 Phase 2` — Removed undefined `estimated community GW request` (circular: Step 2b hasn't run yet). Phase 2 now explicitly covers farm allocations only with explanatory comment. Defined `total_treatment_capacity = water_system.water_treatment.system_capacity_m3_day` (was used but never defined). Made `scale_factor` application explicit (`allocation.groundwater_m3 *= scale_factor`, shortfall added to `municipal_m3`).
- **Decision:** `simulation_flow.md § 3 Step 2 Phase 3` — Replaced undefined `total_gw_drawn_m3` with `total_farm_gw_m3 = SUM(farm allocation.groundwater_m3)`. Changed outflow computation to use `allocation.irrigation_delivered_m3` (the named field). Added missing per-farm `cumulative_gw_month_m3` and `cumulative_gw_year_m3` increment — these trackers were consumed in Phase 1 for `quota_enforced` but never written after allocation.
- **Decision:** `simulation_flow.md § 3 Step 2c` — Replaced vague "Recompute drawdown_m, effective_head_m, pumping_kwh_per_m3" with explicit formulas. Named `community_gw_m3` from Step 2b result. Removed floating `max_groundwater_m3 = 0` assignment (not a state variable; replaced with comment on next-day Phase 1 behavior).
- **Decision:** `policies.md § 4 Water Decision outputs` — Added `irrigation_delivered_m3` (= groundwater_m3 + municipal_m3) as an explicit WaterAllocation output field. It was consumed by name in simulation_flow.md Phase 3 and Section 4.4 but absent from the output table.
- **Decision:** `simulation_flow.md § 4.4` — Updated bare `irrigation_delivered_m3` reference to `allocation.irrigation_delivered_m3` for consistency with the now-named WaterAllocation field.
- **Decision:** `structure.md § 3.4 AquiferState` — Added `max_drawdown_m` and `well_depth_m` as config-sourced constant fields (sourced from `groundwater_wells` config section). Both are used in Step 2c drawdown formulas but were absent from the dataclass.
- **Decision:** `calculations_water.md § 11` — Removed the approximation formula `cumulative_extraction_m3 = exploitable_volume - remaining_volume` from the drawdown model. That formula underestimates cumulative extractions when recharge is non-zero. Replaced with a comment pointing to the running-sum approach in AquiferState (per simulation_flow.md Step 2c).

---

## Pre-Harvest Clearance (Step 3)

- **Decision:** `simulation_flow.md § 3 Step 3` — Replaced `current_price(tranche.crop_name, tranche.product_type)` pseudo-function call with `prices[tranche.crop_name][tranche.product_type]`, consistent with the `prices` dict resolved in Step 0. The function-call notation was not defined anywhere and implied runtime lookup logic outside the established pricing pattern.
- **Decision:** `simulation_flow.md § 3 Step 0` — Added `processed product prices` to the Step 0 `prices` retrieval line. It was omitted; Step 3 and Step 5b both look up processed product prices by product_type, so the daily prices dict must include them.
- **Decision:** `simulation_flow.md § 3 Step 3` — Added zero-price disposal rule: if `price = 0`, log warning and remove tranche with zero revenue. Without this, a zero daily price for an expired tranche silently discards inventory value with no spec-defined behavior (genuine gap).
- **Decision:** `simulation_flow.md § 3 Step 3` — Added `→ structure.md § 3.7` cross-reference for `expiry_date` field and its derivation from `shelf_life_days` in `storage_spoilage_rates-toy.csv`. Step 3 used the field without pointing to where it is set.
- **Decision:** `policies.md § 7 Pricing` — Added clarification that forced-sale price uses the Step 0 daily resolved value (crop CSV for fresh, processed CSV for processed), and added `→ simulation_flow.md § 5` cross-reference. "Current market price" was undefined in context; this was a genuine naming ambiguity.
- **Flagged:** `simulation_flow.md § 3 Step 4` — `expiry_date` is defined as `harvest_date + shelf_life_days` in `structure.md § 3.7` but Step 4 pseudocode never explicitly computes it when creating StorageTranches. Out of scope for Step 3 phase; deferred to Step 4 reviewer.

---

## Food Processing (Step 4)

- **Decision:** `simulation_flow.md § 3 Step 4.2` — Expanded tranche creation block to make `expiry_date` computation explicit: `expiry_date = harvest_date + shelf_life_days` where `shelf_life_days` is looked up from `storage_spoilage_rates-toy.csv` by `(crop_name, product_type)`. Was flagged by prior agent as never computed in Step 4 despite being consumed in Step 3.
- **Decision:** `simulation_flow.md § 3 Step 4.2` — Made `output_kg = input_kg * (1 - weight_loss_pct)` explicit in tranche creation loop, with source note (`processing_specs-toy.csv`). "Apply weight loss" was too vague to implement without ambiguity about what `kg` field to store.
- **Decision:** `simulation_flow.md § 3 Step 4.2` — Made `farm_shares` computation explicit inline (`farm_kg / pooled_kg` where `farm_kg` is post-handling-loss). Added `→ simulation_flow.md § 6.2` cross-reference.
- **Decision:** `simulation_flow.md § 3 Step 4.1` — Added `yield_factor = FarmState.yield_factor → structure.md § 3.2` inline comment. `yield_factor` appeared in the yield formula without a defined source, which was an orphaned reference.
- **Decision:** `simulation_flow.md § 3 Step 4.1` — Renamed "Track farm_shares per crop per batch" to "Track farm_kg per farm (post-handling-loss contribution)" for clarity — shares are not computed here, only the per-farm kg contributions that form shares in 4.2.
- **Decision:** `simulation_flow.md § 6.2` — Added clarifying comment that `farm_kg` is post-handling-loss and that `pooled_kg = SUM(farm_kg)`. Prior wording was ambiguous about which stage the farm_kg comes from.
- No issues found in `policies.md § 6`: all four policy fraction tables sum to 1.0; context fields match Step 4.2 usage; `harvest_available_kg` correctly described as post-handling-loss.
- No issues found in `calculations_crop.md § 4-5`: handling loss applied before pool (per-farm), processing weight loss applied after policy split — consistent with `structure.md § 2.5` and `simulation_flow.md § 6.1`.

---

## Sales & Inventory (Step 5)

- **Decision:** `simulation_flow.md § 3 Step 5a` — Replaced bare `total_stored > storage_capacity` with `total_stored_kg[product_type] > storage_capacities_kg[product_type]`, defined as SUM of tranches per product_type. Neither variable was defined; the WHILE condition was unimplementable.
- **Decision:** `simulation_flow.md § 3 Step 5a` — Expanded WHILE body from single-line stub ("Sell oldest tranche...") to a full partial-tranche FIFO loop with price lookup, per-tranche sell/partial-sell, and revenue attribution. Now consistent with policies.md § 7.
- **Decision:** `simulation_flow.md § 3 Step 5b` — Defined `available_kg` inline as `SUM(tranche.kg for tranches where product_type and crop_name match)`. Genuine gap: it was passed to `MarketPolicyContext` but never defined.
- **Decision:** `simulation_flow.md § 3 Step 5b` — Replaced undefined `current_stored_kg[product_type]` with `total_stored_kg[product_type]`, consistent with the variable name introduced in Step 5a.
- **Decision:** `simulation_flow.md § 3 Step 5b` — Added explicit FIFO sell loop (tranche decrement, tranche removal, per-tranche revenue attribution). Prior text stated "Attribute revenue via tranche.farm_shares (FIFO order)" with no loop; state mutations were absent.
- **Decision:** `simulation_flow.md § 3 Step 5b` — Moved `price` lookup outside the FIFO loop (constant per crop+product_type). Replaced undefined `current_price` variable with `prices[crop_name][product_type]`.
- **Decision:** `policies.md § 7 Step 5a overflow block` — Added `product_type` scope: `IF total_stored_kg[product_type] > storage_capacities_kg[product_type]` and scoped tranche iteration to this product_type. Was using globally-scoped `total_stored > capacity`, contradicting simulation_flow.md Step 5a's per-product_type loop.
- **Decision:** `policies.md § 8 Shared Logic: Tranche Selection` — Removed FIFO sell loop pseudocode (simulation mechanics, not policy logic). Replaced with a one-line note pointing to simulation_flow.md Step 5b where the loop now lives. The `decide()` method returns `sell_fraction` only.
- **Decision:** `policies.md § 8 hold_for_peak and adaptive pseudocode` — Replaced `storage_capacity` with `storage_capacity_kg` in both policy blocks to match the `MarketPolicyContext` field name defined in the Context table.

---

## Energy Dispatch (Step 6)

- **Decision:** `simulation_flow.md § 3 Step 6a` — Replaced undefined `total_irrigation_m3` with `total_irrigation_delivered_m3 = SUM(farm allocation.irrigation_delivered_m3) from Step 2`. The unnamed variable was unimplementable.
- **Decision:** `simulation_flow.md § 3 Step 6a` — Added source comment for `irrigation_pressure_kwh_per_m3`: `→ calculations_water.md § 4` (derived from irrigation_systems-toy.csv at initialization). The variable was used with no defined origin in any spec section.
- **Decision:** `simulation_flow.md § 3 Step 6a` — Added source comment for `community water energy` (from Step 2b). Was implied but unnamed.
- **Decision:** `simulation_flow.md § 3 Step 6b` — Replaced `Call dispatch_energy(total_demand_kwh, combined_flags, ...)` with an explicit argument list including `pv_available_kwh`, `wind_available_kwh`, and battery/generator/price parameters. The `...` left key dispatch inputs undefined — a genuine implementation gap.
- **Decision:** `simulation_flow.md § 3 Step 6b` — Added two lines computing `pv_available_kwh` and `wind_available_kwh` from precomputed data × nameplate capacity. These required dispatch inputs were entirely absent from Step 6b.
- **Decision:** `simulation_flow.md § 3 Step 6b` — Resolved self-discharge ambiguity. Original spec applied self-discharge separately after dispatch, but `structure.md § 3.12 DispatchResult.battery_soc_after` is defined as "SOC after dispatch + self-discharge" — self-discharge is inside `dispatch_energy()`. Removed the redundant external line; state update is now `energy.battery_soc = dispatch_result.battery_soc_after`.
- **Decision:** `simulation_flow.md § 3 Step 6c` — Replaced undefined `farm_demand_kwh_i` and `community_demand_kwh` with explicit definitions. `farm_demand_kwh_i` = farm water energy + farm irrigation pump energy + farm processing energy (pro-rated by harvest_kg, with zero-guard). `community_demand_kwh` = `E_household + E_community_bldg`. Both were consumed in attribution formulas but never defined.
- **Decision:** `simulation_flow.md § 3 Step 6b` — Named dispatch function return value as `dispatch_result` and added `→ structure.md § 3.12` cross-reference for the field list. Consistent with how other steps name their output variables.

---

## Daily Accounting (Step 7)

- **Decision:** `simulation_flow.md § 3 Step 7a` — Removed `daily_debt_service` from `Total_daily_shared_opex`. `DailyFarmRecord` tracks `allocated_shared_cost_usd` and `debt_service_cost_usd` as separate fields; including debt in the shared total and then adding it again in `total_cost` was double-counting. Moved `daily_debt_service` definition to Step 7a preamble; allocation moved to Step 7b.
- **Decision:** `simulation_flow.md § 3 Step 7a` — Replaced vague cross-reference `§ 27.2.3-27.2.4` with inline per-line references. Added `economic_state.infrastructure_annual_opex / 365` as explicit source for `daily_infrastructure_om` (was undefined). Added `× blended wage` to maintenance labor line for symmetry with management labor line.
- **Decision:** `simulation_flow.md § 3 Step 7b` — Added `debt_service_share_i = allocate(daily_debt_service, cost_allocation_method)` so the separately-tracked debt service is properly allocated before Step 7c uses it.
- **Decision:** `simulation_flow.md § 3 Step 7c` — Fixed `labor_cost` comment: removed "management, maintenance" from the list of categories summed by `daily_labor_cost(farm, date)`. Management and maintenance are community-wide shared costs (Step 7a); including them in the per-farm function was a double-count specification error.
- **Decision:** `simulation_flow.md § 3 Step 7c` — Renamed `water_cost` source to `farm_allocations[farm].cost_usd` (matches `WaterAllocation.cost_usd` from policies.md § 4). Renamed `energy_cost` source to `farm_energy_cost_i` (matches Step 6c output variable name).
- **Decision:** `simulation_flow.md § 3 Step 7c` — Replaced vague `storage_cost = SUM(tranche.kg * farm_share * rate per tranche)` with `daily_storage_cost_farm_i` and cross-reference to `§ 6.4` (which has the exact formula). Replaced vague `input_cost` formula with explicit CSV lookup and defined `active_ha`.
- **Decision:** `simulation_flow.md § 3 Step 7c` — Named revenue variables explicitly: `crop_revenue = farm.daily_revenue`, `export_revenue = farm_export_revenue_i`. Added explicit `farm_specific_costs` summation line so `total_cost` formula is unambiguous.
- **Decision:** `simulation_flow.md § 8.2` — Fixed shared OPEX list: replaced `administrative_labor` (informal, undefined term) with `management_labor` and `maintenance_labor` (matching § 27.2.3/27.2.4 names). Removed `debt_service` (now tracked separately). Added note that debt service is allocated separately in Step 7b.
- **Decision:** `simulation_flow.md § 8.1` — Removed duplicate allocation method table (identical copy of `structure.md § 2.8`). Replaced with cross-reference only.
- **Uncertain:** `FarmState.daily_revenue` and `FarmState.daily_costs` — accumulator fields require a daily reset. Reset timing (start of Step 0 or end of Step 7) is not specified in the flow. Did not add spec text without user confirmation.

---

## Post-Loop Reporting (§ 10)

- **Decision:** `simulation_flow.md § 10.1 Step 1` — Replaced "Log in-progress crops" (ambiguous separate output) with "Record in-progress crops as part of final state snapshot (Step 3)." In-progress crop data lives in CropState; no separate logging schema is needed.
- **Decision:** `simulation_flow.md § 10.1 Step 2` — Replaced undefined `current_price` with `prices[crop_name][product_type]` (the same dict resolved on the final simulation day in Step 0). Removed "end-of-simulation prices" ambiguity.
- **Decision:** `simulation_flow.md § 10.1 Step 2` — Clarified that terminal inventory value is "added to the final year's net income for NPV/IRR only" (replacing "enters NPV as salvage inflow," which left the mechanism unspecified). Added cross-reference to `calculations_economic.md § 21`.
- **Decision:** `simulation_flow.md § 10.1 Step 3` — Replaced prose list of fields with `→ structure.md § 3.13` cross-reference and kept explicit field list inline. structure.md § 3.13 is a new section.
- **Decision:** `simulation_flow.md § 10.2 Stage 2` — Fixed bare `→ calculations_economic.md` (no section number) to `→ calculations_economic.md § 15-16; Gini formula in metrics_and_reporting.md § 1`.
- **Decision:** `simulation_flow.md § 10.2 Stage 3` — Made "linear slope" explicit: "least-squares slope of yearly metric series over simulation years." Was undefined.
- **Decision:** `simulation_flow.md § 10.2 Stage 4` — Added instruction: terminal_inventory_value added to final year net income before NPV/IRR. Previously § 10.1 said it enters NPV but Stage 4 had no corresponding instruction.
- **Decision:** `simulation_flow.md § 10.4` — Added schema cross-references for all three output files that lacked them: `monthly_summary.csv → structure.md § 3.14`, `simulation_summary.json → structure.md § 3.15`, `final_state.json → structure.md § 3.13`.
- **Decision:** `simulation_flow.md § 10.4 item 7` — Replaced "per metrics_and_reporting.md" (no section) with `→ metrics_and_reporting.md § 2`.
- **Decision:** `structure.md § 3.13` — Added `FinalState` schema (new section). Fields: water_storage_m3, battery_soc, aquifer_remaining_volume_m3, cash_positions dict, total_debt_remaining_usd, terminal_inventory_value_usd, in_progress_crops list.
- **Decision:** `structure.md § 3.14` — Added `monthly_summary.csv` schema (new section). One row per (farm_id, year, month) plus community aggregate row per month.
- **Decision:** `structure.md § 3.15` — Added `simulation_summary.json` schema (new section). Two keys: `lifetime` (Stage 3 fields) and `financial` (Stage 4 fields).
- **Decision:** `calculations_economic.md § 21` — Added note to `Net_income(t)` parameter: terminal_inventory_value is added to year-N net income before discounting. Previously the NPV formula had no mention of terminal inventory despite simulation_flow.md § 10.1 specifying it enters NPV.
- **Flagged:** `metrics_and_reporting.md § 1 NPV formula` — Formula `NPV = -Initial_CAPEX + SUM ...` omits terminal inventory value as salvage. simulation_flow.md § 10.1 and calculations_economic.md § 21 (now updated) both add it to final-year net income for NPV/IRR. Not fixed (metrics_and_reporting.md is read-only for this phase).
- **Flagged:** `metrics_and_reporting.md § 1` — No metric computation order is defined. simulation_flow.md § 10.2 specifies a strict 4-stage order (per-farm yearly → community yearly → lifetime → financial). Not fixed.

---

