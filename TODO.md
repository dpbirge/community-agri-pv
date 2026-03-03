# TODO

Planned enhancements and deferred work items for the community agri-PV simulation.

## Farming and Crop Yield

- [ ] **Salt stress yield penalty** — Add TDS-based yield reduction to `compute_harvest_yield()` using the Maas-Hoffman linear model with existing crop salt tolerance parameters (`tds_no_penalty_ppm`, `tds_lethal_ppm`, `tds_yield_decline_pct_per_100ppm`). The delivered water TDS series from the water balance would be passed as an optional parameter, producing a season-average salt stress coefficient that multiplies into the yield formula. See `specs/farming_crop_yield_specification.md` Gap 5 and `docs/planning/farming_crop_yield_gaps_plan.md` for implementation details.

## Financial Module (Deferred)

Energy system financial analysis is not yet implemented. Key items to address:

- Capital costs for PV, wind, battery, inverters (data exists: `data/economics/capital_costs-research.csv`)
- Operating costs for wind O&M by turbine class (data exists: `data/economics/operating_costs-research.csv`)
- Equipment replacement schedules and costs
- Levelized cost of energy (LCOE) calculation
- Return on investment (ROI) analysis
- Export revenue modeling for `full_grid` mode (wholesale/bilateral pricing)
- Amortization and financing terms

## Water System

- See `specs/water_system_specification.md` "Intentionally Deferred Water Policy Extensions" section for planned water system enhancements (leaching requirement, drought contingency, priority-based field allocation, rainwater harvesting, etc.).
