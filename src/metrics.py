# Metrics calculator for Water Simulation MVP
# Layer 3: Simulation Engine
#
# Computes yearly output metrics from simulation results:
# 1. Total water use (m3)
# 2. Water use per yield (m3/kg) - by crop and total
# 3. Water cost per unit (USD/m3)
# 4. Self-sufficiency percentage (groundwater / total water)

from dataclasses import dataclass, field


@dataclass
class ComputedYearlyMetrics:
    """Computed metrics for one farm for one year.

    Derived from YearlyFarmMetrics with additional calculated values.
    """
    year: int
    farm_id: str
    farm_name: str
    water_policy: str

    # Volume metrics
    total_water_m3: float
    groundwater_m3: float
    municipal_m3: float

    # Yield metrics
    total_yield_kg: float

    # Cost metrics
    total_water_cost_usd: float

    # Computed ratios
    water_per_yield_m3_kg: float  # total_water / total_yield
    cost_per_m3_usd: float  # total_cost / total_water
    self_sufficiency_pct: float  # groundwater / total_water * 100

    # Per-crop metrics
    crop_water_per_yield: dict = field(default_factory=dict)  # {crop: m3/kg}


@dataclass
class CommunityYearlyMetrics:
    """Aggregated metrics for entire community for one year."""
    year: int

    # Volume totals
    total_water_m3: float
    total_groundwater_m3: float
    total_municipal_m3: float

    # Yield totals
    total_yield_kg: float

    # Cost totals
    total_water_cost_usd: float

    # Computed averages
    avg_water_per_yield_m3_kg: float
    avg_cost_per_m3_usd: float
    community_self_sufficiency_pct: float

    # Per-farm breakdown
    farm_metrics: list = field(default_factory=list)


def compute_yearly_metrics(yearly_farm_metrics):
    """Compute derived metrics from raw yearly farm metrics.

    Args:
        yearly_farm_metrics: YearlyFarmMetrics from simulation

    Returns:
        ComputedYearlyMetrics with calculated ratios
    """
    m = yearly_farm_metrics

    # Calculate ratios (with zero-division protection)
    if m.total_water_m3 > 0:
        cost_per_m3 = m.total_water_cost_usd / m.total_water_m3
        self_sufficiency = 100 * m.groundwater_m3 / m.total_water_m3
    else:
        cost_per_m3 = 0.0
        self_sufficiency = 0.0

    if m.total_yield_kg > 0:
        water_per_yield = m.total_water_m3 / m.total_yield_kg
    else:
        water_per_yield = 0.0

    # Calculate per-crop water efficiency
    crop_water_per_yield = {}
    for crop_name, water_m3 in m.crop_water_m3.items():
        yield_kg = m.crop_yield_kg.get(crop_name, 0)
        if yield_kg > 0:
            crop_water_per_yield[crop_name] = water_m3 / yield_kg
        else:
            crop_water_per_yield[crop_name] = 0.0

    return ComputedYearlyMetrics(
        year=m.year,
        farm_id=m.farm_id,
        farm_name=m.farm_name,
        water_policy=m.water_policy,
        total_water_m3=m.total_water_m3,
        groundwater_m3=m.groundwater_m3,
        municipal_m3=m.municipal_m3,
        total_yield_kg=m.total_yield_kg,
        total_water_cost_usd=m.total_water_cost_usd,
        water_per_yield_m3_kg=water_per_yield,
        cost_per_m3_usd=cost_per_m3,
        self_sufficiency_pct=self_sufficiency,
        crop_water_per_yield=crop_water_per_yield,
    )


