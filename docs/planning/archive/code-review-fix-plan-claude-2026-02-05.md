# Code Review Fix Plan

**Author:** Claude (Opus)
**Date:** 2026-02-05
**Sources:** 4 code reviews + 1 implementation checklist in `docs/codereview/`

---

## 1. Synthesized Issues

All issues from the four code review files have been deduplicated, cross-referenced, and verified against the actual source code. Issues referenced by multiple reviewers are noted.

### Critical (C1–C4) — Affect simulation accuracy and policy comparisons

| ID | Issue | Reviewers | Files |
|----|-------|-----------|-------|
| C1 | **Groundwater cost omits pumping & conveyance energy** — `_calc_gw_cost_per_m3` uses only `treatment_kwh_per_m3`. The spec requires `E_pump + E_convey + E_treatment`. `calculate_pumping_energy()` exists in `calculations.py` but is never called. | All 4 | `water_policies.py`, `simulation.py` |
| C2 | **Crop water allocation tracks demand, not actual delivery** — `update_farm_state` adds full `crop_demands[crop_name]` to `cumulative_water_m3` even when allocation is constrained. | 3 of 4 | `simulation.py` |
| C3 | **Yield ignores water stress and `yield_factor`** — `process_harvests` assigns `expected_total_yield_kg` directly. No FAO water production function applied. Farm `yield_factor` never used. | 3 of 4 | `simulation.py`, `state.py` |
| C4 | **Energy generation uses fixed estimates** — PV uses `* 5.0` hours, wind uses `* 6.0` hours instead of precomputed daily capacity factors from data files. | 3 of 4 | `simulation.py`, `data_loader.py` |

### High (H1–H3) — Affect demand calculations and pricing

| ID | Issue | Reviewers | Files |
|----|-------|-----------|-------|
| H1 | **Irrigation demand ignores system efficiency** — Spec says `demand = (ET_crop × Area) / η_irrigation`. Code uses raw precomputed demand. `get_irrigation_efficiency()` exists in `calculations.py` but is never called. | 3 of 4 | `simulation.py` |
| H2 | **Tiered pricing uses marginal price for total cost** — Policy decisions use marginal tier price, but `allocation.cost_usd` may multiply all municipal volume by the marginal price rather than computing the tiered total. | 2 of 4 | `simulation.py`, `water_policies.py` |
| H3 | **Infrastructure capacity split equally, not by area** — `calculate_system_constraints` divides well/treatment capacity by `num_farms`. Spec says proportional to farm area. | 2 of 4 | `simulation.py` |

### Medium (M1–M5) — Spec gaps and missing features

| ID | Issue | Reviewers | Files |
|----|-------|-----------|-------|
| M1 | **Water storage dynamics not implemented** — No `Storage(t)` tracking. `irrigation_water_storage.capacity_m3` from config is unused. Spec defines storage balance equation. | 3 of 4 | `simulation.py`, `state.py` |
| M2 | **Aquifer depletion not tracked** — `aquifer_exploitable_volume_m3` and `aquifer_recharge_rate_m3_yr` not parsed by loader, not tracked in simulation. | 3 of 4 | `loader.py`, `state.py`, `metrics.py` |
| M3 | **Several spec-defined metrics missing** — Aquifer depletion rate, days without municipal water, water storage utilization, irrigation demand vs delivery, crop diversity index, payback period, ROI, NPV. | 2 of 4 | `metrics.py` |
| M4 | **Salinity level naming mismatch** — Spec defines `low/moderate/high/very_high`, data file uses `light/moderate/heavy`. Using `low` (per spec) would cause `KeyError`. | 1 of 4 | Data files, `loader.py` |
| M5 | **Financing cost model not connected** — `financing_status` in YAML is silently ignored by loader. No infrastructure-specific debt computation. | 1 of 4 | `loader.py` |

### Low (L1–L9) — Minor bugs, dead code, documentation

