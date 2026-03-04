# Stress Test Report

## Summary
- Tests run: 59 (across 7 phases)
- Passed: 59
- Failed: 0
- Warnings: 5 (behavioral observations requiring follow-up)

## Results Table

### Phase 2: Water Policy Tests (W1-W13)

| Test | Status | Key Metrics | Notes |
|------|--------|-------------|-------|
| W1 minimize_cost (oversupply) | PASS | cost=$796,649, deficit=0 m3 | Cheapest sources first; GW+treatment dominant |
| W1 minimize_cost (balanced) | PASS | cost=$792,018, deficit=2,686 m3 | Lowest cost among W1-W3 confirmed |
| W1 minimize_cost (undersupply) | PASS | cost=$289,527, deficit=710,902 m3 | Large deficit from constrained supply |
| W2 minimize_treatment (oversupply) | PASS | cost=$799,347, treatment=0 m3 | Zero treatment; 100% municipal |
| W2 minimize_treatment (balanced) | PASS | cost=$797,895, treatment=0 m3 | Zero treatment confirmed |
| W2 minimize_treatment (undersupply) | PASS | cost=$443,715, treatment=0 m3 | All municipal, large deficit |
| W3 minimize_draw (oversupply) | PASS | cost=$799,347, municipal=1,598,696 m3 | Identical to W2 (see observations) |
| W3 minimize_draw (balanced) | PASS | cost=$797,895, municipal=1,595,792 m3 | Identical to W2 |
| W3 minimize_draw (undersupply) | PASS | cost=$443,715, deficit=710,879 m3 | Identical to W2 |
| W4 maximize_treatment_efficiency | PASS | cost=$730,898, deficit=108,528 m3 | Treatment utilization capped at 46% (see warning) |
| W5 look_ahead_on (cap=500) | PASS | cost=$724,081, deficit=137,648 m3 | Municipal spread across month |
| W6 look_ahead_off (cap=500) | PASS | cost=$725,138, deficit=134,858 m3 | Cap consumed early; 3 months exceeded cap (see warning) |
| W7 tight_municipal_cap (50) | PASS | cost=$713,336, deficit=159,259 m3 | Cap hit; deficit increases 16% vs W5 |
| W8 no_municipal_cap | PASS | cost=$792,018, deficit=2,686 m3 | Municipal=161,283 m3; deficit drops 98% vs W7 |
| W9 groundwater_cap (200) | PASS | cost=$830,620, deficit=2,504 m3 | GW capped; system pivots to municipal |
| W10 prefill_disabled | PASS | cost=$726,188, deficit=108,528 m3 | 41x more deficit than W11 (prefill enabled) |
| W11 prefill_long_horizon (7d) | PASS | cost=$791,463, deficit=2,659 m3 | 85% fewer deficit days than W5 (3d horizon) |
| W12 dynamic_irrigation | PASS | cost=$792,018, deficit=2,686 m3 | FAO yield computed from ETa/ETc ratios |
| W13 static_deficit_60 | PASS | cost=$526,547, deficit=0 m3 | 40% demand reduction eliminates all deficit |

### Phase 3: Energy Policy Tests (E1-E13)

