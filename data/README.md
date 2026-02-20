# Data

All datasets for the Community Agri-PV simulation model. 102 CSV files organized into three categories plus 8 data generation scripts.

## Structure

```
data/
├── parameters/               # Static parameters (45 CSV files)
│   ├── community/            # Farm profiles, land allocation, housing, building demand (4 files)
│   ├── costs/                # Capital, operating, and reference costs (5 files)
│   ├── crops/                # Crop coefficients, growth stages, processing, spoilage, storage, salinity (15 files)
│   ├── economic/             # Financing profiles, equipment lifespans, Monte Carlo defaults (3 files)
│   ├── equipment/            # PV, wind, batteries, wells, pumps, generators, processing, packaging (15 files)
│   └── labor/                # Labor requirements and wages (3 files)
├── precomputed/              # Layer 1 time-series outputs (22 CSV files)
│   ├── community_buildings/  # Daily community building energy and water demand (2 files)
│   ├── crop_yields/          # Seasonal yield kg/ha per crop (5 files)
│   ├── household/            # Daily household energy and water demand (2 files)
│   ├── irrigation_demand/    # Daily irrigation m³/ha per crop (5 files)
│   ├── microclimate/         # PV shade adjustments (2 files)
│   ├── pv_power/             # Normalized PV output kWh/kW (1 file)
│   ├── water_treatment/      # Treatment energy kWh/m³ by salinity (1 file)
│   ├── weather/              # Daily weather: temperature, radiation, wind (3 files)
│   └── wind_power/           # Normalized wind output kWh/kW (1 file)
├── prices/                   # Historical price time-series (35 CSV files)
│   ├── crops/                # Fresh crop prices, toy + research (10 files)
│   ├── diesel/               # Diesel fuel prices (2 files)
│   ├── electricity/          # Grid electricity prices, subsidized and unsubsidized (4 files)
│   ├── inputs/               # Fertilizer costs (1 file)
│   ├── processed/            # Canned, dried, pickled, packaged product prices (16 files)
│   └── water/                # Municipal water prices (2 files)
└── scripts/                  # Data generation scripts (Layer 1, 8 Python files)
    ├── generate_weather_data.py              # 15-year synthetic weather for Sinai (~28N, 34E)
    ├── generate_crop_parameters.py           # Crop coefficients, growth stages, processing specs
    ├── generate_price_data.py                # Historical price time-series
    ├── generate_irrigation_and_yields.py     # FAO Penman-Monteith irrigation and yield calculations
    ├── generate_power_data.py                # PV and wind normalized power output
    ├── generate_household_demand.py          # Household energy and water demand
    ├── generate_community_building_demand.py # Community building energy and water demand
    └── generate_missing_processed_prices.py  # Fill gaps in processed product price data
```

## Data Quality Suffixes

- **`-toy`**: Synthetic data for development
- **`-research`**: Empirically-grounded data from literature
- **`-real`**: Measured data from validated sources (planned)

## Metadata Standards

Every CSV includes header comments:
```csv
# SOURCE: Where the data came from
# DATE: When file was created/updated
# DESCRIPTION: What the data represents
# UNITS: Units for each column
# LOGIC: How values were calculated
```

## Regenerating Data

```bash
python data/scripts/generate_weather_data.py
python data/scripts/generate_crop_parameters.py
python data/scripts/generate_price_data.py
python data/scripts/generate_irrigation_and_yields.py
python data/scripts/generate_power_data.py
python data/scripts/generate_household_demand.py
python data/scripts/generate_community_building_demand.py
python data/scripts/generate_missing_processed_prices.py
```


See [docs/arch/data.md](../docs/arch/data.md) for complete data specifications.