| ID | Issue | Reviewers | Files |
|----|-------|-----------|-------|
| L1 | **Monthly tracker reset timing** — `get_monthly_water_m3` called before `update_monthly_consumption` resets tracker at month boundary. First day of each month uses stale cumulative for tier pricing. | 1 of 4 | `state.py`, `simulation.py` |
| L2 | **`CheapestSource.include_energy_cost` is dead code** — Constructor accepts parameter, never references it in `allocate_water()`. | 1 of 4 | `water_policies.py` |
| L3 | **Energy cost double counting is fragile** — Logic subtracts then re-adds energy cost. Correct in aggregate but confusing and fragile across layers. | 2 of 4 | `metrics.py`, `notebook_plotting.py` |
| L4 | **`state.py` docstring claims immutability** — Line 5: "State is updated immutably" but all state is mutated in-place. | 2 of 4 | `state.py` |
| L5 | **Population variance instead of sample variance** — `compute_cost_volatility` divides by N, not N-1. ~1.4% error for 72 monthly samples. | 1 of 4 | `metrics.py` |
| L6 | **`total_farming_area_ha` vs `total_area_ha`** — Loader reads only `total_area_ha`. Spec lists `total_farming_area_ha` as canonical name. | 1 of 4 | `loader.py` |
| L7 | **Sensitivity `project_root` derivation fragile** — `Path(scenario_path).parent.parent` assumes 2-level depth. | 1 of 4 | `sensitivity.py` |
| L8 | **Policy name mismatch with spec** — Code: `moderate`, `aggressive`. Spec: `aggressive_growth`, `risk_averse`. Stubs only, but would `KeyError` if spec names used. | 1 of 4 | `economic_policies.py` |
| L9 | **Post-harvest losses fixed at 10%** — Spec suggests crop-specific and pathway-specific loss rates. | 1 of 4 | `simulation.py` |

---

## 2. Verification Results

Each issue was verified against the actual source code. Findings:

| ID | Status | Notes |
|----|--------|-------|
| C1 | **Confirmed** | `_calc_gw_cost_per_m3` at line 97-99 uses only treatment + maintenance. `calculate_pumping_energy()` exists at `calculations.py:231-285` but never called by simulation. |
| C2 | **Confirmed** | Lines 242-246: `crop.cumulative_water_m3 += crop_demands[crop.crop_name]` — uses demand directly, ignoring `total_allocated`. |
| C3 | **Confirmed** | Lines 263-265: `crop.harvest_yield_kg = crop.expected_total_yield_kg` — no stress or yield_factor. `initialize_crop_state` at `state.py:233-264` doesn't receive `farm_config` to access `yield_factor`. |
| C4 | **Confirmed** | Lines 149-153: `daily_pv_kwh = pv_kw * 5.0`, `daily_wind_kwh = wind_kw * 6.0`. Precomputed PV/wind capacity factor data exists in `data/precomputed/power/`. |
| H1 | **Confirmed** | Lines 72-80: `crop_demand = irr_per_ha * crop.area_ha` — no efficiency division. `get_irrigation_efficiency()` at `calculations.py:433-448` exists but unused. |
| H2 | **Needs investigation** | Marginal price used for policy decisions is correct for optimization. Actual cost tracking needs verification of how `allocation.cost_usd` is set in each policy. |
| H3 | **Confirmed** | Lines 31-55: `max_gw_per_farm = total_well_capacity / num_farms`. This is a design decision — needs clarification on whether equal split or area-proportional is intended. |
| M1 | **Confirmed** | No storage state anywhere in simulation. `IrrigationStorageConfig.capacity_m3` loaded but unused. |
| M2 | **Confirmed** | `loader.py` does not parse `aquifer_exploitable_volume_m3` or `aquifer_recharge_rate_m3_yr`. Fields not in any dataclass. |
| M3 | **Confirmed** | `ComputedYearlyMetrics` missing aquifer, storage, demand-gap, financial metrics listed in spec. |
| M4 | **Confirmed** | Data file uses `light/moderate/heavy`. Spec uses `low/moderate/high/very_high`. Mismatch on `light` vs `low` and `heavy` vs `high`. |
| M5 | **Confirmed** | `financing_status` not parsed anywhere in `loader.py`. |
| L1 | **Confirmed** | On first day of new month, `get_monthly_water_m3` returns previous month's cumulative before reset occurs in `update_monthly_consumption`. |
| L2 | **Confirmed** | `include_energy_cost` stored at line 229 but never referenced in `allocate_water()`. |
| L3 | **Confirmed** | Logic is correct in aggregate but fragile: `water_cost_net = cost - energy; total = water_cost_net + energy + ...` |
| L4 | **Confirmed** | Line 5: "State is updated immutably — new state objects created each day" — contradicted by in-place mutation throughout. |
| L5 | **Confirmed** | Line 618: `/ len(costs)` — population variance, not sample variance. |
| L6 | **Confirmed** | Line 653: reads `total_area_ha` only. `total_farming_area_ha` silently ignored. |
| L7 | **Confirmed** | Line 73: `Path(scenario_path).parent.parent` — breaks if scenario at different depth. |
| L8 | **Confirmed** | Four stubs: `conservative`, `moderate`, `aggressive`, `balanced`. Spec expects `aggressive_growth` and `risk_averse`. |
| L9 | **Confirmed** | Fixed 10% post-harvest loss applied uniformly. |

