# Community Water Demand Integration

**Date:** 2026-02-06
**Status:** Completed
**Scope:** Integrate household and community building water demands into simulation water balance and energy dispatch

## Summary

Completed integration of household and community building water demands into the simulation. These are essential community needs that must be met regardless of farming policy decisions. Water is sourced from groundwater, treated through the desalination system, and distributed through the same storage infrastructure as irrigation water.

## Changes Made

### 1. State Tracking Updates

#### WaterStorageState.record_daily()
- **File:** `src/simulation/state.py`
- **Changes:** Added parameters to track water consumption by type:
  - `household_m3`: Household water consumption
  - `community_building_m3`: Community building water consumption
  - `irrigation_m3`: Calculated as total minus household and building water
- **Purpose:** Enable detailed tracking and reporting of water use by category

**Code changes (lines 182-203):**
```python
def record_daily(self, current_date, inflow_m3, outflow_m3, household_m3=0.0, community_building_m3=0.0):
    """Record daily storage state for metrics tracking.

    Args:
        current_date: Simulation date
        inflow_m3: Water treated and added to storage (irrigation + community needs)
        outflow_m3: Water distributed from storage (irrigation + community needs)
        household_m3: Household water consumption (subset of outflow)
        community_building_m3: Community building water consumption (subset of outflow)
    """
    self.daily_levels.append({
        "date": current_date,
        "storage_level_m3": self.current_level_m3,
        "inflow_m3": inflow_m3,
        "outflow_m3": outflow_m3,
        "irrigation_m3": outflow_m3 - household_m3 - community_building_m3,
        "household_m3": household_m3,
        "community_building_m3": community_building_m3,
        "utilization_pct": (
            self.current_level_m3 / self.capacity_m3 * 100
            if self.capacity_m3 > 0 else 0.0
        ),
    })
```

### 2. Simulation Integration

#### Main Simulation Loop
- **File:** `src/simulation/simulation.py`
- **Location:** Lines 865-900 (moved to beginning of daily loop, before farm processing)

**Flow:**
1. **Retrieve daily demands** from data loader (temperature-dependent):
   - Household energy and water
   - Community building energy and water

2. **Calculate water treatment energy:**
   - `total_community_water_m3 = household_water + building_water`
   - `community_water_treatment_energy_kwh = total_community_water_m3 × treatment_kwh_per_m3`

3. **Update aquifer depletion tracking:**
   - Record community water extraction in aquifer state
   - Ensures groundwater sustainability tracking includes all uses

4. **Add to water storage system:**
   - Add community water to daily groundwater treated (`day_gw_treated_m3`)
   - Add treatment energy to daily water energy (`day_total_water_energy_kwh`)
   - Flow through water storage (inflow → outflow, same-day in MVP)

5. **Record daily water storage:**
   - Pass household and building water to `record_daily()` for detailed tracking

6. **Energy dispatch:**
   - Total energy demand includes:
     - Irrigation water treatment/pumping energy
     - Community water treatment/pumping energy (already in `day_total_water_energy_kwh`)
     - Household energy (lighting, AC, appliances)
     - Community building energy (offices, storage, halls, workshops)

### 3. Verbose Output Updates

#### Simulation Summary
- **File:** `src/simulation/simulation.py`
- **Changes:** Added water breakdown summary showing irrigation, household, and building water
- **Output example:**
  ```
  Total water treated: 913,953 m3 (irrigation 850,703, household 35,131, buildings 28,120)
  ```

## Validation

### Test Results
**Simulation:** 6-year run (2015-2020), 2,192 days

**Water consumption:**
- Total treated: 913,953 m³
  - Irrigation: 850,703 m³ (93.1%)
  - Household: 35,131 m³ (3.8%)
  - Buildings: 28,120 m³ (3.1%)

**Daily breakdown (winter sample, Jan 1-3, 2015):**
- Household: 14.7 m³/day
- Buildings: 11.8 m³/day
- Total community: 26.5 m³/day
- Irrigation: 0.0 m³/day (winter, no irrigation)

