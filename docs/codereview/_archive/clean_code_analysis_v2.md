# Clean Code Analysis Report

**Date:** 2026-03-03
**Scope:** All Python source files in `src/` (10 files, 6,158 lines)

## Executive Summary

| Metric | Count |
|--------|-------|
| Files Scanned | 10 |
| Total Lines of Code | 6,158 |
| Total Functions Analyzed | 138 |
| Total Classes Analyzed | 0 (functional programming throughout) |
| Dead Code Items | 7 |
| High-Complexity Items | 9 |
| Estimated Lines Removable | ~45 (~0.7% of codebase) |
| Risk Assessment | LOW |

### Dead Code Breakdown

| Category | Count |
|----------|-------|
| Orphaned Functions | 5 |
| Unused Imports | 0 |
| Commented Code Blocks | 0 |
| TODO/FIXME Markers | 0 |
| Duplicate Code (by-design) | 2 |

---

## Part 1: Dead Code Elimination Plan

### 1.1 Dead Code Inventory

#### 1. `save_water_supply()` — src/water.py:1431-1448

- **Type:** Orphaned Function
- **Evidence:** 0 imports, 0 call sites. No `__main__` block calls it. No notebook imports it.
- **Superseded by:** Water supply output is consumed as intermediate by `water_balance.py` pipeline; never saved standalone.
- **Deletion safety:** SAFE

#### 2. `load_irrigation_demand()` — src/irrigation_demand.py:315-324

- **Type:** Orphaned Function
- **Evidence:** 0 imports, 0 call sites. `save_irrigation_demand` is called in `__main__`, but load counterpart has no consumers.
- **Superseded by:** N/A
- **Deletion safety:** SAFE

#### 3. `load_harvest_yields()` — src/crop_yield.py:329-338

- **Type:** Orphaned Function
- **Evidence:** 0 imports, 0 call sites. `save_harvest_yields` IS used in `simulation.ipynb`; load counterpart is not.
- **Superseded by:** N/A
- **Deletion safety:** SAFE

#### 4. `load_energy_balance()` — src/energy_balance.py:1273-1282

- **Type:** Orphaned Function
- **Evidence:** 0 imports, 0 call sites. Referenced only in `plots.py` docstrings as "or load_energy_balance". `simulation.ipynb` uses `compute_daily_energy_balance` directly, never loads from CSV.
- **Superseded by:** N/A
- **Deletion safety:** VERIFY — update `plots.py` docstring references on deletion.

#### 5. `plot_water_balance_summary()` — src/plots.py:340-353

- **Type:** Orphaned Function
- **Evidence:** 0 imports, 0 call sites. Pure convenience wrapper calling `plot_water_demand_by_source`, `plot_water_supply_by_source`, `plot_water_policy_heatmap`. Notebooks call the 3 individual functions directly.
- **Superseded by:** Direct calls to the 3 individual plot functions.
- **Deletion safety:** SAFE

#### 6. Duplicate `_load_yaml()` (7 copies) — Informational Only

- **Files:** `community_demand.py`, `water_balance.py`, `water.py`, `irrigation_demand.py`, `crop_yield.py`, `energy_supply.py`, `energy_balance.py`
- **Status:** Intentional per project architecture. Each module is self-contained with its own `_load_yaml()` / `_load_csv()` helpers (documented in CLAUDE.md).
- **Action:** None recommended.

#### 7. Duplicate `_load_csv()` (4 copies) — Informational Only

- **Files:** `community_demand.py` (with `parse_dates`), `energy_supply.py` (drops `weather_scenario_id`), `water.py` (basic), `energy_balance.py` (basic)
- **Status:** Intentional; minor variations serve module-specific needs.
- **Action:** None recommended.

### 1.2 Deletion Execution Plan

#### Phase 1: Zero-Risk Deletions

| # | File | Action | Lines |
|---|------|--------|-------|
| 1 | `src/water.py` | Remove `save_water_supply()` | 1431-1448 |
| 2 | `src/irrigation_demand.py` | Remove `load_irrigation_demand()` | 315-324 |
| 3 | `src/crop_yield.py` | Remove `load_harvest_yields()` | 329-338 |
| 4 | `src/plots.py` | Remove `plot_water_balance_summary()` | 340-353 |

#### Phase 2: Requires Docstring Updates

| # | File | Action | Lines |
|---|------|--------|-------|
| 5 | `src/energy_balance.py` | Remove `load_energy_balance()` | 1273-1282 |
| 6 | `src/plots.py:371` | Remove "or load_energy_balance" from docstring | — |

#### Phase 3: Module Header Cleanup

