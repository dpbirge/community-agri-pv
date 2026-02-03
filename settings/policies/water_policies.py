# Water allocation policies for Community Agri-PV simulation
# Layer 2: Design configuration
#
# Four policies for comparative testing:
# - AlwaysGroundwater: 100% groundwater, municipal fallback if energy insufficient
# - AlwaysMunicipal: 100% municipal, no treatment energy needed
# - CheapestSource: dynamic selection based on daily cost comparison
# - ConserveGroundwater: prefers municipal, uses GW only when price > threshold

from dataclasses import dataclass


@dataclass
class WaterPolicyContext:
    """Input context for water allocation decisions.

    Args:
        demand_m3: Total water demand in cubic meters
        available_energy_kwh: Energy available for water treatment
        treatment_kwh_per_m3: Energy required to treat 1 m3 of groundwater
        gw_maintenance_per_m3: Maintenance cost per m3 of groundwater treatment (USD)
        municipal_price_per_m3: Current municipal water price (USD/m3)
        energy_price_per_kwh: Current energy price (USD/kWh)
    """
    demand_m3: float
    available_energy_kwh: float
    treatment_kwh_per_m3: float
    gw_maintenance_per_m3: float
    municipal_price_per_m3: float
    energy_price_per_kwh: float


@dataclass
class WaterAllocation:
    """Output from water allocation decision.

    Args:
        groundwater_m3: Volume allocated from treated groundwater
        municipal_m3: Volume allocated from municipal supply
        energy_used_kwh: Energy consumed for groundwater treatment
        cost_usd: Total cost of water allocation
    """
    groundwater_m3: float
    municipal_m3: float
    energy_used_kwh: float
    cost_usd: float


class BaseWaterPolicy:
    """Base class for water allocation policies."""

    name = "base"

    def allocate_water(self, ctx: WaterPolicyContext) -> WaterAllocation:
        raise NotImplementedError

    def get_parameters(self) -> dict:
        return {}

    def describe(self) -> str:
        return f"{self.name}: {self.__class__.__doc__}"

    def _calc_gw_cost_per_m3(self, ctx: WaterPolicyContext) -> float:
        """Calculate total groundwater cost per m3 including energy and maintenance."""
        return (ctx.treatment_kwh_per_m3 * ctx.energy_price_per_kwh) + ctx.gw_maintenance_per_m3

    def _calc_allocation_cost(self, gw_m3: float, muni_m3: float, ctx: WaterPolicyContext) -> float:
        """Calculate total cost for a given allocation."""
        gw_cost = gw_m3 * self._calc_gw_cost_per_m3(ctx)
        muni_cost = muni_m3 * ctx.municipal_price_per_m3
        return gw_cost + muni_cost

    def _calc_energy_used(self, gw_m3: float, ctx: WaterPolicyContext) -> float:
        """Calculate energy used for groundwater treatment."""
        return gw_m3 * ctx.treatment_kwh_per_m3

    def _max_treatable_m3(self, ctx: WaterPolicyContext) -> float:
        """Calculate maximum volume that can be treated with available energy."""
        if ctx.treatment_kwh_per_m3 <= 0:
            return ctx.demand_m3
        return ctx.available_energy_kwh / ctx.treatment_kwh_per_m3


class AlwaysGroundwater(BaseWaterPolicy):
    """Use groundwater for 100% of demand, fall back to municipal if energy insufficient."""

    name = "always_groundwater"

    def allocate_water(self, ctx: WaterPolicyContext) -> WaterAllocation:
        required_energy = ctx.demand_m3 * ctx.treatment_kwh_per_m3

        if ctx.available_energy_kwh >= required_energy:
            gw_m3 = ctx.demand_m3
            muni_m3 = 0.0
        else:
            gw_m3 = self._max_treatable_m3(ctx)
            muni_m3 = ctx.demand_m3 - gw_m3

        return WaterAllocation(
            groundwater_m3=gw_m3,
            municipal_m3=muni_m3,
            energy_used_kwh=self._calc_energy_used(gw_m3, ctx),
            cost_usd=self._calc_allocation_cost(gw_m3, muni_m3, ctx),
        )

    def describe(self) -> str:
        return "always_groundwater: Use 100% groundwater, municipal fallback if energy insufficient"


