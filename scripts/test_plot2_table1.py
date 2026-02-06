#!/usr/bin/env python3
"""Test script for Phase 3 plot/table additions.

Generates:
  - plot2_effective_vs_market.png  — Self-owned blended vs. government municipal water cost
  - Cost comparison table (printed)

Tests:
  - compute_blended_water_cost_per_m3()
  - compute_market_water_price_per_m3()
  - compute_counterfactual_water_cost()
  - plot_effective_vs_market_cost()
  - create_cost_comparison_table()
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
from src.simulation.metrics import (
    compute_all_metrics,
    compute_blended_water_cost_per_m3,
    compute_market_water_price_per_m3,
    compute_counterfactual_water_cost,
)
from src.notebook_plotting import (
    plot_effective_vs_market_cost,
    create_cost_comparison_table,
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

    # Compute standard metrics (for years list)
    all_metrics = compute_all_metrics(state)
    years = all_metrics["years"]

    # Create data loader
    print("Loading research price data...")
    data_loader = SimulationDataLoader(use_research_prices=True)

    # --- Blended water cost per m3 ---
    print("\n--- Blended Water Cost per m³ (Self-Owned Mix) ---")
    blended_costs = compute_blended_water_cost_per_m3(state)
    for year in years:
        for farm_id, cost in blended_costs[year].items():
            print(f"  {year} | {farm_id}: ${cost:.4f}/m³")

    # --- Market water price per m3 ---
    print("\n--- Market Water Price per m³ (Government Municipal) ---")
    market_prices = compute_market_water_price_per_m3(scenario, years)
    for year in years:
        print(f"  {year}: ${market_prices[year]:.4f}/m³")

    # --- Counterfactual water cost ---
    print("\n--- Counterfactual Water Cost (All Municipal) ---")
    counterfactual = compute_counterfactual_water_cost(state, data_loader, scenario)
    for year in years:
        for farm_id, cost in counterfactual["yearly_costs"][year].items():
            print(f"  {year} | {farm_id}: ${cost:,.2f}")

    # --- Comparison: actual vs. counterfactual ---
    print("\n--- Actual vs. Counterfactual Cost Comparison ---")
    farm_id = state.farms[0].farm_id
    for year in years:
        actual = [m for m in state.yearly_metrics
                  if m.year == year and m.farm_id == farm_id]
        if actual:
            actual_cost = actual[0].total_water_cost_usd
        else:
            actual_cost = 0.0
        govt_cost = counterfactual["yearly_costs"][year].get(farm_id, 0.0)
        if govt_cost > 0:
            savings_pct = (govt_cost - actual_cost) / govt_cost * 100
        else:
            savings_pct = 0.0
        print(f"  {year} | Actual: ${actual_cost:,.2f} | "
              f"Government: ${govt_cost:,.2f} | Savings: {savings_pct:.1f}%")

    # --- Plot 2: Effective vs. Market Cost ---
    print("\nGenerating plot2: Effective vs. Market Water Cost...")
    fig = plot_effective_vs_market_cost(blended_costs, market_prices, years)
    out_path = os.path.join(exports_dir, "plot2_effective_vs_market.png")
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    import matplotlib.pyplot as plt
    plt.close(fig)
    print(f"  Saved: {out_path}")

    # --- Table 1: Cost Comparison ---
    print("\n--- Cost Comparison Table ---")
    df = create_cost_comparison_table(
        state.yearly_metrics, counterfactual, blended_costs, market_prices, years
    )
    print(df.to_string(index=False))

    print("\nSUCCESS: All Phase 3 outputs generated")


if __name__ == "__main__":
    main()
