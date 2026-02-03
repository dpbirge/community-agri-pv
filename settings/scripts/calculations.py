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
    pv_specs_path = _get_project_root() / "data/parameters/equipment/pv_systems-toy.csv"
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
    wind_specs_path = _get_project_root() / "data/parameters/equipment/wind_turbines-toy.csv"
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
    """Calculate battery configuration details.
    
    Returns:
        Dict with battery_count, battery_capacity_kwh, etc.
    """
    battery_config = scenario.infrastructure.battery
    
    # Load battery specifications
    battery_specs_path = _get_project_root() / "data/parameters/equipment/batteries-toy.csv"
    battery_specs = _load_csv_with_metadata(battery_specs_path)
    
    # Find matching chemistry (LFP)
    battery_row = battery_specs[battery_specs["battery_type"].str.contains("lithium_iron_phosphate", case=False, na=False)]
    if battery_row.empty:
        raise ValueError(f"Battery chemistry {battery_config.chemistry} not found")
    
    # Select appropriate size based on capacity
    # Use medium if capacity > 200 kWh, large if > 500 kWh, else small
    if battery_config.sys_capacity_kwh > 500:
        size_filter = battery_row["battery_type"].str.contains("large", case=False, na=False)
    elif battery_config.sys_capacity_kwh > 200:
        size_filter = battery_row["battery_type"].str.contains("medium", case=False, na=False)
    else:
        size_filter = battery_row["battery_type"].str.contains("small", case=False, na=False)
    
    battery_data = battery_row[size_filter].iloc[0]
    unit_capacity_kwh = battery_data["capacity_kwh"]
    unit_power_kw = battery_data["power_kw"]
    
    # Calculate number of battery units per bank
    units_per_bank = int(battery_config.sys_capacity_kwh / battery_config.units / unit_capacity_kwh)
    if units_per_bank == 0:
        units_per_bank = 1
    
    total_battery_units = units_per_bank * battery_config.units
    
    return {
        "battery_count": total_battery_units,
        "units_per_bank": units_per_bank,
        "battery_banks": battery_config.units,
        "unit_capacity_kwh": unit_capacity_kwh,
        "unit_power_kw": unit_power_kw,
        "total_capacity_kwh": total_battery_units * unit_capacity_kwh,
        "total_power_kw": total_battery_units * unit_power_kw,
        "round_trip_efficiency": battery_data["round_trip_efficiency"],
        "cycle_life": battery_data["cycle_life"],
        "depth_of_discharge_pct": battery_data["depth_of_discharge_pct"],
    }


def calculate_generator_config(scenario: Scenario) -> Dict[str, Any]:
    """Calculate generator configuration details.
    
    Returns:
        Dict with fuel_consumption, efficiency, etc.
    """
    gen_config = scenario.infrastructure.diesel_backup
    
    # Load generator specifications
    gen_specs_path = _get_project_root() / "data/parameters/equipment/generators-toy.csv"
    gen_specs = _load_csv_with_metadata(gen_specs_path)
    
    # Find matching capacity (closest match)
    gen_row = gen_specs.iloc[(gen_specs["capacity_kw"] - gen_config.capacity_kw).abs().argsort()[:1]]
    if gen_row.empty:
        raise ValueError(f"Generator capacity {gen_config.capacity_kw} kW not found")
    
    gen_data = gen_row.iloc[0]
    
    return {
        "capacity_kw": gen_config.capacity_kw,
        "fuel_consumption_l_per_kwh": gen_data["fuel_consumption_l_per_kwh"],
        "efficiency": gen_data["efficiency"],
        "min_load_pct": gen_data["min_load_pct"],
        "startup_time_min": gen_data["startup_time_min"],
    }


