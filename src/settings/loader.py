# Scenario loader for Community Agri-PV simulation
# Layer 2: Bridges YAML configuration to simulation runtime
#
# Loads scenario files, instantiates policies, returns structured dataclasses.
# Energy and economic policies remain as string names until those modules are implemented.

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

import yaml

from src.policies import get_water_policy, BaseWaterPolicy, get_food_policy, BaseFoodPolicy


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
    """Photovoltaic system configuration (fixed-tilt only)."""
    sys_capacity_kw: float
    tilt_angle: float
    percent_over_crops: float
    density: str
    height_m: float
    financing_status: str = "existing_owned"


@dataclass
class WindConfig:
    """Wind turbine configuration."""
    sys_capacity_kw: float
    type: str
    financing_status: str = "existing_owned"


@dataclass
class BatteryConfig:
    """Battery storage configuration."""
    sys_capacity_kwh: float
    units: int
    chemistry: str
    financing_status: str = "existing_owned"


@dataclass
class DieselBackupConfig:
    """Diesel backup generator configuration."""
    capacity_kw: float
    type: str
    financing_status: str = "existing_owned"


@dataclass
class GroundwaterWellsConfig:
    """Groundwater wells configuration."""
    well_depth_m: float
    well_flow_rate_m3_day: float
    number_of_wells: int
    aquifer_exploitable_volume_m3: float = 0.0
    aquifer_recharge_rate_m3_yr: float = 0.0
    max_drawdown_m: float = 0.0  # Maximum drawdown at full depletion (for pumping energy feedback)
    financing_status: str = "existing_owned"


@dataclass
class WaterTreatmentConfig:
    """Water treatment system configuration."""
    system_capacity_m3_day: float
    number_of_units: int
    salinity_level: str
    tds_ppm: float
    financing_status: str = "existing_owned"


@dataclass
class IrrigationStorageConfig:
    """Irrigation water storage configuration."""
    capacity_m3: float
    type: str
    financing_status: str = "existing_owned"


@dataclass
class IrrigationSystemConfig:
    """Irrigation system configuration."""
    type: str
    financing_status: str = "existing_owned"


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
    financing_status: str = "existing_owned"


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
class TierBracket:
    """Single tier bracket for consumption-based pricing.

    Defines a consumption range and its associated price. Used for both
    water (m3/month) and electricity (kWh/month) tier structures.

    Args:
        min_units: Lower bound of tier (inclusive)
        max_units: Upper bound of tier (exclusive), None for unlimited
        price_per_unit: Price per unit (USD/m3 or USD/kWh)
    """
    min_units: float
    max_units: float  # None indicates unlimited (final tier)
    price_per_unit: float


@dataclass
class TierPricingConfig:
    """Configuration for consumption-based tiered pricing.

    Supports Egyptian-style progressive tier pricing where higher consumption
    levels pay higher per-unit rates. Tiers are applied based on cumulative
    monthly consumption.

    Args:
        enabled: Whether tier pricing is active
        resource_type: "water" or "electricity"
        reset_period: Period for consumption tracking ("monthly" or "annual")
        brackets: List of TierBracket defining consumption tiers
        include_wastewater_surcharge: For water, add wastewater fee as % of tariff
        wastewater_surcharge_pct: Wastewater surcharge percentage (default 75%)

    Egyptian Water Tiers (2018 reference):
        - Tier 1: 0-10 m3/month @ 0.65 EGP/m3
        - Tier 2: 11-20 m3/month @ 1.60 EGP/m3
        - Tier 3: 21-30 m3/month @ 2.25 EGP/m3
        - Tier 4: 31-40 m3/month @ 2.75 EGP/m3
        - Tier 5: >40 m3/month @ 3.15 EGP/m3

    Egyptian Residential Electricity Tiers (Aug 2024 reference):
        - Tier 1: 0-50 kWh/month @ 0.68 EGP/kWh
        - Tier 2: 51-100 kWh/month @ 0.78 EGP/kWh
        - Tier 3: 101-200 kWh/month @ 0.95 EGP/kWh
        - Tier 4: 201-350 kWh/month @ 1.55 EGP/kWh
        - Tier 5: 351-650 kWh/month @ 1.95 EGP/kWh
        - Tier 6: 651-1000 kWh/month @ 2.10 EGP/kWh
        - Tier 7: >1000 kWh/month @ 1.65 EGP/kWh
    """
    enabled: bool
    resource_type: str  # "water" or "electricity"
    reset_period: str  # "monthly" or "annual"
    brackets: list  # List of TierBracket
    include_wastewater_surcharge: bool = False
    wastewater_surcharge_pct: float = 75.0


