# Data Generation Orchestration Plan

**Date**: 2026-02-02
**Purpose**: Parallel data generation for Community Agri-PV model toy datasets
**Context**: Sinai Red Sea region, Egypt - 20 farms, 500 ha, hot arid climate

## Overview

This document provides task definitions for parallel data generation agents. Each agent will generate toy datasets for a specific category, following specifications in [data-organization.md](data-organization.md).

All agents should work independently and can be launched in parallel.

## Project Context Summary

- **Location**: Sinai Peninsula, Red Sea coast, Egypt (~28°N latitude)
- **Climate**: Hot, arid desert, minimal rainfall, high solar resource
- **Community**: 20 farms, 500 hectares farmland, ~150 population
- **Crops**: Tomato, Potato, Onion, Kale, Cucumber (multiple seasons/year for fast crops)
- **Time period**: 15 years weather (2010-2024), 10 years prices (2015-2024)
- **Irrigation**: Drip only (90% efficiency)
- **Energy**: Solar PV (3 densities), 3 wind turbine sizes, 100kW diesel backup, grid connection
- **Processing**: Fresh sales, packaged export to Europe, canned, dried/dehydrated

## Critical Specifications

### All Datasets Must Include:
1. **Metadata header block** with SOURCE, DATE, DESCRIPTION, UNITS, LOGIC, DEPENDENCIES, ASSUMPTIONS
2. **Filename suffix**: `-toy` for synthetic data
3. **Units clearly specified** for all numeric columns
4. **CSV format**: Human-readable, UTF-8 encoding

### Currency
- All prices in **USD**
- Document original currency (EGP, EUR) with conversion rates in metadata

### Egyptian-Specific Data Priorities
Research Egyptian sources for:
- Electricity prices (agricultural tariffs)
- Water prices (municipal)
- Diesel fuel prices
- Agricultural labor wages

Use global datasets for:
- Crop prices (FAO, USDA)
- Equipment costs and specifications
- Weather patterns (synthetic with regional characteristics)

---

## Task 1: Weather Data Generation

**Agent**: Weather Data Generator
**Output folder**: `data/precomputed/weather/`
**Deliverable**: `daily_weather_scenario_001-toy.csv`

### Specifications
- **Time range**: 2010-01-01 to 2024-12-31 (5,479 days)
- **Location**: Sinai Peninsula, Red Sea coast (~28°N, 34°E)
- **Climate characteristics**:
  - Hot arid desert (BWh in Köppen classification)
  - Summer: Very hot (40-45°C max), low humidity, high solar (7-8 kWh/m²/day)
  - Winter: Mild (20-25°C max), comfortable nights (10-15°C min)
  - Annual rainfall: <50mm, mostly Nov-Feb
  - Wind: Moderate, stronger in spring (3-5 m/s average, up to 8-10 m/s gusts)

### Required columns
- `date` (YYYY-MM-DD)
- `temp_max_c` (°C)
- `temp_min_c` (°C)
- `solar_irradiance_kwh_m2` (kWh/m²/day)
- `wind_speed_ms` (m/s, daily average)
- `precip_mm` (mm/day)
- `weather_scenario_id` (text: "001")

### Data generation approach
Use synthetic generation with realistic seasonal patterns:
1. Temperature: Sinusoidal annual cycle + daily variation + random noise
2. Solar: Latitude-based astronomical + cloud cover effects + seasonal variation
3. Wind: Seasonal patterns (stronger spring) + daily/weekly variation + random gusts
4. Precipitation: Rare events concentrated Nov-Feb, exponential distribution

### Quality checks
- Temperature ranges: Summer max 38-46°C, Winter max 18-26°C
- Solar ranges: Summer 6-8 kWh/m²/day, Winter 3-5 kWh/m²/day
- Wind: 2-6 m/s average, occasional gusts to 12 m/s
- Annual rainfall: 20-80mm total
- No missing values

### References
- NREL NSRDB for solar radiation patterns
- NASA POWER for regional climate data
- World Bank Climate Knowledge Portal for Egypt

---

## Task 2: Crop Parameters

**Agent**: Crop Parameters Generator
**Output folder**: `data/parameters/crops/`
**Deliverables**:
- `crop_coefficients-toy.csv`
- `growth_stages-toy.csv`
- `processing_specs-toy.csv`
- `spoilage_rates-toy.csv`

