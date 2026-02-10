# Add Cool Storage to the Processing Chain

**Generated:** February 6, 2026

## Implementation Plan: Add Cool Storage to the Processing Chain

### Problem Statement

The simulation currently models two storage conditions: "ambient" (25-35C) and "climate_controlled" (2-8C, full refrigeration). There is no intermediate option representing low-cost passive cooling -- evaporative coolers, shaded ventilated structures, or zero-energy cool rooms (ZECR). In the Sinai Peninsula's hot arid climate (daytime 35-46C in summer), ambient storage is extremely destructive to fresh produce and dried goods, while full refrigeration is energy-intensive and capital-costly. The simulation therefore overstates post-harvest losses for fresh and dried products, and understates them for any community that invests in modest cooling infrastructure. An intermediate "cool_storage" condition (15-22C interior temperature range) would accurately reflect the most cost-effective storage technology for this climate and community scale.

### Current Behavior

**Spoilage data structure (`spoilage_rates-toy.csv`):**
The file defines two storage conditions per product type:
- `ambient` -- 25-35C, no climate control. Fresh tomatoes: 3.5%/day spoilage, 10-day shelf life.
- `climate_controlled` -- 2-8C full refrigeration. Fresh tomatoes: 1.0%/day spoilage, 28-day shelf life.

**Post-harvest loss in simulation (`simulation.py:process_harvests()`):**
The simulation uses `data_loader.get_post_harvest_loss_fraction(crop, pathway)` which reads from `post_harvest_losses-research.csv`. This file provides a single `loss_pct` per crop/pathway combination (e.g., tomato/fresh = 28%). There is no storage-condition parameter -- the loss percentages implicitly assume ambient storage without cold chain, as stated in the file header: "Small-scale community farming, no industrial cold chain."

**Processing capacity and storage in scenario YAML (`settings.yaml`):**
Each processing category (fresh_food_packaging, drying, canning, packaging) has a `storage_capacity_kg_total` and `shelf_life_days` field, but these are not yet used in the simulation loop. The `process_harvests()` function applies losses at harvest time based solely on the CSV lookup; it does not model inventory sitting in storage.

**Equipment data (`processing_equipment-toy.csv`):**
Lists equipment types for packaging, drying, canning, and fresh packaging categories. No cool storage or evaporative cooling equipment entries exist.

**Capital costs (`capital_costs-research.csv`):**
Contains `processing_equipment_cold_storage` at $45,000/unit (20-40 m3 walk-in cold room). No evaporative cooler or cool room entry.

**Key gap:** The simulation has the data scaffolding for multiple storage conditions (spoilage_rates-toy.csv has the two-condition structure) and for storage infrastructure configuration (YAML has capacity/shelf-life fields), but none of this is wired into the actual simulation loop. Adding "cool_storage" requires both adding the storage condition to data files AND connecting storage conditions to the loss calculation in `process_harvests()`.

### Desired Behavior

1. A new storage condition `cool_storage` (15-22C) is available in all storage-related data files, with spoilage rates and shelf lives that fall between ambient and climate_controlled.

2. The scenario YAML can specify what storage infrastructure each processing category uses (ambient, cool_storage, or climate_controlled), and cool storage equipment types are available in the equipment data.

3. `process_harvests()` in `simulation.py` reads the active storage condition from the scenario config and uses it to look up the correct post-harvest loss rate, so that investing in cool storage infrastructure reduces spoilage.

4. Cool storage energy demand (small for evaporative, zero for ZECR) is included in the daily energy dispatch.

5. Cool storage capital and operating costs are included in infrastructure cost calculations.

### Research Notes: Evaporative Cooling for Sinai Climate

**Climate suitability:** The Sinai Red Sea coast at 28N/34E has hot arid conditions (BWh Koppen). Summer daytime temperatures reach 38-46C, winter 18-26C. Relative humidity is typically 20-40% in summer, 30-55% in winter. This is near-ideal for evaporative cooling, which works best when ambient air is hot and dry.

