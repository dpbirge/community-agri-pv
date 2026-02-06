# Water Simulation MVP - Follow-up Questions and Issues

**STATUS: ✅ COMPLETE - All Decisions Finalized (February 2026)**

All questions resolved and implementation complete. This document serves as a decision log for the water simulation MVP.

---

## Resolved Questions Summary

| Q# | Topic | Resolution |
|----|-------|------------|
| Q1 | Crop planting dates | Single fixed date per crop per farm, MM-DD format |
| Q2 | Yield timing | Option A: Single harvest at end of season |
| Q3 | Municipal water pricing | Configurable: subsidized (tiered) or unsubsidized (SWRO cost) |
| Q4 | Energy for treatment | Option A: Unlimited grid energy for MVP |
| Q5 | Shared infrastructure | Option B: Proportional to farm area |
| Q6 | Crop policy integration | Option A: Skip for MVP (irrigation_multiplier = 1.0) |
| Q7 | Results granularity | Per-farm stored, community-wide plotted; separate per-farm plots |
| Q8 | Missing planting dates | Option A: Error if invalid (won't happen with valid MM-DD) |
| Q10 | Water/yield timing | Option B: Attribute to harvest year |
| Q11 | Electricity pricing | Option A: Use research data file |
| Q12 | Community crops section | Option A: Removed (crops per-farm only) |

---

## Design Decisions Locked

### Data & Calculations
- **Irrigation demand:** Lookup from precomputed CSVs by (crop, planting_date, calendar_date)
- **Yields:** Total per season, attributed to harvest year
- **Electricity prices:** From `historical_grid_electricity_prices-research.csv`
- **Municipal water prices:** From research data (subsidized) or scenario config (unsubsidized)

### Simulation Behavior
- **Energy:** Unlimited grid availability (no treatment constraints)
- **Infrastructure sharing:** Proportional to farm area_ha
- **Crop policies:** Skipped; full irrigation (multiplier = 1.0)
- **Harvest:** Single event at season end

### Results Output
- **Storage:** Daily per-farm results in CSV
- **Primary plots:** Community-wide aggregates (total water use, total yields, costs)
- **Secondary plots:** Per-farm breakdowns (separate files/figures)

---

## Implementation Ready

All questions resolved. Proceed with:

1. **Phase 1 completion:** Update `loader.py` for new YAML schema
2. **Phase 2:** Implement `src/data_loader.py`
3. **Phase 3:** Implement `src/state.py`
4. **Phase 4:** Implement `src/simulation.py`
5. **Phase 5:** Implement `src/metrics.py`
6. **Phase 6:** Implement `src/results.py`

See [water_simulation_mvp_plan.md](water_simulation_mvp_plan.md) for detailed phase specifications.