| # | File | Action |
|---|------|--------|
| 7 | `src/water.py:21` | Remove `save_water_supply` from module docstring usage example |

#### Phase 4: Verification

```bash
python -m py_compile src/water.py src/irrigation_demand.py src/crop_yield.py src/energy_balance.py src/plots.py
python -m pytest tests/
grep -r "save_water_supply\|load_irrigation_demand\|load_harvest_yields\|load_energy_balance\|plot_water_balance_summary" src/ tests/
```

---

## Part 2: Complexity Reduction Plan

### 2.1 High-Complexity Code Inventory

#### 1. `water.py:_dispatch_day()` — Lines 920-1157

| Metric | Value | Threshold |
|--------|-------|-----------|
| Line count | 237 | >100 |
| Nesting depth | 5 | >4 |
| Parameter count | 12 | >6 |
| Cyclomatic complexity | ~15 | >5 |
| Responsibilities | 6 | >1 |

**Responsibilities identified:**

1. Fallow-day handling with treatment-smoothing horizon check
2. Safety flush: detect tank TDS > crop requirement, flush to fields
3. Draw from existing tank stock
4. Strategy-dependent source volume computation (3 strategies)
5. Second source+draw pass for demand exceeding single-pass tank throughput
6. Post-irrigation look-ahead drain for next-day TDS transitions

**Refactoring rationale:** This is the largest function in the codebase. It interleaves six distinct operational phases into a single 237-line block, making it difficult to understand any one phase without reading the entire function. The fallow-day logic, safety flush, and look-ahead drain are each self-contained decision sequences with clear input/output boundaries — they read tank state and demand, then modify volumes and flags. Extracting them into named helpers makes the daily dispatch sequence readable as a high-level recipe ("handle fallow, check flush, draw, source, second pass, drain") rather than requiring a developer to mentally parse 237 lines to find where each phase begins and ends. The high nesting depth (5 levels) also makes it error-prone to modify any single phase without accidentally breaking adjacent logic.

#### 2. `water.py:_source_water()` — Lines 431-569

| Metric | Value | Threshold |
|--------|-------|-----------|
| Line count | 138 | >100 |
| Parameter count | 10 | >6 |
| Cyclomatic complexity | ~10 | >5 |
| Responsibilities | 4 | >1 |

**Responsibilities identified:**

1. Strategy dispatch (minimize_cost vs minimize_treatment vs minimize_draw)
2. TDS correction via municipal top-up
3. Tank headroom enforcement after TDS correction
4. Tank mixing + output row recording

**Refactoring rationale:** Deferred (Priority 4). The three strategy branches are inherently complex due to domain rules — each strategy has different source-ordering logic with TDS constraints. The function is long but its branching structure mirrors the problem domain faithfully. Refactoring risks introducing subtle sourcing bugs (e.g., wrong TDS blending order) for marginal readability gains. The 10-parameter signature is high but each parameter represents a distinct physical quantity (tank level, TDS, caps) that the function genuinely needs.

#### 3. `water.py:compute_water_supply()` — Lines 1289-1428

| Metric | Value | Threshold |
|--------|-------|-----------|
| Line count | 139 | >100 |
| Responsibilities | 3 | >1 |

**Responsibilities identified:**

1. Config loading and resolution (YAML + CSV + paths)
2. Policy assembly (strategy, caps, prefill, smoothing)
3. Simulation invocation and column ordering

**Refactoring rationale:** The first ~80 lines are pure configuration wiring — loading YAML, resolving paths, building spec dicts — that obscures the actual simulation call at the end. Extracting config loading into `_build_supply_config()` separates "what inputs does the simulation need?" from "run the simulation." This makes it easier to add new config parameters (e.g., new water sources) without wading through simulation setup, and makes the public function's intent immediately clear: load config, then simulate.

#### 4. `water_balance.py:compute_daily_water_balance()` — Lines 117-268

| Metric | Value | Threshold |
|--------|-------|-----------|
| Line count | 151 | >100 |
| Parameter count | 7 | >6 |
| Responsibilities | 5 | >1 |

**Responsibilities identified:**

1. Orchestrate sub-computations (irrigation, supply, community, field specs)
2. Merge DataFrames and rename columns
3. Compute per-field delivery + application energy
4. Compute total energy and total cost columns
5. Compute balance diagnostics (over-delivery, balance check)

**Refactoring rationale:** The bottom half of this function (lines ~219-266) performs per-field delivery calculations and balance diagnostics that are logically independent of the orchestration above. These are pure DataFrame transformations with no dependency on the YAML/config loading or sub-computation calls — they only need the merged DataFrame and field specs. Extracting them makes the orchestrator a clean pipeline: "compute irrigation → compute supply → compute community → merge → enrich with delivery/energy → add diagnostics." Each extracted helper becomes independently testable, and future changes to delivery energy formulas or balance checks won't require reading the full 151-line orchestrator.