**Evaporative cooling performance formula:**
```
T_interior = T_ambient - (efficiency * (T_ambient - T_wet_bulb))
```
Where efficiency is 0.65-0.85 for direct evaporative systems. With T_ambient = 40C and RH = 25% (T_wet_bulb ~ 24C), a system at 75% efficiency achieves:
```
T_interior = 40 - 0.75 * (40 - 24) = 40 - 12 = 28C
```
With supplemental nighttime ventilation (desert night temperatures 15-25C lower than daytime), average interior temperatures of 15-22C are achievable. Published studies from similar arid climates show:

- **Zero Energy Cool Chamber (ZECR)**: Brick-and-sand evaporative structure, no electricity. Maintains 15-18C when ambient is 40-45C in dry air. Capital cost: $200-800. Capacity: 100-500 kg. Source: FAO/Indian Agricultural Research Institute.
- **Evaporative pad-and-fan cool room**: Small fan (0.2-0.5 kW) pulls air through wetted pads. Maintains 18-22C. Capital cost: $2,000-5,000 for 5-10 tonne capacity. Water consumption: 50-150 L/day. Source: USDA Appropriate Technology Transfer for Rural Areas.
- **Shaded ventilated storage**: Simple shade structure with natural convection. Reduces ambient temperature by 5-10C. Capital cost: $500-2,000. No energy cost.
- **Charcoal cooler**: Charcoal-filled walls kept wet, evaporative effect. 10-15C reduction. Capital cost: $300-1,000.

**Shelf life extension estimates (arid climate with evaporative cooling):**
Research from similar arid regions shows the following shelf life improvements when moving from ambient (35-45C) to cool storage (15-22C):

| Product | Ambient shelf life | Cool storage shelf life | Extension factor |
|---------|-------------------|------------------------|-----------------|
| Fresh tomato | 7-10 days | 18-25 days | 2.0-2.5x |
| Fresh cucumber | 7-12 days | 20-30 days | 2.5-3.0x |
| Fresh kale | 3-7 days | 10-15 days | 2.0-2.5x |
| Fresh potato | 14-21 days | 30-60 days | 2.0-3.0x |
| Fresh onion | 14-21 days | 30-45 days | 1.5-2.0x |
| Dried tomato | 12-18 months | 18-24 months | 1.5x |
| Dried kale | 12 months | 18 months | 1.5x |
| Packaged produce | Similar to fresh with modest improvement | 1.5-2.0x | |

Sources: FAO Post-Harvest Compendium, USDA ERS storage guidelines, Kitinoja & Thompson (2010) "Precooling Systems for Small-Scale Producers".

**Water consumption for evaporative cooling:** In the Sinai climate, evaporative coolers consume 50-200 L/day per 10 tonnes of stored produce. This is small relative to irrigation water volumes (hundreds of m3/day) but should be tracked as it adds to the desalination/treatment load.

**Weather data gap:** The current weather dataset (`daily_weather_scenario_001-toy.csv`) does not include relative humidity. The evaporative cooling temperature reduction depends on the wet-bulb depression, which requires humidity data. Two approaches exist:
1. **Simple**: Use a fixed seasonal cooling performance factor (e.g., 12C reduction in summer, 8C in winter) based on published averages for the Sinai region. No humidity data needed.
2. **Dynamic**: Add relative humidity to the weather generation script and compute wet-bulb temperature daily for accurate cooling performance. More accurate but requires extending Layer 1.

### Proposed Solution

The implementation follows the existing pattern of the processing chain: data files define parameters, scenario YAML selects configurations, and the simulation loop applies them. The work divides into five phases.

**Phase 1: Data Files -- Add cool_storage condition to parameter files**

1. **`data/parameters/crops/spoilage_rates-toy.csv`** -- Add a third storage condition `cool_storage` for every product type (20 rows, one per crop x processing_type). Spoilage rates and shelf lives should be intermediate between ambient and climate_controlled, derived from the research notes above. Example for tomato_fresh:
   ```
   tomato_fresh,cool_storage,1.8,20
   ```
   (1.8%/day vs ambient 3.5% and climate_controlled 1.0%; 20-day shelf life vs 10 and 28)

2. **`data/parameters/crops/post_harvest_losses-research.csv`** -- This file currently has a single `loss_pct` per crop/pathway with no storage condition dimension. It needs restructuring to add a `storage_condition` column. For each crop/pathway combination, three rows would replace the current one:
   ```
   tomato,fresh,ambient,28.0,...
   tomato,fresh,cool_storage,15.0,...
   tomato,fresh,climate_controlled,8.0,...
   ```
   The cool_storage losses should be roughly 40-60% of the ambient losses, reflecting reduced spoilage, handling damage (slower pace with buffered storage), and transport flexibility.

