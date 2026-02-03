# Scenario loader for Community Agri-PV simulation
# Layer 2: Bridges YAML configuration to simulation runtime
#
# Loads scenario files, instantiates policies, returns structured dataclasses.
# Energy and economic policies remain as string names until those modules are implemented.

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

from settings.policies import get_water_policy, BaseWaterPolicy


@dataclass
class ScenarioMetadata:
    """Scenario identification and timing."""
    name: str
    description: str
    version: str
    start_date: date
    end_date: date
    time_step: str
    weather_scenario: str


@dataclass
class PVConfig:
    """Photovoltaic system configuration."""
    sys_capacity_kw: float
    type: str
    tilt_angle: float
    percent_over_crops: float
    density: str
    height_m: float


@dataclass
class WindConfig:
    """Wind turbine configuration."""
    sys_capacity_kw: float
    type: str
    hub_height_m: float


@dataclass
class BatteryConfig:
    """Battery storage configuration."""
    sys_capacity_kwh: float
    units: int
    chemistry: str


@dataclass
class DieselBackupConfig:
    """Diesel backup generator configuration."""
    capacity_kw: float
    type: str


@dataclass
class GroundwaterWellsConfig:
    """Groundwater wells configuration."""
    well_depth_m: float
    well_flow_rate_m3_day: float
    number_of_wells: int


@dataclass
class WaterTreatmentConfig:
    """Water treatment system configuration."""
    system_capacity_m3_day: float
    number_of_units: int
    salinity_level: str
    tds_ppm: float


@dataclass
class IrrigationStorageConfig:
    """Irrigation water storage configuration."""
    capacity_m3: float
    type: str


@dataclass
class IrrigationSystemConfig:
    """Irrigation system configuration."""
    type: str


@dataclass
class FreshFoodPackagingConfig:
    """Fresh food packaging configuration."""
    processing_capacity_kg_day: float
    shelf_life_days: int
    energy_kwh_per_kg: float
    labor_hours_per_kg: float
    additional_cost_per_kg: float
    storage_capacity_kg_total: float


@dataclass
class DryingConfig:
    """Food drying configuration."""
    processing_capacity_kg_day: float
    shelf_life_days: int
    energy_kwh_per_kg: float
    labor_hours_per_kg: float
    additional_cost_per_kg: float
    storage_capacity_kg_total: float


@dataclass
class CanningConfig:
    """Food canning configuration."""
    processing_capacity_kg_day: float
    shelf_life_days: int
    energy_kwh_per_kg: float
    labor_hours_per_kg: float
    additional_cost_per_kg: float
    storage_capacity_kg_total: float


@dataclass
class ProcessedPackagingConfig:
    """Processed food packaging configuration."""
    processing_capacity_kg_day: float
    shelf_life_days: int
    energy_kwh_per_kg: float
    labor_hours_per_kg: float
    additional_cost_per_kg: float
    storage_capacity_kg_total: float


@dataclass
class FoodProcessingConfig:
    """Food processing infrastructure configuration."""
    fresh_food_packaging: FreshFoodPackagingConfig
    drying: DryingConfig
    canning: CanningConfig
    packaging: ProcessedPackagingConfig


@dataclass
class InfrastructureConfig:
    """Complete infrastructure configuration."""
    pv: PVConfig
    wind: WindConfig
    battery: BatteryConfig
    diesel_backup: DieselBackupConfig
    groundwater_wells: GroundwaterWellsConfig
    water_treatment: WaterTreatmentConfig
    irrigation_storage: IrrigationStorageConfig
    irrigation_system: IrrigationSystemConfig
    food_processing: FoodProcessingConfig


@dataclass
class CropAllocation:
    """Crop area allocation."""
    name: str
    area_fraction: float


@dataclass
class Farm:
    """Farm configuration with instantiated policies."""
    id: str
    name: str
    area_ha: float
    yield_factor: float
    starting_capital_usd: float
    water_policy: BaseWaterPolicy
    energy_policy: str
    economic_policy: str


@dataclass
class CommunityConfig:
    """Community structure configuration."""
    total_farms: int
    total_area_ha: float
    population: int
    crops: list


@dataclass
class DebtConfig:
    """Debt configuration."""
    principal_usd: float
    term_years: int
    interest_rate: float


@dataclass
class EconomicsConfig:
    """Economic parameters."""
    currency: str
    discount_rate: float
    debt: DebtConfig


@dataclass
class Scenario:
    """Complete loaded scenario."""
    metadata: ScenarioMetadata
    infrastructure: InfrastructureConfig
    farms: list
    community: CommunityConfig
    economics: EconomicsConfig


