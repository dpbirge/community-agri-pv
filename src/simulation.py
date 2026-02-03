# Daily simulation loop for Water Simulation MVP
# Layer 3: Simulation Engine
#
# Executes daily water allocation for each farm over the simulation period.
# Tracks water usage, costs, and yields for policy comparison.

from datetime import date, timedelta
from pathlib import Path

from settings.policies import WaterPolicyContext, WaterAllocation
from src.data_loader import SimulationDataLoader
from src.state import (
    SimulationState,
    FarmState,
    CropState,
    DailyWaterRecord,
    YearlyFarmMetrics,
    initialize_simulation_state,
    reinitialize_farm_crops_for_year,
)


# Default maintenance cost per m3 of groundwater treatment (USD)
DEFAULT_GW_MAINTENANCE_PER_M3 = 0.05


def calculate_farm_demand(farm_state, current_date, data_loader):
    """Calculate total irrigation demand for a farm on a given day.

    Args:
        farm_state: FarmState with active crops
        current_date: Current simulation date
        data_loader: SimulationDataLoader for irrigation lookup

    Returns:
        tuple: (total_demand_m3, crop_demands dict {crop_name: demand_m3})
    """
    total_demand = 0.0
    crop_demands = {}

    for crop in farm_state.active_crops(current_date):
        # Get daily irrigation per hectare
        irr_per_ha = data_loader.get_irrigation_m3_per_ha(
            crop.crop_name, crop.planting_date, current_date
        )
        # Scale by crop area
        crop_demand = irr_per_ha * crop.area_ha
        crop_demands[crop.crop_name] = crop_demand
        total_demand += crop_demand

    return total_demand, crop_demands


def build_water_policy_context(
    demand_m3,
    current_date,
    scenario,
    data_loader,
    treatment_kwh_per_m3,
):
    """Build WaterPolicyContext for policy execution.

    Args:
        demand_m3: Total water demand
        current_date: Current simulation date
        scenario: Loaded scenario with pricing config
        data_loader: SimulationDataLoader for price lookup
        treatment_kwh_per_m3: Energy for groundwater treatment

    Returns:
        WaterPolicyContext
    """
    year = current_date.year

    # Get electricity price
    energy_price = data_loader.get_electricity_price_usd_kwh(current_date)

    # Get municipal water price based on pricing regime
    water_pricing = scenario.water_pricing
    if water_pricing.pricing_regime == "subsidized":
        municipal_price = data_loader.get_municipal_price_usd_m3(
            year, tier=water_pricing.subsidized.use_tier
        )
    else:
        # Unsubsidized: use base price with annual escalation
        base_price = water_pricing.unsubsidized.base_price_usd_m3
        escalation = water_pricing.unsubsidized.annual_escalation_pct / 100
        years_from_start = year - scenario.metadata.start_date.year
        municipal_price = base_price * ((1 + escalation) ** years_from_start)

    # For MVP: unlimited energy availability
    available_energy = float("inf")

    return WaterPolicyContext(
        demand_m3=demand_m3,
        available_energy_kwh=available_energy,
        treatment_kwh_per_m3=treatment_kwh_per_m3,
        gw_maintenance_per_m3=DEFAULT_GW_MAINTENANCE_PER_M3,
        municipal_price_per_m3=municipal_price,
        energy_price_per_kwh=energy_price,
    )


def execute_water_policy(farm_config, context):
    """Execute farm's water policy with given context.

    Args:
        farm_config: Farm from scenario (has water_policy attribute)
        context: WaterPolicyContext

    Returns:
        WaterAllocation
    """
    return farm_config.water_policy.allocate_water(context)


