# Policy module exports for Community Agri-PV simulation
# Layer 2: Design configuration

from src.policies.water_policies import (
    WaterPolicyContext,
    WaterAllocation,
    BaseWaterPolicy,
    AlwaysGroundwater,
    AlwaysMunicipal,
    CheapestSource,
    ConserveGroundwater,
    QuotaEnforced,
)

from src.policies.energy_policies import (
    EnergyPolicyContext,
    EnergyAllocation,
    BaseEnergyPolicy,
    PvFirstBatteryGridDiesel,
    GridFirst,
    CheapestEnergy,
    ENERGY_POLICIES,
    get_energy_policy,
)

from src.policies.food_policies import (
    FoodProcessingContext,
    ProcessingAllocation,
    BaseFoodPolicy,
    AllFresh,
    MaximizeStorage,
    Balanced as FoodBalanced,
    MarketResponsive,
    FOOD_POLICIES,
    get_food_policy,
)

from src.policies.crop_policies import (
    CropPolicyContext,
    CropDecision,
    BaseCropPolicy,
    FixedSchedule,
    DeficitIrrigation,
    WeatherAdaptive,
    CROP_POLICIES,
    get_crop_policy,
)

from src.policies.economic_policies import (
    EconomicPolicyContext,
    EconomicDecision,
    BaseEconomicPolicy,
    Balanced as EconomicBalanced,
    AggressiveGrowth,
    Conservative,
    RiskAverse,
    ECONOMIC_POLICIES,
    get_economic_policy,
)

from src.policies.market_policies import (
    MarketPolicyContext,
    MarketDecision,
    BaseMarketPolicy,
    SellImmediately,
    HoldForPeak,
    Adaptive,
    MARKET_POLICIES,
    get_market_policy,
)

# Policy registry for lookup by name (as used in scenario YAML)
WATER_POLICIES = {
    "always_groundwater": AlwaysGroundwater,
    "always_municipal": AlwaysMunicipal,
    "cheapest_source": CheapestSource,
    "conserve_groundwater": ConserveGroundwater,
    "quota_enforced": QuotaEnforced,
}


def get_water_policy(name, **kwargs):
    """Get a water policy instance by name.

    Args:
        name: Policy name as string (e.g., "always_groundwater")
        **kwargs: Parameters to pass to policy constructor

    Returns:
        Instantiated policy object

    Raises:
        KeyError: If policy name not found
    """
    if name not in WATER_POLICIES:
        valid = ", ".join(WATER_POLICIES.keys())
        raise KeyError(f"Unknown water policy '{name}'. Valid: {valid}")
    return WATER_POLICIES[name](**kwargs)


__all__ = [
    # Water policies
    "WaterPolicyContext",
    "WaterAllocation",
    "BaseWaterPolicy",
    "AlwaysGroundwater",
    "AlwaysMunicipal",
    "CheapestSource",
    "ConserveGroundwater",
    "QuotaEnforced",
    # Water registry
    "WATER_POLICIES",
    "get_water_policy",
    # Energy policies
    "EnergyPolicyContext",
    "EnergyAllocation",
    "BaseEnergyPolicy",
    "PvFirstBatteryGridDiesel",
    "GridFirst",
    "CheapestEnergy",
    # Energy registry
    "ENERGY_POLICIES",
    "get_energy_policy",
    # Food policies
    "FoodProcessingContext",
    "ProcessingAllocation",
    "BaseFoodPolicy",
    "AllFresh",
    "MaximizeStorage",
    "FoodBalanced",
    "MarketResponsive",
    # Food registry
    "FOOD_POLICIES",
    "get_food_policy",
    # Crop policies
    "CropPolicyContext",
    "CropDecision",
    "BaseCropPolicy",
    "FixedSchedule",
    "DeficitIrrigation",
    "WeatherAdaptive",
    # Crop registry
    "CROP_POLICIES",
    "get_crop_policy",
    # Economic policies
    "EconomicPolicyContext",
    "EconomicDecision",
    "BaseEconomicPolicy",
    "EconomicBalanced",
    "AggressiveGrowth",
    "Conservative",
    "RiskAverse",
    # Economic registry
    "ECONOMIC_POLICIES",
    "get_economic_policy",
    # Market policies
    "MarketPolicyContext",
    "MarketDecision",
    "BaseMarketPolicy",
    "SellImmediately",
    "HoldForPeak",
    "Adaptive",
    # Market registry
    "MARKET_POLICIES",
    "get_market_policy",
]
