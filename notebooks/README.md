# Notebooks

Jupyter notebooks for interactive analysis, testing, and exploration of the Community Agri-PV simulation model.

## Current Notebooks

### `run_simulation.ipynb` ⭐
**Primary simulation runner** - Interactive notebook for running simulations and viewing results.

**Features:**
- Load and run simulations from scenario YAML files (defaults to `settings/mvp-settings.yaml`)
- View summary statistics in interactive tables
- Selectively display plots using checkboxes:
  - Monthly water use (agricultural vs community)
  - Monthly self-sufficiency
  - Monthly crop yields (by crop type)
  - Monthly water costs
  - Monthly crop revenue
  - Yearly comparison (4-panel overview)
- Export results to timestamped CSV files in `exports/`

**Quick Start:**
1. Open the notebook in Jupyter
2. Run all cells (Cell → Run All)
3. Use checkboxes to select which plots to view
4. Click "Show Selected Plots" button

## Exports Folder

The `exports/` folder contains CSV files exported from notebook analysis sessions. Files are timestamped for easy tracking (e.g., `monthly_metrics_20260205_143022.csv`).
