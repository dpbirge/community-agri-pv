#!/usr/bin/env python3
"""Test script for Phase 1 plot/table additions.

Generates:
  - plot4a_crop_prices.png       — Crop price history (farmgate)
  - plot4b_revenue_by_crop.png   — Monthly revenue stacked by crop
  - Revenue diversification table (printed)
  - Revenue concentration metrics (printed)
"""

import os
import sys

# Ensure project root is on sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Use non-interactive backend before importing pyplot
import matplotlib
matplotlib.use('Agg')

from src.settings.loader import load_scenario
from src.simulation.simulation import run_simulation
from src.simulation.data_loader import SimulationDataLoader
from src.simulation.metrics import compute_all_metrics, compute_revenue_concentration
from src.notebook_plotting import (
    plot_crop_price_history,
    plot_monthly_revenue_by_crop,
    create_revenue_diversification_table,
)


def main():
    # Ensure exports directory exists
    exports_dir = os.path.join(project_root, "notebooks", "exports")
    os.makedirs(exports_dir, exist_ok=True)

    # Load scenario and run simulation
    scenario_path = os.path.join(project_root, "settings", "mvp-settings.yaml")
    print(f"Loading scenario: {scenario_path}")
    scenario = load_scenario(scenario_path)

    print("Running simulation...")
    state = run_simulation(scenario, verbose=False)
    print(f"  Simulation complete: {len(state.yearly_metrics)} yearly metric records")

    # Compute metrics
    print("Computing metrics...")
    all_metrics = compute_all_metrics(state)

    # Create data loader for price lookups
    print("Loading research price data...")
    data_loader = SimulationDataLoader(use_research_prices=True)

    # --- Plot 4a: Crop Price History ---
    print("\nGenerating plot4a: Crop Price History...")
    fig_prices = plot_crop_price_history(data_loader, start_year=2015, end_year=2024)
    out_path = os.path.join(exports_dir, "plot4a_crop_prices.png")
    fig_prices.savefig(out_path, dpi=150, bbox_inches='tight')
    import matplotlib.pyplot as plt
    plt.close(fig_prices)
    print(f"  Saved: {out_path}")

    # --- Plot 4b: Monthly Revenue by Crop ---
    print("Generating plot4b: Monthly Revenue by Crop...")
    fig_revenue = plot_monthly_revenue_by_crop(all_metrics)
    out_path = os.path.join(exports_dir, "plot4b_revenue_by_crop.png")
    fig_revenue.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig_revenue)
    print(f"  Saved: {out_path}")

    # --- Table 2: Revenue Diversification ---
    print("\n--- Revenue Diversification Table ---")
    df = create_revenue_diversification_table(all_metrics, data_loader, scenario)
    print(df.to_string(index=False))

    # --- Revenue Concentration ---
    print("\n--- Revenue Concentration by Year ---")
    concentration = compute_revenue_concentration(state.yearly_metrics)
    for entry in concentration:
        print(f"  {entry['year']} | Farm: {entry['farm_id']} | "
              f"Concentration: {entry['concentration_pct']:.1f}% | "
              f"Dominant: {entry['dominant_crop']}")

    print("\nSUCCESS: All Phase 1 outputs generated")


if __name__ == "__main__":
    main()
