# Systematic Documentation Review Report — Specs Consistency Check

**Date:** 2026-02-19
**Scope:** 13 specification files in `specs/`, cross-referenced against `data/`, `settings/data_registry.yaml`, and `specs/reference_settings.yaml`
**Method:** 5 parallel review agents, each covering one review dimension

---

## 1. Executive Summary

**Overall documentation quality: GOOD with significant fixable issues.**

The 13 spec files form a comprehensive, well-structured specification set. The calculation split is clean (63/63 sections indexed, zero duplication), the data infrastructure is solid (72/72 registry entries resolve, 97 CSV files all accounted for), and the simulation flow pseudocode is implementable. However, a single systemic problem -- **`reference_settings.yaml` policy names diverge from canonical names in `policies.md` and `structure.md`** -- creates confusion across multiple domains and would block a developer from wiring up configuration correctly.

### Top 10 Critical Findings

| # | Severity | Finding |
|---|----------|---------|
| 1 | CRITICAL | **Energy policy names in `reference_settings.yaml` are completely misaligned** with `policies.md`. The YAML uses `all_renewable`, `hybrid`, `cost_minimize`, `cheapest_energy`, `grid_first` -- none of which exist in the spec. The spec defines `microgrid`, `renewable_first`, `all_grid`. Two of three example farms use invalid energy policy names. |
| 2 | CRITICAL | **Crop and market policies are not assignable per-farm** in `reference_settings.yaml`. The YAML has no `policies.crop` or `policies.market` key in any farm block. A comment says these are "set under community_policy_parameters, not per-farm" -- contradicting `policies.md` and `structure.md` which say all 6 domains are per-farm. |
| 3 | CRITICAL | **`metrics_and_reporting.md` is an orphan** -- not referenced by any other spec file. Meanwhile, `calculations.md` and `simulation_flow.md` still reference `structure.md` Section 4 (Metrics) and Section 5 (Plots) which no longer exist (content was migrated to `metrics_and_reporting.md`). |
| 4 | HIGH | **10 policy name mismatches** between `reference_settings.yaml` and `policies.md`/`structure.md`: `always_groundwater`/`always_municipal` (water), `all_renewable`/`hybrid`/`grid_first`/`cost_minimize`/`cheapest_energy` (energy), `preserve_maximum`/`balanced` (food), `sell_immediately` (market). |
| 5 | HIGH | **5 stale `docs/arch/` references** in `data.md` lines 772-776 point to a deleted directory. Should reference `specs/`. |
| 6 | HIGH | **4 undocumented energy policies** (`cost_minimize`, `cheapest_energy`, `grid_first`, `all_renewable`) have parameters and are used by example farms but have no specification in `policies.md` or `structure.md`. |
| 7 | HIGH | **SimulationState dataclass definitions missing** -- the complete field list, types, and initial values for the 5-6 core state dataclasses are scattered across multiple files with no consolidated specification. This is the single largest gap blocking implementation. |
| 8 | HIGH | **15+ `reference_settings.yaml` fields marked "Not parsed by loader"** including critical simulation parameters (`conveyance_kwh_per_m3`, `max_runtime_hours`, `net_metering_ratio`, `cost_allocation_method`, all `annual_escalation_pct` fields, community_buildings). No alternative access path documented. |
| 9 | MODERATE | **5 data file paths in `calculations_economic.md` are broken** -- references to generic filenames (`historical_crop_prices-research.csv`) when actual files are per-crop, missing `historical_` prefix on water price file, and an `equipment_lifespans.csv` noted as "to be created". |
| 10 | MODERATE | **Food processing policy fractions**: `policies.md` presents splits as hardcoded fixed percentages, while `reference_settings.yaml` makes them configurable via `community_policy_parameters`. Inconsistent design intent. |

---

## 2. Cross-Reference Integrity (Agent 1)

### Summary

