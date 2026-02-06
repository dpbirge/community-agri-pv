"""Monte Carlo simulation framework for the community agri-PV simulation.

Runs the simulation many times with stochastic price and yield variations
to evaluate community resilience under uncertainty. Extends the sensitivity
analysis (sensitivity.py) from one-at-a-time perturbation to simultaneous
random sampling across all parameters.

Phase 10-11 of the development plan (mvp-calculations.md Section 8).
"""

import random
import time
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Optional

from src.settings.loader import load_scenario
from src.simulation.simulation import run_simulation
from src.simulation.data_loader import SimulationDataLoader
from src.simulation.metrics import compute_all_metrics


# Default coefficient of variation for each stochastic parameter.
# CV = standard_deviation / mean, where mean is 1.0 (the baseline multiplier).
DEFAULT_VARIATION_RANGES = {
    # Input price variations
    "municipal_water": 0.15,   # ±15% water price volatility
    "electricity": 0.20,       # ±20% electricity price volatility
    "diesel": 0.25,            # ±25% diesel price volatility (global oil)
    "fertilizer": 0.15,        # ±15% fertilizer cost volatility
    # Crop price variations
    "crop_tomato": 0.25,       # ±25% crop price volatility
    "crop_potato": 0.20,
    "crop_onion": 0.20,
    "crop_kale": 0.15,
    "crop_cucumber": 0.25,
    # Yield variation
    "yield_factor": 0.10,      # ±10% yield variation (weather, pests)
}


def _find_project_root(start_path: Path) -> Path:
    """Find project root by searching upward for data_registry.yaml."""
    current = start_path if start_path.is_dir() else start_path.parent
    for _ in range(10):
        if (current / "settings" / "data_registry.yaml").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return start_path.parent.parent


def sample_multipliers(
    variation_ranges: Dict[str, float], rng: random.Random
) -> Dict[str, float]:
    """Sample price multipliers from normal distributions.

    Each parameter gets a multiplier drawn from N(1.0, cv) where cv is
    the coefficient of variation. Multipliers are floored at 0.5 to avoid
    unrealistically low values (e.g., negative prices).

    Args:
        variation_ranges: {parameter_name: cv} mapping
        rng: Seeded random.Random instance

    Returns:
        dict of {parameter_name: multiplier} (excludes yield_factor)
    """
    multipliers = {}
    for param, cv in variation_ranges.items():
        if param == "yield_factor":
            continue  # Handled separately via scenario modification
        multiplier = max(0.5, rng.gauss(1.0, cv))
        multipliers[param] = multiplier
    return multipliers


def sample_yield_factor(
    base_yield_factor: float, cv: float, rng: random.Random
) -> float:
    """Sample a yield factor variation.

    Draws from N(base, base * cv), floored at 0.1 to prevent
    negative or zero yields.

    Args:
        base_yield_factor: Original yield_factor from scenario farm config
        cv: Coefficient of variation for yield
        rng: Seeded random.Random instance

    Returns:
        float: Sampled yield factor
    """
    return max(0.1, rng.gauss(base_yield_factor, base_yield_factor * cv))


def extract_run_outcomes(state, all_metrics, scenario) -> Dict:
    """Extract key outcome metrics from one simulation run.

    Pulls financial performance, yield totals, and resilience metrics
    from the simulation results into a flat dict for aggregation.

    Args:
        state: SimulationState from run_simulation()
        all_metrics: Output from compute_all_metrics()
        scenario: Scenario object used for the run

    Returns:
        dict with outcome metrics for this run
    """
    fp = all_metrics.get("financial_performance") or {}
    farm_metrics = all_metrics["farm_metrics"]
    years = all_metrics["years"]

    # Sum across all years and farms
    total_revenue = sum(m.total_crop_revenue_usd for m in farm_metrics)
    total_water_cost = sum(m.total_water_cost_usd for m in farm_metrics)
    total_yield = sum(m.total_yield_kg for m in farm_metrics)

    # Get final year metrics for self-sufficiency snapshot
    last_year = max(years) if years else None
    last_year_metrics = (
        [m for m in farm_metrics if m.year == last_year] if last_year else []
    )

    # Average self-sufficiency across farms in the final year
    water_self_suff = 0.0
    energy_self_suff = 0.0
    if last_year_metrics:
        water_self_suff = (
            sum(m.self_sufficiency_pct for m in last_year_metrics)
            / len(last_year_metrics)
        )
        energy_self_suff = (
            sum(m.energy_self_sufficiency_pct for m in last_year_metrics)
            / len(last_year_metrics)
        )

    n_years = len(years) if years else 1

    return {
        "total_revenue_usd": total_revenue,
        "total_yield_kg": total_yield,
        "total_water_cost_usd": total_water_cost,
        "net_income_usd": fp.get("avg_annual_net_income_usd", 0) * n_years,
        "avg_annual_net_income_usd": fp.get("avg_annual_net_income_usd", 0),
        "npv_usd": fp.get("npv_usd", 0),
        "cash_reserves_usd": fp.get("cash_reserves_usd", 0),
        "energy_self_sufficiency_pct": energy_self_suff,
        "water_self_sufficiency_pct": water_self_suff,
        "survived": fp.get("cash_reserves_usd", 0) >= 0,
    }


