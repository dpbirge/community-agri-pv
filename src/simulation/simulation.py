# Daily simulation loop for Water Simulation MVP
# Layer 3: Simulation Engine
#
# Executes daily water allocation for each farm over the simulation period.
# Tracks water usage, costs, and yields for policy comparison.

from datetime import date, timedelta
from pathlib import Path

from src.policies import WaterPolicyContext, WaterAllocation
from src.policies.food_policies import FoodProcessingContext, ProcessingAllocation
from src.settings.calculations import calculate_pumping_energy, estimate_infrastructure_costs, calculate_household_demand
from src.simulation.data_loader import SimulationDataLoader
from src.simulation.state import (
    SimulationState,
    FarmState,
    CropState,
    AquiferState,
    WaterStorageState,
    DailyWaterRecord,
    DailyEnergyRecord,
    EnergyState,
    EconomicState,
    YearlyFarmMetrics,
    initialize_simulation_state,
    reinitialize_farm_crops_for_year,
)


# Default maintenance cost per m3 of groundwater treatment (USD)
DEFAULT_GW_MAINTENANCE_PER_M3 = 0.05


def calculate_system_constraints(scenario):
    """Calculate per-farm system constraints from scenario config.

    Infrastructure capacity is shared proportionally to farm area,
    per the architecture specification. Larger farms receive a larger
    share of well extraction and treatment throughput capacity.

    Args:
        scenario: Loaded Scenario with system config

    Returns:
        dict keyed by farm id, each value a dict with:
            max_groundwater_m3: daily groundwater extraction limit (m3)
            max_treatment_m3: daily treatment throughput limit (m3)
    """
    infra = scenario.infrastructure

    # Total well capacity: number_of_wells × well_flow_rate_m3_day
    wells = infra.groundwater_wells
    total_well_capacity = wells.number_of_wells * wells.well_flow_rate_m3_day

    # Total treatment capacity
    treatment = infra.water_treatment
    total_treatment_capacity = treatment.system_capacity_m3_day

    # Area-proportional sharing: each farm's share = farm_area / total_area
    total_farm_area = sum(farm.area_ha for farm in scenario.farms)

    per_farm_constraints = {}
    for farm in scenario.farms:
        if total_farm_area > 0:
            area_fraction = farm.area_ha / total_farm_area
        else:
            # Fallback to equal sharing if no area data
            area_fraction = 1.0 / len(scenario.farms)

        per_farm_constraints[farm.id] = {
            "max_groundwater_m3": total_well_capacity * area_fraction,
            "max_treatment_m3": total_treatment_capacity * area_fraction,
        }

    return per_farm_constraints


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
        # Note: Precomputed irrigation data already includes drip irrigation
        # efficiency (η=0.90). See generate_irrigation_and_yields.py line:
        #   irrigation_m3_per_ha = (etc * 10) / DRIP_EFFICIENCY
        # Do NOT divide by efficiency again here to avoid double-counting.
        irr_per_ha = data_loader.get_irrigation_m3_per_ha(
            crop.crop_name, crop.planting_date, current_date
        )
        # Scale by crop area
        crop_demand = irr_per_ha * crop.area_ha
        crop_demands[crop.crop_name] = crop_demands.get(crop.crop_name, 0.0) + crop_demand
        total_demand += crop_demand

    return total_demand, crop_demands