class AlwaysMunicipal(BaseWaterPolicy):
    """Use municipal water for 100% of demand. No treatment energy required."""

    name = "always_municipal"

    def allocate_water(self, ctx: WaterPolicyContext) -> WaterAllocation:
        return WaterAllocation(
            groundwater_m3=0.0,
            municipal_m3=ctx.demand_m3,
            energy_used_kwh=0.0,
            cost_usd=ctx.demand_m3 * ctx.municipal_price_per_m3,
        )

    def describe(self) -> str:
        return "always_municipal: Use 100% municipal water, no treatment energy needed"


class CheapestSource(BaseWaterPolicy):
    """Select water source based on current cost comparison. Dynamically switches daily."""

    name = "cheapest_source"

    def __init__(self, include_energy_cost: bool = True):
        self.include_energy_cost = include_energy_cost

    def allocate_water(self, ctx: WaterPolicyContext) -> WaterAllocation:
        gw_cost_per_m3 = self._calc_gw_cost_per_m3(ctx)
        muni_cost_per_m3 = ctx.municipal_price_per_m3

        if gw_cost_per_m3 < muni_cost_per_m3:
            required_energy = ctx.demand_m3 * ctx.treatment_kwh_per_m3
            if ctx.available_energy_kwh >= required_energy:
                gw_m3 = ctx.demand_m3
                muni_m3 = 0.0
            else:
                gw_m3 = self._max_treatable_m3(ctx)
                muni_m3 = ctx.demand_m3 - gw_m3
        else:
            gw_m3 = 0.0
            muni_m3 = ctx.demand_m3

        return WaterAllocation(
            groundwater_m3=gw_m3,
            municipal_m3=muni_m3,
            energy_used_kwh=self._calc_energy_used(gw_m3, ctx),
            cost_usd=self._calc_allocation_cost(gw_m3, muni_m3, ctx),
        )

    def get_parameters(self) -> dict:
        return {"include_energy_cost": self.include_energy_cost}

    def describe(self) -> str:
        return "cheapest_source: Dynamic selection based on daily cost comparison"


class ConserveGroundwater(BaseWaterPolicy):
    """Prefer municipal water to conserve aquifer. Use GW only when municipal price exceeds threshold."""

    name = "conserve_groundwater"

    def __init__(self, price_threshold_multiplier: float = 1.5, max_gw_ratio: float = 0.30):
        self.price_threshold_multiplier = price_threshold_multiplier
        self.max_gw_ratio = max_gw_ratio

    def allocate_water(self, ctx: WaterPolicyContext) -> WaterAllocation:
        gw_cost_per_m3 = self._calc_gw_cost_per_m3(ctx)
        threshold = gw_cost_per_m3 * self.price_threshold_multiplier

        if ctx.municipal_price_per_m3 > threshold:
            gw_demand = ctx.demand_m3 * self.max_gw_ratio
            required_energy = gw_demand * ctx.treatment_kwh_per_m3

            if ctx.available_energy_kwh >= required_energy:
                gw_m3 = gw_demand
            else:
                gw_m3 = self._max_treatable_m3(ctx)

            muni_m3 = ctx.demand_m3 - gw_m3
        else:
            gw_m3 = 0.0
            muni_m3 = ctx.demand_m3

        return WaterAllocation(
            groundwater_m3=gw_m3,
            municipal_m3=muni_m3,
            energy_used_kwh=self._calc_energy_used(gw_m3, ctx),
            cost_usd=self._calc_allocation_cost(gw_m3, muni_m3, ctx),
        )

    def get_parameters(self) -> dict:
        return {
            "price_threshold_multiplier": self.price_threshold_multiplier,
            "max_gw_ratio": self.max_gw_ratio,
        }

    def describe(self) -> str:
        return (
            f"conserve_groundwater: Prefer municipal, use GW only when "
            f"municipal > {self.price_threshold_multiplier}x GW cost "
            f"(max {self.max_gw_ratio*100:.0f}% GW)"
        )
