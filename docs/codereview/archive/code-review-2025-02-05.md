# Code Review: Community Agri-PV Simulation Model
**Reviewer:** Claude (AI Assistant)  
**Date:** February 5, 2025  
**Scope:** `/src` directory - Logic and calculation errors, gaps, and inconsistencies

## Executive Summary

This review examines the simulation codebase for logic errors, calculation inconsistencies, and gaps relative to the architecture specifications in `docs/architecture/mvp-calculations.md` and `docs/architecture/mvp-structure.md`. The review focuses on **logic and calculation correctness**, not data believability.

**Overall Assessment:** The codebase is well-structured and implements the water simulation MVP correctly in most areas. However, several calculation errors, logic gaps, and inconsistencies with the architecture documentation were identified that should be addressed.

---

## Critical Issues

### 1. Crop Water Allocation Logic Error
**Location:** `src/simulation/simulation.py:242-246`

**Issue:** Water is allocated to crops based on demand (`crop_demands`), not actual allocation. If demand is 100 m³ but only 50 m³ is allocated due to constraints, crops still get credited with their full demand.

**Current Code:**
```python
for crop in farm_state.active_crops(current_date):
    if crop.crop_name in crop_demands:
        # Assume water is allocated proportionally to demand
        crop.cumulative_water_m3 += crop_demands[crop.crop_name]
```

**Problem:** This tracks demand, not actual allocated water. If constraints reduce allocation, crop water tracking becomes inaccurate.

**Fix:** Allocate water proportionally to actual allocation:
```python
total_allocated = allocation.groundwater_m3 + allocation.municipal_m3
if total_allocated > 0 and sum(crop_demands.values()) > 0:
    allocation_ratio = total_allocated / sum(crop_demands.values())
    for crop in farm_state.active_crops(current_date):
        if crop.crop_name in crop_demands:
            crop.cumulative_water_m3 += crop_demands[crop.crop_name] * allocation_ratio
```

**Impact:** High - affects water use efficiency metrics and per-crop water tracking.

---

### 2. Energy Generation Calculation Uses Fixed Estimates
**Location:** `src/simulation/simulation.py:147-156`

**Issue:** Available energy for water treatment is calculated using fixed daily generation estimates (5 hours for PV, 6 hours for wind) instead of using actual precomputed capacity factors from data files.

**Current Code:**
```python
if pv_kw > 0 or wind_kw > 0:
    # Estimate daily generation (simplified: 5 sun hours for PV, 6 hours for wind)
    daily_pv_kwh = pv_kw * 5.0
    daily_wind_kwh = wind_kw * 6.0
    available_energy = daily_pv_kwh + daily_wind_kwh
```

**Problem:** This ignores:
- Actual weather conditions (precomputed capacity factors vary daily)
- Seasonal variation
- The architecture spec which references precomputed power data

**Fix:** Use precomputed capacity factors from `data/precomputed/power/`:
```python
if pv_kw > 0 or wind_kw > 0:
    # Get actual daily generation from precomputed data
    pv_cf = data_loader.get_pv_capacity_factor(current_date)  # Needs implementation
    wind_cf = data_loader.get_wind_capacity_factor(current_date)  # Needs implementation
    daily_pv_kwh = pv_kw * pv_cf * 24.0  # CF is hourly average
    daily_wind_kwh = wind_kw * wind_cf * 24.0
    available_energy = daily_pv_kwh + daily_wind_kwh
```

**Impact:** High - energy constraints for water treatment are inaccurate, affecting policy decisions.

---

### 3. Missing Irrigation Efficiency Adjustment
**Location:** `src/simulation/simulation.py:58-82` (`calculate_farm_demand`)

**Issue:** The architecture documentation (`mvp-calculations.md:111-143`) specifies that irrigation demand should be adjusted for irrigation system efficiency:
```
Water_demand = (ET_crop × Area) / η_irrigation
```

**Current Code:** Uses raw irrigation demand from precomputed data without efficiency adjustment.

**Problem:** Precomputed data may already include efficiency, or may not. The architecture spec clearly states efficiency should be applied in the simulation.

