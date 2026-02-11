# Water allocation policies for Community Agri-PV simulation
# Layer 2: Design configuration
#
# Four policies for comparative testing:
# - AlwaysGroundwater: 100% groundwater, municipal fallback if energy insufficient
# - AlwaysMunicipal: 100% municipal, no treatment energy needed
# - CheapestSource: dynamic selection based on daily cost comparison
# - ConserveGroundwater: prefers municipal, uses GW only when price > threshold

from dataclasses import dataclass
from typing import Optional


@dataclass
class WaterDecisionMetadata:
    """Metadata explaining why a water allocation decision was made.

    Enables tracking and visualization of policy decision patterns.

    Args:
        decision_reason: Human-readable reason for allocation choice
            Examples: "gw_cheaper", "muni_cheaper", "gw_preferred", "muni_only",
                     "energy_constrained", "threshold_not_met"
        gw_cost_per_m3: Groundwater cost at decision time (energy + maintenance)
        muni_cost_per_m3: Municipal water cost at decision time
        constraint_hit: Which constraint limited GW allocation, if any
            Values: "well_limit", "treatment_limit", "energy_limit", None
        limiting_factor: What actually limited the groundwater allocation.
            Distinguishes ratio caps from infrastructure constraints.
            Values: "ratio_cap", "well_limit", "treatment_limit", "energy_limit", None
    """
    decision_reason: str
    gw_cost_per_m3: float
    muni_cost_per_m3: float
    constraint_hit: Optional[str] = None
    limiting_factor: Optional[str] = None


@dataclass
class WaterPolicyContext:
    """Input context for water allocation decisions.

    Args:
        demand_m3: Total water demand in cubic meters
        available_energy_kwh: Energy available for water treatment
        treatment_kwh_per_m3: Energy required to treat 1 m3 of groundwater (desalination)
        gw_maintenance_per_m3: Maintenance cost per m3 of groundwater treatment (USD)
        municipal_price_per_m3: Current municipal water price (USD/m3)
        energy_price_per_kwh: Current energy price (USD/kWh)
        pumping_kwh_per_m3: Energy to pump 1 m3 from well to surface (default 0.0)
        conveyance_kwh_per_m3: Energy to convey 1 m3 from well/treatment to farm (default 0.0)
        max_groundwater_m3: Maximum groundwater extraction (well capacity / num_farms)
        max_treatment_m3: Maximum treatment throughput (treatment capacity / num_farms)
        cumulative_gw_year_m3: Cumulative groundwater used this year (for quota policies)
        cumulative_gw_month_m3: Cumulative groundwater used this month (for quota policies)
        current_month: Current month (1-12) for monthly quota calculations
    """
    demand_m3: float
    available_energy_kwh: float
    treatment_kwh_per_m3: float
    gw_maintenance_per_m3: float
    municipal_price_per_m3: float
    energy_price_per_kwh: float
    pumping_kwh_per_m3: float = 0.0
    conveyance_kwh_per_m3: float = 0.0
    max_groundwater_m3: float = float("inf")
    max_treatment_m3: float = float("inf")
    cumulative_gw_year_m3: float = 0.0
    cumulative_gw_month_m3: float = 0.0
    current_month: int = 1


