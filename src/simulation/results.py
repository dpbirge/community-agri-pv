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

from src.simulation.metrics import compute_all_metrics, compare_policies


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
            # Labor metrics
            "total_labor_hours": m.total_labor_hours,
            "field_labor_hours": m.field_labor_hours,
            "processing_labor_hours": m.processing_labor_hours,
            "maintenance_labor_hours": m.maintenance_labor_hours,
            "admin_labor_hours": m.admin_labor_hours,
            "fte_count": m.fte_count,
            "total_labor_cost_usd": m.total_labor_cost_usd,
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


def write_monthly_summary(monthly_metrics, output_path):
    """Write monthly metrics to CSV.

    Args:
        monthly_metrics: List of MonthlyFarmMetrics
        output_path: Path to output CSV file
    """
    rows = []
    for m in monthly_metrics:
        rows.append({
            "year": m.year,
            "month": m.month,
            "farm_id": m.farm_id,
            "farm_name": m.farm_name,
            "water_policy": m.water_policy,
            "total_water_m3": m.total_water_m3,
            "groundwater_m3": m.groundwater_m3,
            "municipal_m3": m.municipal_m3,
            "agricultural_water_m3": m.agricultural_water_m3,
            "community_water_m3": m.community_water_m3,
            "total_water_cost_usd": m.total_water_cost_usd,
            "total_yield_kg": m.total_yield_kg,
            "total_crop_revenue_usd": m.total_crop_revenue_usd,
            "self_sufficiency_pct": m.self_sufficiency_pct,
        })

    df = pd.DataFrame(rows)
    df = df.sort_values(["year", "month", "farm_id"])
    df.to_csv(output_path, index=False)
    return df