def _parse_date(date_str):
    """Parse date string in YYYY-MM-DD format."""
    parts = date_str.split("-")
    if len(parts) != 3:
        raise ValueError(f"Invalid date format: {date_str}. Expected YYYY-MM-DD")
    return date(int(parts[0]), int(parts[1]), int(parts[2]))


def _require(data, key, context=""):
    """Get required key from dict, raise if missing."""
    if key not in data:
        ctx = f" in {context}" if context else ""
        raise KeyError(f"Missing required key '{key}'{ctx}")
    return data[key]


def _load_infrastructure(data):
    """Parse infrastructure sections into config objects."""
    # Energy infrastructure
    energy_infra = _require(data, "energy_infrastructure", "root")
    pv = _require(energy_infra, "pv", "energy_infrastructure")
    wind = _require(energy_infra, "wind", "energy_infrastructure")
    battery = _require(energy_infra, "battery", "energy_infrastructure")
    diesel = _require(energy_infra, "backup_generator", "energy_infrastructure")

    # Validate PV configuration
    percent_over_crops = _require(pv, "percent_over_crops", "energy_infrastructure.pv")
    if not (0 <= percent_over_crops <= 1):
        raise ValueError(f"percent_over_crops must be between 0 and 1, got {percent_over_crops}")
    
    density = _require(pv, "density", "energy_infrastructure.pv")
    density_coverage = {"low": 0.30, "medium": 0.50, "high": 0.80}.get(density, 0.50)
    if density_coverage * percent_over_crops > 1.0:
        raise ValueError(f"density × percent_over_crops ({density_coverage} × {percent_over_crops} = {density_coverage * percent_over_crops}) must be ≤ 1.0")

    # Water infrastructure
    water_infra = _require(data, "water_infrastructure", "root")
    wells = _require(water_infra, "groundwater_wells", "water_infrastructure")
    water_treatment = _require(water_infra, "water_treatment", "water_infrastructure")
    irrigation_storage = _require(water_infra, "irrigation_water_storage", "water_infrastructure")
    irrigation_system = _require(water_infra, "irrigation_system", "water_infrastructure")

    # Food processing infrastructure
    food_processing_infra = _require(data, "food_processing_infrastructure", "root")
    fresh_packaging = _require(food_processing_infra, "fresh_food_packaging", "food_processing_infrastructure")
    drying = _require(food_processing_infra, "drying", "food_processing_infrastructure")
    canning = _require(food_processing_infra, "canning", "food_processing_infrastructure")
    packaging = _require(food_processing_infra, "packaging", "food_processing_infrastructure")

    # Validate values before creating configs
    number_of_wells = _require(wells, "number_of_wells", "water_infrastructure.groundwater_wells")
    if number_of_wells <= 0:
        raise ValueError(f"number_of_wells must be > 0, got {number_of_wells}")
    
    number_of_units = _require(water_treatment, "number_of_units", "water_infrastructure.water_treatment")
    if number_of_units <= 0:
        raise ValueError(f"number_of_units must be > 0, got {number_of_units}")
    
    fresh_capacity = _require(fresh_packaging, "processing_capacity_kg_day", "food_processing_infrastructure.fresh_food_packaging")
    if fresh_capacity <= 0:
        raise ValueError(f"fresh_food_packaging.processing_capacity_kg_day must be > 0, got {fresh_capacity}")
    
    drying_capacity = _require(drying, "processing_capacity_kg_day", "food_processing_infrastructure.drying")
    if drying_capacity <= 0:
        raise ValueError(f"drying.processing_capacity_kg_day must be > 0, got {drying_capacity}")
    
    canning_capacity = _require(canning, "processing_capacity_kg_day", "food_processing_infrastructure.canning")
    if canning_capacity <= 0:
        raise ValueError(f"canning.processing_capacity_kg_day must be > 0, got {canning_capacity}")
    
    packaging_capacity = _require(packaging, "processing_capacity_kg_day", "food_processing_infrastructure.packaging")
    if packaging_capacity <= 0:
        raise ValueError(f"packaging.processing_capacity_kg_day must be > 0, got {packaging_capacity}")

    return InfrastructureConfig(
        pv=PVConfig(
            sys_capacity_kw=_require(pv, "sys_capacity_kw", "energy_infrastructure.pv"),
            type=_require(pv, "type", "energy_infrastructure.pv"),
            tilt_angle=_require(pv, "tilt_angle", "energy_infrastructure.pv"),
            percent_over_crops=_require(pv, "percent_over_crops", "energy_infrastructure.pv"),
            density=_require(pv, "density", "energy_infrastructure.pv"),
            height_m=_require(pv, "height_m", "energy_infrastructure.pv"),
        ),
        wind=WindConfig(
            sys_capacity_kw=_require(wind, "sys_capacity_kw", "energy_infrastructure.wind"),
            type=_require(wind, "type", "energy_infrastructure.wind"),
            hub_height_m=_require(wind, "hub_height_m", "energy_infrastructure.wind"),
        ),
        battery=BatteryConfig(
            sys_capacity_kwh=_require(battery, "sys_capacity_kwh", "energy_infrastructure.battery"),
            units=_require(battery, "units", "energy_infrastructure.battery"),
            chemistry=_require(battery, "chemistry", "energy_infrastructure.battery"),
        ),
        diesel_backup=DieselBackupConfig(
            capacity_kw=_require(diesel, "capacity_kw", "energy_infrastructure.backup_generator"),
            type=_require(diesel, "type", "energy_infrastructure.backup_generator"),
        ),
        groundwater_wells=GroundwaterWellsConfig(
            well_depth_m=_require(wells, "well_depth_m", "water_infrastructure.groundwater_wells"),
            well_flow_rate_m3_day=_require(wells, "well_flow_rate_m3_day", "water_infrastructure.groundwater_wells"),
            number_of_wells=number_of_wells,
        ),
        water_treatment=WaterTreatmentConfig(
            system_capacity_m3_day=_require(water_treatment, "system_capacity_m3_day", "water_infrastructure.water_treatment"),
            number_of_units=number_of_units,
            salinity_level=_require(water_treatment, "salinity_level", "water_infrastructure.water_treatment"),
            tds_ppm=_require(water_treatment, "tds_ppm", "water_infrastructure.water_treatment"),
        ),
        irrigation_storage=IrrigationStorageConfig(
            capacity_m3=_require(irrigation_storage, "capacity_m3", "water_infrastructure.irrigation_water_storage"),
            type=_require(irrigation_storage, "type", "water_infrastructure.irrigation_water_storage"),
        ),
        irrigation_system=IrrigationSystemConfig(
            type=_require(irrigation_system, "type", "water_infrastructure.irrigation_system"),
        ),
        food_processing=FoodProcessingConfig(
            fresh_food_packaging=FreshFoodPackagingConfig(
                processing_capacity_kg_day=fresh_capacity,
                shelf_life_days=_require(fresh_packaging, "shelf_life_days", "food_processing_infrastructure.fresh_food_packaging"),
                energy_kwh_per_kg=_require(fresh_packaging, "energy_kwh_per_kg", "food_processing_infrastructure.fresh_food_packaging"),
                labor_hours_per_kg=_require(fresh_packaging, "labor_hours_per_kg", "food_processing_infrastructure.fresh_food_packaging"),
                additional_cost_per_kg=_require(fresh_packaging, "additional_cost_per_kg", "food_processing_infrastructure.fresh_food_packaging"),
                storage_capacity_kg_total=_require(fresh_packaging, "storage_capacity_kg_total", "food_processing_infrastructure.fresh_food_packaging"),
            ),
            drying=DryingConfig(
                processing_capacity_kg_day=drying_capacity,
                shelf_life_days=_require(drying, "shelf_life_days", "food_processing_infrastructure.drying"),
                energy_kwh_per_kg=_require(drying, "energy_kwh_per_kg", "food_processing_infrastructure.drying"),
                labor_hours_per_kg=_require(drying, "labor_hours_per_kg", "food_processing_infrastructure.drying"),
                additional_cost_per_kg=_require(drying, "additional_cost_per_kg", "food_processing_infrastructure.drying"),
                storage_capacity_kg_total=_require(drying, "storage_capacity_kg_total", "food_processing_infrastructure.drying"),
            ),
            canning=CanningConfig(
                processing_capacity_kg_day=canning_capacity,
                shelf_life_days=_require(canning, "shelf_life_days", "food_processing_infrastructure.canning"),
                energy_kwh_per_kg=_require(canning, "energy_kwh_per_kg", "food_processing_infrastructure.canning"),
                labor_hours_per_kg=_require(canning, "labor_hours_per_kg", "food_processing_infrastructure.canning"),
                additional_cost_per_kg=_require(canning, "additional_cost_per_kg", "food_processing_infrastructure.canning"),
                storage_capacity_kg_total=_require(canning, "storage_capacity_kg_total", "food_processing_infrastructure.canning"),
            ),
            packaging=ProcessedPackagingConfig(
                processing_capacity_kg_day=packaging_capacity,
                shelf_life_days=_require(packaging, "shelf_life_days", "food_processing_infrastructure.packaging"),
                energy_kwh_per_kg=_require(packaging, "energy_kwh_per_kg", "food_processing_infrastructure.packaging"),
                labor_hours_per_kg=_require(packaging, "labor_hours_per_kg", "food_processing_infrastructure.packaging"),
                additional_cost_per_kg=_require(packaging, "additional_cost_per_kg", "food_processing_infrastructure.packaging"),
                storage_capacity_kg_total=_require(packaging, "storage_capacity_kg_total", "food_processing_infrastructure.packaging"),
            ),
        ),
    )