3. **`data/parameters/crops/post_harvest_losses-toy.csv`** -- Same restructuring as the research file but with simplified values.

4. **`data/parameters/equipment/processing_equipment-toy.csv`** -- Add cool storage equipment types:
   ```
   cool_storage,zero_energy_cool_chamber,500,0,0.01,800,50,10
   cool_storage,evaporative_pad_fan,5000,0.5,0.005,4000,300,12
   cool_storage,shaded_ventilated_store,3000,0,0.008,1500,100,15
   ```

5. **`data/parameters/costs/capital_costs-research.csv`** -- Add cool storage capital cost entries:
   ```
   processing_equipment_cool_storage_zecr,per_unit,800,15,...
   processing_equipment_cool_storage_evaporative,per_unit,4000,20,...
   processing_equipment_cool_storage_shaded,per_unit,1500,15,...
   ```

6. **`data/scripts/generate_crop_parameters.py`** -- Update `STORAGE_CONDITIONS` from `["ambient", "climate_controlled"]` to `["ambient", "cool_storage", "climate_controlled"]`. Add `cool_storage` entries to `SPOILAGE_RATES` dict. Update `generate_spoilage_rates()` to emit three rows per product type.

**Phase 2: Configuration -- Add cool_storage to scenario YAML and loader**

7. **`settings/settings.yaml`** -- Add a `cool_storage` section under `food_processing_system`:
   ```yaml
   food_processing_system:
     cool_storage:
       equipment:
         - type: evaporative_pad_fan
           fraction: 0.6
         - type: zero_energy_cool_chamber
           fraction: 0.4
       storage_capacity_kg_total: 10000
       shelf_life_days: 21
       financing_status: grant_full
   ```
   Also add a `storage_condition` field to each existing processing category to indicate what type of storage products go to after processing:
   ```yaml
   fresh_food_packaging:
     ...
     storage_condition: cool_storage   # (ambient | cool_storage | climate_controlled)
   drying:
     ...
     storage_condition: cool_storage   # dried goods benefit from cool storage
   canning:
     ...
     storage_condition: ambient        # canned goods are shelf-stable
   packaging:
     ...
     storage_condition: cool_storage
   ```

8. **`src/settings/loader.py`** -- Modify `ProcessingCategoryConfig` to include `storage_condition`:
   ```python
   @dataclass
   class ProcessingCategoryConfig:
       equipment: list
       storage_capacity_kg_total: float
       shelf_life_days: int
       financing_status: str = "existing_owned"
       storage_condition: str = "ambient"  # ambient | cool_storage | climate_controlled
   ```
   Modify `FoodProcessingConfig` to include the new `cool_storage` category:
   ```python
   @dataclass
   class FoodProcessingConfig:
       fresh_food_packaging: ProcessingCategoryConfig
       drying: ProcessingCategoryConfig
       canning: ProcessingCategoryConfig
       packaging: ProcessingCategoryConfig
       cool_storage: ProcessingCategoryConfig = None  # Optional, backward compatible
   ```
   Update `_parse_processing_category()` to read `storage_condition` with default "ambient".
   Update `_load_infrastructure()` to parse the optional `cool_storage` section.

9. **`settings/data_registry.yaml`** -- Add a reference to the cool storage equipment data if a separate file is created, or note it is part of the existing `processing_equipment` file.

**Phase 3: Data Loader -- Expose storage-condition-aware loss lookups**

10. **`src/simulation/data_loader.py`** -- Modify `load_post_harvest_losses()` to handle the new `storage_condition` column. The DataFrame should be multi-indexed by `(crop_name, pathway, storage_condition)`.

11. **`src/simulation/data_loader.py`** -- Modify `SimulationDataLoader.get_post_harvest_loss_fraction()` to accept a `storage_condition` parameter:
    ```python
    def get_post_harvest_loss_fraction(self, crop_name, pathway, storage_condition="ambient"):
        pct = self.post_harvest_losses.loc[(crop_name, pathway, storage_condition), "loss_pct"]
        return float(pct) / 100.0
    ```
    The default "ambient" preserves backward compatibility.

