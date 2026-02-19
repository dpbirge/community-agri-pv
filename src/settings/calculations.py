# Infrastructure calculations for Community Agri-PV simulation
# Layer 2: Design configuration calculations
#
# Calculates derived infrastructure parameters from scenario configuration
# Uses equipment specifications from data files to compute sizing, counts, and costs

import logging
from pathlib import Path
from typing import Dict, Any
import pandas as pd

from src.settings.loader import Scenario


def _get_project_root():
    """Get project root directory."""
    return Path(__file__).parent.parent.parent


def _get_registry():
    """Load data registry. Cache for performance."""
    if not hasattr(_get_registry, "_cache"):
        from src.settings.validation import load_registry
        _get_registry._cache = load_registry()
    return _get_registry._cache


def _get_data_path(category: str, subcategory: str) -> Path:
    """Get data file path from registry.

    Args:
        category: Top-level registry category (e.g., 'equipment', 'community')
        subcategory: Sub-category key (e.g., 'pv_systems', 'housing')

    Returns:
        Full path to the data file

    Raises:
        KeyError: If registry path not found
    """
    registry = _get_registry()
    try:
        path = registry[category][subcategory]
    except KeyError:
        raise KeyError(f"Registry path not found: {category}.{subcategory}")
    return _get_project_root() / path


def _load_csv_with_metadata(file_path: Path) -> pd.DataFrame:
    """Load CSV file, skipping metadata header lines."""
    with open(file_path, "r") as f:
        lines = f.readlines()
    
    header_idx = 0
    for i, line in enumerate(lines):
        if not line.startswith("#"):
            header_idx = i
            break
    
    return pd.read_csv(file_path, skiprows=header_idx)


def _load_pump_system_params():
    """Load pump system parameters from pump_systems CSV.

    Returns dict keyed by parameter name (e.g. 'pump_efficiency') with float values.
    Falls back to locating the file relative to the wells CSV if the registry
    key is not yet configured.
    """
    if hasattr(_load_pump_system_params, "_cache"):
        return _load_pump_system_params._cache

    registry = _get_registry()
    pump_rel = registry.get("equipment", {}).get("pump_systems")
    if pump_rel:
        pump_path = _get_project_root() / pump_rel
    else:
        wells_path = _get_data_path("equipment", "wells")
        pump_path = wells_path.parent / "pump_systems-toy.csv"

    df = _load_csv_with_metadata(pump_path)
    params = {row["parameter"]: float(row["value"]) for _, row in df.iterrows()}

    _load_pump_system_params._cache = params
    return params


def calculate_pv_config(scenario: Scenario) -> Dict[str, Any]:
    """Calculate PV system configuration details.
    
    Returns:
        Dict with panel_count, area_covered_ha, ground_coverage_pct, etc.
    """
    pv_config = scenario.infrastructure.pv
    
    # Load PV system specifications
    pv_specs_path = _get_data_path("equipment", "pv_systems")
    pv_specs = _load_csv_with_metadata(pv_specs_path)
    
    # Find matching density row
    density_row = pv_specs[pv_specs["density_name"] == pv_config.density]
    if density_row.empty:
        raise ValueError(f"Unknown PV density: {pv_config.density}")
    
    density_data = density_row.iloc[0]
    panel_wattage_w = density_data["panel_wattage_w"]
    panel_area_m2 = density_data["panel_area_m2"]
    panels_per_kw = density_data["panels_per_kw"]
    ground_coverage_pct = density_data["ground_coverage_pct"]
    
    # Calculate panel count
    panel_count = int(pv_config.sys_capacity_kw * panels_per_kw)
    
    # Calculate total panel area
    total_panel_area_m2 = panel_count * panel_area_m2
    total_panel_area_ha = total_panel_area_m2 / 10000
    
    # Calculate area covered by panels (percent_over_crops × total farm area)
    total_farm_area_ha = scenario.community.total_area_ha
    area_covered_ha = total_farm_area_ha * pv_config.percent_over_crops
    
    # Calculate ground coverage (density × percent_over_crops)
    actual_ground_coverage_pct = (ground_coverage_pct / 100) * pv_config.percent_over_crops
    
    return {
        "panel_count": panel_count,
        "panel_wattage_w": panel_wattage_w,
        "panel_area_m2": panel_area_m2,
        "total_panel_area_m2": total_panel_area_m2,
        "total_panel_area_ha": total_panel_area_ha,
        "area_covered_ha": area_covered_ha,
        "ground_coverage_pct": ground_coverage_pct,
        "actual_ground_coverage_pct": actual_ground_coverage_pct * 100,
        "panels_per_kw": panels_per_kw,
    }


def calculate_wind_config(scenario: Scenario) -> Dict[str, Any]:
    """Calculate wind turbine configuration details.
    
    Returns:
        Dict with turbine_count, turbine_capacity_kw, etc.
    """
    wind_config = scenario.infrastructure.wind
    
    # Load wind turbine specifications
    wind_specs_path = _get_data_path("equipment", "wind_turbines")
    wind_specs = _load_csv_with_metadata(wind_specs_path)
    
    # Find matching turbine type
    turbine_row = wind_specs[wind_specs["turbine_name"] == wind_config.type]
    if turbine_row.empty:
        raise ValueError(f"Unknown wind turbine type: {wind_config.type}")
    
    turbine_data = turbine_row.iloc[0]
    rated_capacity_kw = turbine_data["rated_capacity_kw"]
    
    # Calculate number of turbines needed
    turbine_count = int(wind_config.sys_capacity_kw / rated_capacity_kw)
    if turbine_count == 0:
        turbine_count = 1  # At least one turbine
    
    # Actual capacity may differ slightly due to rounding
    actual_capacity_kw = turbine_count * rated_capacity_kw
    if actual_capacity_kw < wind_config.sys_capacity_kw:
        turbine_count += 1
        actual_capacity_kw = turbine_count * rated_capacity_kw
    
    return {
        "turbine_count": turbine_count,
        "turbine_capacity_kw": rated_capacity_kw,
        "actual_capacity_kw": actual_capacity_kw,
        "hub_height_m": turbine_data["hub_height_m"],
        "rotor_diameter_m": turbine_data["rotor_diameter_m"],
        "cut_in_speed_ms": turbine_data["cut_in_speed_ms"],
        "rated_speed_ms": turbine_data["rated_speed_ms"],
        "cut_out_speed_ms": turbine_data["cut_out_speed_ms"],
    }