| Test | Status | Key Metrics | Notes |
|------|--------|-------------|-------|
| E1 minimize_cost (oversupply) | PASS | cost=$0, grid=0, gen=0 | Renewables cover 100% |
| E1 minimize_cost (balanced) | PASS | cost=$0, grid=0, gen=0 | Renewables cover 100% |
| E1 minimize_cost (undersupply) | PASS | cost=$36,264, gen=98,497 kWh | Off-grid; generator fills gaps |
| E2 minimize_grid (oversupply) | PASS | cost=$0, grid=0, gen=0 | Identical to E1 (no deficit) |
| E2 minimize_grid (balanced) | PASS | cost=$0, grid=0, gen=0 | Identical to E1 |
| E2 minimize_grid (undersupply) | PASS | cost=$36,264, gen=98,497 kWh | Identical to E1 (off-grid, only generator) |
| E3 minimize_generator (oversupply) | PASS | cost=$0, grid=0, gen=0 | Identical to E1 |
| E3 minimize_generator (balanced) | PASS | cost=$0, grid=0, gen=0 | Identical to E1 |
| E3 minimize_generator (undersupply) | PASS | cost=$36,264, gen=98,497 kWh | Identical to E1 (see observations) |
| E4 full_grid | PASS | export=166,892,110 kWh, curtail=0 | Unlimited import/export |
| E5 net_metering | PASS | export=755,836,926 kWh | Net exporter every month; $0 cost |
| E6 feed_in_tariff | PASS | revenue=$95,235,453 | Export at commercial_small FIT rate |
| E7 self_consumption | PASS | curtailed=755,836,926 kWh | Zero export; all surplus curtailed |
| E8 limited_grid (cap=500) | PASS | curtailed=24,338,420 kWh | Cap never triggered (renewables cover demand) |
| E9 off_grid | PASS | grid=0, gen=98,497 kWh | Off-grid enforced; generator backstops |
| E10 no_battery | PASS | charge=0, discharge=0 | Battery columns zero throughout |
| E11 no_generator | PASS | generator=0 | Generator column zero throughout |
| E12 no_battery_no_generator | PASS | deficit=98,497 kWh (1,050 days) | Only renewables; deficit on low-sun days |
| E13 look_ahead=true | PASS | grid=25,744 kWh, gen=72,753 kWh | Cap spread evenly; 17 months near cap |
| E13 look_ahead=false | PASS | grid=39,047 kWh, gen=59,450 kWh | Cap front-loaded; 60 months at limit |

### Phase 4: Water System Tests (WS1-WS10)

| Test | Status | Key Metrics | Notes |
|------|--------|-------------|-------|
| WS1 single_well | PASS | cost=$1,022,219, treatment=8,046,393 m3 | Lowest cost; low-TDS well is cheapest |
| WS2 high_tds_only | PASS | cost=$1,660,955, treatment=8,914,242 m3 | All GW requires treatment; TDS exceedance on some days |
| WS3 no_treatment | PASS | cost=$1,595,790, GW=0 m3 | Dispatch rejects high-TDS GW; 100% municipal |
| WS4 small_treatment (5 m3/hr) | PASS | cost=$1,610,000, municipal=800,867 m3 | Treatment bottleneck; 3.6x more municipal than WS1 |
| WS5 large_treatment (200 m3/hr) | PASS | cost=$1,584,036, treatment=28,524,501 m3 | Treatment never bottlenecked |
| WS6 no_tank | PASS | cost=$2,178,575, deficit=0 m3 | Virtual unbounded tank; high municipal draw |
| WS7 tiny_tank (50 m3) | PASS | cost=$469,759, deficit=713,006 m3 | 3,827 deficit days (70%); severe constraint |
| WS8 huge_tank (5000 m3) | PASS | cost=$839,169, deficit=0 m3 | Zero deficit; tank buffers peak demand |
| WS9 expensive_municipal ($5/m3) | PASS | cost=$2,214,762, municipal=316,165 m3 | Strategy avoids municipal but forced draws cost 10x |
| WS10 low_tds_municipal (50 ppm) | PASS | cost=$792,058, treatment=1,711,770 m3 | TDS quality doesn't change dispatch mix |

### Phase 5: Energy System Tests (ES1-ES10)

| Test | Status | Key Metrics | Notes |
|------|--------|-------------|-------|
| ES1 solar_only | PASS | solar=21.6M kWh, wind=0 | Seasonal 1.79x summer/winter ratio |
| ES2 wind_only | PASS | solar=145M kWh (agri-PV), wind=9.3M kWh | Community solar=0; agri-PV flows through |
| ES3 minimal_solar | PASS | solar=967k kWh, grid=5.57M kWh | Heavy grid reliance confirmed |
| ES4 large_solar | PASS | solar=483M kWh, export=477M kWh | Massive oversupply; all surplus exported |
| ES5 single_small_turbine | PASS | wind=315k kWh, grid=6.23M kWh | Minimal wind; highest grid reliance |
| ES6 many_large_turbines | PASS | wind=37.8M kWh, solar=21.6M kWh | Wind-dominant (64%); less seasonal (CV 0.218 vs 0.258) |
| ES7 tiny_battery (10 kWh) | PASS | charge=2.1 kWh total | Battery fills day 1, stays full |
| ES8 huge_battery (2000 kWh) | PASS | charge=421 kWh total | Battery fills day 1; marginal difference from ES7 |
| ES9 large_generator (500 kW) | PASS | generator=0 kWh | Never activated; renewables sufficient |
| ES10 no_renewables | PASS | renewable=0, grid=6.54M kWh, cost=$496,166 | Maximum cost baseline; 100% grid |

