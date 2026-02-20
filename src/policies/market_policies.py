# Market/sales policies for Community Agri-PV simulation
# Layer 2: Design configuration
#
# Three policies determining WHEN processed food is sold (sell vs. store):
# - SellImmediately: Sell 100% at market price, no inventory holding
# - HoldForPeak: Hold inventory until price exceeds threshold above average
# - Adaptive: Sigmoid-based sell/store decision based on price ratio to average

from dataclasses import dataclass


@dataclass
class MarketPolicyContext:
    """Input context for market/sales decisions.

    Args:
        crop_name: Crop being considered for sale (e.g., "tomato")
        product_type: Processing type ("fresh", "packaged", "canned", "dried")
        available_kg: Harvest or inventory available to sell
        current_price_per_kg: Today's market price for this crop+product_type
        avg_price_per_kg: Average price for this crop+product_type over recent history
        price_trend: Positive = rising, negative = falling
        days_in_storage: How long product has been stored
        storage_life_days: Max storage duration (days) from storage_spoilage_rates data
        storage_capacity_kg: Available storage space
    """
    crop_name: str = ""
    product_type: str = "fresh"
    available_kg: float = 0.0
    current_price_per_kg: float = 0.0
    avg_price_per_kg: float = 0.0
    price_trend: float = 0.0
    days_in_storage: int = 0
    storage_life_days: int = 7
    storage_capacity_kg: float = 0.0


@dataclass
class MarketDecision:
    """Output from market/sales decision.

    sell_fraction + store_fraction must equal 1.0. Food processing is
    handled entirely by food processing policies, not market policies.

    Args:
        sell_fraction: Fraction to sell now (0-1)
        store_fraction: Fraction to keep in storage (0-1)
        target_price_per_kg: Minimum acceptable price (0 = any price)
        decision_reason: Human-readable decision rationale
        policy_name: Name of the policy that made this decision
    """
    sell_fraction: float = 1.0
    store_fraction: float = 0.0
    target_price_per_kg: float = 0.0
    decision_reason: str = ""
    policy_name: str = ""

    def __post_init__(self):
        total = self.sell_fraction + self.store_fraction
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"Market fractions must sum to 1.0, got {total:.4f} "
                f"(sell={self.sell_fraction}, store={self.store_fraction})"
            )


class BaseMarketPolicy:
    """Base class for market/sales policies."""

    name = "base"

    def decide(self, ctx: MarketPolicyContext) -> MarketDecision:
        raise NotImplementedError("Subclasses must implement decide()")

    def get_parameters(self) -> dict:
        return {}

    def describe(self) -> str:
        return f"{self.name}: {self.__class__.__doc__}"


class SellImmediately(BaseMarketPolicy):
    """Sell all production immediately at market price. No inventory risk."""

    name = "sell_immediately"

    def decide(self, ctx: MarketPolicyContext) -> MarketDecision:
        return MarketDecision(
            sell_fraction=1.0,
            store_fraction=0.0,
            decision_reason="Sell immediately at market price",
            policy_name="sell_immediately",
        )

    def describe(self) -> str:
        return "sell_immediately: No inventory holding, immediate market sale"


class HoldForPeak(BaseMarketPolicy):
    """Hold inventory waiting for price above threshold. Risk spoilage."""

    name = "hold_for_peak"

    def __init__(self, price_threshold_multiplier: float = 1.20):
        self.price_threshold_multiplier = price_threshold_multiplier

    def decide(self, ctx: MarketPolicyContext) -> MarketDecision:
        target_price = ctx.avg_price_per_kg * self.price_threshold_multiplier

        if ctx.current_price_per_kg >= target_price:
            # Price is above target -- sell now
            return MarketDecision(
                sell_fraction=1.0,
                target_price_per_kg=target_price,
                decision_reason=(
                    f"Price ${ctx.current_price_per_kg:.2f} >= "
                    f"target ${target_price:.2f}, selling"
                ),
                policy_name="hold_for_peak",
            )
        elif ctx.days_in_storage >= ctx.storage_life_days - 1:
            # About to spoil -- sell at any price
            return MarketDecision(
                sell_fraction=1.0,
                decision_reason=(
                    f"Storage limit reached ({ctx.days_in_storage} days), forced sale"
                ),
                policy_name="hold_for_peak",
            )
        elif ctx.storage_capacity_kg > ctx.available_kg:
            # Store and wait for better price
            return MarketDecision(
                sell_fraction=0.0,
                store_fraction=1.0,
                target_price_per_kg=target_price,
                decision_reason=(
                    f"Price ${ctx.current_price_per_kg:.2f} < "
                    f"target ${target_price:.2f}, storing"
                ),
                policy_name="hold_for_peak",
            )
        else:
            # No storage space -- sell now
            return MarketDecision(
                sell_fraction=1.0,
                decision_reason="No storage capacity, selling at current price",
                policy_name="hold_for_peak",
            )

    def get_parameters(self) -> dict:
        return {"price_threshold_multiplier": self.price_threshold_multiplier}

    def describe(self) -> str:
        return f"hold_for_peak: Wait for price > {self.price_threshold_multiplier}x average"


