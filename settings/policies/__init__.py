# Policy module exports for Community Agri-PV simulation
# Layer 2: Design configuration

from settings.policies.water_policies import (
    WaterPolicyContext,
    WaterAllocation,
    BaseWaterPolicy,
    AlwaysGroundwater,
    AlwaysMunicipal,
    CheapestSource,
    ConserveGroundwater,
)

# Policy registry for lookup by name (as used in scenario YAML)
WATER_POLICIES = {
    "always_groundwater": AlwaysGroundwater,
    "always_municipal": AlwaysMunicipal,
    "cheapest_source": CheapestSource,
    "conserve_groundwater": ConserveGroundwater,
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
    # Registry
    "WATER_POLICIES",
    "get_water_policy",
]
