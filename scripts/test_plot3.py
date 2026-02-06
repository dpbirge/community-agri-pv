#!/usr/bin/env python3
"""Test script for Phase 4 plot additions.

Generates:
  - plot3_cost_breakdown.png  — Stacked monthly operating cost breakdown

Tests:
  - Energy cost tracking in DailyWaterRecord
  - Fertilizer and labor cost integration in monthly metrics
  - Cost breakdown: water, energy, diesel, fertilizer, labor
  - Cost volatility (CV) calculation
  - plot_monthly_cost_breakdown()
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
    compute_cost_volatility,
)
from src.notebook_plotting import plot_monthly_cost_breakdown


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

    # Create data loader with research prices
    print("Loading research price data...")
    data_loader = SimulationDataLoader(use_research_prices=True)
    print(f"  Labor cost: ${data_loader._labor_cost_usd_per_ha_year:.2f}/ha/year "
          f"(${data_loader.get_labor_cost_usd_ha_month():.2f}/ha/month)")

    # Compute all metrics with cost categories
    print("\nComputing metrics with cost breakdown...")
    all_metrics = compute_all_metrics(state, data_loader=data_loader, scenario=scenario)
    monthly = all_metrics["monthly_metrics"]
    print(f"  Monthly metric records: {len(monthly)}")

    # --- Print monthly cost breakdown for first 6 months ---
    print("\n--- Monthly Cost Breakdown (first 6 months) ---")
    print(f"  {'Month':<10} {'Water':>10} {'Energy':>10} {'Diesel':>10} "
          f"{'Fertilizer':>12} {'Labor':>10} {'Total':>12}")
    print(f"  {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*12} {'-'*10} {'-'*12}")

    for m in monthly[:6]:
        water_net = m.total_water_cost_usd - m.energy_cost_usd
        print(f"  {m.year}-{m.month:02d}    "
              f"${water_net:>9.2f} "
              f"${m.energy_cost_usd:>9.2f} "
              f"${m.diesel_cost_usd:>9.2f} "
              f"${m.fertilizer_cost_usd:>11.2f} "
              f"${m.labor_cost_usd:>9.2f} "
              f"${m.total_operating_cost_usd:>11.2f}")

    # --- Verify total = sum of parts ---
    print("\n--- Verification: total == sum of parts ---")
    all_ok = True
    for m in monthly:
        water_net = m.total_water_cost_usd - m.energy_cost_usd
        expected_total = (water_net + m.energy_cost_usd + m.diesel_cost_usd
                          + m.fertilizer_cost_usd + m.labor_cost_usd)
        diff = abs(m.total_operating_cost_usd - expected_total)
        if diff > 0.01:
            print(f"  MISMATCH at {m.year}-{m.month:02d}: "
                  f"total={m.total_operating_cost_usd:.4f} vs "
                  f"sum={expected_total:.4f} (diff={diff:.4f})")
            all_ok = False

    if all_ok:
        print("  PASS: All months verified (total == sum of parts)")
    else:
        print("  FAIL: Some months have mismatches")
        sys.exit(1)

    # --- Cost volatility ---
    print("\n--- Cost Volatility ---")
    cv = compute_cost_volatility(monthly)
    print(f"  Coefficient of Variation (CV): {cv:.4f}")
    if cv > 0:
        print(f"  Interpretation: {'Low' if cv < 0.3 else 'Moderate' if cv < 0.6 else 'High'} volatility")

    # --- Generate plot ---
    print("\nGenerating plot3: Monthly Cost Breakdown...")
    fig = plot_monthly_cost_breakdown(all_metrics)
    out_path = os.path.join(exports_dir, "plot3_cost_breakdown.png")
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    import matplotlib.pyplot as plt
    plt.close(fig)
    print(f"  Saved: {out_path}")

    print("\nSUCCESS: All Phase 4 outputs generated")


if __name__ == "__main__":
    main()
