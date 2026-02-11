# Economic/financial policies for Community Agri-PV simulation
# Layer 2: Design configuration
#
# Four policies for comparative testing:
# - Balanced: Moderate approach, 3-month reserve target, invest when flush
# - AggressiveGrowth: Low reserves, maximize reinvestment, sell inventory fast
# - Conservative: High reserves, limit spending when under target
# - RiskAverse: Maximum caution, large reserves, minimize all risk

from dataclasses import dataclass


@dataclass
class EconomicPolicyContext:
    """Input context for economic decisions.

    Args:
        cash_reserves_usd: Current cash on hand
        monthly_revenue_usd: Revenue this period
        monthly_operating_cost_usd: Operating costs this period
        total_debt_usd: Outstanding debt principal
        debt_service_monthly_usd: Required monthly debt payment
        crop_inventory_kg: Current stored/unsold crop inventory
        months_of_reserves: Cash divided by average monthly costs
        current_month: Current month (1-12)
    """
    cash_reserves_usd: float = 0.0
    monthly_revenue_usd: float = 0.0
    monthly_operating_cost_usd: float = 0.0
    total_debt_usd: float = 0.0
    debt_service_monthly_usd: float = 0.0
    crop_inventory_kg: float = 0.0
    months_of_reserves: float = 0.0
    current_month: int = 1


@dataclass
class EconomicDecision:
    """Output from economic policy decision.

    Args:
        reserve_target_months: Target months of cash reserves to maintain
        investment_allowed: Whether to approve new investments
        sell_inventory: Whether to sell stored inventory now
        decision_reason: Human-readable decision rationale
        policy_name: Name of the policy that produced this decision
    """
    reserve_target_months: float = 3.0
    investment_allowed: bool = True
    sell_inventory: bool = False
    decision_reason: str = ""
    policy_name: str = ""


class BaseEconomicPolicy:
    """Base class for economic/financial policies."""

    name = "base"

    def decide(self, ctx: EconomicPolicyContext) -> EconomicDecision:
        raise NotImplementedError("Subclasses must implement decide()")

    def get_parameters(self) -> dict:
        return {}

    def describe(self) -> str:
        return f"{self.name}: {self.__class__.__doc__}"


class Balanced(BaseEconomicPolicy):
    """Adaptive: adjust risk based on current financial position."""

    name = "balanced"

    def decide(self, ctx: EconomicPolicyContext) -> EconomicDecision:
        reserve_target = 3.0
        investment_ok = ctx.months_of_reserves > reserve_target

        if ctx.months_of_reserves < 1.0:
            reason = f"Low reserves ({ctx.months_of_reserves:.1f} months), survival mode"
        elif ctx.months_of_reserves < reserve_target:
            reason = f"Building reserves ({ctx.months_of_reserves:.1f}/{reserve_target:.0f} months target)"
        else:
            reason = f"Healthy reserves ({ctx.months_of_reserves:.1f} months), balanced approach"

        return EconomicDecision(
            reserve_target_months=reserve_target,
            investment_allowed=investment_ok,
            sell_inventory=ctx.months_of_reserves < 1.0,
            decision_reason=reason,
            policy_name="balanced",
        )

    def describe(self) -> str:
        return "balanced: Adaptive risk based on financial health, 3-month reserve target"


class AggressiveGrowth(BaseEconomicPolicy):
    """Aggressive growth: hold minimal reserves, maximize reinvestment."""

    name = "aggressive_growth"

    def __init__(self, min_cash_months: int = 1, max_inventory_months: int = 6):
        self.min_cash_months = min_cash_months
        self.max_inventory_months = max_inventory_months

    def decide(self, ctx: EconomicPolicyContext) -> EconomicDecision:
        reserve_target = self.min_cash_months
        investment_ok = ctx.months_of_reserves > 0.5

        # Sell inventory aggressively to free up capital
        sell = ctx.crop_inventory_kg > 0

        return EconomicDecision(
            reserve_target_months=reserve_target,
            investment_allowed=investment_ok,
            sell_inventory=sell,
            decision_reason=f"Aggressive: {self.min_cash_months} month reserve target, invest everything above",
            policy_name="aggressive_growth",
        )

    def get_parameters(self) -> dict:
        return {
            "min_cash_months": self.min_cash_months,
            "max_inventory_months": self.max_inventory_months,
        }

    def describe(self) -> str:
        return (
            f"aggressive_growth: {self.min_cash_months}-month reserve target, "
            f"sell inventory fast, reinvest aggressively"
        )


