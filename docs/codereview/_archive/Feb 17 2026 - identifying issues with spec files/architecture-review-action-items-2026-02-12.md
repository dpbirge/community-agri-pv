# Architecture Deep Review -- Action Items Tracker

**Date:** 2026-02-12
**Source:** `docs/codereview/architecture-deep-review-2026-02-12.md`
**Status:** Active

---

## 1. Document Fixes -- calculations.md

These items require updating calculations.md to align with structure.md and policies.md. This is the big alignment pass identified in cross-cutting issue 5.1.

| Item | Description | Owner Response | Priority | Status |
|------|-------------|----------------|----------|--------|
| 1.1 | Water policy count says "five" -- should not hardcode count; add missing `min_water_quality` policy entry | "Remove any mention of the number of policies (which will always be changing). Ensure that each policy outlined in structure.md is represented in both policies.md and calculations.md (as needed). Add the missing min_water_quality policy where missing and add logic and equations in-line with the policy goal. If there is any question about the right equation, flag it for me as you implement." | CRITICAL | Done |
| 1.2 | Water policy names use PascalCase (`AlwaysGroundwater`, `AlwaysMunicipal`) instead of canonical snake_case (`max_groundwater`, `max_municipal`) | "Agree, use one single naming convention across all files and in turn in the code when written." | HIGH | Done |
| 1.3 | Energy policy names completely mismatched (`PvFirstBatteryGridDiesel`, `GridFirst`, `CheapestEnergy` vs spec names `microgrid`, `renewable_first`, `all_grid`). `CheapestEnergy` has no spec counterpart. | "Agree on naming, see 1.2. Remove any policies not in the structure.md doc throughout." | CRITICAL | Done |
| 1.5 | Energy pricing schema: calculations.md has single global regime vs structure.md dual agricultural/domestic regime. Parameter names differ (`price_usd_per_kwh` vs `base_price_usd_kwh`). calculations.md has extra sub-parameters not in structure.md. | "Agree" | HIGH | Done |
| 1.6 | Water pricing schema: calculations.md references flat `water_pricing.pricing_regime` vs structure.md dual agricultural/domestic regime | "Agree" | HIGH | Done |
| 1.10 | Debt service references nonexistent `economics.debt.*` config section -- actual mechanism is per-subsystem via `financing_status` and `financing_profiles.csv` | "Agree" | HIGH | Done |
| 1.11 | `market_responsive` food processing logic completely different between policies.md (fixed two-state allocation) and calculations.md (dynamic net-value pathway selection). calculations.md version should cross-reference policies.md Section 3.4 as authoritative. | "Agree" | MEDIUM | Done |
| 1.13 | Energy dispatch ignores policy output flags. calculations.md states "Energy policy objects are not consumed by the dispatch function." Needs proper equations for each policy type. | "Update calculation file to implement proper equations for each of the policy types outlined in structure/policies file." | CRITICAL | Done |
| 1.16 | `planting_date` (singular) in calculations.md vs `planting_dates` (plural, list) in structure.md | "Agree" | LOW | Done |
| 1.17 | Total energy demand uses 6 components in one section but only 3 in dispatch section (`E_convey`, `E_processing`, `E_irrigation_pump` missing from dispatch). Owner says no subsets -- use all 6 everywhere. | "The 6 components should be updated everywhere... no subsets" | HIGH | Done |
| 1.18 | Groundwater cost formula uses ambiguous variable names (`E_pump`, `electricity_price`) without unit annotations. Should use per-unit names like `pumping_kwh_per_m3`. | "Agree" | MEDIUM | Done |
| 1.24 | Food processing labeled "Partially TBD" despite being fully specified in policies.md | "Agree" | MEDIUM | Done |
| 1.25 | Crop revenue formula uses fresh-sale-only formula, ignores processing split. Needs unified "Total Crop Revenue" formula combining fresh and processed revenue without double counting. | "Agree, all food products need to be calculated based on their weight after yields have been split. Fresh food is gathered at harvest and then designated into different food product channels for processing. Fresh is one product, canned, etc. Ensure the formulas do not double count." | HIGH | Done |
| 1.27a | `degradation_rate` in calculations.md not in structure.md PV config -- clarify if from parameter file only or add to config | "Agree" | LOW | Done |
| 1.27b | Battery SOC formula: inconsistent `dt` treatment between sections -- note that dispatch uses kWh (dt absorbed) | "Agree" | LOW | Done |
| 1.27c | Post-harvest loss rate: narrative says 10-15%, default hardcoded at 10% -- use single default with range as background | "Agree" | LOW | Done |
| 1.27d | `balanced` food fractions duplicated in calculations.md and policies.md -- replace with cross-reference to policies.md | "Agree" | LOW | Done |

