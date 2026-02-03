# Economic/financial policies for Community Agri-PV simulation
# Layer 2: Design configuration
#
# Stubs for future implementation

from dataclasses import dataclass


@dataclass
class EconomicPolicyContext:
    """Input context for economic decisions.

    Args:
        cash_balance_usd: Current cash on hand
        debt_balance_usd: Outstanding debt principal
        monthly_debt_payment_usd: Required monthly debt payment
        expected_revenue_usd: Expected revenue this period
        expected_costs_usd: Expected costs this period
        crop_inventory_kg: Current crop inventory (by crop)
        market_prices: Current market prices (by crop)
    """
    cash_balance_usd: float
    debt_balance_usd: float
    monthly_debt_payment_usd: float
    expected_revenue_usd: float
    expected_costs_usd: float
    crop_inventory_kg: dict
    market_prices: dict


@dataclass
class EconomicDecision:
    """Output from economic decision.

    Args:
        sell_now: Crops to sell immediately (dict of crop: kg)
        hold_inventory: Crops to hold for better prices (dict of crop: kg)
        defer_maintenance: Whether to defer non-critical maintenance
        reduce_labor: Temporary labor reduction fraction (0-0.3)
        notes: Decision rationale
    """
    sell_now: dict
    hold_inventory: dict
    defer_maintenance: bool
    reduce_labor: float
    notes: str


class BaseEconomicPolicy:
    """Base class for economic/financial policies."""

    name = "base"

    def decide(self, ctx: EconomicPolicyContext) -> EconomicDecision:
        raise NotImplementedError("Economic policy implementation pending")

    def get_parameters(self) -> dict:
        return {}

    def describe(self) -> str:
        return f"{self.name}: {self.__class__.__doc__}"


class Conservative(BaseEconomicPolicy):
    """Risk-averse: maintain high cash reserves, sell early, avoid speculation."""

    name = "conservative"

    def __init__(self, min_cash_months: int = 6):
        self.min_cash_months = min_cash_months

    def decide(self, ctx: EconomicPolicyContext) -> EconomicDecision:
        raise NotImplementedError("Economic policy implementation pending")

    def get_parameters(self) -> dict:
        return {"min_cash_months": self.min_cash_months}

    def describe(self) -> str:
        return f"conservative: Maintain {self.min_cash_months} months cash reserves, minimize risk"


class Moderate(BaseEconomicPolicy):
    """Balanced approach: reasonable reserves, some inventory speculation."""

    name = "moderate"

    def __init__(self, min_cash_months: int = 3):
        self.min_cash_months = min_cash_months

    def decide(self, ctx: EconomicPolicyContext) -> EconomicDecision:
        raise NotImplementedError("Economic policy implementation pending")

    def get_parameters(self) -> dict:
        return {"min_cash_months": self.min_cash_months}

    def describe(self) -> str:
        return f"moderate: Balance cash flow with modest inventory holding"


class Aggressive(BaseEconomicPolicy):
    """High risk tolerance: hold inventory for price peaks, leverage opportunities."""

    name = "aggressive"

    def __init__(self, min_cash_months: int = 1, max_inventory_months: int = 6):
        self.min_cash_months = min_cash_months
        self.max_inventory_months = max_inventory_months

    def decide(self, ctx: EconomicPolicyContext) -> EconomicDecision:
        raise NotImplementedError("Economic policy implementation pending")

    def get_parameters(self) -> dict:
        return {
            "min_cash_months": self.min_cash_months,
            "max_inventory_months": self.max_inventory_months,
        }

    def describe(self) -> str:
        return f"aggressive: Speculate on inventory, minimal cash reserves"


class Balanced(BaseEconomicPolicy):
    """Adaptive: adjust risk based on current financial position."""

    name = "balanced"

    def decide(self, ctx: EconomicPolicyContext) -> EconomicDecision:
        raise NotImplementedError("Economic policy implementation pending")

    def describe(self) -> str:
        return "balanced: Adaptive risk based on financial health"
