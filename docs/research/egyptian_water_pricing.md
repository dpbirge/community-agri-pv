# Egyptian Water Pricing Context

This document provides background on water pricing regimes relevant to the Community Agri-PV simulation, focusing on the Sinai Peninsula context.

## Water Pricing Regimes

### Subsidized Pricing

Egyptian municipal water is heavily subsidized by the government through the Holding Company for Water and Wastewater (HCWW). Subsidized rates are structured in consumption tiers:

| Tier | Consumption (m3/month) | EGP/m3 (2018) | USD/m3 (2018) | Target Users |
|------|------------------------|---------------|---------------|--------------|
| 1    | 0-10                   | 0.65          | ~0.036        | Low-income residential |
| 2    | 11-20                  | 1.60          | ~0.090        | Standard residential |
| 3    | 21-30                  | 2.25          | ~0.126        | Moderate consumption |
| 4    | 31-40                  | 2.75          | ~0.154        | High consumption |
| 5    | >40                    | 3.15          | ~0.177        | Very high / bulk users |

**Historical Tier Rates (EGP/m3):**

| Tier | 2017 | 2018 | Change |
|------|------|------|--------|
| 0-10 m3     | 0.45 | 0.65 | +44% |
| 11-20 m3    | 1.20 | 1.60 | +33% |
| 21-30 m3    | 1.65 | 2.25 | +36% |
| 31-40 m3    | 2.00 | 2.75 | +38% |
| >40 m3      | 2.15 | 3.15 | +47% |

**Notes:**
- Tier 5 (>40 m3) is most appropriate for agricultural bulk water use
- Subsidized pricing may not be available for all agricultural operations
- Rates vary by governorate and may change with policy reforms
- Wastewater surcharge: 75% of water tariff (added to base rate)
- 2018 rates are from Official Gazette, effective May 2018

### Unsubsidized Pricing

Full cost recovery pricing reflects the actual production and delivery costs without government subsidy. This is appropriate for:

- Communities without access to subsidized Nile water infrastructure
- Sinai Peninsula locations relying on seawater desalination
- Private or cooperative water systems

**Seawater Desalination (SWRO) Cost Range:**
- Minimum: $0.50/m3 (large-scale, efficient plants)
- Typical: $0.75/m3 (mid-range estimate for regional plants)
- Maximum: $1.00-1.50/m3 (small-scale or aging infrastructure)

## Sinai Peninsula Context

The simulation models a community on the Sinai Peninsula near the Red Sea coast (~28°N, 34°E). Key characteristics:

1. **No Nile Access**: Unlike the Nile Valley and Delta, Sinai lacks direct access to subsidized Nile water
2. **Groundwater Quality**: Coastal aquifers contain brackish water (TDS 3,000-10,000 ppm)
3. **Municipal Supply**: Regional desalination plants provide SWRO-treated seawater via pipeline
4. **Energy Costs**: Water treatment energy is a significant cost component

## Community Water Sources

### Municipal Supply (SWRO)
- Source: Regional seawater desalination utility
- Treatment: Seawater Reverse Osmosis (SWRO)
- Delivery: Pipeline infrastructure
- Pricing: Per-m3 delivered price (unsubsidized or partially subsidized)

### Community Groundwater (BWRO)
- Source: Community-owned wells tapping brackish aquifer
- Treatment: On-site Brackish Water Reverse Osmosis (BWRO)
- Costs: Pumping energy + treatment energy + maintenance
- Advantage: Potentially lower cost if renewable energy is available

## Cost Comparison Framework

The simulation compares water source costs using:

**Municipal Cost:**
```
cost_per_m3 = municipal_delivered_price
```

**Groundwater Cost:**
```
cost_per_m3 = (treatment_kwh × electricity_price) + maintenance_per_m3
```

Where:
- `treatment_kwh` depends on salinity level (see water_source_metadata.yaml)
- `electricity_price` comes from grid or renewable generation
- `maintenance_per_m3` covers membrane replacement and equipment upkeep

## Electricity Tiered Pricing

Egyptian electricity also uses consumption-based tiered pricing. Agricultural users receive preferential rates compared to commercial and residential users.

### Residential Electricity Tiers (August 2024)

| Tier | Consumption (kWh/month) | Piasters/kWh | EGP/kWh |
|------|-------------------------|--------------|---------|
| 1    | 0-50                    | 68           | 0.68    |
| 2    | 51-100                  | 78           | 0.78    |
| 3    | 101-200                 | 95           | 0.95    |
| 4    | 201-350                 | 155          | 1.55    |
| 5    | 351-650                 | 195          | 1.95    |
| 6    | 651-1000                | 210          | 2.10    |
| 7    | >1000                   | 165          | 1.65    |

### Agricultural Electricity Rates

Agricultural users (low-voltage irrigation at 380V) receive preferential flat rates:

| Period | Piasters/kWh | EGP/kWh | Notes |
|--------|--------------|---------|-------|
| Jan 2024 | 128 (avg) | 1.28 | MV agricultural rate |
| Aug 2024 | 200 | 2.00 | LV agricultural rate |

Agricultural rates are typically 15-20% lower than commercial rates for equivalent consumption levels.

### Tier Pricing Applicability to Simulation

For the Community Agri-PV simulation:

1. **Water Tiers**: Not directly applicable to Sinai Peninsula scenario
   - Agricultural Nile irrigation is historically free/subsidized
   - Sinai communities use desalination (flat per-m3 cost)
   - Municipal water tiers apply only to piped residential supply

2. **Electricity Tiers**: Agricultural flat rate is most appropriate
   - Water treatment uses agricultural electricity rate
   - No consumption-based tier progression for agriculture
   - Peak/off-peak differentials may apply (1.5x ratio)

3. **Implementation Recommendation**: For educational simulation purposes, tier pricing can be implemented as an optional feature to demonstrate consumption-based pricing mechanisms, even if not strictly accurate for the Sinai context.

## References

- HCWW (Holding Company for Water and Wastewater): Egyptian utility tariff structures
- IDA Desalination Yearbook: Global desalination cost benchmarks
- FAO AQUASTAT: Egypt water resources and pricing data
- EgyptERA (egyptera.org): Official electricity tariff schedules
- MadaMasr (2018): Government water tariff increases
- Egypt Today (2024): Electricity price adjustments

## Data Files

Related simulation data files:
- `data/prices/water/historical_municipal_water_prices-research.csv` - Municipal price time series
- `data/prices/electricity/historical_grid_electricity_prices-research.csv` - Electricity price time series
- `data/parameters/water/water_source_metadata.yaml` - Technical definitions and energy requirements