**Fix:** Apply irrigation efficiency from scenario config:
```python
def calculate_farm_demand(farm_state, current_date, data_loader, scenario):
    # ... existing code ...
    irrigation_type = scenario.infrastructure.irrigation_system.type
    efficiency = get_irrigation_efficiency(irrigation_type)  # From calculations.py
    total_demand = total_demand / efficiency  # Adjust for efficiency losses
```

**Impact:** Medium - affects water demand calculations and policy decisions.

---

### 4. Yield Calculation Missing Water Stress Model
**Location:** `src/simulation/simulation.py:249-278` (`process_harvests`)

**Issue:** The architecture documentation (`mvp-calculations.md:607-632`) specifies a water production function:
```
Y_actual = Y_potential × (1 - K_y × (1 - ET_actual / ET_crop))
```

**Current Code:** Uses expected yield directly from precomputed data without applying water stress reduction.

**Problem:** If water allocation is less than demand, yield should be reduced. Current implementation doesn't track ET_actual vs ET_crop.

**Fix:** Track cumulative water stress and apply yield reduction:
```python
# In CropState, add:
cumulative_water_stress: float = 0.0  # ET_actual / ET_crop ratio

# In process_harvests:
water_stress_factor = crop.cumulative_water_m3 / crop.expected_total_water_m3
# Apply yield reduction based on stress
k_y = get_yield_response_factor(crop.crop_name)  # From crop parameters
yield_reduction = k_y * (1 - water_stress_factor)
crop.harvest_yield_kg = crop.expected_total_yield_kg * (1 - yield_reduction)
```

**Impact:** High - yield calculations don't reflect water stress, making policy comparisons inaccurate.

---

### 5. Groundwater Cost Missing Pumping Energy
**Location:** `src/policies/water_policies.py:97-99` (`_calc_gw_cost_per_m3`)

**Issue:** The architecture documentation (`mvp-calculations.md:25-51`) specifies groundwater cost should include:
- Pumping energy (well to surface)
- Treatment energy (BWRO)
- Conveyance energy (pipes)
- O&M costs

**Current Code:** Only includes treatment energy and maintenance:
```python
def _calc_gw_cost_per_m3(self, ctx: WaterPolicyContext) -> float:
    return (ctx.treatment_kwh_per_m3 * ctx.energy_price_per_kwh) + ctx.gw_maintenance_per_m3
```

**Problem:** Missing pumping energy and conveyance energy components.

**Fix:** Add pumping and conveyance energy to context and calculation:
```python
# In build_water_policy_context, calculate pumping energy:
pumping_kwh_per_m3 = calculate_pumping_energy(
    scenario.infrastructure.groundwater_wells.well_depth_m,
    scenario.infrastructure.groundwater_wells.well_flow_rate_m3_day
)["total_pumping_energy_kwh_per_m3"]
conveyance_kwh_per_m3 = 0.2  # Fixed value per architecture spec

# In _calc_gw_cost_per_m3:
total_energy = ctx.treatment_kwh_per_m3 + ctx.pumping_kwh_per_m3 + ctx.conveyance_kwh_per_m3
return (total_energy * ctx.energy_price_per_kwh) + ctx.gw_maintenance_per_m3
```

**Impact:** Medium - groundwater cost is underestimated, affecting policy cost comparisons.

---

## Moderate Issues

### 6. Monthly Consumption Tracker Reset Timing
**Location:** `src/simulation/state.py:126-152` (`update_monthly_consumption`)

**Issue:** Monthly tracker resets when month changes, but `get_monthly_water_m3` is called BEFORE the reset in `simulation.py:412`, potentially causing incorrect tier pricing.

**Current Flow:**
1. `get_monthly_water_m3(current_date)` called → returns previous month's cumulative
2. Policy executes with old cumulative
3. `update_monthly_consumption` called → resets tracker if month changed

**Problem:** If month boundary crossed, tier pricing uses wrong cumulative value.