---

## 2. Document Fixes -- structure.md

| Item | Description | Owner Response | Priority | Status |
|------|-------------|----------------|----------|--------|
| 1.7 | Missing `max_drawdown_m` in structure.md groundwater wells section (referenced in calculations.md as "new parameter") | "Agree" | HIGH | Done |
| 1.8 | Missing `hub_height_m` in wind configuration -- calculations.md references it but structure.md only has `sys_capacity_kw`, `type`, `financing_status` | "Review the data files -- the hub height is specified there I believe. Hub height should not be set by user, they should select a type of wind turbine." | MEDIUM | Done |
| 1.9 | Salinity level categories: structure.md has 4 (`low, moderate, high, very_high`) but calculations.md has only 3 (`low, moderate, high`). Align across documents and data CSV. | "Agree" | MEDIUM | Done |
| 1.12 | `market_responsive` in structure.md shows `30-65%` range notation implying continuous adjustment, but policies.md reveals it is a binary switch between exactly 30% and 65% | "Agree" | LOW | Done |
| 1.14 | Missing output fields from structure.md: 3 of 6 domain output specs omit `decision_reason`. Energy output lists no fields at all. `constraint_hit` absent from Water output spec. | "Agree" | HIGH | Done |
| 1.15 | Execution order (Crop -> Water -> Energy -> Food -> Forced sales -> Market -> Economic) missing from structure.md -- only in policies.md | "Agree" | HIGH | Done |
| 1.19 | `tds_ppm` data flow unclear. Need `municipal_tds_ppm` in structure.md. Clarify groundwater TDS is static for MVP. Document flow for groundwater, treated groundwater, municipal, and mixed salinity values. | "Groundwater tds will be static for the MVP. All files need to properly deal with groundwater, treated groundwater, municipal, and mixed salinity values. The mixed results from adding municipal water to either direct groundwater (if no treatment is available in the community) or the treated groundwater." | HIGH | Done |
| 1.21 | `current_capital_usd` is runtime state listed as static config in structure.md. Move to state management system. | "Move to state management system" | MEDIUM | Done |
| 1.22 | `microgrid` excluded from household energy policies without rationale. Owner says households should qualify for microgrid. | "You're right. Household energy should qualify for the microgrid. Update docs as needed to reflect." | MEDIUM | Done |

---

## 3. Document Fixes -- policies.md

| Item | Description | Owner Response | Priority | Status |
|------|-------------|----------------|----------|--------|
| 1.20 | `fresh_packaging_capacity_kg` contradicts "no capacity limit" for fresh. Remove capacity limits for fresh packaging or set default extremely high. | "Update all files to remove any capacity limits for fresh packaging (or set the default extremely high)" | MEDIUM | Done |
| 1.23 | `hold_for_peak` storage checks overlap with umbrella rule. policies.md says umbrella rule handles storage-life expiry and overflow, yet `hold_for_peak` pseudocode includes its own storage capacity checks. | "Too unclear to answer. Read the structure file again and determine the right edits to make within the context." | MEDIUM | Done |
| 1.26 | `limiting_factor` vs `constraint_hit` overlap. `limiting_factor` adds `"ratio_cap"` alongside infrastructure constraint values. Relationship between the two fields is undocumented. | "Unclear problem. Use the structure document to ensure the logic in policies and calculations coincides with it." | MEDIUM | Done |