**Issues NOT confirmed / demoted:**
- Original Review 1 Issue #11 (`water_per_yield_m3_kg` type mismatch): Verification shows the value is computed as a float, not a dict. **Not a bug.** Removed from plan.

---

## 3. Fix Plans

### C1 — Groundwater cost: add pumping & conveyance energy

**Approach:**
1. In `simulation.py`, where `WaterPolicyContext` is built (`build_water_policy_context`), call `calculate_pumping_energy()` from `calculations.py` using scenario's well depth and flow rate
2. Add `pumping_kwh_per_m3` and `conveyance_kwh_per_m3` fields to `WaterPolicyContext` dataclass
3. Update `_calc_gw_cost_per_m3` in `water_policies.py` to sum all three energy components: `(pumping + conveyance + treatment) × price + maintenance`
4. Set conveyance energy to 0.2 kWh/m³ per architecture spec, or make configurable

**Files:** `water_policies.py`, `simulation.py`

---

### C2 — Crop water allocation: use actual delivery

**Approach:**
1. In `update_farm_state`, compute `delivery_ratio = total_allocated / total_demand` (with guard for zero demand)
2. Replace `crop.cumulative_water_m3 += crop_demands[crop_name]` with `+= crop_demands[crop_name] * delivery_ratio`
3. Store `delivery_ratio` on `FarmState` for use by yield stress calculation (C3)

**Files:** `simulation.py`

---

### C3 — Yield model: apply water stress and yield_factor

**Approach:**
1. In `state.py`, add `yield_factor` parameter to `initialize_crop_state` (pass from farm config)
2. Apply `yield_factor` to `expected_yield_kg_per_ha` during initialization
3. Track cumulative water stress on `CropState` (add `expected_total_water_m3` field)
4. In `process_harvests`, compute: `actual_yield = expected_yield × (1 - Ky × (1 - water_delivery_ratio))`
5. Load `Ky` (yield response factor) from crop parameters data or use standard FAO values per crop

**Dependencies:** Requires C2 (correct water tracking) to be completed first.

**Files:** `simulation.py`, `state.py`, `data_loader.py` (to load Ky values)

---

### C4 — Energy generation: use precomputed capacity factors

**Approach:**
1. Add `get_pv_capacity_factor(date)` and `get_wind_capacity_factor(date)` methods to `SimulationDataLoader`
2. Load from `data/precomputed/power/` CSV files (already exist)
3. Replace fixed `* 5.0` / `* 6.0` with: `daily_pv_kwh = pv_kw × pv_cf × 24.0` (capacity factor is fraction of rated power)
4. Verify the format of precomputed power data to determine correct formula

**Files:** `simulation.py`, `data_loader.py`

---

### H1 — Irrigation efficiency: apply to demand

**Approach:**
1. In `calculate_farm_demand`, get irrigation type from scenario config
2. Call `get_irrigation_efficiency(type)` from `calculations.py`
3. Divide raw demand by efficiency: `crop_demand = (irr_per_ha * crop.area_ha) / efficiency`
4. Verify precomputed data does NOT already include efficiency adjustment (check `generate_irrigation_and_yields.py`)

**Files:** `simulation.py`

---

