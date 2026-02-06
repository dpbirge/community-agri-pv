**Last Updated:** February 5, 2026

## TODO

- Fix issues with inflation: need to use historic prices for food, etc. but match current OPEX/CAPEX prices properly. We should use the variation but start at today's prices: See docs/codereview/inflation-analysis...
- Add cool storage (not cold/refrigerated) to the processing chain for products that benefit from it — fresh produce and dried foods in particular. Evaporative cooling or shaded ventilated storage would extend shelf life in the Sinai heat with minimal energy cost.

See... docs/planning/food_processing_fixes.md
-Add processing energy cost tracking to process_harvests() using energy_kwh_per_kg from processing_specs CSV
- Add processing labor cost deduction in process_harvests() using labor_hours_per_kg from processing_specs CSV
- Split post_harvest_loss_kg into actual waste vs processing weight loss (water removal) — separate metrics
- Replace hardcoded REFERENCE_PRICES in MarketResponsive with CSV-derived or configurable thresholds
- Add fraction sum validation to ProcessingAllocation (enforce fractions sum to 1.0)