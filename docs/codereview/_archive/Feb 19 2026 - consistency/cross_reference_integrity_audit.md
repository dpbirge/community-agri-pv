# Cross-Reference Integrity Audit: specs/ Directory

**Date:** 2026-02-19
**Scope:** All 13 files in `specs/`
**Method:** Extracted every cross-reference (markdown links, file path mentions, section references), verified targets exist, checked for stale/orphaned references.

## Summary

| Status | Count |
| --- | --- |
| BROKEN | 18 |
| STALE | 5 |
| MISMATCH | 10 |
| ORPHAN | 3 |
| OK | 50+ |

---

## 1. BROKEN References

References pointing to files or sections that do not exist.

| Reference Text | Source File:Line | Target | Status | Issue Description |
| --- | --- | --- | --- | --- |
| `Section 4 (Metrics) of structure.md` | calculations.md:7 | structure.md Section 4 | BROKEN | structure.md only has Sections 1-3. Metrics were moved to `metrics_and_reporting.md`. |
| `Plot 6 in Section 5 of structure.md` | calculations.md:201 | structure.md Section 5 | BROKEN | structure.md only has Sections 1-3. Plots are now in `metrics_and_reporting.md`. |
| `docs/codereview/calculations-vs-code-review-2026-02-05.md` | calculations.md:9 | docs/codereview/ file | BROKEN | File does not exist on disk. |
| `structure.md Section 4` | simulation_flow.md:1016 | structure.md Section 4 | BROKEN | structure.md only has Sections 1-3. Should reference `metrics_and_reporting.md`. |
| `docs/planning/processed_product_research_plan.md` | calculations_crop.md:233 | docs/planning/ file | BROKEN | File does not exist on disk. |
| `docs/planning/microclimate_yield_research_plan.md` | calculations_crop.md:297 | docs/planning/ file | BROKEN | File does not exist on disk. |
| `docs/research/egyptian_water_pricing.md` | calculations_economic.md:143 | docs/research/ file | BROKEN | File does not exist on disk. |
| `docs/research/egyptian_water_pricing.md` | calculations_economic.md:197 | docs/research/ file | BROKEN | Same missing file, second reference. |
| `data/parameters/economic/equipment_lifespans.csv` | calculations_economic.md:86 | data file | BROKEN | File does not exist. Spec notes it is "to be created". |
| `data/prices/crops/historical_crop_prices-research.csv` | calculations_economic.md:229 | data file | BROKEN | No aggregate crop price file exists. Individual per-crop files exist instead (e.g., `historical_tomato_prices-research.csv`). |
| `data/prices/crops/historical_crop_prices-research.csv` | calculations_economic.md:382 | data file | BROKEN | Same missing aggregate file, second reference. |
| `data/prices/crops/historical_processed_crop_prices-research.csv` | calculations_economic.md:230 | data file | BROKEN | File does not exist. No processed crop price files exist in `data/prices/crops/`. |
| `data/prices/crops/historical_processed_crop_prices-research.csv` | calculations_economic.md:383 | data file | BROKEN | Same missing file, second reference. |
| `data/prices/water/municipal_water_prices-research.csv` | calculations_economic.md:137 | data file | BROKEN | Actual filename is `historical_municipal_water_prices-research.csv` (missing `historical_` prefix in spec). |

## 2. STALE References

References to the deleted `docs/arch/` directory.

| Reference Text | Source File:Line | Target | Status | Issue Description |
| --- | --- | --- | --- | --- |
| `docs/arch/overview.md` | data.md:772 | docs/arch/ | STALE | `docs/arch/` directory was deleted. Specs are now in `specs/`. Should reference `specs/overview.md`. |
| `docs/arch/structure.md` | data.md:773 | docs/arch/ | STALE | Same. Should reference `specs/structure.md`. |
| `docs/arch/calculations.md` | data.md:774 | docs/arch/ | STALE | Same. Should reference `specs/calculations.md`. |
| `docs/arch/policies.md` | data.md:775 | docs/arch/ | STALE | Same. Should reference `specs/policies.md`. |
| `docs/arch/simulation_flow.md` | data.md:776 | docs/arch/ | STALE | Same. Should reference `specs/simulation_flow.md`. |

## 3. Policy Name MISMATCHES in reference_settings.yaml

