# Energy Stress Test Report

## Summary
- Tests run: 28
- Passed: 25
- Conditional pass: 2
- Failed (key check): 1
- Warnings: 0

## Results Table

### Phase 2: Energy Policy Tests (E1–E13)

| Test | Status | Farm Profile | Supply Regime | Key Metrics | Notes |
|------|--------|-------------|---------------|-------------|-------|
| E1 minimize_cost | PASS | FP-O | All three | Balanced: grid=980K kWh, gen=0, cost=$73K | Grid preferred over generator under minimize_cost |
| E2 minimize_grid_reliance | PASS | FP-O | All three | Balanced: grid=0, gen=968K kWh, cost=$164K | Clean strategy inversion vs E1 — generator before grid |
| E3 minimize_generator | PASS | FP-O | All three | Balanced: grid=980K kWh, gen=0, cost=$73K | Identical to E1 when grid uncapped; diverges only when grid restricted |
| E4 full_grid | CONDITIONAL PASS | FP-M | Balanced | grid_import=0, export=142M kWh, deficit=0 | FP-M agri-PV creates permanent 3x surplus — grid import never triggers |
| E5 net_metering | PASS | FP-H | Oversupply | export=737M kWh, revenue=$0 | Net metering credits reduce import bills, no cash payout — correct |
| E6 feed_in_tariff | PASS | FP-H | Oversupply | export=737M kWh, revenue=$59M | Export at $0.08/kWh confirmed on all 5,479 days |
| E7 self_consumption | PASS | FP-H | Oversupply | export=0, curtailed=756M kWh | No export; surplus → battery (day 1) → curtailed |
| E8 limited_grid | PASS | FP-O | Balanced | Monthly cap 500 kWh enforced (0 violations in 180 months) | Generator/battery cover when cap reached; CSV rounding artifact noted |
| E9 off_grid | PASS | FP-O | Modified undersupply | grid=0, gen=59K kWh, deficit=0 | Grid locked out; generator covers all shortfalls on 586/5,479 days |
| E10 no_battery | PASS | FP-O | Balanced | charge=0, discharge=0, grid=1,015K kWh | 35K kWh more grid than battery-enabled E11 |
| E11 no_generator | PASS | FP-O | Balanced | gen=0, fuel=0, grid=980K kWh | Battery provides modest buffering (35 MWh over 15yr) |
| E12 no_battery_no_generator | PASS | FP-O | Undersupply (off_grid) | deficit on 19.2% of days (1,050 days), all backup=0 | Deficit concentrated in winter months as expected |
| E13 grid_cap_look_ahead | PASS | FP-O | Balanced (limited_grid) | Both respect 5K kWh/mo cap; look_ahead CV=0.37 vs no_look_ahead CV=0.62 | Behavioral inversion: look_ahead uses MORE generator (+38.7%) due to daily proration |

### Phase 3: Energy System Configuration Tests (ES1–ES10)

| Test | Status | Farm Profile | Key Metrics | Notes |
|------|--------|-------------|-------------|-------|
| ES1 solar_only | PASS | FP-O | wind=0, solar=322K kWh/yr | 2.14x seasonal peak-to-trough ratio (June vs Dec) |
| ES2 wind_only | PASS | FP-D | comm_solar=0, agri-PV=9.7M kWh/yr, wind=84K kWh/yr | Agri-PV from FP-D fields correctly persists; per-density columns confirmed |
| ES3 minimal_solar | PASS | FP-O | solar=15% of demand, grid=4.3M kWh | Battery drains to soc_min day 1, stays there (grid cheaper) |
| ES4 large_solar | PASS | FP-O | solar 74x demand, curtailed=478M kWh | Curtailed every day; battery fills day 1, pinned at soc_max |
| ES5 single_small_turbine | PASS | FP-O | wind=6.1% of renewables (315K kWh) | Solar-dominated; low wind-solar correlation (r=0.27) |
| ES6 many_large_turbines | PASS | FP-O | wind 7.82x solar, curtailed=36M kWh | 84.8% of generation curtailed in self_consumption mode |
| ES7 tiny_battery | PASS | FP-O | SOC hits bounds 99.4% of days, curtailed=565K kWh | 10 kWh battery capacity-constrained; only 2.8K kWh charged over 15yr |
| ES8 huge_battery | PASS | FP-O | charge=143K kWh (51x ES7), curtailed=425K kWh (-25%) | Self-consumption ratio up 0.926→0.945; SOC bounded [400, 1900] kWh |
| ES9 large_generator | FAIL (key check) | FP-O | gen=0, grid=980K kWh | Generator never dispatches — minimize_cost + self_consumption allows grid import |
| ES10 no_renewables | PASS | FP-O | renewable=0, grid=6.54M kWh, cost=$496K | Highest cost baseline; grid supplies 100% of demand |