---

## 4. Code Changes Needed

### CRITICAL (Blocks Implementation)

| Item | Description | Owner Response | Priority | Status |
|------|-------------|----------------|----------|--------|
| 3.1 | `min_water_quality` policy not implemented in code. Spec defines 6 water policies, code has only 5. `groundwater_tds_ppm` and `municipal_tds_ppm` not in `WaterPolicyContext`. | "Agree" | CRITICAL | TODO |
| 3.2 | Food processing capacity clipping not implemented. Spec defines shared clipping algorithm (excess redistributes to fresh), but no policy performs it. | "Agree" | CRITICAL | TODO |
| 3.3 | Umbrella rule (FIFO tranche tracking) insufficiently specified. Needs `StorageTranche` dataclass, storage location, FIFO logic across product types, forced sales pricing. | "Agree" | CRITICAL | In Progress (flow spec) |
| 3.4 | Energy policies not consumed by `dispatch_energy()`. Dispatch uses hardcoded merit order regardless of policy selection. | "Agree. This must be fixed so energy policies are correctly implemented." | CRITICAL | TODO |
| 3.5 | Energy policy spec/code name mismatches. Spec: `microgrid`, `renewable_first`, `all_grid`. Code: `PvFirstBatteryGridDiesel`, `GridFirst`, `CheapestEnergy`. Output fields also differ. | "Agree" | CRITICAL | TODO |
| 3.6 | Economic-market policy interaction undefined. When `sell_inventory = true`, does it override market policy? Needs integration spec. | "Agree" | CRITICAL | TODO |

### MAJOR (Could Cause Bugs)

| Item | Description | Owner Response | Priority | Status |
|------|-------------|----------------|----------|--------|
| 3.7 | Policy name registry mismatches. Spec names differ from code registry keys across water, energy, and market domains. No backward compatibility needed. | "Agree, but we don't need backward compatibility" | MAJOR | TODO |
| 3.8 | Water policy registry missing. All other policy modules have registry dict and factory function, but water policies do not. | "Agree" | MAJOR | TODO |
| 3.9 | `decision_reason` missing from `ProcessingAllocation`. Spec requires it as a universal output field, but code only has `policy_name`. | "Agree" | MAJOR | TODO |
| 3.10 | Reference farmgate prices hardcoded. Code uses `REFERENCE_PRICES = {"tomato": 0.30, ...}` instead of loading from data files as spec requires. | "Agree" | MAJOR | TODO |
| 3.11 | `avg_price_per_kg` averaging window unspecified. "Recent history" undefined -- specify 90-day rolling average as default, configurable via YAML. | "Agree" | MAJOR | TODO |
| 3.12 | Growth stage mapping not defined. No formula or lookup for `days_since_planting` -> stage. Research needed. | "Research and update data files to include missing data as needed for policies and simulations." | MAJOR | TODO |
| 3.13 | Crop policy / water policy demand boundary ambiguous. Clarify: crop policy outputs a demand REQUEST; water policy and simulation loop handle allocation against supply. | "Agree" | MAJOR | TODO |
| 3.14 | Economic policy call timing unspecified. "Monthly or at year boundaries" but no exact trigger day or which period's data to use. Specify first day of month using previous month's aggregates. | "Agree" | MAJOR | TODO |
| 3.15 | `months_of_reserves` computation undefined. No spec for who computes it or averaging period for `avg_monthly_opex`. Specify trailing 12 months. | "Agree" | MAJOR | TODO |
| 3.16 | Zero-demand edge cases unspecified. No early return guards for `demand_m3 = 0` or `harvest_yield_kg = 0`. Capacity clipping divides by harvest yield. | "Agree" | MAJOR | TODO |
| 3.17 | `hold_for_peak` code handles spoilage, contradicting umbrella rule. Remove spoilage check from `HoldForPeak.decide()`. | "Agree" | MAJOR | Done (doc fix in policies.md) |
| 3.18 | Processing capacity pipeline undefined. No spec for who calculates processing capacities, when, or whether equipment availability (90%) is applied. Specify at scenario load time. | "Agree" | MAJOR | TODO |
| 3.19 | Household policy integration unspecified. No spec for household demand calculation, dispatch integration, separate vs shared policy instances, or YAML schema. | "Agree, and fill out as best you can" | MAJOR | TODO |
| 3.20 | Municipal water price resolution logic unspecified. "Resolved upstream" but no pseudocode. Agricultural = flat rate; domestic = tiered with monthly tracking. | "Agree, and fill out as best you can" | MAJOR | TODO |

