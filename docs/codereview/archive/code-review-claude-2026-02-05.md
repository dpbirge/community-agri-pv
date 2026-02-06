# Code Review: /src Layer 3 Simulation Engine

**Reviewer:** Claude (Opus)
**Date:** 2026-02-05
**Scope:** All files under `/src`, cross-referenced against `docs/architecture/mvp-calculations.md` and `docs/architecture/mvp-structure.md`
**Focus:** Logic errors, calculation errors, and gaps/inconsistencies between code and planning docs

---

## Executive Summary

The codebase is well-structured and the water simulation MVP is functionally complete. However, I found **7 logic/calculation errors**, **5 gaps between code and spec**, and **4 internal inconsistencies** that should be addressed. The most impactful issues are: (1) groundwater cost in the simulation excludes pumping energy that the spec requires, (2) the crop yield model ignores `yield_factor` and water stress, and (3) the `CheapestSource` policy ignores its `include_energy_cost` parameter. None of these are catastrophic, but several will produce incorrect economic outputs.

---

## 1. Logic and Calculation Errors

### 1.1 CRITICAL — Groundwater cost omits pumping energy (`simulation.py` / `water_policies.py`)

**Spec (mvp-calculations.md §2.1, §5.2):**
```
Cost_gw = (E_pump + E_convey + E_treatment) × electricity_price + O&M_cost
```

**Code (`water_policies.py:97-99`):**
```python
def _calc_gw_cost_per_m3(self, ctx):
    return (ctx.treatment_kwh_per_m3 * ctx.energy_price_per_kwh) + ctx.gw_maintenance_per_m3
```

The groundwater cost calculation uses only `treatment_kwh_per_m3` (BWRO desalination energy). It **omits pumping energy** (`E_pump`) and **conveyance energy** (`E_convey`), both of which are specified in the calculations document. The `calculate_pumping_energy()` function exists in `calculations.py` but is never called by the simulation loop.

**Impact:** Groundwater costs are understated by approximately 0.05–0.15 USD/m³ (the pumping component), which systematically biases all water policy comparisons in favor of groundwater. The `CheapestSource` and `ConserveGroundwater` policies make switching decisions based on this incomplete cost.

**Fix:** Add `pumping_kwh_per_m3` and `conveyance_kwh_per_m3` fields to `WaterPolicyContext`, compute them from `calculations.py`, and include them in `_calc_gw_cost_per_m3()`.

---

### 1.2 CRITICAL — Crop yield ignores `yield_factor` and water stress (`simulation.py:265-266`, `state.py:258-264`)

**Spec (mvp-calculations.md §4.1):**
```
Y_actual = Y_potential × (1 - K_y × (1 - ET_actual / ET_crop))
```

And from mvp-structure.md §2, farms have a `yield_factor` parameter for management quality.

**Code (`process_harvests` in simulation.py:265-266):**
```python
crop.harvest_yield_kg = crop.expected_total_yield_kg
```

And in `state.py:258-264`, `initialize_crop_state`:
```python
return CropState(
    ...
    expected_yield_kg_per_ha=yield_info["yield_kg_per_ha"],
)
```

The simulation assigns `expected_total_yield_kg` (a fixed value from precomputed data) directly as the harvest yield. It never applies:
- The farm's `yield_factor` multiplier (always ignored)
- Water stress reduction from the FAO water production function
- The `weather_stress_factor` returned by `get_season_yield()` (loaded but never used)

**Impact:** All farms produce identical yields regardless of their `yield_factor` setting or how much water they actually received. The core feedback loop between water allocation and crop output is broken — water policy choices have no effect on yield.

**Fix:** In `process_harvests()` or at harvest time, apply: `actual_yield = expected_yield × yield_factor × (1 - Ky × (1 - water_delivery_ratio))`. The `weather_stress_factor` from yield data could also be incorporated.

---

### 1.3 MODERATE — `CheapestSource` ignores its `include_energy_cost` parameter

**Code (`water_policies.py:228-229`):**
```python
def __init__(self, include_energy_cost: bool = True):
    self.include_energy_cost = include_energy_cost
```

The constructor accepts `include_energy_cost` but the `allocate_water()` method never references `self.include_energy_cost`. The cost comparison always includes energy cost via `_calc_gw_cost_per_m3()`. This parameter is dead code.

**Fix:** Either remove the parameter or implement the branching logic (e.g., if `include_energy_cost` is False, compare only maintenance costs).

---

### 1.4 MODERATE — `snapshot_yearly_metrics` uses cumulative values, not yearly deltas (`simulation.py:281-319`)