The `reference_settings.yaml` comment blocks and `community_policy_parameters` section use policy names that differ from those defined in `policies.md` and `structure.md`. These are grouped by domain.

### 3a. Water Policy Names

| YAML Name (reference_settings.yaml:180) | Spec Name (policies.md) | Status | Issue |
| --- | --- | --- | --- |
| `always_groundwater` | `max_groundwater` | MISMATCH | YAML comment lists `always_groundwater`; specs define `max_groundwater` |
| `always_municipal` | `max_municipal` | MISMATCH | YAML comment lists `always_municipal`; specs define `max_municipal` |

Correctly matched: `cheapest_source`, `conserve_groundwater`, `quota_enforced`

### 3b. Energy Policy Names

| YAML Name (reference_settings.yaml:181) | Spec Name (policies.md) | Status | Issue |
| --- | --- | --- | --- |
| `all_renewable` | `microgrid` | MISMATCH | YAML uses `all_renewable`; specs define `microgrid` |
| `hybrid` | `renewable_first` | MISMATCH | YAML uses `hybrid`; specs define `renewable_first` |
| `grid_first` | (none) | MISMATCH | YAML lists `grid_first`; no such policy in specs |
| `cost_minimize` | (none) | MISMATCH | YAML lists `cost_minimize`; no such policy in specs. Also used as farm_3 energy policy (line 270) and has a parameter block (line 378). |
| `cheapest_energy` | (none) | MISMATCH | YAML lists `cheapest_energy`; no such policy in specs |

Correctly matched: `all_grid`

### 3c. Food Policy Names

| YAML Name (reference_settings.yaml:182) | Spec Name (policies.md) | Status | Issue |
| --- | --- | --- | --- |
| `preserve_maximum` | `maximize_storage` | MISMATCH | YAML comment lists `preserve_maximum`; specs define `maximize_storage`. Note: the YAML `community_policy_parameters` section (line 349) correctly uses `maximize_storage`. |
| `balanced` | `balanced_mix` | MISMATCH | YAML comment lists `balanced`; specs define `balanced_mix`. Note: the YAML `community_policy_parameters` section (line 355) correctly uses `balanced_mix`. |

Correctly matched: `all_fresh`, `market_responsive`, `maximize_storage` (in parameter block), `balanced_mix` (in parameter block)

### 3d. Market Policy Names

| YAML Name (reference_settings.yaml:185) | Spec Name (policies.md) | Status | Issue |
| --- | --- | --- | --- |
| `sell_immediately` | `sell_all_immediately` | MISMATCH | YAML uses `sell_immediately`; specs define `sell_all_immediately` |

Correctly matched: `hold_for_peak`, `adaptive`

### 3e. Economic and Crop Policy Names

All economic policy names match: `balanced_finance`, `aggressive_growth`, `conservative`, `risk_averse`.
All crop policy names match: `fixed_schedule`, `deficit_irrigation`, `weather_adaptive`.

## 4. ORPHAN Files

Spec files not referenced by any other spec file.

| File | Status | Issue |
| --- | --- | --- |
| `reference_settings.yaml` | ORPHAN | Not referenced by any other file in `specs/`. Should be linked from `structure.md` or `overview.md` as the reference configuration. |
| `metrics_and_reporting.md` | ORPHAN | Not referenced by any other file in `specs/`. This file received content migrated from `structure.md` (Sections 4-5), but the referring files (`calculations.md`, `simulation_flow.md`) still point to the old locations in `structure.md`. |
| `data.md` | ORPHAN | Not referenced by any other file in `specs/`. Contains the data catalog and format specifications. Should be linked from `overview.md` or `structure.md`. |

## 5. OK Internal Links Between Spec Files

All markdown links between spec files resolve correctly.

