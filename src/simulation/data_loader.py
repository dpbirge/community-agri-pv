# Data loader for Water Simulation MVP
# Layer 3: Simulation Engine
#
# Loads precomputed irrigation demand, yield, and price data for simulation lookup.
# All data is loaded once at simulation start and cached for fast daily lookups.

from datetime import date, datetime
from pathlib import Path

import pandas as pd
import yaml


def load_data_registry(registry_path="settings/data_registry.yaml"):
    """Load data registry YAML and return as dict."""
    with open(registry_path, "r") as f:
        return yaml.safe_load(f)


def _skip_metadata_rows(filepath):
    """Count number of comment rows at start of CSV file."""
    filepath = Path(filepath)
    with open(filepath, "r") as f:
        skip = 0
        for line in f:
            if line.startswith("#"):
                skip += 1
            else:
                break
        return skip


def load_irrigation_demand(crop_name, registry, project_root=None):
    """Load irrigation CSV for a crop, return DataFrame indexed for lookup.

    Args:
        crop_name: Name of crop (tomato, potato, onion, kale, cucumber)
        registry: Data registry dict with file paths
        project_root: Optional path to project root (for resolving relative paths)

    Returns:
        DataFrame with columns: planting_date, calendar_date, irrigation_m3_per_ha_per_day
        Multi-indexed by (planting_date, calendar_date) for fast lookup
    """
    filepath = registry["irrigation"][crop_name]
    if project_root:
        filepath = Path(project_root) / filepath
    skip_rows = _skip_metadata_rows(filepath)

    df = pd.read_csv(filepath, skiprows=skip_rows)
    df["planting_date"] = pd.to_datetime(df["planting_date"])
    df["calendar_date"] = pd.to_datetime(df["calendar_date"])

    # Create multi-index for fast lookup
    df = df.set_index(["planting_date", "calendar_date"])
    return df


def get_daily_irrigation(irrigation_df, planting_date, calendar_date):
    """Look up irrigation_m3_per_ha_per_day for specific date combination.

    Args:
        irrigation_df: DataFrame from load_irrigation_demand (multi-indexed)
        planting_date: Planting date (datetime or date)
        calendar_date: Calendar date to look up (datetime or date)

    Returns:
        float: irrigation_m3_per_ha_per_day, or 0.0 if date not in growing season
    """
    # Normalize to datetime for consistent lookup
    if isinstance(planting_date, date) and not isinstance(planting_date, datetime):
        planting_date = datetime.combine(planting_date, datetime.min.time())
    if isinstance(calendar_date, date) and not isinstance(calendar_date, datetime):
        calendar_date = datetime.combine(calendar_date, datetime.min.time())

    try:
        row = irrigation_df.loc[(planting_date, calendar_date)]
        return row["irrigation_m3_per_ha_per_day"]
    except KeyError:
        # Date not in growing season (before planting or after harvest)
        return 0.0


def load_yield_data(crop_name, registry, project_root=None):
    """Load yield CSV for a crop.

    Args:
        crop_name: Name of crop (tomato, potato, onion, kale, cucumber)
        registry: Data registry dict with file paths
        project_root: Optional path to project root (for resolving relative paths)

    Returns:
        DataFrame with columns: planting_date, harvest_date, yield_kg_per_ha, etc.
        Indexed by planting_date for lookup
    """
    filepath = registry["yields"][crop_name]
    if project_root:
        filepath = Path(project_root) / filepath
    skip_rows = _skip_metadata_rows(filepath)

    df = pd.read_csv(filepath, skiprows=skip_rows)
    df["planting_date"] = pd.to_datetime(df["planting_date"])
    df["harvest_date"] = pd.to_datetime(df["harvest_date"])
    df = df.set_index("planting_date")
    return df