12. **`src/simulation/data_loader.py`** -- Optionally add `get_spoilage_rate()` and `get_shelf_life()` methods for spoilage_rates data, which is already loaded in the registry but not yet accessed by the simulation. These would support future daily-inventory-tracking features.

**Phase 4: Simulation Loop -- Use storage condition in harvest processing**

13. **`src/simulation/simulation.py:process_harvests()`** -- Modify the pathway processing loop (lines 393-423) to pass the storage condition when looking up post-harvest loss:
    ```python
    # Determine storage condition for this pathway from scenario config
    storage_condition = _get_storage_condition(farm_config, pathway)
    loss_frac = data_loader.get_post_harvest_loss_fraction(
        crop.crop_name, pathway, storage_condition=storage_condition
    )
    ```
    Add a helper function `_get_storage_condition(farm_config, pathway)` that maps pathway names to the corresponding `ProcessingCategoryConfig.storage_condition`, defaulting to "ambient" if not configured.

14. **`src/simulation/simulation.py:run_simulation()`** -- Add cool storage energy demand to the daily energy dispatch. The energy is small (0-0.5 kW continuous per unit) and only applies on days with products in storage. For the MVP, compute it as a fixed daily draw based on the cool storage equipment configuration:
    ```python
    cool_storage_energy_kwh = cool_storage_kw_continuous * 24  # daily energy from scenario config
    ```
    Add this to `total_energy_demand_kwh` in the dispatch block (line 1011).

15. **`src/simulation/simulation.py:run_simulation()`** -- Add cool storage water consumption to daily water demand (for evaporative types). Estimate 50-150 L/day per unit from equipment parameters. Add to the community water treatment loop.

**Phase 5: State Tracking and Metrics**

16. **`src/simulation/state.py`** -- Add `storage_condition` field to `CropState` to record what storage condition was used:
    ```python
    storage_condition_used: str = "ambient"
    ```
    Optionally add `cool_storage_energy_kwh: float = 0.0` to `FarmState` for tracking.

17. **`src/simulation/state.py:YearlyFarmMetrics`** -- Add a `cool_storage_energy_kwh` field for yearly tracking.

18. **`src/simulation/metrics.py`** -- Update metric calculations to include cool storage energy in total energy metrics and report storage condition usage.

**Phase 6: Documentation**

19. **`docs/architecture/structure.md`** -- Document the new `cool_storage` section under `food_processing_system` and the `storage_condition` field on each processing category.

20. **`docs/architecture/calculations.md`** -- Add a section on cool storage temperature modeling and its effect on post-harvest loss rates.

### Decision Points Requiring User Input

1. **Weather data: humidity column.** The weather CSV currently lacks relative humidity data. Should we:
   - (a) Use fixed seasonal cooling performance factors (simpler, no Layer 1 changes), or
   - (b) Add humidity to the weather generation script for dynamic wet-bulb calculation?
   Recommendation: Option (a) for now. Humidity can be added later as a Layer 1 enhancement.

2. **Post-harvest loss model: instant vs. daily inventory.** Currently, `process_harvests()` applies all losses at harvest time as a single fraction. With storage, losses should theoretically accumulate daily over the storage period. Should we:
   - (a) Keep the instant-loss model but use storage-condition-adjusted loss percentages (simple; same architecture), or
   - (b) Implement a daily inventory tracker with per-day spoilage rates from `spoilage_rates-toy.csv` (accurate; significant new state management)?
   Recommendation: Option (a) for this implementation. Option (b) is a separate, larger feature (daily inventory management) that should be its own planning document.

3. **Cool storage as separate processing category vs. modifier.** Should cool storage be:
   - (a) A new processing category in `food_processing_system` alongside drying/canning/packaging (parallels existing pattern, but implies a "processing step"), or
   - (b) A `storage_condition` attribute on each existing processing category (more accurate -- storage happens *after* processing, not *instead of* it)?
   Recommendation: Both. Add `cool_storage` as an infrastructure section (for equipment/capacity/cost tracking) AND add `storage_condition` as an attribute on each processing category (for loss calculation). This mirrors how water storage is both an infrastructure section and an operational parameter.

