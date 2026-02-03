# Data

All datasets for the Community Agri-PV simulation model.

## Structure

```
data/
├── precomputed/              # Layer 1 time-series outputs
│   ├── weather/              # Daily weather (temperature, radiation, wind)
│   ├── irrigation_demand/    # Daily irrigation m3/ha per crop
│   ├── crop_yields/          # Seasonal yield kg/ha per crop
│   ├── pv_power/             # Normalized PV output kWh/kW
│   ├── wind_power/           # Normalized wind output kWh/kW
│   ├── microclimate/         # PV shade adjustments
│   └── water_treatment/      # Treatment energy kWh/m3 by salinity
├── parameters/               # Static parameters
│   ├── crops/                # Crop coefficients, growth stages, processing specs
│   ├── equipment/            # Wind turbines, water treatment specs
│   ├── labor/                # Labor requirements and wages
│   ├── community/            # Farm profiles, land allocation, housing
│   └── costs/                # Capital and operating costs
├── prices/                   # Historical price time-series
│   ├── crops/                # Fresh crop prices
│   ├── processed/            # Processed product prices
│   ├── electricity/          # Grid electricity prices
│   ├── water/                # Municipal water prices
│   └── diesel/               # Diesel fuel prices
└── scripts/                  # Data generation scripts (Layer 1)
    ├── generate_weather_data.py
    ├── generate_crop_parameters.py
    ├── generate_price_data.py
    ├── generate_irrigation_and_yields.py
    ├── generate_power_data.py
    └── generate_household_demand.py
```

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
```

See [docs/planning/data-organization.md](../docs/planning/data-organization.md) for complete specifications.
