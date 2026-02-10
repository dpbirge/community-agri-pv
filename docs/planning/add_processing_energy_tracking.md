# Add Processing Energy Cost Tracking

**Generated:** February 6, 2026

## Detailed Implementation Plan: Add Processing Energy Cost Tracking

### Problem Statement

The `process_harvests()` function in `src/simulation/simulation.py` calculates revenue for each food processing pathway (fresh, packaged, canned, dried) but does not account for the electricity consumed during processing. The `processing_specs-research.csv` file contains `energy_kwh_per_kg` values for every crop/pathway combination (ranging from 0.0 kWh/kg for fresh to 2.8 kWh/kg for dried cucumber), but this data is never used. Processed food pathways therefore appear more profitable than they actually are, because their energy costs are invisible. Additionally, processing energy demand is not included in the daily energy dispatch, meaning the community's total electricity demand is underestimated on harvest days.

The simulation already has a placeholder comment acknowledging this gap at line 1009 of `simulation.py`:
```python
# (Food processing energy is skipped for MVP — will be added in Gap 4.)
```

### Current Behavior

**`process_harvests()` (simulation.py lines 318-440):**
- For each crop reaching harvest, computes water-stress-adjusted yield.
- Gets fresh farmgate price, then applies the food processing policy to split harvest across pathways.
- For each pathway with nonzero fraction:
  - Computes `raw_kg = harvest_yield_kg * fraction`
  - Looks up `weight_loss_frac` from `data_loader.get_weight_loss_fraction()`
  - Looks up `loss_frac` (post-harvest spoilage) from `data_loader.get_post_harvest_loss_fraction()`
  - Looks up `multiplier` (value-add) from `data_loader.get_value_multiplier()`
  - Computes `revenue = sellable_kg * price_per_kg * multiplier`
  - **Does NOT** look up `energy_kwh_per_kg` or compute energy cost.
- Stores `harvest_revenue_usd`, `fresh_revenue_usd`, `processed_revenue_usd` on CropState and FarmState accumulators.
- Returns list of harvested CropState objects (return value is not used to feed energy demand).

**Energy dispatch (simulation.py lines 1005-1016):**
- Sums: `day_total_water_energy_kwh` + `daily_household_energy_kwh` + `daily_community_building_energy_kwh`
- Calls `dispatch_energy()` which does merit-order dispatch (PV -> wind -> battery -> grid -> generator).
- Processing energy is explicitly excluded with the comment noted above.

**`SimulationDataLoader`:**
- Already loads `processing_specs` DataFrame (multi-indexed by `(crop_name, processing_type)`).
- Has `get_weight_loss_fraction()` and `get_value_multiplier()` methods that read from `self.processing_specs`.
- Does NOT have a `get_energy_kwh_per_kg()` method.

**State tracking:**
- `CropState` has no field for processing energy.
- `FarmState` has no accumulator for processing energy.
- `YearlyFarmMetrics` has no processing energy field.
- `DailyEnergyRecord.total_demand_kwh` does not include processing energy.
- `MonthlyFarmMetrics` and `ComputedYearlyMetrics` have `energy_cost_usd` but this only covers water treatment energy.

**Processing specs CSV data** (`processing_specs-research.csv`):
| Pathway | Energy Range (kWh/kg fresh input) |
|---------|-----------------------------------|
| fresh | 0.0 (all crops) |
| packaged | 0.03 - 0.06 |
| canned | 0.35 - 0.55 |
| dried | 1.2 - 2.8 |

For context: drying 150 kg of tomatoes would consume 300 kWh (150 * 2.0), which is substantial relative to daily household energy demand (which is on the order of tens to low hundreds of kWh for the community).

### Desired Behavior

1. **Per-pathway energy calculation**: For each processing pathway, compute `energy_kwh = raw_kg * energy_kwh_per_kg` and price it at the current electricity rate.
2. **Deduct energy cost from revenue**: Subtract processing energy cost from the pathway revenue so that net profitability of processing pathways reflects their true cost.
3. **Track processing energy on state**: Store processing energy consumption on CropState, accumulate on FarmState, and report in YearlyFarmMetrics.
4. **Feed into energy dispatch**: Add daily processing energy demand to the total energy demand that goes into `dispatch_energy()`, so it competes for PV/wind/battery/grid resources alongside water treatment, household, and community building loads.
5. **Surface in metrics**: Include processing energy cost in monthly and yearly metrics so operating cost breakdowns and charts reflect the full energy picture.

### Proposed Solution

The implementation touches 4 files, sequentially.

#### Step 1: Add `get_energy_kwh_per_kg()` to `SimulationDataLoader` (data_loader.py)