### MINOR (Inconvenience / Naming)

| Item | Description | Owner Response | Priority | Status |
|------|-------------|----------------|----------|--------|
| 3.22a | `weather_adaptive` temperature thresholds not configurable via YAML | "Resolve as you see best" | MINOR | TODO |
| 3.22b | `soil_moisture_estimate` field in code but not in spec | "Resolve as you see best" | MINOR | TODO |
| 3.22c | `price_trend` field in market code but not in spec | "Resolve as you see best" | MINOR | TODO |
| 3.22d | `sell_all_immediately` doesn't explicitly set `target_price_per_kg = 0` | "Resolve as you see best" | MINOR | Done (doc fix in policies.md) |
| 3.22e | `storage_capacity_kg` ambiguous (remaining or total?) -- rename to `available_storage_capacity_kg` | "Resolve as you see best" | MINOR | TODO |
| 3.22f | `configured_minimum` in `risk_averse` pseudocode undefined -- replace with `min_cash_months` | "Resolve as you see best" | MINOR | Done (doc fix in policies.md) |
| 3.22g | Sigmoid function referenced but never formally defined -- add to Common Patterns | "Resolve as you see best" | MINOR | Done (doc fix in policies.md) |
| 3.22h | `policy_name` field in all code outputs but not in spec outputs -- add to spec common output pattern | "Resolve as you see best" | MINOR | Done (doc fix in policies.md) |
| 3.22i | Spoilage rates CSV schema not specified -- document: `crop_name, product_type, shelf_life_days` | "Resolve as you see best" | MINOR | TODO |
| 3.22j | `available_energy_kwh` in water code contradicts "operational independence" -- decide: remove energy constraint or update spec | "Resolve as you see best" | MINOR | TODO |
| 3.22k | No error handling specification for any policy -- add "Error Handling" to common patterns | "Resolve as you see best" | MINOR | Done (doc fix in policies.md) |
| 3.22l | No test vectors provided for boundary conditions -- add 3-5 input/output pairs per policy | "Resolve as you see best" | MINOR | TODO |
| 3.22m | Community-override YAML schema not specified -- define resolution logic | "Resolve as you see best" | MINOR | TODO |

---

## 5. New Policy Work (Docs + Code)