**Fix:** Ensure tracker is reset before policy execution, or check month in `get_monthly_water_m3`:
```python
def get_monthly_water_m3(self, current_date):
    if self.monthly_consumption is None:
        return 0.0
    # Reset if month changed BEFORE returning value
    if (self.monthly_consumption.current_month != current_date.month or
        self.monthly_consumption.current_year != current_date.year):
        self.monthly_consumption = MonthlyConsumptionTracker(
            current_month=current_date.month,
            current_year=current_date.year,
        )
        return 0.0
    return self.monthly_consumption.water_m3
```

**Impact:** Medium - affects tier pricing accuracy at month boundaries.

---

### 7. Energy Cost Double Counting Risk
**Location:** `src/simulation/metrics.py:250-252` (`compute_monthly_metrics`)

**Issue:** Energy cost is tracked separately (`energy_cost_usd`) but also included in `allocation.cost_usd`. The metrics calculation subtracts energy cost to avoid double counting, but this assumes energy cost is always included in water cost.

**Current Code:**
```python
# Water cost net of energy (to avoid double counting)
water_cost_net = water_data["cost_usd"] - energy_cost
total_operating = water_cost_net + energy_cost + diesel_cost + ...
```

**Problem:** If energy cost is not included in `allocation.cost_usd`, this subtraction is incorrect. Need to verify the relationship.

**Impact:** Low-Medium - depends on how `allocation.cost_usd` is calculated in policies.

---

### 8. Missing Water Storage Dynamics
**Location:** Architecture gap - no storage tracking in simulation

**Issue:** The architecture documentation (`mvp-calculations.md:145-175`) specifies water storage dynamics:
```
Storage(t+1) = Storage(t) + Inflow(t) - Outflow(t)
```

**Current Implementation:** No storage state tracking. Storage is treated as infinite capacity.

**Problem:** Storage utilization metrics cannot be calculated, and storage constraints are not enforced.

**Fix:** Add storage state to `SimulationState` or `FarmState`:
```python
@dataclass
class WaterStorageState:
    capacity_m3: float
    current_level_m3: float = 0.0  # Initialize to 50% per spec
    
    def update(self, inflow_m3: float, outflow_m3: float):
        self.current_level_m3 = max(0.0, min(
            self.capacity_m3,
            self.current_level_m3 + inflow_m3 - outflow_m3
        ))
```

**Impact:** Medium - storage utilization metrics are missing, and storage constraints not enforced.

---

### 9. Tier Pricing Marginal vs Actual Mismatch
**Location:** `src/simulation/simulation.py:434-449`

**Issue:** Marginal tier price is used for policy decisions (`get_marginal_tier_price`), but actual tier pricing is calculated after allocation (`calculate_tiered_cost`). These may differ if allocation spans multiple tiers.

**Problem:** Policy decisions use marginal cost, but actual cost may be higher if allocation crosses tier boundaries.

**Impact:** Low - policy decisions are based on marginal cost, which is correct for optimization, but actual cost tracking should reflect true tiered pricing.

---

### 10. Missing Aquifer Depletion Tracking
**Location:** Architecture gap

**Issue:** The architecture documentation (`mvp-calculations.md:211-248`) specifies aquifer depletion rate calculation, but it's not implemented in the simulation.

**Current Implementation:** No tracking of cumulative groundwater extraction or aquifer depletion.

**Fix:** Add aquifer tracking to `SimulationState`:
```python
@dataclass
class AquiferState:
    exploitable_volume_m3: float
    recharge_rate_m3_yr: float
    cumulative_extraction_m3: float = 0.0
    
    def update(self, extraction_m3: float):
        self.cumulative_extraction_m3 += extraction_m3
    
    def get_years_remaining(self) -> float:
        net_depletion = self.cumulative_extraction_m3 - self.recharge_rate_m3_yr
        if net_depletion <= 0:
            return float('inf')
        remaining = self.exploitable_volume_m3 - net_depletion
        return remaining / net_depletion if net_depletion > 0 else float('inf')
```

**Impact:** Medium - resilience metrics for aquifer sustainability cannot be calculated.

---

## Minor Issues and Inconsistencies

### 11. Water Per Yield Calculation Type Mismatch
**Location:** `src/simulation/metrics.py:157`

**Issue:** `water_per_yield_m3_kg` is assigned a dict (`crop_water_per_yield`) instead of a float.

