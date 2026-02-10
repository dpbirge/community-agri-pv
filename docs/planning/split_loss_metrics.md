# Split Loss Metrics: Waste vs Processing Weight Loss

**Generated:** February 6, 2026

## Plan: Split post_harvest_loss_kg into Waste vs. Processing Weight Loss

### Problem Statement

The current `post_harvest_loss_kg` metric lumps together two fundamentally different things:

1. **Actual waste** -- spoilage, handling damage, transport damage, quality rejection, spillage. This is the kind of loss that represents a real problem, something the community would want to minimize.

2. **Intentional processing weight reduction** -- primarily water removal during drying, peeling, trimming, and concentration. This is a planned, desirable transformation. When 150 kg of fresh tomatoes are dried, 139.5 kg of water evaporates (93% weight loss). That is not "loss" in any meaningful sense; it is the intended outcome of the drying process.

The current calculation on line 417 of `simulation.py`:

```python
total_post_harvest_loss_kg += raw_kg - sellable_kg
```

This computes `raw_kg - sellable_kg`, which equals the processing weight loss (water removal, trimming) PLUS the post-harvest waste (spoilage, damage). For dried tomatoes, this reports ~139.8 kg "loss" from 150 kg input, of which ~139.5 kg is evaporated water and only ~0.3 kg is actual spoilage.

This creates several problems:
- **Misleading metrics**: A farm using MaximizeStorage policy (35% dried) appears to have massive "losses" compared to AllFresh, when in reality it has much lower waste.
- **Poor policy comparison**: Communities cannot compare food processing strategies if the "loss" metric does not distinguish value-creating transformation from value-destroying waste.
- **Inaccurate efficiency assessment**: Food loss reduction is a key sustainability indicator (SDG 12.3). Conflating intentional processing with waste makes it impossible to track genuine food loss.

### Current Behavior

**Data sources** (two separate CSV files, already correctly separated conceptually):

- `processing_specs-research.csv` column `weight_loss_pct` -- intentional weight change during processing (0% for fresh, 3% for packaged tomato, 93% for dried tomato)
- `post_harvest_losses-research.csv` column `loss_pct` -- actual waste (28% for fresh tomato, 3% for dried tomato)

**Calculation in `process_harvests()` (`simulation.py`, lines 393-417)**:

For each pathway, the code correctly computes the two stages separately:
```python
# Stage 1: intentional processing weight loss
weight_loss_frac = data_loader.get_weight_loss_fraction(crop.crop_name, pathway)
output_kg = raw_kg * (1 - weight_loss_frac)

# Stage 2: actual waste/spoilage
loss_frac = data_loader.get_post_harvest_loss_fraction(crop.crop_name, pathway)
sellable_kg = output_kg * (1.0 - loss_frac)
```

But then on line 417, both are merged into one number:
```python
total_post_harvest_loss_kg += raw_kg - sellable_kg
```

Which equals: `raw_kg * weight_loss_frac + output_kg * loss_frac` (processing weight change + waste).

**Where the merged metric propagates**:

| Location | Field Name | Purpose |
|----------|-----------|---------|
| `CropState` (state.py:39) | `post_harvest_loss_kg` | Per-crop-planting total |
| `FarmState` (state.py:230) | `cumulative_post_harvest_loss_kg` | Farm yearly accumulator |
| `YearlyFarmMetrics` (state.py:431) | `post_harvest_loss_kg` | Yearly snapshot |
| `ComputedYearlyMetrics` (metrics.py:99) | `post_harvest_loss_kg` | Derived metrics dataclass |
| `compute_yearly_metrics()` (metrics.py:228) | `post_harvest_loss_kg` | Passed through to computed metrics |
| `snapshot_yearly_metrics()` (simulation.py:484) | `post_harvest_loss_kg` | Yearly snapshot creation |
| `reset_farm_for_new_year()` (simulation.py:504) | Reset to 0.0 | Year boundary reset |
| `validation_plots.py` (line 671) | Used in revenue calculation | Validation figure |

**Where the metric is NOT yet used**:

- `write_yearly_summary()` in results.py -- the field exists on ComputedYearlyMetrics but is not included in the CSV output rows
- `notebook_plotting.py` -- no references at all
- `monte_carlo.py`, `sensitivity.py` -- no references

### Desired Behavior

Track three separate metrics:

1. **`processing_weight_loss_kg`** -- Intentional weight reduction from processing (water removal, trimming, concentration). Formula: `raw_kg - output_kg` = `raw_kg * weight_loss_frac`. This is expected, planned, and proportional to how much crop is processed.