def _load_farm(farm_data, policy_parameters):
    """Parse farm data and instantiate water policy."""
    farm_id = _require(farm_data, "id", "farm")
    policies = _require(farm_data, "policies", f"farm {farm_id}")

    water_policy_name = _require(policies, "water", f"farm {farm_id} policies")
    energy_policy_name = _require(policies, "energy", f"farm {farm_id} policies")
    economic_policy_name = _require(policies, "economic", f"farm {farm_id} policies")

    # Get policy parameters if defined in scenario
    water_params = policy_parameters.get(water_policy_name, {})

    # Instantiate water policy
    water_policy = get_water_policy(water_policy_name, **water_params)

    return Farm(
        id=farm_id,
        name=_require(farm_data, "name", f"farm {farm_id}"),
        area_ha=_require(farm_data, "area_ha", f"farm {farm_id}"),
        yield_factor=_require(farm_data, "yield_factor", f"farm {farm_id}"),
        starting_capital_usd=_require(farm_data, "starting_capital_usd", f"farm {farm_id}"),
        water_policy=water_policy,
        energy_policy=energy_policy_name,
        economic_policy=economic_policy_name,
    )


def _load_crops(crops_data):
    """Parse crop allocation list."""
    return [
        CropAllocation(
            name=_require(crop, "name", "crop"),
            area_fraction=_require(crop, "area_fraction", "crop"),
        )
        for crop in crops_data
    ]


