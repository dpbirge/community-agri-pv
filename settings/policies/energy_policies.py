# Energy dispatch policies for Community Agri-PV simulation
# Layer 2: Design configuration
#
# Stubs for future implementation

from dataclasses import dataclass


@dataclass
class EnergyPolicyContext:
    """Input context for energy dispatch decisions.

    Args:
        demand_kwh: Total energy demand (irrigation, processing, housing, etc.)
        pv_available_kwh: PV generation available this period
        wind_available_kwh: Wind generation available this period
        battery_soc_kwh: Current battery state of charge
        battery_capacity_kwh: Total battery capacity
        grid_price_per_kwh: Current grid electricity price (USD/kWh)
        diesel_price_per_kwh: Current diesel generation cost (USD/kWh)
    """
    demand_kwh: float
    pv_available_kwh: float
    wind_available_kwh: float
    battery_soc_kwh: float
    battery_capacity_kwh: float
    grid_price_per_kwh: float
    diesel_price_per_kwh: float


@dataclass
class EnergyAllocation:
    """Output from energy dispatch decision.

    Args:
        pv_used_kwh: Energy used from PV
        wind_used_kwh: Energy used from wind
        battery_used_kwh: Energy discharged from battery
        grid_used_kwh: Energy purchased from grid
        diesel_used_kwh: Energy from diesel backup
        battery_charged_kwh: Energy sent to battery charging
        excess_kwh: Excess generation (curtailed or exported)
        cost_usd: Total energy cost
    """
    pv_used_kwh: float
    wind_used_kwh: float
    battery_used_kwh: float
    grid_used_kwh: float
    diesel_used_kwh: float
    battery_charged_kwh: float
    excess_kwh: float
    cost_usd: float


class BaseEnergyPolicy:
    """Base class for energy dispatch policies."""

    name = "base"

    def allocate_energy(self, ctx: EnergyPolicyContext) -> EnergyAllocation:
        raise NotImplementedError("Energy policy implementation pending")

    def get_parameters(self) -> dict:
        return {}

    def describe(self) -> str:
        return f"{self.name}: {self.__class__.__doc__}"


class PvFirstBatteryGridDiesel(BaseEnergyPolicy):
    """Energy dispatch priority: PV -> Wind -> Battery -> Grid -> Diesel."""

    name = "pv_first"

    def allocate_energy(self, ctx: EnergyPolicyContext) -> EnergyAllocation:
        raise NotImplementedError("Energy policy implementation pending")

    def describe(self) -> str:
        return "pv_first: Prioritize renewable sources, grid backup, diesel last resort"


class GridFirst(BaseEnergyPolicy):
    """Always use grid when available, renewables charge battery."""

    name = "grid_first"

    def allocate_energy(self, ctx: EnergyPolicyContext) -> EnergyAllocation:
        raise NotImplementedError("Energy policy implementation pending")

    def describe(self) -> str:
        return "grid_first: Grid power primary, renewables to battery"


class CheapestEnergy(BaseEnergyPolicy):
    """Dynamic selection based on current costs. Arbitrage between sources."""

    name = "cheapest_energy"

    def allocate_energy(self, ctx: EnergyPolicyContext) -> EnergyAllocation:
        raise NotImplementedError("Energy policy implementation pending")

    def describe(self) -> str:
        return "cheapest_energy: Cost-optimized dispatch with arbitrage"