| Item | Description | Owner Response | Priority | Status |
|------|-------------|----------------|----------|--------|
| 2.1 | Crop: `combined_deficit_weather` -- combines deficit irrigation with weather-responsive adjustments using growth stage awareness and temperature response simultaneously | (Left blank -- needs owner decision) | HIGH | TODO -- Awaiting Decision |
| 2.7 | Market: `seasonal` -- update `adaptive` policy to include seasonal pricing patterns using historical monthly price averages | "Update adaptive policy to include seasonal pricing patterns." | MEDIUM | TODO |
| 2.11 | Market: `product_type_aware` -- update `hold_for_peak` and `adaptive` to apply logic per product type (fresh: sell immediately; dried/canned: hold strategically; packaged: intermediate). Use blended prices per product type. Add TODO note for crop-specific dynamic selling. | "Update hold_for_peak and adaptive policies to apply the logic per product type (but apply across all crops for now). Use blended prices for each product type. Add a note to TODO.md to improve the policy with crop and product specific dynamic selling behavior." | MEDIUM | TODO |
| 2.13 | Food Processing: `maximize_revenue` -- allocate harvest to pathway with highest effective revenue multiplier (`value_add * (1 - weight_loss)`), subject to capacity constraints | "Ok, implement this." | LOW | TODO |
| 2.9 | Crop: `leaching_schedule` -- periodic extra irrigation for salt flushing (10-15% mid-season, 25% between cycles). Should apply to all watering policies if critical. | "The leaching_schedule should apply to all watering policies if it is critical to preventing salt build up." | MEDIUM | TODO |
| 2.12 | Energy: `net_metering_optimized` -- feed-in tariff arbitrage when community produces more energy than needed (solar peak afternoon, wind at night, summer low-farming periods) | "Don't understand the issue here... this is proper arbitrage behavior (which will likely never happen). Feed-in tariffs should really be applied when the community produces more energy than it needs (solar peak in afternoon, wind turbines at night, etc.). This will happen in the summer when the community is not farming as much." | LOW | TODO |

---

## 6. Research and CSV Data Tasks

| Item | Description | Owner Response | Priority | Status |
|------|-------------|----------------|----------|--------|
| 3.12 | Growth stage mapping research -- define mapping from `days_since_planting` to stage per crop, update data files | "Research and update data files to include missing data as needed for policies and simulations." | MAJOR | TODO |
| 4.1 | Processing energy -> dispatch formula: `E_processing(t) = SUM(throughput_kg(t, pathway) * energy_per_kg(pathway))` -- connect to `dispatch_energy()` | "Agree" | CRITICAL | TODO |
| 4.2 | Grid electricity export price formula: `export_price_per_kwh = grid_import_price * net_metering_ratio` (default 0.70) | "Agree" | CRITICAL | TODO |
| 4.3 | Per-farm cost allocation formula -- provide all three options (equal, area-proportional, usage-proportional) as configuration in community setting | "Provide options for all three -- this is a configuration in the community setting (update all files as needed)" | CRITICAL | TODO |
| 4.4 | Fertilizer, seed, and chemical input costs -- entire `Input_cost_ha` is TBD. Check existing data files, add CSV files as needed. | "Agree, but check data files first and add csv files as needed to parameterize and expose these values" | HIGH | TODO |
| 4.5 | Food storage cost -- holding inventory currently appears cost-free. Research costs and add CSV files. | "Agree... but add csv files for each cost parameter as needed (research best guesses)" | HIGH | TODO |
| 4.6 | Currency conversion (USD/EGP) -- no conversion function exists. Mixing USD and EGP without conversion gives results wrong by ~50x. Audit all specs and code. | "Agree... have an agent look through all specs and code to ensure this is handled correctly." | HIGH | TODO |
| 4.7 | Drip irrigation pressurization energy: `E_irrigation = (P_bar * 100,000) / (eta * 3,600,000)` [kWh/m3]. At 1.5 bar, eta=0.75: ~0.056 kWh/m3. | "Agree" | HIGH | TODO |
| 4.8 | `percent_planted` parameter has no calculation. Should be: `effective_area_ha = plantable_area_ha * area_fraction * percent_planted` used everywhere. | "Agree" | HIGH | TODO |
| 4.9 | Transport cost formula missing. Research Sinai-to-market costs, add CSV file. Suggested: $0.02-0.05/kg. | "Agree, add csv file for transport costs and research as best as possible" | HIGH | TODO |
| 4.10 | Water OPEX costs per m3 -- need single opex cost for groundwater extraction (well to treatment), separate treatment opex, and irrigation opex. Add CSV files and research values. | "There should be a single opex cost per m3 for ground water extraction (from well to treatment). Treatment and irrigation also need opex costs per m3. Add csv files as needed and research values." | HIGH | TODO |
| 4.11 | Blended water cost metric: `Blended_water_cost = (total_gw_cost_yr + total_muni_cost_yr) / total_water_yr` | "Agree" | MEDIUM | TODO |
| 4.12 | LCOE intermediate calculation: `LCOE_renewable = (Annual_cost(pv) + Annual_cost(wind) + Annual_cost(battery)) / E_renewable_yr` | "Agree" | MEDIUM | TODO |
| 4.13 | Processing materials cost per kg (packaging, chemicals, cans) -- research for each product type and add CSV files | "Agree, research for each and add csv files (if not already there)" | MEDIUM | TODO |
| 4.14 | Water storage CAPEX/OPEX by type (reservoir, tank, pond) -- research and add CSV files | "Agree, research for each and add csv files (if not already there)" | MEDIUM | TODO |
| 4.15 | Household water demand formula and data. Research per-capita water demand for hot arid climate (100-200 L/day), add CSV files. | "Agree, research for each and add csv files (if not already there)" | MEDIUM | TODO |