def get_season_yield(yield_df, planting_date):
    """Return yield info for a specific planting date.

    Args:
        yield_df: DataFrame from load_yield_data (indexed by planting_date)
        planting_date: Planting date to look up (datetime or date)

    Returns:
        dict: {yield_kg_per_ha, harvest_date, weather_stress_factor}
        Returns None if planting date not found
    """
    if isinstance(planting_date, date) and not isinstance(planting_date, datetime):
        planting_date = datetime.combine(planting_date, datetime.min.time())

    try:
        row = yield_df.loc[planting_date]
        return {
            "yield_kg_per_ha": row["yield_kg_per_ha"],
            "harvest_date": row["harvest_date"].date() if hasattr(row["harvest_date"], "date") else row["harvest_date"],
            "weather_stress_factor": row["weather_stress_factor"],
        }
    except KeyError:
        return None


def load_municipal_water_prices(registry, use_research=True, project_root=None):
    """Load municipal water prices, return DataFrame indexed by year.

    Args:
        registry: Data registry dict with file paths
        use_research: If True, use research data file; if False, use toy data
        project_root: Optional path to project root (for resolving relative paths)

    Returns:
        DataFrame with columns: usd_per_m3_tier1/2/3
        Indexed by year (int)
    """
    if use_research:
        filepath = "data/prices/water/historical_municipal_water_prices-research.csv"
    else:
        filepath = registry["prices_utilities"]["municipal_water"]
    
    if project_root:
        filepath = Path(project_root) / filepath

    skip_rows = _skip_metadata_rows(filepath)
    df = pd.read_csv(filepath, skiprows=skip_rows)
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df = df.set_index("year")
    return df


def get_municipal_price(prices_df, year, tier=3, pricing_regime="subsidized"):
    """Get municipal water price for a year.

    Args:
        prices_df: DataFrame from load_municipal_water_prices
        year: Year to look up
        tier: 1, 2, or 3 for subsidized pricing
        pricing_regime: 'subsidized' or 'unsubsidized'

    Returns:
        float: USD per m3
    """
    if pricing_regime == "subsidized":
        col = f"usd_per_m3_tier{tier}"
        try:
            return prices_df.loc[year, col]
        except KeyError:
            # Use closest available year
            available_years = prices_df.index.tolist()
            closest = min(available_years, key=lambda y: abs(y - year))
            return prices_df.loc[closest, col]
    else:
        # Unsubsidized pricing is handled by scenario config (not from this file)
        return None


