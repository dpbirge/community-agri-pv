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
    with open(filepath, "r") as f:
        skip = 0
        for line in f:
            if line.startswith("#"):
                skip += 1
            else:
                break
        return skip


def load_irrigation_demand(crop_name, registry):
    """Load irrigation CSV for a crop, return DataFrame indexed for lookup.

    Args:
        crop_name: Name of crop (tomato, potato, onion, kale, cucumber)
        registry: Data registry dict with file paths

    Returns:
        DataFrame with columns: planting_date, calendar_date, irrigation_m3_per_ha_per_day
        Multi-indexed by (planting_date, calendar_date) for fast lookup
    """
    filepath = registry["irrigation"][crop_name]
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


def load_yield_data(crop_name, registry):
    """Load yield CSV for a crop.

    Args:
        crop_name: Name of crop (tomato, potato, onion, kale, cucumber)
        registry: Data registry dict with file paths

    Returns:
        DataFrame with columns: planting_date, harvest_date, yield_kg_per_ha, etc.
        Indexed by planting_date for lookup
    """
    filepath = registry["yields"][crop_name]
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


def load_municipal_water_prices(registry, use_research=True):
    """Load municipal water prices, return DataFrame indexed by year.

    Args:
        registry: Data registry dict with file paths
        use_research: If True, use research data file; if False, use toy data

    Returns:
        DataFrame with columns: usd_per_m3_tier1/2/3
        Indexed by year (int)
    """
    if use_research:
        filepath = "data/prices/water/historical_municipal_water_prices-research.csv"
    else:
        filepath = registry["prices_utilities"]["municipal_water"]

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


def load_electricity_prices(registry, use_research=True):
    """Load electricity prices, return DataFrame indexed by date.

    Args:
        registry: Data registry dict with file paths
        use_research: If True, use research data file; if False, use toy data

    Returns:
        DataFrame with columns: usd_per_kwh_offpeak, usd_per_kwh_peak, usd_per_kwh_avg_daily
        Indexed by date
    """
    if use_research:
        filepath = "data/prices/electricity/historical_grid_electricity_prices-research.csv"
    else:
        filepath = registry["prices_utilities"]["electricity"]

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


def load_water_treatment_energy(registry):
    """Load water treatment energy requirements by salinity level.

    Args:
        registry: Data registry dict with file paths

    Returns:
        DataFrame indexed by salinity_level (light/moderate/heavy)
    """
    filepath = registry["water_treatment"]["energy"]
    skip_rows = _skip_metadata_rows(filepath)

    df = pd.read_csv(filepath, skiprows=skip_rows)
    df = df.set_index("salinity_level")
    return df


def get_treatment_kwh_per_m3(treatment_df, salinity_level="moderate"):
    """Get water treatment energy requirement.

    Args:
        treatment_df: DataFrame from load_water_treatment_energy
        salinity_level: 'light', 'moderate', or 'heavy'

    Returns:
        float: kWh per m3 (typical value)
    """
    return treatment_df.loc[salinity_level, "energy_kwh_per_m3_typical"]


class SimulationDataLoader:
    """Wrapper class that loads and caches all simulation data.

    Provides convenient access to all precomputed data needed for simulation.
    """

    def __init__(self, registry_path="settings/data_registry.yaml", use_research_prices=True):
        """Initialize data loader and load all required data.

        Args:
            registry_path: Path to data registry YAML
            use_research_prices: If True, use research price data instead of toy data
        """
        self.registry = load_data_registry(registry_path)
        self.use_research_prices = use_research_prices

        # Load irrigation demand for all crops
        self.irrigation = {}
        for crop in ["tomato", "potato", "onion", "kale", "cucumber"]:
            self.irrigation[crop] = load_irrigation_demand(crop, self.registry)

        # Load yield data for all crops
        self.yields = {}
        for crop in ["tomato", "potato", "onion", "kale", "cucumber"]:
            self.yields[crop] = load_yield_data(crop, self.registry)

        # Load price data
        self.municipal_prices = load_municipal_water_prices(self.registry, use_research_prices)
        self.electricity_prices = load_electricity_prices(self.registry, use_research_prices)

        # Load water treatment energy
        self.treatment_energy = load_water_treatment_energy(self.registry)

    def get_irrigation_m3_per_ha(self, crop, planting_date, calendar_date):
        """Get daily irrigation requirement for a crop."""
        return get_daily_irrigation(self.irrigation[crop], planting_date, calendar_date)

    def get_yield_info(self, crop, planting_date):
        """Get yield info for a crop planting."""
        return get_season_yield(self.yields[crop], planting_date)

    def get_municipal_price_usd_m3(self, year, tier=3, pricing_regime="subsidized"):
        """Get municipal water price."""
        return get_municipal_price(self.municipal_prices, year, tier, pricing_regime)

    def get_electricity_price_usd_kwh(self, target_date):
        """Get electricity price."""
        return get_electricity_price(self.electricity_prices, target_date)

    def get_treatment_energy_kwh_m3(self, salinity_level="moderate"):
        """Get water treatment energy requirement."""
        return get_treatment_kwh_per_m3(self.treatment_energy, salinity_level)
