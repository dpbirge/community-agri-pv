# Systematic Documentation Review Report

**Date:** 2026-02-18
**Scope:** 6 architecture docs (`docs/arch/`) reviewed against 99 data files (`data/`), data registry (`settings/data_registry.yaml`), and each other.
**Methodology:** 5 parallel review agents examining data completeness, simulation flow, policy framework, calculation consistency, and implementation sufficiency. Code in `src/` was intentionally NOT referenced.
**Question:** "Could a competent developer implement the full simulation from these docs and data files alone?"

---

## 1. Executive Summary

**Overall documentation quality: 3.6/5** — Strong foundation covering ~80% of implementation needs. The core systems (energy dispatch, water policies, food processing chain, StorageTranche/FIFO) are exceptionally well-documented. Gaps cluster in Layer 1 generation algorithms, state management schemas, crop lifecycle logic, daily cost formulas, and cross-document consistency.

### Top 10 Critical Findings

| # | Finding | Source |
|---|---------|--------|
| 1 | **Post-harvest loss formula contradicts weight-loss-per-pathway model** — calculations.md applies 10% fresh loss; simulation_flow.md says losses are only via per-pathway weight loss (fresh = 0%) | Agents 2, 4 |
| 2 | **YAML-to-policy parameter wiring undocumented** — No specification for how configurable policy parameters flow from scenario YAML through loader to policy constructor | Agent 3 |
| 3 | **SimulationState dataclass has no unified schema** — Fields scattered across all 6 docs; no single specification of all fields, types, and initial values | Agent 5 |
| 4 | **E_irrigation_pump (0.056 kWh/m3) has no derivation in calculations.md** — Hardcoded constant in simulation_flow.md with no formula or section in calculations.md | Agents 2, 4 |
| 5 | **Daily storage costs absent from calculations.md** — simulation_flow.md Step 7 deducts daily storage costs but calculations.md has no formula or rate table | Agent 4 |
| 6 | **Daily labor cost formula missing** — Labor is annual aggregates in calculations.md but listed as daily cost in simulation_flow.md Step 7 | Agents 2, 4 |
| 7 | **Crop state machine fragmented across docs** — Planting → growth stages → harvest → fallow → replanting never specified as unified algorithm | Agents 2, 5 |
| 8 | **Battery discharge efficiency direction inconsistent** — simulation_flow.md multiplies by eta; calculations.md divides by eta | Agent 4 |
| 9 | **Generator minimum load behavior contradicts between docs** — calculations.md says don't start below minimum; simulation_flow.md says always start at minimum | Agent 4 |
| 10 | **E_community_bldg missing from calculations.md total demand formula** — 7 components in simulation_flow.md but only 6 in calculations.md | Agents 2, 4 |

---

## 2. Data Completeness (Agent 1)

### Summary

- **99 CSV files on disk, 79 registry entries** — All registry paths resolve to existing files
- **3 planned datasets now created** (salinity tolerance, equipment lifespans, storage costs)
- **20 unregistered files** — All are research/toy alternates or templates (no genuinely orphaned files)
- **2 metadata compliance issues** — `nimbalyst` editor artifacts in 2 files

### File Reference Mismatches

| File Reference | Source Doc | Issue |
|---|---|---|
| `settings/mvp-settings.yaml` | data.md (3 places) | File is `settings.yaml` on disk |
| `data/parameters/water/pump_equipment_parameters.csv` | calculations.md | Stale path — actual: `data/parameters/equipment/pump_systems-toy.csv` |
| `data/parameters/energy/generator_parameters.csv` | calculations.md | Stale path — actual: `data/parameters/equipment/generators-toy.csv` |
| `data/parameters/crops/crop_salinity_tolerance.csv` | calculations.md | Missing `-toy` suffix |
| `data/parameters/water/aquifer_parameters.md` | calculations.md | Wrong path — actual: `docs/research/aquifer_parameters.md` |
| `docs/research/egyptian_utility_pricing.md` | calculations.md | File does not exist |

### data.md Inventory Inaccuracies

