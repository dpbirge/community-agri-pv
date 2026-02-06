# Egyptian Utility Pricing: Seasonal Patterns Analysis

This document summarizes research findings on seasonal pricing patterns for electricity and water utilities in Egypt, conducted to determine whether the Community Agri-PV simulation should implement seasonal price multipliers.

## Executive Summary

**Finding: No significant seasonal tariff variation exists in Egyptian utility pricing.**

Egyptian electricity and water tariffs use tiered consumption-based pricing but do not implement seasonal (summer/winter) rate differentials. While time-of-use (peak/off-peak) pricing exists for electricity, it applies uniformly year-round without seasonal adjustment.

**Recommendation: No implementation required.** The existing data files already capture the relevant pricing structures. The simulation should continue using flat seasonal rates with optional peak/off-peak differentiation for electricity.

## Electricity Pricing Research

### Official Tariff Structure (EgyptERA 2024)

Data sourced from Egyptian Electric Utility and Consumer Protection Regulatory Agency (EgyptERA).

**Agricultural/Irrigation Rates (August 2024):**

| Voltage Level | Rate Structure | Price |
|---------------|----------------|-------|
| Medium Voltage (22-11 kV) | Flat rate | 194.0 pt/kWh |
| Low Voltage (380 V) | Flat rate | 200.0 pt/kWh |

**Medium Voltage Agricultural with Time-of-Use (Jan 2024):**

| Period | Rate |
|--------|------|
| Average | 128.3 pt/kWh |
| Off-peak | 118.4 pt/kWh |
| On-peak | 177.6 pt/kWh |

**Key Finding:** Peak/off-peak differentials exist but are not seasonally adjusted. The tariff documents explicitly show no summer/winter rate variations. All rates are published as uniform rates effective from specific dates.

### Peak Hour Definition

Peak hours are determined by the Ministry of Electricity and Energy and last 4 hours per day. Time-of-use rates apply only where smart meters are installed. The peak/off-peak ratio is approximately 1.5x (based on 177.6/118.4 = 1.50).

### Seasonal Demand Patterns

While Egypt experiences significant seasonal demand variation due to summer air conditioning loads:

- Summer peak demand reached 37.2 GW in August 2024 (vs ~30 GW in winter)
- Load shedding has occurred during summer months (2023-2024)
- Temperatures exceed 40-45 degrees Celsius in summer months

However, this demand variation is **not reflected in seasonal tariff adjustments**. The Egyptian pricing model relies on:
1. Consumption tier increases (residential)
2. Time-of-use pricing (industrial/agricultural with smart meters)
3. Periodic tariff revisions across all months

### Toy Data Observation

The existing toy electricity data file (`historical_grid_electricity_prices-toy.csv`) includes a `rate_schedule` column with "summer" values for June-September. This appears to be a modeling assumption rather than official Egyptian policy. The research data file should use "standard" uniformly since official EgyptERA tariffs show no seasonal differentiation.

## Water Pricing Research

### HCWW Tariff Structure

The Holding Company for Water and Wastewater (HCWW) manages water pricing through 26 affiliated regional companies. Research findings:

**Seasonal Variation: None Found**

Egyptian municipal water tariffs are structured by:
1. Consumption tiers (residential)
2. User category (residential, commercial, industrial, agricultural)
3. Geographic region (urban vs rural, Nile-connected vs coastal)

No documentation was found indicating summer/winter rate differentials for any water category.

### Desalination Costs

For Sinai Peninsula communities relying on desalination:

- Energy costs represent ~50% of total desalination production cost
- Desalination plant operation is continuous year-round
- No seasonal pricing variation documented for delivered desalinated water

While energy costs could theoretically vary seasonally (if electricity had seasonal rates), this is not the case in Egypt. Desalination water costs are primarily driven by:
- Plant scale (inversely proportional to cost)
- Energy source and local electricity pricing
- Maintenance and membrane replacement cycles

## Implications for Simulation

### Current Implementation Status

The existing codebase handles electricity pricing appropriately:

1. **Research data file** (`historical_grid_electricity_prices-research.csv`):
   - Uses "standard" rate_schedule uniformly
   - Includes peak/off-peak columns derived from MV agricultural rates
   - Captures historical tariff changes at fiscal year boundaries

2. **Toy data file** (`historical_grid_electricity_prices-toy.csv`):
   - Includes summer/winter distinction in rate_schedule column
   - This can remain for scenario testing but reflects a hypothetical rather than actual Egyptian practice

3. **Data loader** (`data_loader.py`):
   - `get_electricity_price()` returns average or peak/off-peak rates
   - No seasonal adjustment needed

### Recommended Action

**No code changes required for Phase 5 (Seasonal Pricing).**

The research confirms that seasonal pricing is not a feature of Egyptian utility tariffs. The simulation's existing implementation correctly reflects this reality:

1. Electricity prices vary by date (capturing tariff changes over time)
2. Peak/off-peak differentiation is available for scenarios requiring time-of-use modeling
3. Water prices use tier-based or flat unsubsidized rates without seasonal adjustment

### Future Considerations

If the simulation is extended to other geographic contexts where seasonal utility pricing exists, the following structure could be added:

```yaml
# Example seasonal pricing config (NOT implemented for Egypt)
seasonal_pricing:
  enabled: false
  electricity:
    summer_months: [6, 7, 8, 9]
    summer_multiplier: 1.0  # No adjustment
    winter_multiplier: 1.0
  water:
    summer_months: [6, 7, 8, 9]
    summer_multiplier: 1.0
    winter_multiplier: 1.0
```

## Data Sources

### Primary Sources

- [EgyptERA Current Electricity Tariff (Aug 2024)](https://egyptera.org/en/TarrifAug2024.aspx) - Official agricultural and irrigation rates
- [EgyptERA Electricity Tariff (Jan-Jul 2024)](https://egyptera.org/en/Tarrif2024N.aspx) - Time-of-use rates for medium voltage

### Supporting Sources

- [Egypt - Water and Environment (US Trade.gov)](https://www.trade.gov/country-commercial-guides/egypt-water-and-environment) - HCWW structure and water sector overview
- [Water Supply and Sanitation in Egypt (Wikipedia)](https://en.wikipedia.org/wiki/Water_supply_and_sanitation_in_Egypt) - Utility organization background
- [Ahram Online - Electricity Load Peak](https://english.ahram.org.eg/NewsContent/1/2/549805/Egypt/Society/Electricity-load-in-Egypt-hits-annual-peak-amid-so.aspx) - Summer demand patterns
- [Global Petrol Prices - Egypt Electricity](https://www.globalpetrolprices.com/Egypt/electricity_prices/) - International comparison context

## Research Date

Research conducted: February 2026

Last tariff update reviewed: August 2024 (EgyptERA)
