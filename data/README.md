# Data

All datasets for the Community Agri-PV simulation model.

## Structure

```
data/
├── parameters/               # Static parameters
│   ├── community/            # Farm profiles, land allocation, housing, building demand (4 files)
│   ├── costs/                # Capital and operating costs (4 files)
│   ├── crops/                # Crop coefficients, growth stages, processing, spoilage, storage (15 files)
│   ├── economic/             # Financing profiles, equipment lifespans (2 files)
│   ├── equipment/            # PV, wind, batteries, water treatment, irrigation, etc. (14 files)
│   ├── labor/                # Labor requirements and wages (3 files)
│   └── water/                # Water source metadata and aquifer parameters
├── precomputed/              # Layer 1 time-series outputs
│   ├── community_buildings/  # Daily community building energy and water demand (2 files)
│   ├── crop_yields/          # Seasonal yield kg/ha per crop (5 files)
│   ├── household/            # Daily household energy and water demand (2 files)
│   ├── irrigation_demand/    # Daily irrigation m³/ha per crop (5 files)
│   ├── microclimate/         # PV shade adjustments (2 files)
│   ├── pv_power/             # Normalized PV output kWh/kW (1 file)
│   ├── water_treatment/      # Treatment energy kWh/m³ by salinity (1 file)
│   ├── weather/              # Daily weather: temperature, radiation, wind (3 files)
│   └── wind_power/           # Normalized wind output kWh/kW (1 file)
├── prices/                   # Historical price time-series
│   ├── crops/                # Fresh crop prices (10 files)
│   ├── diesel/               # Diesel fuel prices (2 files)
│   ├── electricity/          # Grid electricity prices, subsidized and unsubsidized (4 files)
│   ├── inputs/               # Fertilizer costs (1 file)
│   ├── processed/            # Canned, dried, pickled, packaged product prices (16 files)
│   └── water/                # Municipal water prices (2 files)
└── scripts/                  # Data generation scripts (Layer 1)
    ├── generate_weather_data.py
    ├── generate_crop_parameters.py
    ├── generate_price_data.py
    ├── generate_irrigation_and_yields.py
    ├── generate_power_data.py
    ├── generate_household_demand.py
    ├── generate_community_building_demand.py
    └── generate_missing_processed_prices.py
```

## Dataset Counts

- **Parameters**: 42 CSV files across 7 categories
- **Precomputed**: 22 CSV files across 9 categories
- **Prices**: 35 CSV files across 6 categories
- **Total**: 99 CSV files

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
```

See [docs/arch/data.md](../docs/arch/data.md) for complete specifications.