@dataclass
class WaterAllocation:
    """Output from water allocation decision.

    Args:
        groundwater_m3: Volume allocated from treated groundwater
        municipal_m3: Volume allocated from municipal supply
        energy_used_kwh: Energy consumed for groundwater treatment
        cost_usd: Total cost of water allocation
        metadata: Decision metadata explaining why this allocation was made
    """
    groundwater_m3: float
    municipal_m3: float
    energy_used_kwh: float
    cost_usd: float
    metadata: Optional[WaterDecisionMetadata] = None


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
        """Calculate total groundwater cost per m3 including energy and maintenance.

        Cost_gw = (E_pump + E_convey + E_treatment) * electricity_price + O&M_cost
        """
        total_energy = ctx.pumping_kwh_per_m3 + ctx.conveyance_kwh_per_m3 + ctx.treatment_kwh_per_m3
        return (total_energy * ctx.energy_price_per_kwh) + ctx.gw_maintenance_per_m3

    def _calc_allocation_cost(self, gw_m3: float, muni_m3: float, ctx: WaterPolicyContext) -> float:
        """Calculate total cost for a given allocation."""
        gw_cost = gw_m3 * self._calc_gw_cost_per_m3(ctx)
        muni_cost = muni_m3 * ctx.municipal_price_per_m3
        return gw_cost + muni_cost

    def _calc_energy_used(self, gw_m3: float, ctx: WaterPolicyContext) -> float:
        """Calculate total energy used for groundwater (pumping + conveyance + treatment)."""
        total_energy_per_m3 = ctx.pumping_kwh_per_m3 + ctx.conveyance_kwh_per_m3 + ctx.treatment_kwh_per_m3
        return gw_m3 * total_energy_per_m3

    def _max_treatable_m3(self, ctx: WaterPolicyContext) -> float:
        """Calculate maximum groundwater volume processable with available energy."""
        total_energy_per_m3 = ctx.pumping_kwh_per_m3 + ctx.conveyance_kwh_per_m3 + ctx.treatment_kwh_per_m3
        if total_energy_per_m3 <= 0:
            return ctx.demand_m3
        return ctx.available_energy_kwh / total_energy_per_m3

    def _apply_constraints(self, requested_gw_m3: float, ctx: WaterPolicyContext) -> tuple:
        """Apply physical infrastructure constraints to groundwater allocation.

        Clips requested groundwater to the minimum of:
        - Energy-limited treatment capacity
        - Well extraction capacity
        - Treatment plant throughput

        Args:
            requested_gw_m3: Desired groundwater volume
            ctx: WaterPolicyContext with constraint values

        Returns:
            tuple: (constrained_gw_m3, constraint_hit)
                - constrained_gw_m3: Groundwater volume after constraints
                - constraint_hit: "energy_limit", "well_limit", "treatment_limit", or None
        """
        max_by_energy = self._max_treatable_m3(ctx)

        # Find which constraint is most restrictive
        limits = [
            (requested_gw_m3, None),
            (max_by_energy, "energy_limit"),
            (ctx.max_groundwater_m3, "well_limit"),
            (ctx.max_treatment_m3, "treatment_limit"),
        ]

        # Find minimum and its label
        min_val, constraint_hit = min(limits, key=lambda x: x[0])
        constrained = max(0.0, min_val)

        # Only report constraint if it actually reduced the allocation
        if constrained >= requested_gw_m3:
            constraint_hit = None

        return constrained, constraint_hit


class AlwaysGroundwater(BaseWaterPolicy):
    """Use groundwater for 100% of demand, fall back to municipal if constrained."""

    name = "always_groundwater"

    def allocate_water(self, ctx: WaterPolicyContext) -> WaterAllocation:
        gw_cost = self._calc_gw_cost_per_m3(ctx)
        muni_cost = ctx.municipal_price_per_m3

        # Request full demand as groundwater, apply constraints
        gw_m3, constraint_hit = self._apply_constraints(ctx.demand_m3, ctx)
        muni_m3 = ctx.demand_m3 - gw_m3

        # Determine decision reason
        if constraint_hit:
            reason = f"gw_preferred_but_{constraint_hit}"
        elif muni_m3 > 0:
            reason = "gw_preferred_partial"
        else:
            reason = "gw_preferred"

        metadata = WaterDecisionMetadata(
            decision_reason=reason,
            gw_cost_per_m3=gw_cost,
            muni_cost_per_m3=muni_cost,
            constraint_hit=constraint_hit,
        )

        return WaterAllocation(
            groundwater_m3=gw_m3,
            municipal_m3=muni_m3,
            energy_used_kwh=self._calc_energy_used(gw_m3, ctx),
            cost_usd=self._calc_allocation_cost(gw_m3, muni_m3, ctx),
            metadata=metadata,
        )

    def describe(self) -> str:
        return "always_groundwater: Use 100% groundwater, municipal fallback if constrained"


