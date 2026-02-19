# Data Gaps and Hardcoded Values Audit

**Date:** 2026-02-18
**Scope:** All 6 docs/arch/ files vs data/ folder and src/ codebase
**Summary:** 12 missing datasets, 8 filename discrepancies, 53 hardcoded values found

---

## 1. Missing Data Report

### 1.1 Missing Data Files

These datasets are referenced or implied by architecture docs but do not exist in the data/ folder or registry.

| # | Doc | Section | Expected Dataset | Purpose | Status |
|---|-----|---------|-----------------|---------|--------|
| 1 | calculations.md | §4 Soil Salinity | `data/parameters/crops/crop_salinity_tolerance.csv` | FAO-29 ECe thresholds and slope b values per crop | MISSING |
| 2 | calculations.md | §2 Pumping Energy | `data/parameters/water/pump_equipment_parameters.csv` | Pump efficiency values by type | MISSING (entire `data/parameters/water/` folder absent) |
| 3 | calculations.md | §3 Generator | `data/parameters/energy/generator_parameters.csv` | Willans line fuel coefficients (a, b) by generator type | MISSING (entire `data/parameters/energy/` folder absent) |
| 4 | calculations.md | §6 Processing | `data/parameters/processing/food_processing_equipment-toy.csv` | Processing equipment capacity and energy per kg by type | MISSING (entire `data/parameters/processing/` folder absent; may be same data as `equipment/processing_equipment-toy.csv` under different path) |
| 5 | data.md | Planned table | `data/parameters/economic/equipment_lifespans.csv` | Component lifespans for replacement cost calculations | EXISTS as `equipment_lifespans-toy.csv` (planned table entry is outdated) |
| 6 | overview.md | §3 Post-harvest | Transport cost/distance parameters | Transport cost per km per kg for market access modeling | MISSING (no transport parameters file exists) |
| 7 | policies.md | Market policies | Rolling 12-month average price data | `avg_price_per_kg` for market policy price ratio calculations | PARTIAL (price files exist but rolling average must be computed at runtime; no pre-computed average file) |
| 8 | calculations.md | §5 Economic | `docs/research/egyptian_utility_pricing.md` | Egyptian tariff structure reference document | MISSING |
| 9 | calculations.md | §5 Economic | `docs/research/egyptian_water_pricing.md` | Egyptian HCWW pricing reference document | MISSING |
| 10 | calculations.md | §4 Microclimate | `docs/planning/microclimate_yield_research_plan.md` | Research plan for microclimate yield data | MISSING |
| 11 | data.md | Prices > inputs | Fertilizer costs research file | Research-grade fertilizer cost data | MISSING (only `-toy` variant exists) |
| 12 | overview.md | §3 Labor | Community labor supply parameters | Working-age population, available hours, skill profiles | MISSING (needed for community vs external labor ratio) |

### 1.2 Filename/Path Discrepancies

The architecture docs reference files under different names or paths than what actually exists. These are not missing data per se, but indicate stale references in the docs that should be corrected.

| # | Doc Reference | Actual File | Issue |
|---|--------------|-------------|-------|
| 1 | `data/precomputed/irrigation/crop_water_requirements-toy.csv` (calculations.md §2) | `data/precomputed/irrigation_demand/irrigation_m3_per_ha_<crop>-toy.csv` | Different folder name and per-crop file pattern |
| 2 | `crop_parameters-toy.csv` (calculations.md §4.3, §4.4) | `crop_coefficients-toy.csv` | Different filename |
| 3 | `data/precomputed/power/pv_power_output_normalized-toy.csv` (calculations.md §3) | `data/precomputed/pv_power/pv_normalized_kwh_per_kw_daily-toy.csv` | Different folder and filename |
| 4 | `data/precomputed/power/wind_power_output_normalized-toy.csv` (calculations.md §3) | `data/precomputed/wind_power/wind_normalized_kwh_per_kw_daily-toy.csv` | Different folder and filename |
| 5 | `data/precomputed/yields/crop_yields-toy.csv` (calculations.md §4) | `data/precomputed/crop_yields/yield_kg_per_ha_<crop>-toy.csv` | Different folder and per-crop file pattern |
| 6 | `tomato_prices-research.csv` (data.md detailed listing) | `historical_tomato_prices-research.csv` | Missing `historical_` prefix in doc |
| 7 | `post_harvest_losses-*.csv` (data.md, visible in git status as deleted) | `handling_loss_rates-*.csv` | File renamed; old name appears in docs |
| 8 | `data/parameters/processing/food_processing_equipment-toy.csv` (calculations.md §6) | `data/parameters/equipment/processing_equipment-toy.csv` | Different subfolder (`processing/` vs `equipment/`) |