4. **Shelf life multiplier values.** The proposed values in the Research Notes above are estimates. Should we use:
   - (a) The estimates from published literature (documented above), or
   - (b) Commission a targeted literature review for Sinai-specific data?
   Recommendation: Option (a) for the toy dataset. Create research-grade values when completing the research dataset transition.

5. **Cool storage water consumption.** For evaporative coolers, water consumption (50-200 L/day) adds to desalination load. Should this be:
   - (a) Tracked explicitly in the daily water loop, or
   - (b) Ignored for now (it is less than 0.1% of daily irrigation volumes)?
   Recommendation: Option (a) -- track it. The simulation already tracks household and community building water separately; adding cool storage water is straightforward and consistent.

### Questions / Remaining Unknowns

1. **Research-grade spoilage data for cool_storage.** The existing `post_harvest_losses-research.csv` cites specific FAO and USDA sources for ambient conditions. Comparable research-grade data for evaporative-cooled storage in Sinai-like conditions would strengthen the model. Are there specific publications or datasets the user has identified?

2. **Seasonal variation in cool storage performance.** Evaporative cooling is most effective in summer (low humidity, high temperature) and least effective in winter (higher humidity, lower temperatures -- though less cooling is needed). Should the model vary the effective storage condition by season, or use a year-round average?

3. **Cool storage for canned goods.** Canned products are shelf-stable and do not meaningfully benefit from cool storage. The plan defaults canning to "ambient" storage. Is this correct, or should the scenario be configurable?

4. **Cool storage capacity constraints.** The scenario YAML already has `storage_capacity_kg_total` per processing category, but this is not enforced in the simulation. When cool storage is added, should capacity overflow (harvest exceeding cool storage capacity) fall back to ambient storage? This would be a natural extension but adds complexity.

5. **Integration with food processing fixes.** The `food_processing_fixes.md` document lists five other issues with the processing chain (energy cost tracking, labor cost deduction, loss metric separation, reference prices, fraction validation). Should cool storage be implemented before or after those fixes? The loss metric separation (Issue 4) is particularly relevant since the current `post_harvest_loss_kg` conflates waste with processing weight change. Recommendation: implement Issue 4 (loss separation) first, then cool storage, so that cool storage benefits are clearly measured in the waste metric rather than conflated.

### Implementation Sequence

1. Fix Issue 4 from `food_processing_fixes.md` (separate waste from weight loss) -- prerequisite
2. Phase 1: Update data files (spoilage_rates, post_harvest_losses, equipment, capital costs, generation script)
3. Phase 2: Update configuration (YAML, loader dataclasses)
4. Phase 3: Update data_loader (storage-condition-aware lookups)
5. Phase 4: Update simulation loop (storage-aware loss calculation, cool storage energy/water)
6. Phase 5: Update state tracking and metrics
7. Phase 6: Update documentation

Estimated effort: 2-3 sessions. Phases 1-3 are straightforward data and configuration work. Phase 4 is the core logic change. Phases 5-6 are bookkeeping.

### Critical Files for Implementation

- `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/simulation.py` - Core simulation loop where `process_harvests()` applies post-harvest losses; must add storage-condition-aware loss lookup and cool storage energy/water tracking
- `/Users/dpbirge/GITHUB/community-agri-pv/src/simulation/data_loader.py` - Data access layer where `get_post_harvest_loss_fraction()` must accept a `storage_condition` parameter; post_harvest_losses DataFrame needs a third index level
- `/Users/dpbirge/GITHUB/community-agri-pv/src/settings/loader.py` - Scenario loader where `ProcessingCategoryConfig` and `FoodProcessingConfig` dataclasses must gain `storage_condition` field and optional `cool_storage` category
- `/Users/dpbirge/GITHUB/community-agri-pv/data/parameters/crops/post_harvest_losses-research.csv` - Primary data file that must be restructured from 2-column (crop, pathway) to 3-column (crop, pathway, storage_condition) indexing with cool_storage rows added
- `/Users/dpbirge/GITHUB/community-agri-pv/data/scripts/generate_crop_parameters.py` - Data generation script that must be updated with cool_storage spoilage rates and the third storage condition for spoilage_rates CSV regeneration
