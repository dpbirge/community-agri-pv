# Stress Test Report

## Summary
- Tests run: 67 (across 51 test configurations, some run under multiple supply regimes)
- Passed: 61
- Failed (crash): 3 (WS3, WS6, X4)
- Warnings: 3 (W4, ES7, ES8)

## Results Table

### Water Policy Tests (W1-W13)

| Test | Regime | Status | Total Cost | Deficit m3 | Deficit Days | Notes |
|------|--------|--------|-----------|-----------|-------------|-------|
| W1 minimize_cost | oversupply | PASS | 1,499,418 | 0 | 0 | Cheapest across regimes |
| W1 minimize_cost | balanced | PASS | 1,211,558 | 594,096 | 1,861 | Structural deficit from treatment bottleneck |
| W1 minimize_cost | undersupply | PASS | 297,701 | 2,154,901 | — | Severe supply constraint |
| W2 minimize_treatment | oversupply | PASS | 1,501,574 | 0 | 0 | Least treatment volume |
| W2 minimize_treatment | balanced | PASS | 1,214,471 | 594,096 | 1,861 | More municipal blending |
| W2 minimize_treatment | undersupply | PASS | 319,020 | 2,154,901 | — | |
| W3 minimize_draw | oversupply | PASS | 1,501,574 | 0 | 0 | Identical to W2 (see findings) |
| W3 minimize_draw | balanced | PASS | 1,214,471 | 594,096 | 1,861 | Identical to W2 |
| W3 minimize_draw | undersupply | PASS | 319,020 | 2,154,901 | — | Identical to W2 |
| W4 max_treatment_eff | balanced | WARNING | 968,692 | 1,086,310 | — | 70-85% target unreachable (well throughput limit) |
| W5 look_ahead_on | balanced | PASS | 1,211,558 | 594,096 | 1,861 | Cap never hit; look-ahead has no effect |
| W6 look_ahead_off | balanced | PASS | 1,211,558 | 594,096 | 1,861 | Identical to W5 |
| W7 tight_muni_cap | balanced | PASS | 1,211,558 | 594,096 | 1,861 | Cap has no effect (muni never used for irrigation) |
| W8 no_muni_cap | balanced | PASS | 1,211,558 | 594,096 | 1,861 | Identical to W1-balanced |
| W9 groundwater_cap | balanced | PASS | 186,733 | 2,815,699 | 5,194 | Most disruptive single param change (+374% deficit) |
| W10 prefill_disabled | balanced | PASS | 966,659 | 1,086,310 | 3,200 | Nearly doubles deficit vs prefill enabled |
| W11 prefill_long_horizon | balanced | PASS | 1,212,107 | 594,096 | 1,861 | 7-day look-ahead, marginal prefill increase |
| W12 dynamic_irrigation | balanced | PASS | 1,211,558 | 594,096 | 1,861 | Dynamic mode works; same supply-side behavior |
| W13 static_deficit_60 | oversupply | PASS | 1,499,418 | 0 | 0 | Demand not reduced (see findings) |

### Energy Policy Tests (E1-E13)

| Test | Regime | Status | Total Cost | Renewable kWh | Grid Import | Generator | Deficit kWh | Curtailed kWh |
|------|--------|--------|-----------|--------------|-------------|-----------|-------------|---------------|
| E1 minimize_cost | oversupply | PASS | $0 | 361,090,430 | 0 | 0 | 0 | 351,932,897 |
| E1 minimize_cost | balanced | PASS | $0 | 173,097,889 | 0 | 0 | 0 | 165,393,830 |
| E1 minimize_cost | undersupply | PASS | $0 | 147,682,829 | 0 | 0 | 0 | 143,298,671 |
| E2 minimize_grid | all | PASS | $0 | (same) | 0 | 0 | 0 | (same) |
| E3 minimize_gen | all | PASS | $0 | (same) | 0 | 0 | 0 | (same) |
| E4 full_grid | balanced | PASS | $0 | 173,097,889 | 0 | 0 | 0 | 0 |
| E5 net_metering | oversupply | PASS | $0 | 361,090,430 | 0 | 0 | 0 | 0 |
| E6 feed_in_tariff | oversupply | PASS | -$44,343,545 | 361,090,430 | 0 | 0 | 0 | 0 |
| E7 self_consumption | oversupply | PASS | $0 | 361,090,430 | 0 | 0 | 0 | 351,932,897 |
| E8 limited_grid | balanced | PASS | $0 | 173,097,889 | 0 | 0 | 0 | 165,393,830 |
| E9 off_grid | undersupply | PASS | $0 | 147,682,829 | 0 | 0 | 0 | 139,978,770 |
| E10 no_battery | balanced | PASS | $0 | 173,097,889 | 0 | 0 | 0 | 165,393,830 |
| E11 no_generator | balanced | PASS | $0 | 173,097,889 | 0 | 0 | 0 | 165,393,830 |
| E12 no_bat_no_gen | undersupply | PASS | $0 | 147,682,829 | 0 | 0 | 0 | 139,978,770 |
| E13a look_ahead_on | balanced | PASS | $0 | 173,097,889 | 0 | 0 | 0 | 165,393,830 |
| E13b look_ahead_off | balanced | PASS | $0 | 173,097,889 | 0 | 0 | 0 | 165,393,830 |

