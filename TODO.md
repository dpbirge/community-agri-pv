**Last Updated:** February 5, 2026

## TODO

Conceptual issues:
- Processing food policies and market selling policies must be coordinated better. The farmers are most likely going to process food into specific products based on current prices and expected prices in the following 2-3 months. It may be better to merge these into a single policy. 


- Fix issues with inflation: need to use historic prices for food, etc. but match current OPEX/CAPEX prices properly. We should use the variation but start at today's prices: See docs/codereview/inflation-analysis...
- Add cool storage (not cold/refrigerated) to the processing chain for products that benefit from it — fresh produce and dried foods in particular. Evaporative cooling or shaded ventilated storage would extend shelf life in the Sinai heat with minimal energy cost.

See... docs/planning/food_processing_fixes.md
-Add processing energy cost tracking to process_harvests() using energy_kwh_per_kg from processing_specs CSV
- Add processing labor cost deduction in process_harvests() using labor_hours_per_kg from processing_specs CSV
- Split post_harvest_loss_kg into actual waste vs processing weight loss (water removal) — separate metrics
- Replace hardcoded REFERENCE_PRICES in MarketResponsive with CSV-derived or configurable thresholds
- Add fraction sum validation to ProcessingAllocation (enforce fractions sum to 1.0)

---

## From Architecture Deep Review (2026-02-12)

### New Policies to Add (Future)

- Add `crop_specific` food processing policy — processes food by profitability of each resulting product BY CROP (e.g., cucumbers get 0% dried due to 92% weight loss; potatoes get 30% packaged) [Review 2.6]
- Add `maturity_based_harvest` crop policy — adjusts harvest timing based on water stress and market conditions. Requires expanding CropDecision output [Review 2.15]
- Add `combined_deficit_weather` crop policy — combines deficit irrigation with weather-responsive adjustments using both growth stage and temperature simultaneously [Review 2.1]

### Policy Improvements (Future)

- Improve market `hold_for_peak` and `adaptive` policies with crop-specific AND product-specific dynamic selling behavior [Review 2.11]

### Missing Formulas and Data (Future)

- Multiple planting dates interaction: how staggered plantings share area and overlap irrigation [Review 4.18a]
- Breakeven thresholds for sensitivity analysis: binary search algorithm needed [Review 4.18b]
- Revenue concentration price CV: `std(price) / mean(price)` per crop [Review 4.18c]
- Scenario stress test construction: drought, price spike, equipment failure parameters [Review 4.18d]
- Battery self-discharge integration [Review 4.18e]
- Community vs external labor ratio: needs community available labor supply data [Review 4.18f]

### Monte Carlo Resilience Metrics to Implement [Review 4.17]

- Probability of crop failure
- Median years to insolvency
- Worst-case farmer outcome
- Income inequality (Gini coefficient)
- Maximum drawdown
