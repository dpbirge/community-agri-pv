#!/usr/bin/env python3
"""Test script for Phase 5: Net income computation and plot.

Generates:
  - plot5_net_income.png — Revenue vs. operating costs with profit/loss shading
  - Monthly net income table (printed)
  - Summary statistics (printed)
"""

import os
import sys

# Ensure project root is on sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Use non-interactive backend before importing pyplot
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from src.settings.loader import load_scenario
from src.simulation.simulation import run_simulation
from src.simulation.data_loader import SimulationDataLoader
from src.simulation.metrics import compute_all_metrics, compute_net_income
from src.notebook_plotting import plot_net_farm_income


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

    # Create data loader for cost lookups
    print("Loading research price data...")
    data_loader = SimulationDataLoader(use_research_prices=True)

    # Compute all metrics (including monthly with cost categories)
    print("Computing metrics...")
    all_metrics = compute_all_metrics(state, data_loader=data_loader, scenario=scenario)
    print(f"  {len(all_metrics['monthly_metrics'])} monthly metric records")

    # --- Net Income Computation ---
    print("\nComputing net income...")
    net_income_data = compute_net_income(all_metrics['monthly_metrics'])

    # Print monthly net income table
    print("\n--- Monthly Net Income ---")
    print(f"{'Year-Month':<12} {'Revenue (USD)':>14} {'Cost (USD)':>14} "
          f"{'Net Income (USD)':>16} {'Margin (%)':>11}")
    print("-" * 69)
    for entry in net_income_data:
        ym = f"{entry['year']}-{entry['month']:02d}"
        print(f"{ym:<12} {entry['revenue_usd']:>14,.2f} {entry['cost_usd']:>14,.2f} "
              f"{entry['net_income_usd']:>16,.2f} {entry['operating_margin_pct']:>10.1f}%")

    # Identify positive and negative income months
    positive_months = [e for e in net_income_data if e['net_income_usd'] > 0]
    negative_months = [e for e in net_income_data if e['net_income_usd'] < 0]
    zero_months = [e for e in net_income_data if e['net_income_usd'] == 0]

    print(f"\n--- Income Breakdown ---")
    print(f"  Months with positive net income: {len(positive_months)}")
    if positive_months:
        for e in positive_months:
            ym = f"{e['year']}-{e['month']:02d}"
            print(f"    {ym}: +${e['net_income_usd']:,.2f} (margin {e['operating_margin_pct']:.1f}%)")

    print(f"  Months with negative net income: {len(negative_months)}")
    if negative_months:
        for e in negative_months:
            ym = f"{e['year']}-{e['month']:02d}"
            print(f"    {ym}: -${abs(e['net_income_usd']):,.2f}")

    print(f"  Months with zero net income:     {len(zero_months)}")

    # Summary statistics
    total_revenue = sum(e['revenue_usd'] for e in net_income_data)
    total_costs = sum(e['cost_usd'] for e in net_income_data)
    total_net_income = sum(e['net_income_usd'] for e in net_income_data)
    margins = [e['operating_margin_pct'] for e in net_income_data if e['revenue_usd'] > 0]
    avg_margin = sum(margins) / len(margins) if margins else 0.0

    print(f"\n--- Summary ---")
    print(f"  Total revenue:    ${total_revenue:,.2f}")
    print(f"  Total costs:      ${total_costs:,.2f}")
    print(f"  Total net income: ${total_net_income:,.2f}")
    print(f"  Average margin (harvest months only): {avg_margin:.1f}%")

    # --- Plot 5: Net Farm Income ---
    print("\nGenerating plot5: Net Farm Income...")
    fig = plot_net_farm_income(all_metrics)
    out_path = os.path.join(exports_dir, "plot5_net_income.png")
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {out_path}")

    print("\nSUCCESS: All Phase 5 outputs generated")


if __name__ == "__main__":
    main()