| Issue | Details |
|---|---|
| Processed product count | Doc says "10 products" but 16 exist on disk and in registry |
| `microclimate_yield_effects` registry status | Doc says "(not in registry)" but it IS registered |
| `fertilizer_costs` registry status | Doc says "(not in registry)" but it IS registered |
| PV power format example | Doc omits `density_variant` column that exists in actual file |
| Irrigation format example | Doc omits `calendar_date` and `etc_mm` columns |
| Planned datasets section | All 3 planned datasets have been created — section should be updated or removed |

### Column/Unit Verification

All major data categories match doc specifications. Actual files are generally supersets (additional useful columns) of the documented minimum. Units are consistent across all files (kWh, m3, kg, USD, ha).

---

## 3. Flow Completeness (Agent 2)

### Subsystem Coverage

| Subsystem | Status | Notes |
|---|---|---|
| Water (extraction → irrigation) | Complete | Storage balance update not shown in pseudocode (MINOR) |
| Energy (generation → dispatch) | Excellent | All 3 policies fully specified with pseudocode |
| Crop growth | **Gaps** | State machine fragmented; harvest trigger undefined |
| Food processing chain | Excellent | FIFO, forced sales, revenue calc all fully specified |
| Economic tracking | Adequate | Daily debt service formula not shown (cross-ref only) |
| Household/community demand | Good | Section 8 is thorough |
| Labor | **Gap** | No daily computation step; annual aggregates only |

### Ordering Assessment

All documented dependencies are correctly ordered in the daily loop:
- Crop → Water → Energy → Food → Market → Economic (monthly) ✓
- Processing energy one-day lag correctly documented ✓
- Forced sales before voluntary sales ✓

### Energy-Water Nexus

| Best Practice | Status |
|---|---|
| Water-energy coupling direction | Correct (one-directional: water → energy demand) |
| All 7 demand components listed | Correct in simulation_flow.md; only 6 in calculations.md |
| Merit-order dispatch per policy | Fully specified for all 3 variants |
| Battery SOC tracking | **IMPORTANT**: Self-discharge absent; EFC accumulator for degradation not shown |
| Aquifer drawdown feedback | Correctly documented with positive feedback loop |
| Grid export revenue / net metering | Correctly modeled |

### Critical Flow Gaps

| ID | Finding | Severity |
|---|---------|----------|
| F-1 | Post-harvest loss vs weight-loss-per-pathway contradiction | CRITICAL |
| F-2 | E_community_bldg missing from calculations.md demand formula | CRITICAL |
| F-3 | Crop growth stage state machine not algorithmically specified | IMPORTANT |
| F-4 | Harvest triggering condition never explicitly defined | IMPORTANT |
| F-5 | Planting date edge cases (mid-year start, overlapping cycles) unspecified | IMPORTANT |
| F-6 | Battery self-discharge absent from dispatch and boundary ops | IMPORTANT |
| F-7 | Equipment replacement costs missing from yearly boundary ops | IMPORTANT |
| F-8 | Labor has no daily computation step | IMPORTANT |
| F-9 | Conveyance energy potential double-counting between water policy output and dispatch | IMPORTANT |
| F-10 | CAPEX initial outflow not shown in pre-loop (needed for IRR/NPV) | IMPORTANT |

---

## 4. Policy Extensibility (Agent 3)

### Per-Domain Assessment

| Domain | Pattern | Context | Decision | Factory | Data Deps | Issues |
|--------|---------|---------|----------|---------|-----------|--------|
| Water | ✓ | ✓ (16 fields) | ✓ (6 fields) | ✓ | Partial | `conserve_groundwater` adds `limiting_factor` beyond schema |
| Energy | ✓ | ✓ (8 fields) | ✓ (8 fields) | ✓ | Partial | No data file refs; dispatch handled externally |
| Crop | ✓ | ✓ (7 fields) | ✓ (3 fields) | ✓ | None | No data file deps listed |
| Food | ✓ | ✓ (6 fields) | ✓ (5 fields) | ✓ | Partial | Reference price source mentioned but not mapped |
| Market | ✓ | ✓ (8 fields) | ✓ (4 fields) | ✓ | Good | `avg_price_per_kg` well-documented |
| Economic | ✓ | ✓ (7 fields) | ✓ (3 fields) | ✓ | None | Runtime state only |

### Extensibility Verdict

A developer can understand WHAT each policy does (context fields, decision fields, pseudocode, error handling). They CANNOT implement the integration scaffolding from docs alone:

- Factory function registration mechanism: **Not documented**
- YAML parameter wiring: **Not documented**
- Scenario validation updates: **Not documented**
- Test patterns: **Not documented**

### overview.md vs policies.md Gap

Features described in overview.md but absent from policies.md:

| Feature | overview.md Section | policies.md Status |
|---------|--------------------|--------------------|
| Insurance policies | Section 3 (detailed) | Absent entirely |
| Collective pooling mechanism | Line 193 | Not specified as policy |
| Community-override policies | All domains claim support | No schema, logic, or pseudocode |
| Load management / load shifting | Energy policies | Not implemented |
| Crop type selection / planting optimization | Crop policies | Not governed by any policy |
| Working capital advance rules | Economic policies | Not specified |
| Gradual spoilage model (rate %/day) | Food processing | Replaced by binary shelf-life model |

---

## 5. Calculation Consistency (Agent 4)

### Formula Status Summary

| Calculation Area | Status | Notes |
|---|---|---|
| Groundwater pumping energy | Complete | Friction losses included; worked example correct |
| Water treatment (BWRO) | Complete | Categorical lookup documented with TDS ranges |
| Water conveyance | Complete | Fixed 0.2 kWh/m3 for MVP |
| Irrigation demand (FAO) | Complete | ET0 referenced but not reproduced |
| PV generation | Complete | Precomputed vs runtime ambiguity (see below) |
| Wind power | Partial | Power curve application not specified |
| Battery dynamics | Complete | SOC, efficiency, degradation models present |
| Generator fuel (Willans line) | Complete | Coefficients match data file |
| Harvest yield (FAO-33) | Complete | Water stress + salinity models |
| Food processing weight loss | Complete | Per-pathway formulas present |
| Debt service / amortization | Complete | Standard formula, parameters documented |
| LCOE | Complete | Full specification |
| NPV, IRR, ROI, payback | Complete | Standard financial formulas |
| E_irrigation_pump | **Missing** | Hardcoded 0.056 in flow; no section in calculations.md |
| Daily storage costs | **Missing** | Referenced in flow; absent from calculations.md |
| Daily labor costs | **Missing** | Annual aggregates only |
| Household/community demand | **Missing** | No generation algorithm |
| E_community_bldg | **Missing** | No section in calculations.md |

### Cross-Document Inconsistencies

| ID | Issue | Severity |
|---|-------|----------|
| C-1 | Post-harvest loss: 10% fresh (calculations.md) vs 0% weight loss (simulation_flow.md) | CRITICAL |
| C-2 | Battery discharge: `* eta` (flow) vs `/ eta` (calculations) | IMPORTANT |
| C-3 | Generator min load: don't start (calculations) vs always start (flow) | IMPORTANT |
| C-4 | Battery SOC_min=0.10 (calculations) vs battery_reserve_pct=0.20 (policies) — relationship unclear | IMPORTANT |
| C-5 | Blended electricity cost includes LCOE_renewable (economic); dispatch cost is cash-only — distinction not clarified | IMPORTANT |
| C-6 | Fresh revenue formula includes `(1-loss_rate)` in calculations.md but not in simulation_flow.md | IMPORTANT |
| C-7 | Salinity yield reduction in calculations.md but absent from simulation_flow.md harvest formula | IMPORTANT |
| C-8 | Total energy demand: 6 components (calculations) vs 7 (flow) — E_community_bldg missing | IMPORTANT |
| C-9 | E_treatment (calculations) vs E_desal (flow) naming inconsistency | MINOR |

### TBD Sections Blocking Implementation

| Section | Impact |
|---------|--------|
| Fertilizer and Input Costs | Total OPEX incomplete without this |
| Community vs External Labor Ratio | Optional metric |
| Weather scenario variation in Monte Carlo | MC runs without it |
| Breakeven thresholds | Optional analysis |

---

## 6. Implementation Readiness (Agent 5)

### Confidence Scores by Area