| Reference Text | Source File | Target | Status |
| --- | --- | --- | --- |
| `[calculations_water.md](calculations_water.md)` | calculations.md | calculations_water.md | OK |
| `[calculations_energy.md](calculations_energy.md)` | calculations.md | calculations_energy.md | OK |
| `[calculations_crop.md](calculations_crop.md)` | calculations.md | calculations_crop.md | OK |
| `[calculations_economic.md](calculations_economic.md)` | calculations.md | calculations_economic.md | OK |
| `calculations_water.md Section 11` | calculations.md:9 | calculations_water.md Section 11 (Aquifer Drawdown Feedback) | OK |
| `calculations_crop.md Section 7` | calculations.md:9 | calculations_crop.md Section 7 (Crop Diversity Index) | OK |
| `policies.md` | structure.md:281+ | policies.md | OK |
| `calculations.md` | structure.md | calculations.md | OK |
| `calculations_water.md` | structure.md | calculations_water.md | OK |
| `simulation_flow.md` | structure.md:267 | simulation_flow.md | OK |
| `simulation_flow.md Section 3.3/3.4` | structure.md:267 | simulation_flow.md Section 3.3/3.4 | OK |
| `structure.md Section 3` | policies.md:96,347,462,692,791 | structure.md Section 3 (Policies) | OK |
| `structure.md Section 3.1` | policies.md:47,984 | structure.md Section 3.1 (Policy parameter wiring) | OK |
| `simulation_flow.md Section 4.4` | policies.md:386 | simulation_flow.md Section 4.4 (Capacity Clipping) | OK |
| `simulation_flow.md Section 5.4` | policies.md:611 | simulation_flow.md Section 5.4 (Dispatch Algorithm) | OK |
| `future_improvements.md` | policies.md:1042,1052 | future_improvements.md | OK |
| `future_improvements.md` | overview.md:206,382,395 | future_improvements.md | OK |
| `overview.md` | simulation_flow.md:14 | overview.md | OK |
| `overview.md Section 2` | future_improvements.md:82 | overview.md Section 2 (Model Architecture) | OK |
| `overview.md Section 3` | future_improvements.md:15,policies.md:1024,1034,1046 | overview.md Section 3 (Subsystem Specifications) | OK |
| `simulation_flow.md Section 2` | future_improvements.md:90 | simulation_flow.md Section 2 (Daily Simulation Loop) | OK |
| `simulation_flow.md Section 5` | future_improvements.md:92 | simulation_flow.md Section 5 (Energy Policy Integration) | OK |
| `simulation_flow.md Section 7.1` | future_improvements.md:205 | simulation_flow.md Section 7.1 (Monthly Boundaries) | OK |
| `simulation_flow.md Section 7.2` | future_improvements.md:50,135 | simulation_flow.md Section 7.2 (Yearly Boundaries) | OK |
| `calculations_economic.md` | calculations_water.md, calculations_crop.md, simulation_flow.md | calculations_economic.md | OK |
| `calculations_energy.md` | calculations_water.md, simulation_flow.md | calculations_energy.md | OK |
| `calculations_crop.md` | calculations_water.md | calculations_crop.md | OK |
| `calculations_economic.md Section 28` | simulation_flow.md:211 | calculations_economic.md Section 28 (Labor Calculations) | OK |
| `structure.md Section 3` | simulation_flow.md:1269 | structure.md Section 3 (Policies) | OK |

## 6. OK Data File Paths

Data file paths referenced in spec files that exist on disk.

| Data Path | Referenced From | Status |
| --- | --- | --- |
| `data/parameters/economic/financing_profiles-toy.csv` | calculations_economic.md:44,313 | OK |
| `data/prices/electricity/historical_grid_electricity_prices-research.csv` | calculations_economic.md:136, calculations_energy.md:673 | OK |
| `data/prices/electricity/historical_grid_electricity_prices_unsubsidized-research.csv` | calculations_energy.md:674 | OK |
| `data/prices/diesel/historical_diesel_prices-research.csv` | calculations_economic.md:332 | OK |
| `data/parameters/crops/processing_specs-toy.csv` | calculations_economic.md:231,384, calculations_crop.md:200,226 | OK |
| `data/parameters/crops/food_storage_costs-toy.csv` | calculations_economic.md:281 | OK |
| `data/parameters/crops/crop_coefficients-toy.csv` | calculations_economic.md:974, calculations_water.md:256, calculations_crop.md:145 | OK |
| `data/parameters/crops/crop_salinity_tolerance-toy.csv` | calculations_crop.md:111 | OK |
| `data/parameters/crops/microclimate_yield_effects-research.csv` | calculations_crop.md:333 | OK |
| `data/parameters/equipment/pump_systems-toy.csv` | calculations_water.md:75 | OK |
| `data/precomputed/water_treatment/treatment_kwh_per_m3-toy.csv` | calculations_water.md:105,123 | OK |
| `data/parameters/equipment/water_treatment-toy.csv` | calculations_water.md:124 | OK |
| `data/parameters/equipment/irrigation_systems-toy.csv` | calculations_water.md:214 | OK |
| `data/precomputed/pv_power/pv_normalized_kwh_per_kw_daily-toy.csv` | calculations_energy.md:73 | OK |
| `data/parameters/equipment/wind_turbines-toy.csv` | calculations_energy.md:129 | OK |
| `data/precomputed/wind_power/wind_normalized_kwh_per_kw_daily-toy.csv` | calculations_energy.md:135 | OK |
| `data/parameters/equipment/generators-toy.csv` | calculations_energy.md:302 | OK |
| `data/parameters/equipment/processing_equipment-toy.csv` | calculations_economic.md:729,744 | OK |
| `data/parameters/labor/labor_requirements-toy.csv` | calculations_economic.md:970 | OK |
| `data/parameters/labor/labor_wages-toy.csv` | calculations_economic.md:971 | OK |
| `docs/planning/implementation_guide.md` | overview.md | OK |
| `docs/research/aquifer_parameters.md` | calculations_water.md:452 | OK |