**Code (`simulation.py:310-313`):**
```python
return YearlyFarmMetrics(
    ...
    total_water_m3=farm_state.total_water_m3(),
    groundwater_m3=farm_state.cumulative_groundwater_m3,
    ...
)
```

This snapshots the cumulative values from `farm_state`, which are reset at the beginning of each year in `reset_farm_for_new_year()`. However, for the **final year** of the simulation (lines 471-476), the metrics are captured *after* the simulation loop exits — and the yearly reset for that year never happened because there's no next-year boundary. This means the final year's metrics work correctly by accident: the accumulators hold exactly that year's data.

**But** there's a subtle timing issue: `snapshot_yearly_metrics` is called at year boundary **before** `reset_farm_for_new_year()`, which is correct. The sequence is: snapshot → reset → reinitialize. This is actually fine. However, the code comment in `state.py:5` says "State is updated immutably — new state objects created each day" which is factually incorrect — state is mutated in place. This is a documentation-only issue, not a logic bug.

**Verdict:** The accumulator logic is correct, but the misleading documentation should be updated.

---

### 1.5 MODERATE — Water allocation distributes water to crops without considering actual delivery vs. demand (`simulation.py:242-246`)

**Code (`update_farm_state` in simulation.py:242-246):**
```python
for crop in farm_state.active_crops(current_date):
    if crop.crop_name in crop_demands:
        crop.cumulative_water_m3 += crop_demands[crop.crop_name]
```

This always adds the **full demand** to each crop's cumulative water, not the actual water delivered. If the allocation was constrained (e.g., by well capacity), the total allocation `groundwater_m3 + municipal_m3` may be less than the total demand. But each crop still gets its full demand recorded.

**Impact:** `crop.cumulative_water_m3` overstates actual water delivery when constraints bind. This inflates the water-per-yield metric and makes it impossible to correctly compute the water stress factor needed for yield reduction (Issue 1.2).

**Fix:** Distribute actual delivered water proportionally. E.g.:
```python
delivery_ratio = total_allocated / total_demand if total_demand > 0 else 1.0
crop.cumulative_water_m3 += crop_demands[crop.crop_name] * delivery_ratio
```

---

### 1.6 MINOR — Irrigation demand does not account for irrigation system efficiency (`simulation.py:72-80`)

**Spec (mvp-calculations.md §2.4):**
```
Water_demand = (ET_crop × Area) / η_irrigation
```

Where η_irrigation is 0.90 for drip irrigation, 0.75 for sprinkler, etc.

**Code (`calculate_farm_demand` in simulation.py:72-80):**
```python
irr_per_ha = data_loader.get_irrigation_m3_per_ha(crop.crop_name, ...)
crop_demand = irr_per_ha * crop.area_ha
```

The irrigation demand is taken directly from the precomputed data without dividing by irrigation efficiency. The `get_irrigation_efficiency()` function exists in `calculations.py` and the `calculate_irrigation_demand_adjustment()` function implements the exact formula — but neither is called by the simulation loop.

**Impact:** Depending on whether the precomputed data already includes efficiency adjustment, this may understate actual water needs for less-efficient systems. For the MVP's drip irrigation (η=0.90), the error is ~11%.

**Fix:** Call `calculate_irrigation_demand_adjustment()` from `calculations.py` in the simulation loop, or verify that the precomputed data already accounts for system efficiency.

---

### 1.7 MINOR — Population-based variance in cost CV (`metrics.py:618`)

**Code (`compute_cost_volatility` in metrics.py:618):**
```python
variance = sum((c - mean_cost) ** 2 for c in costs) / len(costs)
```

This computes population variance (divides by N) rather than sample variance (divides by N-1). For a 6-year simulation with 72 monthly data points, the difference is small (~1.4%), but technically a sample standard deviation should use N-1.

---

## 2. Gaps Between Code and Specification

### 2.1 Water storage dynamics not implemented

**Spec (mvp-calculations.md §2.5):**
```
Storage(t+1) = Storage(t) + Inflow(t) - Outflow(t)
Constraints: 0 ≤ Storage(t) ≤ capacity_m3
```

**Code:** There is no water storage tracking in the simulation. The `IrrigationStorageConfig.capacity_m3` is loaded from YAML but never used during the simulation loop. Water treatment output flows directly to irrigation demand with no storage buffer.

**Impact:** Storage constraints would limit how much water can be buffered between treatment and irrigation. Without this, the simulation implicitly assumes infinite storage throughput and no storage losses (which is noted as an MVP simplification in the spec, but the spec also defines initial storage at 50% capacity — suggesting it was intended for implementation).

---

### 2.2 Aquifer depletion tracking not implemented