def calculate_battery_config(scenario: Scenario) -> Dict[str, Any]:
    """Calculate battery configuration.

    Each bank = one battery unit. Total capacity = unit_capacity × num_banks.
    Finds closest size match based on capacity per bank.

    Returns:
        Dict with battery configuration including counts, capacities, and costs
    """
    battery_config = scenario.infrastructure.battery

    # Load battery specifications
    battery_specs_path = _get_data_path("equipment", "batteries")
    battery_specs = _load_csv_with_metadata(battery_specs_path)

    # Map common abbreviations to full names
    chemistry_map = {
        "LFP": "lithium_iron_phosphate",
        "VRFB": "vanadium_redox_flow",
    }
    chemistry_search = chemistry_map.get(battery_config.chemistry.upper(), battery_config.chemistry)

    # Find matching chemistry
    chemistry_rows = battery_specs[
        battery_specs["battery_type"].str.contains(chemistry_search, case=False, na=False)
    ]
    if chemistry_rows.empty:
        raise ValueError(f"Battery chemistry '{battery_config.chemistry}' not found")

    # Select size based on per-bank capacity
    capacity_per_bank = battery_config.sys_capacity_kwh / battery_config.units

    # Find closest match
    size_diff = (chemistry_rows["capacity_kwh"] - capacity_per_bank).abs()
    battery_data = chemistry_rows.loc[size_diff.idxmin()]

    return {
        "battery_type": battery_data["battery_type"],
        "num_banks": battery_config.units,
        "capacity_per_bank_kwh": battery_data["capacity_kwh"],
        "total_capacity_kwh": battery_data["capacity_kwh"] * battery_config.units,
        "power_per_bank_kw": battery_data["power_kw"],
        "total_power_kw": battery_data["power_kw"] * battery_config.units,
        "round_trip_efficiency": battery_data["round_trip_efficiency"],
        "cycle_life": battery_data["cycle_life"],
        "depth_of_discharge_pct": battery_data["depth_of_discharge_pct"],
        "capital_cost_per_kwh": battery_data["capital_cost_per_kwh"],
        "total_capital_cost": battery_data["capital_cost_per_kwh"] * battery_data["capacity_kwh"] * battery_config.units,
    }


def calculate_generator_config(scenario: Scenario) -> Dict[str, Any]:
    """Calculate generator configuration details.
    
    Returns:
        Dict with fuel_consumption, efficiency, etc.
    """
    gen_config = scenario.infrastructure.diesel_backup
    
    # Load generator specifications
    gen_specs_path = _get_data_path("equipment", "generators")
    gen_specs = _load_csv_with_metadata(gen_specs_path)
    
    # Find matching capacity (closest match)
    gen_row = gen_specs.iloc[(gen_specs["capacity_kw"] - gen_config.capacity_kw).abs().argsort()[:1]]
    gen_data = gen_row.iloc[0]
    
    return {
        "capacity_kw": gen_config.capacity_kw,
        "fuel_consumption_l_per_kwh": gen_data["fuel_consumption_l_per_kwh"],
        "efficiency": gen_data["efficiency"],
        "min_load_pct": gen_data["min_load_pct"],
        "startup_time_min": gen_data["startup_time_min"],
    }


def calculate_pumping_energy(
    well_depth_m,
    flow_rate_m3_day,
    horizontal_distance_km=None,
    pipe_diameter_m=None,
    pump_efficiency=None,
):
    """Calculate pumping energy using hydraulic engineering principles.

    Energy components:
    1. Lift energy: E_lift = (rho*g*h) / (eta * 3.6e6) kWh/m3
       - rho = water density (~1025 kg/m3 for brackish)
       - g = 9.81 m/s2
       - h = total head (m)
       - eta = pump efficiency

    2. Friction losses: Darcy-Weisbach equation for horizontal pipe flow
       - Head loss = f * (L/D) * (v2/2g)
       - f = friction factor (~0.02 for PVC pipes)

    Args:
        well_depth_m: Well depth in meters (vertical lift)
        flow_rate_m3_day: Flow rate in m3/day
        horizontal_distance_km: Horizontal pipe distance to treatment/storage.
            Defaults to value from pump_systems CSV (0.3 km).
        pipe_diameter_m: Main pipe diameter in meters.
            Defaults to value from pump_systems CSV (0.1 m).
        pump_efficiency: Combined pump and motor efficiency.
            Defaults to value from pump_systems CSV (0.60).

    Returns:
        Dict with lift_energy, friction_energy, total_pumping_energy (all kWh/m3)
    """
    pump_params = _load_pump_system_params()
    if horizontal_distance_km is None:
        horizontal_distance_km = pump_params["default_horizontal_distance_km"]
    if pipe_diameter_m is None:
        pipe_diameter_m = pump_params["default_pipe_diameter_m"]
    if pump_efficiency is None:
        pump_efficiency = pump_params["pump_efficiency"]
    WATER_DENSITY = 1025  # kg/m³ (brackish water)
    GRAVITY = 9.81  # m/s²
    FRICTION_FACTOR = 0.02  # typical for PVC pipes
    PI = 3.14159

    # Vertical lift energy (well to surface)
    lift_head_m = well_depth_m
    lift_energy_kwh_per_m3 = (WATER_DENSITY * GRAVITY * lift_head_m) / (pump_efficiency * 3.6e6)

    # Horizontal friction losses
    pipe_area_m2 = PI * (pipe_diameter_m / 2) ** 2
    flow_rate_m3_s = flow_rate_m3_day / 86400
    velocity_m_s = flow_rate_m3_s / pipe_area_m2

    horizontal_distance_m = horizontal_distance_km * 1000
    friction_head_m = FRICTION_FACTOR * (horizontal_distance_m / pipe_diameter_m) * (velocity_m_s ** 2 / (2 * GRAVITY))
    friction_energy_kwh_per_m3 = (WATER_DENSITY * GRAVITY * friction_head_m) / (pump_efficiency * 3.6e6)

    return {
        "lift_energy_kwh_per_m3": round(lift_energy_kwh_per_m3, 4),
        "friction_energy_kwh_per_m3": round(friction_energy_kwh_per_m3, 4),
        "total_pumping_energy_kwh_per_m3": round(lift_energy_kwh_per_m3 + friction_energy_kwh_per_m3, 4),
        "lift_head_m": lift_head_m,
        "friction_head_m": round(friction_head_m, 2),
    }


