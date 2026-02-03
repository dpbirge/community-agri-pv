# Data Folder

This folder contains all datasets for the Community Agri-PV simulation model, organized by computational layer and data type.

## Folder Structure

- **`precomputed/`** - Layer 1 pre-computed physical libraries (time-series)
- **`parameters/`** - Static parameters for crops, equipment, labor, costs
- **`prices/`** - Historical price time-series for economic modeling

Settings and configurations are in the **`settings/`** folder at the repo root.

## Data Quality Indicators

Filenames use suffixes to indicate data source/quality:
- **`-toy`**: Synthetic data for initial development and testing
- **`-real`**: Empirical data from validated sources

## Metadata Standards

Every CSV file MUST include a header block with:
```csv
# SOURCE: Where the data came from
# DATE: When file was created/updated
# DESCRIPTION: What the data represents
# UNITS: Units for each column
# LOGIC: How values were calculated/generated
# DEPENDENCIES: Other files this depends on
# ASSUMPTIONS: Key assumptions made
```

## Documentation

See [docs/planning/data-organization.md](../docs/planning/data-organization.md) for complete specifications.
