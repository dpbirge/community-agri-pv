#!/usr/bin/env python3
"""Test script for Phase 6: Sensitivity analysis and tornado chart.

Generates:
  - plot6_tornado.png — Tornado chart of profit sensitivity to ±20% price changes
  - Sensitivity results table (printed)
  - Top 3 most impactful parameters (printed)
"""

import os
import sys
import time

# Ensure project root is on sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Use non-interactive backend before importing pyplot
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from src.simulation.sensitivity import run_sensitivity_analysis
from src.notebook_plotting import plot_tornado_sensitivity


def main():
    start_time = time.time()

    # Ensure exports directory exists
    exports_dir = os.path.join(project_root, "notebooks", "exports")
    os.makedirs(exports_dir, exist_ok=True)

    # Run sensitivity analysis
    scenario_path = os.path.join(project_root, "settings", "mvp-settings.yaml")
    print(f"Scenario: {scenario_path}")
    print("Running sensitivity analysis (±20% price variations)...\n")

    results = run_sensitivity_analysis(scenario_path, variation_pct=0.20, verbose=True)

    # Print base income
    print(f"\n{'='*70}")
    print(f"Base Net Income: ${results['base_income']:,.2f}")
    print(f"{'='*70}")

    # Print results table sorted by swing
    params = results["parameters"]
    sorted_params = sorted(params.items(), key=lambda kv: kv[1]["total_swing"], reverse=True)

    print(f"\n{'Parameter':<25} {'Low Δ (USD)':>14} {'High Δ (USD)':>14} {'Total Swing':>14}")
    print("-" * 69)
    for param, data in sorted_params:
        print(f"{data['label']:<25} {data['low_delta']:>+14,.2f} {data['high_delta']:>+14,.2f} "
              f"{data['total_swing']:>14,.2f}")

    # Top 3 most impactful
    print(f"\n--- Top 3 Most Impactful Parameters ---")
    for i, (param, data) in enumerate(sorted_params[:3], 1):
        print(f"  {i}. {data['label']} (swing: ${data['total_swing']:,.2f})")

    # Generate tornado plot
    print("\nGenerating plot6: Tornado Sensitivity Chart...")
    fig = plot_tornado_sensitivity(results)
    out_path = os.path.join(exports_dir, "plot6_tornado.png")
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {out_path}")

    # Report runtime
    elapsed = time.time() - start_time
    print(f"\nTotal runtime: {elapsed:.1f} seconds")
    print("\nSUCCESS: All Phase 6 outputs generated")


if __name__ == "__main__":
    main()
