# State management for Water Simulation MVP
# Layer 3: Simulation Engine
#
# Dataclasses for tracking simulation state across daily time steps.
# State is updated in-place during each daily simulation step.

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional


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

    # Expected total water demand over the full growing season (m3)
    # Computed at initialization by summing daily irrigation demand × area
    expected_total_water_m3: float = 0.0

    # Accumulated values during growing season
    cumulative_water_m3: float = 0.0
    harvest_yield_kg: float = 0.0
    harvest_revenue_usd: float = 0.0
    is_harvested: bool = False

    # Food processing tracking (populated at harvest by process_harvests)
    processing_allocation: dict = None  # {pathway: fraction} from policy
    processed_output_kg: float = 0.0  # Total processed product weight (after weight loss)
    fresh_revenue_usd: float = 0.0  # Revenue from fresh sales only
    processed_revenue_usd: float = 0.0  # Revenue from processed pathways
    post_harvest_loss_kg: float = 0.0  # Total post-harvest loss (fresh + processing waste)

    def __post_init__(self):
        # Calculate expected total yield
        self.expected_total_yield_kg = self.expected_yield_kg_per_ha * self.area_ha


@dataclass
class MonthlyConsumptionTracker:
    """Tracks monthly consumption for tiered pricing calculations.

    Resets at the beginning of each month to enable tier-based cost
    calculations that depend on cumulative monthly consumption.

    Args:
        current_month: Month being tracked (1-12)
        current_year: Year being tracked
        water_m3: Cumulative water consumption this month
        groundwater_m3: Cumulative groundwater consumption this month (for quota policies)
        electricity_kwh: Cumulative electricity consumption this month
    """
    current_month: int
    current_year: int
    water_m3: float = 0.0
    groundwater_m3: float = 0.0
    electricity_kwh: float = 0.0


@dataclass
class AquiferState:
    """Tracks aquifer depletion from groundwater extraction.

    Monitors cumulative extraction against the exploitable volume and
    natural recharge rate to estimate long-term aquifer sustainability.
    Initialized once from scenario config; updated daily as groundwater
    is pumped.

    The max_drawdown_m field enables pumping energy feedback: as the aquifer
    depletes, the effective pumping head increases linearly with the fraction
    depleted, making pumping progressively more expensive over multi-year
    simulations. See calculations.md Section 2 "Aquifer Drawdown Feedback".
    """
    exploitable_volume_m3: float
    recharge_rate_m3_yr: float
    cumulative_extraction_m3: float = 0.0
    max_drawdown_m: float = 0.0  # Maximum drawdown at full depletion

    def record_extraction(self, extraction_m3: float):
        """Record daily groundwater extraction."""
        self.cumulative_extraction_m3 += extraction_m3

    def get_net_depletion_m3(self, years_elapsed: float) -> float:
        """Net depletion = total extracted - total recharged."""
        total_recharge = self.recharge_rate_m3_yr * years_elapsed
        return max(0.0, self.cumulative_extraction_m3 - total_recharge)

    def get_years_remaining(self, years_elapsed: float) -> float:
        """Estimate years until aquifer is depleted at current extraction rate."""
        if years_elapsed <= 0:
            return float('inf')
        annual_extraction = self.cumulative_extraction_m3 / years_elapsed
        net_annual_depletion = annual_extraction - self.recharge_rate_m3_yr
        if net_annual_depletion <= 0:
            return float('inf')  # Extraction is sustainable
        remaining = self.exploitable_volume_m3 - self.get_net_depletion_m3(years_elapsed)
        if remaining <= 0:
            return 0.0
        return remaining / net_annual_depletion

    def get_effective_head_m(self, base_well_depth_m: float) -> float:
        """Calculate effective pumping head including drawdown.

        Uses linearized drawdown model from calculations.md:
            Fraction_depleted = cumulative_extraction / exploitable_volume
            Drawdown_m = max_drawdown_m * Fraction_depleted
            Effective_head = well_depth_m + Drawdown_m

        If max_drawdown_m is 0 or exploitable volume is 0, returns the
        base well depth unchanged (backward-compatible behavior).

        Args:
            base_well_depth_m: Static well depth from config (m)

        Returns:
            Effective pumping head in meters
        """
        if self.exploitable_volume_m3 <= 0 or self.max_drawdown_m <= 0:
            return base_well_depth_m

        fraction_depleted = min(1.0, self.cumulative_extraction_m3 / self.exploitable_volume_m3)
        drawdown_m = self.max_drawdown_m * fraction_depleted
        return base_well_depth_m + drawdown_m

    def get_current_drawdown_m(self) -> float:
        """Get current drawdown in meters (0.0 if drawdown feedback disabled).

        Returns:
            Current drawdown in meters
        """
        if self.exploitable_volume_m3 <= 0 or self.max_drawdown_m <= 0:
            return 0.0
        fraction_depleted = min(1.0, self.cumulative_extraction_m3 / self.exploitable_volume_m3)
        return self.max_drawdown_m * fraction_depleted