### 1.3 Data Registry Gaps

Files that exist on disk but are NOT in the data registry:

| File | Type | Note |
|------|------|------|
| `data/parameters/crops/TEMPLATE_crop_coefficients.csv` | Template | Templates typically not registered |
| `data/precomputed/weather/TEMPLATE_weather.csv` | Template | Templates typically not registered |
| `data/parameters/crops/crop_coefficients-research.csv` | Research alt | Has `-toy` registered; research variant not registered |
| `data/parameters/crops/microclimate_yield_effects-research.csv` | Research | Not in registry |
| `data/parameters/equipment/water_treatment-research.csv` | Research alt | Has `-toy` registered; research variant not registered |
| `data/parameters/costs/operating_costs-research.csv` | Research alt | Has `-toy` registered; research variant listed as comment |
| `data/parameters/labor/labor_wages-research.csv` | Research alt | Has `-toy` registered; research variant not registered |
| `data/prices/inputs/historical_fertilizer_costs-toy.csv` | Price data | NOT in registry (no `prices_inputs` section exists) |

---

## 2. Hardcoded Values Report

### 2.1 simulation.py — Simulation Engine

| File:Line | Value | What It Represents | Priority | Recommendation |
|-----------|-------|--------------------|----------|----------------|
| simulation.py:31 | `0.05` | `DEFAULT_GW_MAINTENANCE_PER_M3` — groundwater O&M cost per m3 | HIGH | Move to `data/parameters/costs/operating_costs-toy.csv` or `equipment/water_treatment-toy.csv` |
| simulation.py:174 | `0.005` | PV degradation rate (0.5%/yr mono-Si) | MEDIUM | Load from `equipment/pv_systems-toy.csv` (column may already exist) |
| simulation.py:203 | `0.2` | `conveyance_kwh_per_m3` fallback — pipe energy | MEDIUM | Already in settings.yaml; fallback should reference config not hardcode |
| simulation.py:567 | `0.5` | Initial battery SOC (50%) | MEDIUM | Load from `equipment/batteries-toy.csv` or scenario YAML |
| simulation.py:568 | `0.10` | Battery SOC minimum (10%) | HIGH | Load from `equipment/batteries-toy.csv` |
| simulation.py:569 | `0.90` | Battery SOC maximum (90%) | HIGH | Load from `equipment/batteries-toy.csv` |
| simulation.py:570-571 | `0.95` | Battery charge/discharge efficiency | HIGH | Load from `equipment/batteries-toy.csv` |
| simulation.py:573 | `0.30` | Generator minimum load fraction | HIGH | Load from `equipment/generators-toy.csv` |
| simulation.py:574 | `0.06` | Generator SFC coefficient a (Willans line) | HIGH | Load from `equipment/generators-toy.csv` |
| simulation.py:575 | `0.20` | Generator SFC coefficient b (Willans line) | HIGH | Load from `equipment/generators-toy.csv` |
| simulation.py:639 | `0.005` | PV degradation rate (duplicate of line 174) | MEDIUM | Same as above — centralize |
| simulation.py:642 | `{"low": 0.95, "medium": 0.90, "high": 0.85}` | Agri-PV shading factors by panel density | HIGH | Add to `equipment/pv_systems-toy.csv` as `shading_factor` column |

### 2.1b state.py — Dataclass Defaults (duplicates of simulation.py values)

These duplicate the simulation.py values as dataclass field defaults. Once simulation.py reads from CSVs, these become structural fallbacks.

| File:Line | Value | What It Represents | Priority | Recommendation |
|-----------|-------|--------------------|----------|----------------|
| state.py:355 | `0.5` | EnergyState default battery SOC | MEDIUM | Will resolve when simulation.py externalized |
| state.py:356-357 | `0.10, 0.90` | EnergyState default SOC min/max | HIGH | Same as simulation.py:568-569 |
| state.py:358 | `0.95` (x2) | EnergyState default charge/discharge efficiency | HIGH | Same as simulation.py:570-571 |
| state.py:363 | `0.30` | EnergyState default generator min load | HIGH | Same as simulation.py:573 |
| state.py:364-365 | `0.06, 0.20` | EnergyState default generator SFC a, b | HIGH | Same as simulation.py:574-575 |