| Status | Count |
|--------|-------|
| BROKEN | 14 unique targets (18 occurrences) |
| STALE | 5 |
| ORPHAN files | 3 |
| OK | 50+ |

### Broken References

**Section references to migrated content:**
- `calculations.md:7` -- "Section 4 (Metrics) of `structure.md`" -- section no longer exists (moved to `metrics_and_reporting.md`)
- `calculations.md:201` -- "Plot 6 in Section 5 of `structure.md`" -- same issue
- `simulation_flow.md:1016` -- "`structure.md` Section 4" -- same issue

**Documentation files that don't exist:**
- `docs/codereview/calculations-vs-code-review-2026-02-05.md` (referenced by `calculations.md:9`)
- `docs/planning/processed_product_research_plan.md` (referenced by `calculations_crop.md:233`)
- `docs/planning/microclimate_yield_research_plan.md` (referenced by `calculations_crop.md:297`)
- `docs/research/egyptian_water_pricing.md` (referenced by `calculations_economic.md:143,197`)

**Data file path errors:**
- `data/parameters/economic/equipment_lifespans.csv` -- missing `-toy` suffix
- `data/prices/crops/historical_crop_prices-research.csv` -- aggregate file doesn't exist; per-crop files do
- `data/prices/crops/historical_processed_crop_prices-research.csv` -- doesn't exist
- `data/prices/water/municipal_water_prices-research.csv` -- missing `historical_` prefix

### Stale References

`data.md` lines 772-776 still point to `docs/arch/overview.md`, `docs/arch/structure.md`, etc. The `docs/arch/` directory was deleted; these specs are now in `specs/`.

### Orphan Files

Three spec files are not referenced by any other spec:
1. **`metrics_and_reporting.md`** -- received migrated content from `structure.md` but no referring files were updated
2. **`reference_settings.yaml`** -- the reference configuration file is never linked from `structure.md`
3. **`data.md`** -- the data catalog is never linked from `overview.md` or other specs

---

## 3. Policy Consistency (Agent 2)

### Summary

The policy domain has the most severe consistency issues. Energy policies are almost entirely misaligned between `reference_settings.yaml` and the spec files.

### Policy Name Mismatches by Domain

#### Water (2 mismatches)

| YAML Name | Canonical Name | Issue |
|-----------|---------------|-------|
| `always_groundwater` | `max_groundwater` | Name mismatch |
| `always_municipal` | `max_municipal` | Name mismatch |

#### Energy (7 mismatches -- worst domain)

| YAML Name | Canonical Name | Issue |
|-----------|---------------|-------|
| `all_renewable` | `microgrid` (probable) | Used by farm_2, has parameters, but no spec exists |
| `hybrid` | `renewable_first` (probable) | Listed as valid option, no spec |
| `grid_first` | (none) | Listed as valid option, no spec anywhere |
| `cost_minimize` | (none) | Used by farm_3, has parameters, no spec |
| `cheapest_energy` | (none) | Listed as valid option, no spec |
| `microgrid` | (not in YAML) | Spec-defined but not listed in YAML valid options |
| `renewable_first` | (not in YAML) | Spec-defined but not listed in YAML valid options |

#### Food (2 mismatches)

| YAML Name | Canonical Name | Issue |
|-----------|---------------|-------|
| `preserve_maximum` | `maximize_storage` | Name mismatch in valid options comment |
| `balanced` | `balanced_mix` | Name mismatch in valid options comment |

#### Market (1 mismatch)

| YAML Name | Canonical Name | Issue |
|-----------|---------------|-------|
| `sell_immediately` | `sell_all_immediately` | Name mismatch |

### Structural Conflicts

1. **Crop/market policy assignment**: `reference_settings.yaml` has no `policies.crop` or `policies.market` key in farm blocks. Comments say these are community-level. `policies.md` and `structure.md` say all 6 domains are per-farm.

