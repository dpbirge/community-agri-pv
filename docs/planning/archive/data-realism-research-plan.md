# Data Realism Research Plan

**Date**: 2026-02-02
**Purpose**: Structure research tasks to improve toy dataset realism with empirical data
**Reference**: [data_generation_validation_report.md](../validation/data_generation_validation_report.md)

---

## Research Progress

| Task | Priority | Status | Output File | Notes |
|------|----------|--------|-------------|-------|
| R1: Egyptian Electricity | High | ✅ Complete | `historical_grid_electricity_prices-research.csv` | Agricultural rates documented |
| R2: Agricultural Wages | High | 📋 Planned | `labor_wages-research.csv` | Not started |
| R3: Egyptian Water | High | ✅ Complete | `historical_municipal_water_prices-research.csv` | Tiered rates + SWRO costs |
| R4: Diesel Prices | High | 📋 Planned | `historical_diesel_prices-research.csv` | Not started |
| R5: Sinai Weather | High | 📋 Planned | `daily_weather_scenario_001-research.csv` | NASA POWER data needed |
| R6: Crop Prices | High | 📋 Planned | `historical_*_prices-research.csv` (5 files) | Not started |
| R7: Crop Coefficients | Medium | 📋 Planned | `crop_coefficients-research.csv` | Not started |
| R8: Renewable Costs | Medium | 📋 Planned | `capital_costs-research.csv` | Not started |
| R9: Desalination | Medium | 📋 Planned | `water_treatment-research.csv` | Not started |
| R10: Agri-PV Microclimate | Low | 📋 Planned | `pv_shade_adjustments-research.csv` | Not started |

**Progress: 2/10 Complete (20%)**

---

## Overview

The toy datasets (`-toy` suffix) provide synthetic data for simulation development. This plan structures research to create improved datasets (`-research` suffix) incorporating empirical data from authoritative sources.

### File Naming Convention

| Data Type | Current (Synthetic) | Improved (Research) |
|-----------|---------------------|---------------------|
| Weather | `*-toy.csv` | `*-research.csv` |
| Prices | `*-toy.csv` | `*-research.csv` |
| Parameters | `*-toy.csv` | `*-research.csv` |

**Critical Rule**: Never overwrite `-toy` files. Create parallel `-research` files that can be compared against synthetic baselines.

---

## Research Task Structure

### Priority 1: Egyptian-Specific Economic Data (High Impact)

#### Task R1: Egyptian Electricity Tariffs
**Output**: `data/prices/electricity/historical_grid_electricity_prices-research.csv`

**Research Sources**:
- Egyptian Electricity Holding Company (EEHC): https://www.eehc.gov.eg/
- Egyptian Electric Utility and Consumer Protection Regulatory Agency (EgyptERA)
- Ministry of Electricity and Renewable Energy annual reports

**Data to Collect**:
- Agricultural tariff schedules 2015-2024
- Time-of-use rate structures (peak/off-peak)
- Subsidy removal timeline and rate changes
- Any seasonal rate adjustments

**Validation Criteria**:
- Rates should show subsidy removal progression
- Peak/off-peak differential documented
- Original EGP values with dated exchange rates

---

#### Task R2: Egyptian Agricultural Wages
**Output**: `data/parameters/labor/labor_wages-research.csv`

**Research Sources**:
- Egyptian Ministry of Manpower: https://www.manpower.gov.eg/
- ILO ILOSTAT database: https://ilostat.ilo.org/
- Central Agency for Public Mobilization and Statistics (CAPMAS)
- World Bank data on Egypt

**Data to Collect**:
- Minimum wage decrees 2015-2024
- Agricultural sector wage surveys
- Skill-based wage differentials
- Regional wage variations (Sinai vs national average)

**Validation Criteria**:
- Wages aligned with official minimum wage progression
- Skill premiums reasonable (1.5-2.5x unskilled)
- Source citations for each wage category

---

#### Task R3: Egyptian Water Prices
**Output**: `data/prices/water/historical_municipal_water_prices-research.csv`

