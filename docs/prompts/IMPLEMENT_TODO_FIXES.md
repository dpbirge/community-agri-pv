# Food Processing & Economics Implementation Prompt

**Copy and paste this prompt to implement the TODO fixes in sequence.**

---

Implement the 7 fixes and features listed in `TODO.md`. Each task has a detailed plan in `docs/planning/` that you must read before starting work. The plans contain problem analysis, proposed solutions, decision points, and file-by-file implementation steps.

## Critical Instructions

- **Read the full plan file before writing any code for that task.**
- **Run the simulation after each wave** to verify nothing is broken: `python src/simulation/results.py settings/settings.yaml`
- **Do not skip decision points.** Each plan lists decisions that need user input — ask before proceeding on those.
- **Commit after each wave** with a descriptive message summarizing what changed.

## Reference Documents

Read before starting:
1. `CLAUDE.md` — Project architecture, conventions, key files
2. `docs/architecture/calculations.md` — Current calculation methodology
3. `docs/architecture/policies.md` — Policy decision rules

## Dependency Graph

```
Wave 1 (parallel)          Wave 2 (sequential)       Wave 3 (parallel w/ Wave 2)    Wave 4 (after Wave 2)
┌──────────────────┐      ┌───────────────────────┐  ┌──────────────────────────┐   ┌───────────────────┐
│ A1: Fraction     │      │ B1: Split loss metrics │  │ C1: Fix inflation        │   │ D1: Cool storage  │
│     validation   │      │         ↓              │  │                          │   │                   │
│                  │      │ B2: Energy tracking    │  │                          │   │                   │
│ A2: Reference    │      │         ↓              │  │                          │   │                   │
│     prices       │      │ B3: Labor costs        │  │                          │   │                   │
└──────────────────┘      └───────────────────────┘  └──────────────────────────┘   └───────────────────┘
```

Tasks B1, B2, B3 all modify `process_harvests()` in `simulation.py` and must run sequentially. C1 modifies price lookups in `data_loader.py` and `simulation.py` but does not touch `process_harvests()`, so it can run in parallel with Wave 2. D1 depends on B1 (loss separation is a prerequisite for storage-condition-aware loss lookups).

---

## Wave 1 — Quick Fixes (2 parallel agents)

Small, self-contained changes that touch isolated code. No dependencies.

### Agent A1: Fraction Sum Validation

**Plan:** `docs/planning/add_fraction_validation.md`

**Scope:** Add `__post_init__` validation to `ProcessingAllocation` in `src/policies/food_policies.py`. Enforce non-negativity of each fraction and sum-to-1.0 within tolerance (0.001). Raise `ValueError` on violation.

**Files modified:**
- `src/policies/food_policies.py` — Add `__post_init__` to `ProcessingAllocation`

**Decision points from plan:**
1. Tolerance value (0.001 recommended)
2. Error type: `ValueError` vs custom exception
3. Whether to auto-normalize near-valid sums or always reject

### Agent A2: Replace Hardcoded REFERENCE_PRICES

**Plan:** `docs/planning/replace_reference_prices.md`

**Scope:** Make `REFERENCE_PRICES` in the `MarketResponsive` class configurable via `__init__` kwargs and derive defaults from CSV historical price averages instead of the current hardcoded values (which are 3-6x too low, effectively making the "low price → more processing" branch dead code).

**Files modified:**
- `src/policies/food_policies.py` — `MarketResponsive.__init__()` accepts `reference_prices` kwarg
- `src/simulation/data_loader.py` — Add `compute_reference_crop_prices()` method
- `src/policies/food_policies.py` — `get_food_policy()` factory passes data-derived prices
- `settings/settings.yaml` — Optional `market_responsive` config section under `community_policy_parameters`

**Decision points from plan:**
1. Percentile for "low" threshold (25th percentile recommended)
2. Whether to pass reference prices via scenario YAML or compute at runtime

**After Wave 1:** Run the simulation to verify. Commit.

