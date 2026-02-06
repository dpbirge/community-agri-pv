# Food processing allocation policies for Community Agri-PV simulation
# Layer 2: Design configuration
#
# Four policies for comparative testing:
# - AllFresh: 100% to fresh sale (current behavior, backward compatible)
# - MaximizeStorage: Maximize shelf life by processing most of harvest
# - Balanced: Mix of fresh and processed per mvp-calculations.md
# - MarketResponsive: More processing when fresh prices are low

from dataclasses import dataclass


@dataclass
class FoodProcessingContext:
    """Input context for food processing policy decisions.

    Args:
        harvest_yield_kg: Total harvest yield before processing (kg)
        crop_name: Name of crop being processed
        fresh_price_per_kg: Current fresh farmgate price (USD/kg)
        fresh_packaging_capacity_kg: Daily fresh packaging capacity limit (kg)
        drying_capacity_kg: Daily drying capacity limit (kg)
        canning_capacity_kg: Daily canning capacity limit (kg)
        packaging_capacity_kg: Daily packaging capacity limit (kg)
    """
    harvest_yield_kg: float
    crop_name: str
    fresh_price_per_kg: float
    # Processing capacity limits (from food_processing_system config)
    fresh_packaging_capacity_kg: float = float('inf')
    drying_capacity_kg: float = float('inf')
    canning_capacity_kg: float = float('inf')
    packaging_capacity_kg: float = float('inf')


@dataclass
class ProcessingAllocation:
    """Result of food processing policy decision.

    Fractions must sum to 1.0. Each represents the share of harvest
    directed to that processing pathway.

    Args:
        fresh_fraction: Fraction sold as fresh produce (0-1)
        packaged_fraction: Fraction sent to fresh packaging (0-1)
        canned_fraction: Fraction sent to canning (0-1)
        dried_fraction: Fraction sent to drying (0-1)
        policy_name: Name of the policy that produced this allocation
    """
    fresh_fraction: float = 1.0
    packaged_fraction: float = 0.0
    canned_fraction: float = 0.0
    dried_fraction: float = 0.0
    policy_name: str = ""


class BaseFoodPolicy:
    """Base class for food processing policies.

    Subclasses implement allocate() to determine how harvested crop
    is split across processing pathways (fresh, packaged, canned, dried).
    """

    name: str = "base"

    def allocate(self, ctx: FoodProcessingContext) -> ProcessingAllocation:
        """Allocate harvest across processing pathways.

        Args:
            ctx: FoodProcessingContext with harvest and pricing info

        Returns:
            ProcessingAllocation with fractions for each pathway
        """
        raise NotImplementedError


class AllFresh(BaseFoodPolicy):
    """100% fresh sale — no processing.

    This is the default policy and must produce identical revenue to the
    pre-food-processing code path (backward compatible).
    """

    name = "all_fresh"

    def allocate(self, ctx: FoodProcessingContext) -> ProcessingAllocation:
        return ProcessingAllocation(
            fresh_fraction=1.0,
            packaged_fraction=0.0,
            canned_fraction=0.0,
            dried_fraction=0.0,
            policy_name="all_fresh",
        )


class MaximizeStorage(BaseFoodPolicy):
    """Maximize shelf life by processing most of harvest.

    Sends only 20% to fresh sale; the rest is split between dried (35%),
    canned (35%), and packaged (10%) for long-term storage.
    """

    name = "maximize_storage"

    def allocate(self, ctx: FoodProcessingContext) -> ProcessingAllocation:
        return ProcessingAllocation(
            fresh_fraction=0.20,
            packaged_fraction=0.10,
            canned_fraction=0.35,
            dried_fraction=0.35,
            policy_name="maximize_storage",
        )


class Balanced(BaseFoodPolicy):
    """Balanced mix of fresh and processed per mvp-calculations.md.

    50% fresh, 20% packaged, 15% canned, 15% dried. Provides a moderate
    level of value-add processing while keeping half the harvest for
    immediate fresh sale.
    """

    name = "balanced"

    def allocate(self, ctx: FoodProcessingContext) -> ProcessingAllocation:
        return ProcessingAllocation(
            fresh_fraction=0.50,
            packaged_fraction=0.20,
            canned_fraction=0.15,
            dried_fraction=0.15,
            policy_name="balanced",
        )


class MarketResponsive(BaseFoodPolicy):
    """Adjust processing mix based on current fresh prices.

    When fresh prices are below 80% of reference farmgate prices, shifts
    more harvest into processing (higher value-add pathways). When prices
    are normal or high, sells more fresh.

    Reference prices are typical Egyptian farmgate prices in USD/kg.
    """

    name = "market_responsive"

    # Reference farmgate prices (USD/kg) for threshold comparison
    REFERENCE_PRICES = {
        "tomato": 0.30,
        "potato": 0.25,
        "onion": 0.20,
        "kale": 0.40,
        "cucumber": 0.35,
    }

    def allocate(self, ctx: FoodProcessingContext) -> ProcessingAllocation:
        ref = self.REFERENCE_PRICES.get(ctx.crop_name, 0.30)

        if ctx.fresh_price_per_kg < ref * 0.80:
            # Low prices — process more to capture value-add
            return ProcessingAllocation(
                fresh_fraction=0.30,
                packaged_fraction=0.20,
                canned_fraction=0.25,
                dried_fraction=0.25,
                policy_name="market_responsive",
            )
        else:
            # Normal/high prices — sell more fresh
            return ProcessingAllocation(
                fresh_fraction=0.65,
                packaged_fraction=0.15,
                canned_fraction=0.10,
                dried_fraction=0.10,
                policy_name="market_responsive",
            )


# Policy registry for lookup by name (as used in scenario YAML)
FOOD_POLICIES = {
    "all_fresh": AllFresh,
    "maximize_storage": MaximizeStorage,
    "balanced": Balanced,
    "market_responsive": MarketResponsive,
}


def get_food_policy(name, **kwargs):
    """Get a food processing policy instance by name.

    Args:
        name: Policy name as string (e.g., "all_fresh", "balanced")
        **kwargs: Parameters to pass to policy constructor

    Returns:
        Instantiated policy object

    Raises:
        KeyError: If policy name not found
    """
    if name not in FOOD_POLICIES:
        valid = ", ".join(FOOD_POLICIES.keys())
        raise KeyError(f"Unknown food policy '{name}'. Valid: {valid}")
    return FOOD_POLICIES[name](**kwargs)