#### 5. `energy_balance.py:_dispatch_day()` — Lines 777-911

| Metric | Value | Threshold |
|--------|-------|-----------|
| Line count | 134 | >100 |
| Parameter count | 18 | >6 |
| Cyclomatic complexity | ~12 | >5 |
| Responsibilities | 4 | >1 |

**Responsibilities identified:**

1. Net-load calculation and surplus/deficit branching
2. Surplus disposition loop (battery -> export -> curtail)
3. Deficit fulfillment loop (battery -> grid/generator, strategy-ordered)
4. Cost computation (import, export revenue, fuel)

**Refactoring rationale:** The 18-parameter signature is the worst in the codebase — it forces every caller to pass battery state, grid caps, net metering state, price vectors, and equipment specs as individual arguments. This makes the function impossible to understand from its signature alone and creates a maintenance hazard: adding any new dispatch consideration (e.g., demand response) requires threading yet another parameter through every call site. Grouping related parameters into a context dict and extracting the surplus/deficit loops into `_handle_surplus()` and `_handle_deficit()` directly addresses both problems. The surplus and deficit paths are already structurally independent (they branch on the sign of net load and never share mutable state within a single day), making extraction straightforward and low-risk.

#### 6. `energy_balance.py:_run_simulation()` — Lines 918-1056

| Metric | Value | Threshold |
|--------|-------|-----------|
| Line count | 138 | >100 |
| Parameter count | 13 | >6 |
| Responsibilities | 3 | >1 |

**Responsibilities identified:**

1. Initialize state objects (battery, grid caps, net metering)
2. Daily loop with month-boundary resets
3. Grid cap accumulation and column stamping

**Refactoring rationale:** The 13 individual parameters are the direct cause of `_dispatch_day()`'s 18-parameter signature — `_run_simulation()` unpacks its own parameters and then forwards most of them plus loop state to `_dispatch_day()` on every iteration. Grouping the 13 parameters into 2-3 config dicts (equipment specs, price vectors, policy settings) at this level automatically reduces `_dispatch_day()`'s signature too, since the dicts pass through. This is a prerequisite for the Priority 1 `_dispatch_day()` refactoring — fixing the parameter explosion here propagates the benefit downstream.

#### 7. `energy_balance.py:compute_daily_energy_balance()` — Lines 1110-1250

| Metric | Value | Threshold |
|--------|-------|-----------|
| Line count | 140 | >100 |
| Parameter count | 7 | >6 |
| Responsibilities | 4 | >1 |

**Responsibilities identified:**

1. Compute renewable generation and community demand
2. Date intersection and alignment
3. Config loading + validation + equipment specs
4. Price loading and simulation invocation

**Refactoring rationale:** This public-facing function mixes two concerns: preparing all inputs (computing generation/demand, loading configs, loading prices, aligning dates) and invoking the simulation. The input preparation is ~100 lines of wiring that must be read through to understand what actually gets simulated. Extracting `_prepare_energy_inputs()` creates a clear boundary: "gather and validate everything the simulation needs" vs. "run the simulation with those inputs." This also makes it straightforward to add new input sources (e.g., demand-side flexibility) — they slot into the preparation helper without cluttering the public API.

#### 8. `water_sizing.py:size_water_system()` — Lines 694-858

| Metric | Value | Threshold |
|--------|-------|-----------|
| Line count | 164 | >100 |
| Parameter count | 8 | >6 |
| Cyclomatic complexity | ~8 | >5 |
| Responsibilities | 4 | >1 |

**Responsibilities identified:**

1. Load catalogs and demand analysis
2. Well selection (initial + re-selection)
3. Treatment throughput and storage sizing
4. Iterative deficit reduction loop (up to 3 iterations)

**Refactoring rationale:** The iterative deficit-reduction loop (select components → simulate → check deficit → re-select) is nearly identical between `size_water_system()` and `optimize_water_system()`, but currently duplicated across both functions. This means any bug fix or improvement to the iteration logic must be applied in two places — a classic maintenance hazard. Extracting the shared loop into `_iterate_until_target()` with a callback for the config-building step eliminates the duplication while preserving each function's distinct sizing strategy. The 8-parameter signature also benefits from the extraction: the shared iterator encapsulates the loop state, reducing the parameter surface of each public function.

#### 9. `water_sizing.py:optimize_water_system()` — Lines 865-1065