def load_electricity_prices(registry, use_research=True, project_root=None):
    """Load electricity prices, return DataFrame indexed by date.

    Args:
        registry: Data registry dict with file paths
        use_research: If True, use research data file; if False, use toy data
        project_root: Optional path to project root (for resolving relative paths)

    Returns:
        DataFrame with columns: usd_per_kwh_offpeak, usd_per_kwh_peak, usd_per_kwh_avg_daily
        Indexed by date
    """
    if use_research:
        filepath = "data/prices/electricity/historical_grid_electricity_prices-research.csv"
    else:
        filepath = registry["prices_utilities"]["electricity"]
    
    if project_root:
        filepath = Path(project_root) / filepath

    skip_rows = _skip_metadata_rows(filepath)
    df = pd.read_csv(filepath, skiprows=skip_rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    return df


def get_electricity_price(prices_df, target_date, use_average=True):
    """Get electricity price for a date.

    Args:
        prices_df: DataFrame from load_electricity_prices
        target_date: Date to look up
        use_average: If True, return avg_daily price; if False, return tuple (offpeak, peak)

    Returns:
        float or tuple: USD per kWh

    Note:
        Egyptian agricultural electricity tariffs do not have seasonal (summer/winter)
        rate variations. Research into EgyptERA official tariff schedules (2024) confirms
        rates are set uniformly year-round, with only peak/off-peak time-of-use
        differentiation available for users with smart meters. See
        docs/research/egyptian_utility_pricing.md for full analysis.
    """
    if isinstance(target_date, date) and not isinstance(target_date, datetime):
        target_date = datetime.combine(target_date, datetime.min.time())

    # Find the applicable price (most recent date <= target_date)
    applicable_dates = prices_df.index[prices_df.index <= target_date]
    if len(applicable_dates) == 0:
        applicable_date = prices_df.index.min()
    else:
        applicable_date = applicable_dates.max()

    row = prices_df.loc[applicable_date]

    if use_average:
        return row["usd_per_kwh_avg_daily"]
    else:
        return (row["usd_per_kwh_offpeak"], row["usd_per_kwh_peak"])


def load_water_treatment_energy(registry, project_root=None):
    """Load water treatment energy requirements by salinity level.

    Args:
        registry: Data registry dict with file paths
        project_root: Optional path to project root (for resolving relative paths)

    Returns:
        DataFrame indexed by salinity_level (low/moderate/high)
    """
    filepath = registry["water_treatment"]["energy"]
    if project_root:
        filepath = Path(project_root) / filepath
    skip_rows = _skip_metadata_rows(filepath)

    df = pd.read_csv(filepath, skiprows=skip_rows)
    df = df.set_index("salinity_level")
    return df


def get_treatment_kwh_per_m3(treatment_df, salinity_level="moderate"):
    """Get water treatment energy requirement.

    Args:
        treatment_df: DataFrame from load_water_treatment_energy
        salinity_level: 'low', 'moderate', or 'high'

    Returns:
        float: kWh per m3 (typical value)
    """
    return treatment_df.loc[salinity_level, "energy_kwh_per_m3_typical"]


def load_diesel_prices(use_research=True, project_root=None):
    """Load diesel prices, return DataFrame indexed by date.

    Args:
        use_research: If True, use research data file; if False, use toy data
        project_root: Optional path to project root (for resolving relative paths)

    Returns:
        DataFrame with columns: usd_per_liter, egp_per_liter_original, usd_egp_exchange_rate, subsidy_regime
        Indexed by date
    """
    if use_research:
        filepath = "data/prices/diesel/historical_diesel_prices-research.csv"
    else:
        filepath = "data/prices/diesel/historical_diesel_prices-toy.csv"

    if project_root:
        filepath = Path(project_root) / filepath

    skip_rows = _skip_metadata_rows(filepath)
    df = pd.read_csv(filepath, skiprows=skip_rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    return df


def get_diesel_price(prices_df, target_date):
    """Get diesel price for a date.

    Args:
        prices_df: DataFrame from load_diesel_prices
        target_date: Date to look up

    Returns:
        float: USD per liter
    """
    if isinstance(target_date, date) and not isinstance(target_date, datetime):
        target_date = datetime.combine(target_date, datetime.min.time())

    # Find the applicable price (most recent date <= target_date)
    applicable_dates = prices_df.index[prices_df.index <= target_date]
    if len(applicable_dates) == 0:
        applicable_date = prices_df.index.min()
    else:
        applicable_date = applicable_dates.max()

    row = prices_df.loc[applicable_date]
    return row["usd_per_liter"]


def load_fertilizer_costs(project_root=None):
    """Load fertilizer costs, return DataFrame indexed by date.

    Args:
        project_root: Optional path to project root (for resolving relative paths)

    Returns:
        DataFrame with columns: usd_per_ha, egp_per_ha_original, usd_egp_exchange_rate, notes
        Indexed by date
    """
    filepath = "data/prices/inputs/historical_fertilizer_costs-toy.csv"

    if project_root:
        filepath = Path(project_root) / filepath

    skip_rows = _skip_metadata_rows(filepath)
    df = pd.read_csv(filepath, skiprows=skip_rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    return df


def get_fertilizer_cost(costs_df, target_date):
    """Get fertilizer cost per hectare for a date.

    Args:
        costs_df: DataFrame from load_fertilizer_costs
        target_date: Date to look up

    Returns:
        float: USD per hectare
    """
    if isinstance(target_date, date) and not isinstance(target_date, datetime):
        target_date = datetime.combine(target_date, datetime.min.time())

    # Find the applicable cost (most recent date <= target_date)
    applicable_dates = costs_df.index[costs_df.index <= target_date]
    if len(applicable_dates) == 0:
        applicable_date = costs_df.index.min()
    else:
        applicable_date = applicable_dates.max()

    row = costs_df.loc[applicable_date]
    return row["usd_per_ha"]


def load_pv_power_data(registry, project_root=None):
    """Load normalized daily PV power output data.

    Args:
        registry: Data registry dict with file paths
        project_root: Optional path to project root

    Returns:
        DataFrame with columns: kwh_per_kw_per_day, capacity_factor
        Multi-indexed by (date, density_variant) for fast lookup
    """
    filepath = registry["power"]["pv"]
    if project_root:
        filepath = Path(project_root) / filepath
    skip_rows = _skip_metadata_rows(filepath)

    df = pd.read_csv(filepath, skiprows=skip_rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index(["date", "density_variant"])
    return df


def get_pv_kwh_per_kw(pv_df, target_date, density_variant="medium"):
    """Get daily PV output per kW of installed capacity.

    Args:
        pv_df: DataFrame from load_pv_power_data (multi-indexed)
        target_date: Date to look up
        density_variant: Panel density variant ('low', 'medium', 'high')

    Returns:
        float: kWh per kW per day for the given date and density
    """
    if isinstance(target_date, date) and not isinstance(target_date, datetime):
        target_date = datetime.combine(target_date, datetime.min.time())

    try:
        return pv_df.loc[(target_date, density_variant), "kwh_per_kw_per_day"]
    except KeyError:
        # Date not found; use closest available date
        dates = pv_df.index.get_level_values("date").unique()
        closest = min(dates, key=lambda d: abs((d - target_date).total_seconds()))
        return pv_df.loc[(closest, density_variant), "kwh_per_kw_per_day"]


def load_wind_power_data(registry, project_root=None):
    """Load normalized daily wind power output data.

    Args:
        registry: Data registry dict with file paths
        project_root: Optional path to project root

    Returns:
        DataFrame with columns: kwh_per_kw_per_day, capacity_factor
        Multi-indexed by (date, turbine_variant) for fast lookup
    """
    filepath = registry["power"]["wind"]
    if project_root:
        filepath = Path(project_root) / filepath
    skip_rows = _skip_metadata_rows(filepath)

    df = pd.read_csv(filepath, skiprows=skip_rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index(["date", "turbine_variant"])
    return df


def get_wind_kwh_per_kw(wind_df, target_date, turbine_variant="medium"):
    """Get daily wind output per kW of installed capacity.

    Args:
        wind_df: DataFrame from load_wind_power_data (multi-indexed)
        target_date: Date to look up
        turbine_variant: Turbine size variant ('small', 'medium', 'large')

    Returns:
        float: kWh per kW per day for the given date and turbine variant
    """
    if isinstance(target_date, date) and not isinstance(target_date, datetime):
        target_date = datetime.combine(target_date, datetime.min.time())

    try:
        return wind_df.loc[(target_date, turbine_variant), "kwh_per_kw_per_day"]
    except KeyError:
        # Date not found; use closest available date
        dates = wind_df.index.get_level_values("date").unique()
        closest = min(dates, key=lambda d: abs((d - target_date).total_seconds()))
        return wind_df.loc[(closest, turbine_variant), "kwh_per_kw_per_day"]


def load_crop_prices(crop_name, use_research=True, project_root=None):
    """Load crop prices, return DataFrame indexed by date.

    Args:
        crop_name: Name of crop (tomato, potato, onion, kale, cucumber)
        use_research: If True, use research data file; if False, use toy data
        project_root: Optional path to project root (for resolving relative paths)

    Returns:
        DataFrame with columns: usd_per_kg_farmgate, usd_per_kg_wholesale, usd_per_kg_retail
        Indexed by date
    """
    if use_research:
        filepath = f"data/prices/crops/{crop_name}_prices-research.csv"
    else:
        filepath = f"data/prices/crops/historical_{crop_name}_prices-toy.csv"
    
    if project_root:
        filepath = Path(project_root) / filepath

    skip_rows = _skip_metadata_rows(filepath)
    df = pd.read_csv(filepath, skiprows=skip_rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    return df


def get_crop_price(prices_df, target_date, price_type="farmgate"):
    """Get crop price for a date.

    Args:
        prices_df: DataFrame from load_crop_prices
        target_date: Date to look up
        price_type: 'farmgate', 'wholesale', or 'retail'

    Returns:
        float: USD per kg
    """
    if isinstance(target_date, date) and not isinstance(target_date, datetime):
        target_date = datetime.combine(target_date, datetime.min.time())

    # Find the applicable price (most recent date <= target_date)
    applicable_dates = prices_df.index[prices_df.index <= target_date]
    if len(applicable_dates) == 0:
        applicable_date = prices_df.index.min()
    else:
        applicable_date = applicable_dates.max()

    row = prices_df.loc[applicable_date]
    col = f"usd_per_kg_{price_type}"
    # Toy data has a single 'usd_per_kg' column; fall back to it when
    # the price_type-specific column (e.g. usd_per_kg_farmgate) is missing
    if col not in row.index:
        col = "usd_per_kg"
    return row[col]


def calculate_tiered_cost(consumption, cumulative_consumption, tier_config):
    """Calculate cost for consumption under tiered pricing structure.

    Applies Egyptian-style progressive tier pricing where each unit of
    consumption is charged at the rate for its tier bracket. Tiers are
    determined by cumulative monthly consumption.

    Args:
        consumption: Current consumption to price (m3 or kWh)
        cumulative_consumption: Consumption already used this period (m3 or kWh)
        tier_config: TierPricingConfig with bracket definitions

    Returns:
        dict with:
            - total_cost: Total cost for this consumption
            - cost_per_unit: Effective average cost per unit
            - tier_breakdown: List of (tier_num, units, cost) for each tier used
            - marginal_tier: Tier number for the last unit consumed

    Example:
        Egyptian water tiers (2018):
        - 0-10 m3: 0.65 EGP/m3
        - 11-20 m3: 1.60 EGP/m3

        If cumulative = 8 m3 and consumption = 5 m3:
        - First 2 m3 at Tier 1 (0.65): 1.30 EGP
        - Next 3 m3 at Tier 2 (1.60): 4.80 EGP
        - Total: 6.10 EGP, effective rate: 1.22 EGP/m3
    """
    if not tier_config or not tier_config.enabled or not tier_config.brackets:
        return None

    if consumption <= 0:
        return {
            "total_cost": 0.0,
            "cost_per_unit": 0.0,
            "tier_breakdown": [],
            "marginal_tier": 0,
        }

    brackets = tier_config.brackets
    remaining = consumption
    total_cost = 0.0
    tier_breakdown = []
    marginal_tier = 1

    # Track position in consumption (cumulative + current)
    position = cumulative_consumption

    for i, bracket in enumerate(brackets):
        tier_num = i + 1
        min_units = bracket.min_units
        max_units = bracket.max_units if bracket.max_units is not None else float("inf")
        price = bracket.price_per_unit

        # Skip tiers we've already passed
        if position >= max_units:
            continue

        # Calculate how much of this consumption falls in this tier
        tier_start = max(position, min_units)
        tier_end = min(position + remaining, max_units)
        units_in_tier = max(0.0, tier_end - tier_start)

        if units_in_tier > 0:
            tier_cost = units_in_tier * price
            total_cost += tier_cost
            tier_breakdown.append((tier_num, units_in_tier, tier_cost))
            marginal_tier = tier_num

            remaining -= units_in_tier
            position += units_in_tier

        if remaining <= 0:
            break

    # Apply wastewater surcharge if configured (water only)
    if tier_config.include_wastewater_surcharge and tier_config.resource_type == "water":
        surcharge = total_cost * (tier_config.wastewater_surcharge_pct / 100.0)
        total_cost += surcharge

    cost_per_unit = total_cost / consumption if consumption > 0 else 0.0

    return {
        "total_cost": total_cost,
        "cost_per_unit": cost_per_unit,
        "tier_breakdown": tier_breakdown,
        "marginal_tier": marginal_tier,
    }


def get_marginal_tier_price(cumulative_consumption, tier_config):
    """Get the price for the next unit of consumption (marginal cost).

    Used for policy decisions where marginal cost comparison is needed.

    Args:
        cumulative_consumption: Consumption already used this period
        tier_config: TierPricingConfig with bracket definitions

    Returns:
        float: Price per unit for the next unit consumed, or None if no tier config
    """
    if not tier_config or not tier_config.enabled or not tier_config.brackets:
        return None

    for bracket in tier_config.brackets:
        max_units = bracket.max_units if bracket.max_units is not None else float("inf")
        if cumulative_consumption < max_units:
            price = bracket.price_per_unit
            # Apply wastewater surcharge if configured
            if tier_config.include_wastewater_surcharge and tier_config.resource_type == "water":
                price *= (1 + tier_config.wastewater_surcharge_pct / 100.0)
            return price

    # If we've exceeded all tiers, use the last tier's price
    last_bracket = tier_config.brackets[-1]
    price = last_bracket.price_per_unit
    if tier_config.include_wastewater_surcharge and tier_config.resource_type == "water":
        price *= (1 + tier_config.wastewater_surcharge_pct / 100.0)
    return price


class SimulationDataLoader:
    """Wrapper class that loads and caches all simulation data.

    Provides convenient access to all precomputed data needed for simulation.
    """

    def __init__(self, registry_path="settings/data_registry.yaml", use_research_prices=True,
                 project_root=None, price_multipliers=None):
        """Initialize data loader and load all required data.

        Args:
            registry_path: Path to data registry YAML
            use_research_prices: If True, use research price data instead of toy data
            project_root: Optional path to project root (for resolving relative paths from registry)
            price_multipliers: Optional dict mapping parameter names to multipliers.
                E.g. {"municipal_water": 1.2, "electricity": 0.8, "crop_tomato": 1.1}
        """
        self.price_multipliers = price_multipliers or {}
        self.registry = load_data_registry(registry_path)
        self.use_research_prices = use_research_prices
        self.project_root = Path(project_root) if project_root else Path.cwd()

        # Load irrigation demand for all crops
        self.irrigation = {}
        for crop in ["tomato", "potato", "onion", "kale", "cucumber"]:
            self.irrigation[crop] = load_irrigation_demand(crop, self.registry, self.project_root)

        # Load yield data for all crops
        self.yields = {}
        for crop in ["tomato", "potato", "onion", "kale", "cucumber"]:
            self.yields[crop] = load_yield_data(crop, self.registry, self.project_root)

        # Load price data
        self.municipal_prices = load_municipal_water_prices(self.registry, use_research_prices, self.project_root)
        self.electricity_prices = load_electricity_prices(self.registry, use_research_prices, self.project_root)

        # Load water treatment energy
        self.treatment_energy = load_water_treatment_energy(self.registry, self.project_root)

        # Load diesel prices
        self.diesel_prices = load_diesel_prices(use_research_prices, self.project_root)

        # Load fertilizer costs
        self.fertilizer_costs = load_fertilizer_costs(self.project_root)

        # Load crop prices
        self.crop_prices = {}
        for crop in ["tomato", "potato", "onion", "kale", "cucumber"]:
            self.crop_prices[crop] = load_crop_prices(crop, use_research_prices, self.project_root)

        # Load precomputed power generation data
        self.pv_power = load_pv_power_data(self.registry, self.project_root)
        self.wind_power = load_wind_power_data(self.registry, self.project_root)

        # Load labor costs
        self._load_labor_costs()

    def _load_labor_costs(self):
        """Load labor requirement and wage data, compute annual labor cost per hectare.

        Reads labor_requirements-toy.csv and labor_wages-toy.csv, matches per_hectare
        activities to wage rates by skill level, and computes the total annual
        labor cost per hectare.

        Skill level mapping:
            unskilled  -> field_worker
            semi-skilled -> field_supervisor
            skilled    -> equipment_operator
        """
        req_path = self.project_root / "data/parameters/labor/labor_requirements-toy.csv"
        wage_path = self.project_root / "data/parameters/labor/labor_wages-toy.csv"

        req_skip = _skip_metadata_rows(req_path)
        wage_skip = _skip_metadata_rows(wage_path)

        req_df = pd.read_csv(req_path, skiprows=req_skip)
        wage_df = pd.read_csv(wage_path, skiprows=wage_skip)

        # Build wage lookup: skill_level -> usd_per_hour (using mapped worker category)
        skill_to_category = {
            "unskilled": "field_worker",
            "semi-skilled": "field_supervisor",
            "skilled": "equipment_operator",
        }
        wage_lookup = {}
        for _, row in wage_df.iterrows():
            wage_lookup[row["worker_category"]] = row["usd_per_hour"]

        skill_wage = {}
        for skill, category in skill_to_category.items():
            skill_wage[skill] = wage_lookup.get(category, 0.0)

        # Sum hours × wage for all per_hectare activities
        annual_cost = 0.0
        per_ha = req_df[req_df["unit"] == "per_hectare"]
        for _, row in per_ha.iterrows():
            hours = row["hours_per_unit"]
            skill = row["skill_level"]
            wage = skill_wage.get(skill, 0.0)
            annual_cost += hours * wage

        self._labor_cost_usd_per_ha_year = annual_cost

    def get_irrigation_m3_per_ha(self, crop, planting_date, calendar_date):
        """Get daily irrigation requirement for a crop."""
        return get_daily_irrigation(self.irrigation[crop], planting_date, calendar_date)

    def get_yield_info(self, crop, planting_date):
        """Get yield info for a crop planting."""
        return get_season_yield(self.yields[crop], planting_date)

    def get_municipal_price_usd_m3(self, year, tier=3, pricing_regime="subsidized"):
        """Get municipal water price."""
        price = get_municipal_price(self.municipal_prices, year, tier, pricing_regime)
        if price is not None:
            price = price * self.price_multipliers.get("municipal_water", 1.0)
        return price

    def get_electricity_price_usd_kwh(self, target_date):
        """Get electricity price."""
        result = get_electricity_price(self.electricity_prices, target_date)
        if isinstance(result, tuple):
            multiplier = self.price_multipliers.get("electricity", 1.0)
            return tuple(v * multiplier for v in result)
        return result * self.price_multipliers.get("electricity", 1.0)

    def get_treatment_energy_kwh_m3(self, salinity_level="moderate"):
        """Get water treatment energy requirement."""
        return get_treatment_kwh_per_m3(self.treatment_energy, salinity_level)

    def get_diesel_price_usd_liter(self, target_date):
        """Get diesel price for a date."""
        return get_diesel_price(self.diesel_prices, target_date) * self.price_multipliers.get("diesel", 1.0)

    def get_fertilizer_cost_usd_ha(self, target_date):
        """Get fertilizer cost per hectare for a date."""
        return get_fertilizer_cost(self.fertilizer_costs, target_date) * self.price_multipliers.get("fertilizer", 1.0)

    def get_crop_price_usd_kg(self, crop, target_date, price_type="farmgate"):
        """Get crop price for a date."""
        return get_crop_price(self.crop_prices[crop], target_date, price_type) * self.price_multipliers.get(f"crop_{crop}", 1.0)

    def get_pv_kwh_per_kw(self, target_date, density_variant="medium"):
        """Get daily PV output per kW of installed capacity.

        Args:
            target_date: Date to look up
            density_variant: Panel density ('low', 'medium', 'high')

        Returns:
            float: kWh per kW per day
        """
        return get_pv_kwh_per_kw(self.pv_power, target_date, density_variant)

    def get_wind_kwh_per_kw(self, target_date, turbine_variant="medium"):
        """Get daily wind output per kW of installed capacity.

        Args:
            target_date: Date to look up
            turbine_variant: Turbine size ('small', 'medium', 'large')

        Returns:
            float: kWh per kW per day
        """
        return get_wind_kwh_per_kw(self.wind_power, target_date, turbine_variant)

    def get_labor_cost_usd_ha_month(self):
        """Get monthly labor cost per hectare (annual ÷ 12)."""
        return (self._labor_cost_usd_per_ha_year / 12.0) * self.price_multipliers.get("labor", 1.0)