def build_water_policy_context(
    demand_m3,
    current_date,
    scenario,
    data_loader,
    treatment_kwh_per_m3,
    constraints,
    cumulative_gw_year_m3=0.0,
    cumulative_gw_month_m3=0.0,
    aquifer_state=None,
):
    """Build WaterPolicyContext for policy execution.

    Args:
        demand_m3: Total water demand
        current_date: Current simulation date
        scenario: Loaded scenario with pricing config
        data_loader: SimulationDataLoader for price lookup
        treatment_kwh_per_m3: Energy for groundwater treatment
        constraints: dict with max_groundwater_m3 and max_treatment_m3
        cumulative_gw_year_m3: Cumulative groundwater used this year (for quota policies)
        cumulative_gw_month_m3: Cumulative groundwater used this month (for quota policies)
        aquifer_state: Optional AquiferState for dynamic pumping head calculation.
            When provided and max_drawdown_m > 0, the effective pumping depth increases
            with cumulative extraction per the linearized drawdown model
            (calculations.md Section 2).

    Returns:
        WaterPolicyContext
    """
    year = current_date.year

    # Get agricultural electricity price (for water pumping and treatment)
    energy_pricing = scenario.energy_pricing
    ag_energy = energy_pricing.agricultural
    if ag_energy.pricing_regime == "subsidized":
        energy_price = ag_energy.subsidized_price_usd_kwh
    else:
        energy_price = ag_energy.unsubsidized_price_usd_kwh

    # Get agricultural water price based on pricing regime
    water_pricing = scenario.water_pricing
    ag_pricing = water_pricing.agricultural

    if ag_pricing.pricing_regime == "subsidized":
        municipal_price = ag_pricing.subsidized_price_usd_m3
    else:
        # Unsubsidized: use base price with annual escalation
        base_price = ag_pricing.unsubsidized_base_price_usd_m3
        escalation = ag_pricing.annual_escalation_pct / 100
        years_from_start = year - scenario.metadata.start_date.year
        municipal_price = base_price * ((1 + escalation) ** years_from_start)

    # Calculate available energy for water treatment using precomputed power data
    pv_kw = scenario.infrastructure.pv.sys_capacity_kw
    wind_kw = scenario.infrastructure.wind.sys_capacity_kw
    if pv_kw > 0 or wind_kw > 0:
        daily_pv_kwh = 0.0
        daily_wind_kwh = 0.0
        if pv_kw > 0:
            pv_kwh_per_kw = data_loader.get_pv_kwh_per_kw(
                current_date, density_variant=scenario.infrastructure.pv.density
            )
            # Apply panel degradation: ~0.5%/yr for mono-crystalline Si (IEC 61215).
            # Cumulative output loss is (1 - rate)^years from commissioning date.
            degradation_rate = 0.005  # 0.5%/yr
            years_since_start = (current_date - scenario.metadata.start_date).days / 365.25
            degradation_factor = (1 - degradation_rate) ** years_since_start
            daily_pv_kwh = pv_kw * pv_kwh_per_kw * degradation_factor
        if wind_kw > 0:
            wind_kwh_per_kw = data_loader.get_wind_kwh_per_kw(
                current_date, turbine_variant=scenario.infrastructure.wind.type
            )
            daily_wind_kwh = wind_kw * wind_kwh_per_kw
        available_energy = daily_pv_kwh + daily_wind_kwh
    else:
        # Grid-powered: unlimited energy for treatment
        available_energy = float("inf")

    # Calculate pumping energy from well parameters.
    # Use dynamic head if aquifer state is available and drawdown feedback is enabled;
    # otherwise fall back to static well_depth_m from config (backward-compatible).
    wells = scenario.infrastructure.groundwater_wells
    if aquifer_state is not None:
        effective_depth = aquifer_state.get_effective_head_m(wells.well_depth_m)
    else:
        effective_depth = wells.well_depth_m
    pumping = calculate_pumping_energy(
        well_depth_m=effective_depth,
        flow_rate_m3_day=wells.well_flow_rate_m3_day,
    )
    pumping_kwh_per_m3 = pumping["total_pumping_energy_kwh_per_m3"]

    # Fixed conveyance energy per architecture spec
    conveyance_kwh_per_m3 = 0.2

    return WaterPolicyContext(
        demand_m3=demand_m3,
        available_energy_kwh=available_energy,
        treatment_kwh_per_m3=treatment_kwh_per_m3,
        gw_maintenance_per_m3=DEFAULT_GW_MAINTENANCE_PER_M3,
        municipal_price_per_m3=municipal_price,
        energy_price_per_kwh=energy_price,
        pumping_kwh_per_m3=pumping_kwh_per_m3,
        conveyance_kwh_per_m3=conveyance_kwh_per_m3,
        max_groundwater_m3=constraints["max_groundwater_m3"],
        max_treatment_m3=constraints["max_treatment_m3"],
        cumulative_gw_year_m3=cumulative_gw_year_m3,
        cumulative_gw_month_m3=cumulative_gw_month_m3,
        current_month=current_date.month,
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


def calculate_domestic_water_cost(
    household_m3: float,
    community_building_m3: float,
    current_date: date,
    scenario,
) -> float:
    """Calculate daily cost for domestic water consumption.

    Domestic water includes household and community building consumption.
    Costs are tracked at community level as operating expenses (not allocated
    to individual farms).

    Args:
        household_m3: Daily household water consumption
        community_building_m3: Daily community building water consumption
        current_date: Current simulation date
        scenario: Loaded scenario with pricing config

    Returns:
        float: Total domestic water cost (USD)
    """
    total_domestic_m3 = household_m3 + community_building_m3
    if total_domestic_m3 <= 0:
        return 0.0

    year = current_date.year
    water_pricing = scenario.water_pricing
    domestic_pricing = water_pricing.domestic

    if domestic_pricing.pricing_regime == "subsidized":
        price = domestic_pricing.subsidized_price_usd_m3
    else:
        # Unsubsidized: use base price with annual escalation
        base_price = domestic_pricing.unsubsidized_base_price_usd_m3
        escalation = domestic_pricing.annual_escalation_pct / 100
        years_from_start = year - scenario.metadata.start_date.year
        price = base_price * ((1 + escalation) ** years_from_start)

    return total_domestic_m3 * price


def calculate_domestic_electricity_cost(
    household_kwh: float,
    community_building_kwh: float,
    scenario,
) -> float:
    """Calculate daily cost for domestic electricity consumption.

    Domestic electricity includes household and community building consumption.
    Costs are tracked at community level as operating expenses (not allocated
    to individual farms).

    Args:
        household_kwh: Daily household electricity consumption
        community_building_kwh: Daily community building electricity consumption
        scenario: Loaded scenario with pricing config

    Returns:
        float: Total domestic electricity cost (USD)
    """
    total_domestic_kwh = household_kwh + community_building_kwh
    if total_domestic_kwh <= 0:
        return 0.0

    energy_pricing = scenario.energy_pricing
    domestic_pricing = energy_pricing.domestic

    if domestic_pricing.pricing_regime == "subsidized":
        price = domestic_pricing.subsidized_price_usd_kwh
    else:
        price = domestic_pricing.unsubsidized_price_usd_kwh

    return total_domestic_kwh * price


def update_farm_state(farm_state, allocation, crop_demands, current_date, energy_cost_usd=0.0):
    """Update farm state after water allocation.

    Args:
        farm_state: FarmState to update
        allocation: WaterAllocation from policy
        crop_demands: dict {crop_name: demand_m3} for distributing water to crops
        current_date: Current simulation date
        energy_cost_usd: Energy cost for water treatment this day (USD)
    """
    # Update cumulative water usage
    farm_state.cumulative_groundwater_m3 += allocation.groundwater_m3
    farm_state.cumulative_municipal_m3 += allocation.municipal_m3
    farm_state.cumulative_water_cost_usd += allocation.cost_usd

    # Update monthly consumption tracker
    farm_state.update_monthly_consumption(
        current_date,
        groundwater_m3=allocation.groundwater_m3,
        electricity_kwh=allocation.energy_used_kwh,
    )

    # Record daily water allocation with decision metadata
    metadata = allocation.metadata
    record = DailyWaterRecord(
        date=current_date,
        demand_m3=sum(crop_demands.values()),
        groundwater_m3=allocation.groundwater_m3,
        municipal_m3=allocation.municipal_m3,
        cost_usd=allocation.cost_usd,
        energy_kwh=allocation.energy_used_kwh,
        energy_cost_usd=energy_cost_usd,
        decision_reason=metadata.decision_reason if metadata else None,
        gw_cost_per_m3=metadata.gw_cost_per_m3 if metadata else None,
        muni_cost_per_m3=metadata.muni_cost_per_m3 if metadata else None,
        constraint_hit=metadata.constraint_hit if metadata else None,
    )
    farm_state.daily_water_records.append(record)

    # Distribute water to active crops proportionally to demand.
    # If allocation was constrained (well/treatment/energy limits), scale
    # each crop's water credit by the delivery ratio to avoid over-counting.
    # (C2 fix: previously credited full demand regardless of actual delivery)
    total_demand = sum(crop_demands.values())
    total_allocated = allocation.groundwater_m3 + allocation.municipal_m3
    delivery_ratio = total_allocated / total_demand if total_demand > 0 else 1.0

    for crop in farm_state.active_crops(current_date):
        if crop.crop_name in crop_demands:
            crop.cumulative_water_m3 += crop_demands[crop.crop_name] * delivery_ratio


def process_harvests(farm_state, current_date, data_loader, farm_config=None):
    """Check for and process crop harvests with food processing allocation.

    Applies the farm's food processing policy to determine how harvested crop
    is split across fresh/packaged/canned/dried pathways. Each pathway has
    different weight loss, post-harvest loss, and value multiplier characteristics
    loaded from CSV data files via data_loader.

    All crop-specific coefficients are loaded from CSV files:
    - Ky (yield response factors): yield_response_factors CSV
    - Weight loss by pathway: processing_specs CSV
    - Value-add multipliers: processing_specs CSV
    - Post-harvest loss by pathway: post_harvest_losses CSV

    When farm_config is None or has no food_policy, defaults to AllFresh behavior
    (100% fresh sale).

    Args:
        farm_state: FarmState to check
        current_date: Current simulation date
        data_loader: SimulationDataLoader for price and parameter lookup
        farm_config: Optional Farm config with food_policy attribute

    Returns:
        list: Harvested CropState objects
    """
    harvested = []
    for crop in farm_state.crops:
        if not crop.is_harvested and crop.harvest_date <= current_date:
            crop.is_harvested = True

            # Apply FAO water production function for water stress.
            # Y_actual = Y_potential × (1 - Ky × (1 - ET_actual / ET_crop))
            if crop.expected_total_water_m3 > 0:
                water_ratio = min(1.0, crop.cumulative_water_m3 / crop.expected_total_water_m3)
            else:
                water_ratio = 1.0

            ky = data_loader.get_ky_value(crop.crop_name)
            stress_factor = 1.0 - ky * (1.0 - water_ratio)
            stress_factor = max(0.0, min(1.0, stress_factor))

            crop.harvest_yield_kg = crop.expected_total_yield_kg * stress_factor

            # Get fresh farmgate price for revenue calculation
            price_per_kg = data_loader.get_crop_price_usd_kg(
                crop.crop_name, current_date, price_type="farmgate"
            )

            # Apply food processing policy to determine allocation
            if farm_config and hasattr(farm_config, 'food_policy') and farm_config.food_policy:
                ctx = FoodProcessingContext(
                    harvest_yield_kg=crop.harvest_yield_kg,
                    crop_name=crop.crop_name,
                    fresh_price_per_kg=price_per_kg,
                )
                allocation = farm_config.food_policy.allocate(ctx)
            else:
                allocation = ProcessingAllocation(fresh_fraction=1.0, policy_name="all_fresh")

            # Record allocation on crop state
            crop.processing_allocation = {
                "fresh": allocation.fresh_fraction,
                "packaged": allocation.packaged_fraction,
                "canned": allocation.canned_fraction,
                "dried": allocation.dried_fraction,
            }

            # Calculate revenue and losses by processing pathway
            total_revenue = 0.0
            total_fresh_revenue = 0.0
            total_processed_revenue = 0.0
            total_post_harvest_loss_kg = 0.0
            total_processed_output_kg = 0.0

            for pathway, fraction in [
                ("fresh", allocation.fresh_fraction),
                ("packaged", allocation.packaged_fraction),
                ("canned", allocation.canned_fraction),
                ("dried", allocation.dried_fraction),
            ]:
                if fraction <= 0:
                    continue

                raw_kg = crop.harvest_yield_kg * fraction

                # Weight loss from processing (dehydration, trimming) — from processing_specs CSV
                weight_loss_frac = data_loader.get_weight_loss_fraction(crop.crop_name, pathway)
                output_kg = raw_kg * (1 - weight_loss_frac)

                # Post-harvest loss (spoilage, damage, rejection) — from post_harvest_losses CSV
                loss_frac = data_loader.get_post_harvest_loss_fraction(crop.crop_name, pathway)
                sellable_kg = output_kg * (1.0 - loss_frac)

                # Revenue: sellable weight × (fresh price × value-add multiplier from CSV)
                multiplier = data_loader.get_value_multiplier(crop.crop_name, pathway)
                revenue = sellable_kg * price_per_kg * multiplier

                total_revenue += revenue
                total_post_harvest_loss_kg += raw_kg - sellable_kg

                if pathway == "fresh":
                    total_fresh_revenue += revenue
                else:
                    total_processed_revenue += revenue
                    total_processed_output_kg += output_kg

            # Store results on crop state
            crop.harvest_revenue_usd = total_revenue
            crop.fresh_revenue_usd = total_fresh_revenue
            crop.processed_revenue_usd = total_processed_revenue
            crop.processed_output_kg = total_processed_output_kg
            crop.post_harvest_loss_kg = total_post_harvest_loss_kg

            # Update farm accumulators
            farm_state.cumulative_yield_kg += crop.harvest_yield_kg
            farm_state.cumulative_crop_revenue_usd += crop.harvest_revenue_usd
            farm_state.cumulative_fresh_revenue_usd += total_fresh_revenue
            farm_state.cumulative_processed_revenue_usd += total_processed_revenue
            farm_state.cumulative_processed_output_kg += total_processed_output_kg
            farm_state.cumulative_post_harvest_loss_kg += total_post_harvest_loss_kg
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
    # Calculate crop yields and revenues for the year (harvested crops from this year only)
    crop_yields = {}
    crop_revenues = {}
    for crop in farm_state.crops:
        # Only include crops planted in this year
        if crop.is_harvested and crop.planting_date.year == year:
            # Aggregate by crop name (in case multiple plantings of same crop)
            if crop.crop_name not in crop_yields:
                crop_yields[crop.crop_name] = 0.0
                crop_revenues[crop.crop_name] = 0.0
            crop_yields[crop.crop_name] += crop.harvest_yield_kg
            crop_revenues[crop.crop_name] += crop.harvest_revenue_usd

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
        total_crop_revenue_usd=farm_state.cumulative_crop_revenue_usd,
        crop_water_m3=dict(crop_water_totals),
        crop_yield_kg=crop_yields,
        crop_revenue_usd=crop_revenues,
        fresh_revenue_usd=farm_state.cumulative_fresh_revenue_usd,
        processed_revenue_usd=farm_state.cumulative_processed_revenue_usd,
        processed_output_kg=farm_state.cumulative_processed_output_kg,
        post_harvest_loss_kg=farm_state.cumulative_post_harvest_loss_kg,
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
    farm_state.cumulative_crop_revenue_usd = 0.0
    farm_state.cumulative_fresh_revenue_usd = 0.0
    farm_state.cumulative_processed_revenue_usd = 0.0
    farm_state.cumulative_processed_output_kg = 0.0
    farm_state.cumulative_post_harvest_loss_kg = 0.0


def initialize_energy_state(scenario):
    """Initialize EnergyState from scenario infrastructure configuration.

    Creates an EnergyState with PV/wind/battery/generator capacities from
    the scenario. Battery starts at 50% SOC per architecture spec.

    Args:
        scenario: Loaded Scenario with energy infrastructure config

    Returns:
        EnergyState
    """
    return EnergyState(
        pv_capacity_kw=scenario.infrastructure.pv.sys_capacity_kw,
        wind_capacity_kw=scenario.infrastructure.wind.sys_capacity_kw,
        battery_capacity_kwh=scenario.infrastructure.battery.sys_capacity_kwh,
        battery_soc=0.5,
        battery_soc_min=0.10,
        battery_soc_max=0.90,
        battery_charge_efficiency=0.95,
        battery_discharge_efficiency=0.95,
        generator_capacity_kw=scenario.infrastructure.diesel_backup.capacity_kw,
        generator_min_load_fraction=0.30,
        generator_sfc_a=0.06,
        generator_sfc_b=0.20,
    )


def reset_energy_for_new_year(energy_state):
    """Reset energy state accumulators for new year tracking.

    Preserves daily_energy_records for full simulation history and
    battery SOC (physical state that persists across years).

    Args:
        energy_state: EnergyState to reset
    """
    energy_state.cumulative_pv_kwh = 0.0
    energy_state.cumulative_wind_kwh = 0.0
    energy_state.cumulative_grid_import_kwh = 0.0
    energy_state.cumulative_grid_export_kwh = 0.0
    energy_state.cumulative_generator_kwh = 0.0
    energy_state.cumulative_generator_fuel_L = 0.0
    energy_state.cumulative_battery_charge_kwh = 0.0
    energy_state.cumulative_battery_discharge_kwh = 0.0
    energy_state.cumulative_curtailment_kwh = 0.0


def dispatch_energy(energy_state, total_demand_kwh, current_date, data_loader, scenario):
    """Dispatch energy using merit-order: renewables -> battery -> grid -> generator.

    Implements the energy dispatch algorithm from calculations.md Section 3.

    Merit order (lowest marginal cost first):
      1. PV + wind generation (marginal cost ~ 0)
      2. Battery discharge (degradation cost)
      3. Grid import (grid electricity price)
      4. Backup generator (diesel fuel cost)

    Surplus handling (when generation > demand):
      1. Charge battery (limited by capacity and max SOC)
      2. Export to grid (unlimited for MVP)
      3. Curtail remainder

    Battery SOC update per architecture spec:
      SOC_new = SOC + (charge * eta_charge - discharge / eta_discharge) / capacity_kwh

    Generator uses Willans line fuel model:
      fuel_L = (a * P_rated + b * P_gen) * hours

    Args:
        energy_state: EnergyState with current battery SOC and system parameters
        total_demand_kwh: Total community energy demand for the day (kWh)
        current_date: Current simulation date
        data_loader: SimulationDataLoader for PV/wind capacity factor lookup
        scenario: Loaded Scenario for infrastructure config (density, type, start_date)

    Returns:
        DailyEnergyRecord with dispatch results
    """
    # --- 1. PV generation ---
    pv_kwh = 0.0
    if energy_state.pv_capacity_kw > 0:
        pv_kwh_per_kw = data_loader.get_pv_kwh_per_kw(
            current_date, density_variant=scenario.infrastructure.pv.density
        )
        # Panel degradation: 0.5%/yr for mono-crystalline Si (IEC 61215)
        years_since_start = (current_date - scenario.metadata.start_date).days / 365.25
        degradation_factor = (1 - 0.005) ** years_since_start

        # Shading factor by agri-PV density (annual average, from calculations.md)
        shading_factors = {"low": 0.95, "medium": 0.90, "high": 0.85}
        shading_factor = shading_factors.get(scenario.infrastructure.pv.density, 0.90)

        pv_kwh = (
            energy_state.pv_capacity_kw
            * pv_kwh_per_kw
            * degradation_factor
            * shading_factor
        )

    # --- 2. Wind generation ---
    wind_kwh = 0.0
    if energy_state.wind_capacity_kw > 0:
        wind_kwh_per_kw = data_loader.get_wind_kwh_per_kw(
            current_date, turbine_variant=scenario.infrastructure.wind.type
        )
        wind_kwh = energy_state.wind_capacity_kw * wind_kwh_per_kw

    # --- 3. Calculate surplus or deficit ---
    total_generation = pv_kwh + wind_kwh
    net = total_generation - total_demand_kwh

    battery_charge_kwh = 0.0
    battery_discharge_kwh = 0.0
    grid_import_kwh = 0.0
    grid_export_kwh = 0.0
    generator_kwh = 0.0
    generator_fuel_L = 0.0
    curtailment_kwh = 0.0

    if net >= 0:
        # --- 4. Surplus: charge battery -> export -> curtail ---
        surplus = net

        # Charge battery (limited by room to SOC_max, accounting for charge efficiency)
        if energy_state.battery_capacity_kwh > 0 and surplus > 0:
            available_room_kwh = (
                (energy_state.battery_soc_max - energy_state.battery_soc)
                * energy_state.battery_capacity_kwh
            )
            # Input energy needed to fill available room (losses during charging)
            max_charge_input = available_room_kwh / energy_state.battery_charge_efficiency
            battery_charge_kwh = min(surplus, max(0.0, max_charge_input))
            surplus -= battery_charge_kwh

        # Export to grid (unlimited for MVP — no grid export limit configured)
        grid_export_kwh = surplus
        surplus -= grid_export_kwh

        # Curtail remainder (should be 0 with unlimited export)
        curtailment_kwh = surplus

    else:
        # --- 5. Deficit: discharge battery -> import grid -> generator ---
        deficit = -net

        # Discharge battery (limited by energy above SOC_min, after discharge losses)
        if energy_state.battery_capacity_kwh > 0 and deficit > 0:
            available_stored_kwh = (
                (energy_state.battery_soc - energy_state.battery_soc_min)
                * energy_state.battery_capacity_kwh
            )
            # Useful energy output after discharge efficiency losses
            max_discharge_output = (
                available_stored_kwh * energy_state.battery_discharge_efficiency
            )
            battery_discharge_kwh = min(deficit, max(0.0, max_discharge_output))
            deficit -= battery_discharge_kwh

        # Import from grid (unlimited for MVP — no grid import limit configured)
        grid_import_kwh = deficit
        deficit -= grid_import_kwh

        # --- 6. Run generator (only if deficit remains after grid import) ---
        if deficit > 0 and energy_state.generator_capacity_kw > 0:
            P_rated = energy_state.generator_capacity_kw
            max_gen_kwh = P_rated * 24.0  # Maximum energy in one day at full load
            generator_kwh = min(deficit, max_gen_kwh)

            # Willans line fuel model: run at full rated load for shortest time
            # (most fuel-efficient operating point per calculations.md Section 3)
            # fuel_L = (a * P_rated + b * P_gen) * hours
            # At full load: P_gen = P_rated, hours = gen_kwh / P_rated
            P_gen = P_rated
            hours = generator_kwh / P_gen
            generator_fuel_L = (
                energy_state.generator_sfc_a * P_rated
                + energy_state.generator_sfc_b * P_gen
            ) * hours

    # --- 7. Update battery SOC ---
    if energy_state.battery_capacity_kwh > 0:
        energy_stored = battery_charge_kwh * energy_state.battery_charge_efficiency
        energy_removed = battery_discharge_kwh / energy_state.battery_discharge_efficiency
        soc_delta = (energy_stored - energy_removed) / energy_state.battery_capacity_kwh
        energy_state.battery_soc += soc_delta
        # Clamp to bounds (safety against floating-point drift)
        energy_state.battery_soc = max(
            energy_state.battery_soc_min,
            min(energy_state.battery_soc_max, energy_state.battery_soc),
        )

    # --- 8. Update yearly accumulators ---
    energy_state.cumulative_pv_kwh += pv_kwh
    energy_state.cumulative_wind_kwh += wind_kwh
    energy_state.cumulative_grid_import_kwh += grid_import_kwh
    energy_state.cumulative_grid_export_kwh += grid_export_kwh
    energy_state.cumulative_generator_kwh += generator_kwh
    energy_state.cumulative_generator_fuel_L += generator_fuel_L
    energy_state.cumulative_battery_charge_kwh += battery_charge_kwh
    energy_state.cumulative_battery_discharge_kwh += battery_discharge_kwh
    energy_state.cumulative_curtailment_kwh += curtailment_kwh

    # --- 9. Record daily dispatch ---
    record = DailyEnergyRecord(
        date=current_date,
        pv_generation_kwh=pv_kwh,
        wind_generation_kwh=wind_kwh,
        total_demand_kwh=total_demand_kwh,
        battery_charge_kwh=battery_charge_kwh,
        battery_discharge_kwh=battery_discharge_kwh,
        grid_import_kwh=grid_import_kwh,
        grid_export_kwh=grid_export_kwh,
        generator_kwh=generator_kwh,
        generator_fuel_L=generator_fuel_L,
        curtailment_kwh=curtailment_kwh,
        battery_soc=energy_state.battery_soc,
    )
    energy_state.daily_energy_records.append(record)

    return record


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
        # Initialize data loader (electricity pricing now comes from scenario config, not CSV files)
        data_loader = SimulationDataLoader(electricity_pricing_regime="subsidized")

    # Get treatment energy from scenario water system
    salinity_level = scenario.infrastructure.water_treatment.salinity_level
    treatment_kwh_per_m3 = data_loader.get_treatment_energy_kwh_m3(salinity_level)

    # Calculate system constraints
    constraints = calculate_system_constraints(scenario)

    # Initialize state
    state = initialize_simulation_state(scenario, data_loader)

    # Compute infrastructure financing costs and initialize economic state
    try:
        infra_costs = estimate_infrastructure_costs(scenario)
        initial_cash = sum(f.starting_capital_usd for f in scenario.farms)
        total_annual_infra = sum(c["annual_total_usd"] for c in infra_costs.values())
        total_annual_debt = sum(
            c["monthly_debt_service_usd"] * 12
            for c in infra_costs.values()
            if c.get("monthly_debt_service_usd", 0) > 0
        )
        state.economic = EconomicState(
            cash_reserves_usd=initial_cash,
            annual_infrastructure_costs=infra_costs,
            total_annual_infrastructure_cost_usd=total_annual_infra,
            total_annual_debt_service_usd=total_annual_debt,
        )
        if verbose:
            print(f"Infrastructure costs: ${total_annual_infra:,.0f}/yr "
                  f"(debt service: ${total_annual_debt:,.0f}/yr)")
    except Exception as e:
        if verbose:
            print(f"Warning: Could not compute infrastructure costs: {e}")
        state.economic = EconomicState()

    # Initialize aquifer depletion tracking from scenario groundwater config
    wells_config = scenario.infrastructure.groundwater_wells
    state.aquifer = AquiferState(
        exploitable_volume_m3=wells_config.aquifer_exploitable_volume_m3,
        recharge_rate_m3_yr=wells_config.aquifer_recharge_rate_m3_yr,
        max_drawdown_m=getattr(wells_config, 'max_drawdown_m', 0.0),
    )

    # M1 fix: Initialize community water storage between treatment and irrigation.
    # Storage starts at 50% capacity per architecture spec (calculations.md §2.5).
    storage_capacity = scenario.infrastructure.irrigation_storage.capacity_m3
    state.water_storage = WaterStorageState(
        capacity_m3=storage_capacity,
        current_level_m3=storage_capacity * 0.5,
    )

    # Initialize community energy system state from scenario config
    state.energy = initialize_energy_state(scenario)

    if verbose:
        print(f"Starting simulation: {state.start_date} to {state.end_date}")
        print(f"Farms: {len(state.farms)}, Treatment energy: {treatment_kwh_per_m3:.2f} kWh/m3")
        print(f"Energy system: PV {state.energy.pv_capacity_kw:.0f} kW, "
              f"Wind {state.energy.wind_capacity_kw:.0f} kW, "
              f"Battery {state.energy.battery_capacity_kwh:.0f} kWh, "
              f"Generator {state.energy.generator_capacity_kw:.0f} kW")
        # Note: Household and community building demands vary daily with weather, shown during simulation
        print("System constraints (area-proportional sharing):")
        for farm_id, fc in constraints.items():
            print(f"  {farm_id}: GW max {fc['max_groundwater_m3']:.0f} m3/day, "
                  f"Treatment max {fc['max_treatment_m3']:.0f} m3/day")

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

            # Update economic state with previous year's totals (before reset)
            if state.economic is not None:
                year_revenue = sum(fs.cumulative_crop_revenue_usd for fs in state.farms)
                year_water_cost = sum(fs.cumulative_water_cost_usd for fs in state.farms)
                annual_infra = state.economic.total_annual_infrastructure_cost_usd
                annual_debt = state.economic.total_annual_debt_service_usd
                state.economic.cumulative_revenue_usd += year_revenue
                state.economic.cumulative_operating_cost_usd += year_water_cost + annual_infra
                state.economic.cumulative_infrastructure_cost_usd += annual_infra
                state.economic.cumulative_debt_service_usd += annual_debt
                state.economic.cash_reserves_usd += year_revenue - year_water_cost - annual_infra

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

            # Reset energy accumulators for new year (community-level, once)
            if state.energy is not None:
                reset_energy_for_new_year(state.energy)

        # M1: Track daily groundwater for water storage dynamics
        day_gw_treated_m3 = 0.0
        # Track daily water treatment energy for energy dispatch
        day_total_water_energy_kwh = 0.0

        # Get daily household and community building demands (vary with temperature)
        # These are essential community needs independent of farming decisions
        daily_household_energy_kwh = data_loader.get_household_energy_kwh(current_date)
        daily_household_water_m3 = data_loader.get_household_water_m3(current_date)
        daily_community_building_energy_kwh = data_loader.get_community_building_energy_kwh(current_date)
        daily_community_building_water_m3 = data_loader.get_community_building_water_m3(current_date)

        # Community water (household + buildings) must be treated through desalination system.
        # Calculate treatment/pumping energy for community water demand.
        total_community_water_m3 = daily_household_water_m3 + daily_community_building_water_m3
        community_water_treatment_energy_kwh = total_community_water_m3 * treatment_kwh_per_m3

        # Calculate domestic water cost (community-level operating expense)
        domestic_water_cost_usd = calculate_domestic_water_cost(
            daily_household_water_m3,
            daily_community_building_water_m3,
            current_date,
            scenario
        )

        # Calculate domestic electricity cost (community-level operating expense)
        domestic_electricity_cost_usd = calculate_domestic_electricity_cost(
            daily_household_energy_kwh,
            daily_community_building_energy_kwh,
            scenario
        )

        # Track domestic costs in economic state
        if state.economic is not None:
            state.economic.cumulative_operating_cost_usd += domestic_water_cost_usd
            state.economic.cumulative_operating_cost_usd += domestic_electricity_cost_usd

        # Add community water to storage system and aquifer tracking
        if total_community_water_m3 > 0:
            # Record groundwater extraction for community needs in aquifer depletion tracking
            if state.aquifer is not None:
                state.aquifer.record_extraction(total_community_water_m3)

            # Community water goes through same treatment/storage as irrigation water
            day_gw_treated_m3 += total_community_water_m3
            day_total_water_energy_kwh += community_water_treatment_energy_kwh

            # Add to water storage (treated water enters storage, then distributed)
            if state.water_storage is not None:
                state.water_storage.add_inflow(total_community_water_m3)
                state.water_storage.draw_outflow(total_community_water_m3)

        # Process each farm
        for i, farm_state in enumerate(state.farms):
            farm_config = scenario.farms[i]

            # Calculate irrigation demand
            demand_m3, crop_demands = calculate_farm_demand(
                farm_state, current_date, data_loader
            )

            if demand_m3 > 0:
                # Get cumulative groundwater for quota policies
                cumulative_gw_year = farm_state.cumulative_groundwater_m3
                cumulative_gw_month = farm_state.get_monthly_groundwater_m3(current_date)

                # Get per-farm constraints (area-proportional sharing)
                farm_constraints = constraints[farm_config.id]

                # Build policy context with per-farm constraints
                # Pass aquifer state for dynamic pumping head (drawdown feedback).
                context = build_water_policy_context(
                    demand_m3, current_date, scenario, data_loader, treatment_kwh_per_m3,
                    farm_constraints,
                    cumulative_gw_year_m3=cumulative_gw_year,
                    cumulative_gw_month_m3=cumulative_gw_month,
                    aquifer_state=state.aquifer,
                )

                # Execute water policy
                allocation = execute_water_policy(farm_config, context)

                # Compute energy cost for water treatment (agricultural rate)
                ag_energy = scenario.energy_pricing.agricultural
                if ag_energy.pricing_regime == "subsidized":
                    energy_price = ag_energy.subsidized_price_usd_kwh
                else:
                    energy_price = ag_energy.unsubsidized_price_usd_kwh
                energy_cost_usd = allocation.energy_used_kwh * energy_price

                # Update farm state with energy cost
                update_farm_state(farm_state, allocation, crop_demands, current_date, energy_cost_usd=energy_cost_usd)

                # Record groundwater extraction for aquifer depletion tracking
                if state.aquifer is not None and allocation.groundwater_m3 > 0:
                    state.aquifer.record_extraction(allocation.groundwater_m3)

                # M1: Accumulate daily groundwater for storage tracking
                day_gw_treated_m3 += allocation.groundwater_m3

                # Accumulate water treatment/pumping energy for energy dispatch
                day_total_water_energy_kwh += allocation.energy_used_kwh

                # Track crop water for yearly metrics (scaled by delivery ratio)
                # Recompute delivery_ratio here to keep yearly tracking consistent
                # with per-crop tracking in update_farm_state (C2 fix)
                total_demand = sum(crop_demands.values())
                total_allocated = allocation.groundwater_m3 + allocation.municipal_m3
                delivery_ratio = total_allocated / total_demand if total_demand > 0 else 1.0

                for crop_name, crop_m3 in crop_demands.items():
                    if crop_name not in farm_crop_water[farm_state.farm_id]:
                        farm_crop_water[farm_state.farm_id][crop_name] = 0.0
                    farm_crop_water[farm_state.farm_id][crop_name] += crop_m3 * delivery_ratio

            # Process any harvests (pass farm_config for food processing policy)
            harvested = process_harvests(farm_state, current_date, data_loader, farm_config=farm_config)

        # M1: Update community water storage dynamics.
        # Inflow = groundwater treated today (irrigation + household + building water).
        # Outflow = water delivered today (irrigation + household + building water).
        # In MVP, inflow == outflow (same-day allocation), so net storage change is
        # zero. The tracking records daily throughput for capacity utilization metrics
        # and prepares the infrastructure for future temporal buffering.
        # Note: day_gw_treated_m3 now includes community water added above.
        if state.water_storage is not None:
            state.water_storage.record_daily(
                current_date,
                day_gw_treated_m3,
                day_gw_treated_m3,
                household_m3=daily_household_water_m3,
                community_building_m3=daily_community_building_water_m3
            )

        # Energy dispatch: sum all demand components and run merit-order dispatch.
        # Total demand = irrigation water treatment energy + community water treatment energy +
        # household energy + community building energy.
        # Note: community_water_treatment_energy_kwh already added to day_total_water_energy_kwh above
        # (Food processing energy is skipped for MVP — will be added in Gap 4.)
        if state.energy is not None:
            total_energy_demand_kwh = (day_total_water_energy_kwh +
                                       daily_household_energy_kwh +
                                       daily_community_building_energy_kwh)
            dispatch_energy(
                state.energy, total_energy_demand_kwh, current_date, data_loader, scenario
            )

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

    # Update economic state with final year's totals
    if state.economic is not None:
        year_revenue = sum(fs.cumulative_crop_revenue_usd for fs in state.farms)
        year_water_cost = sum(fs.cumulative_water_cost_usd for fs in state.farms)
        annual_infra = state.economic.total_annual_infrastructure_cost_usd
        annual_debt = state.economic.total_annual_debt_service_usd
        state.economic.cumulative_revenue_usd += year_revenue
        state.economic.cumulative_operating_cost_usd += year_water_cost + annual_infra
        state.economic.cumulative_infrastructure_cost_usd += annual_infra
        state.economic.cumulative_debt_service_usd += annual_debt
        state.economic.cash_reserves_usd += year_revenue - year_water_cost - annual_infra

    if verbose:
        print(f"Simulation complete: {days_simulated} days, {len(state.yearly_metrics)} yearly metrics")
        # Report water storage summary
        if state.water_storage is not None:
            ws = state.water_storage
            total_irrigation = sum(r.get("irrigation_m3", 0) for r in ws.daily_levels)
            total_household = sum(r.get("household_m3", 0) for r in ws.daily_levels)
            total_buildings = sum(r.get("community_building_m3", 0) for r in ws.daily_levels)
            total_water = total_irrigation + total_household + total_buildings
            print(f"Water storage: capacity {ws.capacity_m3:,.0f} m3, "
                  f"final level {ws.current_level_m3:,.0f} m3 "
                  f"({ws.current_level_m3 / ws.capacity_m3 * 100:.1f}% full), "
                  f"{len(ws.daily_levels)} daily records")
            if total_water > 0:
                print(f"  Total water treated: {total_water:,.0f} m3 "
                      f"(irrigation {total_irrigation:,.0f}, "
                      f"household {total_household:,.0f}, "
                      f"buildings {total_buildings:,.0f})")
        # Report energy system summary
        if state.energy is not None and state.energy.daily_energy_records:
            es = state.energy
            records = es.daily_energy_records
            total_pv = sum(r.pv_generation_kwh for r in records)
            total_wind = sum(r.wind_generation_kwh for r in records)
            total_demand = sum(r.total_demand_kwh for r in records)
            total_grid_import = sum(r.grid_import_kwh for r in records)
            total_grid_export = sum(r.grid_export_kwh for r in records)
            total_curtailment = sum(r.curtailment_kwh for r in records)
            print(f"Energy: generation {total_pv + total_wind:,.0f} kWh "
                  f"(PV {total_pv:,.0f}, Wind {total_wind:,.0f}), "
                  f"demand {total_demand:,.0f} kWh")
            print(f"  Grid import: {total_grid_import:,.0f} kWh, "
                  f"export: {total_grid_export:,.0f} kWh, "
                  f"curtailment: {total_curtailment:,.0f} kWh")
            if total_demand > 0:
                renewable_used = total_pv + total_wind - total_grid_export - total_curtailment
                self_suff = max(0.0, renewable_used / total_demand * 100)
                print(f"  Energy self-sufficiency: {self_suff:.1f}%, "
                      f"battery SOC: {es.battery_soc:.1%}")
        # Report aquifer depletion summary
        if state.aquifer is not None:
            years_elapsed = days_simulated / 365.25
            net_depletion = state.aquifer.get_net_depletion_m3(years_elapsed)
            years_remaining = state.aquifer.get_years_remaining(years_elapsed)
            print(f"Aquifer: extracted {state.aquifer.cumulative_extraction_m3:,.0f} m3, "
                  f"net depletion {net_depletion:,.0f} m3, "
                  f"est. years remaining: {years_remaining:,.1f}")

    return state


def main():
    """Run simulation from command line."""
    import sys

    from src.settings.loader import load_scenario

    if len(sys.argv) < 2:
        print("Usage: python src/simulation/simulation.py <scenario_file>")
        print("Example: python src/simulation/simulation.py settings/dev_scenario/dev.yaml")
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
