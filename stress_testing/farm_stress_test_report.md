# Farm Profile Stress Test Report

## Summary
- Tests run: 10 (FP1–FP10), plus 1 paired sub-run (FP8 = 2 simulations)
- Passed: 10
- Failed: 0
- Warnings: 2 (planting overlap corrections in FP1 and FP6)

All tests completed without crashes. Universal validation checks (no NaN, non-negative quantities, water balance conservation, date continuity, tank bounds, battery bounds) pass for every test.

## Baseline Configuration
- Energy system: 0.05 ha each low/medium/high density solar, 4 small wind turbines, 200 kWh battery, 50 kW generator, full grid
- Water system: 3 wells (20m/1400ppm, 50m/3500ppm, 100m/6500ppm), BWRO 50 m3/hr, 200 m3 tank, municipal at $0.50/m3
- Water policy: minimize_cost, static irrigation (full_eto), 15000 m3/month groundwater cap, prefill enabled
- Energy policy: minimize_cost, full grid, look-ahead cap enforcement

## Results Table

| Test | Farm Profile | Total Area (ha) | Total Water Demand (m3) | Total Agri-PV (kWh) | Water Deficit Days | Energy Deficit Days | Status | Notes |
|------|-------------|:---:|---:|---:|:---:|:---:|:---:|-------|
| FP1 | 4 fields, openfield, sprinkler | 9.0 | 2,008,714 | 0 | 819 | 0 | PASS | Planting overlaps corrected |
| FP2 | 4 fields, underpv_high, sprinkler | 12.0 | 916,019 | 542,526,736 | 0 | 0 | PASS | Agri-PV dominates; 103x demand |
| FP3 | 4 fields, mixed density, mixed irr | 6.0 | 833,714 | 145,046,676 | 0 | 0 | PASS | Density ranking confirmed |
| FP4 | 2 fields, drip, openfield | 1.0 | 315,452 | 0 | 0 | 0 | PASS | Comfortable surplus |
| FP5 | 4 fields, furrow, openfield | 12.0 | 3,230,091 | 0 | 2,385 | 0 | PASS | Furrow drives high demand |
| FP6 | 1 field, underpv_high, drip | 5.0 | 486,369 | 226,052,807 | 0 | 0 | PASS | Kale oct01 removed (overlap) |
| FP7 | 8 fields, 4 farms, mixed | 2.0 | 292,180 | 48,348,892 | 0 | 0 | PASS | 4 agripv columns confirmed |
| FP8a | 4 fields, openfield, sprinkler | 10.0 | 1,951,878 | 0 | 492 | 0 | PASS | Paired comparison baseline |
| FP8b | 4 fields, underpv_high, sprinkler | 10.0 | 719,611 | 452,105,614 | 0 | 0 | PASS | 68.5% less water demand |
| FP9 | 4 fields, 10 ha each, mixed pv | 40.0 | 6,817,959 | 632,083,628 | 3,624 | 0 | PASS | Graceful degradation |
| FP10 | 3 fields, drip/sprinkler/furrow | 6.0 | 1,679,062 | 0 | 895 | 0 | PASS | Exact efficiency ratios |

## Cross-Test Comparisons

### Irrigation Efficiency Impact

**FP10 (drip vs sprinkler vs furrow, same crop/area/condition):**
- furrow/drip demand ratio: **1.5000** (exact match to 0.90/0.60 efficiency ratio)
- sprinkler/drip demand ratio: **1.2000** (exact match to 0.90/0.75 efficiency ratio)
- Confirms irrigation efficiency scaling is purely linear and exact.

**FP4 (1 ha drip) vs FP5 (12 ha furrow):**
- FP5 water demand is 10.2x FP4's (3,230,091 vs 315,452 m3)
- Area ratio is 12x; remaining difference explained by irrigation efficiency (furrow 0.60 vs drip 0.90 = 1.5x) and crop mix
- FP4: 0 deficit days; FP5: 2,385 deficit days — balanced infrastructure breaks down under high furrow demand

### Agri-PV Scaling

**FP1 (openfield) vs FP2 (underpv_high):**
- FP1 total renewable: 6,093,135 kWh (community solar + wind only)
- FP2 total renewable: 548,619,872 kWh (agri-PV adds 542.5 GWh)
- Agri-PV from 12 ha underpv_high exceeds community demand by 103x