class AlwaysMunicipal(BaseWaterPolicy):
    """Use municipal water for 100% of demand. No treatment energy required."""

    name = "always_municipal"

    def allocate_water(self, ctx: WaterPolicyContext) -> WaterAllocation:
        gw_cost = self._calc_gw_cost_per_m3(ctx)
        muni_cost = ctx.municipal_price_per_m3

        metadata = WaterDecisionMetadata(
            decision_reason="muni_only",
            gw_cost_per_m3=gw_cost,
            muni_cost_per_m3=muni_cost,
            constraint_hit=None,
        )

        return WaterAllocation(
            groundwater_m3=0.0,
            municipal_m3=ctx.demand_m3,
            energy_used_kwh=0.0,
            cost_usd=ctx.demand_m3 * ctx.municipal_price_per_m3,
            metadata=metadata,
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

        # When include_energy_cost=False, compare only maintenance costs for source
        # selection. The final recorded cost still uses the full energy-inclusive cost.
        if self.include_energy_cost:
            gw_compare_cost = gw_cost_per_m3
        else:
            gw_compare_cost = ctx.gw_maintenance_per_m3

        constraint_hit = None
        if gw_compare_cost < muni_cost_per_m3:
            # Groundwater is cheaper - use as much as constraints allow
            gw_m3, constraint_hit = self._apply_constraints(ctx.demand_m3, ctx)
            muni_m3 = ctx.demand_m3 - gw_m3
            if constraint_hit:
                reason = f"gw_cheaper_but_{constraint_hit}"
            else:
                reason = "gw_cheaper"
        else:
            gw_m3 = 0.0
            muni_m3 = ctx.demand_m3
            reason = "muni_cheaper"

        metadata = WaterDecisionMetadata(
            decision_reason=reason,
            gw_cost_per_m3=gw_cost_per_m3,
            muni_cost_per_m3=muni_cost_per_m3,
            constraint_hit=constraint_hit,
        )

        return WaterAllocation(
            groundwater_m3=gw_m3,
            municipal_m3=muni_m3,
            energy_used_kwh=self._calc_energy_used(gw_m3, ctx),
            cost_usd=self._calc_allocation_cost(gw_m3, muni_m3, ctx),
            metadata=metadata,
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
        muni_cost_per_m3 = ctx.municipal_price_per_m3

        constraint_hit = None
        limiting_factor = None
        if muni_cost_per_m3 > threshold:
            # Municipal expensive - use GW up to max ratio, subject to constraints
            gw_demand = ctx.demand_m3 * self.max_gw_ratio
            gw_m3, constraint_hit = self._apply_constraints(gw_demand, ctx)
            muni_m3 = ctx.demand_m3 - gw_m3
            if constraint_hit:
                limiting_factor = constraint_hit
                reason = f"threshold_exceeded_but_{constraint_hit}"
            else:
                limiting_factor = "ratio_cap"
                reason = "threshold_exceeded"
        else:
            gw_m3 = 0.0
            muni_m3 = ctx.demand_m3
            reason = "threshold_not_met"

        metadata = WaterDecisionMetadata(
            decision_reason=reason,
            gw_cost_per_m3=gw_cost_per_m3,
            muni_cost_per_m3=muni_cost_per_m3,
            constraint_hit=constraint_hit,
            limiting_factor=limiting_factor,
        )

        return WaterAllocation(
            groundwater_m3=gw_m3,
            municipal_m3=muni_m3,
            energy_used_kwh=self._calc_energy_used(gw_m3, ctx),
            cost_usd=self._calc_allocation_cost(gw_m3, muni_m3, ctx),
            metadata=metadata,
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


class QuotaEnforced(BaseWaterPolicy):
    """Enforces annual groundwater quota with monthly tracking.

    Hard annual limit on groundwater extraction with monthly variance controls.
    Once quota is exhausted, forces 100% municipal water.

    Args:
        annual_quota_m3: Maximum groundwater that can be extracted in a year
        monthly_variance_pct: Allowed variance from equal monthly distribution (default 0.15 = 15%)
            Example: 12000 m3/year quota -> 1000 m3/month target
            With 15% variance: 850-1150 m3/month allowed
    """

    name = "quota_enforced"

    def __init__(self, annual_quota_m3: float, monthly_variance_pct: float = 0.15):
        self.annual_quota = annual_quota_m3
        self.monthly_variance = monthly_variance_pct

    def allocate_water(self, ctx: WaterPolicyContext) -> WaterAllocation:
        gw_cost = self._calc_gw_cost_per_m3(ctx)
        muni_cost = ctx.municipal_price_per_m3

        # Calculate quota constraints
        remaining_annual = max(0.0, self.annual_quota - ctx.cumulative_gw_year_m3)
        monthly_target = self.annual_quota / 12.0
        monthly_max = monthly_target * (1 + self.monthly_variance)
        remaining_monthly = max(0.0, monthly_max - ctx.cumulative_gw_month_m3)

        # Effective quota limit is the minimum of annual remaining and monthly remaining
        quota_limit = min(remaining_annual, remaining_monthly)

        # Determine allocation based on quota status
        constraint_hit = None

        if remaining_annual <= 0:
            # Annual quota exhausted - force 100% municipal
            gw_m3 = 0.0
            muni_m3 = ctx.demand_m3
            reason = "quota_exhausted"
        elif remaining_monthly <= 0:
            # Monthly limit exceeded - force municipal for rest of month
            gw_m3 = 0.0
            muni_m3 = ctx.demand_m3
            reason = "quota_monthly_limit"
        else:
            # Quota available - try to use groundwater up to quota limit
            requested_gw = min(ctx.demand_m3, quota_limit)

            # Apply physical constraints (well, treatment, energy)
            gw_m3, constraint_hit = self._apply_constraints(requested_gw, ctx)
            muni_m3 = ctx.demand_m3 - gw_m3

            if constraint_hit:
                reason = f"quota_available_but_{constraint_hit}"
            elif gw_m3 < ctx.demand_m3:
                # Partial allocation due to quota limit (not physical constraint)
                if gw_m3 < quota_limit:
                    reason = "quota_available"
                else:
                    reason = "quota_available_partial"
            else:
                reason = "quota_available"

        metadata = WaterDecisionMetadata(
            decision_reason=reason,
            gw_cost_per_m3=gw_cost,
            muni_cost_per_m3=muni_cost,
            constraint_hit=constraint_hit,
        )

        return WaterAllocation(
            groundwater_m3=gw_m3,
            municipal_m3=muni_m3,
            energy_used_kwh=self._calc_energy_used(gw_m3, ctx),
            cost_usd=self._calc_allocation_cost(gw_m3, muni_m3, ctx),
            metadata=metadata,
        )

    def get_parameters(self) -> dict:
        return {
            "annual_quota_m3": self.annual_quota,
            "monthly_variance_pct": self.monthly_variance,
        }

    def describe(self) -> str:
        monthly_target = self.annual_quota / 12.0
        monthly_min = monthly_target * (1 - self.monthly_variance)
        monthly_max = monthly_target * (1 + self.monthly_variance)
        return (
            f"quota_enforced: Hard annual limit of {self.annual_quota:,.0f} m3/year, "
            f"monthly range {monthly_min:,.0f}-{monthly_max:,.0f} m3 "
            f"({self.monthly_variance*100:.0f}% variance)"
        )