### Crop Coefficients (`crop_coefficients-toy.csv`)

**Crops**: tomato, potato, onion, kale, cucumber

**Columns**:
- `crop_name`
- `kc_initial` (dimensionless, at planting)
- `kc_mid` (dimensionless, at full canopy)
- `kc_end` (dimensionless, at harvest)
- `root_depth_m` (meters)
- `season_length_days` (days from planting to harvest)
- `water_stress_sensitivity` (high/medium/low)

**Source**: FAO Irrigation and Drainage Paper 56 (FAO-56), Table 12
**Adjustments**: Increase Kc by ~5-10% for hot arid conditions (advection effects)

### Growth Stages (`growth_stages-toy.csv`)

**Columns**:
- `crop_name`
- `stage` (initial/development/mid/late)
- `duration_days` (days in this stage)
- `kc` (average Kc for this stage)
- `water_stress_impact` (yield loss % per 10% water deficit)

**Total duration must match `season_length_days` in coefficients file**

### Processing Specs (`processing_specs-toy.csv`)

**Processing types**: fresh, packaged, canned, dried

**Columns**:
- `crop_name`
- `processing_type`
- `energy_kwh_per_kg` (processing energy)
- `labor_hours_per_kg` (labor requirement)
- `weight_loss_pct` (% mass lost during processing)
- `value_add_multiplier` (price multiplier vs fresh, e.g., 1.5 for dried)
- `processing_time_hours` (time from input to output)

**Notes**:
- Fresh: no processing (zeros except value_add = 1.0)
- Packaged: minimal processing (washing, sorting, boxing)
- Canned: moderate energy (heating, sealing), significant labor
- Dried: high energy (dehydration), high weight loss (80-90%), high value-add

### Spoilage Rates (`spoilage_rates-toy.csv`)

**Columns**:
- `product_type` (crop_name + processing_type, e.g., "tomato_fresh")
- `storage_condition` (ambient/climate_controlled)
- `spoilage_rate_pct_per_day` (% lost per day)
- `shelf_life_days` (max storage before total loss)

**Typical ranges**:
- Fresh produce, ambient: 2-5% per day, 7-14 days shelf life
- Fresh produce, climate-controlled: 0.5-2% per day, 21-45 days
- Dried: 0.01-0.1% per day, 365+ days
- Canned: <0.01% per day, 730+ days

---

## Task 3: Equipment Specifications

**Agent**: Equipment Specs Generator
**Output folder**: `data/parameters/equipment/`
**Deliverables**:
- `pv_systems-toy.csv`
- `batteries-toy.csv`
- `wind_turbines-toy.csv`
- `water_treatment-toy.csv`
- `processing_equipment-toy.csv`
- `equipment_failure_rates-toy.csv`

### PV Systems (`pv_systems-toy.csv`)

**Variants**: 3 installation densities (same panel type)
- Low: 30% ground coverage
- Medium: 50% ground coverage
- High: 80% ground coverage

**Columns**:
- `density_name` (low/medium/high)
- `ground_coverage_pct` (30/50/80)
- `panel_type` (same for all: "polycrystalline_standard")
- `module_efficiency` (decimal, ~0.18-0.20)
- `temp_coefficient_per_c` (decimal, ~-0.004 to -0.005)
- `system_losses_pct` (14-16% typical)
- `degradation_rate_per_year` (0.005-0.008)
- `tilt_angle_deg` (28 for Sinai latitude)
- `azimuth_deg` (180 = south-facing)
- `panel_height_m` (3.0 for all)
- `lifespan_years` (25-30)

### Wind Turbines (`wind_turbines-toy.csv`)

**Variants**: 3 microgrid-scale turbines with different characteristics

**Columns**:
- `turbine_name` (small/medium/large)
- `rated_capacity_kw` (e.g., 10/30/60 kW)
- `cut_in_speed_ms` (wind speed to start generating)
- `rated_speed_ms` (wind speed for rated output)
- `cut_out_speed_ms` (wind speed to shut down for safety)
- `hub_height_m` (tower height)
- `rotor_diameter_m`
- `capacity_factor_typical` (% of rated capacity, annual average)
- `lifespan_years` (20-25)

