# Food Processing Module — Implementation Plan

## Overview

Implement `src/food_processing.py` and supporting configuration per
`specs/food_processing_specification.md`. The module reads daily harvest
output from `crop_yield.py`, simulates processing queues with equipment
throughput limits, tracks storage inventory with cohort-based spoilage,
and reports daily energy/labor demands.

All data files already exist. The work is pure implementation: one new
source module, one new settings YAML, and registry/scenario wiring.

**Design principle:** Food processing is a pure downstream observer. It
reads `simulation/daily_harvest_yields.csv` (already produced by
`crop_yield.py`) and writes `simulation/daily_food_processing.csv`. It
never modifies upstream crop growth, irrigation, water balance, or energy
balance code. Energy and labor outputs are reported in the output CSV for
analysis but do not feed back into the energy dispatch or water system.
Upstream integration (e.g., adding processing energy to the energy
balance) is a separate, deferred task.

---

## Paired Subagent Execution Model

Each phase uses two concurrent subagents:

| Role | Agent Type | Responsibility |
|------|-----------|----------------|
| **Writer** | `ouroboros:hacker` | Implements code per spec. Writes files, runs standalone verification. |
| **Reviewer** | `ouroboros:evaluator` | Reviews written code against spec. Runs tests. Identifies bugs, spec deviations, edge cases. Returns fix list. |

**Workflow per phase:**
1. Writer agent implements the phase deliverables
2. Reviewer agent reads the written code + spec, runs validation, reports issues
3. Writer agent applies fixes from the review
4. Repeat review/fix cycle until Reviewer passes

Phases are sequential — each depends on the prior phase's outputs.

---

## Phase 0: Data Fix (Pre-Implementation)

**Goal:** Fix known data issue before any code reads the files.

**Deliverables:**
- Update `data/food_processing/processing_specs-research.csv`: set
  `energy_kwh_per_kg = 0.013` and `labor_hours_per_kg = 0.06` for all
  5 `fresh` rows (spec section "Data update required")

**Writer task:** Edit the CSV directly.
**Reviewer task:** Verify all 5 fresh rows updated, no other rows changed.

---

## Phase 1: Configuration & Registry Wiring

**Goal:** Create the settings YAML and wire data paths so the module can
load everything it needs.

**Deliverables:**
1. `settings/food_processing_base.yaml` — processing allocation fractions,
   equipment selection, storage conditions, cold storage params, working
   schedule (spec section "Processing Policy Configuration")
2. Add `food_processing:` section to `settings/data_registry_base.yaml`
   with all 8 data file paths (spec section "Data Registry Additions")
3. Update `scenarios/scenario_base.yaml` — uncomment and fix the
   `food_processing:` line to point to `settings/food_processing_base.yaml`

**Writer task:** Create/edit all three files per spec.
**Reviewer task:**
- Validate YAML syntax loads without error
- Confirm all 8 registry paths resolve to existing files
- Confirm allocation fractions sum to 1.0 per crop
- Confirm equipment types exist in `processing_equipment-toy.csv`
- Confirm scenario file references correct path with `_base` suffix

---

## Phase 2: Core Module — Data Loading & Validation

**Goal:** Implement internal helpers that load and index all data files.

**Deliverables:**
- `src/food_processing.py` with these internal functions:
  - `_load_processing_specs(registry, root_dir)` — index by (crop, type)
  - `_load_handling_losses(registry, root_dir)` — index by (crop, pathway)
  - `_load_equipment(registry, root_dir)` — load equipment catalog
  - `_load_spoilage_rates(registry, root_dir)` — index by (crop, type, condition)
  - `_load_processing_labor(registry, root_dir)` — index by (crop, type)
  - `_load_storage_labor(registry, root_dir)` — load with wildcard expansion
  - `_load_processing_policy(policy_path)` — load + validate YAML
  - `_is_working_day(date, working_days_per_week)` — Saturday = rest day

**Writer task:** Implement all loaders following existing `src/` module
patterns (`_load_yaml`, `_load_csv`, `comment='#'`, `root_dir` resolution).
Include validation: allocation sums, equipment existence, crop coverage.

**Reviewer task:**
- Read every loader and compare column names against actual CSV headers
- Verify (crop, type) indexing matches CSV `crop`/`processing_type` columns
- Verify wildcard expansion for `storage_labor-research.csv` handles
  `fresh_all`, `canned_all`, `dried_all`, `all` entries
- Test loaders standalone (call each with real paths, check no exceptions)

---

## Phase 3: Core Module — Processing Queue & Inventory Engine

**Goal:** Implement the daily simulation loop.

**Deliverables:**
- `_parse_harvest_columns(harvest_df)` — extract crop names from column patterns
- `_compute_product_weight(fresh_kg, crop, pathway, specs, losses)` — two-step loss
- `_step_day(day, harvest_row, queues, cohorts, allocation, specs, losses,
  equipment, spoilage_rates, labor_specs, storage_labor, policy)` — single day:
  1. Allocate harvest to queues with handling loss
  2. Apply queue spoilage (fresh ambient rate)
  3. If working day: process up to capacity, proportional sharing across crops
  4. Apply processing weight loss → create new cohorts
  5. Apply daily storage spoilage to all cohorts
  6. Remove expired cohorts (shelf life check)
  7. Compute daily energy (processing + cold storage)
  8. Compute daily labor by worker category
  9. Return updated queues, cohorts, and day's output row