| Area | Score | Assessment |
|------|:-----:|------------|
| **Layer 1: Weather generator** | 2/5 | Algorithm in CSV headers only, not in arch docs |
| **Layer 1: PV power calculator** | 3/5 | Precomputed vs runtime ambiguity |
| **Layer 1: Wind power calculator** | 3/5 | Power curve application missing |
| **Layer 1: Irrigation demand** | 4/5 | FAO-56 referenced but ET0 equation not reproduced |
| **Layer 1: Crop yield calculator** | 3/5 | Y_potential generation method missing |
| **Layer 1: Household/building demand** | 2/5 | Generation algorithm missing |
| **Layer 2: YAML schema** | 4/5 | Working example; no formal schema |
| **Layer 2: Data registry** | 5/5 | Fully self-documenting |
| **Layer 2: Scenario validation** | 3/5 | No complete rule set |
| **Layer 2: System constraints** | 4/5 | Conceptually clear; exact API unspecified |
| **Layer 2: Infrastructure costs** | 5/5 | Fully specified |
| **Layer 3: SimulationState** | 2/5 | Fields scattered across all docs |
| **Layer 3: Daily loop** | 4/5 | Comprehensive pseudocode |
| **Layer 3: Crop state machine** | 2/5 | Fragmented across docs |
| **Layer 3: StorageTranche/FIFO** | 5/5 | Complete pseudocode |
| **Layer 3: Energy dispatch** | 5/5 | Exceptionally well-documented |
| **Layer 3: All policies** | 5/5 | Complete pseudocode for all 22 |
| **Data contracts** | 4/5 | Comprehensive mapping tables |
| **Output format** | 2/5 | Metrics listed; file/plot structure unspecified |
| **Monte Carlo** | 4/5 | Algorithm specified; some features flagged |
| **Sensitivity analysis** | 5/5 | Fully specified |

### Key Developer Questions (Unanswered in Docs)

**Design decisions needed:**
1. SimulationState dataclass — complete field/type/initial-value schema
2. Crop lifecycle state machine — planting → growth → harvest → fallow → replanting transitions
3. Results output format — CSV/JSON file structure, column names, organization
4. SimulationDataLoader API — return types, caching, lookup interface
5. Year-boundary crops — what happens to crops planted in December?
6. Energy policy conflict — farm vs household (flagged for owner in simulation_flow.md 10.3)

**Formulas missing:**
7. ET0 (reference evapotranspiration) — FAO-56 referenced but not reproduced
8. Y_potential generation — how base potential yields are computed in Layer 1
9. Weather data generation — AR(1) parameters only in CSV metadata
10. Household energy/water demand — no generation algorithm
11. Wind power curve application — speed → capacity factor conversion
12. Daily labor cost — how to derive from annual aggregates