@dataclass
class SubsidizedPricingConfig:
    """Subsidized municipal water pricing (tiered rates)."""
    use_tier: int  # 1, 2, or 3 (legacy simple tier selection)
    tier_pricing: TierPricingConfig = None  # Optional full tier configuration


@dataclass
class UnsubsidizedPricingConfig:
    """Unsubsidized municipal water pricing (SWRO full cost)."""
    base_price_usd_m3: float
    annual_escalation_pct: float


@dataclass
class WaterPricingConfig:
    """Water pricing configuration for municipal water."""
    municipal_source: str  # seawater_desalination or piped_groundwater
    pricing_regime: str  # subsidized or unsubsidized
    subsidized: SubsidizedPricingConfig
    unsubsidized: UnsubsidizedPricingConfig


@dataclass
class GridSubsidizedConfig:
    """Subsidized grid electricity pricing (agricultural rates)."""
    use_peak_offpeak: bool = False  # If True, use peak/offpeak rates; if False, use average daily


@dataclass
class GridUnsubsidizedConfig:
    """Unsubsidized grid electricity pricing (commercial/industrial rates)."""
    base_price_usd_kwh: float
    annual_escalation_pct: float


@dataclass
class GridPricingConfig:
    """Grid electricity pricing configuration."""
    pricing_regime: str  # subsidized or unsubsidized
    subsidized: GridSubsidizedConfig
    unsubsidized: GridUnsubsidizedConfig


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
    food_policy: BaseFoodPolicy
    crops: list  # List of FarmCropConfig


@dataclass
class CommunityConfig:
    """Community structure configuration."""
    total_farms: int
    total_area_ha: float
    population: int
    crops: list = None  # Optional for backward compatibility (per-farm crops preferred)
    industrial_buildings_m2: float = 0.0  # Square meters of industrial/processing facilities
    community_buildings_m2: float = 0.0  # Square meters of community buildings (offices, halls, etc.)


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
    energy_pricing: GridPricingConfig = None
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
    context = f"food_processing_system.{category_name}"
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
        financing_status=category_data.get("financing_status", "existing_owned"),
    )