**Current Code:**
```python
water_per_yield_m3_kg=water_per_yield,  # This is a dict!
```

**Fix:** Should be total water / total yield:
```python
water_per_yield_m3_kg=water_per_yield,  # This should be a float
```

**Impact:** Low - type inconsistency, but may not cause runtime errors if code handles dict.

---

### 12. Missing Yield Factor Application
**Location:** `src/simulation/state.py:233-264` (`initialize_crop_state`)

**Issue:** Farm `yield_factor` from scenario config is not applied to crop yields. Architecture spec suggests yield_factor should modify expected yields.

**Current Code:** Uses yield directly from precomputed data without farm-specific adjustment.

**Impact:** Low - farm management quality differences not reflected.

---

### 13. Inconsistent Energy Cost Tracking
**Location:** `src/simulation/simulation.py:431-432`

**Issue:** Energy cost is calculated separately but `allocation.cost_usd` may or may not include it. Need to verify policy implementations.

**Impact:** Low - depends on policy implementation details.

---

## Gaps Relative to Architecture Documentation

### Missing Implementations (Expected but Not Implemented)

1. **Water Storage Dynamics** - No storage level tracking (see issue #8)
2. **Aquifer Depletion** - No aquifer state tracking (see issue #10)
3. **Yield Stress Model** - No water stress yield reduction (see issue #4)
4. **PV Microclimate Yield Protection** - Architecture spec exists but not implemented
5. **Days Without Municipal Water** - Metric defined but not calculated
6. **Water Storage Utilization** - Metric defined but cannot be calculated without storage state
7. **Irrigation Demand vs Delivery** - Gap calculation exists in architecture but not implemented

### Partially Implemented

1. **Energy System** - Only water treatment energy is tracked, not full energy dispatch
2. **Economic Calculations** - Water costs tracked, but full economic model (debt service, infrastructure costs) not integrated
3. **Processing System** - Configuration exists but processing logic not implemented

---

## Recommendations

### Priority 1 (Critical - Fix Immediately)
1. Fix crop water allocation to use actual allocation, not demand (#1)
2. Implement yield stress model based on water allocation (#4)
3. Use actual capacity factors for energy generation (#2)

### Priority 2 (Important - Fix Soon)
4. Add pumping and conveyance energy to groundwater cost (#5)
5. Apply irrigation efficiency adjustment (#3)
6. Implement water storage dynamics (#8)
7. Fix monthly tracker reset timing (#6)

### Priority 3 (Nice to Have)
8. Implement aquifer depletion tracking (#10)
9. Add missing resilience metrics
10. Verify energy cost double counting (#7)

---

## Positive Observations

1. **Well-structured code** - Clear separation of concerns, good use of dataclasses
2. **Policy pattern** - Clean policy implementation with context objects
3. **Data loading** - Comprehensive data loader with caching
4. **Metrics calculation** - Good separation of raw metrics and computed metrics
5. **Documentation** - Code is well-commented and follows architecture patterns

---

## Conclusion

The codebase demonstrates solid engineering practices and correctly implements the water simulation MVP core functionality. However, several calculation errors and gaps relative to the architecture documentation should be addressed to ensure accurate simulation results and complete feature coverage.

The most critical issues are:
- Crop water tracking using demand instead of allocation
- Missing yield stress model
- Energy generation using fixed estimates instead of actual data

Addressing these issues will significantly improve the accuracy of policy comparisons and simulation outputs.

---

## Appendix: Files Reviewed

- `src/simulation/simulation.py` - Main simulation loop
- `src/simulation/state.py` - State management
- `src/simulation/data_loader.py` - Data loading
- `src/simulation/metrics.py` - Metrics calculation
- `src/simulation/results.py` - Output generation
- `src/policies/water_policies.py` - Water allocation policies
- `src/settings/calculations.py` - Infrastructure calculations
- `src/settings/loader.py` - Scenario loading
- `src/settings/validation.py` - Validation logic

**Architecture References:**
- `docs/architecture/mvp-calculations.md`
- `docs/architecture/mvp-structure.md`
