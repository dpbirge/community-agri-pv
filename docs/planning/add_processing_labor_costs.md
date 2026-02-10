# Add Processing Labor Cost Deduction

**Generated:** February 6, 2026

## Implementation Plan: Add Processing Labor Cost Deduction in `process_harvests()`

### Problem Statement

The `process_harvests()` function in `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/simulation.py` (lines 318-440) calculates revenue from food processing pathways (fresh, packaged, canned, dried) but never deducts the labor cost of performing that processing. The `processing_specs-research.csv` file contains a `labor_hours_per_kg` column with per-pathway labor intensity data (ranging from 0.0 hours/kg for fresh to 0.14 hours/kg for dried potato), but this data is loaded and never used during simulation. As a result, net revenue from processed pathways is overstated -- processed goods appear more profitable than they actually are.

This is a companion issue to Issue 2 (processing energy cost not tracked) from the food processing fixes planning document at `/Users/dpbirge/GITHUB/community-agri-pv/docs/planning/food_processing_fixes.md`.

### Current Behavior

**How `process_harvests()` handles costs now (simulation.py lines 386-438):**

The function iterates over each processing pathway (fresh, packaged, canned, dried), calculates:
1. `raw_kg` = harvest yield multiplied by pathway fraction
2. `output_kg` = raw_kg adjusted for weight loss (from `get_weight_loss_fraction()`)
3. `sellable_kg` = output_kg adjusted for post-harvest loss (from `get_post_harvest_loss_fraction()`)
4. `revenue` = sellable_kg multiplied by fresh price multiplied by value-add multiplier (from `get_value_multiplier()`)

Revenue is accumulated and stored on `CropState` and `FarmState`. No costs of any kind are deducted within this function. The revenue figures are gross revenue, not net revenue.

**How labor costs are tracked elsewhere (two parallel systems):**

1. **Monthly metrics system** (`metrics.py` lines 312-313): Uses `data_loader.get_labor_cost_usd_ha_month()` which computes a flat per-hectare-per-month labor cost from the `labor_requirements-toy.csv` file. This covers field labor (planting, harvesting, weeding, etc.) and maps skill levels to wage rates from `labor_wages-toy.csv`. This is a generic area-based estimate, not tied to actual processing volumes.

2. **Yearly farm metrics system** (`metrics.py` lines 687-731): Uses `LABOR_PROCESSING_HRS_PER_KG` (a fixed constant of 0.02 hrs/kg from `calculations.py` line 839) multiplied by `processed_output_kg` to estimate processing labor hours. Then multiplies all labor hours by `LABOR_HOURLY_RATE_USD` ($3.50/hr from `calculations.py` line 821) to get total labor cost. This is a post-hoc calculation for metrics reporting only -- it does not feed back into revenue or economic state.

**Key gap:** Neither labor system deducts processing labor cost from pathway revenue at the time of harvest. The `total_labor_cost_usd` field on `YearlyFarmMetrics` (state.py line 424) and `FarmMetrics` (metrics.py line 108) captures an estimate for reporting, but it uses a flat rate constant (`LABOR_PROCESSING_HRS_PER_KG = 0.02`) instead of the crop-and-pathway-specific `labor_hours_per_kg` values from the CSV.

**Available but unused data:**

The processing specs CSV (`/Users/dpbirge/GITHUB/community-agri-pv/data/parameters/crops/processing_specs-research.csv`) contains `labor_hours_per_kg` values that vary significantly by crop and pathway:

| Crop | Pathway | labor_hours_per_kg |
|------|---------|-------------------|
| tomato | fresh | 0.00 |
| tomato | packaged | 0.02 |
| tomato | canned | 0.07 |
| tomato | dried | 0.10 |
| potato | canned | 0.09 |
| potato | dried | 0.14 |
| cucumber | canned | 0.05 |
| kale | dried | 0.08 |

These values are already loaded into `self.processing_specs` in `SimulationDataLoader` (data_loader.py line 844) and accessible via the multi-indexed DataFrame at key `(crop_name, processing_type)`, but no accessor method exists to retrieve `labor_hours_per_kg`.