### Phase 6: Cross-System Tests (X1-X5)

| Test | Status | Key Metrics | Notes |
|------|--------|-------------|-------|
| X1 water_energy_coupling | PASS | water_deficit=65,683 m3, energy_deficit=0 | Water energy demand routed to energy balance correctly |
| X2 oversupply_both | PASS | water_deficit=0, energy_deficit=0, export=755.8M kWh | No deficits; all surplus exported |
| X3 undersupply_both | PASS | water_deficit=1,124,951 m3, energy_deficit=0 | Graceful degradation; no crashes/NaN |
| X4 no_treatment_solar_only | PASS | water_deficit=2,504 m3, treatment=0 | No treatment block handled cleanly |
| X5 huge_farm_minimal_infra | PASS | water_deficit=3,585,331 m3 (53%), export=635.9M kWh | Extreme mismatch; agri-PV dominates energy |

### Phase 7: Farm Profile Tests (FP1-FP8)

| Test | Status | Key Metrics | Notes |
|------|--------|-------------|-------|
| FP1 all_openfield | PASS | agripv=0, renewable=30.9M kWh | Zero agri-PV confirmed |
| FP2 all_underpv_high | PASS | agripv=542.5M kWh, demand=5.4M kWh | 106x renewable/demand ratio |
| FP3 mixed_pv_densities | PASS | agripv=145M kWh, high_farm=3.9x low_farm | Density hierarchy confirmed |
| FP4 small_drip_no_pv | PASS | agripv=0, water_demand=329k m3 | Lowest water demand; system in surplus |
| FP5 large_furrow_high_demand | PASS | water_deficit=631,232 m3, agripv=0 | Furrow inefficiency drives 65% demand increase |
| FP6 single_field_underpv_high | PASS | agripv=226M kWh | Single 5 ha field; one agripv column |
| FP7 many_small_fields | PASS | agripv=48.3M kWh, 4 farm columns | 8 fields across 4 farms scale correctly |
| FP8 openfield vs heavy_pv | PASS | ETc reduction=54%, surplus_diff=543.7M kWh | Paired comparison; underpv reduces water demand |

## Failures (detailed)

No test failures occurred. All 59 simulation runs completed without crashes, NaN values, negative quantities, or balance violations.

## Observations

### 1. W2/W3 Strategy Convergence
`minimize_treatment` and `minimize_draw` produce identical outputs across all supply regimes. Both strategies avoid groundwater entirely (routing 100% to municipal) because all available well water exceeds crop TDS tolerance without treatment. The strategies converge when municipal is both TDS-compliant and sufficient to meet throughput needs. Differentiation would require a well configuration where groundwater TDS is below crop tolerance (e.g., wells at 400 ppm vs crop requirement of 510-1070 ppm).

### 2. E1/E2/E3 Strategy Non-Differentiation
All three energy dispatch strategies produce identical outputs within each supply regime. In oversupply/balanced, renewables cover 100% of demand so secondary source ordering is never invoked. In undersupply (off-grid), only the generator is available as a secondary source, so all strategies converge. A test regime with limited_grid + generator + intermittent deficits would differentiate the three strategies.

### 3. W4 Treatment Utilization Below Sweet Spot
The `maximize_treatment_efficiency` strategy targets 70-85% of rated BWRO capacity (840-1,020 m3/day for the 50 m3/hr system), but peak daily demand is only 753.6 m3/day. The strategy operates correctly but the sizing mismatch means it can never reach target utilization. Testing with a smaller BWRO (e.g., 20 m3/hr) where demand exceeds the sweet-spot floor would properly exercise this path.