### H2 — Tiered pricing: verify marginal vs actual cost

**Approach:**
1. Trace how `allocation.cost_usd` is set in each of the 4 water policies
2. Verify whether municipal cost uses marginal price × volume or proper tiered total
3. If marginal, replace with call to `calculate_tiered_cost()` for the municipal portion
4. Ensure policy decision still uses marginal price (correct for optimization), but recorded cost uses tiered total

**Files:** `water_policies.py`, `simulation.py`

---

### H3 — Infrastructure capacity: area-proportional sharing

**Approach:**
1. **Decision needed:** Confirm with project owner whether capacity should be pooled (community-level check), area-proportional (per-farm), or equal split (current)
2. If area-proportional: change `max_gw_per_farm = total / num_farms` to `total × (farm.area_ha / community.total_area_ha)`
3. If pooled: move constraint checking to community level after all farms submit demands

**Files:** `simulation.py`

---

### M1 — Water storage dynamics

**Approach:**
1. Add `WaterStorageState` dataclass to `state.py` with `capacity_m3`, `current_level_m3`
2. Initialize at 50% capacity per spec
3. In daily loop: treated water fills storage, irrigation draws from storage
4. Enforce `0 ≤ storage ≤ capacity` constraints
5. Add `water_storage_utilization` metric to `metrics.py`

**Files:** `state.py`, `simulation.py`, `metrics.py`

---

### M2 — Aquifer depletion tracking

**Approach:**
1. Add `aquifer_exploitable_volume_m3` and `aquifer_recharge_rate_m3_yr` fields to `GroundwaterWellsConfig` in `loader.py`
2. Add `AquiferState` dataclass to `state.py`
3. Track cumulative extraction in daily loop
4. Compute `years_remaining` in metrics

**Files:** `loader.py`, `state.py`, `simulation.py`, `metrics.py`

---

### M3 — Missing spec metrics

**Approach:** Add the following metrics to `ComputedYearlyMetrics` and implement in `compute_all_metrics`:
- `aquifer_depletion_rate` (depends on M2)
- `days_without_municipal_water` (count from daily records)
- `water_storage_utilization` (depends on M1)
- `irrigation_demand_gap` (daily demand vs delivery — depends on C2)
- `crop_diversity_index` (Shannon index from planted areas)

**Dependencies:** M1, M2, C2

**Files:** `metrics.py`

---

### M4 — Salinity naming alignment

**Approach:**
1. Standardize on spec names: `low`, `moderate`, `high`, `very_high`
2. Update data file `treatment_kwh_per_m3-toy.csv`: rename `light` → `low`, `heavy` → `high`
3. Verify all YAML files use the standardized names
4. Add validation in `loader.py` for allowed salinity values

**Files:** Data CSVs, `loader.py`

---

### M5 — Financing model connection

**Approach:** Defer to economic system implementation (Phase 8 per development roadmap). Document as known gap. This is a feature addition, not a bug fix.

**Action:** No code change. Add note to architecture doc.

---

### L1 — Monthly tracker reset timing

**Approach:** In `get_monthly_water_m3`, check if the month has changed and return `0.0` if so (before update_monthly_consumption is called). This ensures tier pricing starts fresh on the first day of each month.

**Files:** `state.py`

---

### L2 — CheapestSource include_energy_cost

**Approach:** Implement the parameter: when `include_energy_cost=False`, compare only maintenance costs (skip energy portion in `_calc_gw_cost_per_m3`). Or remove the parameter if the distinction is not needed.

**Files:** `water_policies.py`

---

### L3 — Energy cost double counting clarity

**Approach:** Add clear comments explaining the subtraction/re-addition pattern. Consider refactoring `allocation.cost_usd` to exclude energy cost, making the separation clean.

**Files:** `metrics.py`

---

### L4 — State.py docstring

**Approach:** Update line 5 docstring to: "State is updated in-place during each daily step."

**Files:** `state.py`

---

### L5 — Sample variance

**Approach:** Change `/ len(costs)` to `/ (len(costs) - 1)` with guard for `len(costs) < 2`.

**Files:** `metrics.py`

---

### L6 — total_farming_area_ha field