def _load_economics(econ_data):
    """Parse economics section."""
    debt_data = _require(econ_data, "debt", "economics")

    return EconomicsConfig(
        currency=_require(econ_data, "currency", "economics"),
        discount_rate=_require(econ_data, "discount_rate", "economics"),
        debt=DebtConfig(
            principal_usd=_require(debt_data, "principal_usd", "economics.debt"),
            term_years=_require(debt_data, "term_years", "economics.debt"),
            interest_rate=_require(debt_data, "interest_rate", "economics.debt"),
        ),
    )


def load_scenario(path):
    """Load scenario from YAML file and return structured Scenario object.

    Args:
        path: Path to scenario YAML file (string or Path object)

    Returns:
        Scenario object with all configuration loaded

    Raises:
        FileNotFoundError: If scenario file doesn't exist
        KeyError: If required configuration is missing
        ValueError: If configuration values are invalid
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Scenario file not found: {path}")

    with open(path, "r") as f:
        data = yaml.safe_load(f)

    # Extract top-level sections
    scenario_data = _require(data, "scenario", "root")
    simulation_data = _require(data, "simulation", "root")
    community_data = _require(data, "community_structure", "root")
    econ_data = _require(data, "economics", "root")
    policy_parameters = data.get("community_policy_parameters", {})

    # Build metadata
    metadata = ScenarioMetadata(
        name=_require(scenario_data, "name", "scenario"),
        description=_require(scenario_data, "description", "scenario"),
        version=_require(scenario_data, "version", "scenario"),
        start_date=_parse_date(_require(simulation_data, "start_date", "simulation")),
        end_date=_parse_date(_require(simulation_data, "end_date", "simulation")),
        time_step=_require(simulation_data, "time_step", "simulation"),
        weather_scenario=_require(simulation_data, "weather_scenario", "simulation"),
    )

    # Build infrastructure (combines energy_infrastructure, water_infrastructure, food_processing_infrastructure)
    infrastructure = _load_infrastructure(data)

    # Build farms with instantiated policies
    farms_data = _require(community_data, "farms", "community_structure")
    farms = [_load_farm(farm, policy_parameters) for farm in farms_data]

    # Build community config
    crops_data = _require(community_data, "crops", "community_structure")
    community = CommunityConfig(
        total_farms=_require(community_data, "total_farms", "community_structure"),
        total_area_ha=_require(community_data, "total_area_ha", "community_structure"),
        population=_require(community_data, "community_population", "community_structure"),
        crops=_load_crops(crops_data),
    )

    # Build economics
    economics = _load_economics(econ_data)

    return Scenario(
        metadata=metadata,
        infrastructure=infrastructure,
        farms=farms,
        community=community,
        economics=economics,
    )