def calculate_well_costs(number_of_wells: int, well_depth_m: float, flow_rate_m3_day: float) -> Dict[str, float]:
    """Calculate well capital and O&M costs.
    
    Returns:
        Dict with capital_cost_total, om_cost_per_year
    """
    # Load well specifications
    wells_specs_path = _get_data_path("equipment", "wells")
    wells_specs = _load_csv_with_metadata(wells_specs_path)
    
    # Find matching well configuration
    depth_diff = (wells_specs["well_depth_m"] - well_depth_m).abs()
    flow_diff = (wells_specs["flow_rate_m3_day"] - flow_rate_m3_day).abs()
    combined_diff = depth_diff + flow_diff * 0.01
    
    well_row = wells_specs.iloc[combined_diff.idxmin()]
    
    capital_cost_per_well = well_row["capital_cost_per_well"]
    om_cost_per_well_per_year = well_row["om_cost_per_year"]
    
    return {
        "capital_cost_per_well": capital_cost_per_well,
        "capital_cost_total": capital_cost_per_well * number_of_wells,
        "om_cost_per_well_per_year": om_cost_per_well_per_year,
        "om_cost_total_per_year": om_cost_per_well_per_year * number_of_wells,
    }


def calculate_treatment_unit_sizing(total_capacity_m3_day: float, number_of_units: int) -> Dict[str, float]:
    """Calculate individual treatment unit capacity.
    
    Returns:
        Dict with capacity_per_unit_m3_day
    """
    capacity_per_unit = total_capacity_m3_day / number_of_units
    
    return {
        "capacity_per_unit_m3_day": capacity_per_unit,
        "total_capacity_m3_day": total_capacity_m3_day,
        "number_of_units": number_of_units,
    }


def calculate_distances(wells_config, treatment_config, farms) -> Dict[str, float]:
    """Calculate average distances between infrastructure components.

    Uses simplified geometric estimation assuming uniform distribution of
    infrastructure across the farm area. Formula based on expected distance
    between uniformly distributed points in a square region:

        E[d] = coeff * sqrt(A) / sqrt(n)

    Distance coefficients are loaded from pump_systems CSV. Default values
    (0.3 for well-to-treatment, 0.4 for treatment-to-farm) are adjusted
    for typical rural infrastructure placement patterns.

    Args:
        wells_config: Groundwater wells configuration
        treatment_config: Water treatment configuration
        farms: List of farm objects

    Returns:
        Dict with average_well_to_treatment_km, average_treatment_to_farm_km, etc.
    """
    pump_params = _load_pump_system_params()
    coeff_well_treatment = pump_params["distance_coeff_well_to_treatment"]
    coeff_treatment_farm = pump_params["distance_coeff_treatment_to_farm"]

    number_of_wells = wells_config.number_of_wells
    number_of_farms = len(farms)

    total_area_ha = sum(farm.area_ha for farm in farms)
    total_area_km2 = total_area_ha / 100

    avg_well_to_treatment_km = (total_area_km2 ** 0.5) / (number_of_wells ** 0.5) * coeff_well_treatment
    avg_treatment_to_farm_km = (total_area_km2 ** 0.5) / (number_of_farms ** 0.5) * coeff_treatment_farm

    return {
        "average_well_to_treatment_km": avg_well_to_treatment_km,
        "average_treatment_to_farm_km": avg_treatment_to_farm_km,
        "average_well_to_farm_km": avg_well_to_treatment_km + avg_treatment_to_farm_km,
    }


def calculate_storage_evaporation(capacity_m3: float, storage_type: str) -> Dict[str, float]:
    """Calculate storage evaporation losses.

    Args:
        capacity_m3: Storage capacity
        storage_type: Type of storage (underground_tank, surface_tank, reservoir)

    Returns:
        Dict with evaporation_rate_annual_pct, daily_evaporation_m3, etc.
    """
    # Load storage specifications
    storage_specs_path = _get_data_path("equipment", "storage_systems")
    storage_specs = _load_csv_with_metadata(storage_specs_path)
    
    # Find matching storage type
    storage_row = storage_specs[storage_specs["storage_type"] == storage_type]
    if storage_row.empty:
        raise ValueError(f"Unknown storage type: {storage_type}")
    
    storage_data = storage_row.iloc[0]
    evaporation_rate_annual_pct = storage_data["evaporation_rate_annual_pct"]
    
    # Calculate daily evaporation
    daily_evaporation_m3 = capacity_m3 * (evaporation_rate_annual_pct / 100) / 365
    
    return {
        "evaporation_rate_annual_pct": evaporation_rate_annual_pct,
        "daily_evaporation_m3": daily_evaporation_m3,
        "annual_evaporation_m3": capacity_m3 * (evaporation_rate_annual_pct / 100),
    }


def calculate_storage_costs(capacity_m3: float, storage_type: str) -> Dict[str, float]:
    """Calculate storage capital costs.
    
    Returns:
        Dict with capital_cost_total
    """
    # Load storage specifications
    storage_specs_path = _get_data_path("equipment", "storage_systems")
    storage_specs = _load_csv_with_metadata(storage_specs_path)
    
    # Find matching storage type
    storage_row = storage_specs[storage_specs["storage_type"] == storage_type]
    if storage_row.empty:
        raise ValueError(f"Unknown storage type: {storage_type}")
    
    storage_data = storage_row.iloc[0]
    capital_cost_per_m3 = storage_data["capital_cost_per_m3"]
    om_cost_per_m3_per_year = storage_data["om_cost_per_m3_per_year"]
    
    return {
        "capital_cost_per_m3": capital_cost_per_m3,
        "capital_cost_total": capital_cost_per_m3 * capacity_m3,
        "om_cost_per_m3_per_year": om_cost_per_m3_per_year,
        "om_cost_total_per_year": om_cost_per_m3_per_year * capacity_m3,
    }


def get_irrigation_efficiency(irrigation_type: str) -> float:
    """Get irrigation efficiency for irrigation type.
    
    Returns:
        Efficiency as decimal (0-1)
    """
    # Load irrigation system specifications
    irrigation_specs_path = _get_data_path("equipment", "irrigation_systems")
    irrigation_specs = _load_csv_with_metadata(irrigation_specs_path)
    
    # Find matching irrigation type
    irrigation_row = irrigation_specs[irrigation_specs["irrigation_type"] == irrigation_type]
    if irrigation_row.empty:
        raise ValueError(f"Unknown irrigation type: {irrigation_type}")
    
    return irrigation_row.iloc[0]["efficiency"]


