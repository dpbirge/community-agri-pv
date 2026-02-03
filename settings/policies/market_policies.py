# Market/sales policies for Community Agri-PV simulation
# Layer 2: Design configuration
#
# Stubs for future implementation

from dataclasses import dataclass


@dataclass
class MarketPolicyContext:
    """Input context for market/sales decisions.

    Args:
        crop_name: Crop to sell
        inventory_kg: Available inventory
        current_price_usd_kg: Current market price
        price_30d_avg_usd_kg: 30-day average price
        price_90d_avg_usd_kg: 90-day average price
        spoilage_rate_per_day: Daily spoilage rate (fraction)
        storage_cost_per_kg_day: Daily storage cost
        days_until_next_harvest: Days until next harvest of this crop
    """
    crop_name: str
    inventory_kg: float
    current_price_usd_kg: float
    price_30d_avg_usd_kg: float
    price_90d_avg_usd_kg: float
    spoilage_rate_per_day: float
    storage_cost_per_kg_day: float
    days_until_next_harvest: int


@dataclass
class MarketDecision:
    """Output from market/sales decision.

    Args:
        sell_kg: Quantity to sell
        hold_kg: Quantity to hold
        process_kg: Quantity to send to processing (drying, canning, etc.)
        target_price_usd_kg: Price target for held inventory (None = market price)
        notes: Decision rationale
    """
    sell_kg: float
    hold_kg: float
    process_kg: float
    target_price_usd_kg: float
    notes: str


class BaseMarketPolicy:
    """Base class for market/sales policies."""

    name = "base"

    def decide(self, ctx: MarketPolicyContext) -> MarketDecision:
        raise NotImplementedError("Market policy implementation pending")

    def get_parameters(self) -> dict:
        return {}

    def describe(self) -> str:
        return f"{self.name}: {self.__class__.__doc__}"


class SellImmediately(BaseMarketPolicy):
    """Sell all production immediately at market price. No inventory risk."""

    name = "sell_immediately"

    def decide(self, ctx: MarketPolicyContext) -> MarketDecision:
        raise NotImplementedError("Market policy implementation pending")

    def describe(self) -> str:
        return "sell_immediately: No inventory holding, immediate market sale"


class HoldForPeak(BaseMarketPolicy):
    """Hold inventory waiting for price above threshold. Risk spoilage."""

    name = "hold_for_peak"

    def __init__(self, price_threshold_multiplier: float = 1.20):
        self.price_threshold_multiplier = price_threshold_multiplier

    def decide(self, ctx: MarketPolicyContext) -> MarketDecision:
        raise NotImplementedError("Market policy implementation pending")

    def get_parameters(self) -> dict:
        return {"price_threshold_multiplier": self.price_threshold_multiplier}

    def describe(self) -> str:
        return f"hold_for_peak: Wait for price > {self.price_threshold_multiplier}x average"


class ProcessWhenLow(BaseMarketPolicy):
    """Process fresh produce when prices are low. Preserves value, extends shelf life."""

    name = "process_when_low"

    def __init__(self, price_floor_multiplier: float = 0.80):
        self.price_floor_multiplier = price_floor_multiplier

    def decide(self, ctx: MarketPolicyContext) -> MarketDecision:
        raise NotImplementedError("Market policy implementation pending")

    def get_parameters(self) -> dict:
        return {"price_floor_multiplier": self.price_floor_multiplier}

    def describe(self) -> str:
        return f"process_when_low: Process when price < {self.price_floor_multiplier}x average"


class AdaptiveMarketing(BaseMarketPolicy):
    """Combine immediate sales, holding, and processing based on conditions."""

    name = "adaptive_marketing"

    def decide(self, ctx: MarketPolicyContext) -> MarketDecision:
        raise NotImplementedError("Market policy implementation pending")

    def describe(self) -> str:
        return "adaptive_marketing: Dynamic mix of sell/hold/process strategies"