| Metric | Value | Threshold |
|--------|-------|-----------|
| Line count | 200 | >100 |
| Parameter count | 11 | >6 |
| Cyclomatic complexity | ~8 | >5 |
| Responsibilities | 5 | >1 |

**Responsibilities identified:**

1. Load catalogs and demand analysis
2. Treatment-anchored well selection
3. Storage and municipal sizing
4. Efficiency curve application
5. Iterative deficit reduction loop (near-duplicate of `size_water_system`'s loop)

**Refactoring rationale:** At 200 lines with 11 parameters, this is the second-largest function in the codebase. It shares ~50% of its logic with `size_water_system()` (catalog loading, demand analysis, and the iterative deficit-reduction loop) but adds treatment-anchored well selection and an efficiency curve. The duplication means that changes to shared logic (e.g., how deficit thresholds work, how catalogs are filtered) must be synchronized across both functions — a fragile pattern that has already produced subtle divergences in how the two functions handle re-selection. Consolidating the shared iteration into a common helper and letting each public function supply its own config-building callback eliminates this synchronization burden while keeping each function's distinct optimization strategy clearly separated.

### 2.2 Refactoring Priority Matrix

#### Priority 1: HIGH IMPACT, LOW RISK (Do First)

**`energy_balance.py:_dispatch_day()`** — 18 parameters is the most in the codebase.

- Group parameters into a `dispatch_context` dict to reduce parameter explosion.
- Extract `_handle_surplus()` and `_handle_deficit()` as independent helpers.
- Expected result: orchestrator reduced to ~40 lines, each helper ~30-40 lines.

**`water_balance.py:compute_daily_water_balance()`** — Lines 219-266 are self-contained.

- Extract `_compute_delivery_and_energy()` for per-field delivery + energy + cost rollup.
- Extract `_compute_balance_diagnostics()` for over-delivery and balance check.
- Expected result: orchestrator reduced to ~80 lines.

#### Priority 2: HIGH IMPACT, MEDIUM RISK (Do Second)

**`water.py:_dispatch_day()`** — Largest function at 237 lines.

- Extract `_handle_fallow_day()` for fallow-day + smoothing horizon logic (lines 958-988).
- Extract `_second_source_pass()` for the second source+draw pass (lines 1051-1098).
- Extract `_look_ahead_drain()` for post-irrigation drain logic (lines 1132-1145).
- Expected result: orchestrator reduced to ~120 lines.

**`water_sizing.py:size_water_system()` and `optimize_water_system()`** — ~50% shared code.

- Extract `_iterate_until_target(config_builder, demand_df, ...)` for the shared deficit-reduction loop.
- Both public functions call the shared iterator with their respective config-building callbacks.
- Expected result: each public function reduced by ~40 lines.

#### Priority 3: MEDIUM IMPACT, LOW RISK (Do Third)

- **`water.py:compute_water_supply()`** — Extract config loading into `_build_supply_config()`.
- **`energy_balance.py:compute_daily_energy_balance()`** — Extract `_prepare_energy_inputs()`.
- **`energy_balance.py:_run_simulation()`** — Group 13 parameters into 2-3 config dicts.

#### Priority 4: LOW IMPACT (Defer)

- **`water.py:_source_water()`** — Strategy branches are readable despite length. Refactoring risks introducing subtle sourcing bugs. Domain complexity, not code complexity.

---

## Part 3: Implementation Guide

### 3.1 Pre-Implementation Checklist

```bash
git checkout -b cleanup/dead-code-and-refactoring
python -m pytest tests/       # Record baseline pass count
git status                     # Verify clean working tree
```

### 3.2 Implementation Sequence

1. **Dead Code Elimination** (Part 1 Phases 1-3) — execute before any refactoring
2. **Complexity Reduction** (Part 2 Priorities 1-2) — execute after dead code is removed
3. **Verification** — `python -m pytest tests/` after each phase

### 3.3 Commit Strategy

**Dead code deletion:**
```
cleanup: remove unused {artifact_type} {artifact_name}

- File: src/path/to/file.py
- Lines removed: X-Y
- Reason: No references found across codebase
- Verified: grep confirmed zero matches
```

**Refactoring:**
```
refactor: extract {new_function} from {original_function}

- Extracted to: src/path/to/file.py
- Lines moved: X-Y from original
- Behavior: Preserved (verified by test suite)
```

### 3.4 Constraints

- **Dead code phase:** DELETE only — zero logic modifications
- **Refactoring phase:** MOVE/EXTRACT only — zero behavior changes
- **Verification mandatory:** Test suite must pass after every single change
- **Atomic commits:** Each deletion or extraction independently revertible