def calculate_irrigation_demand_adjustment(base_demand_m3: float, irrigation_type: str) -> float:
    """Adjust irrigation demand for irrigation system efficiency.
    
    Args:
        base_demand_m3: Base irrigation demand (m³)
        irrigation_type: Type of irrigation system
    
    Returns:
        Adjusted demand accounting for efficiency losses
    """
    efficiency = get_irrigation_efficiency(irrigation_type)
    # Demand increases if efficiency is lower (more water needed to meet crop needs)
    return base_demand_m3 / efficiency


def _load_equipment_specs():
    """Load processing equipment specifications from CSV. Cache for performance."""
    if not hasattr(_load_equipment_specs, "_cache"):
        equipment_file = _get_data_path("equipment", "processing")
        _load_equipment_specs._cache = _load_csv_with_metadata(equipment_file)
    return _load_equipment_specs._cache


def calculate_processing_category_specs(
    category_config, expected_category: str, equipment_availability=0.90
) -> Dict[str, Any]:
    """Calculate processing specs for a category from equipment mix.

    Looks up each equipment type from CSV, validates category matches,
    and calculates weighted averages for mixed equipment.

    Args:
        category_config: ProcessingCategoryConfig with equipment list
        expected_category: Expected category name (drying, canning, etc.)
        equipment_availability: Fraction of time equipment is operational (0-1).
            Accounts for maintenance downtime, cleaning, and unplanned outages.
            Per calculations.md section 6.1. Default 0.90 (90% uptime).
            # TODO: Should eventually come from equipment CSVs per equipment type.

    Returns:
        Dict with total_capacity, weighted_energy_kw, weighted_labor_hours_per_kg, etc.
    """
    equipment_specs = _load_equipment_specs()

    total_capacity = 0.0
    weighted_energy = 0.0
    weighted_labor = 0.0
    equipment_details = []

    for eq in category_config.equipment:
        eq_row = equipment_specs[equipment_specs["equipment_type"] == eq.type]
        if eq_row.empty:
            raise ValueError(
                f"Equipment type '{eq.type}' not found in processing equipment file. "
                f"Available types: {equipment_specs['equipment_type'].tolist()}"
            )

        eq_data = eq_row.iloc[0]
        eq_category = eq_data["category"]

        # Validate category matches
        if eq_category != expected_category:
            raise ValueError(
                f"Equipment '{eq.type}' has category '{eq_category}' but was used in "
                f"'{expected_category}' section. Use equipment from the correct category."
            )

        capacity = eq_data["capacity_kg_per_day"]
        energy_kw = eq_data["energy_kw_continuous"]
        labor_per_kg = eq_data["labor_hours_per_kg"]

        total_capacity += capacity * eq.fraction * equipment_availability
        weighted_energy += energy_kw * eq.fraction
        weighted_labor += labor_per_kg * eq.fraction

        equipment_details.append({
            "type": eq.type,
            "fraction": eq.fraction,
            "capacity_kg_per_day": capacity,
            "energy_kw_continuous": energy_kw,
            "labor_hours_per_kg": labor_per_kg,
        })

    return {
        "total_capacity_kg_per_day": total_capacity,
        "weighted_energy_kw": weighted_energy,
        "weighted_labor_hours_per_kg": weighted_labor,
        "storage_capacity_kg": category_config.storage_capacity_kg_total,
        "shelf_life_days": category_config.shelf_life_days,
        "equipment_details": equipment_details,
    }


def calculate_household_demand(community_config, housing_data_path: str = None) -> Dict[str, float]:
    """Calculate household energy and water demand.
    
    Args:
        community_config: Community configuration
        housing_data_path: Path to housing CSV (uses default if None)
    
    Returns:
        Dict with total_energy_kwh_day, total_water_m3_day, etc.
    """
    population = community_config.population

    # Load housing data
    if housing_data_path is None:
        housing_data_path = _get_data_path("community", "housing")

    housing_data = _load_csv_with_metadata(housing_data_path)

    # Use weighted average from housing data
    total_occupants = housing_data["occupants_per_household"].sum()
    avg_energy = (housing_data["kwh_per_household_per_day"] * housing_data["occupants_per_household"]).sum() / total_occupants
    avg_water = (housing_data["m3_per_household_per_day"] * housing_data["occupants_per_household"]).sum() / total_occupants
    avg_household_size = total_occupants / len(housing_data)

    households = population / avg_household_size

    return {
        "households": households,
        "total_energy_kwh_day": households * avg_energy,
        "total_water_m3_day": households * avg_water,
        "energy_per_household_kwh_day": avg_energy,
        "water_per_household_m3_day": avg_water,
    }


def calculate_community_building_demand(community_config, building_data_path: str = None) -> Dict[str, float]:
    """Calculate community building energy and water demand.

    Community buildings include offices, storage/warehouse, meeting halls, and workshops.

    Args:
        community_config: Community configuration with building square footage
        building_data_path: Path to building specs CSV (uses default if None)

    Returns:
        Dict with total_energy_kwh_day, total_water_m3_day, breakdown by building type
    """
    community_buildings_m2 = community_config.community_buildings_m2

    # If no community buildings specified, return zero demand
    if community_buildings_m2 <= 0:
        return {
            "total_area_m2": 0.0,
            "total_energy_kwh_day": 0.0,
            "total_water_m3_day": 0.0,
        }

    # Load building specifications
    if building_data_path is None:
        building_data_path = _get_data_path("community", "buildings")

    building_data = _load_csv_with_metadata(building_data_path)

    # Calculate weighted average energy and water per m² across all building types
    # Using equal weighting across building types for simplicity
    avg_energy_per_m2 = building_data["kwh_per_m2_per_day"].mean()
    avg_water_per_m2 = building_data["m3_per_m2_per_day"].mean()

    total_energy = community_buildings_m2 * avg_energy_per_m2
    total_water = community_buildings_m2 * avg_water_per_m2

    return {
        "total_area_m2": community_buildings_m2,
        "total_energy_kwh_day": total_energy,
        "total_water_m3_day": total_water,
        "energy_per_m2_kwh_day": avg_energy_per_m2,
        "water_per_m2_m3_day": avg_water_per_m2,
    }