## Failures (detailed)

### ES9 — large_generator
- **What failed**: Generator never dispatches despite 500 kW rated capacity
- **Expected**: Generator covers deficits on many days; fuel cost dominates
- **Actual**: Generator = 0 kWh; grid import = 980,424 kWh; grid covers all deficits
- **Root cause**: `self_consumption` mode only blocks grid *export*, not import. Under `minimize_cost`, dispatch order is battery → grid → generator. Grid is always cheaper than diesel, so the generator is never reached in the dispatch queue.
- **Fix**: To exercise the generator, use `grid.mode: off_grid` or `strategy: minimize_grid_reliance`

### E4 — full_grid (conditional pass)
- **What partially failed**: `grid_import_kwh > 0` check — grid import = 0 every day
- **Expected**: Both import and export days (mixed surplus/deficit profile)
- **Actual**: FP-M with 4.5 ha of `underpv_medium` agri-PV produces minimum 3x surplus every day
- **Root cause**: Configuration pairing creates structural oversupply. Not a simulation defect.
- **Fix**: Re-run with smaller farm profile or `energy_system_undersupply` to test import path

## Observations

### Cross-Test Comparisons

**Strategy cost ranking (balanced regime, FP-O):**
| Strategy | Total Cost | Grid Import | Generator |
|----------|-----------|-------------|-----------|
| E1 minimize_cost | $73,074 | 980,424 kWh | 0 kWh |
| E3 minimize_generator | $73,074 | 980,424 kWh | 0 kWh |
| E2 minimize_grid_reliance | $164,240 | 0 kWh | 968,085 kWh |

E1 and E3 produce identical results when grid is uncapped — both strategies prefer grid over generator. The strategies only diverge when grid is restricted. E2 cleanly inverts the dispatch order: generator replaces grid entirely.

**Grid mode comparison (FP-H + oversupply):**
| Mode | Export (kWh) | Revenue | Curtailed |
|------|-------------|---------|-----------|
| E5 net_metering | 737M | $0 (credits only) | 0 |
| E6 feed_in_tariff | 737M | $59M | 0 |
| E7 self_consumption | 0 | $0 | 756M |

Feed-in tariff is the only mode that generates cash export revenue. Self_consumption forces all surplus to curtailment.

**Battery size impact (self_consumption, FP-O):**
| Config | Capacity | Charged | Curtailed | Self-consumption ratio |
|--------|----------|---------|-----------|----------------------|
| ES7 tiny | 10 kWh | 2,787 kWh | 565,072 kWh | 0.926 |
| ES8 huge | 2,000 kWh | 143,124 kWh | 424,735 kWh | 0.945 |

51x more charge absorbed; 25% less curtailment. Diminishing returns — even a 200x larger battery only reduces curtailment by 25%.

**Look-ahead behavioral inversion (E13):**
Look-ahead grid cap enforcement spreads grid usage more evenly (CV 0.37 vs 0.62) but uses 38.7% MORE generator because daily proration restricts cheap grid draws on high-demand days. The spreading mechanism trades cost efficiency for operational smoothness.

### Parameter Sensitivity Findings

1. **Agri-PV dominance**: Even moderate `underpv_medium` fields (FP-M, 4.5 ha) produce enough energy to mask all deficit behavior. Energy dispatch testing requires FP-O (no agri-PV) to properly exercise deficit paths.

2. **Battery irrelevance at extremes**: In both oversupply (battery pinned at soc_max) and severe undersupply (battery drains day 1 and never recharges), the battery plays no meaningful operational role. Battery behavior is only exercised in near-balanced regimes.

3. **Generator rarely needed with grid access**: Under `minimize_cost` with any grid-connected mode, the generator never dispatches because grid is always cheaper. Generator testing requires `off_grid`, `minimize_grid_reliance`, or tight grid caps.

## Phase 4: Additional Coverage Tests (E4b, ES9b, ES11–ES13)

These tests were added to address gaps identified in the original 23 tests.