@dataclass
class WaterStorageState:
    """Tracks water storage level between treatment and irrigation.

    Community-level shared infrastructure: one treatment plant serves all farms.
    Per architecture spec (calculations.md section 2.5):
        Storage(t+1) = Storage(t) + Inflow(t) - Outflow(t)
        Constraints: 0 <= Storage(t) <= capacity_m3

    In the MVP, treated water is allocated same-day (no temporal buffering),
    so inflow == outflow and storage level stays near its initial value.
    This class provides the tracking infrastructure for future enhancement
    where treatment and irrigation can be decoupled across days.
    """
    capacity_m3: float
    current_level_m3: float = 0.0

    # Daily tracking for metrics: list of dicts with date, level, inflow, outflow
    daily_levels: list = field(default_factory=list)

    def add_inflow(self, inflow_m3: float) -> float:
        """Add treated water to storage. Returns actual amount stored (may be limited by capacity)."""
        space_available = self.capacity_m3 - self.current_level_m3
        actual_stored = min(inflow_m3, space_available)
        self.current_level_m3 += actual_stored
        return actual_stored

    def draw_outflow(self, requested_m3: float) -> float:
        """Draw water from storage for irrigation. Returns actual amount drawn.

        In MVP mode, if storage would go negative (due to same-day inflow==outflow
        ordering), the draw is capped at current level. The caller should not block
        delivery based on the return value — this is a soft tracking constraint.
        """
        actual_drawn = min(requested_m3, self.current_level_m3)
        self.current_level_m3 -= actual_drawn
        return actual_drawn

    def record_daily(self, current_date, inflow_m3, outflow_m3, household_m3=0.0, community_building_m3=0.0):
        """Record daily storage state for metrics tracking.

        Args:
            current_date: Simulation date
            inflow_m3: Water treated and added to storage (irrigation + community needs)
            outflow_m3: Water distributed from storage (irrigation + community needs)
            household_m3: Household water consumption (subset of outflow)
            community_building_m3: Community building water consumption (subset of outflow)
        """
        self.daily_levels.append({
            "date": current_date,
            "storage_level_m3": self.current_level_m3,
            "inflow_m3": inflow_m3,
            "outflow_m3": outflow_m3,
            "irrigation_m3": outflow_m3 - household_m3 - community_building_m3,
            "household_m3": household_m3,
            "community_building_m3": community_building_m3,
            "utilization_pct": (
                self.current_level_m3 / self.capacity_m3 * 100
                if self.capacity_m3 > 0 else 0.0
            ),
        })


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

    # Accumulated values (yearly reset)
    cumulative_groundwater_m3: float = 0.0
    cumulative_municipal_m3: float = 0.0
    cumulative_water_cost_usd: float = 0.0
    cumulative_yield_kg: float = 0.0
    cumulative_crop_revenue_usd: float = 0.0

    # Food processing accumulators (yearly reset)
    cumulative_fresh_revenue_usd: float = 0.0
    cumulative_processed_revenue_usd: float = 0.0
    cumulative_processed_output_kg: float = 0.0
    cumulative_post_harvest_loss_kg: float = 0.0

    # Monthly consumption tracking for tiered pricing
    monthly_consumption: MonthlyConsumptionTracker = None

    # Daily tracking for metrics
    daily_water_records: list = field(default_factory=list)

    def active_crops(self, current_date):
        """Return list of crops that are currently growing (not yet harvested)."""
        return [c for c in self.crops if not c.is_harvested and c.planting_date <= current_date]

    def total_water_m3(self):
        """Total water used by this farm."""
        return self.cumulative_groundwater_m3 + self.cumulative_municipal_m3

    def get_monthly_water_m3(self, current_date):
        """Get cumulative water consumption for the current month.

        Returns 0.0 if tracker not initialized or month has changed.
        """
        if self.monthly_consumption is None:
            return 0.0
        if (self.monthly_consumption.current_month != current_date.month or
            self.monthly_consumption.current_year != current_date.year):
            return 0.0
        return self.monthly_consumption.water_m3

    def get_monthly_electricity_kwh(self, current_date):
        """Get cumulative electricity consumption for the current month.

        Returns 0.0 if tracker not initialized or month has changed.
        """
        if self.monthly_consumption is None:
            return 0.0
        if (self.monthly_consumption.current_month != current_date.month or
            self.monthly_consumption.current_year != current_date.year):
            return 0.0
        return self.monthly_consumption.electricity_kwh

    def get_monthly_groundwater_m3(self, current_date):
        """Get cumulative groundwater consumption for the current month.

        Used by quota policies to enforce monthly groundwater limits.
        Returns 0.0 if tracker not initialized or month has changed.
        """
        if self.monthly_consumption is None:
            return 0.0
        if (self.monthly_consumption.current_month != current_date.month or
            self.monthly_consumption.current_year != current_date.year):
            return 0.0
        return self.monthly_consumption.groundwater_m3

    def update_monthly_consumption(self, current_date, water_m3=0.0, groundwater_m3=0.0, electricity_kwh=0.0):
        """Update monthly consumption tracker, resetting if month changed.

        Args:
            current_date: Current simulation date
            water_m3: Total water consumed today
            groundwater_m3: Groundwater consumed today (for quota tracking)
            electricity_kwh: Electricity consumed today
        """
        if self.monthly_consumption is None:
            self.monthly_consumption = MonthlyConsumptionTracker(
                current_month=current_date.month,
                current_year=current_date.year,
            )

        # Reset if month changed
        if (self.monthly_consumption.current_month != current_date.month or
            self.monthly_consumption.current_year != current_date.year):
            self.monthly_consumption = MonthlyConsumptionTracker(
                current_month=current_date.month,
                current_year=current_date.year,
            )

        # Add today's consumption
        self.monthly_consumption.water_m3 += water_m3
        self.monthly_consumption.groundwater_m3 += groundwater_m3
        self.monthly_consumption.electricity_kwh += electricity_kwh


