# Notebooks

Jupyter notebooks for interactive analysis, testing, and exploration of the Community Agri-PV simulation model.

### `run_simulation.ipynb`

Primary simulation runner. Loads and runs simulations from scenario YAML files, displays summary statistics in interactive tables, and provides checkbox-based plot selection (water use, self-sufficiency, crop yields, costs, revenue, yearly comparison). Exports results to timestamped CSV files in `exports/`.

### `validations.ipynb`

Data validation notebook for verifying dataset integrity, checking metadata standards, and inspecting parameter distributions.

## Exports

The `exports/` folder contains CSV files and PNG plots exported from notebook analysis sessions. Files are timestamped for tracking (e.g., `monthly_metrics_20260205_143022.csv`).