| Test | Status | Farm Profile | Key Metrics | Notes |
|------|--------|-------------|-------------|-------|
| E4b full_grid undersupply | PASS | FP-M (0.12 ha underpv) | import=1,331K kWh (79.8% of days), export=181K kWh (15.4%) | Both grid import AND export paths now exercised; deficit=0 |
| ES9b large_generator off_grid | PASS | FP-O | gen=611K kWh, fuel=$451K, grid=0, deficit=0 | Generator active 50.3% of days; confirms dispatch path ES9 couldn't exercise |
| ES11 battery_cycling | CONDITIONAL PASS | FP-O | 564 charge days, 546 discharge days, SOC std=72 kWh | Solar reduced 0.15→0.055 ha to achieve balance; seasonal cycling confirmed |
| ES12 generator_min_load | PASS | FP-O | 3,432 gen days, 1,050 at min-load (30 kW × 6h), 0 violations | `generator_kwh` stores delivered energy; excess goes to `curtailed_kwh` |
| ES13 solar_degradation | PASS | FP-O | -0.598%/yr regression slope (code default 0.6%/yr) | Degradation confirmed over 15 years; wind shows no degradation trend |

### E4b — full_grid undersupply (resolves E4 gap)

E4 used FP-M (4.5 ha underpv_medium) which created permanent 3x oversupply. E4b reduced underpv_medium to 0.12 ha so supply/demand ratio is ~0.82x. Grid import triggers on 79.8% of days, grid export on 15.4% — both paths validated. Battery uses full SOC range [0.20, 0.95]. Deficit = 0 confirms full_grid mode fulfills all unmet demand.

### ES9b — large_generator off_grid (resolves ES9 gap)

ES9 used self_consumption mode which still allows grid import. The grid was always cheaper than diesel, so the 500 kW generator never fired. ES9b switches to off_grid, forcing generator dispatch on 2,757/5,479 days (50.3%). Total generator output 611,444 kWh, fuel cost $450,567 over 15 years. Deficit = 0 confirms 500 kW generator covers all shortfalls.

### ES11 — battery_cycling

Required reducing community solar from 0.15 to 0.055 ha/density (spec deviation) to achieve near-balanced regime. At 0.15 ha, supply/demand ratio was 2.41x and battery pinned at soc_max 99.7% of time. At 0.055 ha, battery exhibits genuine seasonal cycling: summer at soc_max (surplus curtailed), winter at soc_min (grid supplements), transition seasons show active daily charge/discharge alternation. SOC std dev = 72 kWh confirms battery is not flat-lined.

### ES12 — generator_min_load

Off-grid with no battery forces generator dispatch on 62.6% of days. Generator runs at exactly 30 kW (min_load_fraction × 100 kW) on 1,050 days with 6-hour minimum shifts. 0 min-load violations. Key finding: `generator_kwh` column stores *delivered* energy, not total generator output. Excess above deficit goes to `curtailed_kwh`. Correct validation formula: `(generator_kwh + curtailed_kwh) / runtime_hours >= min_load_kw`.

### ES13 — solar_degradation

Solar degradation confirmed at -0.598%/yr (linear regression over 15 years), consistent with code default of 0.6%/yr for N-type TOPCon panels. Year-over-year changes are not monotonic due to weather variation, but the systematic trend is clear. Wind shows no degradation (mean +0.72%/yr, pure weather noise). Code implementation: `_apply_degradation()` in `src/energy_supply.py:153-170` applies `(1 - rate)^years_elapsed` to solar columns only.

## Updated Observations

### Additional Cross-Test Comparisons

**Generator dispatch conditions:**
| Test | Grid Mode | Strategy | Generator (kWh) | Why |
|------|-----------|----------|-----------------|-----|
| ES9 | self_consumption | minimize_cost | 0 | Grid import cheaper than diesel |
| ES9b | off_grid | minimize_cost | 611,444 | No grid available; generator is only backup |
| E2 | full_grid | minimize_grid_reliance | 968,085 | Strategy avoids grid; routes to generator |
| E9 | off_grid | minimize_cost | 58,967 | Moderate renewables + battery reduce generator need |

Generator only dispatches when grid is unavailable (off_grid) or strategy deliberately avoids it (minimize_grid_reliance). Under minimize_cost with any grid mode, grid always wins on cost.

**Battery cycling regimes:**
| Test | Capacity | Supply/Demand | SOC Behavior | Charge Days |
|------|----------|---------------|--------------|-------------|
| ES4 | 200 kWh | 74x (oversupply) | Pinned soc_max | 1 (day 1 only) |
| ES3 | 200 kWh | 0.15x (undersupply) | Drains day 1, pinned soc_min | 0 |
| ES11 | 200 kWh | 1.0x (balanced) | Full cycling, std=72 kWh | 564 |
| ES7 | 10 kWh | 0.93x | Bounds hit 99.4% of days | ~600 |

Battery cycling only occurs in near-balanced regimes. At supply/demand extremes, the battery is operationally inert.
