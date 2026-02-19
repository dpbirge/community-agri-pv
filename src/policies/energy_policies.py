# Energy dispatch policies for Community Agri-PV simulation
# Layer 2: Design configuration
#
# Three energy dispatch strategies that provide strategy parameters
# to the merit-order dispatch_energy() function in simulation.py:
#   - PvFirstBatteryGridDiesel: Renewable-first merit order (default)
#   - GridFirst: Grid-only, no renewables or battery
#   - CheapestEnergy: Dynamic cost comparison (LCOE vs grid price)

from dataclasses import dataclass


@dataclass
class EnergyPolicyContext:
    """Input context for energy dispatch decisions.

    Provides the policy with enough information to choose a dispatch
    strategy.  Built by the simulation loop before calling the policy.

    Args:
        total_demand_kwh: Total energy demand (irrigation, processing, housing, etc.)
        pv_available_kwh: PV generation available this period
        wind_available_kwh: Wind generation available this period
        battery_soc: Current battery state of charge (0-1 fraction)
        battery_capacity_kwh: Total battery capacity
        grid_price_per_kwh: Current grid electricity price (USD/kWh)
        diesel_price_per_L: Current diesel fuel price (USD/L)
        generator_capacity_kw: Backup generator nameplate capacity (kW)
        renewable_lcoe_per_kwh: Levelized cost of energy for renewables (USD/kWh),
            from scenario config (energy_pricing.renewable.lcoe_pv_usd_kwh)
    """
    total_demand_kwh: float = 0.0
    pv_available_kwh: float = 0.0
    wind_available_kwh: float = 0.0
    battery_soc: float = 0.0
    battery_capacity_kwh: float = 0.0
    grid_price_per_kwh: float = 0.0
    diesel_price_per_L: float = 0.0
    generator_capacity_kw: float = 0.0
    renewable_lcoe_per_kwh: float = 0.0


@dataclass
class EnergyAllocation:
    """Result of energy policy decision.

    Contains strategy parameters that guide the dispatch_energy()
    function in simulation.py.  The policies do NOT perform dispatch
    themselves — they return flags and thresholds that influence the
    merit-order algorithm.

    Args:
        use_renewables: Whether to use PV/wind generation
        use_battery: Whether to use battery charge/discharge
        use_grid: Whether to import from / export to grid
        use_generator: Whether to use backup diesel generator
        battery_reserve_pct: Minimum SOC to keep in reserve (0-1)
        max_grid_import_pct: Max fraction of demand from grid (1.0 = unlimited)
        prefer_grid_over_generator: Grid before generator in merit order?
        allow_grid_export: Can sell excess generation to grid?
        policy_name: Name of the policy that produced this allocation
        decision_reason: Human-readable explanation of the dispatch strategy
    """
    # Dispatch source flags
    use_renewables: bool = True
    use_battery: bool = True
    use_grid: bool = True
    use_generator: bool = True

    # Strategy parameters
    battery_reserve_pct: float = 0.10
    max_grid_import_pct: float = 1.0
    prefer_grid_over_generator: bool = True
    allow_grid_export: bool = True

    # Decision metadata
    policy_name: str = ""
    decision_reason: str = ""


class BaseEnergyPolicy:
    """Base class for energy dispatch policies."""

    name = "base"

    def allocate_energy(self, ctx: EnergyPolicyContext) -> EnergyAllocation:
        raise NotImplementedError("Subclasses must implement allocate_energy()")

    def get_parameters(self) -> dict:
        return {}

    def describe(self) -> str:
        return f"{self.name}: {self.__class__.__doc__}"


class PvFirstBatteryGridDiesel(BaseEnergyPolicy):
    """Energy dispatch priority: PV -> Wind -> Battery -> Grid -> Diesel.

    Prioritizes renewable energy, uses battery to smooth supply,
    grid as backup, generator as last resort.  Keeps a configurable
    battery reserve for evening / nighttime demand (default 20%).
    Allows grid export of surplus renewable generation.

    This is the default merit-order dispatch — it passes through with
    renewable-first priorities, matching the dispatch_energy() logic.

    Maps to scenario policy names: "all_renewable", "hybrid".
    """

    name = "pv_first_battery_grid_diesel"

    def __init__(self, battery_reserve_fraction=0.20):
        self.battery_reserve_fraction = battery_reserve_fraction

    def allocate_energy(self, ctx: EnergyPolicyContext) -> EnergyAllocation:
        return EnergyAllocation(
            use_renewables=True,
            use_battery=True,
            use_grid=True,
            use_generator=True,
            battery_reserve_pct=self.battery_reserve_fraction,
            max_grid_import_pct=1.0,
            prefer_grid_over_generator=True,
            allow_grid_export=True,
            policy_name="pv_first_battery_grid_diesel",
            decision_reason="Merit order: renewables → battery → grid → diesel",
        )

    def get_parameters(self):
        return {"battery_reserve_fraction": self.battery_reserve_fraction}

    def describe(self) -> str:
        return "pv_first_battery_grid_diesel: Prioritize renewable sources, grid backup, diesel last resort"