## 7. Recommended Fixes

### Priority 1: Fix stale docs/arch/ references in data.md

Replace lines 772-776 in `data.md`:
```
- Community Farm Model Specifications: `specs/overview.md`
- Configuration Schema: `specs/structure.md`
- Calculation Methodologies: `specs/calculations.md`
- Policy Specifications: `specs/policies.md`
- Simulation Flow: `specs/simulation_flow.md`
```

### Priority 2: Fix broken section references to structure.md

Update these references to point to `metrics_and_reporting.md`:
- `calculations.md:7` -- Change "Section 4 (Metrics) of `structure.md`" to reference `metrics_and_reporting.md`
- `calculations.md:201` -- Change "Plot 6 in Section 5 of `structure.md`" to reference `metrics_and_reporting.md`
- `simulation_flow.md:1016` -- Change "`structure.md` Section 4" to reference `metrics_and_reporting.md`

### Priority 3: Align policy names in reference_settings.yaml

Rename the policy names in comment blocks (lines 180-186) and farm policy assignments to match spec-defined names:
- `always_groundwater` -> `max_groundwater`
- `always_municipal` -> `max_municipal`
- `all_renewable` -> `microgrid`
- `hybrid` -> `renewable_first`
- `sell_immediately` -> `sell_all_immediately`
- `preserve_maximum` -> `maximize_storage`
- `balanced` -> `balanced_mix`
- Remove `grid_first`, `cost_minimize`, `cheapest_energy` from valid options comments (or add these policies to the specs)

### Priority 4: Fix broken data file path references

- `calculations_economic.md:137` -- Change `data/prices/water/municipal_water_prices-research.csv` to `data/prices/water/historical_municipal_water_prices-research.csv`
- `calculations_economic.md:229,382` -- Change `data/prices/crops/historical_crop_prices-research.csv` to list individual per-crop files (e.g., `data/prices/crops/historical_tomato_prices-research.csv`)
- `calculations_economic.md:230,383` -- Either create `data/prices/crops/historical_processed_crop_prices-research.csv` or update the reference to describe how processed prices are derived from value_add_multiplier

### Priority 5: Remove or create missing referenced files

Either create these files or remove the references:
- `docs/codereview/calculations-vs-code-review-2026-02-05.md` (referenced by calculations.md:9)
- `docs/planning/processed_product_research_plan.md` (referenced by calculations_crop.md:233)
- `docs/planning/microclimate_yield_research_plan.md` (referenced by calculations_crop.md:297)
- `docs/research/egyptian_water_pricing.md` (referenced by calculations_economic.md:143,197)
- `data/parameters/economic/equipment_lifespans.csv` (referenced by calculations_economic.md:86, noted as "to be created")

### Priority 6: Resolve orphan files

Add cross-references to these files from at least one other spec file:
- `metrics_and_reporting.md` -- Add link from `calculations.md` (where Section 4/5 references currently point to structure.md)
- `reference_settings.yaml` -- Add link from `structure.md` Section 3 as the reference configuration
- `data.md` -- Add link from `overview.md` data architecture section