@dataclass
class DailyWaterRecord:
    """Record of daily water allocation for a farm.

    Includes decision metadata to track why allocations were made.
    """
    date: date
    demand_m3: float
    groundwater_m3: float
    municipal_m3: float
    cost_usd: float
    energy_kwh: float
    energy_cost_usd: float = 0.0  # Energy cost for water treatment (kWh × price)
    # Decision metadata
    decision_reason: Optional[str] = None
    gw_cost_per_m3: Optional[float] = None
    muni_cost_per_m3: Optional[float] = None
    constraint_hit: Optional[str] = None
    # Tier pricing metadata
    cumulative_monthly_water_m3: Optional[float] = None
    water_tier: Optional[int] = None
    tier_effective_rate: Optional[float] = None


@dataclass
class DailyEnergyRecord:
    """Record of daily energy balance for the community.

    One record per simulation day, capturing the dispatch results
    from the merit-order energy system (PV/wind → battery → grid → generator).
    """
    date: date
    pv_generation_kwh: float = 0.0
    wind_generation_kwh: float = 0.0
    total_demand_kwh: float = 0.0
    battery_charge_kwh: float = 0.0
    battery_discharge_kwh: float = 0.0
    grid_import_kwh: float = 0.0
    grid_export_kwh: float = 0.0
    generator_kwh: float = 0.0
    generator_fuel_L: float = 0.0
    curtailment_kwh: float = 0.0
    battery_soc: float = 0.0