def write_daily_results(simulation_state, output_path):
    """Write daily water allocation records to CSV.

    Includes decision metadata columns (decision_reason, constraint_hit,
    gw_cost_per_m3, muni_cost_per_m3) from Phase 3 implementation.

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
                "decision_reason": record.decision_reason,
                "constraint_hit": record.constraint_hit,
                "gw_cost_per_m3": record.gw_cost_per_m3,
                "muni_cost_per_m3": record.muni_cost_per_m3,
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
        "systems": {
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


def plot_daily_cost_distribution(simulation_state, output_path):
    """Plot box plot of daily water cost distribution per farm.

    Shows the spread and quartiles of daily water costs for each farm,
    enabling comparison of cost volatility across water policies.

    Args:
        simulation_state: SimulationState with farm daily records
        output_path: Path to save plot
    """
    # Collect daily costs per farm
    farm_data = {}
    for farm in simulation_state.farms:
        label = f"{farm.farm_name.split()[0]}\n({farm.water_policy_name})"
        farm_data[label] = [r.cost_usd for r in farm.daily_water_records]

    fig, ax = plt.subplots(figsize=(12, 6))

    labels = list(farm_data.keys())
    data = [farm_data[k] for k in labels]

    colors = ["#2E86AB", "#28A745", "#FCA311", "#A23B72"]
    bp = ax.boxplot(data, tick_labels=labels, patch_artist=True)

    for patch, color in zip(bp["boxes"], colors[:len(labels)]):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.set_xlabel("Farm (Policy)")
    ax.set_ylabel("Daily Water Cost (USD)")
    ax.set_title("Daily Water Cost Distribution by Farm")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_decision_reason_counts(simulation_state, output_path):
    """Plot stacked bar chart of decision_reason counts per year.

    Shows how often each type of water allocation decision was made,
    broken down by year. Useful for understanding policy behavior patterns.

    Args:
        simulation_state: SimulationState with farm daily records
        output_path: Path to save plot
    """
    # Collect decision reasons by year
    reason_counts = {}  # {year: {reason: count}}
    for farm in simulation_state.farms:
        for record in farm.daily_water_records:
            year = record.date.year
            reason = record.decision_reason or "unknown"
            if year not in reason_counts:
                reason_counts[year] = {}
            reason_counts[year][reason] = reason_counts[year].get(reason, 0) + 1

    years = sorted(reason_counts.keys())
    all_reasons = sorted(set(r for yr_data in reason_counts.values() for r in yr_data))

    # Build data matrix
    data = {reason: [reason_counts[yr].get(reason, 0) for yr in years] for reason in all_reasons}

    fig, ax = plt.subplots(figsize=(12, 6))

    # Color palette for decision reasons
    reason_colors = {
        "gw_preferred": "#2E86AB",
        "gw_preferred_partial": "#5DA7C7",
        "gw_preferred_but_energy_limit": "#8EC8E3",
        "gw_preferred_but_well_limit": "#B0D9EF",
        "gw_preferred_but_treatment_limit": "#D2EAFB",
        "muni_only": "#A23B72",
        "gw_cheaper": "#28A745",
        "gw_cheaper_but_energy_limit": "#5DC77A",
        "gw_cheaper_but_well_limit": "#8EE7AF",
        "gw_cheaper_but_treatment_limit": "#BFF7E4",
        "muni_cheaper": "#FCA311",
        "threshold_exceeded": "#6B5B95",
        "threshold_exceeded_but_energy_limit": "#9B8BB5",
        "threshold_exceeded_but_well_limit": "#CBBBD5",
        "threshold_exceeded_but_treatment_limit": "#FBEBF5",
        "threshold_not_met": "#E15D44",
        "unknown": "#888888",
    }

    bottom = [0] * len(years)
    for reason in all_reasons:
        values = data[reason]
        color = reason_colors.get(reason, "#888888")
        ax.bar(years, values, bottom=bottom, label=reason, color=color)
        bottom = [b + v for b, v in zip(bottom, values)]

    ax.set_xlabel("Year")
    ax.set_ylabel("Decision Count")
    ax.set_title("Water Allocation Decision Reasons by Year")
    ax.set_xticks(years)
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=8)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_constraint_hit_timeline(simulation_state, output_path):
    """Plot timeline scatter of constraint hit events.

    Shows when system constraints limited groundwater allocation.
    Each point represents a day when a constraint was hit, color-coded
    by constraint type and positioned by farm.

    Args:
        simulation_state: SimulationState with farm daily records
        output_path: Path to save plot
    """
    fig, ax = plt.subplots(figsize=(14, 6))

    constraint_colors = {
        "energy_limit": "#E15D44",
        "well_limit": "#FCA311",
        "treatment_limit": "#6B5B95",
    }

    farm_names = []
    for i, farm in enumerate(simulation_state.farms):
        short_name = f"{farm.farm_name.split()[0]} ({farm.water_policy_name})"
        farm_names.append(short_name)

        for record in farm.daily_water_records:
            if record.constraint_hit:
                color = constraint_colors.get(record.constraint_hit, "#888888")
                ax.scatter(
                    record.date, i, c=color, s=15, alpha=0.7,
                    marker="o", edgecolors="none"
                )

    ax.set_yticks(range(len(farm_names)))
    ax.set_yticklabels(farm_names)
    ax.set_xlabel("Date")
    ax.set_ylabel("Farm")
    ax.set_title("Constraint Hit Events Timeline")

    # Add legend
    handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=c, markersize=8, label=lbl)
        for lbl, c in constraint_colors.items()
    ]
    ax.legend(handles=handles, loc="upper right")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_farm_water_sources_area(simulation_state, output_path):
    """Plot per-farm stacked area chart of GW vs municipal over time.

    Shows daily water use from each source as stacked areas, enabling
    visualization of source mix changes over the simulation period.
    Creates one subplot per farm.

    Args:
        simulation_state: SimulationState with farm daily records
        output_path: Path to save plot
    """
    n_farms = len(simulation_state.farms)
    fig, axes = plt.subplots(n_farms, 1, figsize=(14, 4 * n_farms), sharex=True)

    if n_farms == 1:
        axes = [axes]

    for ax, farm in zip(axes, simulation_state.farms):
        dates = [r.date for r in farm.daily_water_records]
        gw = [r.groundwater_m3 for r in farm.daily_water_records]
        muni = [r.municipal_m3 for r in farm.daily_water_records]

        ax.fill_between(dates, 0, gw, label="Groundwater (BWRO)", color="#2E86AB", alpha=0.8)
        ax.fill_between(dates, gw, [g + m for g, m in zip(gw, muni)],
                        label="Municipal (SWRO)", color="#A23B72", alpha=0.8)

        short_name = farm.farm_name.split()[0]
        ax.set_ylabel("Water (m³)")
        ax.set_title(f"{short_name} ({farm.water_policy_name})")
        ax.legend(loc="upper right")

    axes[-1].set_xlabel("Date")
    fig.suptitle("Daily Water Sources by Farm", fontsize=14, y=1.02)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_monthly_water_use(monthly_metrics, output_path):
    """Plot monthly water use split by agriculture vs community.

    Args:
        monthly_metrics: List of MonthlyFarmMetrics
        output_path: Path to save plot
    """
    if not monthly_metrics:
        return

    # Create month labels (YYYY-MM format)
    dates = [f"{m.year}-{m.month:02d}" for m in monthly_metrics]
    agri_water = [m.agricultural_water_m3 for m in monthly_metrics]
    comm_water = [m.community_water_m3 for m in monthly_metrics]

    fig, ax = plt.subplots(figsize=(14, 6))
    
    x = range(len(dates))
    ax.fill_between(x, 0, agri_water, label="Agricultural Water", color="#2E86AB", alpha=0.7)
    ax.fill_between(x, agri_water, [a + c for a, c in zip(agri_water, comm_water)],
                     label="Community Water", color="#FCA311", alpha=0.7)

    ax.set_xlabel("Month")
    ax.set_ylabel("Water Use (m³)")
    ax.set_title("Monthly Water Use by Type")
    ax.legend()
    
    # Show every 3rd month label to avoid crowding
    tick_indices = list(range(0, len(dates), 3))
    ax.set_xticks(tick_indices)
    ax.set_xticklabels([dates[i] for i in tick_indices], rotation=45, ha="right")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_yearly_water_use(farm_metrics, output_path):
    """Plot yearly water use (total by year).

    Args:
        farm_metrics: List of ComputedYearlyMetrics
        output_path: Path to save plot
    """
    if not farm_metrics:
        return

    # Group by year
    yearly_data = {}
    for m in farm_metrics:
        if m.year not in yearly_data:
            yearly_data[m.year] = {"agri": 0.0, "comm": 0.0}
        yearly_data[m.year]["agri"] += m.total_water_m3

    years = sorted(yearly_data.keys())
    agri_water = [yearly_data[y]["agri"] for y in years]
    comm_water = [yearly_data[y]["comm"] for y in years]

    fig, ax = plt.subplots(figsize=(10, 6))
    
    ax.plot(years, agri_water, marker="o", linewidth=2, label="Agricultural Water", color="#2E86AB")
    ax.plot(years, comm_water, marker="s", linewidth=2, label="Community Water", color="#FCA311")

    ax.set_xlabel("Year")
    ax.set_ylabel("Water Use (m³)")
    ax.set_title("Yearly Water Use by Type")
    ax.legend()
    ax.set_xticks(years)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_monthly_self_sufficiency(monthly_metrics, output_path):
    """Plot monthly water self-sufficiency percentage.

    Args:
        monthly_metrics: List of MonthlyFarmMetrics
        output_path: Path to save plot
    """
    if not monthly_metrics:
        return

    dates = [f"{m.year}-{m.month:02d}" for m in monthly_metrics]
    self_suff = [m.self_sufficiency_pct for m in monthly_metrics]

    fig, ax = plt.subplots(figsize=(14, 6))
    
    x = range(len(dates))
    ax.plot(x, self_suff, marker="o", linewidth=2, color="#28A745", markersize=4)
    ax.fill_between(x, 0, self_suff, alpha=0.3, color="#28A745")

    ax.set_xlabel("Month")
    ax.set_ylabel("Self-Sufficiency (%)")
    ax.set_title("Monthly Groundwater Self-Sufficiency")
    ax.set_ylim(0, 105)
    
    tick_indices = list(range(0, len(dates), 3))
    ax.set_xticks(tick_indices)
    ax.set_xticklabels([dates[i] for i in tick_indices], rotation=45, ha="right")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_yearly_self_sufficiency(farm_metrics, output_path):
    """Plot yearly water self-sufficiency percentage.

    Args:
        farm_metrics: List of ComputedYearlyMetrics
        output_path: Path to save plot
    """
    if not farm_metrics:
        return

    years = [m.year for m in farm_metrics]
    self_suff = [m.self_sufficiency_pct for m in farm_metrics]

    fig, ax = plt.subplots(figsize=(10, 6))
    
    ax.plot(years, self_suff, marker="o", linewidth=2, color="#28A745")
    ax.fill_between(years, 0, self_suff, alpha=0.3, color="#28A745")

    ax.set_xlabel("Year")
    ax.set_ylabel("Self-Sufficiency (%)")
    ax.set_title("Yearly Groundwater Self-Sufficiency")
    ax.set_ylim(0, 105)
    ax.set_xticks(years)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_monthly_crop_yields(monthly_metrics, output_path):
    """Plot monthly crop yields by crop type.

    Args:
        monthly_metrics: List of MonthlyFarmMetrics
        output_path: Path to save plot
    """
    if not monthly_metrics:
        return

    # Get all crops
    all_crops = set()
    for m in monthly_metrics:
        all_crops.update(m.crop_yields_kg.keys())
    all_crops = sorted(all_crops)

    if not all_crops:
        return

    dates = [f"{m.year}-{m.month:02d}" for m in monthly_metrics]
    
    # Build data series for each crop
    crop_data = {crop: [m.crop_yields_kg.get(crop, 0.0) / 1000 for m in monthly_metrics] 
                 for crop in all_crops}

    fig, ax = plt.subplots(figsize=(14, 6))
    
    colors = {"tomato": "#E63946", "potato": "#A8DADC", "onion": "#9B59B6", 
              "kale": "#52B788", "cucumber": "#06A77D"}
    
    x = range(len(dates))
    for crop in all_crops:
        color = colors.get(crop, "#888888")
        ax.plot(x, crop_data[crop], marker="o", linewidth=2, label=crop.capitalize(),
                color=color, markersize=4)

    ax.set_xlabel("Month")
    ax.set_ylabel("Crop Yield (thousand kg)")
    ax.set_title("Monthly Crop Yields by Type")
    ax.legend()
    
    tick_indices = list(range(0, len(dates), 3))
    ax.set_xticks(tick_indices)
    ax.set_xticklabels([dates[i] for i in tick_indices], rotation=45, ha="right")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_yearly_crop_yields(simulation_state, output_path):
    """Plot yearly crop yields by crop type.

    Args:
        simulation_state: SimulationState with yearly_metrics
        output_path: Path to save plot
    """
    # Get all crops from yearly metrics
    all_crops = set()
    for m in simulation_state.yearly_metrics:
        all_crops.update(m.crop_yield_kg.keys())
    all_crops = sorted(all_crops)

    if not all_crops:
        return

    # Group by year and aggregate across farms
    yearly_data = {}
    for m in simulation_state.yearly_metrics:
        if m.year not in yearly_data:
            yearly_data[m.year] = {crop: 0.0 for crop in all_crops}
        for crop, yield_kg in m.crop_yield_kg.items():
            yearly_data[m.year][crop] += yield_kg

    years = sorted(yearly_data.keys())
    
    # Build data series for each crop
    crop_data = {crop: [yearly_data[y][crop] / 1000 for y in years] for crop in all_crops}

    fig, ax = plt.subplots(figsize=(10, 6))
    
    colors = {"tomato": "#E63946", "potato": "#A8DADC", "onion": "#9B59B6", 
              "kale": "#52B788", "cucumber": "#06A77D"}
    
    for crop in all_crops:
        color = colors.get(crop, "#888888")
        ax.plot(years, crop_data[crop], marker="o", linewidth=2, label=crop.capitalize(),
                color=color)

    ax.set_xlabel("Year")
    ax.set_ylabel("Crop Yield (thousand kg)")
    ax.set_title("Yearly Crop Yields by Type")
    ax.legend()
    ax.set_xticks(years)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_monthly_water_costs(monthly_metrics, output_path):
    """Plot monthly water costs.

    Args:
        monthly_metrics: List of MonthlyFarmMetrics
        output_path: Path to save plot
    """
    if not monthly_metrics:
        return

    dates = [f"{m.year}-{m.month:02d}" for m in monthly_metrics]
    costs = [m.total_water_cost_usd for m in monthly_metrics]

    fig, ax = plt.subplots(figsize=(14, 6))
    
    x = range(len(dates))
    ax.plot(x, costs, marker="o", linewidth=2, color="#2E86AB", markersize=4)
    ax.fill_between(x, 0, costs, alpha=0.3, color="#2E86AB")

    ax.set_xlabel("Month")
    ax.set_ylabel("Water Cost (USD)")
    ax.set_title("Monthly Water Costs")
    
    tick_indices = list(range(0, len(dates), 3))
    ax.set_xticks(tick_indices)
    ax.set_xticklabels([dates[i] for i in tick_indices], rotation=45, ha="right")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_yearly_water_costs(farm_metrics, output_path):
    """Plot yearly water costs.

    Args:
        farm_metrics: List of ComputedYearlyMetrics
        output_path: Path to save plot
    """
    if not farm_metrics:
        return

    years = [m.year for m in farm_metrics]
    costs = [m.total_water_cost_usd for m in farm_metrics]

    fig, ax = plt.subplots(figsize=(10, 6))
    
    ax.plot(years, costs, marker="o", linewidth=2, color="#2E86AB")
    ax.fill_between(years, 0, costs, alpha=0.3, color="#2E86AB")

    ax.set_xlabel("Year")
    ax.set_ylabel("Water Cost (USD)")
    ax.set_title("Yearly Water Costs")
    ax.set_xticks(years)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_monthly_crop_revenue(monthly_metrics, output_path):
    """Plot monthly crop revenue.

    Args:
        monthly_metrics: List of MonthlyFarmMetrics
        output_path: Path to save plot
    """
    if not monthly_metrics:
        return

    dates = [f"{m.year}-{m.month:02d}" for m in monthly_metrics]
    revenue = [m.total_crop_revenue_usd for m in monthly_metrics]

    fig, ax = plt.subplots(figsize=(14, 6))
    
    x = range(len(dates))
    ax.plot(x, revenue, marker="o", linewidth=2, color="#28A745", markersize=4)
    ax.fill_between(x, 0, revenue, alpha=0.3, color="#28A745")

    ax.set_xlabel("Month")
    ax.set_ylabel("Crop Revenue (USD)")
    ax.set_title("Monthly Crop Revenue")
    
    tick_indices = list(range(0, len(dates), 3))
    ax.set_xticks(tick_indices)
    ax.set_xticklabels([dates[i] for i in tick_indices], rotation=45, ha="right")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_yearly_crop_revenue(farm_metrics, output_path):
    """Plot yearly crop revenue.

    Args:
        farm_metrics: List of ComputedYearlyMetrics
        output_path: Path to save plot
    """
    if not farm_metrics:
        return

    years = [m.year for m in farm_metrics]
    revenue = [m.total_crop_revenue_usd for m in farm_metrics]

    fig, ax = plt.subplots(figsize=(10, 6))
    
    ax.plot(years, revenue, marker="o", linewidth=2, color="#28A745")
    ax.fill_between(years, 0, revenue, alpha=0.3, color="#28A745")

    ax.set_xlabel("Year")
    ax.set_ylabel("Crop Revenue (USD)")
    ax.set_title("Yearly Crop Revenue")
    ax.set_xticks(years)

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

    # Compute all metrics (pass scenario for labor and financial metrics)
    all_metrics = compute_all_metrics(simulation_state, scenario=scenario)
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

    monthly_df = write_monthly_summary(
        all_metrics["monthly_metrics"],
        output_dir / "monthly_summary.csv"
    )
    print(f"  - monthly_summary.csv: {len(monthly_df)} rows")

    daily_df = write_daily_results(
        simulation_state,
        output_dir / "daily_farm_results.csv"
    )
    print(f"  - daily_farm_results.csv: {len(daily_df)} rows")

    write_simulation_config(scenario, output_dir / "simulation_config.json")
    print("  - simulation_config.json")

    # Generate plots
    plots_dir = output_dir / "plots"

    # New primary plots: Monthly and Yearly
    print("\n  Generating monthly plots...")
    
    plot_monthly_water_use(
        all_metrics["monthly_metrics"],
        plots_dir / "monthly_water_use.png"
    )
    print("  - plots/monthly_water_use.png")

    plot_monthly_self_sufficiency(
        all_metrics["monthly_metrics"],
        plots_dir / "monthly_self_sufficiency.png"
    )
    print("  - plots/monthly_self_sufficiency.png")

    plot_monthly_crop_yields(
        all_metrics["monthly_metrics"],
        plots_dir / "monthly_crop_yields.png"
    )
    print("  - plots/monthly_crop_yields.png")

    plot_monthly_water_costs(
        all_metrics["monthly_metrics"],
        plots_dir / "monthly_water_costs.png"
    )
    print("  - plots/monthly_water_costs.png")

    plot_monthly_crop_revenue(
        all_metrics["monthly_metrics"],
        plots_dir / "monthly_crop_revenue.png"
    )
    print("  - plots/monthly_crop_revenue.png")

    print("\n  Generating yearly plots...")

    plot_yearly_water_use(
        all_metrics["farm_metrics"],
        plots_dir / "yearly_water_use.png"
    )
    print("  - plots/yearly_water_use.png")

    plot_yearly_self_sufficiency(
        all_metrics["farm_metrics"],
        plots_dir / "yearly_self_sufficiency.png"
    )
    print("  - plots/yearly_self_sufficiency.png")

    plot_yearly_crop_yields(
        simulation_state,
        plots_dir / "yearly_crop_yields.png"
    )
    print("  - plots/yearly_crop_yields.png")

    plot_yearly_water_costs(
        all_metrics["farm_metrics"],
        plots_dir / "yearly_water_costs.png"
    )
    print("  - plots/yearly_water_costs.png")

    plot_yearly_crop_revenue(
        all_metrics["farm_metrics"],
        plots_dir / "yearly_crop_revenue.png"
    )
    print("  - plots/yearly_crop_revenue.png")

    # Legacy community plots (kept for reference)
    print("\n  Generating legacy plots...")
    
    plot_community_water_use(
        all_metrics["community_metrics"],
        plots_dir / "legacy_community_water_use.png"
    )
    print("  - plots/legacy_community_water_use.png")

    plot_community_self_sufficiency(
        all_metrics["community_metrics"],
        plots_dir / "legacy_community_self_sufficiency.png"
    )
    print("  - plots/legacy_community_self_sufficiency.png")

    # Decision metadata visualizations
    plot_daily_cost_distribution(
        simulation_state,
        plots_dir / "daily_cost_distribution.png"
    )
    print("  - plots/daily_cost_distribution.png")

    plot_decision_reason_counts(
        simulation_state,
        plots_dir / "decision_reason_counts.png"
    )
    print("  - plots/decision_reason_counts.png")

    plot_farm_water_sources_area(
        simulation_state,
        plots_dir / "farm_water_sources.png"
    )
    print("  - plots/farm_water_sources.png")

    print(f"\nResults written to: {output_dir}")
    return output_dir


def main():
    """Run simulation and write results from command line."""
    import sys

    from src.settings.loader import load_scenario
    from src.simulation.simulation import run_simulation

    if len(sys.argv) < 2:
        print("Usage: python src/simulation/results.py <scenario_file> [output_dir]")
        print("Example: python src/simulation/results.py settings/dev_scenario/dev.yaml")
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
