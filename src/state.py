# State management for Water Simulation MVP
# Layer 3: Simulation Engine
#
# Dataclasses for tracking simulation state across daily time steps.
# State is updated immutably - new state objects created each day.

from dataclasses import dataclass, field
from datetime import date, timedelta


@dataclass
class CropState:
    """State for a single crop planting on a farm.

    Tracks water use and yield for one crop from planting to harvest.
    """
    crop_name: str
    planting_date: date
    harvest_date: date
    area_ha: float
    expected_yield_kg_per_ha: float

    # Accumulated values during growing season
    cumulative_water_m3: float = 0.0
    harvest_yield_kg: float = 0.0
    is_harvested: bool = False

    def __post_init__(self):
        # Calculate expected total yield
        self.expected_total_yield_kg = self.expected_yield_kg_per_ha * self.area_ha


@dataclass
class FarmState:
    """State for a single farm during simulation.

    Tracks all crops and accumulated water usage/costs.
    """
    farm_id: str
    farm_name: str
    area_ha: float
    water_policy_name: str
    crops: list  # List of CropState

    # Accumulated values
    cumulative_groundwater_m3: float = 0.0
    cumulative_municipal_m3: float = 0.0
    cumulative_water_cost_usd: float = 0.0
    cumulative_yield_kg: float = 0.0

    # Daily tracking for metrics
    daily_water_records: list = field(default_factory=list)

    def active_crops(self, current_date):
        """Return list of crops that are currently growing (not yet harvested)."""
        return [c for c in self.crops if not c.is_harvested and c.planting_date <= current_date]

    def total_water_m3(self):
        """Total water used by this farm."""
        return self.cumulative_groundwater_m3 + self.cumulative_municipal_m3


@dataclass
class DailyWaterRecord:
    """Record of daily water allocation for a farm."""
    date: date
    demand_m3: float
    groundwater_m3: float
    municipal_m3: float
    cost_usd: float
    energy_kwh: float


@dataclass
class YearlyFarmMetrics:
    """Accumulated metrics for one farm for one year."""
    year: int
    farm_id: str
    farm_name: str
    water_policy: str

    total_water_m3: float = 0.0
    groundwater_m3: float = 0.0
    municipal_m3: float = 0.0
    total_yield_kg: float = 0.0
    total_water_cost_usd: float = 0.0

    # Per-crop tracking
    crop_water_m3: dict = field(default_factory=dict)  # {crop_name: m3}
    crop_yield_kg: dict = field(default_factory=dict)  # {crop_name: kg}


@dataclass
class SimulationState:
    """Top-level state for the entire simulation."""
    current_date: date
    start_date: date
    end_date: date
    farms: list  # List of FarmState

    # Yearly metrics snapshots (populated at year boundaries)
    yearly_metrics: list = field(default_factory=list)  # List of YearlyFarmMetrics

    def current_year(self):
        """Return current simulation year."""
        return self.current_date.year

    def is_year_boundary(self, prev_date):
        """Check if we crossed a year boundary from prev_date to current_date."""
        return prev_date.year != self.current_date.year

    def is_simulation_complete(self):
        """Check if simulation has reached end date."""
        return self.current_date > self.end_date

    def advance_day(self):
        """Advance simulation by one day."""
        self.current_date += timedelta(days=1)


def initialize_crop_state(farm_crop_config, farm_area_ha, simulation_year, data_loader):
    """Initialize CropState from farm crop configuration.

    Args:
        farm_crop_config: FarmCropConfig from scenario (name, area_fraction, planting_date, percent_planted)
        farm_area_ha: Total farm area in hectares
        simulation_year: Year to construct full planting date
        data_loader: SimulationDataLoader for yield lookup

    Returns:
        CropState or None if yield data not available for this year
    """
    # Construct full planting date from MM-DD format and year
    month, day = map(int, farm_crop_config.planting_date.split("-"))
    planting_date = date(simulation_year, month, day)

    # Calculate planted area
    planted_area = farm_area_ha * farm_crop_config.area_fraction * farm_crop_config.percent_planted

    # Look up yield and harvest date from precomputed data
    yield_info = data_loader.get_yield_info(farm_crop_config.name, planting_date)
    if yield_info is None:
        # No yield data for this planting date - skip this crop
        return None

    return CropState(
        crop_name=farm_crop_config.name,
        planting_date=planting_date,
        harvest_date=yield_info["harvest_date"],
        area_ha=planted_area,
        expected_yield_kg_per_ha=yield_info["yield_kg_per_ha"],
    )


def initialize_farm_state(farm_config, simulation_year, data_loader):
    """Initialize FarmState from scenario farm configuration.

    Args:
        farm_config: Farm from scenario (id, name, area_ha, crops, water_policy)
        simulation_year: Year to construct planting dates
        data_loader: SimulationDataLoader for yield lookup

    Returns:
        FarmState
    """
    crops = []
    for crop_config in farm_config.crops:
        crop_state = initialize_crop_state(
            crop_config, farm_config.area_ha, simulation_year, data_loader
        )
        if crop_state is not None:
            crops.append(crop_state)

    return FarmState(
        farm_id=farm_config.id,
        farm_name=farm_config.name,
        area_ha=farm_config.area_ha,
        water_policy_name=farm_config.water_policy.name,
        crops=crops,
    )


def initialize_simulation_state(scenario, data_loader):
    """Initialize full simulation state from scenario.

    Args:
        scenario: Loaded Scenario object
        data_loader: SimulationDataLoader

    Returns:
        SimulationState
    """
    start_year = scenario.metadata.start_date.year

    farms = []
    for farm_config in scenario.farms:
        farm_state = initialize_farm_state(farm_config, start_year, data_loader)
        farms.append(farm_state)

    return SimulationState(
        current_date=scenario.metadata.start_date,
        start_date=scenario.metadata.start_date,
        end_date=scenario.metadata.end_date,
        farms=farms,
    )


def reinitialize_farm_crops_for_year(farm_state, farm_config, year, data_loader):
    """Re-initialize crops for a new simulation year.

    Called at year boundary to create new crop plantings.

    Args:
        farm_state: Existing FarmState to update
        farm_config: Farm from scenario
        year: New year for crop plantings
        data_loader: SimulationDataLoader
    """
    new_crops = []
    for crop_config in farm_config.crops:
        crop_state = initialize_crop_state(
            crop_config, farm_config.area_ha, year, data_loader
        )
        if crop_state is not None:
            new_crops.append(crop_state)

    farm_state.crops = new_crops
