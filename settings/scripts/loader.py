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
class EquipmentMix:
    """Single equipment type with its usage fraction."""
    type: str
    fraction: float


@dataclass
class ProcessingCategoryConfig:
    """Configuration for a processing category (drying, canning, etc.).

    YAML specifies equipment mix; CSV specifies equipment specifications.
    Energy, labor, and capacity are looked up from CSV based on equipment type.
    """
    equipment: list  # List of EquipmentMix
    storage_capacity_kg_total: float
    shelf_life_days: int


@dataclass
class FoodProcessingConfig:
    """Food processing infrastructure configuration."""
    fresh_food_packaging: ProcessingCategoryConfig
    drying: ProcessingCategoryConfig
    canning: ProcessingCategoryConfig
    packaging: ProcessingCategoryConfig


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
    """Crop area allocation (community-level, deprecated)."""
    name: str
    area_fraction: float


@dataclass
class FarmCropConfig:
    """Per-farm crop configuration with planting schedule."""
    name: str
    area_fraction: float
    planting_date: str  # MM-DD format
    percent_planted: float


@dataclass
class SubsidizedPricingConfig:
    """Subsidized municipal water pricing (tiered rates)."""
    use_tier: int  # 1, 2, or 3


@dataclass
class UnsubsidizedPricingConfig:
    """Unsubsidized municipal water pricing (SWRO full cost)."""
    base_price_usd_m3: float
    annual_escalation_pct: float


@dataclass
class WaterPricingConfig:
    """Water pricing configuration for municipal water."""
    municipal_source: str  # seawater_desalination or piped_nile
    pricing_regime: str  # subsidized or unsubsidized
    subsidized: SubsidizedPricingConfig
    unsubsidized: UnsubsidizedPricingConfig


@dataclass
class GridConfig:
    """Grid electricity configuration."""
    pricing_regime: str  # subsidized or unsubsidized


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
    food_policy: str
    crops: list  # List of FarmCropConfig


@dataclass
class CommunityConfig:
    """Community structure configuration."""
    total_farms: int
    total_area_ha: float
    population: int
    crops: list = None  # Optional for backward compatibility (per-farm crops preferred)


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
    water_pricing: WaterPricingConfig = None
    grid: GridConfig = None
    policy_parameters: dict = None


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


def _parse_equipment_list(equipment_data, context):
    """Parse equipment list from YAML and create EquipmentMix objects."""
    equipment_list = []
    for eq in equipment_data:
        eq_type = _require(eq, "type", context)
        eq_fraction = _require(eq, "fraction", context)
        equipment_list.append(EquipmentMix(type=eq_type, fraction=eq_fraction))
    return equipment_list


def _parse_processing_category(category_data, category_name):
    """Parse a processing category from YAML into ProcessingCategoryConfig."""
    context = f"food_processing_infrastructure.{category_name}"
    equipment_data = _require(category_data, "equipment", context)
    equipment_list = _parse_equipment_list(equipment_data, context)

    # Validate fractions sum to 1.0
    total_fraction = sum(eq.fraction for eq in equipment_list)
    if abs(total_fraction - 1.0) > 0.01:
        raise ValueError(f"{context}: equipment fractions must sum to 1.0, got {total_fraction}")

    return ProcessingCategoryConfig(
        equipment=equipment_list,
        storage_capacity_kg_total=_require(category_data, "storage_capacity_kg_total", context),
        shelf_life_days=_require(category_data, "shelf_life_days", context),
    )


def _load_infrastructure(data):
    """Parse infrastructure sections into config objects.

    Supports both full scenario format with all fields and simplified format
    with just capacity numbers (using sensible defaults for optional fields).
    """
    # Energy infrastructure
    energy_infra = _require(data, "energy_infrastructure", "root")
    pv = energy_infra.get("pv", {})
    wind = energy_infra.get("wind", {})
    battery = energy_infra.get("battery", {})
    diesel = energy_infra.get("backup_generator", {})

    # Validate PV configuration if full config provided
    percent_over_crops = pv.get("percent_over_crops", 0.0)
    if not (0 <= percent_over_crops <= 1):
        raise ValueError(f"percent_over_crops must be between 0 and 1, got {percent_over_crops}")

    density = pv.get("density", "medium")
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

    # Validate water infrastructure values
    number_of_wells = _require(wells, "number_of_wells", "water_infrastructure.groundwater_wells")
    if number_of_wells <= 0:
        raise ValueError(f"number_of_wells must be > 0, got {number_of_wells}")

    number_of_units = _require(water_treatment, "number_of_units", "water_infrastructure.water_treatment")
    if number_of_units <= 0:
        raise ValueError(f"number_of_units must be > 0, got {number_of_units}")

    # Battery units - use default of 1 if not specified (for simplified scenarios)
    battery_units = battery.get("units", 1)
    if battery_units <= 0:
        raise ValueError(f"battery.units must be > 0, got {battery_units}")

    return InfrastructureConfig(
        pv=PVConfig(
            sys_capacity_kw=pv.get("sys_capacity_kw", 0.0),
            type=pv.get("type", "fixed_tilt"),
            tilt_angle=pv.get("tilt_angle", 28.0),
            percent_over_crops=percent_over_crops,
            density=density,
            height_m=pv.get("height_m", 4.0),
        ),
        wind=WindConfig(
            sys_capacity_kw=wind.get("sys_capacity_kw", 0.0),
            type=wind.get("type", "horizontal_axis"),
            hub_height_m=wind.get("hub_height_m", 40.0),
        ),
        battery=BatteryConfig(
            sys_capacity_kwh=battery.get("sys_capacity_kwh", 0.0),
            units=battery_units,
            chemistry=battery.get("chemistry", "lithium_iron_phosphate"),
        ),
        diesel_backup=DieselBackupConfig(
            capacity_kw=diesel.get("capacity_kw", 0.0),
            type=diesel.get("type", "diesel_generator"),
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
            fresh_food_packaging=_parse_processing_category(fresh_packaging, "fresh_food_packaging"),
            drying=_parse_processing_category(drying, "drying"),
            canning=_parse_processing_category(canning, "canning"),
            packaging=_parse_processing_category(packaging, "packaging"),
        ),
    )