2. **`post_harvest_waste_kg`** -- Actual losses from spoilage, damage, rejection. Formula: `output_kg - sellable_kg` = `output_kg * loss_frac`. This is the metric communities want to minimize.

3. **`total_weight_reduction_kg`** (computed, not stored) -- Sum of the above two, available if anyone wants the old behavior. Equals `raw_kg - sellable_kg`.

### Proposed Solution

#### Step 1: Update CropState dataclass (`state.py`)

Replace line 39:
```python
post_harvest_loss_kg: float = 0.0  # Total post-harvest loss (fresh + processing waste)
```

With:
```python
processing_weight_loss_kg: float = 0.0  # Intentional weight reduction (water removal, trimming)
post_harvest_waste_kg: float = 0.0  # Actual waste (spoilage, damage, rejection)
```

Remove the old `post_harvest_loss_kg` field entirely. No backward compatibility needed per project coding principles.

#### Step 2: Update FarmState dataclass (`state.py`)

Replace line 230:
```python
cumulative_post_harvest_loss_kg: float = 0.0
```

With:
```python
cumulative_processing_weight_loss_kg: float = 0.0
cumulative_post_harvest_waste_kg: float = 0.0
```

#### Step 3: Update YearlyFarmMetrics dataclass (`state.py`)

Replace line 431:
```python
post_harvest_loss_kg: float = 0.0
```

With:
```python
processing_weight_loss_kg: float = 0.0
post_harvest_waste_kg: float = 0.0
```

#### Step 4: Update process_harvests() calculation (`simulation.py`)

Replace the loop accumulator initialization (line 390):
```python
total_post_harvest_loss_kg = 0.0
```

With:
```python
total_processing_weight_loss_kg = 0.0
total_post_harvest_waste_kg = 0.0
```

Replace line 417:
```python
total_post_harvest_loss_kg += raw_kg - sellable_kg
```

With:
```python
total_processing_weight_loss_kg += raw_kg - output_kg
total_post_harvest_waste_kg += output_kg - sellable_kg
```

These two values come directly from the already-computed `weight_loss_frac` and `loss_frac` stages, so no new data lookups are needed.

Update CropState assignment (line 430):
```python
crop.post_harvest_loss_kg = total_post_harvest_loss_kg
```

Becomes:
```python
crop.processing_weight_loss_kg = total_processing_weight_loss_kg
crop.post_harvest_waste_kg = total_post_harvest_waste_kg
```

Update FarmState accumulation (line 438):
```python
farm_state.cumulative_post_harvest_loss_kg += total_post_harvest_loss_kg
```

Becomes:
```python
farm_state.cumulative_processing_weight_loss_kg += total_processing_weight_loss_kg
farm_state.cumulative_post_harvest_waste_kg += total_post_harvest_waste_kg
```

#### Step 5: Update snapshot_yearly_metrics() (`simulation.py`)

Replace line 484:
```python
post_harvest_loss_kg=farm_state.cumulative_post_harvest_loss_kg,
```

With:
```python
processing_weight_loss_kg=farm_state.cumulative_processing_weight_loss_kg,
post_harvest_waste_kg=farm_state.cumulative_post_harvest_waste_kg,
```

#### Step 6: Update reset_farm_for_new_year() (`simulation.py`)

Replace line 504:
```python
farm_state.cumulative_post_harvest_loss_kg = 0.0
```

With:
```python
farm_state.cumulative_processing_weight_loss_kg = 0.0
farm_state.cumulative_post_harvest_waste_kg = 0.0
```

#### Step 7: Update ComputedYearlyMetrics dataclass (`metrics.py`)

Replace line 99:
```python
post_harvest_loss_kg: float = 0.0
```

With:
```python
processing_weight_loss_kg: float = 0.0
post_harvest_waste_kg: float = 0.0
```

#### Step 8: Update compute_yearly_metrics() (`metrics.py`)

Replace line 228:
```python
post_harvest_loss_kg=m.post_harvest_loss_kg,
```

With:
```python
processing_weight_loss_kg=m.processing_weight_loss_kg,
post_harvest_waste_kg=m.post_harvest_waste_kg,
```

#### Step 9: Update write_yearly_summary() in results.py (currently omitted, should be added)

Add both new fields to the output CSV rows dict (currently `post_harvest_loss_kg` is not written, but the new metrics should be):
```python
"processing_weight_loss_kg": m.processing_weight_loss_kg,
"post_harvest_waste_kg": m.post_harvest_waste_kg,
```