**Research Sources**:
- Holding Company for Water and Wastewater (HCWW)
- Egyptian Water Regulatory Agency
- World Bank IBNET database
- Academic papers on Egyptian water pricing

**Data to Collect**:
- Municipal water tariffs for agricultural/bulk users
- Regional variations (Sinai/Red Sea governorate)
- Groundwater extraction costs if available
- Desalination cost benchmarks in region

**Validation Criteria**:
- Prices reflect water scarcity premium
- Comparison with MENA regional averages

---

#### Task R4: Egyptian Diesel Prices
**Output**: `data/prices/diesel/historical_diesel_prices-research.csv`

**Research Sources**:
- Egyptian General Petroleum Corporation (EGPC)
- World Bank Commodity Price Data (Pink Sheet)
- Trading Economics Egypt fuel prices
- IMF Egypt subsidy reform documentation

**Data to Collect**:
- Monthly diesel prices 2015-2024
- Subsidy removal timeline
- Agricultural diesel subsidies if any
- Correlation with global Brent crude

**Validation Criteria**:
- Prices track global oil with subsidy adjustments
- Subsidy removal milestones documented

---

### Priority 2: Weather and Climate Data (High Impact)

#### Task R5: Sinai Weather Data
**Output**: `data/precomputed/weather/daily_weather_scenario_001-research.csv`

**Research Sources**:
- NASA POWER Data Access Viewer: https://power.larc.nasa.gov/
- MERRA-2 reanalysis data
- World Bank Climate Knowledge Portal
- Egyptian Meteorological Authority (if accessible)

**Data to Collect** (for ~28°N, 34°E):
- Daily temperature (min/max) 2010-2024
- Global horizontal irradiance (GHI)
- Wind speed at 10m and 50m heights
- Precipitation (daily)
- Relative humidity

**Validation Criteria**:
- Coordinates match Sinai Red Sea coast
- Temperature extremes within observed records
- Solar resource matches PVGIS/SolarGIS benchmarks
- Missing data handling documented

---

### Priority 3: Agricultural Market Data (Medium Impact)

#### Task R6: Crop Price Data
**Output**: `data/prices/crops/historical_[crop]_prices-research.csv` (5 files)

**Research Sources**:
- FAO GIEWS Food Price Monitoring: https://www.fao.org/giews/food-prices/
- FAO FAOSTAT: https://www.fao.org/faostat/
- USDA Global Agricultural Trade System (GATS)
- Egyptian Ministry of Agriculture market reports

**Data to Collect**:
- Monthly wholesale prices for tomato, potato, onion, kale, cucumber
- Egyptian domestic prices if available
- MENA regional prices as proxy
- Export prices (European market for packaged goods)

**Validation Criteria**:
- Seasonal patterns match harvest cycles
- Year-to-year volatility realistic (20-30% CV)
- Price relationships between crops reasonable

---

#### Task R7: Crop Coefficient Validation
**Output**: `data/parameters/crops/crop_coefficients-research.csv`

**Research Sources**:
- FAO Irrigation and Drainage Paper 56 (official tables)
- FAO AquaCrop model documentation
- Academic papers on Kc in arid climates
- Egyptian agricultural extension publications

**Data to Collect**:
- FAO-56 base Kc values (verify current values)
- Hot arid climate adjustment factors
- Any Egypt/MENA-specific field trial data
- Drip irrigation adjustment factors

**Validation Criteria**:
- Adjustments justified by literature citations
- Comparison with similar climate zones (Israel, Jordan, Saudi Arabia)

---

### Priority 4: Equipment and Technology Data (Medium Impact)

#### Task R8: Renewable Energy Costs (Egypt/MENA)
**Output**: `data/parameters/costs/capital_costs-research.csv`

**Research Sources**:
- IRENA Renewable Cost Database: https://www.irena.org/costs
- NREL Annual Technology Baseline 2024
- Egyptian Renewable Energy Authority (NREA)
- BloombergNEF solar/wind cost indices

**Data to Collect**:
- PV system costs in Egypt/MENA ($/kW installed)
- Battery storage costs ($/kWh)
- Small wind turbine costs
- Installation cost premiums for remote locations