def aggregate_community_metrics(yearly_farm_metrics_list, year):
    """Aggregate farm metrics into community-level metrics for a year.

    Args:
        yearly_farm_metrics_list: List of YearlyFarmMetrics for the year
        year: Year for the metrics

    Returns:
        CommunityYearlyMetrics
    """
    # Filter to specified year
    year_metrics = [m for m in yearly_farm_metrics_list if m.year == year]

    if not year_metrics:
        return None

    # Sum totals across farms
    total_water = sum(m.total_water_m3 for m in year_metrics)
    total_gw = sum(m.groundwater_m3 for m in year_metrics)
    total_muni = sum(m.municipal_m3 for m in year_metrics)
    total_yield = sum(m.total_yield_kg for m in year_metrics)
    total_cost = sum(m.total_water_cost_usd for m in year_metrics)

    # Calculate averages
    if total_water > 0:
        avg_cost_per_m3 = total_cost / total_water
        self_sufficiency = 100 * total_gw / total_water
    else:
        avg_cost_per_m3 = 0.0
        self_sufficiency = 0.0

    if total_yield > 0:
        avg_water_per_yield = total_water / total_yield
    else:
        avg_water_per_yield = 0.0

    # Compute individual farm metrics
    farm_metrics = [compute_yearly_metrics(m) for m in year_metrics]

    return CommunityYearlyMetrics(
        year=year,
        total_water_m3=total_water,
        total_groundwater_m3=total_gw,
        total_municipal_m3=total_muni,
        total_yield_kg=total_yield,
        total_water_cost_usd=total_cost,
        avg_water_per_yield_m3_kg=avg_water_per_yield,
        avg_cost_per_m3_usd=avg_cost_per_m3,
        community_self_sufficiency_pct=self_sufficiency,
        farm_metrics=farm_metrics,
    )


def compute_all_metrics(simulation_state):
    """Compute all metrics from simulation results.

    Args:
        simulation_state: SimulationState with yearly_metrics

    Returns:
        dict: {
            'farm_metrics': [ComputedYearlyMetrics],
            'community_metrics': [CommunityYearlyMetrics],
            'years': [int]
        }
    """
    # Get all years in the simulation
    years = sorted(set(m.year for m in simulation_state.yearly_metrics))

    # Compute per-farm metrics
    farm_metrics = [
        compute_yearly_metrics(m) for m in simulation_state.yearly_metrics
    ]

    # Compute community metrics per year
    community_metrics = []
    for year in years:
        cm = aggregate_community_metrics(simulation_state.yearly_metrics, year)
        if cm:
            community_metrics.append(cm)

    return {
        "farm_metrics": farm_metrics,
        "community_metrics": community_metrics,
        "years": years,
    }


def summarize_farm(farm_metrics_list):
    """Generate summary statistics for a farm across all years.

    Args:
        farm_metrics_list: List of ComputedYearlyMetrics for one farm

    Returns:
        dict with summary statistics
    """
    if not farm_metrics_list:
        return {}

    n = len(farm_metrics_list)
    total_water = sum(m.total_water_m3 for m in farm_metrics_list)
    total_yield = sum(m.total_yield_kg for m in farm_metrics_list)
    total_cost = sum(m.total_water_cost_usd for m in farm_metrics_list)
    total_gw = sum(m.groundwater_m3 for m in farm_metrics_list)

    return {
        "farm_id": farm_metrics_list[0].farm_id,
        "farm_name": farm_metrics_list[0].farm_name,
        "water_policy": farm_metrics_list[0].water_policy,
        "years": n,
        "total_water_m3": total_water,
        "total_yield_kg": total_yield,
        "total_cost_usd": total_cost,
        "total_groundwater_m3": total_gw,
        "avg_water_per_year_m3": total_water / n if n > 0 else 0,
        "avg_yield_per_year_kg": total_yield / n if n > 0 else 0,
        "avg_cost_per_year_usd": total_cost / n if n > 0 else 0,
        "overall_water_per_yield_m3_kg": total_water / total_yield if total_yield > 0 else 0,
        "overall_cost_per_m3_usd": total_cost / total_water if total_water > 0 else 0,
        "overall_self_sufficiency_pct": 100 * total_gw / total_water if total_water > 0 else 0,
    }


def compare_policies(all_metrics):
    """Generate policy comparison summary.

    Args:
        all_metrics: Output from compute_all_metrics()

    Returns:
        dict with policy comparison data
    """
    # Group farm metrics by farm
    by_farm = {}
    for m in all_metrics["farm_metrics"]:
        if m.farm_id not in by_farm:
            by_farm[m.farm_id] = []
        by_farm[m.farm_id].append(m)

    # Generate summaries
    summaries = [summarize_farm(metrics) for metrics in by_farm.values()]

    # Sort by total cost (lowest first)
    summaries.sort(key=lambda s: s["total_cost_usd"])

    return {
        "farm_summaries": summaries,
        "total_years": len(all_metrics["years"]),
        "start_year": min(all_metrics["years"]),
        "end_year": max(all_metrics["years"]),
    }