The labor wages CSV (`/Users/dpbirge/GITHUB/community-agri-pv/data/parameters/labor/labor_wages-toy.csv`) has a `processing_worker` category at $1.43/hr (semi-skilled). The current metrics system uses a flat $3.50/hr (`LABOR_HOURLY_RATE_USD`) for all labor categories, which is significantly higher than the processing-specific wage.

### Desired Behavior

When `process_harvests()` processes each pathway, it should:

1. Look up `labor_hours_per_kg` for the crop/pathway combination from the processing specs CSV.
2. Compute `labor_hours = raw_kg * labor_hours_per_kg`.
3. Compute `labor_cost_usd = labor_hours * processing_wage_rate`.
4. Deduct `labor_cost_usd` from pathway revenue (so revenue stored on `CropState` is net of processing labor cost).
5. Accumulate processing labor cost and hours on `CropState` and `FarmState` for reporting.
6. Flow the processing labor cost into `YearlyFarmMetrics` and `EconomicState` at year boundaries.

### Proposed Solution

#### Step 1: Add accessor method to SimulationDataLoader

**File:** `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/data_loader.py`

Add a new method `get_processing_labor_hours_per_kg()` to `SimulationDataLoader` (after `get_value_multiplier()` around line 1062). Pattern follows `get_weight_loss_fraction()` and `get_value_multiplier()`:

```python
def get_processing_labor_hours_per_kg(self, crop_name, processing_type):
    """Get labor hours per kg of fresh input for a crop/processing combination.

    Args:
        crop_name: Name of crop
        processing_type: Processing pathway (fresh, packaged, canned, dried)

    Returns:
        float: Labor hours per kg of fresh input
    """
    return float(self.processing_specs.loc[(crop_name, processing_type), "labor_hours_per_kg"])
```

Also add a method to retrieve the processing worker wage rate from the already-loaded wage data, or expose the processing worker wage as a constant/property. The simplest approach: add a `get_processing_wage_usd_per_hour()` method that returns the `processing_worker` wage from the wages CSV. This requires storing the wage lookup during `_load_labor_costs()`.

Alternatively, use the already-existing `LABOR_HOURLY_RATE_USD` constant from `calculations.py` for consistency with the existing metrics system, even though it overstates the processing-specific rate. This is a decision point (see below).

#### Step 2: Add processing labor cost fields to CropState and FarmState

**File:** `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/state.py`

Add to `CropState` (after `post_harvest_loss_kg` around line 39):
```python
processing_labor_hours: float = 0.0
processing_labor_cost_usd: float = 0.0
```

Add to `FarmState` (after `cumulative_post_harvest_loss_kg` around line 230):
```python
cumulative_processing_labor_hours: float = 0.0
cumulative_processing_labor_cost_usd: float = 0.0
```

Add to `YearlyFarmMetrics` (after `post_harvest_loss_kg` around line 431):
```python
processing_labor_hours: float = 0.0
processing_labor_cost_usd: float = 0.0
```

Note: `YearlyFarmMetrics` already has a `labor_cost_usd` field at line 424. The new `processing_labor_cost_usd` field tracks specifically the per-pathway processing labor cost computed at harvest time, which is a subset of total labor cost. Whether to fold it into the existing `labor_cost_usd` or keep it separate is a design choice -- keeping it separate provides clearer accounting.

#### Step 3: Modify `process_harvests()` to compute and deduct labor cost

**File:** `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/simulation.py`

Inside the pathway loop (lines 393-423), after computing `revenue` and before accumulating totals, add labor cost calculation:

```python
# Processing labor cost -- from processing_specs CSV
labor_hrs_per_kg = data_loader.get_processing_labor_hours_per_kg(crop.crop_name, pathway)
labor_hours = raw_kg * labor_hrs_per_kg
labor_cost = labor_hours * processing_wage_rate
revenue -= labor_cost
total_processing_labor_hours += labor_hours
total_processing_labor_cost += labor_cost
```