**Aquifer tracking:**
- Extraction: 913,953 m³ (includes all water sources: irrigation + household + buildings)
- Properly tracks groundwater depletion from all uses

**Energy dispatch:**
- Includes water treatment energy for community water
- Includes household and building electrical loads
- Correctly sums all components for merit-order dispatch

## Impact on Simulation

### Before This Update
- Only irrigation water was tracked and treated
- Household and building water data was generated but not used
- Energy included household loads but not their water treatment energy
- Aquifer depletion only tracked irrigation water extraction

### After This Update
- **Complete water balance:** All water uses tracked (irrigation + household + buildings)
- **Complete energy accounting:** Water treatment energy for all uses + electrical loads
- **Complete aquifer tracking:** All groundwater extractions recorded for sustainability analysis
- **Detailed metrics:** Water storage daily records show breakdown by use type
- **Policy-independent:** Community water demands are fixed, independent of farming decisions

## Key Design Decisions

### 1. Community Water as Fixed Demand
- Household and building water are essential needs
- Not subject to water allocation policies (which focus on irrigation)
- Processed before farm water allocation loop
- Always sourced from groundwater (no municipal option for community water in current model)

### 2. Integration with Water Storage
- Community water flows through same treatment and storage infrastructure as irrigation water
- Same-day processing (MVP model: inflow = outflow)
- Enables future temporal buffering if needed

### 3. Energy Accounting
- Water treatment energy calculated same as irrigation (same `treatment_kwh_per_m3`)
- Added to total water energy before energy dispatch
- Separate electrical loads (lighting, AC, etc.) added as distinct demand components

### 4. Aquifer Sustainability
- Community water extraction recorded in aquifer depletion tracking
- Critical for long-term sustainability analysis
- Ensures accurate "years remaining" calculations

## Future Enhancements

### 1. Municipal Water Option
- Could add option to source community water from municipal supply instead of groundwater
- Would require policy decisions about water source allocation

### 2. Demand-Side Management
- Could add conservation policies that reduce household/building water use
- Temperature-based demand is already implemented (cooling, cleaning)

### 3. Water Quality Tiers
- Could differentiate water quality requirements (potable vs. irrigation)
- May enable cost savings through differentiated treatment

### 4. Wastewater Recycling
- Could add wastewater treatment and reuse for irrigation
- Would reduce groundwater extraction and improve sustainability

## Files Modified

**Modified files (2):**
- `src/simulation/state.py` - Updated WaterStorageState.record_daily() signature and tracking
- `src/simulation/simulation.py` - Integrated community water into main simulation loop, added verbose output

**No new files created** - leverages existing data infrastructure:
- Data files: Already created in previous work (household and community building demand CSVs)
- Data loader: Already supports retrieval methods (`get_household_water_m3()`, etc.)
- Configuration: Already includes building square footage in scenario YAML

## Configuration

Community water demands are controlled by scenario YAML settings:

```yaml
community_structure:
  houses: 10                         # Number of households
  community_buildings_m2: 1000      # Square meters of community buildings
```

Data is precomputed from:
- `data/precomputed/household/household_water_m3_per_day-toy.csv`
- `data/precomputed/community_buildings/community_buildings_water_m3_per_day-toy.csv`

Both vary daily based on weather/temperature (generated by Layer 1 scripts).

## Notes

1. **Complete integration:** This completes the water demand integration started in the previous community building work. Both energy and water are now fully integrated.

2. **Policy independence:** Community water demands are fixed and not subject to water allocation policies. This reflects the reality that household needs must be met regardless of farming decisions.

3. **Groundwater source:** Currently all community water comes from groundwater. Future work could add municipal water as an option.

4. **Temperature variation:** Water demands vary with temperature through precomputed time-series data. Summer demands are higher due to increased cooling water needs.

5. **Data quality:** Current data is synthetic ("toy" dataset). Should be replaced with measured data or Egyptian building standards for research-grade simulations.