def compute_monte_carlo_summary(run_results: List[Dict]) -> Dict:
    """Compute summary statistics from Monte Carlo runs.

    Aggregates per-run outcome metrics into percentile distributions,
    survival rates, and risk indicators.

    Args:
        run_results: List of dicts from extract_run_outcomes()

    Returns:
        dict with:
            n_runs: number of runs
            survival_rate_pct: % of runs that stayed solvent
            probability_of_negative_income_pct: % of runs with negative avg income
            avg_net_income_usd: mean annual net income across runs
            std_net_income_usd: standard deviation of annual net income
            worst_case_income_usd: 5th percentile annual income
            net_income_percentiles: {p5, p25, p50, p75, p95}
            npv_percentiles: {p5, p25, p50, p75, p95}
    """
    incomes = sorted(r["avg_annual_net_income_usd"] for r in run_results)
    npvs = sorted(r["npv_usd"] for r in run_results)
    survived = [r["survived"] for r in run_results]

    n = len(incomes)

    def percentile(data, pct):
        """Compute percentile using nearest-rank method."""
        idx = int(pct / 100 * (len(data) - 1))
        return data[idx]

    mean_income = sum(incomes) / n
    std_income = (
        (sum((i - mean_income) ** 2 for i in incomes) / (n - 1)) ** 0.5
        if n > 1
        else 0.0
    )

    return {
        "n_runs": n,
        "survival_rate_pct": sum(survived) / n * 100,
        "probability_of_negative_income_pct": (
            sum(1 for i in incomes if i < 0) / n * 100
        ),
        "avg_net_income_usd": mean_income,
        "std_net_income_usd": std_income,
        "worst_case_income_usd": percentile(incomes, 5),
        "net_income_percentiles": {
            "p5": percentile(incomes, 5),
            "p25": percentile(incomes, 25),
            "p50": percentile(incomes, 50),
            "p75": percentile(incomes, 75),
            "p95": percentile(incomes, 95),
        },
        "npv_percentiles": {
            "p5": percentile(npvs, 5),
            "p25": percentile(npvs, 25),
            "p50": percentile(npvs, 50),
            "p75": percentile(npvs, 75),
            "p95": percentile(npvs, 95),
        },
    }