---

## Wave 2 — Process Harvests Refactor (1 agent, 3 sequential tasks)

These three tasks all modify `process_harvests()` in `simulation.py` and related state/metrics code. They must be done in order by a single agent to avoid conflicts.

### Task B1: Split Loss Metrics

**Plan:** `docs/planning/split_loss_metrics.md`

**Scope:** Replace `post_harvest_loss_kg` with two separate metrics: `post_harvest_waste_kg` (actual spoilage/damage) and `processing_weight_loss_kg` (intentional water removal, trimming). This requires changes to the process_harvests() loop, state dataclasses, and metrics calculations.

**Files modified:**
- `src/simulation/simulation.py` — Refactor loss calculation in `process_harvests()`
- `src/simulation/state.py` — Replace `post_harvest_loss_kg` field on `CropState` and `FarmState`; add new fields to `YearlyFarmMetrics`
- `src/simulation/metrics.py` — Update metric calculations
- `src/simulation/results.py` — Update CSV output columns and plot labels

**Decision points from plan:**
1. Whether to keep a computed `total_loss_kg` property for backward compatibility
2. Naming convention: `processing_weight_loss_kg` vs `processing_conversion_loss_kg`

### Task B2: Processing Energy Tracking

**Plan:** `docs/planning/add_processing_energy_tracking.md`

**Scope:** Add energy cost tracking to `process_harvests()` using `energy_kwh_per_kg` from `processing_specs-research.csv`. Feed processing energy demand into `dispatch_energy()` so it is included in the community's total electricity load.

**Files modified:**
- `src/simulation/data_loader.py` — Add `get_energy_kwh_per_kg()` accessor
- `src/simulation/simulation.py` — Compute processing energy in pathway loop; pass to `dispatch_energy()`
- `src/simulation/state.py` — Add `processing_energy_kwh` to `CropState`/`FarmState`
- `src/simulation/metrics.py` — Include processing energy in yearly metrics

**Decision points from plan:**
1. Whether processing energy is dispatched per-farm or aggregated at community level
2. Whether to deduct energy cost from crop revenue or track it as a separate line item

### Task B3: Processing Labor Costs

**Plan:** `docs/planning/add_processing_labor_costs.md`

**Scope:** Deduct labor costs from processing revenue using `labor_hours_per_kg` from `processing_specs-research.csv` and wage rates from `labor_wages-research.csv`. Track processing labor hours and costs separately.

**Files modified:**
- `src/simulation/data_loader.py` — Add `get_processing_labor_hours_per_kg()` accessor
- `src/simulation/simulation.py` — Compute labor cost in pathway loop; deduct from revenue
- `src/simulation/state.py` — Add `processing_labor_hours` and `processing_labor_cost_usd` fields
- `src/simulation/metrics.py` — Include processing labor in yearly financial metrics

**Decision points from plan:**
1. Whether to use a single processing wage rate or differentiate by skill level
2. Whether labor cost is deducted from crop revenue or tracked as a separate operating expense

**After Wave 2:** Run the simulation to verify. Commit.

---

## Wave 3 — Price System Overhaul (1 agent, parallel with Wave 2)

This task modifies price loading and lookup code in `data_loader.py` and `simulation.py` but does **not** touch `process_harvests()`, so it can run concurrently with Wave 2.

### Agent C1: Fix Inflation / Price-Year Alignment

**Plan:** `docs/planning/fix_inflation.md`

**Scope:** Fix the temporal mismatch between historic prices (2015-era revenues) and current-dollar infrastructure costs (2024 CAPEX/OPEX). Implement a "re-anchoring" approach: preserve seasonal/market variation patterns from historical price series but shift them to a reference price level (e.g., 2024 dollars). Add `price_basis_year` to scenario configuration.

