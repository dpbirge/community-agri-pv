# Market/sales policies for Community Agri-PV simulation
# Layer 2: Design configuration
#
# Four policies for comparative testing:
# - SellImmediately: Sell 100% at harvest, no storage, no processing
# - HoldForPeak: Hold crop in storage if price below threshold, sell when prices rise
# - ProcessWhenLow: Send crops to processing when fresh prices are low
# - AdaptiveMarketing: Combine strategies based on conditions

from dataclasses import dataclass


@dataclass
class MarketPolicyContext:
    """Input context for market/sales decisions.

    Args:
        crop_name: Crop to sell
        available_kg: Harvest or inventory available to sell
        current_price_per_kg: Today's farmgate price
        avg_price_per_kg: Average price this season
        price_trend: Positive = rising, negative = falling
        days_in_storage: How long crop has been stored
        shelf_life_days: Fresh crop shelf life
        storage_capacity_kg: Available storage space
        processing_capacity_kg: Available processing capacity
    """
    crop_name: str = ""
    available_kg: float = 0.0
    current_price_per_kg: float = 0.0
    avg_price_per_kg: float = 0.0
    price_trend: float = 0.0
    days_in_storage: int = 0
    shelf_life_days: int = 7
    storage_capacity_kg: float = 0.0
    processing_capacity_kg: float = 0.0


@dataclass
class MarketDecision:
    """Output from market/sales decision.

    Fractions (sell_fraction, store_fraction, process_fraction) should
    sum to approximately 1.0.

    Args:
        sell_fraction: Fraction to sell now (0-1)
        store_fraction: Fraction to store
        process_fraction: Fraction to send to processing
        target_price_per_kg: Minimum acceptable price (0 = any price)
        decision_reason: Human-readable decision rationale
        policy_name: Name of the policy that made this decision
    """
    sell_fraction: float = 1.0
    store_fraction: float = 0.0
    process_fraction: float = 0.0
    target_price_per_kg: float = 0.0
    decision_reason: str = ""
    policy_name: str = ""


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
            process_fraction=0.0,
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
        elif ctx.days_in_storage >= ctx.shelf_life_days - 1:
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


class ProcessWhenLow(BaseMarketPolicy):
    """Process fresh produce when prices are low. Preserves value, extends shelf life."""

    name = "process_when_low"

    def __init__(self, price_floor_multiplier: float = 0.80):
        self.price_floor_multiplier = price_floor_multiplier

    def decide(self, ctx: MarketPolicyContext) -> MarketDecision:
        price_floor = ctx.avg_price_per_kg * self.price_floor_multiplier

        if ctx.current_price_per_kg < price_floor and ctx.processing_capacity_kg > 0:
            # Price is low -- process instead of selling fresh
            processable = min(ctx.available_kg, ctx.processing_capacity_kg)
            process_frac = processable / ctx.available_kg if ctx.available_kg > 0 else 0.0
            sell_frac = 1.0 - process_frac
            return MarketDecision(
                sell_fraction=sell_frac,
                process_fraction=process_frac,
                decision_reason=(
                    f"Low price ${ctx.current_price_per_kg:.2f} < "
                    f"floor ${price_floor:.2f}, processing {process_frac:.0%}"
                ),
                policy_name="process_when_low",
            )
        else:
            # Price is acceptable -- sell fresh
            return MarketDecision(
                sell_fraction=1.0,
                decision_reason=(
                    f"Price ${ctx.current_price_per_kg:.2f} >= "
                    f"floor ${price_floor:.2f}, selling fresh"
                ),
                policy_name="process_when_low",
            )

    def get_parameters(self) -> dict:
        return {"price_floor_multiplier": self.price_floor_multiplier}

    def describe(self) -> str:
        return f"process_when_low: Process when price < {self.price_floor_multiplier}x average"


class AdaptiveMarketing(BaseMarketPolicy):
    """Combine immediate sales, holding, and processing based on conditions."""

    name = "adaptive_marketing"

    def decide(self, ctx: MarketPolicyContext) -> MarketDecision:
        if ctx.current_price_per_kg > ctx.avg_price_per_kg * 1.10:
            # Above average -- sell everything
            return MarketDecision(
                sell_fraction=1.0,
                decision_reason=(
                    f"Price above average "
                    f"({ctx.current_price_per_kg:.2f} > {ctx.avg_price_per_kg * 1.10:.2f}), sell all"
                ),
                policy_name="adaptive_marketing",
            )
        elif ctx.price_trend > 0 and ctx.days_in_storage < ctx.shelf_life_days // 2:
            # Price is rising and we have storage time -- hold some
            store_frac = min(0.50, ctx.storage_capacity_kg / max(ctx.available_kg, 1))
            return MarketDecision(
                sell_fraction=1.0 - store_frac,
                store_fraction=store_frac,
                decision_reason=f"Rising prices, holding {store_frac:.0%} in storage",
                policy_name="adaptive_marketing",
            )
        elif ctx.current_price_per_kg < ctx.avg_price_per_kg * 0.85:
            # Well below average -- process if possible
            if ctx.processing_capacity_kg > 0:
                process_frac = min(
                    0.60, ctx.processing_capacity_kg / max(ctx.available_kg, 1)
                )
                return MarketDecision(
                    sell_fraction=1.0 - process_frac,
                    process_fraction=process_frac,
                    decision_reason=f"Low price, processing {process_frac:.0%}",
                    policy_name="adaptive_marketing",
                )
            return MarketDecision(
                sell_fraction=1.0,
                decision_reason="Low price but no processing capacity, selling",
                policy_name="adaptive_marketing",
            )
        else:
            # Normal price range -- sell now
            return MarketDecision(
                sell_fraction=1.0,
                decision_reason=(
                    f"Normal price range, selling at ${ctx.current_price_per_kg:.2f}"
                ),
                policy_name="adaptive_marketing",
            )

    def describe(self) -> str:
        return "adaptive_marketing: Dynamic mix of sell/hold/process strategies"


# ---------------------------------------------------------------------------
# Registry and factory
# ---------------------------------------------------------------------------

MARKET_POLICIES = {
    "sell_immediately": SellImmediately,
    "hold_for_peak": HoldForPeak,
    "process_when_low": ProcessWhenLow,
    "adaptive_marketing": AdaptiveMarketing,
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
