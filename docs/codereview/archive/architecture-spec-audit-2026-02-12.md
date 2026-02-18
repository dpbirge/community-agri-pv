# Architecture Specification Audit

**Date:** 2026-02-12
**Reviewer:** Claude Opus 4.6
**Scope:** All files in `docs/arch/` except `overview.md`
**Files reviewed:** `structure.md`, `calculations.md`, `data.md`, `policies.md`

## Purpose

Assess whether these specification documents provide sufficient detail for a junior developer to independently build a working Python simulation model without significant senior guidance.

## Verdict

**No.** A junior developer could implement every individual policy, formula, and data loader from these specs — but could not wire them together into a working simulation. The specs define *what the model computes* very well but do not define *how the model runs*.

## Coverage Summary

| Category | Coverage | Implementable from spec alone? |
|---|---|---|
| Policy decision logic | Excellent | Yes |
| Physical/economic formulas | Very good | Yes (formulas only, not when to call them) |
| Data file organization | Good | Yes |
| Simulation orchestration | Missing | No |
| State management | Missing | No |
| Crop lifecycle mechanics | Missing | No |
| Infrastructure sharing | Missing | No |
| YAML schema / data loading | Missing | No |
| Output format | Missing | No |
| Energy dispatch integration | Ambiguous | Probably not |
| Edge cases / error handling | Missing | No |

---

## Strengths

### Policy specifications (policies.md)

Best document of the four. Context/output tables, pseudocode, shared logic extraction, constraint handling, and decision reasons are all clearly specified. A junior dev could implement all 23 policies from this alone.

### Calculation formulas (calculations.md)

Thorough. Worked examples, parameter tables, dependency tracing back to config paths and data files, scientific citations. The MVP vs. future distinction is consistently marked. The progressive detail (e.g., constant SFC vs. Willans line for generators) lets a developer choose their level of fidelity.

### Data organization (data.md)

Clear file format examples with embedded metadata standards. The quality evolution path (`-toy` → `-research` → `-real`) is well thought out.

### Cross-referencing

Documents point to each other consistently and to specific code files.

---

## Structural Gaps

### Gap 1: No simulation loop / orchestration spec

**Severity:** Critical
**Impact:** Blocks implementation entirely

The daily execution order appears as a 6-line list in `policies.md` lines 38-46. That is the only specification of simulation flow across all four documents. Missing:

- How the daily loop is structured end-to-end (init → iterate → finalize)
- What happens before the loop starts (data loading, state initialization, constraint pre-computation)
- When year-boundary processing fires (metric snapshots, aquifer updates, quota resets)
- How multi-farm iteration works within a single day (sequential? all at once? order matters?)
- How the simulation terminates (fixed duration? insolvency early-stop?)

This is the single largest gap. A junior dev would have to reverse-engineer the orchestration from the existing code or make it up.

### Gap 2: No state management specification

**Severity:** Critical
**Impact:** Cannot implement without guessing data structures

The CLAUDE.md references `SimulationState`, `FarmState`, `CropState`, `AquiferState`, `EnergyState`, `EconomicState` — but the architecture docs never define these. Missing:

- What fields each state object holds
- How state is initialized (starting values for all tracked quantities)
- How daily records are accumulated (append to lists? rolling windows?)
- How yearly snapshots work
- The relationship between farm-level and community-level state

### Gap 3: No crop lifecycle specification

**Severity:** Critical
**Impact:** Yield formulas exist but cannot be applied without lifecycle mechanics

`calculations.md` covers growth stages and yield formulas but never specifies the lifecycle mechanics:

- When does a crop "start"? (planting_date from scenario → what code action?)
- How do multiple `planting_dates` per crop work? (overlapping seasons? sequential?)
- How does `percent_planted` interact with `area_fraction`?
- What triggers harvest? (planting_date + season_length_days from crop parameters?)
- What happens during fallow periods between seasons?
- How is crop state tracked day-to-day? (days_since_planting, growth_stage transitions, cumulative water received)

### Gap 4: No shared infrastructure allocation spec

**Severity:** High
**Impact:** Cannot implement multi-farm simulation

`structure.md` defines per-farm configs and community infrastructure, but never formalizes:

- How well capacity is divided among 20 farms (`policies.md` mentions `well_capacity / num_farms` as a context field, but where is this calculated and what is the authoritative formula?)
- How treatment capacity is shared
- How PV/wind/battery capacity is shared or per-farm
- How storage capacity is partitioned
- Whether infrastructure is community-pooled or farm-allocated (or a mix)

### Gap 5: No scenario YAML schema

**Severity:** High
**Impact:** Cannot write or validate configuration files

`structure.md` lists all parameters with their options but never shows:

- The actual YAML nesting structure
- How policy parameters are passed (e.g., where does `price_threshold_multiplier: 1.5` live in the YAML?)
- How farm-level vs. community-override policies are distinguished in YAML
- A complete annotated example scenario

`data.md` mentions `mvp-settings.yaml` exists but does not describe its schema.

### Gap 6: No data loading / registry specification

**Severity:** High
**Impact:** Cannot implement data pipeline

`data.md` describes file structures. But there is no spec for:

- How `data_registry.yaml` maps logical keys to file paths (format, nesting, key naming convention)
- How `SimulationDataLoader` resolves data at runtime
- How price data is looked up by date (interpolation? nearest date? exact match required?)
- How precomputed irrigation data is joined by (weather_scenario_id, planting_date, crop_day)
- How toy vs. research data selection works at runtime (`use_research_prices` flag behavior)

### Gap 7: No output / results specification

**Severity:** Medium
**Impact:** Cannot implement results pipeline

`structure.md` Section 4 lists ~60 metrics. Section 5 lists 6 plots and 2 tables. But no spec for:

- Output file formats (CSV column names and ordering, JSON structure)
- Results directory organization and naming
- What gets persisted to disk vs. stays in-memory
- How timestamped result folders are structured

---

## Ambiguities

### Ambiguity 1: Energy dispatch vs. energy policy integration

`policies.md` lines 541-643 say energy policies return boolean flags (`use_renewables`, `grid_import`, etc.). `calculations.md` lines 778-850 say the dispatch function has its own hardcoded merit-order logic. `calculations.md` explicitly states: *"Energy policy objects exist but are not yet consumed by the dispatch function."*

Additionally, the spec-defined policy names (`microgrid`, `renewable_first`, `all_grid`) do not match the code-referenced class names (`PvFirstBatteryGridDiesel`, `GridFirst`, `CheapestEnergy`).

A junior dev would not know which to implement or how they connect.

### Ambiguity 2: Food storage / tranche pipeline under-specified

The forced-sale + FIFO tranche system in `policies.md` lines 317-328 is described narratively but missing:

- Data structure for tranches (what fields? entry_date, crop, product_type, kg, storage_type?)
- How storage capacity is shared across product types (one pool? separate pools per type?)
- How revenue from forced sales vs. market sales is recorded (same? different?)
- Whether processing is instantaneous or has a time delay

### Ambiguity 3: Time and date handling unspecified

- Weather data is calendar-date-indexed
- Crop growth is day-count-indexed from planting
- Price data is date-indexed (some monthly, some daily)

No spec for:

- How simulation start/end dates are determined
- How sim-day maps to calendar date and back to weather/price data
- Monthly/yearly boundary detection
- Leap year handling
- What happens when data does not cover the simulation period

---

## Minor Inconsistencies

1. **Water policy count mismatch:** `structure.md` intro says "5 water allocation policies" but lists 6 (including `min_water_quality` and `quota_enforced`). `calculations.md` Section 2.8 MVP note says "five water allocation policies" and lists 5 — omits `min_water_quality`.

2. **Market-responsive splits:** `structure.md` shows ranges for `market_responsive` food policy ("30-65%") suggesting continuous adjustment. `policies.md` shows fixed two-state splits (30% or 65% based on threshold), which is clearer but does not match the range description.

3. **Processing equipment file path mismatch:** `calculations.md` references `data/parameters/processing/food_processing_equipment-toy.csv`. `data.md` lists it under `data/parameters/equipment/processing_equipment-toy.csv`. Different subdirectory paths.

4. **Energy policy class names vs. spec names:** Spec defines `microgrid`, `renewable_first`, `all_grid`. Code references `PvFirstBatteryGridDiesel`, `GridFirst`, `CheapestEnergy`. The third policy (`CheapestEnergy`) does not appear in the spec at all.

---

## Missing Edge Case / Error Handling

No document addresses any of the following:

- **Insolvency behavior:** What happens when a farm's cash goes below zero? Does the farm continue operating? Exit the simulation? Receive community bailout?
- **Storage deadlock:** What happens when storage is 100% full AND new harvest arrives AND nothing can be forced-sold (e.g., all tranches are fresh from today)?
- **Data gaps:** What happens when weather data or price data has missing dates or does not cover the simulation period?
- **Validation rules:** Must `area_fractions` per farm sum to <= 1.0? Must `total_farms` match the number of farm entries? Must equipment fractions per processing type sum to 1.0? What is the valid range for each numeric parameter?
- **Crop season overflow:** What happens when a crop's growing season extends past the end of the simulation year or past the end of the simulation?

---

## Recommended New Specifications

To close the gaps above, the following new documents or document sections are recommended, in priority order:

1. **Simulation orchestration spec** — Daily loop structure, initialization sequence, year-boundary processing, multi-farm iteration, termination conditions. (Closes Gaps 1, 3 partially, and Ambiguity 3)

2. **State management spec** — All state dataclass definitions with field names, types, initial values, and update rules. (Closes Gap 2)

3. **Scenario YAML schema spec** — Full annotated YAML example with nesting structure, policy parameter passing, farm-level vs. community-override syntax. (Closes Gap 5)

4. **Data loading spec** — Registry format, loader behavior, date lookup/interpolation rules, toy-vs-research selection. (Closes Gap 6)

5. **Crop lifecycle spec** — Planting triggers, multi-season handling, harvest timing, fallow periods, cumulative tracking. (Closes Gap 3)

6. **Infrastructure allocation spec** — How community infrastructure is partitioned across farms. (Closes Gap 4)

7. **Output format spec** — Results directory structure, CSV/JSON schemas, metric-to-file mapping. (Closes Gap 7)

8. **Edge case / validation rules spec** — Insolvency handling, storage overflow, data gap behavior, scenario validation constraints. (Closes edge case section)