@dataclass
class EnergyState:
    """Community-level energy system state.

    Tracks PV/wind generation, battery storage, backup generator,
    and daily dispatch results for the merit-order energy system.

    The energy system is shared community infrastructure — one dispatch
    serves all farms. Battery SOC persists between days; accumulators
    reset at year boundaries while daily_energy_records are preserved
    for full simulation history.
    """
    # PV/Wind capacities
    pv_capacity_kw: float = 0.0
    wind_capacity_kw: float = 0.0

    # Battery parameters
    battery_capacity_kwh: float = 0.0
    battery_soc: float = 0.5  # State of charge (0-1), starts at 50%
    battery_soc_min: float = 0.10
    battery_soc_max: float = 0.90
    battery_charge_efficiency: float = 0.95
    battery_discharge_efficiency: float = 0.95

    # Generator parameters
    generator_capacity_kw: float = 0.0
    generator_min_load_fraction: float = 0.30
    generator_sfc_a: float = 0.06  # No-load fuel coefficient (L/kWh)
    generator_sfc_b: float = 0.20  # Incremental fuel coefficient (L/kWh)

    # Yearly tracking accumulators (reset at year boundaries)
    cumulative_pv_kwh: float = 0.0
    cumulative_wind_kwh: float = 0.0
    cumulative_grid_import_kwh: float = 0.0
    cumulative_grid_export_kwh: float = 0.0
    cumulative_generator_kwh: float = 0.0
    cumulative_generator_fuel_L: float = 0.0
    cumulative_battery_charge_kwh: float = 0.0
    cumulative_battery_discharge_kwh: float = 0.0
    cumulative_curtailment_kwh: float = 0.0

    # Daily records for metrics (preserved across year boundaries)
    daily_energy_records: list = field(default_factory=list)


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
    total_crop_revenue_usd: float = 0.0

    # Per-crop tracking
    crop_water_m3: dict = field(default_factory=dict)  # {crop_name: m3}
    crop_yield_kg: dict = field(default_factory=dict)  # {crop_name: kg}
    crop_revenue_usd: dict = field(default_factory=dict)  # {crop_name: usd}
    energy_cost_usd: float = 0.0
    diesel_cost_usd: float = 0.0
    fertilizer_cost_usd: float = 0.0
    labor_cost_usd: float = 0.0
    total_operating_cost_usd: float = 0.0

    # Food processing tracking
    fresh_revenue_usd: float = 0.0
    processed_revenue_usd: float = 0.0
    processed_output_kg: float = 0.0
    post_harvest_loss_kg: float = 0.0


@dataclass
class EconomicState:
    """Tracks community-level financial state across the simulation.

    Initialized once at simulation start with pre-computed annual infrastructure
    costs (from estimate_infrastructure_costs). Updated at each year boundary
    with revenue and operating costs from farm states.
    """
    cash_reserves_usd: float = 0.0
    cumulative_revenue_usd: float = 0.0
    cumulative_operating_cost_usd: float = 0.0
    cumulative_infrastructure_cost_usd: float = 0.0
    cumulative_debt_service_usd: float = 0.0

    # Pre-computed annual costs (set at initialization, constant each year)
    annual_infrastructure_costs: dict = field(default_factory=dict)
    total_annual_infrastructure_cost_usd: float = 0.0
    total_annual_debt_service_usd: float = 0.0