### 4. Municipal Cap Overshoot with look_ahead=false (W6, W7)
With `cap_enforcement.look_ahead: false`, 3 months exceed the 500 m3 municipal cap (max 683.5 m3 in W6) and 3 months exceed the 50 m3 cap in W7. This is expected greedy-draw behavior, but if the cap is intended as a hard ceiling, the enforcement logic may need tightening for same-day overshoot scenarios.

### 5. Municipal TDS Quality Has No Effect on Dispatch (WS10)
Lowering municipal TDS from 200 ppm to 50 ppm produces identical dispatch mix and nearly identical costs under `minimize_cost`. The strategy's source selection is cost-ordered, not TDS-sensitive. This is correct behavior for the cost-minimizing strategy but worth documenting.

### 6. Balanced Energy System is Oversized for FP-O
The "balanced" energy system generates 30.9M kWh over 15 years against 6.5M kWh demand — a 4.7x surplus for the openfield farm profile. Tests E8, E10, E11, ES6-ES9 never exercise their intended deficit/dispatch paths. Battery tests (ES7/ES8) show trivial differences because the battery fills on day 1 and is never discharged. A "tight-balanced" energy system where renewable generation is ~80-120% of demand would properly stress-test these paths.

### 7. Agri-PV Dominates Energy Balance
Farm profiles with `underpv_*` fields generate energy that dwarfs community solar + wind. FP-H (12 ha underpv_high) produces 542.5M kWh agri-PV vs 30.9M kWh community renewable — a 17.5x ratio. This is architecturally correct but means any profile with significant underpv area will mask energy dispatch behavior. Using FP-O (all openfield) for energy tests is essential.

### 8. Tank Size is the Dominant Water Deficit Driver
WS7 (50 m3 tank) produces 3,827 deficit days; WS8 (5,000 m3 tank) produces 0. Treatment throughput, municipal cost, and TDS quality have secondary effects. Prefill effectiveness is also tank-dependent: W10 (prefill disabled, 200 m3 tank) has 1,136 deficit days vs W11 (7-day prefill) with 72 days.

### 9. Furrow Irrigation Creates Realistic Stress
FP5 (furrow, efficiency ~0.60) increases irrigation demand by 65% over FP1 (sprinkler, ~0.75) at comparable area, producing 631,232 m3 deficit — one of the most effective ways to stress the water system.

### 10. Underpv Reduces Crop Water Demand by 54%
FP8 paired comparison shows underpv_high reduces annual water demand from 2,045,288 m3 to 940,737 m3 — a 54% reduction from reduced solar radiation lowering crop transpiration.

## Parameter Sensitivity Rankings

**Water deficit sensitivity (most to least impactful):**
1. Tank capacity (WS7 vs WS8: 3,827 → 0 deficit days)
2. Prefill enabled/disabled (W10 vs W11: 1,136 → 72 deficit days)
3. Municipal cap (W7 vs W8: 546 → 72 deficit days)
4. Irrigation system type (FP5 furrow vs FP1 sprinkler: 631k vs 66k m3 deficit)
5. Treatment throughput (WS4 vs WS5: secondary effect)

**Energy cost sensitivity (most to least impactful):**
1. Renewable presence (ES10 no_renewables: $496k vs $0 for all others)
2. Grid mode (E6 feed_in_tariff: -$95M revenue vs E7 self_consumption: $0)
3. Farm profile PV density (FP1 vs FP2: surplus differs by 543M kWh)
4. Battery/generator availability (E12: 98,497 kWh deficit when both removed)

## Suggestions for Additional Test Coverage
1. **Tight-balanced energy regime** (~80-120% of demand) to exercise battery cycling, generator dispatch, and grid cap paths
2. **Low-TDS well configuration** (e.g., 400 ppm) to differentiate minimize_treatment from minimize_draw
3. **Seasonal farm profile** with heavy summer-only plantings to test demand correlation
4. **Multi-system water configuration** with fields on different water systems
5. **Solar degradation sweep** testing degradation rates over the 15-year horizon