### 2.1c data_loader.py — Hardcoded Crop Lists

| File:Line | Value | What It Represents | Priority | Recommendation |
|-----------|-------|--------------------|----------|----------------|
| data_loader.py:684,689,709 | `["tomato","potato","onion","kale","cucumber"]` | Crop list for loading irrigation, yield, and price data | HIGH | Derive from `data_registry.yaml` crop entries; currently adding a crop requires code changes in 3 places |

### 2.2 calculations.py — Derived Calculations

| File:Line | Value | What It Represents | Priority | Recommendation |
|-----------|-------|--------------------|----------|----------------|
| calculations.py:235 | `0.3` | Default horizontal distance to wells (km) | MEDIUM | Derive from scenario config or new parameter |
| calculations.py:236 | `0.1` | Default pipe diameter (m) | MEDIUM | Move to equipment parameter file |
| calculations.py:237 | `0.60` | Default pump efficiency | HIGH | Move to `data/parameters/water/pump_equipment_parameters.csv` (currently missing) |
| calculations.py:262 | `1025` | Brackish water density (kg/m3) | LOW | Acceptable as constant but differs from pure water (1000) — document the distinction |
| calculations.py:264 | `0.02` | PVC pipe friction factor | LOW | Standard value; acceptable as constant |
| calculations.py:362 | `0.3` | Well-to-treatment distance coefficient | MEDIUM | Document derivation or make configurable |
| calculations.py:366 | `0.4` | Treatment-to-farm distance coefficient | MEDIUM | Document derivation or make configurable |
| calculations.py:492 | `0.90` | Equipment availability (90% uptime) | MEDIUM | Move to equipment parameter files |
| calculations.py:708-713 | dict | `FINANCING_PROFILE_DEFAULTS` — 6 profiles with rates, terms | HIGH | Fallback for CSV load failure. Already loads from CSV when available, but fallback values should stay synchronized with CSV |
| calculations.py:716 | `15` | Default depreciation years | MEDIUM | Move to `economic/equipment_lifespans-toy.csv` |
| calculations.py:778-788 | dict | `DEFAULT_CAPEX_OPEX` — capital costs and O&M percentages for all infrastructure types | HIGH | Fallback lookup table; should load from `costs/capital_costs-*.csv` and `costs/operating_costs-*.csv` |
| calculations.py:821 | `3.50` | Egyptian agricultural labor rate (USD/hr) | HIGH | Load from `labor/labor_wages-toy.csv` |
| calculations.py:823 | `280` | Working days per year | MEDIUM | Move to labor parameters |
| calculations.py:827 | `200` | Base field hours per hectare per year | HIGH | Load from `labor/labor_requirements-toy.csv` |
| calculations.py:831-835 | dict | `LABOR_CROP_MULTIPLIERS` — crop-specific labor factors | HIGH | Move to `labor/labor_requirements-toy.csv` (per-crop column) |
| calculations.py:839 | `0.02` | Processing labor hours per kg | HIGH | Load from `labor/labor_requirements-toy.csv` |
| calculations.py:842-847 | values | Maintenance labor hours per infrastructure unit (6 values) | HIGH | Move to `labor/labor_requirements-toy.csv` or `equipment/*` files |
| calculations.py:850 | `0.05` | Admin labor overhead fraction (5%) | MEDIUM | Move to `labor/labor_requirements-toy.csv` |
| calculations.py:936 | `3.0` | Harvest labor multiplier | MEDIUM | Move to `labor/labor_requirements-toy.csv` |

### 2.3 Policy Files — Decision Thresholds

