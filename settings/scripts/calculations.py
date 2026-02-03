# Infrastructure calculations for Community Agri-PV simulation
# Layer 2: Design configuration calculations
#
# Calculates derived infrastructure parameters from scenario configuration
# Uses equipment specifications from data files to compute sizing, counts, and costs

from pathlib import Path
from typing import Dict, Any
import pandas as pd

from settings.scripts.loader import Scenario


def _get_project_root():
    """Get project root directory."""
    return Path(__file__).parent.parent.parent


def _get_registry():
    """Load data registry. Cache for performance."""
    if not hasattr(_get_registry, "_cache"):
        from settings.scripts.validation import load_registry
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
        "hub_height_m": wind_config.hub_height_m,
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
    well_depth_m: float,
    flow_rate_m3_day: float,
    horizontal_distance_km: float = 0.3,
    pipe_diameter_m: float = 0.1,
    pump_efficiency: float = 0.60
) -> Dict[str, float]:
    """Calculate pumping energy using hydraulic engineering principles.

    Energy components:
    1. Lift energy: E_lift = (ρgh) / (η × 3.6e6) kWh/m³
       - ρ = water density (~1025 kg/m³ for brackish)
       - g = 9.81 m/s²
       - h = total head (m)
       - η = pump efficiency

    2. Friction losses: Darcy-Weisbach equation for horizontal pipe flow
       - Head loss = f × (L/D) × (v²/2g)
       - f = friction factor (~0.02 for PVC pipes)

    Args:
        well_depth_m: Well depth in meters (vertical lift)
        flow_rate_m3_day: Flow rate in m³/day
        horizontal_distance_km: Horizontal pipe distance to treatment/storage
        pipe_diameter_m: Main pipe diameter in meters
        pump_efficiency: Combined pump and motor efficiency

    Returns:
        Dict with lift_energy, friction_energy, total_pumping_energy (all kWh/m³)
    """
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
    
        E[d] = (0.52 * sqrt(A)) / sqrt(n)
    
    where A = area, n = number of points. Coefficients (0.3, 0.4) are adjusted
    for typical rural infrastructure placement patterns.
    
    Args:
        wells_config: Groundwater wells configuration
        treatment_config: Water treatment configuration  
        farms: List of farm objects
    
    Returns:
        Dict with average_well_to_treatment_km, average_treatment_to_farm_km, etc.
    """
    number_of_wells = wells_config.number_of_wells
    number_of_units = treatment_config.number_of_units
    number_of_farms = len(farms)
    
    # Calculate total area
    total_area_ha = sum(farm.area_ha for farm in farms)
    total_area_km2 = total_area_ha / 100
    
    # Average distance between wells and treatment
    # Uses 0.3 coefficient (wells tend to be distributed near treatment)
    avg_well_to_treatment_km = (total_area_km2 ** 0.5) / (number_of_wells ** 0.5) * 0.3
    
    # Average distance from treatment to farms
    # Uses 0.4 coefficient (farms more spread out from central treatment)
    avg_treatment_to_farm_km = (total_area_km2 ** 0.5) / (number_of_farms ** 0.5) * 0.4
    
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


def calculate_processing_category_specs(category_config, expected_category: str) -> Dict[str, Any]:
    """Calculate processing specs for a category from equipment mix.

    Looks up each equipment type from CSV, validates category matches,
    and calculates weighted averages for mixed equipment.

    Args:
        category_config: ProcessingCategoryConfig with equipment list
        expected_category: Expected category name (drying, canning, etc.)

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

        total_capacity += capacity * eq.fraction
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

    results["community"] = calculate_household_demand(scenario.community)

    return results