def run_monte_carlo(
    scenario_path: str,
    n_runs: int = 100,
    seed: int = 42,
    variation_ranges: Optional[Dict] = None,
    verbose: bool = False,
) -> Dict:
    """Run Monte Carlo simulation with stochastic price/yield variations.

    For each run:
    1. Sample price multipliers from normal distributions
    2. Sample yield variation factor
    3. Run full simulation with sampled parameters
    4. Record outcome metrics

    Each run is a full simulation using run_simulation() and
    compute_all_metrics(). Price variations are applied via the
    SimulationDataLoader's price_multipliers parameter. Yield variations
    are applied by modifying the scenario's per-farm yield_factor on a
    deep-copied Scenario object.

    Args:
        scenario_path: Path to scenario YAML file
        n_runs: Number of simulation runs (default 100)
        seed: Random seed for reproducibility (default 42)
        variation_ranges: Optional dict overriding default parameter ranges.
            Keys are parameter names (matching DEFAULT_VARIATION_RANGES),
            values are coefficients of variation (CV = std / mean).
        verbose: Print progress messages

    Returns:
        dict with:
            runs: list of per-run result dicts (outcomes + sampled parameters)
            summary: aggregated statistics from compute_monte_carlo_summary()
            parameters: the variation ranges used
    """
    # Merge user overrides with defaults
    ranges = dict(DEFAULT_VARIATION_RANGES)
    if variation_ranges:
        ranges.update(variation_ranges)

    # Initialize reproducible RNG
    rng = random.Random(seed)

    # Resolve project root and load base scenario once
    project_root = str(_find_project_root(Path(scenario_path)))
    base_scenario = load_scenario(scenario_path)

    # Extract base yield factors for each farm (for stochastic perturbation)
    base_yield_factors = {
        farm.id: farm.yield_factor for farm in base_scenario.farms
    }
    yield_cv = ranges.get("yield_factor", 0.0)

    if verbose:
        print(f"Monte Carlo: {n_runs} runs, seed={seed}, "
              f"{len(ranges)} stochastic parameters")
        print(f"  Scenario: {scenario_path}")
        print(f"  Farms: {len(base_scenario.farms)}, "
              f"yield CV: {yield_cv:.0%}")

    run_results = []
    t_start = time.time()

    for run_idx in range(n_runs):
        # 1. Sample price multipliers from normal distributions
        price_multipliers = sample_multipliers(ranges, rng)

        # 2. Deep-copy scenario and apply yield variation
        scenario = deepcopy(base_scenario)
        sampled_yield_factors = {}
        if yield_cv > 0:
            for farm in scenario.farms:
                base_yf = base_yield_factors[farm.id]
                farm.yield_factor = sample_yield_factor(base_yf, yield_cv, rng)
                sampled_yield_factors[farm.id] = farm.yield_factor
        else:
            sampled_yield_factors = dict(base_yield_factors)

        # 3. Create data loader with sampled price multipliers
        data_loader = SimulationDataLoader(
            use_research_prices=True,
            project_root=project_root,
            price_multipliers=price_multipliers,
        )

        # 4. Run full simulation
        state = run_simulation(scenario, data_loader=data_loader, verbose=False)

        # 5. Compute all metrics (including financial performance)
        all_metrics = compute_all_metrics(
            state, data_loader=data_loader, scenario=scenario
        )

        # 6. Extract outcome metrics for this run
        outcomes = extract_run_outcomes(state, all_metrics, scenario)
        outcomes["run_index"] = run_idx
        outcomes["price_multipliers"] = dict(price_multipliers)
        outcomes["yield_factors"] = dict(sampled_yield_factors)

        run_results.append(outcomes)

        # Progress reporting at ~10% intervals
        if verbose and (run_idx + 1) % max(1, n_runs // 10) == 0:
            elapsed = time.time() - t_start
            rate = (run_idx + 1) / elapsed if elapsed > 0 else 0
            remaining = (n_runs - run_idx - 1) / rate if rate > 0 else 0
            print(
                f"  Run {run_idx + 1}/{n_runs} "
                f"({elapsed:.1f}s elapsed, ~{remaining:.0f}s remaining)"
            )

    elapsed_total = time.time() - t_start

    # Compute summary statistics across all runs
    summary = compute_monte_carlo_summary(run_results)
    summary["elapsed_seconds"] = elapsed_total

    if verbose:
        print(
            f"  All {n_runs} runs complete in {elapsed_total:.1f}s "
            f"({elapsed_total / n_runs:.2f}s per run)"
        )

    return {
        "runs": run_results,
        "summary": summary,
        "parameters": ranges,
    }


def main():
    """Run Monte Carlo from command line."""
    import sys

    if len(sys.argv) < 2:
        print(
            "Usage: python -m src.simulation.monte_carlo "
            "<scenario.yaml> [n_runs]"
        )
        sys.exit(1)

    scenario_path = sys.argv[1]
    n_runs = int(sys.argv[2]) if len(sys.argv) > 2 else 100

    print(f"Running Monte Carlo simulation: {scenario_path}")
    print(f"  Runs: {n_runs}")
    print(f"  Variation ranges: {len(DEFAULT_VARIATION_RANGES)} parameters")

    results = run_monte_carlo(scenario_path, n_runs=n_runs, verbose=True)

    summary = results["summary"]
    print(f"\n{'='*60}")
    print(f"MONTE CARLO RESULTS ({summary['n_runs']} runs)")
    print(f"{'='*60}")
    print(f"Survival rate: {summary['survival_rate_pct']:.1f}%")
    print(
        f"Avg annual net income: ${summary['avg_net_income_usd']:,.0f} "
        f"\u00b1 ${summary['std_net_income_usd']:,.0f}"
    )
    print(f"Worst case (P5): ${summary['worst_case_income_usd']:,.0f}")
    print(
        f"P(negative income): "
        f"{summary['probability_of_negative_income_pct']:.1f}%"
    )

    pctiles = summary["net_income_percentiles"]
    print(f"\nNet income distribution:")
    for key in ["p5", "p25", "p50", "p75", "p95"]:
        print(f"  {key.upper()}: ${pctiles[key]:,.0f}")

    npv_pctiles = summary["npv_percentiles"]
    print(f"\nNPV distribution:")
    for key in ["p5", "p25", "p50", "p75", "p95"]:
        print(f"  {key.upper()}: ${npv_pctiles[key]:,.0f}")

    print(
        f"\nElapsed: {summary['elapsed_seconds']:.1f}s "
        f"({summary['elapsed_seconds'] / summary['n_runs']:.2f}s per run)"
    )


if __name__ == "__main__":
    main()