### Water System Config Tests (WS1-WS10)

| Test | Status | Total Cost | Treatment m3 | Municipal m3 | GW m3 | Deficit m3 | Deficit Days |
|------|--------|-----------|-------------|-------------|-------|-----------|-------------|
| WS1 single_well | PASS | 733,671 | 2,061,236 | 154,882 | 2,710,216 | 594,096 | 1,861 |
| WS2 high_tds_only | PASS | 1,281,063 | 3,245,239 | 154,882 | 3,374,069 | 594,096 | 1,861 |
| WS3 no_treatment | FAIL | — | — | — | — | — | — |
| WS4 small_treatment | PASS | 794,864 | 1,768,346 | 242,259 | 1,873,198 | 1,499,617 | 4,103 |
| WS5 large_treatment | PASS | 1,211,558 | 3,103,353 | 154,882 | 3,266,599 | 594,096 | 1,861 |
| WS6 no_tank | FAIL | — | — | — | — | — | — |
| WS7 tiny_tank | PASS | 490,777 | 1,021,313 | 154,882 | 1,081,258 | 2,154,901 | 4,985 |
| WS8 huge_tank | PASS | 1,538,138 | 4,039,238 | 202,349 | 4,241,364 | 0 | 0 |
| WS9 expensive_muni | PASS | 1,908,527 | 3,103,353 | 154,882 | 3,266,599 | 594,096 | 1,861 |
| WS10 low_tds_muni | PASS | 1,211,558 | 3,103,353 | 154,882 | 3,266,599 | 594,096 | 1,861 |

### Energy System Config Tests (ES1-ES10)

| Test | Status | Total Solar kWh | Total Wind kWh | Curtailed kWh | Notes |
|------|--------|----------------|---------------|---------------|-------|
| ES1 solar_only | PASS | 163,818,901 | 0 | 156,114,843 | Clear seasonal pattern |
| ES2 wind_only | PASS | 142,218,816 | 9,278,987 | 143,793,745 | Solar is agri-PV only |
| ES3 minimal_solar | PASS | 143,185,794 | 9,278,987 | 144,760,723 | Agri-PV dominates |
| ES4 large_solar | PASS | 625,707,735 | 9,278,987 | 627,282,664 | 98.8% curtailed |
| ES5 single_small_turb | PASS | 163,818,901 | 314,562 | 156,429,404 | Negligible wind |
| ES6 many_large_turbs | PASS | 163,818,901 | 37,792,729 | 193,907,572 | Wind less seasonal than solar |
| ES7 tiny_battery | WARNING | 163,818,901 | 9,278,987 | 165,393,735 | Config capacity_kwh ignored |
| ES8 huge_battery | WARNING | 163,818,901 | 9,278,987 | 165,393,735 | Config capacity_kwh ignored |
| ES9 large_generator | PASS | 163,818,901 | 9,278,987 | 165,393,830 | Generator never fires |
| ES10 no_renewables | PASS | 142,218,816 | 0 | 134,514,758 | Agri-PV still present |

### Cross-System Tests (X1-X5)

| Test | Status | Water Deficit m3 | Energy Deficit kWh | Notes |
|------|--------|-----------------|-------------------|-------|
| X1 water_energy_coupling | PASS | 594,096 | 0 | Water energy demand correctly reflected in energy balance |
| X2 oversupply_both | PASS | 0 | 0 | Zero deficits everywhere |
| X3 undersupply_both | PASS | 2,154,901 | 0 | Graceful degradation; no NaN or crashes |
| X4 no_treatment_solar | FAIL | — | — | Crash: KeyError 'treatment' |
| X5 huge_farm_minimal | PASS | 5,363,900 | 0 | 80% unmet water demand; no crashes |

## Failures (detailed)

### WS3 — no_treatment
- **What failed**: Simulation crashed at startup
- **Expected**: Run without treatment, using only raw groundwater and municipal
- **Actual**: `KeyError: 'treatment'` at `src/water.py` line 1405
- **Root cause**: `compute_water_supply()` unconditionally accesses `system['treatment']['goal_output_tds_ppm']`. There is no guard for absent treatment block. 15 access sites across 6+ functions assume treatment exists.

### WS6 — no_tank
- **What failed**: Simulation crashed at startup
- **Expected**: Run without storage, delivering water directly to demand
- **Actual**: `KeyError: 'storage'` at `src/water.py` line 1418
- **Root cause**: `compute_water_supply()` unconditionally accesses `system['storage']`. No tankless dispatch path exists.

### X4 — no_treatment_solar_only
- **What failed**: Same crash as WS3 (treatment block absent)
- **Expected**: Combined stress of no-treatment + solar-only energy
- **Actual**: `KeyError: 'treatment'` — identical root cause

## Bugs Found