def update_farm_state(farm_state, allocation, crop_demands, current_date):
    """Update farm state after water allocation.

    Args:
        farm_state: FarmState to update
        allocation: WaterAllocation from policy
        crop_demands: dict {crop_name: demand_m3} for distributing water to crops
        current_date: Current simulation date
    """
    # Update cumulative water usage
    farm_state.cumulative_groundwater_m3 += allocation.groundwater_m3
    farm_state.cumulative_municipal_m3 += allocation.municipal_m3
    farm_state.cumulative_water_cost_usd += allocation.cost_usd

    # Record daily water allocation
    record = DailyWaterRecord(
        date=current_date,
        demand_m3=sum(crop_demands.values()),
        groundwater_m3=allocation.groundwater_m3,
        municipal_m3=allocation.municipal_m3,
        cost_usd=allocation.cost_usd,
        energy_kwh=allocation.energy_used_kwh,
    )
    farm_state.daily_water_records.append(record)

    # Distribute water to active crops (for tracking)
    total_allocated = allocation.groundwater_m3 + allocation.municipal_m3
    for crop in farm_state.active_crops(current_date):
        if crop.crop_name in crop_demands:
            # Assume water is allocated proportionally to demand
            crop.cumulative_water_m3 += crop_demands[crop.crop_name]


def process_harvests(farm_state, current_date):
    """Check for and process crop harvests.

    Args:
        farm_state: FarmState to check
        current_date: Current simulation date

    Returns:
        list: Harvested CropState objects
    """
    harvested = []
    for crop in farm_state.crops:
        if not crop.is_harvested and crop.harvest_date <= current_date:
            # Harvest this crop
            crop.is_harvested = True
            crop.harvest_yield_kg = crop.expected_total_yield_kg
            farm_state.cumulative_yield_kg += crop.harvest_yield_kg
            harvested.append(crop)
    return harvested


def snapshot_yearly_metrics(farm_state, year, crop_water_totals):
    """Create yearly metrics snapshot for a farm.

    Args:
        farm_state: FarmState with accumulated data
        year: Year for the snapshot
        crop_water_totals: dict {crop_name: total_m3} for the year

    Returns:
        YearlyFarmMetrics
    """
    # Calculate crop yields for the year (harvested crops)
    crop_yields = {}
    for crop in farm_state.crops:
        if crop.is_harvested:
            crop_yields[crop.crop_name] = crop.harvest_yield_kg

    return YearlyFarmMetrics(
        year=year,
        farm_id=farm_state.farm_id,
        farm_name=farm_state.farm_name,
        water_policy=farm_state.water_policy_name,
        total_water_m3=farm_state.total_water_m3(),
        groundwater_m3=farm_state.cumulative_groundwater_m3,
        municipal_m3=farm_state.cumulative_municipal_m3,
        total_yield_kg=farm_state.cumulative_yield_kg,
        total_water_cost_usd=farm_state.cumulative_water_cost_usd,
        crop_water_m3=dict(crop_water_totals),
        crop_yield_kg=crop_yields,
    )


def reset_farm_for_new_year(farm_state):
    """Reset farm state accumulators for new year tracking.

    Note: Keeps daily_water_records for full simulation history.

    Args:
        farm_state: FarmState to reset
    """
    farm_state.cumulative_groundwater_m3 = 0.0
    farm_state.cumulative_municipal_m3 = 0.0
    farm_state.cumulative_water_cost_usd = 0.0
    farm_state.cumulative_yield_kg = 0.0