The `processing_wage_rate` needs to be obtained before the loop. Options:
- Pass it as a parameter to `process_harvests()`
- Look it up from `data_loader` (new method)
- Use the `LABOR_HOURLY_RATE_USD` constant from `calculations.py`

Initialize accumulators before the pathway loop:
```python
total_processing_labor_hours = 0.0
total_processing_labor_cost = 0.0
```

After the pathway loop, store on crop state and update farm accumulators:
```python
crop.processing_labor_hours = total_processing_labor_hours
crop.processing_labor_cost_usd = total_processing_labor_cost
farm_state.cumulative_processing_labor_hours += total_processing_labor_hours
farm_state.cumulative_processing_labor_cost_usd += total_processing_labor_cost
```

#### Step 4: Update `snapshot_yearly_metrics()` to include processing labor

**File:** `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/simulation.py`

In `snapshot_yearly_metrics()` (lines 443-485), add processing labor fields to the `YearlyFarmMetrics` constructor:

```python
processing_labor_hours=farm_state.cumulative_processing_labor_hours,
processing_labor_cost_usd=farm_state.cumulative_processing_labor_cost_usd,
```

#### Step 5: Reset processing labor accumulators at year boundary

**File:** `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/simulation.py`

In `reset_farm_for_new_year()` (lines 488-504), add:
```python
farm_state.cumulative_processing_labor_hours = 0.0
farm_state.cumulative_processing_labor_cost_usd = 0.0
```

#### Step 6: Flow processing labor cost into EconomicState

**File:** `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/simulation.py`

At year boundaries (lines 833-842) and final year (lines 1034-1043), the economic state update currently uses `year_water_cost` as the only operating cost. Processing labor cost should be added:

```python
year_processing_labor = sum(fs.cumulative_processing_labor_cost_usd for fs in state.farms)
state.economic.cumulative_operating_cost_usd += year_water_cost + annual_infra + year_processing_labor
state.economic.cash_reserves_usd += year_revenue - year_water_cost - annual_infra - year_processing_labor
```

#### Step 7: Reconcile with existing metrics labor system

**File:** `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/metrics.py`

The existing metrics system (lines 687-731) computes processing labor hours using the flat `LABOR_PROCESSING_HRS_PER_KG = 0.02` constant multiplied by `processed_output_kg`. After this change, actual per-pathway labor hours will be tracked on `YearlyFarmMetrics.processing_labor_hours`. The metrics computation should prefer the simulation-computed value when available:

```python
# Use simulation-tracked processing labor if available; otherwise fall back to estimate
if fm.processing_labor_hours > 0:
    processing_hrs = fm.processing_labor_hours
else:
    processing_hrs = fm.processed_output_kg * LABOR_PROCESSING_HRS_PER_KG
```

This maintains backward compatibility for any code paths that do not go through the updated `process_harvests()`.

#### Step 8: Update results output

**File:** `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/results.py`

Add `processing_labor_cost_usd` to the yearly metrics output dict (around line 67):
```python
"processing_labor_cost_usd": m.processing_labor_cost_usd,
```

### Decision Points

1. **Wage rate source: Which rate to use for processing labor?**

   Three options exist:
   - **Option A:** Use `LABOR_HOURLY_RATE_USD` ($3.50/hr) from `calculations.py`. Advantage: consistent with the existing metrics system. Disadvantage: overstates processing labor cost because this is a blended rate across all worker types, not a processing-specific rate.
   - **Option B:** Use the `processing_worker` rate from `labor_wages-toy.csv` ($1.43/hr). Advantage: accurate to the data. Disadvantage: introduces a second wage rate system that diverges from the flat-rate used everywhere else.
   - **Option C:** Make the processing wage rate a configurable parameter in the scenario YAML, with the CSV value as default. Advantage: flexible. Disadvantage: added complexity for a feature that may not need scenario-level variation yet.

   **Recommendation:** Option B for the `process_harvests()` deduction (use the actual processing_worker wage from the CSV, loaded via `data_loader`). Then update the metrics system in Step 7 to also use the simulation-tracked values. This gives accurate per-pathway cost accounting without requiring the flat constant to change.