**Trade-offs**:
- Small: Lower cost, lower cut-in, works in light winds, lower efficiency
- Medium: Balanced performance
- Large: Higher capacity factor, higher cut-in, better in strong winds, higher cost per kW

### Water Treatment (`water_treatment-toy.csv`)

**Variants**: 3 brackish water salinity levels

**Columns**:
- `salinity_level` (light/moderate/heavy)
- `tds_ppm` (1000-3000 / 3000-10000 / 10000-20000)
- `energy_kwh_per_m3` (desalination energy requirement)
- `membrane_life_months` (membrane replacement interval)
- `recovery_rate_pct` (% of input water recovered as freshwater)
- `capital_cost_per_m3_day` ($/m³/day capacity)
- `maintenance_cost_per_m3` ($/m³ operating cost)

**Energy ranges** (brackish RO typical):
- Light: 0.5-1.5 kWh/m³
- Moderate: 1.5-3.0 kWh/m³
- Heavy: 3.0-5.0 kWh/m³

### Processing Equipment (`processing_equipment-toy.csv`)

**Types**: packaged, canned, dried

**Columns**:
- `equipment_type`
- `capacity_kg_per_day` (throughput)
- `energy_kw_continuous` (power draw during operation)
- `capital_cost_usd`
- `maintenance_cost_per_year_usd`
- `lifespan_years`

**Sizing**: Capacities should handle ~10-20% of peak daily harvest (to be determined from crop yields)

### Equipment Failure Rates (`equipment_failure_rates-toy.csv`)

**Columns**:
- `equipment_type` (pv_inverter, battery, water_pump, treatment_plant, processing_equipment, diesel_generator)
- `mtbf_hours` (mean time between failures)
- `failure_probability_per_year` (calculated: 8760/MTBF)
- `repair_cost_usd` (typical repair cost)
- `downtime_days` (typical repair duration)
- `maintenance_interval_days` (preventive maintenance frequency)

**Use conservative estimates for hot, dusty desert environment**

---

## Task 4: Price Time-Series

**Agent**: Price Data Generator
**Output folder**: `data/prices/`
**Deliverables**:
- `crops/historical_[crop]_prices-toy.csv` (5 files)
- `processed/historical_[processed]_prices-toy.csv` (multiple files)
- `electricity/historical_grid_electricity_prices-toy.csv`
- `water/historical_municipal_water_prices-toy.csv`
- `diesel/historical_diesel_prices-toy.csv`

### Time Range
- **Crop/processed prices**: 2015-01-01 to 2024-12-31 (10 years, monthly frequency)
- **Electricity/water/diesel**: 2015-01-01 to 2024-12-31 (10 years, monthly or annual)

### Crop Prices (5 files, one per crop)

**Columns**:
- `date` (monthly, first of month)
- `usd_per_kg` (wholesale price in USD)
- `season` (winter/spring/summer/fall)
- `market_condition` (low/medium/high relative to annual mean)

**Data sources**:
- FAO GIEWS (Global Information and Early Warning System)
- USDA Global Agricultural Trade System
- World Bank Commodity Price Data

**Characteristics**:
- Seasonal variation: Low prices at harvest peaks, high in off-season
- Year-to-year volatility: ~20-30% coefficient of variation
- Synthetic generation: Use sinusoidal seasonality + AR(1) process + random shocks

**Example price ranges** (wholesale, global markets):
- Tomato: $0.50-$1.20/kg (fresh)
- Potato: $0.30-$0.80/kg
- Onion: $0.25-$0.70/kg
- Kale: $1.50-$3.00/kg (higher value)
- Cucumber: $0.60-$1.40/kg

### Processed Product Prices

**Types**: dried tomato, canned tomato, dried kale, pickled cucumber, etc.

**Columns**: Same as crop prices

**Price relationship**: Processed price = Raw price × value_add_multiplier (from processing_specs)
- Add stochastic variation in spread (processing costs vary)

### Electricity Prices (`electricity/historical_grid_electricity_prices-toy.csv`)

**Source**: Egyptian electricity authority, agricultural tariff schedule