**Files modified:**
- `src/simulation/data_loader.py` — Add `reanchor_price_series()` function; call during price loading
- `src/settings/loader.py` — Add `price_basis_year` to `EconomicsConfig` dataclass
- `settings/settings.yaml` — Add `economics.price_basis_year: 2024`
- `src/simulation/simulation.py` — Verify price lookups use re-anchored data (no structural changes needed if anchoring happens at load time)
- `docs/architecture/calculations.md` — Document the re-anchoring methodology

**Decision points from plan:**
1. Re-anchoring method: ratio-based (multiply by anchor/mean) vs additive shift
2. Whether `price_basis_year` should also adjust CAPEX/OPEX or only revenue prices
3. Whether to re-anchor all price series (crops, electricity, diesel, water) or only crops
4. Fallback behavior if historical data doesn't cover the `price_basis_year`

**After Wave 3:** Run the simulation to verify. Commit.

---

## Wave 4 — Cool Storage (1 agent, after Wave 2 completes)

This is the largest task. It depends on B1 (loss metric separation) because cool storage needs storage-condition-aware loss lookups, which require the split loss metric infrastructure.

### Agent D1: Add Cool Storage to Processing Chain

**Plan:** `docs/planning/add_cool_storage.md`

**Scope:** Add an intermediate storage condition `cool_storage` (15-22C via evaporative cooling) between ambient and climate-controlled. This spans data files, configuration, data loading, and the simulation loop. The plan has 6 phases and 20 implementation steps.

**Files modified:**
- `data/parameters/crops/spoilage_rates-toy.csv` — Add `cool_storage` rows
- `data/parameters/crops/post_harvest_losses-research.csv` — Add `storage_condition` column
- `data/parameters/equipment/processing_equipment-toy.csv` — Add cool storage equipment
- `data/parameters/costs/capital_costs-research.csv` — Add cool storage cost entries
- `data/scripts/generate_crop_parameters.py` — Update generation with `cool_storage` condition
- `settings/settings.yaml` — Add `cool_storage` section and `storage_condition` per category
- `src/settings/loader.py` — Add `storage_condition` to `ProcessingCategoryConfig`
- `src/simulation/data_loader.py` — Add `storage_condition` parameter to `get_post_harvest_loss_fraction()`
- `src/simulation/simulation.py` — Pass storage condition in `process_harvests()`; add cool storage energy/water to daily dispatch
- `src/simulation/state.py` — Add cool storage tracking fields
- `src/simulation/metrics.py` — Include cool storage in metrics

**Decision points from plan:**
1. Weather humidity data: use fixed seasonal cooling factors (recommended) vs add humidity to Layer 1
2. Loss model: instant loss with adjusted percentages (recommended) vs daily inventory tracking
3. Storage as infrastructure section AND per-category attribute (recommended) vs one or the other
4. Cool storage water consumption: track explicitly (recommended) vs ignore
5. Implementation order relative to other food processing fixes (loss split is prerequisite)

**After Wave 4:** Run the simulation to verify. Commit.

---

## Verification Checklist

After all waves are complete:

- [ ] Simulation runs without errors: `python src/simulation/results.py settings/settings.yaml`
- [ ] `ProcessingAllocation` fractions are validated (test with invalid values)
- [ ] `MarketResponsive` uses CSV-derived reference prices (verify "low price" branch activates)
- [ ] Loss metrics show separate waste vs weight loss in output CSVs
- [ ] Processing energy appears in energy dispatch totals
- [ ] Processing labor costs appear as a deduction in financial metrics
- [ ] Price series are re-anchored to `price_basis_year` (compare pre/post NPV)
- [ ] Cool storage reduces post-harvest waste for fresh and dried pathways
- [ ] All output CSVs have updated column headers reflecting new metrics

## Notes

- Plans may reference absolute file paths from the analysis session. Use relative paths from project root when implementing.
- Each plan has a "Questions / Remaining Unknowns" section — review these but don't block on them unless they affect the implementation approach.
- Tasks B1-B3 (Wave 2) touch overlapping code. If implementing as separate commits within one agent, run the simulation between each to catch regressions early.
