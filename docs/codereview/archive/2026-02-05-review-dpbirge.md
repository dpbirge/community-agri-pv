# Code Review: Water Simulation MVP

**Reviewer:** dpbirge
**Date:** 2026-02-05
**Scope:** `/src` codebase vs `docs/architecture/mvp-calculations.md` and `docs/architecture/mvp-structure.md`

## Summary

The current `/src` codebase implements a functional "Layer 3" simulation loop that correctly handles basic daily water demand, crop growth, and policy-based allocation. However, there are significant gaps between the implemented logic and the specifications in `mvp-calculations.md`, particularly regarding **energy costs**, **water storage dynamics**, and **resilience metrics**.

## Critical Logic Errors & Gaps

### 1. Pumping Energy is Ignored
**Severity:** High
**Location:** `src/policies/water_policies.py`, `src/simulation/simulation.py`
**Issue:**
The calculation for groundwater cost (`_calc_gw_cost_per_m3` in `water_policies.py`) only includes **treatment energy** and **maintenance**. It completely ignores **pumping energy** (lifting water from the well).
*   `mvp-calculations.md` (Section 2) explicitly defines `E_pump` separately from `E_treatment`.
*   `src/settings/calculations.py` contains a correct `calculate_pumping_energy` function, but this is **never called** in the simulation loop.
*   **Impact:** Groundwater costs are significantly underestimated (by 0.2-0.5 kWh/m³ or more depending on depth), biasing policy decisions toward groundwater.

### 2. Water Storage Dynamics Missing
**Severity:** High
**Location:** `src/simulation/simulation.py`
**Issue:**
The simulation calculates daily demand and attempts to meet it immediately from supply. There is **no water storage state** modeled.
*   `mvp-calculations.md` (Section 2) defines `Storage(t+1) = Storage(t) + Inflow - Outflow`.
*   The code effectively assumes `Storage = 0` or infinite flow-through. The `irrigation_water_storage` capacity from config is unused in the daily loop.
*   **Impact:** The model fails to simulate the primary benefit of storage: smoothing peak demands and surviving supply constraints. The "Water Storage Utilization" metric cannot be computed.

### 3. Aquifer Depletion Not Tracked
**Severity:** Medium
**Location:** `src/simulation/metrics.py`
**Issue:**
`mvp-structure.md` lists "Aquifer depletion rate" and "Years remaining" as key resilience metrics.
*   The simulation tracks `cumulative_groundwater_m3`, but does not compare this against `aquifer_exploitable_volume_m3` or `aquifer_recharge_rate_m3_yr` (from `water_system` config).
*   **Impact:** Resilience analysis is incomplete. The "tragedy of the commons" effect cannot be measured.

### 4. Simplified Energy Availability
**Severity:** Medium
**Location:** `src/simulation/simulation.py`
**Issue:**
Energy availability for treatment is calculated as `pv_kw * 5.0 + wind_kw * 6.0`.
*   This hardcoded "sun hours" approximation ignores actual weather data (cloud cover, wind speed) available in the precomputed files.
*   It assumes all generated energy is available for water treatment, ignoring other loads (household, processing) which `mvp-calculations.md` (Section 3) suggests should be balanced.
*   **Impact:** Overestimates reliability of renewable-powered desalination.

## Implementation Inconsistencies

### 1. Capacity Allocation
**Location:** `src/simulation/simulation.py` -> `calculate_system_constraints`
**Observation:**
Total community well and treatment capacity is divided equally by `num_farms` (`max_gw_per_farm = total / num_farms`).
*   **Critique:** This effectively enforces a "hard quota" on capacity per farm. In reality, a community might share a central plant where one farm could use more if others use less.
*   **Recommendation:** Verify if this "partitioned capacity" model is the intended design for the MVP. If infrastructure is shared, the constraint should likely be checked at the *community* level (sum of all allocations <= total capacity), not farm level.

### 2. Metric Completeness
**Location:** `src/simulation/metrics.py`
**Observation:**
The `ComputedYearlyMetrics` class is missing several fields defined in `mvp-structure.md`:
*   `aquifer_depletion_rate`
*   `days_without_municipal_water`
*   `water_storage_utilization`
*   `irrigation_demand_gap`

## Recommendations

1.  **Integrate Pumping Energy:**
    *   Update `SimulationDataLoader` to accept or calculate pumping energy (using `calculate_pumping_energy` from settings).
    *   Pass `pumping_kwh_per_m3` into `WaterPolicyContext`.
    *   Add it to the cost and energy formulas in `BaseWaterPolicy`.

2.  **Implement Storage State:**
    *   Add `storage_m3` to `FarmState`.
    *   Update `calculate_farm_demand` to net out available storage.
    *   Update logic to refill storage when renewable energy/capacity is excess.

3.  **Add Resilience Metrics:**
    *   Implement the aquifer depletion formulas in `metrics.py` using the community configuration parameters.

4.  **Refine Energy Logic:**
    *   Use the actual daily PV/Wind capacity factors from precomputed data (via `data_loader`) instead of the `* 5.0` approximation.

5.  **Review Capacity Constraints:**
    *   Decide if capacity is strictly partitioned (current) or pooled. If pooled, move constraint checking to a community-level step in the loop.