def _load_infrastructure(data):
    """Parse system sections into config objects.

    Supports both full scenario format with all fields and simplified format
    with just capacity numbers (using sensible defaults for optional fields).
    """
    # Energy system
    energy_infra = _require(data, "energy_system", "root")
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

    # Water system
    water_infra = _require(data, "water_system", "root")
    wells = _require(water_infra, "groundwater_wells", "water_system")
    water_treatment = _require(water_infra, "water_treatment", "water_system")
    irrigation_storage = _require(water_infra, "irrigation_water_storage", "water_system")
    irrigation_system = _require(water_infra, "irrigation_system", "water_system")

    # Food processing system
    food_processing_infra = _require(data, "food_processing_system", "root")
    fresh_packaging = _require(food_processing_infra, "fresh_food_packaging", "food_processing_system")
    drying = _require(food_processing_infra, "drying", "food_processing_system")
    canning = _require(food_processing_infra, "canning", "food_processing_system")
    packaging = _require(food_processing_infra, "packaging", "food_processing_system")

    # Validate water system values
    number_of_wells = _require(wells, "number_of_wells", "water_system.groundwater_wells")
    if number_of_wells <= 0:
        raise ValueError(f"number_of_wells must be > 0, got {number_of_wells}")

    number_of_units = _require(water_treatment, "number_of_units", "water_system.water_treatment")
    if number_of_units <= 0:
        raise ValueError(f"number_of_units must be > 0, got {number_of_units}")

    # Battery units - use default of 1 if not specified (for simplified scenarios)
    battery_units = battery.get("units", 1)
    if battery_units <= 0:
        raise ValueError(f"battery.units must be > 0, got {battery_units}")

    return InfrastructureConfig(
        pv=PVConfig(
            sys_capacity_kw=pv.get("sys_capacity_kw", 0.0),
            tilt_angle=pv.get("tilt_angle", 28.0),
            percent_over_crops=percent_over_crops,
            density=density,
            height_m=pv.get("height_m", 4.0),
            financing_status=pv.get("financing_status", "existing_owned"),
        ),
        wind=WindConfig(
            sys_capacity_kw=wind.get("sys_capacity_kw", 0.0),
            type=wind.get("type", "small"),
            financing_status=wind.get("financing_status", "existing_owned"),
        ),
        battery=BatteryConfig(
            sys_capacity_kwh=battery.get("sys_capacity_kwh", 0.0),
            units=battery_units,
            chemistry=battery.get("chemistry", "lithium_iron_phosphate"),
            financing_status=battery.get("financing_status", "existing_owned"),
        ),
        diesel_backup=DieselBackupConfig(
            capacity_kw=diesel.get("capacity_kw", 0.0),
            type=diesel.get("type", "diesel_generator"),
            financing_status=diesel.get("financing_status", "existing_owned"),
        ),
        groundwater_wells=GroundwaterWellsConfig(
            well_depth_m=_require(wells, "well_depth_m", "water_system.groundwater_wells"),
            well_flow_rate_m3_day=_require(wells, "well_flow_rate_m3_day", "water_system.groundwater_wells"),
            number_of_wells=number_of_wells,
            aquifer_exploitable_volume_m3=wells.get("aquifer_exploitable_volume_m3", 0.0),
            aquifer_recharge_rate_m3_yr=wells.get("aquifer_recharge_rate_m3_yr", 0.0),
            max_drawdown_m=wells.get("max_drawdown_m", 0.0),
            financing_status=wells.get("financing_status", "existing_owned"),
        ),
        water_treatment=WaterTreatmentConfig(
            system_capacity_m3_day=_require(water_treatment, "system_capacity_m3_day", "water_system.water_treatment"),
            number_of_units=number_of_units,
            salinity_level=_require(water_treatment, "salinity_level", "water_system.water_treatment"),
            tds_ppm=_require(water_treatment, "tds_ppm", "water_system.water_treatment"),
            financing_status=water_treatment.get("financing_status", "existing_owned"),
        ),
        irrigation_storage=IrrigationStorageConfig(
            capacity_m3=_require(irrigation_storage, "capacity_m3", "water_system.irrigation_water_storage"),
            type=_require(irrigation_storage, "type", "water_system.irrigation_water_storage"),
            financing_status=irrigation_storage.get("financing_status", "existing_owned"),
        ),
        irrigation_system=IrrigationSystemConfig(
            type=_require(irrigation_system, "type", "water_system.irrigation_system"),
            financing_status=irrigation_system.get("financing_status", "existing_owned"),
        ),
        food_processing=FoodProcessingConfig(
            fresh_food_packaging=_parse_processing_category(fresh_packaging, "fresh_food_packaging"),
            drying=_parse_processing_category(drying, "drying"),
            canning=_parse_processing_category(canning, "canning"),
            packaging=_parse_processing_category(packaging, "packaging"),
        ),
    )