def calculate_infrastructure(scenario: Scenario) -> Dict[str, Any]:
    """Main function to calculate all infrastructure parameters.
    
    Args:
        scenario: Loaded scenario object
    
    Returns:
        Dict with all calculated infrastructure parameters
    """
    results = {
        "energy": {
            "pv": calculate_pv_config(scenario),
            "wind": calculate_wind_config(scenario),
            "battery": calculate_battery_config(scenario),
            "generator": calculate_generator_config(scenario),
        },
        "water": {},
    }

    # Calculate distances first (needed for pumping energy)
    distances = calculate_distances(
        scenario.infrastructure.groundwater_wells,
        scenario.infrastructure.water_treatment,
        scenario.farms,
    )

    results["water"] = {
        "wells": calculate_well_costs(
            scenario.infrastructure.groundwater_wells.number_of_wells,
            scenario.infrastructure.groundwater_wells.well_depth_m,
            scenario.infrastructure.groundwater_wells.well_flow_rate_m3_day,
        ),
        "pumping": calculate_pumping_energy(
            scenario.infrastructure.groundwater_wells.well_depth_m,
            scenario.infrastructure.groundwater_wells.well_flow_rate_m3_day,
            horizontal_distance_km=distances["average_well_to_treatment_km"],
        ),
        "treatment": calculate_treatment_unit_sizing(
            scenario.infrastructure.water_treatment.system_capacity_m3_day,
            scenario.infrastructure.water_treatment.number_of_units,
        ),
        "storage": calculate_storage_costs(
            scenario.infrastructure.irrigation_storage.capacity_m3,
            scenario.infrastructure.irrigation_storage.type,
        ),
        "storage_evaporation": calculate_storage_evaporation(
            scenario.infrastructure.irrigation_storage.capacity_m3,
            scenario.infrastructure.irrigation_storage.type,
        ),
        "irrigation_efficiency": get_irrigation_efficiency(
            scenario.infrastructure.irrigation_system.type,
        ),
        "distances": distances,
    }

    results["processing"] = {
        "fresh_packaging": calculate_processing_category_specs(
            scenario.infrastructure.food_processing.fresh_food_packaging, "fresh_packaging"
        ),
        "drying": calculate_processing_category_specs(
            scenario.infrastructure.food_processing.drying, "drying"
        ),
        "canning": calculate_processing_category_specs(
            scenario.infrastructure.food_processing.canning, "canning"
        ),
        "packaging": calculate_processing_category_specs(
            scenario.infrastructure.food_processing.packaging, "packaging"
        ),
    }

    results["community"] = {
        "household": calculate_household_demand(scenario.community),
        "buildings": calculate_community_building_demand(scenario.community),
    }

    return results


# ---------------------------------------------------------------------------
# Infrastructure Financing Cost Model
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

def _load_financing_profiles():
    """Load financing profiles from CSV registered under economic.financing_profiles.

    Returns dict: {status_name: {capex_mult, has_debt, term_yrs, rate, opex_mult}}.
    """
    if hasattr(_load_financing_profiles, "_cache"):
        return _load_financing_profiles._cache

    path = _get_data_path("economic", "financing_profiles")
    df = _load_csv_with_metadata(path)

    profiles = {}
    for _, row in df.iterrows():
        profiles[row["financing_status"]] = {
            "capex_mult": float(row["capex_cost_multiplier"]),
            "has_debt": str(row["has_debt_service"]).lower() == "true",
            "term_yrs": int(row["loan_term_years"]),
            "rate": float(row["interest_rate"]),
            "opex_mult": float(row["opex_cost_multiplier"]),
        }

    _load_financing_profiles._cache = profiles
    return profiles


# Fallback must stay synchronized with financing_profiles CSV
_FINANCING_PROFILES_FALLBACK = {
    "existing_owned":    {"capex_mult": 0.0, "has_debt": False, "term_yrs": 0,  "rate": 0.000, "opex_mult": 1.0},
    "grant_full":        {"capex_mult": 0.0, "has_debt": False, "term_yrs": 0,  "rate": 0.000, "opex_mult": 0.0},
    "grant_capex":       {"capex_mult": 0.0, "has_debt": False, "term_yrs": 0,  "rate": 0.000, "opex_mult": 1.0},
    "purchased_cash":    {"capex_mult": 1.0, "has_debt": False, "term_yrs": 0,  "rate": 0.000, "opex_mult": 1.0},
    "loan_standard":     {"capex_mult": 0.0, "has_debt": True,  "term_yrs": 10, "rate": 0.060, "opex_mult": 1.0},
    "loan_concessional": {"capex_mult": 0.0, "has_debt": True,  "term_yrs": 15, "rate": 0.035, "opex_mult": 1.0},
}

FINANCING_PROFILES = _load_financing_profiles()

def calculate_financing_costs(
    financing_status, capital_cost_usd, annual_om_cost_usd, depreciation_years=15
):
    """Calculate annual financing costs based on financing profile.

    For debt-financed infrastructure, uses fixed-rate amortization:
        Monthly_payment = P * [r(1+r)^n] / [(1+r)^n - 1]
    For cash-purchased infrastructure, uses straight-line depreciation.

    Args:
        financing_status: One of FINANCING_PROFILES keys
        capital_cost_usd: Total capital cost of the infrastructure
        annual_om_cost_usd: Annual O&M cost
        depreciation_years: Straight-line depreciation period for cash purchases.
            Default 15. For component-specific lifespans, see equipment_lifespans CSV.

    Returns:
        dict with annual_capex_usd, annual_opex_usd, annual_total_usd,
        monthly_debt_service_usd
    """
    profile = FINANCING_PROFILES.get(financing_status)
    if profile is None:
        logger.warning(
            "Unknown financing_status '%s', defaulting to 'existing_owned'",
            financing_status,
        )
        profile = FINANCING_PROFILES["existing_owned"]

    annual_capex = 0.0
    monthly_debt_service = 0.0

    if profile["has_debt"]:
        # Fixed-rate amortization
        P = capital_cost_usd
        annual_rate = profile["rate"]
        r = annual_rate / 12  # monthly rate
        n = profile["term_yrs"] * 12  # number of monthly payments

        if r > 0 and n > 0:
            monthly_debt_service = P * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
        elif n > 0:
            monthly_debt_service = P / n  # zero-interest loan

        annual_capex = monthly_debt_service * 12

    elif profile["capex_mult"] > 0:
        # Cash purchase: straight-line depreciation
        annual_capex = (capital_cost_usd * profile["capex_mult"]) / depreciation_years

    annual_opex = annual_om_cost_usd * profile["opex_mult"]

    return {
        "annual_capex_usd": round(annual_capex, 2),
        "annual_opex_usd": round(annual_opex, 2),
        "annual_total_usd": round(annual_capex + annual_opex, 2),
        "monthly_debt_service_usd": round(monthly_debt_service, 2),
    }