**Approach:** In `loader.py`, accept either `total_area_ha` or `total_farming_area_ha` (with the latter as canonical). Fall back if one is missing.

**Files:** `loader.py`

---

### L7 — Sensitivity project_root

**Approach:** Derive project root by searching upward for `settings/data_registry.yaml` or accept `project_root` as a parameter.

**Files:** `sensitivity.py`

---

### L8 — Policy name alignment

**Approach:** Rename stubs to match spec: `moderate` → `risk_averse`, `aggressive` → `aggressive_growth`. Update the registry dict.

**Files:** `economic_policies.py`

---

### L9 — Post-harvest losses

**Approach:** Defer to post-harvest system implementation (Phase 7 per roadmap). The 10% fixed rate is acceptable for MVP.

**Action:** No code change.

---

## 4. Execution Order

Fixes are grouped into phases based on dependencies. Within each phase, work can proceed in parallel.

```
Phase 1: Foundation fixes (no dependencies)
├── C1  Groundwater cost: pumping + conveyance
├── C4  Energy generation: precomputed capacity factors
├── H1  Irrigation efficiency adjustment
├── L1  Monthly tracker reset timing
├── L4  State.py docstring fix
├── L5  Sample variance fix
├── L6  total_farming_area_ha handling
├── L7  Sensitivity project_root
├── L8  Policy name alignment
└── M4  Salinity naming alignment

Phase 2: Core simulation fixes (depends on Phase 1)
├── C2  Crop water allocation: actual delivery
├── H2  Tiered pricing verification
└── H3  Infrastructure capacity sharing (needs design decision)

Phase 3: Yield model (depends on C2)
└── C3  Yield stress model + yield_factor

Phase 4: New features (depends on Phases 1-3)
├── M1  Water storage dynamics
├── M2  Aquifer depletion tracking
├── L2  CheapestSource include_energy_cost
└── L3  Energy cost double counting clarity

Phase 5: Metrics completion (depends on M1, M2, C2)
└── M3  Missing spec metrics
```

---

## 5. Agent Assignments

Four agents can work in parallel within each phase. The key constraint is that agents editing the same file must not run simultaneously. Below is the optimal assignment.

### Phase 1 — Four parallel agents

#### Agent 1: Water Policy Fixes
**Scope:** Fix groundwater cost calculation
**Issues:** C1, L2
**Files modified:**
- `src/policies/water_policies.py` — Add pumping + conveyance to `_calc_gw_cost_per_m3`; implement or remove `include_energy_cost`
- `src/simulation/simulation.py` — Update `build_water_policy_context` to compute and pass pumping/conveyance energy fields

**Steps:**
1. Read `src/settings/calculations.py` to understand `calculate_pumping_energy()` signature and return values
2. Add `pumping_kwh_per_m3: float` and `conveyance_kwh_per_m3: float` to `WaterPolicyContext` dataclass
3. In `build_water_policy_context` in `simulation.py`, call `calculate_pumping_energy()` with well depth and flow rate from scenario, set conveyance to 0.2 kWh/m³
4. Update `_calc_gw_cost_per_m3` to: `(pumping + conveyance + treatment) × price + maintenance`
5. Either implement `include_energy_cost` branching in `CheapestSource.allocate_water()` or remove the dead parameter
6. Run simulation to verify no errors

**Estimated effort:** Medium

---

#### Agent 2: Energy & Demand Fixes
**Scope:** Fix energy generation and irrigation efficiency
**Issues:** C4, H1
**Files modified:**
- `src/simulation/data_loader.py` — Add `get_pv_capacity_factor(date)` and `get_wind_capacity_factor(date)` methods
- `src/simulation/simulation.py` — Replace fixed energy estimates; apply irrigation efficiency

**Steps:**
1. Read `data/precomputed/power/` files to understand format (columns, date format, units)
2. Add capacity factor loading/lookup methods to `SimulationDataLoader`
3. In `simulation.py`, replace `pv_kw * 5.0` / `wind_kw * 6.0` with capacity factor lookups
4. Read `src/settings/calculations.py` to confirm `get_irrigation_efficiency()` interface
5. In `calculate_farm_demand`, get irrigation type from scenario and divide demand by efficiency
6. Verify precomputed irrigation data doesn't already include efficiency (check `data/scripts/generate_irrigation_and_yields.py`)
7. Run simulation to verify