def _load_farm_crops(crops_data, farm_id):
    """Parse per-farm crop configuration list.

    Each crop entry has a `planting_dates` list (MM-DD strings). One FarmCropConfig
    is created per planting date, all sharing the same area_fraction and percent_planted.
    """
    crops = []
    for crop in crops_data:
        context = f"farm {farm_id} crops"
        name = _require(crop, "name", context)
        area_fraction = _require(crop, "area_fraction", context)
        planting_dates = _require(crop, "planting_dates", context)
        percent_planted = _require(crop, "percent_planted", context)

        if not isinstance(planting_dates, list) or len(planting_dates) == 0:
            raise ValueError(f"{context}: planting_dates must be a non-empty list for crop '{name}'")

        for pd in planting_dates:
            crops.append(FarmCropConfig(
                name=name,
                area_fraction=area_fraction,
                planting_date=pd,
                percent_planted=percent_planted,
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

    # Instantiate food processing policy
    food_params = policy_parameters.get(food_policy_name, {})
    food_policy = get_food_policy(food_policy_name, **food_params)

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
        food_policy=food_policy,
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


def _load_tier_brackets(brackets_data, context):
    """Parse tier bracket list from YAML.

    Args:
        brackets_data: List of bracket dicts from YAML
        context: Context string for error messages

    Returns:
        List of TierBracket objects
    """
    brackets = []
    for i, b in enumerate(brackets_data):
        bracket_context = f"{context}.bracket[{i}]"
        brackets.append(TierBracket(
            min_units=_require(b, "min_units", bracket_context),
            max_units=b.get("max_units"),  # None for final tier
            price_per_unit=_require(b, "price_per_unit", bracket_context),
        ))
    return brackets


def _load_tier_pricing(tier_data, context):
    """Parse tier pricing configuration from YAML.

    Args:
        tier_data: Dict with tier pricing configuration
        context: Context string for error messages

    Returns:
        TierPricingConfig or None if not present
    """
    if not tier_data:
        return None

    brackets_data = tier_data.get("brackets", [])
    if not brackets_data:
        return None

    brackets = _load_tier_brackets(brackets_data, f"{context}.tier_pricing")

    return TierPricingConfig(
        enabled=tier_data.get("enabled", True),
        resource_type=tier_data.get("resource_type", "water"),
        reset_period=tier_data.get("reset_period", "monthly"),
        brackets=brackets,
        include_wastewater_surcharge=tier_data.get("include_wastewater_surcharge", False),
        wastewater_surcharge_pct=tier_data.get("wastewater_surcharge_pct", 75.0),
    )


def _load_water_pricing(data):
    """Parse water_pricing section if present."""
    if "water_pricing" not in data:
        return None

    wp = data["water_pricing"]
    context = "water_pricing"

    subsidized_data = wp.get("subsidized", {})
    unsubsidized_data = wp.get("unsubsidized", {})

    # Parse optional tier pricing configuration
    tier_pricing = _load_tier_pricing(
        subsidized_data.get("tier_pricing"),
        f"{context}.subsidized"
    )

    return WaterPricingConfig(
        municipal_source=_require(wp, "municipal_source", context),
        pricing_regime=_require(wp, "pricing_regime", context),
        subsidized=SubsidizedPricingConfig(
            use_tier=subsidized_data.get("use_tier", 3),
            tier_pricing=tier_pricing,
        ),
        unsubsidized=UnsubsidizedPricingConfig(
            base_price_usd_m3=unsubsidized_data.get("base_price_usd_m3", 0.75),
            annual_escalation_pct=unsubsidized_data.get("annual_escalation_pct", 3.0),
        ),
    )


def _load_energy_pricing(data):
    """Parse energy pricing configuration if present.

    Args:
        data: Parsed YAML data

    Returns:
        GridPricingConfig or None
    """
    ep = data.get("energy_pricing", {})
    if not ep:
        return None

    context = "energy_pricing"
    grid_data = ep.get("grid", {})

    if not grid_data:
        return None

    subsidized_data = grid_data.get("subsidized", {})
    unsubsidized_data = grid_data.get("unsubsidized", {})

    return GridPricingConfig(
        pricing_regime=grid_data.get("pricing_regime", "subsidized"),
        subsidized=GridSubsidizedConfig(
            use_peak_offpeak=subsidized_data.get("use_peak_offpeak", False),
        ),
        unsubsidized=GridUnsubsidizedConfig(
            base_price_usd_kwh=unsubsidized_data.get("base_price_usd_kwh", 0.15),
            annual_escalation_pct=unsubsidized_data.get("annual_escalation_pct", 3.0),
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

    # Build infrastructure (combines energy_system, water_system, food_processing_system)
    infrastructure = _load_infrastructure(data)

    # Build farms with instantiated policies
    farms_data = _require(community_data, "farms", "community_structure")
    farms = [_load_farm(farm, policy_parameters) for farm in farms_data]

    # Build community config (crops optional for per-farm crop scenarios)
    # Accept total_farming_area_ha (spec canonical) with fallback to total_area_ha
    crops_data = community_data.get("crops", [])
    total_area = community_data.get(
        "total_farming_area_ha",
        _require(community_data, "total_area_ha", "community_structure"),
    )
    community = CommunityConfig(
        total_farms=_require(community_data, "total_farms", "community_structure"),
        total_area_ha=total_area,
        population=_require(community_data, "community_population", "community_structure"),
        crops=_load_crops(crops_data) if crops_data else None,
        industrial_buildings_m2=community_data.get("industrial_buildings_m2", 0.0),
        community_buildings_m2=community_data.get("community_buildings_m2", 0.0),
    )

    # Build economics
    economics = _load_economics(econ_data)

    # Build water pricing config (optional)
    water_pricing = _load_water_pricing(data)

    # Build energy pricing config (optional)
    energy_pricing = _load_energy_pricing(data)

    return Scenario(
        metadata=metadata,
        infrastructure=infrastructure,
        farms=farms,
        community=community,
        economics=economics,
        water_pricing=water_pricing,
        energy_pricing=energy_pricing,
        policy_parameters=policy_parameters,
    )