def _load_reference_costs():
    """Load reference cost parameters from reference_costs CSV.

    Reads the reference_costs CSV from the data registry (costs.reference).
    Falls back to locating the file relative to the operating costs CSV
    if the registry key is not yet configured.

    Returns dict: {subsystem: {capital_cost_key: rate, om_key: rate}}.
    """
    if hasattr(_load_reference_costs, "_cache"):
        return _load_reference_costs._cache

    registry = _get_registry()
    ref_rel = registry.get("costs", {}).get("reference")
    if ref_rel:
        ref_path = _get_project_root() / ref_rel
    else:
        # Derive path from operating costs file location
        operating_path = _get_data_path("costs", "operating")
        ref_path = operating_path.parent / "reference_costs-toy.csv"

    df = _load_csv_with_metadata(ref_path)

    costs = {}
    for _, row in df.iterrows():
        subsystem = row["subsystem"]
        entry = {row["capital_cost_key"]: float(row["capital_cost_rate"])}
        entry[row["om_key"]] = float(row["om_rate"])
        costs[subsystem] = entry

    _load_reference_costs._cache = costs
    return costs


# Reference cost estimates for infrastructure subsystems (USD).
# Loaded from reference_costs CSV; see data/parameters/costs/reference_costs-toy.csv.
REFERENCE_COSTS = _load_reference_costs()


def _zero_cost_entry():
    """Return a zero-cost entry for missing or failed cost estimates."""
    return {
        "capital_usd": 0.0,
        "annual_om_usd": 0.0,
        "financing_status": "unknown",
        "annual_capex_usd": 0.0,
        "annual_opex_usd": 0.0,
        "annual_total_usd": 0.0,
        "monthly_debt_service_usd": 0.0,
    }


def _estimate_subsystem(name, capital, annual_om, financing_status):
    """Helper: compute financing costs for one subsystem and merge metadata."""
    result = calculate_financing_costs(financing_status, capital, annual_om)
    result.update({
        "capital_usd": capital,
        "annual_om_usd": annual_om,
        "financing_status": financing_status,
    })
    return result


# ---------------------------------------------------------------------------
# Labor Requirements Model
# ---------------------------------------------------------------------------
# Values loaded from CSV data files (labor_requirements-toy.csv and
# labor_wages-toy.csv) via the data registry. See those files for sources.


def _load_labor_params():
    """Load labor model parameters from CSV data files. Cached on first call.

    Reads labor_requirements and labor_wages CSVs, extracts model-level
    parameters (rows with unit types like multiplier, fraction, per_year, etc.),
    and returns them in a flat dict.
    """
    if hasattr(_load_labor_params, "_cache"):
        return _load_labor_params._cache

    req_path = _get_data_path("labor", "requirements")
    wages_path = _get_data_path("labor", "wages")

    req_df = pd.read_csv(req_path, comment="#")
    wages_df = pd.read_csv(wages_path, comment="#")

    # Helper to look up a single value from the requirements CSV
    def _req(activity_type):
        row = req_df[req_df["activity_type"] == activity_type]
        if row.empty:
            raise KeyError(f"Labor parameter '{activity_type}' not found in {req_path}")
        return row.iloc[0]["hours_per_unit"]

    # Blended agricultural wage rate from wages CSV
    wage_row = wages_df[wages_df["worker_category"] == "blended_agricultural"]
    if wage_row.empty:
        raise KeyError(f"'blended_agricultural' wage category not found in {wages_path}")
    hourly_rate = float(wage_row.iloc[0]["usd_per_hour"])

    working_hours_per_day = float(_req("working_hours"))
    working_days_per_year = float(_req("working_days"))

    # Crop multipliers: rows named crop_multiplier_<crop>
    crop_rows = req_df[req_df["activity_type"].str.startswith("crop_multiplier_")]
    crop_multipliers = {}
    for _, row in crop_rows.iterrows():
        crop_name = row["activity_type"].replace("crop_multiplier_", "")
        crop_multipliers[crop_name] = float(row["hours_per_unit"])

    params = {
        "hourly_rate_usd": hourly_rate,
        "working_hours_per_day": working_hours_per_day,
        "working_days_per_year": working_days_per_year,
        "fte_hours": working_hours_per_day * working_days_per_year,
        "base_field_hrs_ha_yr": float(_req("base_field_labor")),
        "crop_multipliers": crop_multipliers,
        "processing_hrs_per_kg": float(_req("processing_labor")),
        "pv_hrs_per_100kw": float(_req("maint_pv")),
        "wind_hrs_per_100kw": float(_req("maint_wind")),
        "bwro_hrs_per_unit": float(_req("maint_bwro")),
        "well_hrs_per_well": float(_req("maint_well")),
        "battery_hrs_per_unit": float(_req("maint_battery")),
        "generator_hrs": float(_req("maint_generator")),
        "admin_fraction": float(_req("admin_overhead")),
        "harvest_multiplier": float(_req("harvest_multiplier")),
    }

    _load_labor_params._cache = params
    return params


# Module-level constants loaded from CSV data files.
# These preserve the existing public interface so that other modules
# (e.g., metrics.py) can import them by name.
_lp = _load_labor_params()
LABOR_HOURLY_RATE_USD = _lp["hourly_rate_usd"]
LABOR_WORKING_HOURS_PER_DAY = _lp["working_hours_per_day"]
LABOR_WORKING_DAYS_PER_YEAR = _lp["working_days_per_year"]
LABOR_FTE_HOURS = _lp["fte_hours"]
LABOR_BASE_FIELD_HRS_HA_YR = _lp["base_field_hrs_ha_yr"]
LABOR_CROP_MULTIPLIERS = _lp["crop_multipliers"]
LABOR_PROCESSING_HRS_PER_KG = _lp["processing_hrs_per_kg"]
LABOR_PV_HRS_PER_100KW = _lp["pv_hrs_per_100kw"]
LABOR_WIND_HRS_PER_100KW = _lp["wind_hrs_per_100kw"]
LABOR_BWRO_HRS_PER_UNIT = _lp["bwro_hrs_per_unit"]
LABOR_WELL_HRS_PER_WELL = _lp["well_hrs_per_well"]
LABOR_BATTERY_HRS_PER_UNIT = _lp["battery_hrs_per_unit"]
LABOR_GENERATOR_HRS = _lp["generator_hrs"]
LABOR_ADMIN_FRACTION = _lp["admin_fraction"]
del _lp  # Clean up temporary variable