#### Step 10: Update validation_plots.py

In `plot_food_processing_validation()` (line 671), the validation plot already uses a correct local calculation:
```python
sellable_wt = output_wt * (1 - post_harvest_loss / 100)
```

This function loads data directly from CSV files, not from simulation state, so it does not need structural changes. However, the function name and comments reference "post_harvest_loss" generically. Update the local variable name for clarity if desired, but this is cosmetic.

#### Step 11: Update TODO.md

Remove the completed TODO item:
```
- Split post_harvest_loss_kg into actual waste vs processing weight loss (water removal) -- separate metrics
```

### Decision Points

1. **Naming convention**: The plan uses `processing_weight_loss_kg` and `post_harvest_waste_kg`. Alternatives considered:
   - `water_removal_kg` -- too narrow (also includes peeling, trimming for canned/packaged)
   - `dehydration_loss_kg` -- same issue, only applies to drying
   - `conversion_weight_loss_kg` -- less clear
   - **Recommendation**: `processing_weight_loss_kg` and `post_harvest_waste_kg` are the clearest pair. "Weight loss" is the standard food processing term for intentional mass reduction. "Waste" clearly distinguishes from intentional processing.

2. **Whether to track water removed separately**: For drying specifically, the weight loss is almost entirely water. For canned/packaged, it includes trimming, peeling, etc. The current `weight_loss_pct` in the CSV already captures the combined effect. Splitting further (water vs. trimming) would require new CSV columns and new data research. **Recommendation**: Not needed now. The `processing_weight_loss_kg` metric captures the aggregate of all intentional weight changes. If water-vs-trimming breakdowns become important later, add a `water_removed_pct` column to the processing_specs CSV.

3. **Backward compatibility of output formats**: Per the project's coding principles ("Backwards compatibility is generally not required... Code should be cleaned up during refactors"), the old `post_harvest_loss_kg` field should be removed entirely rather than kept alongside the new fields. Any downstream consumers (there are currently none beyond the internal metrics pipeline) will need to use the new field names.

4. **Whether to add a computed total**: A convenience property `total_weight_reduction_kg` (= processing_weight_loss_kg + post_harvest_waste_kg) could be added to CropState for anyone who wants the old combined number. **Recommendation**: Do not add it. The point of this change is to force consumers to think about which metric they actually want. A combined total can be trivially computed where needed.

### File Change Summary

| File | Changes |
|------|---------|
| `src/simulation/state.py` | Replace `post_harvest_loss_kg` with two new fields on CropState, FarmState, YearlyFarmMetrics |
| `src/simulation/simulation.py` | Split accumulator in process_harvests(), update snapshot_yearly_metrics(), update reset_farm_for_new_year() |
| `src/simulation/metrics.py` | Replace field on ComputedYearlyMetrics, update compute_yearly_metrics() |
| `src/simulation/results.py` | Add both new metrics to write_yearly_summary() output CSV |
| `src/plotting/validation_plots.py` | Cosmetic: clarify variable naming in revenue formula (optional) |
| `TODO.md` | Remove completed item |

### Questions

1. **Should monthly metrics also track the split?** Currently `MonthlyFarmMetrics` in metrics.py does not track post-harvest loss at all. If monthly food processing tracking is added later, it should use the new split fields from the start.

2. **Per-pathway breakdown**: Currently the crop-level metric is a single total across all pathways. Should we also store per-pathway breakdowns (e.g., `{fresh: {waste: X, processing_loss: Y}, dried: {...}}`)? This would enable analysis like "how much waste occurs in each pathway?" The data to compute it already exists in the loop. **Recommendation**: Not for this change. Add per-pathway tracking as a separate enhancement if policy comparison requires it.

3. **Impact on food_processing_fixes.md Issue 4**: This plan directly implements the fix described in Issue 4 of `docs/planning/food_processing_fixes.md`. After implementation, Issue 4 should be marked complete in that document.

### Critical Files for Implementation

- `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/simulation.py` - Contains process_harvests() where the loss calculation happens (lines 390-438) and snapshot/reset functions
- `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/state.py` - Contains CropState, FarmState, YearlyFarmMetrics dataclasses that store the metric
- `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/metrics.py` - Contains ComputedYearlyMetrics and compute_yearly_metrics() that propagate the metric
- `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/results.py` - Output CSV writing where the new metrics should appear
- `/Users/dpbirge/GITHUB/community-agri-pv/data/parameters/crops/processing_specs-research.csv` - Reference: weight_loss_pct column provides the processing weight loss data (no changes needed)