**Spec (mvp-calculations.md §2.7):**
```
Remaining_volume_m3(t) = aquifer_exploitable_volume_m3 - Σ Net_depletion_m3_yr
Years_remaining = Remaining_volume_m3 / Net_depletion_m3_yr
```

**Code:** The YAML settings include `aquifer_exploitable_volume_m3` and `aquifer_recharge_rate_m3_yr` fields, but the `GroundwaterWellsConfig` dataclass in `loader.py` doesn't capture them, and no simulation code tracks aquifer depletion.

---

### 2.3 Financing cost model not connected to simulation economics

**Spec (mvp-calculations.md §5.1):** Defines a complete financing cost model with 6 financing categories affecting CAPEX/OPEX calculations.

**Code:** The YAML settings define `financing_status` for every subsystem. The `_load_infrastructure()` function in `loader.py` does **not** parse `financing_status` from any section — it's silently ignored. No `financing_profiles.csv` lookup occurs. The `EconomicsConfig` only has a single `DebtConfig` with principal/term/rate, but infrastructure-specific debt is never computed.

**Impact:** Economic outputs (net income, operating costs, payback period) do not reflect the configured financing structure. All infrastructure costs are effectively zero in the simulation.

---

### 2.4 Several spec-defined metrics not computed

The following metrics from mvp-structure.md §4 are referenced but not implemented anywhere in `metrics.py`:

- **Aquifer depletion rate** (m³/yr, years remaining)
- **Days without municipal water** (days/yr)
- **Water storage utilization** (%)
- **Irrigation demand vs delivery** (gap m³/day, delivery ratio)
- **Crop diversity index** (Shannon index)
- **Post-harvest losses** as a tracked metric (only applied as a fixed 10% in revenue)
- **Payback period, ROI, NPV** (financial metrics)
- **Cash reserves** tracking
- **Debt-to-revenue ratio**

These are defined in the spec but not yet coded. Some are marked TBD in the spec; others (like days without municipal water, irrigation demand vs delivery) should be straightforward to add from existing daily records.

---

### 2.5 Policy name mismatch between YAML and mvp-structure.md

**Spec (mvp-structure.md §3):**
- Economic policy options: `[balanced, aggressive_growth, conservative, risk_averse]`
- Food processing policy options: `[all_fresh, maximize_storage, balanced, market_responsive]`

**Code (economic_policies.py):**
- Implemented classes: `Conservative`, `Moderate`, `Aggressive`, `Balanced`
- Names: `conservative`, `moderate`, `aggressive`, `balanced`

The spec says `aggressive_growth` and `risk_averse`, but the code has `aggressive` and `moderate`. There's no `risk_averse` class. The spec's `balanced` maps to the code's `balanced`, but `aggressive_growth` ≠ `aggressive`. This will cause `KeyError` if anyone configures a scenario using the spec's names.

---

## 3. Internal Inconsistencies

### 3.1 `salinity_level` naming inconsistency between YAML and data files

**YAML (`mvp-settings.yaml:22`):** `salinity_level: moderate` (on groundwater_wells)
**YAML (`mvp-settings.yaml:35`):** `salinity_level: moderate` (on water_treatment)
**Data (`treatment_kwh_per_m3-toy.csv`):** Uses index values like `light`, `moderate`, `heavy`

But `mvp-structure.md §2` defines: `salinity_level: [low, moderate, high, very_high]`

The YAML uses `moderate` which matches the data file, but the spec defines `low/moderate/high/very_high` while the data file uses `light/moderate/heavy`. The code `get_treatment_kwh_per_m3()` looks up by the value from config, so if anyone uses `low` (per spec), it will fail with a KeyError because the data file has `light` instead.

---

### 3.2 `total_farming_area_ha` vs `total_area_ha` in community_structure

**YAML (`mvp-settings.yaml:123-124`):**
```yaml
total_farming_area_ha: 125
total_area_ha: 125
```

**Loader (`loader.py:652-653`):**
```python
total_area_ha=_require(community_data, "total_area_ha", ...),
```

The loader reads `total_area_ha` but the YAML also defines `total_farming_area_ha`. The spec (mvp-structure.md §2) lists `total_farming_area_ha` as the canonical field name. The loader doesn't read `total_farming_area_ha` at all, so it's silently ignored. If a scenario only specifies `total_farming_area_ha` without `total_area_ha`, loading will fail.

---

### 3.3 Monthly operating cost calculation double-counts then re-adds energy

**Code (`metrics.py:250-252`):**
```python
water_cost_net = water_data["cost_usd"] - energy_cost
total_operating = water_cost_net + energy_cost + diesel_cost + fertilizer_monthly + labor_monthly
```