2. **`min_water_quality` status**: Commented out in YAML with "not in WATER_POLICIES registry yet" but fully specified in `policies.md` and listed in `structure.md` policy table.

### Undocumented Parameters

| Policy | Parameter | Location |
|--------|-----------|----------|
| `aggressive_growth` | `max_inventory_months` | YAML only -- not in `policies.md` or `structure.md` |
| `all_renewable` | `battery_reserve_fraction` | YAML only -- policy doesn't exist in specs |
| `cost_minimize` | `battery_reserve_grid_cheap` | YAML only -- policy doesn't exist in specs |
| `cost_minimize` | `battery_reserve_renewable_cheap` | YAML only -- policy doesn't exist in specs |

### Parameterization Inconsistencies

Food processing splits (`maximize_storage`, `balanced_mix`, `market_responsive`) and crop policy thresholds (`weather_adaptive`) are presented as **hardcoded fixed values** in `policies.md` pseudocode but exposed as **configurable parameters** in `reference_settings.yaml`. The spec and YAML have different design intents.

---

## 4. Data Completeness (Agent 3)

### Summary

The data layer is in excellent condition. No critical issues.

| Category | Count |
|----------|-------|
| CSV files on disk | 97 (+2 templates) |
| Registry entries | 72 active |
| Registry -> disk resolution | 72/72 (100%) |
| True orphan files | 0 |

### Issues Found

**Moderate (3):**

| # | Issue | Location |
|---|-------|----------|
| M1 | `calculations_economic.md` references `equipment_lifespans.csv` without `-toy` suffix | Sec 2, Dependencies |
| M2 | `calculations_economic.md` references non-existent generic filenames `historical_crop_prices-research.csv` and `historical_processed_crop_prices-research.csv` -- actual files are per-crop | Sec 5, 10 |
| M3 | `financing_profiles-toy.csv` uses non-standard metadata header format | Header format |

**Minor (2):**

| # | Issue | Location |
|---|-------|----------|
| m1 | `calculations_economic.md` Sec 3 references `municipal_water_prices-research.csv` without `historical_` prefix | Sec 3 Dependencies |
| m2 | `data.md` crop coefficients example shows `season_length_days=130` for tomato; actual file and `simulation_flow.md` both use 135 | data.md example |

### Header/Column Verification (15-file sample)

All 15 sampled files pass column verification against spec expectations. 14/15 use the standard metadata header format (SOURCE, DATE, DESCRIPTION, UNITS, LOGIC, DEPENDENCIES). One file (`financing_profiles-toy.csv`) uses a non-standard format.

### Registry Completeness

Registry is 100% complete relative to spec requirements in `data.md`. All 18 registry sections have all expected keys.

---

## 5. Calculation Split Quality (Agent 4)

### Summary

**The calculation split is well-executed and consistent.** This is the strongest area of the spec documentation.

| Metric | Result |
|--------|--------|
| Sections indexed | 63/63 (100%) |
| Orphaned index entries | 0 |
| Duplicate formulas across files | 0 |
| Misplaced content | 0 |
| Cross-reference errors between domain files | 0 |
| Inbound reference errors from other specs | 1 (minor) |

### Domain File Coverage

| Domain File | Sections | All in Index? |
|-------------|----------|---------------|
| `calculations_water.md` | 14 | Yes |
| `calculations_energy.md` | 13 (+1 subsection) | Yes |
| `calculations_crop.md` | 8 | Yes |
| `calculations_economic.md` | 28 (incl. labor subsections) | Yes |

### Non-Domain Content in Index

The index file correctly houses content that doesn't belong in any domain file:
- Resilience/Monte Carlo calculations (Section 3)
- Sensitivity analysis framework
- Units and conversions (Section 4)
- Consolidated references (Section 5)

None of this content is duplicated in domain files.

### Single Minor Issue

`policies.md` references "calculations.md" for the FAO-33 formula, but the formula is in `calculations_crop.md` Section 1. The index is a valid entry point but less precise.