@dataclass
class SimulationState:
    """Top-level state for the entire simulation."""
    current_date: date
    start_date: date
    end_date: date
    farms: list  # List of FarmState

    # Community-level water storage (shared infrastructure between treatment and irrigation)
    water_storage: Optional[WaterStorageState] = None

    # Yearly metrics snapshots (populated at year boundaries)
    yearly_metrics: list = field(default_factory=list)  # List of YearlyFarmMetrics

    # Aquifer depletion tracking (initialized from scenario groundwater config)
    aquifer: Optional[AquiferState] = None

    # Community-level economic state (infrastructure financing, cash reserves)
    economic: Optional['EconomicState'] = None

    # Community-level energy system state (PV, wind, battery, generator dispatch)
    energy: Optional[EnergyState] = None

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


def initialize_crop_state(farm_crop_config, farm_area_ha, simulation_year, data_loader, yield_factor=1.0):
    """Initialize CropState from farm crop configuration.

    Args:
        farm_crop_config: FarmCropConfig from scenario (name, area_fraction, planting_date, percent_planted)
        farm_area_ha: Total farm area in hectares
        simulation_year: Year to construct full planting date
        data_loader: SimulationDataLoader for yield and irrigation lookup
        yield_factor: Farm management quality factor (from scenario config),
            multiplies expected yield. Default 1.0 (no adjustment).

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

    # Apply yield_factor to expected yield (farm management quality)
    adjusted_yield_kg_per_ha = yield_info["yield_kg_per_ha"] * yield_factor

    crop_state = CropState(
        crop_name=farm_crop_config.name,
        planting_date=planting_date,
        harvest_date=yield_info["harvest_date"],
        area_ha=planted_area,
        expected_yield_kg_per_ha=adjusted_yield_kg_per_ha,
    )

    # Compute expected total water demand over the full growing season.
    # Sum daily irrigation demand from planting to harvest, scaled by area.
    total_water_m3 = 0.0
    current_day = planting_date
    while current_day <= crop_state.harvest_date:
        irr_per_ha = data_loader.get_irrigation_m3_per_ha(
            farm_crop_config.name, planting_date, current_day
        )
        total_water_m3 += irr_per_ha * planted_area
        current_day += timedelta(days=1)
    crop_state.expected_total_water_m3 = total_water_m3

    return crop_state


def _check_planting_overlap(crops, farm_id):
    """Check that no two plantings of the same crop overlap in time.

    Two plantings overlap if one's growing season [planting_date, harvest_date]
    intersects another's. This would mean the same land is double-booked.

    Raises:
        ValueError: If overlapping plantings are found.
    """
    from collections import defaultdict
    by_name = defaultdict(list)
    for crop in crops:
        by_name[crop.crop_name].append(crop)

    for crop_name, plantings in by_name.items():
        sorted_plantings = sorted(plantings, key=lambda c: c.planting_date)
        for i in range(len(sorted_plantings) - 1):
            current = sorted_plantings[i]
            next_planting = sorted_plantings[i + 1]
            if current.harvest_date >= next_planting.planting_date:
                raise ValueError(
                    f"Farm {farm_id}: overlapping {crop_name} plantings — "
                    f"{current.planting_date} harvests {current.harvest_date}, "
                    f"but next planting starts {next_planting.planting_date}"
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
            crop_config, farm_config.area_ha, simulation_year, data_loader,
            yield_factor=farm_config.yield_factor,
        )
        if crop_state is not None:
            crops.append(crop_state)

    _check_planting_overlap(crops, farm_config.id)

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
    Appends new crops to existing crops list to preserve historical data.

    Args:
        farm_state: Existing FarmState to update
        farm_config: Farm from scenario
        year: New year for crop plantings
        data_loader: SimulationDataLoader
    """
    new_crops = []
    for crop_config in farm_config.crops:
        crop_state = initialize_crop_state(
            crop_config, farm_config.area_ha, year, data_loader,
            yield_factor=farm_config.yield_factor,
        )
        if crop_state is not None:
            new_crops.append(crop_state)

    # Append new crops to preserve historical crop data
    farm_state.crops.extend(new_crops)
