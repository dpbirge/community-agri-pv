# Community Agri-PV Simulation Model

An educational simulation tool for farming communities exploring co-ownership models for water, energy, and agricultural systems. Simulates a collective farm in the Sinai Peninsula, Egypt (hot arid climate, year-round irrigation) to help communities understand trade-offs between infrastructure configurations, policies, and risk management strategies.

Uses a three-layer architecture: pre-computed physical libraries (Layer 1), scenario configuration with policies across multiple domains (Layer 2), and daily time-step simulation with water allocation, energy dispatch, crop processing, market sales, economic tracking, and post-simulation assessment and metrics (Layer 3).

## Project Status

Layer 1 data generation is operational. The simulation engine (Layer 3) and scenario configuration system (Layer 2) are under development.

## Directory Structure

```text
/data          - Pre-computed data libraries (Layer 1) organized by domain
/docs          - Project documentation (methods, validation, plans, code review)
/notebooks     - User-facing Jupyter notebooks for running and analyzing simulations
/scripts       - Utility scripts for project-level tasks
/settings      - Scenario configuration files (Layer 2)
/specs         - Simulation design specifications
/src           - Simulation engine source code (Layer 3)
/testing       - Test suites
```

## Tech Stack

- Python 3.12+
- pandas, numpy (data generation and analysis)
- Jupyter notebooks (user interface)

## Key Specifications

- **Location**: Sinai Peninsula, Egypt (~28N, 34E), BWh climate
- **Weather source**: NASA POWER API (MERRA-2 reanalysis, 2010-2024)
- **Crops**: tomato, potato, onion, kale, cucumber
- **Energy**: agri-PV (low/medium/high density), wind turbines, batteries, diesel generators
- **Water**: groundwater wells, municipal supply, brackish water treatment (BWRO)

## Data Suffixes

CSV files use suffixes to indicate data quality:

- `-research` — derived from peer-reviewed sources (NASA, FAO, NREL, IRENA)
- `-toy` — synthetic or simplified data for early development and testing