def calculate_labor_requirements(
    scenario: Scenario, processed_output_kg: float = 0.0
) -> Dict[str, float]:
    """Estimate annual labor requirements by activity type.

    Uses simple per-hectare and per-infrastructure-unit estimates based on
    FAO literature for irrigated agriculture in arid climates.

    Args:
        scenario: Loaded Scenario with farms and infrastructure config.
        processed_output_kg: Annual processed output in kg (packaged/canned/dried,
            not fresh). Defaults to 0.0 if not known at calculation time.

    Returns:
        dict with labor breakdown:
            field_labor_hrs: Annual field work hours
            processing_labor_hrs: Annual processing labor hours
            maintenance_labor_hrs: Annual infrastructure maintenance hours
            admin_labor_hrs: Annual administrative hours
            total_labor_hrs: Total annual labor hours
            fte_count: Full-time equivalent positions
            labor_cost_usd: Total annual labor cost
    """
    # --- Field labor: crop-specific hours per hectare ---
    field_labor_hrs = 0.0
    for farm in scenario.farms:
        for crop_config in farm.crops:
            crop_area_ha = farm.area_ha * crop_config.area_fraction
            multiplier = LABOR_CROP_MULTIPLIERS.get(crop_config.name, 1.0)
            field_labor_hrs += LABOR_BASE_FIELD_HRS_HA_YR * multiplier * crop_area_ha

    # --- Processing labor: hours per kg of non-fresh output ---
    processing_labor_hrs = processed_output_kg * LABOR_PROCESSING_HRS_PER_KG

    # --- Infrastructure maintenance ---
    infra = scenario.infrastructure
    pv_hrs = (infra.pv.sys_capacity_kw / 100.0) * LABOR_PV_HRS_PER_100KW
    wind_hrs = (infra.wind.sys_capacity_kw / 100.0) * LABOR_WIND_HRS_PER_100KW
    bwro_hrs = infra.water_treatment.number_of_units * LABOR_BWRO_HRS_PER_UNIT
    well_hrs = infra.groundwater_wells.number_of_wells * LABOR_WELL_HRS_PER_WELL
    battery_hrs = infra.battery.units * LABOR_BATTERY_HRS_PER_UNIT
    generator_hrs = LABOR_GENERATOR_HRS

    maintenance_labor_hrs = (
        pv_hrs + wind_hrs + bwro_hrs + well_hrs + battery_hrs + generator_hrs
    )

    # --- Administration: 5% of all other labor ---
    non_admin_total = field_labor_hrs + processing_labor_hrs + maintenance_labor_hrs
    admin_labor_hrs = non_admin_total * LABOR_ADMIN_FRACTION

    # --- Totals ---
    total_labor_hrs = non_admin_total + admin_labor_hrs
    fte_count = total_labor_hrs / LABOR_FTE_HOURS
    labor_cost_usd = total_labor_hrs * LABOR_HOURLY_RATE_USD

    return {
        "field_labor_hrs": round(field_labor_hrs, 1),
        "processing_labor_hrs": round(processing_labor_hrs, 1),
        "maintenance_labor_hrs": round(maintenance_labor_hrs, 1),
        "admin_labor_hrs": round(admin_labor_hrs, 1),
        "total_labor_hrs": round(total_labor_hrs, 1),
        "fte_count": round(fte_count, 2),
        "labor_cost_usd": round(labor_cost_usd, 2),
    }


def compute_peak_labor_demand(
    scenario: Scenario, all_metrics: dict
) -> Dict[int, float]:
    """Estimate peak monthly labor demand for workforce planning.

    Harvest months have 2-4x the base labor demand.  Uses monthly metrics to
    identify which months have harvests (total_yield_kg > 0) and applies a 3x
    multiplier to field labor for those months.

    Args:
        scenario: Loaded Scenario with farms and infrastructure config.
        all_metrics: Output from compute_all_metrics() containing monthly_metrics.

    Returns:
        dict: {month: labor_hours} for the peak year (month is 1-12).
    """
    HARVEST_MULTIPLIER = _load_labor_params()["harvest_multiplier"]

    # Get base labor breakdown from scenario (no processing output estimate)
    base_labor = calculate_labor_requirements(scenario)
    base_field_monthly = base_labor["field_labor_hrs"] / 12.0
    base_maintenance_monthly = base_labor["maintenance_labor_hrs"] / 12.0
    base_processing_monthly = base_labor["processing_labor_hrs"] / 12.0

    monthly_metrics = all_metrics.get("monthly_metrics", [])
    if not monthly_metrics:
        # No monthly data available; return uniform monthly estimate
        monthly_total = base_labor["total_labor_hrs"] / 12.0
        return {m: round(monthly_total, 1) for m in range(1, 13)}

    # Group by year, track which months have harvests (any farm)
    year_month_harvest = {}  # {year: {month: bool}}
    for mm in monthly_metrics:
        if mm.year not in year_month_harvest:
            year_month_harvest[mm.year] = {}
        if mm.month not in year_month_harvest[mm.year]:
            year_month_harvest[mm.year][mm.month] = False
        if mm.total_yield_kg > 0:
            year_month_harvest[mm.year][mm.month] = True

    # Compute monthly labor for each year; select the peak year
    peak_year = None
    peak_total = 0.0
    peak_monthly = {}

    for year, months_data in year_month_harvest.items():
        monthly = {}
        year_total = 0.0
        for month in range(1, 13):
            has_harvest = months_data.get(month, False)
            field_hrs = base_field_monthly * (
                HARVEST_MULTIPLIER if has_harvest else 1.0
            )
            # Admin scales with the underlying labor for this month
            admin_hrs = (
                (field_hrs + base_maintenance_monthly + base_processing_monthly)
                * LABOR_ADMIN_FRACTION
            )
            total = (
                field_hrs
                + base_maintenance_monthly
                + base_processing_monthly
                + admin_hrs
            )
            monthly[month] = round(total, 1)
            year_total += total

        if year_total > peak_total:
            peak_total = year_total
            peak_year = year
            peak_monthly = monthly

    return peak_monthly if peak_monthly else {m: 0.0 for m in range(1, 13)}