| File:Line | Value | What It Represents | Priority | Recommendation |
|-----------|-------|--------------------|----------|----------------|
| crop_policies.py:92 | `0.80` | Deficit irrigation fraction (default) | MEDIUM | Already a constructor parameter; document in scenario YAML |
| crop_policies.py:101 | `0.9` | Late season deficit multiplier (0.80 × 0.9 = 0.72) | MEDIUM | Make configurable alongside deficit_fraction |
| crop_policies.py:133-140 | `40, 35, 20` | Temperature thresholds for weather_adaptive irrigation (C) | HIGH | Move to crop parameters or policy config in YAML |
| crop_policies.py:134-141 | `1.15, 1.05, 0.85` | Irrigation multipliers for temp thresholds | HIGH | Move to crop parameters or policy config in YAML |
| food_policies.py:108-111 | fractions | `preserve_maximum` fixed splits (20/10/35/35%) | MEDIUM | Make configurable via scenario YAML |
| food_policies.py:128-131 | fractions | `balanced` fixed splits (50/20/15/15%) | MEDIUM | Make configurable via scenario YAML |
| food_policies.py:149-154 | dict | `REFERENCE_PRICES` — per-crop reference farmgate prices (USD/kg) | HIGH | Load from price data files (historical averages) rather than hardcoding |
| food_policies.py:160 | `0.80` | Price threshold for market_responsive policy trigger | MEDIUM | Make configurable |
| market_policies.py:96 | `1.20` | `hold_for_peak` price threshold multiplier | MEDIUM | Already a constructor param; exposed in YAML |
| market_policies.py:158 | `1.0, 5.0, 0.2, 1.0` | Adaptive sigmoid parameters (midpoint, steepness, min_sell, max_sell) | MEDIUM | Already constructor params; could document in YAML |
| energy_policies.py:121 | `0.20` | Microgrid battery reserve fraction (20%) | HIGH | Move to scenario YAML `energy_system.battery` |
| energy_policies.py:148 | `0.20` | Renewable_first battery reserve (20%) | HIGH | Same as above |
| energy_policies.py:182-199 | `0.10, 0.15` | Cost_minimize battery reserve fractions | MEDIUM | Context-dependent; make configurable |
| economic_policies.py:74 | `3.0` | Balanced_finance reserve target months | MEDIUM | Already in YAML `community_policy_parameters` |
| economic_policies.py:166 | `6.0` | Risk_averse minimum reserve months | MEDIUM | Already in YAML `community_policy_parameters` |

### 2.4 validation.py / loader.py — Inline Lookup Tables and Fallback Defaults

| File:Line | Value | What It Represents | Priority | Recommendation |
|-----------|-------|--------------------|----------|----------------|
| validation.py:122 | `{"low": 0.30, "medium": 0.50, "high": 0.80}` | PV density coverage fractions | HIGH | Load from `equipment/pv_systems-toy.csv` — triplicated across 3 files |
| loader.py:368 | `{"low": 0.30, "medium": 0.50, "high": 0.80}` | PV density coverage fractions (duplicate) | HIGH | Same as above — centralize to one location |
| loader.py:403 | `28.0` | Default PV tilt angle (degrees) fallback | MEDIUM | Acceptable fallback; matches Sinai latitude |
| loader.py:406 | `4.0` | Default PV height above ground (m) | MEDIUM | **Mismatch**: settings.yaml uses `3` m; fallback says `4` m — reconcile |
| loader.py:590 | `0.75` | Default agricultural subsidized water price (USD/m3) | MEDIUM | Consistent with settings.yaml — acceptable fallback |
| loader.py:591 | `1.20` | Default agricultural unsubsidized water price (USD/m3) | MEDIUM | **Mismatch**: settings.yaml uses `0.75`; fallback says `1.20` — reconcile |
| loader.py:602 | `0.45` | Default domestic subsidized water price (USD/m3) | MEDIUM | Acceptable fallback for Egyptian tiered rate approximation |
| loader.py:631-640 | `0.12, 0.15, 0.10, 0.15` | Default electricity prices (4 regime variants) | MEDIUM | All consistent with settings.yaml — acceptable fallbacks |

### 2.5 validation_plots.py / notebook_plotting.py — Visualization Constants

| File:Line | Value | What It Represents | Priority | Recommendation |
|-----------|-------|--------------------|----------|----------------|
| validation_plots.py:327-331 | dict | PV performance model params (temp_coefficient=-0.004, temp_reference_c=25, system_losses=0.15) | MEDIUM | Load from `equipment/pv_systems-toy.csv` to avoid desync with generation scripts |
| validation_plots.py:332-336 | dict | PV density temperature adjustments for validation recalculation | MEDIUM | Load from data files to stay synchronized |
| validation_plots.py:345 | `1.05` | PV tilt factor (fixed tilt enhancement over horizontal) | MEDIUM | Add to `equipment/pv_systems-toy.csv` as `tilt_factor` column |
| validation_plots.py:479-483 | values | Battery validation params (capacity=200, SOC min/max, efficiencies) | MEDIUM | Once simulation.py reads from CSV, validation should read from same source |
| notebook_plotting.py:371 | `range(2015, 2025)` | Hardcoded year range for price CV calculation | MEDIUM | Derive from scenario start/end dates |

### 2.6 monte_carlo.py — Default Stochastic Parameters