This subtracts `energy_cost` from water cost, then adds it back. The net effect is `total_operating = water_data["cost_usd"] + diesel_cost + fertilizer_monthly + labor_monthly`, which means energy is included via the original water cost (which bundles treatment energy cost). The intent is to separate energy as its own category in the cost breakdown.

However, in `plot_monthly_cost_breakdown()` (notebook_plotting.py:740-741):
```python
water_costs = [m.total_water_cost_usd - m.energy_cost_usd for m in monthly_metrics]
energy_costs = [m.energy_cost_usd for m in monthly_metrics]
```

The plotting code re-separates them correctly. So the total stacks correctly. **But** the `total_operating_cost_usd` field on the metric includes the full water cost (with energy bundled in), then the plotting layer subtracts it back out. This is correct in aggregate but confusing, and `total_operating_cost_usd` is used directly in `compute_net_income()` for net income calculation, where it represents the right total. No actual error, but the layering is fragile.

---

### 3.4 Sensitivity analysis `project_root` derivation is fragile

**Code (`sensitivity.py:73`):**
```python
project_root = str(Path(scenario_path).parent.parent)
```

This assumes the scenario file is always exactly two directory levels below the project root (e.g., `settings/mvp-settings.yaml`). If the scenario is at a different depth (e.g., `settings/scenarios/dev.yaml` or an absolute path), this will resolve to the wrong root, causing all data file lookups to fail silently or with cryptic errors.

**Fix:** Derive project root from a known anchor (e.g., find the directory containing `settings/data_registry.yaml`) or accept it as a parameter.

---

## 4. Minor Observations (Non-Errors)

### 4.1 No crop active-season boundary check for harvests across years

Crops planted late in the year (e.g., onion planted Sep-15) may have harvest dates in the following year. The code handles this correctly via `reinitialize_farm_crops_for_year()` which appends new crops while preserving old ones. Harvests trigger based on `harvest_date <= current_date` regardless of year. This is correct behavior.

### 4.2 `load_crop_prices` research file path format differs from registry

```python
# Research path:
filepath = f"data/prices/crops/{crop_name}_prices-research.csv"
# Registry (toy) path:
filepath = f"data/prices/crops/historical_{crop_name}_prices-toy.csv"
```

The research file naming convention (`{crop}_prices-research.csv`) differs from the toy convention (`historical_{crop}_prices-toy.csv`). This is intentional but could cause confusion — the registry doesn't know about research files since they use a different naming pattern.

### 4.3 Processing category specs calculated but unused

`calculations.py` computes detailed processing specs (capacity, energy, labor) for each food processing category, but none of these values are used by the simulation loop. The `food_policy: all_fresh` means no processing occurs, which is consistent for MVP, but the computation infrastructure exists without integration.

---

## 5. Recommendations (Prioritized)

| Priority | Issue | Section | Effort |
|----------|-------|---------|--------|
| P0 | Add pumping + conveyance energy to GW cost | 1.1 | Medium |
| P0 | Implement yield_factor and water stress on yield | 1.2 | Medium |
| P0 | Fix crop water tracking to use actual delivery | 1.5 | Small |
| P1 | Apply irrigation efficiency adjustment | 1.6 | Small |
| P1 | Remove or implement `include_energy_cost` param | 1.3 | Small |
| P1 | Parse `financing_status` in loader | 2.3 | Medium |
| P1 | Align policy names with spec | 2.5 | Small |
| P1 | Align salinity level names (spec ↔ data) | 3.1 | Small |
| P2 | Implement water storage dynamics | 2.1 | Medium |
| P2 | Parse aquifer parameters in loader | 2.2 | Small |
| P2 | Add missing metrics (demand vs delivery, etc.) | 2.4 | Medium |
| P2 | Fix `total_farming_area_ha` field handling | 3.2 | Small |
| P2 | Make sensitivity `project_root` robust | 3.4 | Small |
| P3 | Fix state.py docstring about immutability | 1.4 | Trivial |
| P3 | Use sample variance in CV calculation | 1.7 | Trivial |

---

## 6. Summary of Findings

| Category | Count |
|----------|-------|
| Critical logic/calculation errors | 2 |
| Moderate logic/calculation errors | 3 |
| Minor logic/calculation errors | 2 |
| Spec gaps (features not implemented) | 5 |
| Internal inconsistencies | 4 |
| **Total issues** | **16** |

The two critical issues (1.1 and 1.2) should be addressed before using simulation outputs for any economic analysis or policy comparison, as they directly affect the accuracy of cost calculations and the fundamental water-yield feedback loop.