**Columns**:
- `date` (monthly)
- `usd_per_kwh_offpeak` (off-peak rate)
- `usd_per_kwh_peak` (peak rate, if time-of-use pricing)
- `usd_per_kwh_avg_daily` (weighted daily average)
- `rate_schedule` (standard/summer/winter if seasonal rates)
- `egp_per_kwh_original` (original EGP price)
- `usd_egp_exchange_rate` (conversion rate used)

**Research Egyptian agricultural electricity tariffs**. If not available, use regional comparisons (Jordan, Saudi Arabia agricultural rates).

**Typical range**: $0.06-$0.12/kWh for agricultural users in MENA region

### Water Prices (`water/historical_municipal_water_prices-toy.csv`)

**Source**: Egyptian water authority, municipal utility rates

**Columns**:
- `date` (monthly or annual if rates are stable)
- `usd_per_m3` (price per cubic meter)
- `egp_per_m3_original`
- `usd_egp_exchange_rate`
- `rate_category` (agricultural/bulk)

**Research Egyptian municipal water pricing for agricultural users**

**Typical range**: $0.20-$0.80/m³ for treated municipal water in water-scarce regions

### Diesel Prices (`diesel/historical_diesel_prices-toy.csv`)

**Source**: Egyptian petroleum authority, World Bank commodity prices

**Columns**:
- `date` (monthly)
- `usd_per_liter`
- `egp_per_liter_original`
- `usd_egp_exchange_rate`

**Research Egyptian diesel prices 2015-2024 (subsidies removed gradually)**

**Typical range**: $0.40-$1.00/liter (varies significantly with oil prices and subsidies)

---

## Task 5: Labor Parameters

**Agent**: Labor Data Generator
**Output folder**: `data/parameters/labor/`
**Deliverables**:
- `labor_requirements-toy.csv`
- `labor_wages-toy.csv`

### Labor Requirements (`labor_requirements-toy.csv`)

**Activity categories**:
- Field work: planting, weeding, harvesting, irrigation management
- Management: planning, coordination, sales, administration
- Canning: processing operations
- Packaging: sorting, packing for export
- Maintenance: equipment, facilities
- Logistics: transport, loading/unloading

**Columns**:
- `activity_type`
- `unit` (per_hectare, per_kg, per_day, per_equipment)
- `hours_per_unit` (labor requirement)
- `skill_level` (unskilled/semi-skilled/skilled)
- `seasonality` (year_round/seasonal)

**Sources**:
- FAO agricultural labor benchmarks
- Regional agricultural extension data
- Small-farm labor studies for similar crops

### Labor Wages (`labor_wages-toy.csv`)

**Worker categories**:
- Field worker (unskilled)
- Field supervisor (semi-skilled)
- Processing worker (semi-skilled)
- Equipment operator (skilled)
- Manager/administrator (skilled)

**Columns**:
- `worker_category`
- `skill_level`
- `usd_per_hour` (wage rate)
- `egp_per_hour_original` (Egyptian wages)
- `usd_egp_exchange_rate`
- `typical_hours_per_week`

**Research Egyptian agricultural wages by skill level**

**Guidance**: Egypt has relatively low agricultural wages compared to global averages. Look for:
- Egyptian Ministry of Manpower data
- ILO (International Labour Organization) wage statistics
- Agricultural sector surveys

---

## Task 6: Community Parameters

**Agent**: Community Data Generator
**Output folder**: `data/parameters/community/`
**Deliverables**:
- `farm_profiles-toy.csv`
- `land_allocation-toy.csv`
- `housing_energy_water-toy.csv`

### Farm Profiles (`farm_profiles-toy.csv`)

**Profile types**: conservative, moderate, risk_tolerant

**Columns**:
- `profile_name`
- `farm_size_ha_mean` (mean farm size for this profile)
- `farm_size_ha_std` (standard deviation for variation)
- `yield_factor_mean` (soil quality multiplier, 0.8-1.2)
- `yield_factor_std`
- `starting_capital_usd_mean` (initial cash reserves)
- `starting_capital_usd_std`
- `risk_tolerance` (description of economic behavior)

**Distribution across 20 farms**:
- 8 conservative (40%)
- 8 moderate (40%)
- 4 risk-tolerant (20%)

**Total farmland constraint**: All farms must sum to ~500 ha

