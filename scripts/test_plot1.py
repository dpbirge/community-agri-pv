#!/usr/bin/env python3
"""Test script for Phase 2 plot additions.

Generates:
  - plot1_input_price_index.png  — Input prices normalized to base year = 100

Tests:
  - Diesel price loader (2015-2024)
  - Fertilizer cost loader (2015-2024)
  - Water and electricity price reference values
"""

import os
import sys

# Ensure project root is on sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Use non-interactive backend before importing pyplot
import matplotlib
matplotlib.use('Agg')

import datetime
from src.simulation.data_loader import SimulationDataLoader
from src.notebook_plotting import plot_input_price_index


def main():
    # Ensure exports directory exists
    exports_dir = os.path.join(project_root, "notebooks", "exports")
    os.makedirs(exports_dir, exist_ok=True)

    # Create data loader
    print("Loading data (research prices where available)...")
    data_loader = SimulationDataLoader(use_research_prices=True)
    print("  Data loader initialized.\n")

    # --- Test diesel price loader ---
    print("--- Diesel Prices (USD/liter) ---")
    for year in range(2015, 2025):
        d = datetime.date(year, 7, 1)
        price = data_loader.get_diesel_price_usd_liter(d)
        print(f"  {year}: ${price:.4f}/L")

    # --- Test fertilizer cost loader ---
    print("\n--- Fertilizer Costs (USD/ha) ---")
    for year in range(2015, 2025):
        d = datetime.date(year, 7, 1)
        cost = data_loader.get_fertilizer_cost_usd_ha(d)
        print(f"  {year}: ${cost:.2f}/ha")

    # --- Reference: water and electricity prices ---
    print("\n--- Municipal Water Prices (USD/m³, tier 3 subsidized) ---")
    for year in range(2015, 2025):
        price = data_loader.get_municipal_price_usd_m3(year, tier=3, pricing_regime="subsidized")
        print(f"  {year}: ${price:.4f}/m³")

    print("\n--- Grid Electricity Prices (USD/kWh, average) ---")
    for year in range(2015, 2025):
        d = datetime.date(year, 7, 1)
        price = data_loader.get_electricity_price_usd_kwh(d)
        print(f"  {year}: ${price:.4f}/kWh")

    # --- Plot 1: Input Price Index ---
    print("\nGenerating plot1: Input Price Index...")
    fig = plot_input_price_index(data_loader, base_year=2015, end_year=2024)
    out_path = os.path.join(exports_dir, "plot1_input_price_index.png")
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    import matplotlib.pyplot as plt
    plt.close(fig)
    print(f"  Saved: {out_path}")

    print("\nSUCCESS: All Phase 2 outputs generated")


if __name__ == "__main__":
    main()