Add a new method on `SimulationDataLoader` that mirrors the existing `get_weight_loss_fraction()` and `get_value_multiplier()` pattern:

```python
def get_energy_kwh_per_kg(self, crop_name, processing_type):
    """Get processing energy requirement per kg of fresh input.

    Args:
        crop_name: Name of crop
        processing_type: Processing pathway (fresh, packaged, canned, dried)

    Returns:
        float: kWh per kg of fresh input
    """
    return float(self.processing_specs.loc[(crop_name, processing_type), "energy_kwh_per_kg"])
```

This requires no new data loading since `self.processing_specs` is already loaded in `__init__()` at line 844.

#### Step 2: Add processing energy fields to state dataclasses (state.py)

**CropState** -- add after `post_harvest_loss_kg`:
```python
processing_energy_kwh: float = 0.0  # Total energy consumed by processing
processing_energy_cost_usd: float = 0.0  # Energy cost for processing
```

**FarmState** -- add a new accumulator in the "Food processing accumulators" group:
```python
cumulative_processing_energy_kwh: float = 0.0
cumulative_processing_energy_cost_usd: float = 0.0
```

**YearlyFarmMetrics** -- add in the "Food processing tracking" group:
```python
processing_energy_kwh: float = 0.0
processing_energy_cost_usd: float = 0.0
```

#### Step 3: Compute and deduct processing energy in `process_harvests()` (simulation.py)

**Signature change**: Add `current_date` is already passed. No new parameters needed since `data_loader` already has the processing_specs and electricity price lookups.

**Inside the pathway loop** (after computing `revenue`, around line 414), add:
```python
# Processing energy cost — from processing_specs CSV energy_kwh_per_kg
energy_kwh_per_kg = data_loader.get_energy_kwh_per_kg(crop.crop_name, pathway)
pathway_energy_kwh = raw_kg * energy_kwh_per_kg
energy_price = data_loader.get_electricity_price_usd_kwh(current_date)
pathway_energy_cost = pathway_energy_kwh * energy_price

# Deduct processing energy cost from pathway revenue
revenue -= pathway_energy_cost

total_processing_energy_kwh += pathway_energy_kwh
total_processing_energy_cost_usd += pathway_energy_cost
```

Initialize accumulators before the pathway loop:
```python
total_processing_energy_kwh = 0.0
total_processing_energy_cost_usd = 0.0
```

After the pathway loop, store on CropState:
```python
crop.processing_energy_kwh = total_processing_energy_kwh
crop.processing_energy_cost_usd = total_processing_energy_cost_usd
```

Update FarmState accumulators:
```python
farm_state.cumulative_processing_energy_kwh += total_processing_energy_kwh
farm_state.cumulative_processing_energy_cost_usd += total_processing_energy_cost_usd
```

**Return value change**: `process_harvests()` currently returns a list of harvested CropState objects. To feed processing energy into dispatch, the simplest approach is to also return the total processing energy for all crops harvested this call. Change the return to a tuple:
```python
return harvested, day_processing_energy_kwh
```

Where `day_processing_energy_kwh` sums all crops' processing energy for that farm on that day.

#### Step 4: Integrate processing energy into energy dispatch (simulation.py main loop)

In `run_simulation()`, around line 987 where `process_harvests()` is called:

```python
# Before the farm loop, initialize daily accumulator
day_processing_energy_kwh = 0.0

# Inside the farm loop (line ~987):
harvested, farm_processing_energy_kwh = process_harvests(
    farm_state, current_date, data_loader, farm_config=farm_config
)
day_processing_energy_kwh += farm_processing_energy_kwh
```

Then at line 1011 where total energy demand is assembled, add processing energy:
```python
total_energy_demand_kwh = (day_total_water_energy_kwh +
                           daily_household_energy_kwh +
                           daily_community_building_energy_kwh +
                           day_processing_energy_kwh)
```

Remove the "Gap 4" comment at line 1009.

#### Step 5: Update yearly resets and snapshots (simulation.py)

**`reset_farm_for_new_year()`** -- add:
```python
farm_state.cumulative_processing_energy_kwh = 0.0
farm_state.cumulative_processing_energy_cost_usd = 0.0
```

**`snapshot_yearly_metrics()`** -- add to the `YearlyFarmMetrics` constructor call:
```python
processing_energy_kwh=farm_state.cumulative_processing_energy_kwh,
processing_energy_cost_usd=farm_state.cumulative_processing_energy_cost_usd,
```

#### Step 6: Surface in metrics (metrics.py)

**`ComputedYearlyMetrics`** -- add in the food processing metrics group:
```python
processing_energy_kwh: float = 0.0
processing_energy_cost_usd: float = 0.0
```

