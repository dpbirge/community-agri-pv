# Crop management policies for Community Agri-PV simulation
# Layer 2: Design configuration
#
# Three policies for comparative testing:
# - FixedSchedule: Apply full standard irrigation demand every day
# - DeficitIrrigation: Deliberately apply less water than full demand to save water
# - WeatherAdaptive: Adjust irrigation based on temperature conditions

from dataclasses import dataclass, field


@dataclass
class CropPolicyContext:
    """Input context for crop management decisions.

    Args:
        crop_name: Name of the crop
        growth_stage: Current growth stage ("initial", "development", "mid_season", "late_season")
        days_since_planting: Days since crop was planted
        total_growing_days: Total days in the growing cycle
        base_demand_m3: Standard irrigation demand for today (m3)
        water_stress_ratio: Cumulative water received / expected water (0-1)
        soil_moisture_estimate: Rough soil moisture estimate 0-1 (unused for now)
        temperature_c: Ambient temperature in Celsius
        available_water_m3: How much water is available today (m3)
    """
    crop_name: str = ""
    growth_stage: str = ""
    days_since_planting: int = 0
    total_growing_days: int = 0
    base_demand_m3: float = 0.0
    water_stress_ratio: float = 1.0
    soil_moisture_estimate: float = 0.5
    temperature_c: float = 25.0
    available_water_m3: float = float("inf")


@dataclass
class CropDecision:
    """Output from crop management decision.

    Args:
        adjusted_demand_m3: How much water to request (m3)
        demand_multiplier: Multiplier applied to base demand (for tracking)
        priority: Crop priority (higher = more important to water)
        decision_reason: Human-readable explanation of the decision
        policy_name: Name of the policy that made this decision
    """
    adjusted_demand_m3: float = 0.0
    demand_multiplier: float = 1.0
    priority: float = 1.0
    decision_reason: str = ""
    policy_name: str = ""


class BaseCropPolicy:
    """Base class for crop management policies."""

    name = "base"

    def decide(self, ctx: CropPolicyContext) -> CropDecision:
        raise NotImplementedError("Subclasses must implement decide()")

    def get_parameters(self) -> dict:
        return {}

    def describe(self) -> str:
        return f"{self.name}: {self.__class__.__doc__}"


class FixedSchedule(BaseCropPolicy):
    """Apply full standard irrigation demand every day, regardless of conditions."""

    name = "fixed_schedule"

    def decide(self, ctx: CropPolicyContext) -> CropDecision:
        return CropDecision(
            adjusted_demand_m3=ctx.base_demand_m3,
            demand_multiplier=1.0,
            priority=1.0,
            decision_reason="Fixed schedule: full irrigation demand",
            policy_name="fixed_schedule",
        )

    def describe(self) -> str:
        return "fixed_schedule: Apply full irrigation demand on a fixed daily schedule"


class DeficitIrrigation(BaseCropPolicy):
    """Apply controlled water deficit during less sensitive growth stages to save water."""

    name = "deficit_irrigation"

    def __init__(self, deficit_fraction: float = 0.80):
        self.deficit_fraction = deficit_fraction

    def decide(self, ctx: CropPolicyContext) -> CropDecision:
        # Apply deficit during mid-season when crops are more tolerant
        if ctx.growth_stage == "mid_season":
            multiplier = self.deficit_fraction
            reason = f"Deficit irrigation at {self.deficit_fraction:.0%} during mid-season"
        elif ctx.growth_stage == "late_season":
            multiplier = self.deficit_fraction * 0.9  # Even less in late season
            reason = f"Deficit irrigation at {self.deficit_fraction * 0.9:.0%} during late season"
        else:
            # Full water during initial establishment and development
            multiplier = 1.0
            reason = f"Full irrigation during {ctx.growth_stage}"

        return CropDecision(
            adjusted_demand_m3=ctx.base_demand_m3 * multiplier,
            demand_multiplier=multiplier,
            priority=1.0,
            decision_reason=reason,
            policy_name="deficit_irrigation",
        )

    def get_parameters(self) -> dict:
        return {"deficit_fraction": self.deficit_fraction}

    def describe(self) -> str:
        return (
            f"deficit_irrigation: Apply {self.deficit_fraction * 100:.0f}% of full demand "
            f"in mid/late season, full demand during establishment and development"
        )


class WeatherAdaptive(BaseCropPolicy):
    """Adjust irrigation based on temperature: more water on hot days, less on cool days."""

    name = "weather_adaptive"

    def decide(self, ctx: CropPolicyContext) -> CropDecision:
        # Increase water on very hot days, reduce on cooler days
        if ctx.temperature_c > 40:
            multiplier = 1.15  # 15% extra on extreme heat days
            reason = f"Heat stress adjustment: +15% (T={ctx.temperature_c:.0f}\u00b0C)"
        elif ctx.temperature_c > 35:
            multiplier = 1.05  # 5% extra on hot days
            reason = f"Warm day adjustment: +5% (T={ctx.temperature_c:.0f}\u00b0C)"
        elif ctx.temperature_c < 20:
            multiplier = 0.85  # 15% less on cool days
            reason = f"Cool day adjustment: -15% (T={ctx.temperature_c:.0f}\u00b0C)"
        else:
            multiplier = 1.0
            reason = f"Normal irrigation (T={ctx.temperature_c:.0f}\u00b0C)"

        return CropDecision(
            adjusted_demand_m3=ctx.base_demand_m3 * multiplier,
            demand_multiplier=multiplier,
            priority=1.0,
            decision_reason=reason,
            policy_name="weather_adaptive",
        )

    def describe(self) -> str:
        return "weather_adaptive: Temperature-based irrigation adjustment (+15% above 40\u00b0C, -15% below 20\u00b0C)"


# --- Registry and factory ---

CROP_POLICIES = {
    "fixed_schedule": FixedSchedule,
    "deficit_irrigation": DeficitIrrigation,
    "weather_adaptive": WeatherAdaptive,
}


def get_crop_policy(name, **kwargs):
    """Get a crop policy instance by name.

    Args:
        name: Policy name as string (e.g., "fixed_schedule")
        **kwargs: Parameters to pass to policy constructor

    Returns:
        Instantiated policy object

    Raises:
        ValueError: If policy name not found
    """
    if name not in CROP_POLICIES:
        raise ValueError(
            f"Unknown crop policy: {name}. Available: {list(CROP_POLICIES.keys())}"
        )
    return CROP_POLICIES[name](**kwargs)
