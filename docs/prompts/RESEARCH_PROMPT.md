# Data Realism Research Task

## Objective
Improve the realism of the Community Agri-PV simulation datasets by researching and collecting empirical data from authoritative sources.

## Critical Instructions

**DO NOT OVERWRITE existing `-toy` files.** These are the synthetic baseline datasets and must be preserved.

**CREATE NEW FILES with `-research` suffix** in the same directory structure. For example:
- `historical_grid_electricity_prices-toy.csv` → `historical_grid_electricity_prices-research.csv`
- `daily_weather_scenario_001-toy.csv` → `daily_weather_scenario_001-research.csv`

## Reference Documents
Read these files before starting:
1. `docs/planning/data-realism-research-plan.md` - Full research task specifications
2. `docs/validation/data_generation_validation_report.md` - Identified research gaps
3. `docs/planning/data-organization.md` - File format specifications

## Research Tasks (Launch in Parallel)

### Wave 1: High Priority (Egyptian Economic Data + Weather)

**Agent R1 - Egyptian Electricity Tariffs**
- Output: `data/prices/electricity/historical_grid_electricity_prices-research.csv`
- Sources: EEHC, EgyptERA, Ministry of Electricity reports
- Collect: Agricultural tariffs 2015-2024, peak/off-peak rates, subsidy removal timeline

**Agent R2 - Egyptian Agricultural Wages**
- Output: `data/parameters/labor/labor_wages-research.csv`
- Sources: Ministry of Manpower, ILO ILOSTAT, CAPMAS, World Bank
- Collect: Minimum wage progression, agricultural sector wages by skill level

**Agent R3 - Egyptian Water Prices**
- Output: `data/prices/water/historical_municipal_water_prices-research.csv`
- Sources: HCWW, Egyptian Water Regulatory Agency, World Bank IBNET
- Collect: Municipal water tariffs for agricultural/bulk users

**Agent R4 - Egyptian Diesel Prices**
- Output: `data/prices/diesel/historical_diesel_prices-research.csv`
- Sources: EGPC, World Bank Pink Sheet, IMF subsidy reform docs
- Collect: Monthly diesel prices 2015-2024, subsidy removal milestones

**Agent R5 - Sinai Weather Data**
- Output: `data/precomputed/weather/daily_weather_scenario_001-research.csv`
- Sources: NASA POWER, MERRA-2, World Bank Climate Portal
- Collect: Daily temp, GHI, wind, precip for ~28°N, 34°E (2010-2024)

**Agent R6 - Crop Price Data**
- Output: `data/prices/crops/historical_[crop]_prices-research.csv` (5 files: tomato, potato, onion, kale, cucumber)
- Sources: FAO GIEWS, FAOSTAT, USDA GATS
- Collect: Monthly wholesale prices, MENA regional averages

### Wave 2: Medium Priority (Equipment and Parameters)

**Agent R7 - Crop Coefficients**
- Output: `data/parameters/crops/crop_coefficients-research.csv`
- Sources: FAO-56, AquaCrop docs, arid climate studies
- Collect: Verified Kc values with hot arid adjustments

**Agent R8 - Renewable Energy Costs**
- Output: `data/parameters/costs/capital_costs-research.csv`
- Sources: IRENA, NREL ATB 2024, NREA (Egypt)
- Collect: PV, battery, wind costs for Egypt/MENA region

**Agent R9 - Desalination Parameters**
- Output: `data/parameters/equipment/water_treatment-research.csv`
- Sources: DesalData, DOE, BWRO literature
- Collect: Sinai groundwater quality, energy consumption curves

**Agent R10 - Agri-PV Microclimate**
- Output: `data/precomputed/microclimate/pv_shade_adjustments-research.csv`
- Sources: Fraunhofer ISE, University of Arizona, peer-reviewed studies
- Collect: Temperature, irradiance, ET adjustments by panel density

## Output Requirements

Each `-research.csv` file must include:
1. **Complete metadata header** with SOURCE, DATE, DESCRIPTION, UNITS, LOGIC, DEPENDENCIES, ASSUMPTIONS
2. **Additional metadata**:
   - `DATA_QUALITY`: Note any gaps, interpolations, or data quality issues
   - `COMPARISON_TO_TOY`: How this differs from the synthetic baseline
3. **Source citations** with URLs and access dates
4. **Columns matching the `-toy` files exactly** for compatibility

## Quality Checklist
- [ ] File loads successfully in pandas
- [ ] No unexplained missing values
- [ ] Units match `-toy` file
- [ ] Column names identical to `-toy` file
- [ ] All data points have source citations
- [ ] Metadata header complete

## Handoff Format
When complete, each agent should report:
- ✅ File created with path
- ✅ Number of data points collected
- ✅ Primary sources used
- ⚠️ Data gaps or limitations
- 📊 Key differences from `-toy` baseline