---

## 7. Items Owner Decided to Skip/Defer

| Item | Description | Owner Response | Priority | Status |
|------|-------------|----------------|----------|--------|
| 2.2 | Energy: `microgrid` code implementation (off-grid vs grid-connected) | "Ignore for now..." | HIGH | Deferred |
| 2.5 | Energy: `battery_priority` -- aggressive battery cycling strategy | "Ignore..." | MEDIUM | Deferred |
| 2.14 | Economic: `seasonal_cash_flow` -- reserve targets adjusted by agricultural calendar | "Don't implement yet." | LOW | Deferred |
| 4.16 | PV temperature derating in dispatch formula -- already handled at Layer 1 | "Ignore, handled." | MEDIUM | Deferred |

---

## 8. Items Handled by Other Agents

| Item | Description | Status |
|------|-------------|--------|
| 1.4, 1.27e | CLAUDE.md policy counts (market 4->3, total 23 recount) | Done |
| 2.6, 2.15, 4.17, 4.18 | TODO.md updates (crop_specific food policy note, maturity_based_harvest note, Monte Carlo metrics, low-priority formula gaps) | Done |
| 2.3 | Crop: `water_stress_responsive` -- owner says remove water stress completely from all code and docs | Done |
| 2.4 | Water: `seasonal_blend` -- owner says remove seasonal water draw completely | Done |
| 2.8 | Economic: `debt_first` -- owner says remove all debt pay down policies, assume loans paid at per-month rate | Done |
| 2.10 | Water: `aquifer_responsive` -- owner says remove aquifer depletion-based policies completely, track state for resilience only | Done |
| 3.21 | `investment_allowed` output -- owner says assume opex covers all upgrades/repairs | Done |
| 5.2, 5.3, 5.4, 5.5 | New simulation flow spec file (pricing pipeline, food-market-revenue chain, energy policy integration, error handling) | Done |

---

## Summary Counts

| Category | Total Items | TODO | In Progress | Done | Deferred |
|----------|-------------|------|-------------|------|----------|
| 1. calculations.md fixes | 17 | 0 | 0 | 17 | 0 |
| 2. structure.md fixes | 9 | 0 | 0 | 9 | 0 |
| 3. policies.md fixes | 3 | 0 | 0 | 3 | 0 |
| 4. Code changes | 31 | 26 | 0 | 5 | 0 |
| 5. New policy work | 6 | 6 | 0 | 0 | 0 |
| 6. Research and CSV data | 15 | 15 | 0 | 0 | 0 |
| 7. Skipped/Deferred | 4 | 0 | 0 | 0 | 4 |
| 8. Handled by other agents | 11 | 0 | 0 | 11 | 0 |
| **Totals** | **96** | **47** | **0** | **45** | **4** |

---

*Generated from architecture-deep-review-2026-02-12.md*