class Conservative(BaseEconomicPolicy):
    """Risk-averse: maintain high cash reserves, limit spending when low."""

    name = "conservative"

    def __init__(self, min_cash_months: int = 6):
        self.min_cash_months = min_cash_months

    def decide(self, ctx: EconomicPolicyContext) -> EconomicDecision:
        reserve_target = self.min_cash_months
        investment_ok = ctx.months_of_reserves > reserve_target * 1.5

        if ctx.months_of_reserves < reserve_target:
            reason = f"Conservative: under {reserve_target} months reserves"
        else:
            reason = f"Conservative: {ctx.months_of_reserves:.1f} months reserves, adequate"

        return EconomicDecision(
            reserve_target_months=reserve_target,
            investment_allowed=investment_ok,
            sell_inventory=False,
            decision_reason=reason,
            policy_name="conservative",
        )

    def get_parameters(self) -> dict:
        return {"min_cash_months": self.min_cash_months}

    def describe(self) -> str:
        return f"conservative: Maintain {self.min_cash_months} months cash reserves, minimize risk"


class RiskAverse(BaseEconomicPolicy):
    """Maximum caution: build large reserves, minimize all risk exposure."""

    name = "risk_averse"

    def __init__(self, min_cash_months: int = 3):
        self.min_cash_months = min_cash_months

    def decide(self, ctx: EconomicPolicyContext) -> EconomicDecision:
        reserve_target = max(self.min_cash_months, 6.0)  # At least 6 months always
        investment_ok = ctx.months_of_reserves > 12.0  # Only invest with 12+ months reserves

        # Sell inventory immediately to lock in revenue
        sell = ctx.crop_inventory_kg > 0

        if ctx.months_of_reserves < 3.0:
            reason = f"Risk averse: critically low reserves ({ctx.months_of_reserves:.1f} months)"
        else:
            reason = f"Risk averse: {ctx.months_of_reserves:.1f} months reserves, target {reserve_target:.0f}"

        return EconomicDecision(
            reserve_target_months=reserve_target,
            investment_allowed=investment_ok,
            sell_inventory=sell,
            decision_reason=reason,
            policy_name="risk_averse",
        )

    def get_parameters(self) -> dict:
        return {"min_cash_months": self.min_cash_months}

    def describe(self) -> str:
        return (
            f"risk_averse: At least {max(self.min_cash_months, 6)} months reserves, "
            f"invest only with 12+ months, sell inventory immediately"
        )


# ---------------------------------------------------------------------------
# Policy registry
# ---------------------------------------------------------------------------

ECONOMIC_POLICIES = {
    "balanced": Balanced,
    "aggressive_growth": AggressiveGrowth,
    "conservative": Conservative,
    "risk_averse": RiskAverse,
}


def get_economic_policy(name, **kwargs):
    """Get an economic policy instance by name.

    Args:
        name: Policy name as string (e.g., "balanced", "conservative")
        **kwargs: Parameters to pass to policy constructor

    Returns:
        Instantiated policy object

    Raises:
        ValueError: If policy name not found
    """
    if name not in ECONOMIC_POLICIES:
        valid = ", ".join(ECONOMIC_POLICIES.keys())
        raise ValueError(
            f"Unknown economic policy: '{name}'. Available: {valid}"
        )
    return ECONOMIC_POLICIES[name](**kwargs)