2. **Deduct from gross revenue or track separately?**

   Two approaches:
   - **Approach 1:** Deduct labor cost from revenue inside `process_harvests()` so that `crop.harvest_revenue_usd` and `crop.processed_revenue_usd` represent net-of-labor revenue. This means revenue fields change meaning.
   - **Approach 2:** Keep revenue gross and track processing labor cost as a separate cost field. Total profit = revenue - processing_labor_cost - other_costs. Revenue fields keep their current meaning.

   **Recommendation:** Approach 2 (track separately). This avoids changing the semantics of existing revenue fields, which could break downstream metrics and plots that compare revenue across policy scenarios. The processing labor cost should be treated as an operating cost, not a revenue reduction.

3. **Community vs per-farm labor pools?**

   The current architecture treats labor as community-level resources (field labor distributed by area fraction in metrics). Processing labor is inherently per-farm because each farm's food policy determines how much processing occurs. The proposed solution correctly tracks processing labor at the farm level (on `FarmState` and `CropState`). No change to the community-level labor pool is needed at this stage. In a future enhancement where labor is a constrained resource (finite worker-hours per day), the per-farm tracking provides the foundation for a community labor allocation policy.

### Implementation Sequence

1. Add `get_processing_labor_hours_per_kg()` to `SimulationDataLoader` (data_loader.py)
2. Store the processing_worker wage rate during `_load_labor_costs()` (data_loader.py)
3. Add `get_processing_wage_usd_per_hour()` method to `SimulationDataLoader` (data_loader.py)
4. Add processing labor fields to `CropState`, `FarmState`, `YearlyFarmMetrics` (state.py)
5. Modify `process_harvests()` to compute and store processing labor cost (simulation.py)
6. Update `snapshot_yearly_metrics()` to include processing labor (simulation.py)
7. Update `reset_farm_for_new_year()` to reset processing labor accumulators (simulation.py)
8. Update year-boundary and final-year economic state calculations (simulation.py)
9. Reconcile metrics labor computation (metrics.py)
10. Add processing labor cost to results output (results.py)

### Questions

1. **Should this change be coordinated with Issue 2 (processing energy cost)?** Both issues affect the same code path in `process_harvests()` and both add cost deductions. Implementing them together would avoid touching the same function twice and ensure the combined cost accounting is consistent. The energy cost fix needs `energy_kwh_per_kg` from the same CSV and an electricity price lookup.

2. **Should `labor_hours_per_kg` apply to `raw_kg` (fresh input) or `output_kg` (after weight loss)?** The CSV header says "hours per kg fresh input", so the calculation should use `raw_kg`. This is consistent with the physical reality that labor is applied to the fresh produce at the start of processing, before weight is lost.

3. **Does the `LABOR_PROCESSING_HRS_PER_KG` constant in calculations.py need updating?** Currently set to 0.02, which matches `tomato/packaged` but underestimates labor-intensive pathways (dried potato is 0.14 hrs/kg, 7x higher). Once per-pathway labor hours are tracked in the simulation, the flat constant becomes redundant for simulation purposes but may still be useful for planning estimates. It could be updated to a weighted average or deprecated.

4. **What happens to AllFresh policy?** Fresh pathway has `labor_hours_per_kg = 0.0` for all crops, so the AllFresh policy will incur zero processing labor cost. This is correct -- fresh sale requires no processing labor (harvesting labor is covered separately in field labor).

### Critical Files for Implementation

- `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/simulation.py` - Contains `process_harvests()` where the labor cost deduction must be added
- `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/state.py` - State dataclasses (`CropState`, `FarmState`, `YearlyFarmMetrics`) that need new processing labor fields
- `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/data_loader.py` - Needs new accessor method for `labor_hours_per_kg` and processing wage rate storage
- `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/metrics.py` - Existing labor metrics computation (lines 687-731) must be reconciled with simulation-tracked values
- `/Users/dpbirge/GITHUB/community-agri-pv/data/parameters/crops/processing_specs-research.csv` - Source data with `labor_hours_per_kg` values per crop/pathway (read-only reference)
