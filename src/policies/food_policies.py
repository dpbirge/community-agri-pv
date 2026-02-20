# Food processing allocation policies for Community Agri-PV simulation
# Layer 2: Design configuration
#
# Four policies for comparative testing:
# - AllFresh: 100% to fresh sale (current behavior, backward compatible)
# - MaximizeStorage: Maximize shelf life by processing most of harvest
# - Balanced: Mix of fresh and processed per calculations.md
# - MarketResponsive: More processing when fresh prices are low

import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml


# Fallback reference prices (USD/kg) used when historical data is unavailable
_FALLBACK_REFERENCE_PRICES = {
    "tomato": 0.30,
    "potato": 0.25,
    "onion": 0.20,
    "kale": 0.40,
    "cucumber": 0.35,
}


def _get_project_root():
    """Get project root directory (parent of src/policies/)."""
    return Path(__file__).parent.parent.parent


def _load_reference_prices_from_registry():
    """Compute median farmgate prices from historical crop price data.

    Reads the data registry to find crop price CSV paths, loads each file,
    and computes the median price per crop. Prefers the 'usd_per_kg_farmgate'
    column (research data) and falls back to 'usd_per_kg' (toy/wholesale data).

    Returns:
        Dict mapping crop name to median price in USD/kg.
    """
    if hasattr(_load_reference_prices_from_registry, "_cache"):
        return _load_reference_prices_from_registry._cache

    project_root = _get_project_root()
    registry_path = project_root / "settings" / "data_registry.yaml"

    try:
        with open(registry_path, "r") as f:
            registry = yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError) as e:
        print(
            f"WARNING: Could not load data registry ({e}); "
            "using fallback reference prices",
            file=sys.stderr,
        )
        _load_reference_prices_from_registry._cache = _FALLBACK_REFERENCE_PRICES
        return _FALLBACK_REFERENCE_PRICES

    prices_section = registry.get("prices_crops", {})
    if not prices_section:
        print(
            "WARNING: No 'prices_crops' section in data registry; "
            "using fallback reference prices",
            file=sys.stderr,
        )
        _load_reference_prices_from_registry._cache = _FALLBACK_REFERENCE_PRICES
        return _FALLBACK_REFERENCE_PRICES

    ref_prices = {}
    for crop_name, rel_path in prices_section.items():
        filepath = project_root / rel_path
        try:
            df = pd.read_csv(filepath, comment="#")
            # Prefer farmgate column (research data), fall back to wholesale (toy data)
            if "usd_per_kg_farmgate" in df.columns:
                col = "usd_per_kg_farmgate"
            elif "usd_per_kg" in df.columns:
                col = "usd_per_kg"
            else:
                print(
                    f"WARNING: No recognized price column in {rel_path} "
                    f"(columns: {list(df.columns)}); "
                    f"using fallback for '{crop_name}'",
                    file=sys.stderr,
                )
                continue
            median_price = df[col].median()
            # TODO: Consider whether to use farmgate-adjusted wholesale
            # (e.g. wholesale * 0.55) when only wholesale data is available,
            # rather than raw wholesale median.
            ref_prices[crop_name] = float(median_price)
        except Exception as e:
            print(
                f"WARNING: Could not load price data for '{crop_name}' "
                f"from {rel_path} ({e}); using fallback",
                file=sys.stderr,
            )

    # Fill in any missing crops from fallback
    for crop_name, fallback_price in _FALLBACK_REFERENCE_PRICES.items():
        if crop_name not in ref_prices:
            print(
                f"WARNING: No historical price data for '{crop_name}'; "
                f"using fallback ${fallback_price:.2f}/kg",
                file=sys.stderr,
            )
            ref_prices[crop_name] = fallback_price

    _load_reference_prices_from_registry._cache = ref_prices
    return ref_prices


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

    def __post_init__(self):
        total = self.fresh_fraction + self.packaged_fraction + self.canned_fraction + self.dried_fraction
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"Processing fractions must sum to 1.0, got {total:.4f} "
                f"(fresh={self.fresh_fraction}, packaged={self.packaged_fraction}, "
                f"canned={self.canned_fraction}, dried={self.dried_fraction})"
            )


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

    Sends a small share to fresh sale (default 20%); the rest is split
    between dried (default 35%), canned (default 35%), and packaged
    (default 10%) for long-term storage. All fractions are configurable
    and must sum to 1.0.
    """

    name = "maximize_storage"

    def __init__(self, fresh_fraction=0.20, packaged_fraction=0.10,
                 canned_fraction=0.35, dried_fraction=0.35):
        self.fresh_fraction = fresh_fraction
        self.packaged_fraction = packaged_fraction
        self.canned_fraction = canned_fraction
        self.dried_fraction = dried_fraction

    def allocate(self, ctx: FoodProcessingContext) -> ProcessingAllocation:
        return ProcessingAllocation(
            fresh_fraction=self.fresh_fraction,
            packaged_fraction=self.packaged_fraction,
            canned_fraction=self.canned_fraction,
            dried_fraction=self.dried_fraction,
            policy_name="maximize_storage",
        )

    def get_parameters(self):
        return {
            "fresh_fraction": self.fresh_fraction,
            "packaged_fraction": self.packaged_fraction,
            "canned_fraction": self.canned_fraction,
            "dried_fraction": self.dried_fraction,
        }


class BalancedMix(BaseFoodPolicy):
    """Balanced mix of fresh and processed per calculations.md.

    Default: 50% fresh, 20% packaged, 15% canned, 15% dried. Provides
    a moderate level of value-add processing while keeping half the
    harvest for immediate fresh sale. All fractions are configurable
    and must sum to 1.0.
    """

    name = "balanced_mix"

    def __init__(self, fresh_fraction=0.50, packaged_fraction=0.20,
                 canned_fraction=0.15, dried_fraction=0.15):
        self.fresh_fraction = fresh_fraction
        self.packaged_fraction = packaged_fraction
        self.canned_fraction = canned_fraction
        self.dried_fraction = dried_fraction

    def allocate(self, ctx: FoodProcessingContext) -> ProcessingAllocation:
        return ProcessingAllocation(
            fresh_fraction=self.fresh_fraction,
            packaged_fraction=self.packaged_fraction,
            canned_fraction=self.canned_fraction,
            dried_fraction=self.dried_fraction,
            policy_name="balanced_mix",
        )

    def get_parameters(self):
        return {
            "fresh_fraction": self.fresh_fraction,
            "packaged_fraction": self.packaged_fraction,
            "canned_fraction": self.canned_fraction,
            "dried_fraction": self.dried_fraction,
        }


class MarketResponsive(BaseFoodPolicy):
    """Adjust processing mix based on current fresh prices.

    When fresh prices are below a configurable threshold (default 80%)
    of reference farmgate prices, shifts more harvest into processing
    (higher value-add pathways). When prices are normal or high, sells
    more fresh.

    Reference prices are median historical farmgate prices (USD/kg) derived
    from the crop price data registered in data_registry.yaml. Falls back
    to hardcoded values if historical data is unavailable.

    Both the low-price and normal-price split ratios are configurable.
    Each set of fractions must sum to 1.0.
    """

    name = "market_responsive"

    def __init__(self, price_threshold=0.80,
                 low_fresh=0.30, low_packaged=0.20, low_canned=0.25, low_dried=0.25,
                 normal_fresh=0.65, normal_packaged=0.15, normal_canned=0.10, normal_dried=0.10):
        self.price_threshold = price_threshold
        # Splits when fresh prices are low (below threshold)
        self.low_fresh = low_fresh
        self.low_packaged = low_packaged
        self.low_canned = low_canned
        self.low_dried = low_dried
        # Splits when fresh prices are normal/high
        self.normal_fresh = normal_fresh
        self.normal_packaged = normal_packaged
        self.normal_canned = normal_canned
        self.normal_dried = normal_dried

    @property
    def reference_prices(self):
        """Median farmgate prices (USD/kg) loaded lazily from historical data."""
        return _load_reference_prices_from_registry()

    def allocate(self, ctx: FoodProcessingContext) -> ProcessingAllocation:
        ref = self.reference_prices.get(ctx.crop_name, 0.30)

        if ctx.fresh_price_per_kg < ref * self.price_threshold:
            # Low prices — process more to capture value-add
            return ProcessingAllocation(
                fresh_fraction=self.low_fresh,
                packaged_fraction=self.low_packaged,
                canned_fraction=self.low_canned,
                dried_fraction=self.low_dried,
                policy_name="market_responsive",
            )
        else:
            # Normal/high prices — sell more fresh
            return ProcessingAllocation(
                fresh_fraction=self.normal_fresh,
                packaged_fraction=self.normal_packaged,
                canned_fraction=self.normal_canned,
                dried_fraction=self.normal_dried,
                policy_name="market_responsive",
            )

    def get_parameters(self):
        return {
            "price_threshold": self.price_threshold,
            "low_price_splits": {
                "fresh": self.low_fresh,
                "packaged": self.low_packaged,
                "canned": self.low_canned,
                "dried": self.low_dried,
            },
            "normal_price_splits": {
                "fresh": self.normal_fresh,
                "packaged": self.normal_packaged,
                "canned": self.normal_canned,
                "dried": self.normal_dried,
            },
        }


# Policy registry for lookup by name (as used in scenario YAML)
FOOD_POLICIES = {
    "all_fresh": AllFresh,
    "maximize_storage": MaximizeStorage,
    "preserve_maximum": MaximizeStorage,  # Alias
    "balanced_mix": BalancedMix,
    "balanced": BalancedMix,  # Alias
    "market_responsive": MarketResponsive,
}


def get_food_policy(name, **kwargs):
    """Get a food processing policy instance by name.

    Args:
        name: Policy name as string (e.g., "all_fresh", "balanced_mix")
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
