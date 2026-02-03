# Results output for Water Simulation MVP
# Layer 3: Simulation Engine
#
# Writes simulation results to CSV files and generates matplotlib plots.
# Output structure:
#   /results/water_policy_only_YYYYMMDD_HHMMSS/
#     yearly_summary.csv
#     yearly_community_summary.csv
#     daily_farm_results.csv
#     simulation_config.json
#     plots/
#       community_*.png (primary plots)
#       farm_*.png (secondary plots)

import json
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.metrics import compute_all_metrics, compare_policies


def create_output_directory(base_path="results", scenario_name="water_policy"):
    """Create timestamped output directory.

    Args:
        base_path: Base results directory
        scenario_name: Name prefix for output folder

    Returns:
        Path to created directory
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(base_path) / f"{scenario_name}_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "plots").mkdir(exist_ok=True)
    return output_dir


def write_yearly_summary(farm_metrics, output_path):
    """Write yearly metrics per farm to CSV.

    Args:
        farm_metrics: List of ComputedYearlyMetrics
        output_path: Path to output CSV file
    """
    rows = []
    for m in farm_metrics:
        rows.append({
            "year": m.year,
            "farm_id": m.farm_id,
            "farm_name": m.farm_name,
            "water_policy": m.water_policy,
            "total_water_m3": m.total_water_m3,
            "groundwater_m3": m.groundwater_m3,
            "municipal_m3": m.municipal_m3,
            "total_yield_kg": m.total_yield_kg,
            "water_cost_usd": m.total_water_cost_usd,
            "water_per_yield_m3_kg": m.water_per_yield_m3_kg,
            "cost_per_m3_usd": m.cost_per_m3_usd,
            "self_sufficiency_pct": m.self_sufficiency_pct,
        })

    df = pd.DataFrame(rows)
    df = df.sort_values(["year", "farm_id"])
    df.to_csv(output_path, index=False)
    return df


def write_yearly_community_summary(community_metrics, output_path):
    """Write yearly community-wide aggregates to CSV.

    Args:
        community_metrics: List of CommunityYearlyMetrics
        output_path: Path to output CSV file
    """
    rows = []
    for m in community_metrics:
        rows.append({
            "year": m.year,
            "total_water_m3": m.total_water_m3,
            "total_groundwater_m3": m.total_groundwater_m3,
            "total_municipal_m3": m.total_municipal_m3,
            "total_yield_kg": m.total_yield_kg,
            "total_water_cost_usd": m.total_water_cost_usd,
            "avg_water_per_yield_m3_kg": m.avg_water_per_yield_m3_kg,
            "avg_cost_per_m3_usd": m.avg_cost_per_m3_usd,
            "community_self_sufficiency_pct": m.community_self_sufficiency_pct,
        })

    df = pd.DataFrame(rows)
    df = df.sort_values("year")
    df.to_csv(output_path, index=False)
    return df


def write_daily_results(simulation_state, output_path):
    """Write daily water allocation records to CSV.

    Args:
        simulation_state: SimulationState with farm daily records
        output_path: Path to output CSV file
    """
    rows = []
    for farm in simulation_state.farms:
        for record in farm.daily_water_records:
            rows.append({
                "date": record.date.isoformat(),
                "farm_id": farm.farm_id,
                "farm_name": farm.farm_name,
                "water_policy": farm.water_policy_name,
                "demand_m3": record.demand_m3,
                "groundwater_m3": record.groundwater_m3,
                "municipal_m3": record.municipal_m3,
                "cost_usd": record.cost_usd,
                "energy_kwh": record.energy_kwh,
            })

    df = pd.DataFrame(rows)
    df = df.sort_values(["date", "farm_id"])
    df.to_csv(output_path, index=False)
    return df


def write_simulation_config(scenario, output_path):
    """Write scenario configuration snapshot to JSON.

    Args:
        scenario: Loaded Scenario object
        output_path: Path to output JSON file
    """
    config = {
        "scenario": {
            "name": scenario.metadata.name,
            "description": scenario.metadata.description,
            "version": scenario.metadata.version,
            "start_date": scenario.metadata.start_date.isoformat(),
            "end_date": scenario.metadata.end_date.isoformat(),
        },
        "water_pricing": {
            "regime": scenario.water_pricing.pricing_regime if scenario.water_pricing else "N/A",
            "municipal_source": scenario.water_pricing.municipal_source if scenario.water_pricing else "N/A",
        },
        "farms": [
            {
                "id": f.id,
                "name": f.name,
                "area_ha": f.area_ha,
                "water_policy": f.water_policy.name,
                "crops": [c.name for c in f.crops],
            }
            for f in scenario.farms
        ],
        "infrastructure": {
            "well_count": scenario.infrastructure.groundwater_wells.number_of_wells,
            "treatment_capacity_m3_day": scenario.infrastructure.water_treatment.system_capacity_m3_day,
            "salinity_level": scenario.infrastructure.water_treatment.salinity_level,
        },
    }

    with open(output_path, "w") as f:
        json.dump(config, f, indent=2)


def plot_community_water_use(community_metrics, output_path):
    """Plot community water use over time by source.

    Args:
        community_metrics: List of CommunityYearlyMetrics
        output_path: Path to save plot
    """
    years = [m.year for m in community_metrics]
    gw = [m.total_groundwater_m3 / 1000 for m in community_metrics]  # Convert to thousands
    muni = [m.total_municipal_m3 / 1000 for m in community_metrics]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(years, gw, label="Groundwater (BWRO)", color="#2E86AB")
    ax.bar(years, muni, bottom=gw, label="Municipal (SWRO)", color="#A23B72")

    ax.set_xlabel("Year")
    ax.set_ylabel("Water Use (thousand m³)")
    ax.set_title("Community Water Use by Source")
    ax.legend()
    ax.set_xticks(years)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_community_water_cost(community_metrics, output_path):
    """Plot community water cost over time.

    Args:
        community_metrics: List of CommunityYearlyMetrics
        output_path: Path to save plot
    """
    years = [m.year for m in community_metrics]
    costs = [m.total_water_cost_usd / 1000 for m in community_metrics]  # Convert to thousands

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(years, costs, marker="o", linewidth=2, color="#2E86AB")
    ax.fill_between(years, costs, alpha=0.3, color="#2E86AB")

    ax.set_xlabel("Year")
    ax.set_ylabel("Water Cost (thousand USD)")
    ax.set_title("Community Total Water Cost Over Time")
    ax.set_xticks(years)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_community_self_sufficiency(community_metrics, output_path):
    """Plot community self-sufficiency percentage over time.

    Args:
        community_metrics: List of CommunityYearlyMetrics
        output_path: Path to save plot
    """
    years = [m.year for m in community_metrics]
    self_suff = [m.community_self_sufficiency_pct for m in community_metrics]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(years, self_suff, marker="o", linewidth=2, color="#28A745")
    ax.fill_between(years, self_suff, alpha=0.3, color="#28A745")

    ax.set_xlabel("Year")
    ax.set_ylabel("Self-Sufficiency (%)")
    ax.set_title("Community Groundwater Self-Sufficiency")
    ax.set_ylim(0, 105)
    ax.set_xticks(years)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_community_yields(community_metrics, output_path):
    """Plot community total yields over time.

    Args:
        community_metrics: List of CommunityYearlyMetrics
        output_path: Path to save plot
    """
    years = [m.year for m in community_metrics]
    yields = [m.total_yield_kg / 1_000_000 for m in community_metrics]  # Convert to millions

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(years, yields, color="#FCA311")

    ax.set_xlabel("Year")
    ax.set_ylabel("Total Yield (million kg)")
    ax.set_title("Community Total Crop Yields")
    ax.set_xticks(years)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_farm_water_use_comparison(farm_metrics, years, output_path):
    """Plot water use comparison across farms.

    Args:
        farm_metrics: List of ComputedYearlyMetrics
        years: List of years
        output_path: Path to save plot
    """
    # Group by farm
    farms = {}
    for m in farm_metrics:
        if m.farm_id not in farms:
            farms[m.farm_id] = {"name": m.farm_name, "policy": m.water_policy, "data": {}}
        farms[m.farm_id]["data"][m.year] = m.total_water_m3 / 1000

    fig, ax = plt.subplots(figsize=(12, 6))
    width = 0.2
    x = list(range(len(years)))

    colors = ["#2E86AB", "#A23B72", "#FCA311", "#28A745"]
    for i, (farm_id, info) in enumerate(farms.items()):
        values = [info["data"].get(y, 0) for y in years]
        offset = (i - len(farms) / 2 + 0.5) * width
        ax.bar([xi + offset for xi in x], values, width, label=f"{info['name']} ({info['policy']})", color=colors[i % len(colors)])

    ax.set_xlabel("Year")
    ax.set_ylabel("Water Use (thousand m³)")
    ax.set_title("Water Use by Farm")
    ax.set_xticks(x)
    ax.set_xticklabels(years)
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_farm_costs_comparison(farm_metrics, years, output_path):
    """Plot water cost comparison across farms.

    Args:
        farm_metrics: List of ComputedYearlyMetrics
        years: List of years
        output_path: Path to save plot
    """
    # Group by farm
    farms = {}
    for m in farm_metrics:
        if m.farm_id not in farms:
            farms[m.farm_id] = {"name": m.farm_name, "policy": m.water_policy, "data": {}}
        farms[m.farm_id]["data"][m.year] = m.total_water_cost_usd / 1000

    fig, ax = plt.subplots(figsize=(12, 6))
    width = 0.2
    x = list(range(len(years)))

    colors = ["#2E86AB", "#A23B72", "#FCA311", "#28A745"]
    for i, (farm_id, info) in enumerate(farms.items()):
        values = [info["data"].get(y, 0) for y in years]
        offset = (i - len(farms) / 2 + 0.5) * width
        ax.bar([xi + offset for xi in x], values, width, label=f"{info['name']} ({info['policy']})", color=colors[i % len(colors)])

    ax.set_xlabel("Year")
    ax.set_ylabel("Water Cost (thousand USD)")
    ax.set_title("Water Cost by Farm")
    ax.set_xticks(x)
    ax.set_xticklabels(years)
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_farm_self_sufficiency_comparison(farm_metrics, years, output_path):
    """Plot self-sufficiency comparison across farms.

    Args:
        farm_metrics: List of ComputedYearlyMetrics
        years: List of years
        output_path: Path to save plot
    """
    # Group by farm
    farms = {}
    for m in farm_metrics:
        if m.farm_id not in farms:
            farms[m.farm_id] = {"name": m.farm_name, "policy": m.water_policy, "data": {}}
        farms[m.farm_id]["data"][m.year] = m.self_sufficiency_pct

    fig, ax = plt.subplots(figsize=(12, 6))

    colors = ["#2E86AB", "#A23B72", "#FCA311", "#28A745"]
    for i, (farm_id, info) in enumerate(farms.items()):
        values = [info["data"].get(y, 0) for y in years]
        ax.plot(years, values, marker="o", linewidth=2, label=f"{info['name']} ({info['policy']})", color=colors[i % len(colors)])

    ax.set_xlabel("Year")
    ax.set_ylabel("Self-Sufficiency (%)")
    ax.set_title("Groundwater Self-Sufficiency by Farm")
    ax.set_ylim(-5, 105)
    ax.set_xticks(years)
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_policy_summary(comparison, output_path):
    """Plot policy comparison summary.

    Args:
        comparison: Output from compare_policies()
        output_path: Path to save plot
    """
    summaries = comparison["farm_summaries"]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    # Total cost comparison
    ax = axes[0]
    names = [s["farm_name"].split()[0] for s in summaries]  # Short names
    costs = [s["total_cost_usd"] / 1_000_000 for s in summaries]
    colors = ["#2E86AB", "#28A745", "#FCA311", "#A23B72"]
    ax.barh(names, costs, color=colors[:len(names)])
    ax.set_xlabel("Total Cost (million USD)")
    ax.set_title("Total Water Cost\n(10 years)")

    # Water per yield
    ax = axes[1]
    wpy = [s["overall_water_per_yield_m3_kg"] for s in summaries]
    ax.barh(names, wpy, color=colors[:len(names)])
    ax.set_xlabel("Water per Yield (m³/kg)")
    ax.set_title("Water Efficiency\n(lower is better)")

    # Self-sufficiency
    ax = axes[2]
    ss = [s["overall_self_sufficiency_pct"] for s in summaries]
    ax.barh(names, ss, color=colors[:len(names)])
    ax.set_xlabel("Self-Sufficiency (%)")
    ax.set_title("Groundwater Independence\n(higher = less municipal dependency)")
    ax.set_xlim(0, 105)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def write_results(simulation_state, scenario, output_dir=None):
    """Write all simulation results to files.

    Args:
        simulation_state: SimulationState with results
        scenario: Loaded Scenario object
        output_dir: Output directory (created if not provided)

    Returns:
        Path to output directory
    """
    if output_dir is None:
        output_dir = create_output_directory(scenario_name=scenario.metadata.name)
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "plots").mkdir(exist_ok=True)

    # Compute all metrics
    all_metrics = compute_all_metrics(simulation_state)
    comparison = compare_policies(all_metrics)

    # Write CSV files
    print(f"Writing results to {output_dir}")

    yearly_df = write_yearly_summary(
        all_metrics["farm_metrics"],
        output_dir / "yearly_summary.csv"
    )
    print(f"  - yearly_summary.csv: {len(yearly_df)} rows")

    community_df = write_yearly_community_summary(
        all_metrics["community_metrics"],
        output_dir / "yearly_community_summary.csv"
    )
    print(f"  - yearly_community_summary.csv: {len(community_df)} rows")

    daily_df = write_daily_results(
        simulation_state,
        output_dir / "daily_farm_results.csv"
    )
    print(f"  - daily_farm_results.csv: {len(daily_df)} rows")

    write_simulation_config(scenario, output_dir / "simulation_config.json")
    print("  - simulation_config.json")

    # Generate plots
    plots_dir = output_dir / "plots"

    # Primary plots (community-wide)
    plot_community_water_use(
        all_metrics["community_metrics"],
        plots_dir / "community_water_use.png"
    )
    print("  - plots/community_water_use.png")

    plot_community_water_cost(
        all_metrics["community_metrics"],
        plots_dir / "community_water_cost.png"
    )
    print("  - plots/community_water_cost.png")

    plot_community_self_sufficiency(
        all_metrics["community_metrics"],
        plots_dir / "community_self_sufficiency.png"
    )
    print("  - plots/community_self_sufficiency.png")

    plot_community_yields(
        all_metrics["community_metrics"],
        plots_dir / "community_crop_yields.png"
    )
    print("  - plots/community_crop_yields.png")

    # Secondary plots (per-farm comparison)
    plot_farm_water_use_comparison(
        all_metrics["farm_metrics"],
        all_metrics["years"],
        plots_dir / "farm_water_use.png"
    )
    print("  - plots/farm_water_use.png")

    plot_farm_costs_comparison(
        all_metrics["farm_metrics"],
        all_metrics["years"],
        plots_dir / "farm_costs.png"
    )
    print("  - plots/farm_costs.png")

    plot_farm_self_sufficiency_comparison(
        all_metrics["farm_metrics"],
        all_metrics["years"],
        plots_dir / "farm_self_sufficiency.png"
    )
    print("  - plots/farm_self_sufficiency.png")

    plot_policy_summary(comparison, plots_dir / "policy_comparison.png")
    print("  - plots/policy_comparison.png")

    print(f"\nResults written to: {output_dir}")
    return output_dir


def main():
    """Run simulation and write results from command line."""
    import sys

    from settings.scripts.loader import load_scenario
    from src.simulation import run_simulation

    if len(sys.argv) < 2:
        print("Usage: python src/results.py <scenario_file> [output_dir]")
        print("Example: python src/results.py settings/scenarios/water_policy_only.yaml")
        sys.exit(1)

    scenario_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"Loading scenario: {scenario_path}")
    scenario = load_scenario(scenario_path)

    print("Running simulation...")
    state = run_simulation(scenario, verbose=True)

    print("\nGenerating output files and plots...")
    output_path = write_results(state, scenario, output_dir)

    print(f"\nDone! Results saved to: {output_path}")


if __name__ == "__main__":
    main()
