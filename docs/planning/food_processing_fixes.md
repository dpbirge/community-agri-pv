# Food Processing System Fixes

Issues identified during code review (2026-02-06). See full review context in conversation.

## Issue 2 — Processing energy cost not tracked

- **Location:** `src/simulation/simulation.py:process_harvests()`
- **Problem:** `processing_specs-research.csv` has `energy_kwh_per_kg` per pathway but `process_harvests()` never computes or deducts processing energy cost. Processed pathways appear more profitable than they are.
- **Fix:** For each pathway, compute `energy_kwh = raw_kg * energy_kwh_per_kg`, look up electricity price, deduct cost from pathway revenue. Add a `get_processing_energy()` method to `SimulationDataLoader`. Accumulate total processing energy into energy dispatch demand.
- **Data:** `data/parameters/crops/processing_specs-research.csv` column `energy_kwh_per_kg`

## Issue 3 — Processing labor cost not deducted

- **Location:** `src/simulation/simulation.py:process_harvests()`
- **Problem:** `processing_specs-research.csv` has `labor_hours_per_kg` per pathway but labor cost is never computed or deducted at harvest time. Net revenue from processed pathways is overstated.
- **Fix:** For each pathway, compute `labor_hrs = raw_kg * labor_hours_per_kg`, multiply by wage rate (from labor wages CSV or a configurable rate), deduct from pathway revenue. Store processing labor cost on `CropState` and accumulate on `FarmState`.
- **Data:** `data/parameters/crops/processing_specs-research.csv` column `labor_hours_per_kg`

## Issue 4 — post_harvest_loss_kg conflates waste with processing weight loss

- **Location:** `src/simulation/simulation.py:417`
- **Problem:** `total_post_harvest_loss_kg += raw_kg - sellable_kg` includes both intentional weight reduction (water evaporation in drying) and actual waste (spoilage, damage). For dried tomatoes this reports 139.8 kg "loss" from 150 kg input — but 93% is evaporated water, not waste.
- **Fix:** Track two separate metrics: `processing_weight_change_kg` (intentional: `raw_kg - output_kg`) and `post_harvest_waste_kg` (actual losses: `output_kg - sellable_kg`). Update `CropState`, `FarmState`, and `YearlyFarmMetrics` accordingly.
- **Affected state:** `CropState.post_harvest_loss_kg`, `FarmState.cumulative_post_harvest_loss_kg`, `YearlyFarmMetrics.post_harvest_loss_kg`

## Issue 5 — MarketResponsive reference prices hardcoded

- **Location:** `src/policies/food_policies.py:149-155`
- **Problem:** `REFERENCE_PRICES` dict has fixed USD values. Over multi-year simulations with price inflation or currency shifts, the 80% threshold becomes stale.
- **Fix options:**
  1. Make reference prices a constructor parameter so they can be set from scenario YAML
  2. Compute reference prices from the crop price CSV (e.g., rolling 12-month average) passed via `FoodProcessingContext`
  3. At minimum, add `reference_prices` as a kwarg to `MarketResponsive.__init__()` with the current dict as default
- **Preferred:** Option 3 (minimal change, backward compatible) with option 2 as future enhancement

## Issue 6 — No fraction validation in ProcessingAllocation

- **Location:** `src/policies/food_policies.py:37-54`
- **Problem:** Docstring says "Fractions must sum to 1.0" but no enforcement. A bad policy or config error could silently create or lose harvest volume.
- **Fix:** Add `__post_init__` validation to `ProcessingAllocation` that checks `abs(sum - 1.0) < tolerance` and raises `ValueError` if violated. Use tolerance of 0.001 to handle floating point.
