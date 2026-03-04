# Clean Code Analysis — src/ Modules

**Date:** 2026-03-03
**Scope:** 9 Python files in `src/`, 4,012 lines, 97 functions

## Executive Summary

- **Files scanned:** 9
- **Functions analyzed:** 97
- **Unused imports:** 0
- **TODO/FIXME markers:** 0
- **Commented-out code:** 0
- **Duplicate helpers:** 9 copies across modules (`_load_yaml` x6, `_load_csv` x3)
- **Unconnected public functions:** 11 (all documented in specs — see assessment below)
- **High-complexity functions:** 3

## 1. Unconnected Functions (Not Dead Code)

The following public functions have zero import/call sites outside their own module's
`__main__` block. However, all are explicitly documented in specification files
(`specs/water_system_specification.md`, `specs/energy_system_specification.md`) and
project docs (`CLAUDE.md`, `docs/plans/`). They are **designed but not yet wired into
notebooks or a top-level pipeline** — not abandoned.

### 1.1 Entire Modules — Pre-Built, Not Yet Integrated

| Module | Public Functions | Lines | Spec Reference |
|--------|-----------------|-------|----------------|
| `water_sizing.py` | `size_water_system`, `optimize_water_system` | 1,087 | `specs/water_system_specification.md` §4-5 |
| `crop_yield.py` | `compute_harvest_yield` | 169 | `CLAUDE.md`, `docs/plans/water_policy_extensions.md` |

These modules are complete, self-verifiable via `__main__`, and have extensive spec
documentation. They await integration into a notebook or orchestrator workflow.

**Recommendation:** No action. These are the next features to connect. When a sizing
or yield notebook is created, these modules plug in directly.

### 1.2 save_* Functions — API Pattern, Used by __main__

Each `src/` module follows a `compute_*` / `save_*` / `load_*` triplet. Several
`save_*` functions are only exercised by their module's `__main__` block (which is
the primary way to regenerate simulation CSVs).

| Function | Module | External Callers |
|----------|--------|------------------|
| `save_irrigation_demand` | `irrigation_demand.py` | `__main__` only |
| `save_water_supply` | `water.py` | `__main__` only |
| `save_daily_water_balance` | `water_balance.py` | `__main__` only |
| `save_demands` | `community_demand.py` | `__main__` only |
| `save_energy` | `energy_supply.py` | `__main__` only |

**Recommendation:** Keep. The `__main__` blocks are the primary execution mechanism
for regenerating `simulation/` CSVs (`python -m src.water_balance`, etc.). Removing
`save_*` would break this workflow.

### 1.3 load_* Functions — Two Are Unused

| Function | Module | External Callers |
|----------|--------|------------------|
| `load_irrigation_demand` | `irrigation_demand.py` | 0 (zero references) |
| `load_water_supply` | `water.py` | 0 (zero references) |

These have zero callers anywhere — not even `__main__`. All other `load_*` functions
are used by notebooks (`load_demands`, `load_energy`, `load_daily_water_balance`).

**Recommendation:** Low priority. These are API completeness functions. Could be
removed but the cost of keeping them (10 lines each) is negligible. A future notebook
consuming intermediate water supply data would use `load_water_supply`.

### 1.4 Convenience Wrapper

| Function | Module | External Callers |
|----------|--------|------------------|
| `plot_water_balance_summary` | `plots.py` | 0 (documented in spec) |

Convenience wrapper that calls `plot_water_demand_by_source`, `plot_water_supply_by_source`,
and `plot_water_policy_heatmap`. The water balance notebook calls these individually
instead. Documented in `specs/water_system_specification.md`.

**Recommendation:** Keep. Useful for quick one-liner visualization in future notebooks.


## 2. Duplicate Code

### 2.1 `_load_yaml(path)` — 6 Identical Copies

Defined in: `crop_yield.py`, `irrigation_demand.py`, `water.py`, `water_balance.py`,
`community_demand.py`, `energy_supply.py`

All 6 copies have identical bodies:
```python
def _load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)
```

Additionally, `water_sizing.py` imports `_load_yaml` from `water.py` rather than
defining its own copy.

### 2.2 `_load_csv(path)` — 3 Variant Copies

| Module | Behavior |
|--------|----------|
| `water.py` | `pd.read_csv(path, comment='#')` |
| `community_demand.py` | `pd.read_csv(path, comment='#', parse_dates=['date'])` |
| `energy_supply.py` | Same as community_demand + drops `weather_scenario_id` column |

These are not exact duplicates — each has domain-specific behavior.

### Assessment

The current architecture treats each module as self-contained, which is consistent
with the functional programming style documented in `CLAUDE.md`. The duplication
is intentional: modules can be understood, tested, and executed independently.

**Recommendation:** No action. Consolidating into a shared `_utils.py` module would
add a dependency layer for minimal benefit (saves ~18 lines across 6 files). The
self-contained module pattern is a deliberate design choice documented in the
project's architecture section.