class Adaptive(BaseMarketPolicy):
    """Sigmoid-based sell/store decision based on price ratio to average.

    When prices are high relative to history, sell more. When prices are
    low, store more and wait for better conditions.
    """

    name = "adaptive"

    def __init__(self, midpoint=1.0, steepness=5.0, min_sell=0.2, max_sell=1.0):
        self.midpoint = midpoint
        self.steepness = steepness
        self.min_sell = min_sell
        self.max_sell = max_sell

    def _sigmoid(self, price_ratio):
        """Map price ratio to sell fraction using scaled sigmoid."""
        import math
        raw = 1.0 / (1.0 + math.exp(-self.steepness * (price_ratio - self.midpoint)))
        return self.min_sell + (self.max_sell - self.min_sell) * raw

    def decide(self, ctx: MarketPolicyContext) -> MarketDecision:
        if ctx.avg_price_per_kg <= 0:
            return MarketDecision(
                sell_fraction=1.0,
                decision_reason="No average price data, selling all",
                policy_name="adaptive",
            )

        price_ratio = ctx.current_price_per_kg / ctx.avg_price_per_kg
        sell_fraction = self._sigmoid(price_ratio)
        store_fraction = 1.0 - sell_fraction

        # Clip store_fraction to available storage capacity
        if ctx.storage_capacity_kg <= 0:
            sell_fraction = 1.0
            store_fraction = 0.0
        elif store_fraction * ctx.available_kg > ctx.storage_capacity_kg:
            store_fraction = ctx.storage_capacity_kg / max(ctx.available_kg, 1)
            sell_fraction = 1.0 - store_fraction

        if sell_fraction > 0.9:
            reason = "high_price_selling"
        elif sell_fraction < 0.3:
            reason = "low_price_storing"
        else:
            reason = "moderate_price_partial_sale"

        return MarketDecision(
            sell_fraction=sell_fraction,
            store_fraction=store_fraction,
            decision_reason=reason,
            policy_name="adaptive",
        )

    def get_parameters(self) -> dict:
        return {
            "midpoint": self.midpoint,
            "steepness": self.steepness,
            "min_sell": self.min_sell,
            "max_sell": self.max_sell,
        }

    def describe(self) -> str:
        return (
            f"adaptive: Sigmoid sell/store (midpoint={self.midpoint}, "
            f"steepness={self.steepness}, range=[{self.min_sell}, {self.max_sell}])"
        )


# ---------------------------------------------------------------------------
# Registry and factory
# ---------------------------------------------------------------------------

MARKET_POLICIES = {
    "sell_immediately": SellImmediately,
    "hold_for_peak": HoldForPeak,
    "adaptive": Adaptive,
}


def get_market_policy(name, **kwargs):
    """Get a market policy instance by name.

    Args:
        name: Policy name as string (e.g., "sell_immediately")
        **kwargs: Parameters to pass to policy constructor

    Returns:
        Instantiated policy object

    Raises:
        ValueError: If policy name not found
    """
    if name not in MARKET_POLICIES:
        raise ValueError(
            f"Unknown market policy: {name}. "
            f"Available: {list(MARKET_POLICIES.keys())}"
        )
    return MARKET_POLICIES[name](**kwargs)