def calculate_well_pumping_energy(well_depth_m: float, flow_rate_m3_day: float) -> float:
    """Calculate well pumping energy requirement (kWh/m³).
    
    Args:
        well_depth_m: Well depth in meters
        flow_rate_m3_day: Flow rate in m³/day
    
    Returns:
        Energy requirement in kWh/m³
    """
    # Load well specifications
    wells_specs_path = _get_project_root() / "data/parameters/equipment/wells-toy.csv"
    wells_specs = _load_csv_with_metadata(wells_specs_path)
    
    # Find matching well configuration (closest match)
    depth_diff = (wells_specs["well_depth_m"] - well_depth_m).abs()
    flow_diff = (wells_specs["flow_rate_m3_day"] - flow_rate_m3_day).abs()
    combined_diff = depth_diff + flow_diff * 0.01  # Weight depth more heavily
    
    well_row = wells_specs.iloc[combined_diff.idxmin()]
    
    return well_row["pumping_energy_kwh_per_m3"]


def calculate_well_costs(number_of_wells: int, well_depth_m: float, flow_rate_m3_day: float) -> Dict[str, float]:
    """Calculate well capital and O&M costs.
    
    Returns:
        Dict with capital_cost_total, om_cost_per_year
    """
    # Load well specifications
    wells_specs_path = _get_project_root() / "data/parameters/equipment/wells-toy.csv"
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
    
    Returns:
        Dict with average_well_to_treatment_km, average_treatment_to_farm_km, etc.
    """
    # Simplified distance calculation - assumes uniform distribution
    # In a real implementation, this would use actual farm locations
    
    number_of_wells = wells_config.number_of_wells
    number_of_units = treatment_config.number_of_units
    number_of_farms = len(farms)
    
    # Estimate average distances (simplified)
    # Assume wells are distributed, treatment units are centralized
    # Rough estimate: sqrt(area) / sqrt(number_of_points) * 0.5
    total_area_ha = sum(farm.area_ha for farm in farms)
    total_area_km2 = total_area_ha / 100
    
    # Average distance between wells and treatment (simplified)
    avg_well_to_treatment_km = (total_area_km2 ** 0.5) / (number_of_wells ** 0.5) * 0.3
    
    # Average distance from treatment to farms
    avg_treatment_to_farm_km = (total_area_km2 ** 0.5) / (number_of_farms ** 0.5) * 0.4
    
    return {
        "average_well_to_treatment_km": avg_well_to_treatment_km,
        "average_treatment_to_farm_km": avg_treatment_to_farm_km,
        "average_well_to_farm_km": avg_well_to_treatment_km + avg_treatment_to_farm_km,
    }


def calculate_storage_evaporation(capacity_m3: float, storage_type: str, weather_data: pd.DataFrame = None) -> Dict[str, float]:
    """Calculate storage evaporation losses.
    
    Args:
        capacity_m3: Storage capacity
        storage_type: Type of storage (underground_tank, surface_tank, reservoir)
        weather_data: Optional weather data for detailed calculation
    
    Returns:
        Dict with evaporation_rate_annual_pct, daily_evaporation_m3, etc.
    """
    # Load storage specifications
    storage_specs_path = _get_project_root() / "data/parameters/equipment/storage_systems-toy.csv"
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
    storage_specs_path = _get_project_root() / "data/parameters/equipment/storage_systems-toy.csv"
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
    irrigation_specs_path = _get_project_root() / "data/parameters/equipment/irrigation_systems-toy.csv"
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


def validate_processing_capacity(processing_config, equipment_specs: pd.DataFrame) -> Dict[str, Any]:
    """Validate processing capacity against equipment capabilities.
    
    Returns:
        Dict with validation results
    """
    # This would compare processing_config.processing_capacity_kg_day
    # against equipment_specs capacity_kg_per_day
    # For now, return basic validation
    return {
        "valid": True,
        "message": "Processing capacity validation not fully implemented",
    }


def calculate_processing_energy_demand(processing_config, daily_throughput_kg: float) -> float:
    """Calculate total energy demand for processing.
    
    Args:
        processing_config: Processing configuration (FreshFoodPackagingConfig, etc.)
        daily_throughput_kg: Daily throughput in kg
    
    Returns:
        Total energy demand in kWh/day
    """
    # Energy per kg × daily throughput
    return processing_config.energy_kwh_per_kg * daily_throughput_kg


def calculate_processing_labor_demand(processing_config, daily_throughput_kg: float) -> float:
    """Calculate total labor demand for processing.
    
    Args:
        processing_config: Processing configuration
        daily_throughput_kg: Daily throughput in kg
    
    Returns:
        Total labor demand in hours/day
    """
    # Labor hours per kg × daily throughput
    return processing_config.labor_hours_per_kg * daily_throughput_kg


def calculate_household_demand(community_config, housing_data: pd.DataFrame = None) -> Dict[str, float]:
    """Calculate household energy and water demand.
    
    Args:
        community_config: Community configuration
        housing_data: Optional housing data for detailed calculation
    
    Returns:
        Dict with total_energy_kwh_day, total_water_m3_day, etc.
    """
    # Simplified calculation - would use housing_data if available
    population = community_config.population
    households = population / 5  # Assume 5 people per household
    
    # Rough estimates for Egyptian community
    energy_per_household_kwh_day = 8.0  # kWh/day per household
    water_per_person_m3_day = 0.15  # m³/day per person
    
    return {
        "households": households,
        "total_energy_kwh_day": households * energy_per_household_kwh_day,
        "total_water_m3_day": population * water_per_person_m3_day,
        "energy_per_household_kwh_day": energy_per_household_kwh_day,
        "water_per_person_m3_day": water_per_person_m3_day,
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
        "water": {
            "wells": calculate_well_costs(
                scenario.infrastructure.groundwater_wells.number_of_wells,
                scenario.infrastructure.groundwater_wells.well_depth_m,
                scenario.infrastructure.groundwater_wells.well_flow_rate_m3_day,
            ),
            "well_pumping_energy": calculate_well_pumping_energy(
                scenario.infrastructure.groundwater_wells.well_depth_m,
                scenario.infrastructure.groundwater_wells.well_flow_rate_m3_day,
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
            "distances": calculate_distances(
                scenario.infrastructure.groundwater_wells,
                scenario.infrastructure.water_treatment,
                scenario.farms,
            ),
        },
        "processing": {
            "fresh_packaging": {
                "energy_kwh_per_day": calculate_processing_energy_demand(
                    scenario.infrastructure.food_processing.fresh_food_packaging,
                    scenario.infrastructure.food_processing.fresh_food_packaging.processing_capacity_kg_day,
                ),
                "labor_hours_per_day": calculate_processing_labor_demand(
                    scenario.infrastructure.food_processing.fresh_food_packaging,
                    scenario.infrastructure.food_processing.fresh_food_packaging.processing_capacity_kg_day,
                ),
            },
            "drying": {
                "energy_kwh_per_day": calculate_processing_energy_demand(
                    scenario.infrastructure.food_processing.drying,
                    scenario.infrastructure.food_processing.drying.processing_capacity_kg_day,
                ),
                "labor_hours_per_day": calculate_processing_labor_demand(
                    scenario.infrastructure.food_processing.drying,
                    scenario.infrastructure.food_processing.drying.processing_capacity_kg_day,
                ),
            },
            "canning": {
                "energy_kwh_per_day": calculate_processing_energy_demand(
                    scenario.infrastructure.food_processing.canning,
                    scenario.infrastructure.food_processing.canning.processing_capacity_kg_day,
                ),
                "labor_hours_per_day": calculate_processing_labor_demand(
                    scenario.infrastructure.food_processing.canning,
                    scenario.infrastructure.food_processing.canning.processing_capacity_kg_day,
                ),
            },
            "packaging": {
                "energy_kwh_per_day": calculate_processing_energy_demand(
                    scenario.infrastructure.food_processing.packaging,
                    scenario.infrastructure.food_processing.packaging.processing_capacity_kg_day,
                ),
                "labor_hours_per_day": calculate_processing_labor_demand(
                    scenario.infrastructure.food_processing.packaging,
                    scenario.infrastructure.food_processing.packaging.processing_capacity_kg_day,
                ),
            },
        },
        "community": calculate_household_demand(scenario.community),
    }
    
    return results