**Estimated effort:** Medium

---

#### Agent 3: Config & Naming Fixes
**Scope:** Fix loader, naming mismatches, and config issues
**Issues:** M4, L6, L8, M2 (loader portion only)
**Files modified:**
- `src/settings/loader.py` — Parse aquifer fields, handle `total_farming_area_ha`
- `src/policies/economic_policies.py` — Rename policy stubs
- `data/parameters/water/treatment_kwh_per_m3-toy.csv` — Rename salinity levels

**Steps:**
1. Update `GroundwaterWellsConfig` dataclass to include `aquifer_exploitable_volume_m3` and `aquifer_recharge_rate_m3_yr` (with defaults for backward compat)
2. Update `_load_infrastructure()` to parse aquifer fields from YAML
3. Update `CommunityStructureConfig` to accept either `total_area_ha` or `total_farming_area_ha`
4. Rename salinity levels in data CSV: `light` → `low`, `heavy` → `high`
5. Add validation for allowed salinity values in loader
6. In `economic_policies.py`, rename `Moderate` → `RiskAverse`, `Aggressive` → `AggressiveGrowth`, update registry

**Estimated effort:** Small-Medium

---

#### Agent 4: Trivial Fixes
**Scope:** Documentation, variance, sensitivity
**Issues:** L4, L5, L7
**Files modified:**
- `src/simulation/state.py` — Fix docstring (line 5)
- `src/simulation/metrics.py` — Fix variance calculation (line 618)
- `src/simulation/sensitivity.py` — Make `project_root` robust (line 73)

**Steps:**
1. Update `state.py` line 5 docstring
2. In `metrics.py`, change `/ len(costs)` to `/ (len(costs) - 1)` with `len(costs) >= 2` guard
3. In `sensitivity.py`, replace `Path(scenario_path).parent.parent` with upward search for `data_registry.yaml` or add `project_root` parameter
4. Run simulation to verify no regressions

**Estimated effort:** Small

---

### Phase 2 — Two parallel agents

#### Agent 5: Core Allocation Fixes
**Scope:** Fix water allocation tracking and tier pricing
**Issues:** C2, H2, L1
**Files modified:**
- `src/simulation/simulation.py` — Fix `update_farm_state` water distribution; verify tier pricing
- `src/simulation/state.py` — Fix monthly tracker reset in `get_monthly_water_m3`

**Steps:**
1. In `update_farm_state`, compute `delivery_ratio = total_allocated / total_demand`
2. Replace `crop.cumulative_water_m3 += crop_demands[crop_name]` with `+= demand × delivery_ratio`
3. Store `delivery_ratio` on `FarmState` daily for use by yield model
4. In `state.py`, update `get_monthly_water_m3` to check month boundary and return 0 if month changed
5. Trace `allocation.cost_usd` through all 4 policies; verify municipal cost uses tiered total, not marginal × volume
6. If needed, fix cost calculation to use `calculate_tiered_cost()` for recorded cost
7. Run simulation and compare outputs to baseline

**Estimated effort:** Medium

---

#### Agent 6: Capacity Sharing (Design Decision)
**Scope:** Determine and implement correct capacity sharing model
**Issues:** H3
**Files modified:**
- `src/simulation/simulation.py` — `calculate_system_constraints`

**Steps:**
1. Review architecture docs for the intended sharing model
2. If area-proportional: change division to use `farm.area_ha / total_community_area_ha`
3. If community-pooled: move capacity check to after all farms submit demands
4. Document the chosen approach in code comments
5. Run simulation and verify constraints work correctly

**Estimated effort:** Small (but blocked on design decision)

---

### Phase 3 — One agent

#### Agent 7: Yield Stress Model
**Scope:** Implement FAO water production function and yield_factor
**Issues:** C3
**Files modified:**
- `src/simulation/state.py` — Add `yield_factor` to `CropState`, modify `initialize_crop_state`
- `src/simulation/simulation.py` — Implement yield reduction in `process_harvests`
- `src/simulation/data_loader.py` — Load Ky (yield response factor) values per crop