---

## 6. Implementation Readiness (Agent 5)

### Confidence Scores by Area

| Area | Score | Assessment |
|------|:-----:|------------|
| **Layer 1: Weather generator** | 3/5 | Synthetic generation algorithm undocumented |
| **Layer 1: PV power calculator** | 4/5 | Simplified model documented; tilt factor derivation implicit |
| **Layer 1: Wind power calculator** | 3/5 | Power curve integration not specified |
| **Layer 1: Irrigation demand** | 4/5 | ET0 formula delegated to FAO-56 reference |
| **Layer 1: Crop yield calculator** | 4/5 | Y_potential baseline values not specified |
| **Layer 1: Household/building demand** | 3/5 | Demand model not in specs |
| **Layer 2: YAML schema** | 5/5 | Complete with reference file |
| **Layer 2: Data registry** | 5/5 | Comprehensive with naming conventions |
| **Layer 2: Scenario validation** | 4/5 | Validation rules implicit |
| **Layer 2: System constraints** | 4/5 | Simple division documented |
| **Layer 2: Infrastructure costs** | 5/5 | Complete formulas and financing profiles |
| **Layer 3: SimulationState** | 3/5 | No consolidated dataclass specification |
| **Layer 3: Daily loop** | 5/5 | Complete step-by-step pseudocode |
| **Layer 3: State transitions** | 4/5 | Well-documented; minor gaps |
| **Layer 3: Crop state machine** | 5/5 | Exemplary specification |
| **Layer 3: StorageTranche/FIFO** | 5/5 | Complete with pseudocode |
| **Layer 3: Energy dispatch** | 5/5 | Complete for all 3 policies |
| **Data contracts** | 4/5 | File formats documented; loader API not specified |
| **Output format** | 3/5 | Metrics listed but CSV/JSON structure undefined |
| **Plots and tables** | 4/5 | 6 plots + 2 tables described; data transforms not fully specified |
| **Monte Carlo** | 4/5 | Algorithm complete; weather variation missing |
| **Sensitivity analysis** | 5/5 | Fully specified |
| **Deferred features tracking** | 3/5 | 6+ deferred features missing from `future_improvements.md` |

**Strongest areas (5/5):** YAML schema, data registry, infrastructure costs, daily loop, crop state machine, StorageTranche/FIFO, energy dispatch, sensitivity analysis.

**Weakest areas (3/5):** Weather generator, wind power calculator, household demand, SimulationState definitions, output format specification, deferred features tracking.

### Missing from `future_improvements.md`

These features are described as deferred elsewhere in the specs but have no entry in `future_improvements.md`:
1. Insurance policies (crop insurance, equipment insurance) -- referenced in `policies.md`
2. Community-override policy scope -- referenced in `structure.md`
3. Harvest scheduling optimization -- referenced in `simulation_flow.md`
4. PV microclimate yield protection (TBD) -- referenced in `calculations_crop.md`
5. Equipment failure events -- data exists but simulation not specified
6. Aquifer drawdown feedback -- noted as "pending code implementation" in `calculations.md`

### Top Implementation-Blocking Gaps

1. **SimulationState dataclass definitions** -- fields, types, and initial values are scattered with no consolidated spec
2. **Policy name inconsistency** -- developer cannot know which names the loader should accept
3. **"Not parsed by loader" fields** -- 15+ critical parameters have no documented access path
4. **ET0 computation formula** -- foundation of irrigation calculations, not reproduced in specs
5. **Y_potential baseline yield values** -- yield precomputed file appears empty (header-only)

---

## 7. Prioritized Action Items

### CRITICAL (Must fix before implementation)