def estimate_infrastructure_costs(scenario: Scenario) -> Dict[str, Dict[str, float]]:
    """Estimate capital and O&M costs for all infrastructure subsystems.

    Uses reference cost estimates scaled by scenario configuration parameters
    and applies the financing profile from each component's financing_status
    to compute annual costs (CAPEX amortization or debt service + O&M).

    If a subsystem's cost cannot be computed (missing data), it defaults to
    zero and logs a warning.

    Args:
        scenario: Loaded Scenario with infrastructure and community config

    Returns:
        Dict of {subsystem_name: {capital_usd, annual_om_usd, financing_status,
                                   annual_capex_usd, annual_opex_usd,
                                   annual_total_usd, monthly_debt_service_usd}}
    """
    infra = scenario.infrastructure
    ref = REFERENCE_COSTS
    costs = {}

    # --- Water subsystems ---

    # Wells
    try:
        wells = infra.groundwater_wells
        capital = wells.number_of_wells * wells.well_depth_m * ref["wells"]["cost_per_m_depth"]
        annual_om = wells.number_of_wells * ref["wells"]["om_per_well_yr"]
        fs = getattr(wells, "financing_status", "existing_owned")
        costs["wells"] = _estimate_subsystem("wells", capital, annual_om, fs)
    except Exception as e:
        logger.warning("Could not estimate well costs: %s", e)
        costs["wells"] = _zero_cost_entry()

    # Water treatment (BWRO)
    try:
        wt = infra.water_treatment
        capital = wt.system_capacity_m3_day * ref["water_treatment"]["cost_per_m3_day"]
        annual_om = capital * ref["water_treatment"]["om_pct"]
        fs = getattr(wt, "financing_status", "existing_owned")
        costs["water_treatment"] = _estimate_subsystem("water_treatment", capital, annual_om, fs)
    except Exception as e:
        logger.warning("Could not estimate water treatment costs: %s", e)
        costs["water_treatment"] = _zero_cost_entry()

    # Irrigation storage
    try:
        storage = infra.irrigation_storage
        capital = storage.capacity_m3 * ref["irrigation_storage"]["cost_per_m3"]
        annual_om = capital * ref["irrigation_storage"]["om_pct"]
        fs = getattr(storage, "financing_status", "existing_owned")
        costs["irrigation_storage"] = _estimate_subsystem("irrigation_storage", capital, annual_om, fs)
    except Exception as e:
        logger.warning("Could not estimate irrigation storage costs: %s", e)
        costs["irrigation_storage"] = _zero_cost_entry()

    # Irrigation system (scaled by total farming area)
    try:
        total_area_ha = scenario.community.total_area_ha
        capital = total_area_ha * ref["irrigation_system"]["cost_per_ha"]
        annual_om = capital * ref["irrigation_system"]["om_pct"]
        fs = getattr(infra.irrigation_system, "financing_status", "existing_owned")
        costs["irrigation_system"] = _estimate_subsystem("irrigation_system", capital, annual_om, fs)
    except Exception as e:
        logger.warning("Could not estimate irrigation system costs: %s", e)
        costs["irrigation_system"] = _zero_cost_entry()

    # --- Energy subsystems ---

    # PV
    try:
        pv = infra.pv
        capital = pv.sys_capacity_kw * ref["pv"]["cost_per_kw"]
        annual_om = pv.sys_capacity_kw * ref["pv"]["om_per_kw_yr"]
        fs = getattr(pv, "financing_status", "existing_owned")
        costs["pv"] = _estimate_subsystem("pv", capital, annual_om, fs)
    except Exception as e:
        logger.warning("Could not estimate PV costs: %s", e)
        costs["pv"] = _zero_cost_entry()

    # Wind
    try:
        wind = infra.wind
        capital = wind.sys_capacity_kw * ref["wind"]["cost_per_kw"]
        annual_om = wind.sys_capacity_kw * ref["wind"]["om_per_kw_yr"]
        fs = getattr(wind, "financing_status", "existing_owned")
        costs["wind"] = _estimate_subsystem("wind", capital, annual_om, fs)
    except Exception as e:
        logger.warning("Could not estimate wind costs: %s", e)
        costs["wind"] = _zero_cost_entry()

    # Battery
    try:
        bat = infra.battery
        capital = bat.sys_capacity_kwh * ref["battery"]["cost_per_kwh"]
        annual_om = capital * ref["battery"]["om_pct"]
        fs = getattr(bat, "financing_status", "existing_owned")
        costs["battery"] = _estimate_subsystem("battery", capital, annual_om, fs)
    except Exception as e:
        logger.warning("Could not estimate battery costs: %s", e)
        costs["battery"] = _zero_cost_entry()

    # Backup generator
    try:
        gen = infra.diesel_backup
        capital = gen.capacity_kw * ref["generator"]["cost_per_kw"]
        annual_om = gen.capacity_kw * ref["generator"]["om_per_kw_yr"]
        fs = getattr(gen, "financing_status", "existing_owned")
        costs["generator"] = _estimate_subsystem("generator", capital, annual_om, fs)
    except Exception as e:
        logger.warning("Could not estimate generator costs: %s", e)
        costs["generator"] = _zero_cost_entry()

    # --- Food processing subsystems ---

    processing = infra.food_processing
    proc_items = [
        ("fresh_packaging", processing.fresh_food_packaging, "fresh_packaging"),
        ("drying", processing.drying, "drying"),
        ("canning", processing.canning, "canning"),
        ("packaging", processing.packaging, "packaging"),
    ]
    for proc_name, proc_config, cost_key in proc_items:
        try:
            ref_entry = ref[cost_key]
            capital = ref_entry.get("cost_per_line", ref_entry.get("cost_per_unit", 0))
            annual_om = capital * ref_entry["om_pct"]
            fs = getattr(proc_config, "financing_status", "existing_owned")
            costs[proc_name] = _estimate_subsystem(proc_name, capital, annual_om, fs)
        except Exception as e:
            logger.warning("Could not estimate %s costs: %s", proc_name, e)
            costs[proc_name] = _zero_cost_entry()

    return costs