| File:Line | Value | What It Represents | Priority | Recommendation |
|-----------|-------|--------------------|----------|----------------|
| monte_carlo.py:27-38 | dict | `DEFAULT_CV_RANGES` — 10 coefficient of variation values for price/yield volatility | MEDIUM | Move to new CSV `data/parameters/economic/monte_carlo_defaults-toy.csv` or add to scenario YAML |
| monte_carlo.py:75 | `0.5` | Price multiplier floor | LOW | Document rationale; acceptable as safety bound |
| monte_carlo.py:96 | `0.1` | Yield factor floor | LOW | Document rationale; acceptable as safety bound |

---

## 3. Summary

### Missing Data
- **7 missing data files** that block planned calculations (salinity tolerance, pump parameters, generator parameters, processing equipment path, transport parameters, community labor supply, fertilizer research data)
- **3 missing documentation files** referenced in calculations.md (Egyptian pricing research docs, microclimate research plan)
- **1 resolved planned file** (equipment_lifespans exists as `-toy` variant; planned table outdated)
- **1 partial** (rolling average prices computed at runtime, not pre-stored)
- **8 filename/path discrepancies** between docs and actual files — docs need updating

### Hardcoded Values (53 findings across 12 files)

- **20 HIGH priority** — directly affect simulation output and should be externalized
- **27 MEDIUM priority** — reasonable defaults but should be configurable
- **6 LOW priority** — stable/universal values where externalizing adds complexity without benefit

### Key Mismatches Discovered (all resolved 2026-02-18)

- ~~**loader.py:406** defaults PV height to `4.0` m but settings.yaml specifies `3` m~~ — fixed
- ~~**loader.py:591** defaults unsubsidized ag water price to `1.20` USD/m3 but settings.yaml uses `0.75`~~ — fixed
- ~~**PV density coverage** dict triplicated across validation.py, loader.py, and calculations.py~~ — centralized to `load_pv_density_coverage()` reading from CSV

### Recommended Actions (prioritized)

1. **~~Externalize battery and generator parameters~~** — RESOLVED 2026-02-18. Battery SOC/efficiency params loaded from `batteries-toy.csv`, generator Willans line coefficients from `generators-toy.csv`. PV degradation rate centralized from `pv_systems-toy.csv`. Shading factors moved to CSV. `data_loader.py` accessor methods added.

2. **~~Externalize labor constants~~** — RESOLVED 2026-02-18. 16 labor constants externalized to `labor_requirements-toy.csv` (17 new rows) and `labor_wages-toy.csv` (1 new row). `calculations.py` loads via cached `_load_labor_params()`.

3. **~~Centralize PV density coverage lookup~~** — RESOLVED 2026-02-18. Shared `load_pv_density_coverage()` in `data_loader.py` reads from `pv_systems-toy.csv`. Replaced inline dicts in `validation.py` and `loader.py`. (`calculations.py` already read from CSV.)

4. **~~Derive crop list from registry~~** — RESOLVED 2026-02-18. `derive_crop_list_from_registry()` in `data_loader.py` extracts crop names from registry irrigation section. All 3 hardcoded lists replaced.

5. **~~Create `crop_salinity_tolerance.csv`~~** — RESOLVED 2026-02-18. Created `data/parameters/crops/crop_salinity_tolerance-toy.csv` with FAO-29 values for all 5 crops. Registered in data registry under `crops.salinity_tolerance`.

6. **~~Fix loader.py fallback mismatches~~** — RESOLVED 2026-02-18. PV height fallback corrected from 4.0 to 3.0 m. Unsubsidized ag water price fallback corrected from 1.20 to 0.75 USD/m3. Comments added.

7. **~~Externalize crop policy temperature thresholds~~** — RESOLVED 2026-02-18. `WeatherAdaptive.__init__()` now accepts 6 configurable parameters (3 thresholds, 3 multipliers) with current values as defaults.

8. **~~Externalize food policy reference prices~~** — RESOLVED 2026-02-18. `MarketResponsive.reference_prices` now lazily loads median prices from historical CSV data via registry. Falls back to hardcoded values with stderr warning if data unavailable.

9. **~~Fix 8 filename discrepancies~~** — RESOLVED 2026-02-18. Updated 8+ stale file paths in `calculations.md` and `data.md` to match actual filenames on disk.

10. **~~Add fertilizer costs to data registry~~** — RESOLVED 2026-02-18. New `prices_inputs` section added with `fertilizer_costs` key. Registry validates clean (76/76 files found).