def run_simulation(scenario, data_loader=None, verbose=False):
    """Run daily simulation from start_date to end_date.

    Args:
        scenario: Loaded Scenario object
        data_loader: SimulationDataLoader (created if not provided)
        verbose: If True, print progress messages

    Returns:
        SimulationState with all results
    """
    if data_loader is None:
        data_loader = SimulationDataLoader()

    # Get treatment energy from scenario infrastructure
    salinity_level = scenario.infrastructure.water_treatment.salinity_level
    treatment_kwh_per_m3 = data_loader.get_treatment_energy_kwh_m3(salinity_level)

    # Initialize state
    state = initialize_simulation_state(scenario, data_loader)

    if verbose:
        print(f"Starting simulation: {state.start_date} to {state.end_date}")
        print(f"Farms: {len(state.farms)}, Treatment energy: {treatment_kwh_per_m3:.2f} kWh/m3")

    # Track crop water usage per year per farm
    farm_crop_water = {f.farm_id: {} for f in state.farms}

    # Main simulation loop
    current_year = state.current_year()
    days_simulated = 0

    while not state.is_simulation_complete():
        current_date = state.current_date
        prev_year = current_year
        current_year = current_date.year

        # Check for year boundary
        if current_year != prev_year:
            if verbose:
                print(f"Year boundary: {prev_year} -> {current_year}")

            # Snapshot yearly metrics for each farm
            for i, farm_state in enumerate(state.farms):
                farm_config = scenario.farms[i]
                metrics = snapshot_yearly_metrics(
                    farm_state, prev_year, farm_crop_water[farm_state.farm_id]
                )
                state.yearly_metrics.append(metrics)

                # Reset for new year
                reset_farm_for_new_year(farm_state)
                farm_crop_water[farm_state.farm_id] = {}

                # Re-initialize crops for new year
                reinitialize_farm_crops_for_year(
                    farm_state, farm_config, current_year, data_loader
                )

        # Process each farm
        for i, farm_state in enumerate(state.farms):
            farm_config = scenario.farms[i]

            # Calculate irrigation demand
            demand_m3, crop_demands = calculate_farm_demand(
                farm_state, current_date, data_loader
            )

            if demand_m3 > 0:
                # Build policy context
                context = build_water_policy_context(
                    demand_m3, current_date, scenario, data_loader, treatment_kwh_per_m3
                )

                # Execute water policy
                allocation = execute_water_policy(farm_config, context)

                # Update farm state
                update_farm_state(farm_state, allocation, crop_demands, current_date)

                # Track crop water for yearly metrics
                for crop_name, crop_m3 in crop_demands.items():
                    if crop_name not in farm_crop_water[farm_state.farm_id]:
                        farm_crop_water[farm_state.farm_id][crop_name] = 0.0
                    farm_crop_water[farm_state.farm_id][crop_name] += crop_m3

            # Process any harvests
            harvested = process_harvests(farm_state, current_date)

        # Advance to next day
        state.advance_day()
        days_simulated += 1

        if verbose and days_simulated % 365 == 0:
            print(f"  Simulated {days_simulated} days...")

    # Capture final year metrics
    final_year = state.end_date.year
    for i, farm_state in enumerate(state.farms):
        metrics = snapshot_yearly_metrics(
            farm_state, final_year, farm_crop_water[farm_state.farm_id]
        )
        state.yearly_metrics.append(metrics)

    if verbose:
        print(f"Simulation complete: {days_simulated} days, {len(state.yearly_metrics)} yearly metrics")

    return state


def main():
    """Run simulation from command line."""
    import sys

    from settings.scripts.loader import load_scenario

    if len(sys.argv) < 2:
        print("Usage: python src/simulation.py <scenario_file>")
        print("Example: python src/simulation.py settings/scenarios/water_policy_only.yaml")
        sys.exit(1)

    scenario_path = sys.argv[1]
    print(f"Loading scenario: {scenario_path}")
    scenario = load_scenario(scenario_path)

    print("Running simulation...")
    state = run_simulation(scenario, verbose=True)

    # Print summary
    print("\n=== SIMULATION SUMMARY ===")
    print(f"Years simulated: {state.start_date.year} - {state.end_date.year}")

    # Group metrics by farm
    by_farm = {}
    for m in state.yearly_metrics:
        if m.farm_id not in by_farm:
            by_farm[m.farm_id] = []
        by_farm[m.farm_id].append(m)

    for farm_id, metrics in by_farm.items():
        print(f"\n{farm_id} ({metrics[0].farm_name}) - Policy: {metrics[0].water_policy}")
        total_water = sum(m.total_water_m3 for m in metrics)
        total_yield = sum(m.total_yield_kg for m in metrics)
        total_cost = sum(m.total_water_cost_usd for m in metrics)
        total_gw = sum(m.groundwater_m3 for m in metrics)

        print(f"  Total water: {total_water:,.0f} m3")
        print(f"  Total yield: {total_yield:,.0f} kg")
        print(f"  Total cost: ${total_cost:,.2f}")
        if total_water > 0:
            print(f"  Self-sufficiency: {100 * total_gw / total_water:.1f}%")
            print(f"  Water per yield: {total_water / total_yield:.4f} m3/kg")
            print(f"  Cost per m3: ${total_cost / total_water:.4f}")


if __name__ == "__main__":
    main()