**Steps:**
1. Add `expected_total_water_m3` field to `CropState` (total irrigation demand over growth period)
2. Pass `yield_factor` from farm config through to `initialize_crop_state`; apply to `expected_yield_kg_per_ha`
3. In `process_harvests`, compute `water_ratio = cumulative_water_m3 / expected_total_water_m3`
4. Look up Ky per crop (standard FAO values: tomato=1.05, potato=1.10, onion=1.10, kale=0.95, cucumber=1.05)
5. Apply: `harvest_yield_kg = expected_yield × (1 - Ky × (1 - min(1.0, water_ratio)))`
6. Verify yields decrease under water stress and differ by farm yield_factor
7. Run simulation and compare policy outcomes

**Estimated effort:** Medium-Large

---

### Phase 4 — Two parallel agents

#### Agent 8: Water Storage Dynamics
**Scope:** Implement storage state tracking
**Issues:** M1
**Files modified:**
- `src/simulation/state.py` — Add `WaterStorageState` dataclass
- `src/simulation/simulation.py` — Integrate storage into daily loop

**Steps:**
1. Add `WaterStorageState(capacity_m3, current_level_m3)` to `state.py`
2. Initialize at 50% capacity per spec
3. In daily loop: treated water → storage inflow; irrigation demand → storage outflow
4. Enforce `0 ≤ level ≤ capacity`
5. Track storage utilization for metrics

**Estimated effort:** Medium

---

#### Agent 9: Aquifer & Clarity Fixes
**Scope:** Aquifer tracking + energy cost clarity
**Issues:** M2 (simulation portion), L3
**Files modified:**
- `src/simulation/state.py` — Add `AquiferState` dataclass
- `src/simulation/simulation.py` — Track extraction daily
- `src/simulation/metrics.py` — Compute depletion metrics; clarify energy cost comments

**Steps:**
1. Add `AquiferState` to `state.py` using aquifer params from loader (Phase 1 Agent 3)
2. Update daily loop to track cumulative extraction
3. In metrics, compute `years_remaining` from extraction rate and exploitable volume
4. Add clear comments explaining the energy cost subtraction/re-addition pattern in `compute_monthly_metrics`

**Estimated effort:** Medium

---

### Phase 5 — One agent

#### Agent 10: Missing Metrics
**Scope:** Implement remaining spec metrics
**Issues:** M3
**Files modified:**
- `src/simulation/metrics.py` — Add new metric fields and computations

**Steps:**
1. Add to `ComputedYearlyMetrics`: `aquifer_depletion_rate`, `days_without_municipal_water`, `water_storage_utilization`, `irrigation_demand_gap`, `crop_diversity_index`
2. Implement each from daily records or new state data
3. Update `compute_all_metrics()` to call new calculations
4. Run simulation and verify metrics appear in output

**Estimated effort:** Medium

---

## 6. Summary

| Phase | Agents | Issues Addressed | Can Parallelize? |
|-------|--------|-----------------|------------------|
| 1 | 4 agents | C1, C4, H1, M4, L1–L8, M2 (loader) | Yes — all 4 parallel |
| 2 | 2 agents | C2, H2, H3, L1 | Yes — 2 parallel |
| 3 | 1 agent  | C3 | No — depends on C2 |
| 4 | 2 agents | M1, M2 (sim), L3 | Yes — 2 parallel |
| 5 | 1 agent  | M3 | No — depends on M1, M2 |

**Total: 10 agent assignments across 5 phases**
**Deferred (no code change):** M5 (financing model), L9 (post-harvest losses)

### Critical Path

```
C1 (GW cost) ──────────────────────────────────────────→ done
C4 (energy)  ──────────────────────────────────────────→ done
H1 (efficiency) ───────────────────────────────────────→ done
                   C2 (water tracking) → C3 (yield model) → M3 (metrics)
                                       ↗
              M1 (storage) ────────────→ M3 (metrics)
              M2 (aquifer) ────────────→ M3 (metrics)
```

The longest dependency chain is: **Phase 1 → C2 → C3 → M3** (4 sequential steps).
All other work can proceed in parallel alongside this chain.