**Validation Criteria**:
- Costs reflect 2024 market conditions
- Regional premium over global average documented

---

#### Task R9: Desalination Parameters
**Output**: `data/parameters/equipment/water_treatment-research.csv`

**Research Sources**:
- DesalData global desalination database
- DOE Desalination and Water Purification Research
- Academic literature on BWRO in MENA
- Egyptian desalination plant data if available

**Data to Collect**:
- Brackish water quality ranges in Sinai
- Energy consumption by salinity level
- Membrane replacement frequencies
- Capital and O&M costs for small-scale BWRO

**Validation Criteria**:
- Salinity ranges match Sinai groundwater surveys
- Energy consumption aligned with manufacturer specs

---

### Priority 5: Microclimate and Agri-PV Data (Lower Impact)

#### Task R10: Agri-PV Microclimate Studies
**Output**: `data/precomputed/microclimate/pv_shade_adjustments-research.csv`

**Research Sources**:
- Fraunhofer ISE agri-PV publications
- University of Arizona agri-PV research
- Academic papers on agri-PV microclimate effects
- Agri-PV field trial data (Germany, Japan, USA, Chile)

**Data to Collect**:
- Temperature reduction under panels by coverage density
- PAR (photosynthetically active radiation) reduction
- Evapotranspiration reduction factors
- Wind speed reduction under panels

**Validation Criteria**:
- Values supported by peer-reviewed literature
- Range of values from multiple studies documented

---

## Research Output Requirements

### File Structure
Each `-research.csv` file must include:

1. **Enhanced metadata header**:
```
# SOURCE: [Primary sources with URLs]
# DATE: [Research date]
# DESCRIPTION: [Dataset description]
# UNITS: [Unit definitions]
# LOGIC: [How data was collected/processed]
# DEPENDENCIES: [Related files]
# ASSUMPTIONS: [Key assumptions]
# DATA_QUALITY: [Completeness, gaps, interpolations]
# COMPARISON_TO_TOY: [How this differs from synthetic version]
```

2. **Source citations**: Every data point should be traceable to a source
3. **Gap documentation**: Where empirical data unavailable, document interpolation methods
4. **Comparison notes**: Document differences from `-toy` baseline

### Quality Checklist
- [ ] All files load successfully in pandas
- [ ] No missing values (or documented with reason)
- [ ] Units consistent with `-toy` files for compatibility
- [ ] Column names match `-toy` files exactly
- [ ] Metadata complete per template above

---

## Research Agent Guidelines

1. **Do not modify `-toy` files** - these are the synthetic baseline
2. **Create `-research` suffix files** in the same directory structure
3. **Document all sources** with URLs and access dates
4. **Note data gaps** where empirical data unavailable
5. **Prefer authoritative sources**: Government agencies > International organizations > Academic papers > Industry reports
6. **Validate ranges** against `-toy` files and note significant differences

---

## Success Criteria

Research complete when:
- [ ] All 10 research tasks have corresponding `-research.csv` files
- [ ] All files have complete metadata headers
- [ ] Source citations provided for all data
- [ ] Data gaps and interpolations documented
- [ ] Comparison summary written for each file vs `-toy` baseline
- [ ] Files load and validate in Python/pandas

---

## Recommended Execution Order

**Wave 1** (Independent, can run in parallel):
- R1: Egyptian Electricity Tariffs
- R2: Egyptian Agricultural Wages
- R3: Egyptian Water Prices
- R4: Egyptian Diesel Prices
- R5: Sinai Weather Data
- R6: Crop Price Data

**Wave 2** (Can run in parallel, lower priority):
- R7: Crop Coefficient Validation
- R8: Renewable Energy Costs
- R9: Desalination Parameters
- R10: Agri-PV Microclimate Studies

---

## References

- [Data Generation Orchestration](data-generation-orchestration.md) - Original task specifications
- [Validation Report](../validation/data_generation_validation_report.md) - Identified research gaps
- [Data Organization](data-organization.md) - File structure and format specifications