## 3. High-Complexity Functions

### 3.1 `_dispatch_day()` — water.py:533-776

| Metric | Value | Threshold |
|--------|-------|-----------|
| Line count | 244 | >100 |
| Parameters | 12 | >6 |
| Cyclomatic complexity | ~15 | >5 |
| Responsibilities | 6 | >1 |

**Responsibilities:**
1. Initialize output row dict (lines 569-605, ~35 lines)
2. Safety flush: tank TDS exceeds crop requirement (lines 625-630)
3. Draw existing tank water toward demand (lines 632-643)
4. Source shortfall from wells/municipal (lines 646-648)
5. Look-ahead prefill for upcoming peaks (lines 663-715, ~52 lines)
6. Post-irrigation drain + finalize delivery totals (lines 717-776)

**Decomposition candidates:**

- **`_prefill_tank(...)`** — Extract the look-ahead prefill block (lines 663-715).
  This is the largest self-contained block: it builds its own temporary row dict,
  calls `_source_water`, and accumulates results back into the main row. Extracting
  it removes 52 lines and the deepest nesting from `_dispatch_day`.

- **`_finalize_dispatch_row(...)`** — Extract delivery total computation and policy
  metadata (lines 732-776). Pure calculation over already-computed values.

- **`_init_dispatch_row(...)`** — Extract the 35-line row initialization block
  (lines 569-605). This is boilerplate dict construction.

**Priority:** MEDIUM. The function is complex but stable — the simulation loop runs
correctly across 15 years of daily data. Refactoring has correctness risk since the
function mutates a shared `tank` dict and `row` dict across phases. Extract only
if active development on dispatch logic is planned.

### 3.2 `_source_water()` — water.py:382-526

| Metric | Value | Threshold |
|--------|-------|-----------|
| Line count | 145 | >100 |
| Parameters | 10 | >6 |
| Cyclomatic complexity | ~12 | >5 |
| Responsibilities | 4 | >1 |

**Responsibilities:**
1. Strategy-based dispatch routing (lines 421-458)
2. TDS correction: add municipal to bring blend below threshold (lines 466-480)
3. Tank capacity enforcement after correction (lines 482-497)
4. Mix sourced water into tank + record output row (lines 499-526)

**Decomposition candidate:**

- **`_correct_tds_blend(...)`** — Extract TDS correction + capacity enforcement
  (lines 466-497). Self-contained: takes sourced volumes + TDS values, returns
  adjusted municipal volume.

**Priority:** MEDIUM. Same stability considerations as `_dispatch_day`. These two
functions are tightly coupled — refactoring one benefits the other.

### 3.3 `compute_daily_water_balance()` — water_balance.py:39-251

| Metric | Value | Threshold |
|--------|-------|-----------|
| Line count | 213 | >100 |
| Parameters | 7 | >6 |
| Cyclomatic complexity | ~8 | >5 |
| Responsibilities | 5 | >1 |

**Responsibilities:**
1. Call sub-modules: irrigation, supply, community (lines 65-97)
2. Merge DataFrames and rename columns (lines 107-138)
3. Compute per-field delivered/energy columns (lines 141-155)
4. Compute energy and cost totals (lines 157-173)
5. Order output columns (lines 190-251, ~60 lines)

**Decomposition candidate:**

- **`_order_balance_columns(result)`** — Extract the 60-line column ordering block
  (lines 190-251). This is pure formatting with zero logic dependencies — it just
  defines the preferred column order for the output CSV.

**Priority:** LOW. This is an orchestrator function that is inherently multi-step.
The column ordering extraction would be clean and risk-free, but the function is
readable as-is since each section is clearly commented.


## 4. Items Not Found

- **Unused imports:** None across all 9 files
- **TODO/FIXME/HACK markers:** None
- **Commented-out code blocks:** None
- **Orphaned classes:** None (no classes in codebase — functional architecture)


## 5. Recommendations Summary

| Item | Action | Risk | Lines Affected |
|------|--------|------|----------------|
| `water_sizing.py` + `crop_yield.py` | Keep as-is | N/A | 0 |
| `save_*` functions (5) | Keep as-is | N/A | 0 |
| `load_irrigation_demand` + `load_water_supply` | Optional removal | LOW | ~20 |
| `plot_water_balance_summary` | Keep as-is | N/A | 0 |
| `_load_yaml` duplication (6x) | Keep (self-contained modules) | N/A | 0 |
| `_dispatch_day` decomposition | Optional refactor | MEDIUM | ~244 |
| `_source_water` decomposition | Optional refactor | MEDIUM | ~145 |
| `compute_daily_water_balance` column ordering | Optional extract | LOW | ~60 |

**Bottom line:** The codebase is clean. No dead code, no unused imports, no abandoned
markers. The main improvement opportunity is decomposing the two largest functions in
`water.py` (`_dispatch_day` at 244 lines and `_source_water` at 145 lines), which
would improve readability for future dispatch logic changes.