- `compute_food_processing(...)` — public orchestrator: load data, loop days,
  build output DataFrame with all columns per spec, append cumulative metrics

**Writer task:** Implement all functions. Follow spec exactly for:
- Queue spoilage before processing (spec section "Queue Spoilage")
- Proportional capacity sharing (spec section "Capacity Sharing Across Crops")
- Cohort dict-of-lists structure (spec section "Cohort Data Structure")
- Non-working day handling (spoilage runs, processing doesn't)
- Cold storage energy from total climate-controlled inventory
- Labor aggregation by worker category from both CSV sources

**Reviewer task:**
- Trace through the dried tomato example in spec: 1000 kg allocated →
  970 kg after 3% handling loss → 67.9 kg dried product
- Verify queue spoilage uses `fresh` + `ambient` rate from spoilage CSV
- Verify shelf life expiry removes cohorts correctly
- Verify capacity sharing formula matches spec
- Verify cold storage energy uses `kg_per_m3_storage` denominator
- Check labor categories match spec's 6 output categories
- Check column names match spec's output column table exactly

---

## Phase 4: Save/Load & Standalone Verification

**Goal:** Complete the public API and verify end-to-end.

**Deliverables:**
- `save_food_processing(df, *, output_path)` — write to CSV
- `load_food_processing(*, output_path)` — read with `parse_dates=['day']`
- `if __name__ == '__main__':` block per spec's standalone verification section
- Run standalone: `python -m src.food_processing` — must complete without error
  and print summary statistics

**Writer task:** Implement save/load, add main block, run it.
**Reviewer task:**
- Verify output CSV exists at `simulation/daily_food_processing.csv`
- Spot-check: total_processed_kg > 0 on days after harvest
- Spot-check: spoilage_pct is reasonable (5-30% range typical)
- Verify cumulative columns are monotonically non-decreasing
- Verify all spec-documented columns present in output

---

## Phase 5: Notebook Integration

**Goal:** Add food processing to the simulation notebook as a standalone
post-harvest step. No upstream code changes.

**Deliverables:**
- Add cells to `notebooks/simulation.ipynb`:
  1. Call `compute_food_processing()` after harvest computation
  2. Call `save_food_processing()`
  3. Add summary output cell (total processed, spoilage rate, peak inventory,
     total processing energy, total labor hours)

**Writer task:** Add notebook cells following existing cell patterns
(inline comment descriptions, no markdown cells per project conventions).
Do NOT modify energy balance calls or pass food processing data upstream.

**Reviewer task:**
- Run full notebook via nbconvert — must execute without errors
- Verify `simulation/daily_food_processing.csv` written
- Verify no upstream modules (energy_balance, water_balance, crop_yield) modified

---

## Phase 6: Tests

**Goal:** Automated regression tests.

**Deliverables:**

- `tests/test_food_processing.py` with tests for:
  - Allocation validation (fractions sum to 1.0)
  - Two-step loss calculation (dried tomato example from spec)
  - Queue spoilage reduces queue on non-working days
  - Equipment capacity limits daily throughput
  - Proportional capacity sharing across crops
  - Cohort expiry at shelf life boundary
  - Cold storage energy proportional to climate-controlled inventory
  - Working day detection (Saturday = rest)

**Writer task:** Write pytest tests using minimal synthetic data (not full
simulation). Each test isolates one behavior.

**Reviewer task:**

- Run `python -m pytest tests/test_food_processing.py -v`
- Verify all tests pass
- Check edge cases: zero harvest, single crop, all pathways at 0% allocation

---

## Execution Sequence

```
Phase 0  ──→  Phase 1  ──→  Phase 2  ──→  Phase 3  ──→  Phase 4  ──→  Phase 5  ──→  Phase 6
 (data)      (config)      (loaders)     (engine)      (save/run)    (notebook)    (tests)
```

Each phase: Writer → Reviewer → Fix cycle → Next phase.

Phases 5 and 6 can run in parallel since they have no mutual dependency
(tests use synthetic data, notebook uses real data).

---

## Files Created or Modified

| File | Action |
|------|--------|
| `data/food_processing/processing_specs-research.csv` | Edit (fix fresh rows) |
| `settings/food_processing_base.yaml` | Create |
| `settings/data_registry_base.yaml` | Edit (add food_processing section) |
| `scenarios/scenario_base.yaml` | Edit (uncomment + fix path) |
| `src/food_processing.py` | Create (~400-600 lines) |
| `notebooks/simulation.ipynb` | Edit (add processing cells) |
| `tests/test_food_processing.py` | Create |

---

## Key Risks

| Risk | Mitigation |
|------|------------|
| Harvest CSV column names don't match expected pattern | Phase 2 reviewer verifies against actual `daily_harvest_yields.csv` |
| Storage labor wildcard expansion misses edge cases | Phase 2 reviewer tests all wildcard variants against CSV |
| Cohort tracking memory with 15-year simulation | Spec notes max ~8-16 active cohorts per crop×pathway — reviewer validates |
| Notebook cell ordering dependencies | Phase 5 reviewer runs full nbconvert execution |