### BUG 1: Missing treatment-absent handling (src/water.py)
- **Location**: Line 1405 and 15 downstream access sites
- **Impact**: WS3, X4 crash — no-treatment is a valid physical scenario
- **Fix**: Guard all `system['treatment']` accesses with conditional checks

### BUG 2: Missing storage-absent handling (src/water.py)
- **Location**: Line 1418 and downstream
- **Impact**: WS6 crash — tankless (direct-to-field) irrigation is a valid configuration
- **Fix**: Guard `system['storage']` accesses; provide zero-capacity passthrough fallback

### BUG 3: Battery capacity_kwh config ignored (src/energy_balance.py)
- **Location**: `_build_battery_specs()` ~line 157
- **Impact**: ES7 (10 kWh) and ES8 (2000 kWh) both used 200 kWh from equipment CSV
- **Actual**: `row['capacity_kwh']` is read from `batteries-toy.csv`, not from `energy_system.yaml`
- **Fix**: Override CSV value with config value when `battery.capacity_kwh` is set

### BUG 4: Generator rated_capacity_kw config ignored (src/energy_balance.py)
- **Location**: `_build_generator_specs()` ~line 189
- **Impact**: ES9 (500 kW config) used 100 kW from equipment CSV
- **Actual**: `row['capacity_kw']` from `generators-toy.csv` used; config value ignored
- **Fix**: Override CSV value with config value when `generator.rated_capacity_kw` is set

### BUG 5: deficit_60 does not reduce irrigation demand (src/irrigation_demand.py)
- **Location**: `_load_daily_etc()` line 86
- **Impact**: W13 demand identical to full_eto despite deficit_60 policy
- **Actual**: Function reads `etc_mm` (crop need, policy-independent) not `water_applied_mm` (policy-dependent)
- **Design question**: Is this intentional? If deficit policies should reduce what the water system is asked to deliver, `_load_daily_etc()` should read `water_applied_mm` for non-full_eto policies.

## Observations

### Strategy Differentiation
- **W1 < W2 = W3 cost** across all regimes — minimize_cost is confirmed cheapest.
- **W2 ≡ W3**: minimize_treatment and minimize_draw produce identical results in all regimes. Both converge to the same municipal/groundwater blending solution when the TDS constraint dominates and the municipal irrigation cap is not binding. The strategies would diverge only when the municipal cap is actually reached for irrigation-portion water.
- **E1 ≡ E2 ≡ E3**: All energy strategies are degenerate because renewable generation (including agri-PV) massively exceeds demand in every baseline regime. No grid import, generator, or battery dispatch is ever triggered.

### Agri-PV Dominance
The farm profile's agri-PV fields generate ~142M kWh/year of solar energy (12-33x community demand). This single source exceeds demand even in the "undersupply" energy regime, making it impossible to create energy-deficit scenarios via `energy_system.yaml` alone. Tests ES2, ES3, ES10, E9, E12, X1, X3 all show zero energy deficit despite being designed to test undersupply behavior. **Recommendation**: Create an alternative farm profile with `condition: openfield` (no PV) for energy-deficit stress tests.

### Water System Sensitivity
- **Tank sizing is the dominant factor**: WS8 (5000 m3 tank) is the only test with zero water deficit. WS7 (50 m3 tank) has the worst deficit (4,985 days). Treatment throughput is secondary.
- **Groundwater cap is the most disruptive single parameter**: W9 (200 m3/month cap) increases deficit by 374%.
- **Prefill matters**: Disabling prefill (W10) nearly doubles deficit days (1,861 → 3,200).

### Municipal Cap Scoping
The `municipal.monthly_cap_m3` in water policy applies only to irrigation-portion municipal water (`municipal_to_tank_m3`), not community building water (`municipal_community_m3`). Under `minimize_cost`, municipal is never used for irrigation (groundwater is cheaper), so W5/W6/W7/W8 all show `muni_cap_used_month_m3 = 0` even though total municipal consumption exceeds the cap. This is correct behavior but may be surprising.

### treatment_utilization_pct Always Zero
This output column is present but always 0.0 in all dispatch runs. It appears to be populated only during the `optimize_water_system()` / sizing flow, not during `compute_water_supply()` dispatch.

### E8/E13 Require grid_connection Change
The `_validate_grid_config()` function in `src/energy_balance.py` rejects `grid.mode: limited_grid` when `grid_connection` is `full_grid`. The energy system YAML must set `grid_connection: limited_grid` for these tests to run.

### Suggestions for Additional Test Coverage
1. **Openfield-only farm profile** for energy tests — removes agri-PV to create genuine energy-deficit scenarios
2. **minimize_draw + near-binding municipal cap** — would exercise the look-ahead mechanism and differentiate W2 from W3
3. **Larger wells or higher treatment throughput** for W4 — to test the maximize_treatment_efficiency sweet spot with adequate supply
4. **Time-of-use tariff tests** — not covered; would require tariff schedule data
5. **Multi-system water tests** — current tests use single water system; multi-system would test routing logic
