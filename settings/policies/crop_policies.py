# Crop management policies for Community Agri-PV simulation
# Layer 2: Design configuration
#
# Stubs for future implementation

from dataclasses import dataclass


@dataclass
class CropPolicyContext:
    """Input context for crop management decisions.

    Args:
        crop_name: Name of the crop
        growth_stage: Current growth stage (establishment, vegetative, flowering, yield_formation, ripening)
        days_since_planting: Days since crop was planted
        current_water_stress: Water stress factor (0-1, 0=no stress)
        soil_moisture_pct: Current soil moisture percentage
        weather_forecast_days: Number of days of weather forecast available
    """
    crop_name: str
    growth_stage: str
    days_since_planting: int
    current_water_stress: float
    soil_moisture_pct: float
    weather_forecast_days: int


@dataclass
class CropDecision:
    """Output from crop management decision.

    Args:
        irrigation_multiplier: Multiplier on base irrigation demand (0.5-1.5)
        harvest_now: Whether to harvest immediately
        abandon_crop: Whether to abandon crop due to stress
        notes: Decision rationale
    """
    irrigation_multiplier: float
    harvest_now: bool
    abandon_crop: bool
    notes: str


class BaseCropPolicy:
    """Base class for crop management policies."""

    name = "base"

    def decide(self, ctx: CropPolicyContext) -> CropDecision:
        raise NotImplementedError("Crop policy implementation pending")

    def get_parameters(self) -> dict:
        return {}

    def describe(self) -> str:
        return f"{self.name}: {self.__class__.__doc__}"


class FixedSchedule(BaseCropPolicy):
    """Follow fixed irrigation schedule regardless of conditions."""

    name = "fixed_schedule"

    def decide(self, ctx: CropPolicyContext) -> CropDecision:
        raise NotImplementedError("Crop policy implementation pending")

    def describe(self) -> str:
        return "fixed_schedule: Irrigation based on calendar schedule"


class DeficitIrrigation(BaseCropPolicy):
    """Apply controlled water deficit during less sensitive growth stages."""

    name = "deficit_irrigation"

    def __init__(self, deficit_fraction: float = 0.80):
        self.deficit_fraction = deficit_fraction

    def decide(self, ctx: CropPolicyContext) -> CropDecision:
        raise NotImplementedError("Crop policy implementation pending")

    def get_parameters(self) -> dict:
        return {"deficit_fraction": self.deficit_fraction}

    def describe(self) -> str:
        return f"deficit_irrigation: Apply {self.deficit_fraction*100:.0f}% of full demand in non-critical stages"


class WeatherAdaptive(BaseCropPolicy):
    """Adjust irrigation based on weather forecast (reduce before rain, increase before heat)."""

    name = "weather_adaptive"

    def decide(self, ctx: CropPolicyContext) -> CropDecision:
        raise NotImplementedError("Crop policy implementation pending")

    def describe(self) -> str:
        return "weather_adaptive: Forecast-based irrigation adjustment"