**Ambiguous specifications:**
13. PV output scaling — does precomputed data include temp derating? (CSV says yes; calculations.md applies it at runtime)
14. Post-harvest loss vs weight loss — which model applies? (see Critical Finding #1)
15. `percent_planted` interaction with sequential cropping planting dates
16. Market policy `avg_price_per_kg` — rolling 12-month mean from what reference point?
17. Battery self-discharge — documented but noted as "can be omitted for MVP"

---

## 7. Prioritized Action Items

### CRITICAL (7 items) — Blocks correct implementation

| # | Action | Documents Affected |
|---|--------|--------------------|
| 1 | **Resolve post-harvest loss contradiction.** Decide whether fresh produce has a 10% handling loss (calculations.md) or 0% loss (simulation_flow.md weight-loss model). Update the superseded document. | calculations.md, simulation_flow.md |
| 2 | **Add E_irrigation_pump section to calculations.md.** Document the derivation: P = (1.5 bar × 100000 Pa) / (0.75 × 3.6e6 J/kWh) = 0.056 kWh/m3. | calculations.md |
| 3 | **Add daily storage cost formula to calculations.md.** Include rate table reference and Total OPEX integration. | calculations.md |
| 4 | **Add daily labor cost formula.** Specify how annual labor estimates translate to daily costs (fixed daily rate? harvest-day multiplier?). | calculations.md, simulation_flow.md |
| 5 | **Add E_community_bldg to calculations.md total demand formula.** Update from 6 to 7 components. | calculations.md |
| 6 | **Document YAML-to-policy parameter wiring.** Specify how configurable policy parameters are structured in YAML, extracted by loader, and injected into policy constructors. | structure.md or policies.md |
| 7 | **Write unified SimulationState schema.** Single document/section listing all dataclass fields, types, initial values for SimulationState, FarmState, CropState, AquiferState, EnergyState, EconomicState. | simulation_flow.md or new doc |

### IMPORTANT (15 items) — Causes incorrect results or significant developer confusion

| # | Action | Documents Affected |
|---|--------|--------------------|
| 8 | **Standardize battery discharge efficiency.** Choose `* eta` or `/ eta` and update inconsistent doc. | simulation_flow.md, calculations.md |
| 9 | **Resolve generator minimum load behavior.** Update calculations.md to match simulation_flow.md resolved behavior (always start, run at minimum). | calculations.md |
| 10 | **Clarify SOC_min (0.10 hardware) vs battery_reserve_pct (0.20 policy) relationship.** Add note that effective floor = max(SOC_min, battery_reserve_pct). | calculations.md, simulation_flow.md |
| 11 | **Write crop state machine specification.** Unified algorithm: planting date resolution, growth stage tracking, harvest trigger, fallow → replanting, year-boundary handling. | simulation_flow.md |
| 12 | **Add battery EFC accumulator to daily loop.** Needed for cycle-based degradation model at yearly boundary. | simulation_flow.md |
| 13 | **Add battery self-discharge to dispatch or explicitly exclude.** Currently documented in calculations.md but absent from flow. | simulation_flow.md |
| 14 | **Add equipment replacement costs to yearly boundary operations.** Sinking fund reserve or discrete replacement events. | simulation_flow.md |
| 15 | **Clarify conveyance energy source.** Is E_convey decomposed from water policy output or independently computed by dispatch? Prevent double-counting. | simulation_flow.md |
| 16 | **Add CAPEX initial outflow to pre-loop initialization.** Required for IRR/NPV computation. | simulation_flow.md |
| 17 | **Clarify blended cost vs cash cost distinction.** Note that dispatch cost is cash; LCOE-inclusive cost is economic metric only. | calculations.md |
| 18 | **Reconcile salinity yield reduction.** Either add salinity_factor to simulation_flow.md harvest formula or explicitly exclude for MVP. | simulation_flow.md |
| 19 | **Document factory function registration mechanism.** How to register new policies. | policies.md |
| 20 | **Document insurance policies or explicitly defer.** Mentioned prominently in overview.md but absent from policies.md. | policies.md or overview.md |
| 21 | **Clarify community-override policy scope.** Either specify the YAML schema and interaction mechanism or remove "community override supported" claims from policy domains. | policies.md, simulation_flow.md |
| 22 | **Rename E_treatment to E_desal consistently** (or vice versa) across all documents. | calculations.md |

### MINOR (15 items) — Cosmetic, clarification, or documentation hygiene

| # | Action | Documents Affected |
|---|--------|--------------------|
| 23 | Fix `settings/mvp-settings.yaml` references → `settings/settings.yaml` | data.md |
| 24 | Fix stale path `data/parameters/water/pump_equipment_parameters.csv` | calculations.md |
| 25 | Fix stale path `data/parameters/energy/generator_parameters.csv` | calculations.md |
| 26 | Fix stale path `data/parameters/water/aquifer_parameters.md` | calculations.md |
| 27 | Add `-toy` suffix to `crop_salinity_tolerance.csv` reference | calculations.md |
| 28 | Create or remove reference to `docs/research/egyptian_utility_pricing.md` | calculations.md |
| 29 | Update data.md: processed product count (10 → 16) | data.md |
| 30 | Update data.md: mark `microclimate_yield_effects` as registered | data.md |
| 31 | Update data.md: mark `fertilizer_costs` as registered | data.md |
| 32 | Update data.md: add `density_variant` column to PV format example | data.md |
| 33 | Update or remove "Planned Datasets" section (all 3 created) | data.md |
| 34 | Remove `nimbalyst` editor annotations from `wells-toy.csv` and `community_buildings_energy_kwh_per_day-toy.csv` | data files |
| 35 | Add water storage balance update location to daily loop pseudocode | simulation_flow.md |
| 36 | Clarify monthly vs yearly groundwater tracking reset scope | simulation_flow.md |
| 37 | Fix calculations.md water pricing dependencies (agricultural tier_pricing reference where only domestic uses tiers) | calculations.md |

---

*Report generated by 5 parallel review agents. Code in `src/` was intentionally not referenced.*