### Land Allocation (`land_allocation-toy.csv`)

**Community area**: 25 km² (2,500 hectares)

**Columns**:
- `land_use_type`
- `area_ha`
- `percentage_of_total`
- `description`

**Categories**:
- Farmland (irrigated crops): 500 ha
- Housing and buildings: TBD
- Solar arrays (ground-mounted, non-agri-PV): TBD
- Agri-PV structures (over farmland): Covered by farmland
- Roads and infrastructure: TBD
- Buffer zones: TBD
- Undeveloped/reserve: Remainder

### Housing Energy and Water (`housing_energy_water-toy.csv`)

**Population**: 150 people (~30-40 households)

**Columns**:
- `category` (household_type)
- `occupants_per_household`
- `kwh_per_household_per_day` (electricity demand)
- `m3_per_household_per_day` (water demand)
- `equipment_list` (typical appliances)

**Energy demand per household**:
- Small AC unit: 1-2 kW, 6-10 hours/day = 8-12 kWh/day
- Refrigerator: 0.1-0.2 kW continuous = 2.4-4.8 kWh/day
- Lighting: 5-10 LED bulbs × 4 hours = 0.4-0.8 kWh/day
- Other (TV, fans, charging): 2-3 kWh/day
- **Total: 13-20 kWh/household/day**

**Water demand per household**:
- Drinking, cooking, washing: 50-100 liters/person/day
- **Total: ~0.3-0.6 m³/household/day**

---

## Task 7: Cost Parameters

**Agent**: Cost Data Generator
**Output folder**: `data/parameters/costs/`
**Deliverables**:
- `capital_costs-toy.csv`
- `operating_costs-toy.csv`

### Capital Costs (`capital_costs-toy.csv`)