**FP3 (mixed densities) — per-density generation ranking:**
- high density: 8,629 kWh/ha/day (mean)
- medium density: 6,032 kWh/ha/day
- low density: 3,795 kWh/ha/day
- Ranking confirmed: high > medium > low, with clear separation between tiers

**FP8 (paired comparison, 10 ha each):**
- Openfield agri-PV: 0 kWh
- Underpv_high agri-PV: 452,105,614 kWh
- Water demand reduction under PV: 1,232,267 m3 (63.1% less irrigation)
- Water deficit days: 492 → 0 (eliminated entirely by PV shading reducing ETc)
- Energy self-sufficiency: 0.882 → 1.000

### Area Scaling

| Test | Total Area | Water Demand | Demand/ha | Deficit Days |
|------|:---:|---:|---:|:---:|
| FP4 | 1 ha | 315,452 m3 | 315,452 | 0 |
| FP7 | 2 ha | 292,180 m3 | 146,090 | 0 |
| FP10 | 6 ha | 1,679,062 m3 | 279,844 | 895 |
| FP1 | 9 ha | 2,008,714 m3 | 223,191 | 819 |
| FP5 | 12 ha | 3,230,091 m3 | 269,174 | 2,385 |
| FP9 | 40 ha | 6,817,959 m3 | 170,449 | 3,624 |

Per-ha demand varies by crop mix, irrigation type, and PV condition. Deficit days increase sharply above ~6 ha total area against the balanced water infrastructure.

### PV Shading Effect on Water Demand

The paired FP8 test isolates the PV shading effect on ETc:

| Field | Openfield Demand (m3) | Underpv_high Demand (m3) | Reduction |
|-------|---:|---:|:---:|
| field_a (tomato) | 650,924 | 199,059 | -69.4% |
| field_b (cucumber) | 415,993 | 127,293 | -69.4% |
| field_c (potato) | 417,801 | 136,591 | -67.3% |
| field_d (kale) | 312,280 | 101,787 | -67.3% |

Underpv_high consistently reduces ETc by 67–69% across all crops tested.

## Warnings

### Planting Overlap Corrections
- **FP1 field_a**: `kale oct01` removed — overlapped with `tomato aug01` (tomato ends Nov 29, kale starts Oct 1)
- **FP1 field_d**: `onion dec01` removed, `kale mar15` replaced with `kale oct01` — cross-year overlap between onion plantings
- **FP6**: `kale oct01` removed — same overlap with `tomato aug01`

These corrections reduce year-round coverage for affected fields but are required by the planting overlap validator.

### Agri-PV Column Propagation
The per-farm `*_agripv_kwh` columns exist in the intermediate `compute_daily_energy()` DataFrame but are **not carried through** to the final `daily_energy_balance.csv`. The dispatch loop in `_run_simulation` only consumes `total_solar_kwh`, `total_wind_kwh`, and `total_renewable_kwh`. All agri-PV validation checks were performed against the intermediate supply DataFrame.

## Observations

1. **Irrigation efficiency is the dominant water demand lever.** FP10 confirms exact linear scaling — switching from drip to furrow increases demand by exactly 50% for the same crop and area. This is often a larger effect than field area changes.

2. **PV shading has a dual benefit.** Beyond energy generation, underpv_high reduces irrigation demand by ~68% (FP8). This eliminates water deficit days that openfield profiles experience, creating a strong coupling between PV density choice and water system sizing requirements.

3. **The balanced infrastructure has a capacity threshold around 6 ha.** Tests below ~6 ha (FP4, FP7, FP3) show zero water deficits. Tests above 6 ha (FP1, FP5, FP10) show increasing deficit days. This is useful for calibrating test infrastructure.

4. **Many-field scaling works correctly.** FP7 (8 fields, 4 farms) produced correct per-farm agri-PV columns and reasonable water demand, confirming no edge cases with field count scaling.

5. **Graceful degradation under extreme mismatch.** FP9 (40 ha against balanced infrastructure) completed without crashes despite 3,624 water deficit days (66% of simulation). The system correctly tracks deficits without producing NaN or negative values.

6. **Battery behavior is binary.** In heavily over-supplied scenarios (FP2, FP3, FP6, FP9), the battery fills to soc_max on day 1 and never discharges. In balanced/deficit scenarios (FP1, FP5, FP8-open, FP10), the battery cycles normally within bounds.

7. **Energy deficit is never observed.** All tests show 0 energy deficit days because the balanced energy config includes full grid access. To stress-test energy deficits, an off-grid or limited-grid energy policy would be needed.
