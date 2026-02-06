"""Sensitivity analysis for the community agri-PV simulation.

Runs the simulation multiple times with perturbed input prices to measure
which parameters have the greatest impact on net farm income.
"""

from pathlib import Path

from src.settings.loader import load_scenario
from src.simulation.simulation import run_simulation
from src.simulation.data_loader import SimulationDataLoader
from src.simulation.metrics import compute_all_metrics, compute_net_income


def _find_project_root(start_path: Path) -> Path:
    """Find project root by searching upward for data_registry.yaml."""
    current = start_path if start_path.is_dir() else start_path.parent
    for _ in range(10):  # limit search depth
        if (current / "settings" / "data_registry.yaml").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    # Fallback: assume 2 levels up from scenario file
    return start_path.parent.parent


def _compute_total_net_income(scenario_path, price_multipliers=None, project_root=None):
    """Run a single simulation and return total net income.

    Args:
        scenario_path: Path to scenario YAML file
        price_multipliers: Optional dict of price multipliers
        project_root: Project root for data resolution

    Returns:
        float: Total net income (USD) across all months
    """
    scenario = load_scenario(scenario_path)
    data_loader = SimulationDataLoader(
        use_research_prices=True,
        project_root=project_root,
        price_multipliers=price_multipliers,
    )
    state = run_simulation(scenario, data_loader=data_loader, verbose=False)
    metrics = compute_all_metrics(state, data_loader=data_loader, scenario=scenario)
    net_income_data = compute_net_income(metrics["monthly_metrics"])
    return sum(row["net_income_usd"] for row in net_income_data)


def run_sensitivity_analysis(scenario_path, variation_pct=0.20, verbose=False):
    """Run sensitivity analysis by varying each input price ±variation_pct.

    Parameters tested:
    - municipal_water: Municipal water price
    - electricity: Grid electricity price
    - diesel: Diesel fuel price
    - fertilizer: Fertilizer cost
    - labor: Labor cost
    - crop_tomato: Tomato farmgate price
    - crop_potato: Potato farmgate price
    - crop_onion: Onion farmgate price
    - crop_kale: Kale farmgate price
    - crop_cucumber: Cucumber farmgate price

    Args:
        scenario_path: Path to scenario YAML file
        variation_pct: Fraction to vary prices (default 0.20 = ±20%)
        verbose: Print progress if True

    Returns:
        dict: {
            "base_income": float,  # Total net income with no perturbation
            "parameters": {
                param_name: {
                    "label": str,  # Human-readable label
                    "low_income": float,  # Income with price at (1 - variation_pct)
                    "high_income": float,  # Income with price at (1 + variation_pct)
                    "low_delta": float,  # low_income - base_income
                    "high_delta": float,  # high_income - base_income
                    "total_swing": float,  # abs(high_delta) + abs(low_delta)
                }
            }
        }
    """
    project_root = str(_find_project_root(Path(scenario_path)))

    # Define parameters and their labels
    parameters = {
        "municipal_water": "Municipal Water Price",
        "electricity": "Grid Electricity Price",
        "diesel": "Diesel Fuel Price",
        "fertilizer": "Fertilizer Cost",
        "labor": "Labor Cost",
        "crop_tomato": "Tomato Price",
        "crop_potato": "Potato Price",
        "crop_onion": "Onion Price",
        "crop_kale": "Kale Price",
        "crop_cucumber": "Cucumber Price",
    }

    # Run base case
    if verbose:
        print("Running base case (no price changes)...")
    base_income = _compute_total_net_income(scenario_path, project_root=project_root)
    if verbose:
        print(f"  Base net income: ${base_income:,.2f}")

    # Run perturbed cases
    results = {}
    low_mult = 1.0 - variation_pct
    high_mult = 1.0 + variation_pct

    for i, (param, label) in enumerate(parameters.items(), 1):
        if verbose:
            print(f"[{i}/{len(parameters)}] Testing {label}...")

        # Low case: price reduced
        low_income = _compute_total_net_income(
            scenario_path,
            price_multipliers={param: low_mult},
            project_root=project_root,
        )

        # High case: price increased
        high_income = _compute_total_net_income(
            scenario_path,
            price_multipliers={param: high_mult},
            project_root=project_root,
        )

        low_delta = low_income - base_income
        high_delta = high_income - base_income
        total_swing = abs(high_delta) + abs(low_delta)

        results[param] = {
            "label": label,
            "low_income": low_income,
            "high_income": high_income,
            "low_delta": low_delta,
            "high_delta": high_delta,
            "total_swing": total_swing,
        }

        if verbose:
            print(f"  Low ({low_mult:.0%}): delta ${low_delta:+,.2f}  |  "
                  f"High ({high_mult:.0%}): delta ${high_delta:+,.2f}  |  "
                  f"Swing: ${total_swing:,.2f}")

    return {
        "base_income": base_income,
        "parameters": results,
    }