**Columns**:
- `equipment_type`
- `cost_metric` (per_kw, per_kwh, per_m3_day, per_unit)
- `usd_per_unit` (capital cost)
- `installation_cost_pct` (% of equipment cost for installation)
- `source` (NREL, IRENA, manufacturer, etc.)
- `year_basis` (which year's prices)

**Equipment types**:
- PV system ($/kW installed)
- Battery storage ($/kWh capacity)
- Wind turbine ($/kW rated)
- Water treatment plant ($/m³/day capacity)
- Diesel generator ($/kW)
- Processing equipment (per unit or $/kg/day capacity)
- Water storage tanks ($/m³ capacity)
- Irrigation system ($/hectare)

**Sources**:
- NREL Annual Technology Baseline (ATB) for renewable energy
- IRENA Renewable Cost Database
- Industry reports for water treatment and processing

**Normalize to 2024 USD**

### Operating Costs (`operating_costs-toy.csv`)

**Columns**:
- `equipment_type`
- `cost_metric` (per_kw_per_year, per_m3, per_kwh_throughput, etc.)
- `usd_per_unit` (annual O&M cost)
- `description` (what's included: maintenance, consumables, etc.)

**Include**:
- PV O&M ($/kW/year): cleaning, inverter maintenance
- Battery O&M ($/kWh/year): monitoring, capacity testing
- Wind O&M ($/kW/year): higher than PV due to moving parts
- Water treatment O&M: membrane replacement, chemicals, energy ($/m³)
- Diesel generator O&M: oil changes, filters ($/kWh generated)
- Processing O&M: cleaning, consumables ($/kg processed)

---

## Task 8: Pre-computed PV and Wind Power

**Agent**: Power Generation Calculator
**Output folder**: `data/precomputed/pv_power/` and `data/precomputed/wind_power/`
**Dependencies**: Requires `weather/daily_weather_scenario_001-toy.csv` to be completed first
**Deliverables**:
- `pv_power/pv_normalized_kwh_per_kw_daily-toy.csv`
- `wind_power/wind_normalized_kwh_per_kw_daily-toy.csv`

### PV Power (`pv_normalized_kwh_per_kw_daily-toy.csv`)

**Computation method**: Use pvlib-python library

**Columns**:
- `weather_scenario_id` ("001")
- `date`
- `density_variant` (low/medium/high - affects microclimate, compute all 3)
- `kwh_per_kw_per_day` (normalized daily output)
- `capacity_factor` (daily capacity factor, 0-1)

**PV system specs** (from equipment specs):
- Fixed-tilt 28° south-facing
- Module efficiency ~19%
- Temperature coefficient -0.4%/°C
- System losses 15%

**Apply microclimate adjustments** for agri-PV:
- High density: Lower irradiance (panel shading), lower temps (shading effect)
- Low density: Full irradiance, higher temps (less shading)

### Wind Power (`wind_normalized_kwh_per_kw_daily-toy.csv`)

**Computation method**: Power curve modeling

**Columns**:
- `weather_scenario_id` ("001")
- `date`
- `turbine_variant` (small/medium/large)
- `kwh_per_kw_per_day` (normalized daily output)
- `capacity_factor`

**Use power curves** from equipment specs (cut-in, rated, cut-out speeds)

**Typical capacity factors**:
- Small: 15-25% (works in light winds)
- Medium: 20-30%
- Large: 25-35% (better in strong winds)

---

## Task 9: Pre-computed Irrigation Demand and Crop Yields

**Agent**: Crop Water Calculator
**Output folder**: `data/precomputed/irrigation_demand/` and `data/precomputed/crop_yields/`
**Dependencies**: Requires weather data and crop parameters
**Deliverables**:
- `irrigation_demand/irrigation_m3_per_ha_[crop]-toy.csv` (5 files)
- `crop_yields/yield_kg_per_ha_[crop]-toy.csv` (5 files)

### Irrigation Demand Files

**Computation**: FAO Penman-Monteith ET₀ + crop coefficients

**Columns**:
- `weather_scenario_id` ("001")
- `planting_date` (multiple planting dates per crop to test)
- `crop_day` (days since planting, 1 to season_length)
- `calendar_date` (actual date)
- `growth_stage` (initial/development/mid/late)
- `kc` (crop coefficient for this day)
- `et0_mm` (reference evapotranspiration)
- `etc_mm` (crop evapotranspiration = ET₀ × Kc)
- `irrigation_m3_per_ha_per_day` (ETc × 10 to convert mm to m³/ha)

**Planting dates to model**:
- Vary planting dates throughout year to capture seasonal effects
- For multi-season crops: 3-4 planting dates per year
- For single-season crops: 2-3 planting dates

**Include drip irrigation efficiency**: Apply 90% efficiency (10% losses)

### Crop Yield Files

**Computation**: Baseline yield × weather effects × water stress factor

**Columns**:
- `weather_scenario_id` ("001")
- `planting_date`
- `harvest_date`
- `yield_kg_per_ha` (total harvest)
- `season_length_actual_days`
- `weather_stress_factor` (yield reduction from weather, 0.8-1.2)
- `water_stress_factor` (assume 1.0 for fully irrigated)

**Baseline yields** (well-managed, drip-irrigated hot arid conditions):
- Tomato: 60,000-80,000 kg/ha
- Potato: 30,000-40,000 kg/ha
- Onion: 40,000-50,000 kg/ha
- Kale: 15,000-25,000 kg/ha
- Cucumber: 40,000-60,000 kg/ha

**Weather stress factors**:
- Extreme heat during sensitive stages reduces yield (5-20%)
- Cool periods may extend season but can reduce yield slightly

---

## Task 10: Water Treatment Energy Curves

**Agent**: Water Treatment Calculator
**Output folder**: `data/precomputed/water_treatment/`
**Deliverable**: `treatment_kwh_per_m3-toy.csv`

### Specifications

**Columns**:
- `salinity_level` (light/moderate/heavy)
- `tds_ppm_min` (lower bound of range)
- `tds_ppm_max` (upper bound)
- `energy_kwh_per_m3_min` (minimum energy at best efficiency)
- `energy_kwh_per_m3_typical` (typical operating energy)
- `energy_kwh_per_m3_max` (maximum energy at worst efficiency)
- `recovery_rate_pct` (% of feedwater recovered)
- `brine_disposal_m3_per_m3_product` (brine waste volume)

**Technology**: Brackish water reverse osmosis (BWRO)

**Energy relationships**:
- Light (1,000-3,000 ppm): 0.5-1.5 kWh/m³
- Moderate (3,000-10,000 ppm): 1.5-3.0 kWh/m³
- Heavy (10,000-20,000 ppm): 3.0-5.0 kWh/m³

**Recovery rates**:
- Light: 85-90%
- Moderate: 75-85%
- Heavy: 65-75%

**Sources**:
- DOE desalination databases
- Membrane manufacturer specifications
- Academic papers on BWRO energy consumption

---

## Task 11: Microclimate Adjustments

**Agent**: Microclimate Calculator
**Output folder**: `data/precomputed/microclimate/`
**Deliverable**: `pv_shade_adjustments-toy.csv`

### Specifications

**Purpose**: Quantify how agri-PV panels affect temperature and light below panels

**Columns**:
- `density_variant` (low/medium/high: 30%/50%/80% coverage)
- `temp_adjustment_c` (temperature reduction below panels, °C)
- `irradiance_multiplier` (fraction of full sun reaching crops, 0-1)
- `wind_speed_multiplier` (wind reduction below panels, 0-1)
- `evapotranspiration_multiplier` (combined effect on ET, 0-1)

**Typical adjustments** (based on agri-PV literature):
- High density (80%):
  - Temp reduction: -2 to -4°C
  - Irradiance: 30-40% of full sun
  - Wind: 70% of ambient
  - ET reduction: 20-30% (cooler + less radiation)
- Medium density (50%):
  - Temp reduction: -1 to -2°C
  - Irradiance: 55-65% of full sun
  - Wind: 85% of ambient
  - ET reduction: 10-15%
- Low density (30%):
  - Temp reduction: -0.5 to -1°C
  - Irradiance: 75-85% of full sun
  - Wind: 95% of ambient
  - ET reduction: 5-10%

**These adjustments feed into**:
- Reduced irrigation demand under denser PV
- Potential crop yield impacts (shade-tolerant crops benefit, sun-loving crops penalized)
- Temperature stress reduction in extreme heat

**Sources**:
- Academic agri-PV studies (Germany, Japan, USA trials)
- Fraunhofer ISE agri-PV research
- University of Arizona agri-PV microclimate studies

---

## Coordination Notes

### Task Dependencies
- **Tasks 1-7**: Independent, can run in parallel
- **Task 8**: Depends on Task 1 (weather data)
- **Task 9**: Depends on Task 1 (weather) and Task 2 (crop parameters)
- **Tasks 10-11**: Independent of others

### Recommended Launch Order
1. **Wave 1** (launch immediately, fully independent):
   - Task 1: Weather
   - Task 2: Crop parameters
   - Task 3: Equipment specs
   - Task 4: Price time-series
   - Task 5: Labor parameters
   - Task 6: Community parameters
   - Task 7: Cost parameters
   - Task 10: Water treatment
   - Task 11: Microclimate

2. **Wave 2** (launch after Task 1 completes):
   - Task 8: PV and wind power
   - Task 9: Irrigation demand and crop yields

### Quality Assurance
Each agent should:
1. **Validate outputs** against specified ranges
2. **Check for missing values** (none allowed)
3. **Verify units** match specifications
4. **Include complete metadata** headers
5. **Test CSV loading** in Python/pandas before finalizing

### Handoff Format
When complete, each agent should report:
- ✅ Files created (list with file sizes)
- ✅ Quality checks passed
- ⚠️ Any assumptions made
- ⚠️ Any data sources that could be improved
- 📊 Key statistics (means, ranges, totals)

---

## Success Criteria

All tasks complete when:
- [ ] All CSV files exist in correct folders
- [ ] All files have complete metadata headers
- [ ] No missing values in any dataset
- [ ] Units are consistent and documented
- [ ] Files load successfully in pandas/Python
- [ ] Cross-file references are valid (e.g., crop names match across files)
- [ ] Egyptian-specific data sources documented for electricity, water, diesel, labor
- [ ] Currency conversions documented with exchange rates

---

## References

- [Data Organization Specification](data-organization.md)
- [Community Model Plan](community-model-plan.md)
- FAO Irrigation and Drainage Paper 56: http://www.fao.org/3/x0490e/x0490e00.htm
- NREL Annual Technology Baseline: https://atb.nrel.gov/
- Egyptian Electricity Holding Company: https://www.eehc.gov.eg/
- FAO GIEWS Price Data: https://www.fao.org/giews/food-prices/home/en/
