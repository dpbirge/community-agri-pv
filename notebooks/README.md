# Notebooks

Jupyter notebooks for interactive analysis, testing, and exploration of the Community Agri-PV simulation model.

## Current Notebooks

### `run_simulation.ipynb`

Primary simulation runner. Load and run simulations from scenario YAML files, view summary statistics in interactive tables, and selectively display plots using checkboxes (water use, self-sufficiency, crop yields, costs, revenue, yearly comparison). Export results to timestamped CSV files in `exports/`.

### `validations.ipynb`

Data validation notebook for verifying dataset integrity, checking metadata standards, and inspecting parameter distributions.

## Exports Folder

The `exports/` folder contains CSV files exported from notebook analysis sessions. Files are timestamped for easy tracking (e.g., `monthly_metrics_20260205_143022.csv`).