**`compute_yearly_metrics()`** -- pass through from YearlyFarmMetrics:
```python
processing_energy_kwh=m.processing_energy_kwh,
processing_energy_cost_usd=m.processing_energy_cost_usd,
```

**`MonthlyFarmMetrics`** -- consider adding `processing_energy_cost_usd` as a separate line item. This is a lower priority since processing energy cost is already deducted from revenue (reducing `total_crop_revenue_usd`), but having it as a visible cost category improves transparency. If added, the `compute_monthly_metrics()` function would need to aggregate processing energy from harvested crops in each month.

#### Step 7: Update results export (results.py)

In the results export dictionary where yearly metrics are serialized (around line 65), add:
```python
"processing_energy_kwh": m.processing_energy_kwh,
"processing_energy_cost_usd": m.processing_energy_cost_usd,
```

### Decision Points

**1. Should processing energy be dispatchable (merit-order) or just accounted as a cost?**

**Recommendation: Both.** The plan above does both:
- Energy cost is computed and deducted from revenue (economic accounting).
- Energy demand is added to `total_energy_demand_kwh` for dispatch (physical flow).

This is the correct approach because processing equipment draws electricity from the same grid/PV/battery system as everything else. If processing energy is large on harvest days (e.g., 300 kWh for drying tomatoes), it could push the community into grid import or diesel generator territory, which has real cost implications that should be captured by dispatch.

**2. Should processing energy reduce available energy for other uses?**

**Yes**, by including it in `dispatch_energy()` total demand. The merit-order system already handles resource competition: if processing energy pushes demand above renewable generation, the battery discharges or grid import occurs. This is physically accurate -- you cannot run drying equipment for free if PV output is already consumed by water treatment.

**3. Should energy cost be deducted from revenue or tracked as an operating expense?**

**Recommendation: Deduct from revenue AND track separately.** The deduction from `revenue -= pathway_energy_cost` ensures that `harvest_revenue_usd` reflects true net revenue after processing costs. Tracking `processing_energy_cost_usd` separately enables the metrics system to report it as a visible cost category (like how water treatment energy is separated in `MonthlyFarmMetrics.energy_cost_usd`).

**Alternative considered**: Track only as a separate operating expense without deducting from revenue. This would require changes to how `total_crop_revenue_usd` feeds into economic metrics, and would break the existing pattern where `harvest_revenue_usd` represents the net sellable value. The deduction approach is simpler and consistent with how the food_processing_fixes.md describes the fix.

**4. Harvest timing: processing energy is event-driven, not daily.**

Harvests happen on specific dates, not every day. Processing energy will create spiky demand on harvest days rather than smooth daily load. This is physically realistic (you process on the day you harvest) and the dispatch system handles it correctly since it operates on daily totals. No special smoothing is needed.

### Questions / Remaining Unknowns

1. **Blended vs. dispatch electricity price for processing cost**: The current plan uses `data_loader.get_electricity_price_usd_kwh(current_date)` (grid tariff) for pricing processing energy. However, if the community's actual blended electricity cost differs significantly from grid price (because much of their energy comes from zero-marginal-cost PV), this could overstate or understate the real cost. For the current implementation phase, grid price is the correct choice because it matches how water treatment energy cost is calculated elsewhere in the code.

2. **Processing happens at farm level or community level?**: The current code processes harvests per-farm inside the farm loop, consistent with processing being farm-level activity. The processing energy is accumulated to community-level dispatch after all farms are processed, which is correct for shared energy infrastructure.

3. **Should `process_harvests()` return format change be a tuple or a dedicated result dataclass?**: A tuple `(harvested_list, energy_kwh)` is the simplest change. A dataclass could be cleaner if more return values are added later (e.g., when labor cost tracking from Issue 3 is implemented). For now, a tuple is sufficient and matches the minimal-change principle.

4. **Interaction with Issue 3 (labor cost tracking)**: If Issue 3 is implemented concurrently, the same loop that computes processing energy would also compute labor cost. The changes are additive and non-conflicting but could be combined into a single implementation pass for efficiency.

### Critical Files for Implementation

- `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/simulation.py` - Core changes: process_harvests() energy calculation, dispatch integration, yearly resets/snapshots
- `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/state.py` - Add processing energy fields to CropState, FarmState, YearlyFarmMetrics
- `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/data_loader.py` - Add get_energy_kwh_per_kg() method to SimulationDataLoader
- `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/metrics.py` - Surface processing energy in ComputedYearlyMetrics, MonthlyFarmMetrics
- `/Users/dpbirge/GITHUB/community-agri-pv/data/parameters/crops/processing_specs-research.csv` - Reference data (no changes needed, already has energy_kwh_per_kg column)