class GridFirst(BaseEnergyPolicy):
    """Always use grid when available, renewables and battery disabled.

    Relies on grid as primary source with generator as emergency
    backup only.  Does not use renewables or battery — represents a
    community that hasn't invested in on-site generation.  No grid
    export (not producing surplus to sell).

    Maps to scenario policy name: "all_grid".
    """

    name = "grid_first"

    def allocate_energy(self, ctx: EnergyPolicyContext) -> EnergyAllocation:
        return EnergyAllocation(
            use_renewables=False,
            use_battery=False,
            use_grid=True,
            use_generator=True,
            battery_reserve_pct=0.0,
            max_grid_import_pct=1.0,
            prefer_grid_over_generator=True,
            allow_grid_export=False,
            policy_name="grid_first",
            decision_reason="Grid primary, generator backup",
        )

    def describe(self) -> str:
        return "grid_first: Grid power primary, generator backup, no renewables"


class CheapestEnergy(BaseEnergyPolicy):
    """Dynamic selection based on current costs. Arbitrage between sources.

    Compares the renewable LCOE to the current grid price each period.
    If the grid is cheaper than renewables, signals grid-first dispatch;
    otherwise uses the standard renewable-first merit order.  Always
    uses battery when it saves money and exports to grid when profitable.

    Uses separate configurable battery reserve fractions for each mode:
    lower reserve when grid is cheap (default 10%), higher when using
    renewables (default 15%).

    Maps to scenario policy name: "cost_minimize".
    """

    name = "cheapest_energy"

    def __init__(self, battery_reserve_grid_cheap=0.10, battery_reserve_renewable_cheap=0.15):
        self.battery_reserve_grid_cheap = battery_reserve_grid_cheap
        self.battery_reserve_renewable_cheap = battery_reserve_renewable_cheap

    def allocate_energy(self, ctx: EnergyPolicyContext) -> EnergyAllocation:
        if ctx.grid_price_per_kwh < ctx.renewable_lcoe_per_kwh:
            # Grid is cheaper — prefer grid, use renewables to charge battery / export
            return EnergyAllocation(
                use_renewables=True,
                use_battery=True,
                use_grid=True,
                use_generator=True,
                battery_reserve_pct=self.battery_reserve_grid_cheap,
                max_grid_import_pct=1.0,
                prefer_grid_over_generator=True,
                allow_grid_export=True,
                policy_name="cheapest_energy",
                decision_reason=(
                    f"Grid cheaper ({ctx.grid_price_per_kwh:.3f}) "
                    f"than LCOE ({ctx.renewable_lcoe_per_kwh:.3f}), prefer grid"
                ),
            )
        else:
            # Renewables cheaper — standard merit order
            return EnergyAllocation(
                use_renewables=True,
                use_battery=True,
                use_grid=True,
                use_generator=True,
                battery_reserve_pct=self.battery_reserve_renewable_cheap,
                max_grid_import_pct=1.0,
                prefer_grid_over_generator=True,
                allow_grid_export=True,
                policy_name="cheapest_energy",
                decision_reason=(
                    f"LCOE ({ctx.renewable_lcoe_per_kwh:.3f}) "
                    f"<= grid ({ctx.grid_price_per_kwh:.3f}), prefer renewables"
                ),
            )

    def get_parameters(self):
        return {
            "strategy": "dynamic_cost_comparison",
            "battery_reserve_grid_cheap": self.battery_reserve_grid_cheap,
            "battery_reserve_renewable_cheap": self.battery_reserve_renewable_cheap,
        }

    def describe(self) -> str:
        return "cheapest_energy: Cost-optimized dispatch with dynamic LCOE vs grid comparison"


# ---------------------------------------------------------------------------
# Policy registry
# ---------------------------------------------------------------------------

ENERGY_POLICIES = {
    "all_renewable": PvFirstBatteryGridDiesel,
    "hybrid": PvFirstBatteryGridDiesel,  # Same as all_renewable for now
    "pv_first_battery_grid_diesel": PvFirstBatteryGridDiesel,  # Direct class name alias
    "all_grid": GridFirst,
    "grid_first": GridFirst,  # Direct class name alias
    "cost_minimize": CheapestEnergy,
    "cheapest_energy": CheapestEnergy,  # Direct class name alias
}


def get_energy_policy(name, **kwargs):
    """Get an energy policy instance by name.

    Args:
        name: Policy name as string (e.g., "all_renewable", "cost_minimize")
        **kwargs: Parameters to pass to policy constructor

    Returns:
        Instantiated policy object

    Raises:
        ValueError: If policy name not found
    """
    if name not in ENERGY_POLICIES:
        valid = ", ".join(ENERGY_POLICIES.keys())
        raise ValueError(
            f"Unknown energy policy: '{name}'. Available: {valid}"
        )
    return ENERGY_POLICIES[name](**kwargs)