def _load_farm_crops(crops_data, farm_id):
    """Parse per-farm crop configuration list."""
    crops = []
    for crop in crops_data:
        context = f"farm {farm_id} crops"
        crops.append(FarmCropConfig(
            name=_require(crop, "name", context),
            area_fraction=_require(crop, "area_fraction", context),
            planting_date=_require(crop, "planting_date", context),
            percent_planted=_require(crop, "percent_planted", context),
        ))
    return crops


def _load_farm(farm_data, policy_parameters):
    """Parse farm data and instantiate water policy."""
    farm_id = _require(farm_data, "id", "farm")
    policies = _require(farm_data, "policies", f"farm {farm_id}")

    water_policy_name = _require(policies, "water", f"farm {farm_id} policies")
    energy_policy_name = _require(policies, "energy", f"farm {farm_id} policies")
    economic_policy_name = _require(policies, "economic", f"farm {farm_id} policies")
    food_policy_name = policies.get("food", "all_fresh")  # Default to all_fresh

    # Get policy parameters if defined in scenario
    water_params = policy_parameters.get(water_policy_name, {})

    # Instantiate water policy
    water_policy = get_water_policy(water_policy_name, **water_params)

    # Parse per-farm crops if present
    crops_data = farm_data.get("crops", [])
    crops = _load_farm_crops(crops_data, farm_id) if crops_data else []

    return Farm(
        id=farm_id,
        name=_require(farm_data, "name", f"farm {farm_id}"),
        area_ha=_require(farm_data, "area_ha", f"farm {farm_id}"),
        yield_factor=_require(farm_data, "yield_factor", f"farm {farm_id}"),
        starting_capital_usd=_require(farm_data, "starting_capital_usd", f"farm {farm_id}"),
        water_policy=water_policy,
        energy_policy=energy_policy_name,
        economic_policy=economic_policy_name,
        food_policy=food_policy_name,
        crops=crops,
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


def _load_water_pricing(data):
    """Parse water_pricing section if present."""
    if "water_pricing" not in data:
        return None

    wp = data["water_pricing"]
    context = "water_pricing"

    subsidized_data = wp.get("subsidized", {})
    unsubsidized_data = wp.get("unsubsidized", {})

    return WaterPricingConfig(
        municipal_source=_require(wp, "municipal_source", context),
        pricing_regime=_require(wp, "pricing_regime", context),
        subsidized=SubsidizedPricingConfig(
            use_tier=subsidized_data.get("use_tier", 3),
        ),
        unsubsidized=UnsubsidizedPricingConfig(
            base_price_usd_m3=unsubsidized_data.get("base_price_usd_m3", 0.75),
            annual_escalation_pct=unsubsidized_data.get("annual_escalation_pct", 3.0),
        ),
    )


def _load_grid_config(data):
    """Parse grid configuration from energy_infrastructure if present."""
    energy_infra = data.get("energy_infrastructure", {})
    grid_data = energy_infra.get("grid", {})

    if not grid_data:
        return None

    return GridConfig(
        pricing_regime=grid_data.get("pricing_regime", "subsidized"),
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

    # Build community config (crops optional for per-farm crop scenarios)
    crops_data = community_data.get("crops", [])
    community = CommunityConfig(
        total_farms=_require(community_data, "total_farms", "community_structure"),
        total_area_ha=_require(community_data, "total_area_ha", "community_structure"),
        population=_require(community_data, "community_population", "community_structure"),
        crops=_load_crops(crops_data) if crops_data else None,
    )

    # Build economics
    economics = _load_economics(econ_data)

    # Build water pricing config (optional)
    water_pricing = _load_water_pricing(data)

    # Build grid config (optional)
    grid = _load_grid_config(data)

    return Scenario(
        metadata=metadata,
        infrastructure=infrastructure,
        farms=farms,
        community=community,
        economics=economics,
        water_pricing=water_pricing,
        grid=grid,
        policy_parameters=policy_parameters,
    )