| # | Action | Files to Update | Effort |
|---|--------|----------------|--------|
| C1 | **Align all energy policy names** -- either add specs for `all_renewable`, `cost_minimize`, `cheapest_energy`, `grid_first`, `hybrid` to `policies.md`/`structure.md`, OR update `reference_settings.yaml` to use only `microgrid`, `renewable_first`, `all_grid` | `reference_settings.yaml`, possibly `policies.md`, `structure.md` | Medium |
| C2 | **Resolve crop/market policy assignment** -- add `policies.crop` and `policies.market` keys to farm blocks in YAML, OR document community-level assignment in `policies.md`/`structure.md` | `reference_settings.yaml`, `policies.md`, `structure.md` | Small |
| C3 | **Fix metrics/plots section references** -- update `calculations.md:7,201` and `simulation_flow.md:1016` to reference `metrics_and_reporting.md` instead of `structure.md` Section 4/5 | `calculations.md`, `simulation_flow.md` | Small |
| C4 | **Add consolidated SimulationState specification** -- define all dataclass fields, types, and initial values in one location (e.g., new section in `simulation_flow.md` or `structure.md`) | `simulation_flow.md` or `structure.md` | Medium |

### IMPORTANT (Should fix soon)

| # | Action | Files to Update | Effort |
|---|--------|----------------|--------|
| I1 | **Rename water policy names** in YAML: `always_groundwater` -> `max_groundwater`, `always_municipal` -> `max_municipal` | `reference_settings.yaml` | Small |
| I2 | **Rename food/market policy names** in YAML: `preserve_maximum` -> `maximize_storage`, `balanced` -> `balanced_mix`, `sell_immediately` -> `sell_all_immediately` | `reference_settings.yaml` | Small |
| I3 | **Fix stale `docs/arch/` references** in `data.md` lines 772-776 to point to `specs/` | `data.md` | Small |
| I4 | **Link orphan files** -- add references to `metrics_and_reporting.md`, `reference_settings.yaml`, and `data.md` from other spec files | `structure.md`, `overview.md`, `calculations.md` | Small |
| I5 | **Resolve "Not parsed by loader" fields** -- either document how these parameters reach the simulation or mark them as future enhancements | `reference_settings.yaml`, `structure.md` | Medium |
| I6 | **Fix broken data file paths** in `calculations_economic.md` -- update to per-crop filenames, add `historical_` prefix, add `-toy` suffix | `calculations_economic.md` | Small |
| I7 | **Resolve food policy parameterization design** -- decide whether processing splits are fixed or configurable; align `policies.md` pseudocode with `reference_settings.yaml` | `policies.md` or `reference_settings.yaml` | Small |
| I8 | **Document `max_inventory_months`** parameter in `policies.md` for `aggressive_growth`, or remove from YAML | `policies.md` or `reference_settings.yaml` | Small |
| I9 | **Add missing deferred features** to `future_improvements.md` -- insurance, community-override, harvest scheduling, microclimate TBD, equipment failures, aquifer drawdown | `future_improvements.md` | Small |

### MINOR (Fix when convenient)

| # | Action | Files to Update | Effort |
|---|--------|----------------|--------|
| m1 | Update `policies.md` FAO-33 reference from `calculations.md` to `calculations_crop.md` | `policies.md` | Trivial |
| m2 | Fix `data.md` tomato season length example (130 -> 135) | `data.md` | Trivial |
| m3 | Reformat `financing_profiles-toy.csv` header to standard metadata format | Data file | Small |
| m4 | Create or remove broken doc references: `docs/codereview/calculations-vs-code-review-2026-02-05.md`, `docs/planning/processed_product_research_plan.md`, `docs/planning/microclimate_yield_research_plan.md`, `docs/research/egyptian_water_pricing.md` | Various | Small |
| m5 | Clarify `min_water_quality` status -- uncomment in YAML or add deferral note to `policies.md` | `reference_settings.yaml` or `policies.md` | Trivial |

---

*Generated by 5-agent parallel documentation review. See individual agent reports for detailed tables and evidence.*
