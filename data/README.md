# Data

All datasets for the Community Agri-PV simulation model.

## Structure

```
data/
├── parameters/               # Static parameters
│   ├── community/            # Farm profiles, land allocation, housing (3 files)
│   ├── costs/                # Capital and operating costs (3 files)
│   ├── crops/                # Crop coefficients, growth stages, processing specs (9 files)
│   ├── economic/             # Financing profiles (1 file)
│   ├── equipment/            # PV, wind, batteries, water treatment, irrigation, etc. (15 files)
│   ├── labor/                # Labor requirements and wages (3 files)
│   └── water/                # Water source metadata and aquifer parameters
├── precomputed/              # Layer 1 time-series outputs
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
│   ├── electricity/          # Grid electricity prices (2 files)
│   ├── inputs/               # Fertilizer costs (1 file)
│   ├── processed/            # Processed product prices (11 files)
│   └── water/                # Municipal water prices (2 files)
└── scripts/                  # Data generation scripts (Layer 1)
    ├── generate_weather_data.py
    ├── generate_crop_parameters.py
    ├── generate_price_data.py
    ├── generate_irrigation_and_yields.py
    ├── generate_power_data.py
    └── generate_household_demand.py
```

## Dataset Counts

- **Parameters**: 35 files across 7 categories
- **Precomputed**: 20 files across 8 categories
- **Prices**: 28 files across 6 categories
- **Total**: 78 CSV files + 1 YAML metadata file

## Data Quality Suffixes

- **`-toy`**: Synthetic data for development (50 files complete)
- **`-research`**: Empirically-grounded data from literature (14 files in progress)
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
```

See [docs/architecture/data.md](../docs/architecture/data.md) for complete specifications.
