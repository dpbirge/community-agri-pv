# Generate seasonal household energy and water demand files
# Layer 1: Pre-computation
#
# Generates daily household energy and water demand based on weather data.
# Energy demand includes AC multiplier based on temperature.
# Water demand includes slight increase in summer months.

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime


def get_project_root():
    """Get project root directory."""
    return Path(__file__).parent.parent.parent


def load_weather_data():
    """Load daily weather data."""
    root = get_project_root()
    weather_path = root / "raw_data/precomputed/weather/daily_weather_scenario_001-toy.csv"
    if not weather_path.exists():
        weather_path = root / "data/precomputed/weather/daily_weather_scenario_001-toy.csv"

    # Skip metadata header
    with open(weather_path, "r") as f:
        lines = f.readlines()

    header_idx = 0
    for i, line in enumerate(lines):
        if not line.startswith("#"):
            header_idx = i
            break

    return pd.read_csv(weather_path, skiprows=header_idx)


def load_housing_data():
    """Load housing energy and water baseline data from building_demands factors."""
    housing_path = get_project_root() / "data/building_demands/housing_energy_water_factors-toy.csv"

    with open(housing_path, "r") as f:
        lines = f.readlines()

    header_idx = 0
    for i, line in enumerate(lines):
        if not line.startswith("#"):
            header_idx = i
            break

    df = pd.read_csv(housing_path, skiprows=header_idx)
    # Normalize column names (factors use energy_per_household_per_day_kWh, water_per_household_per_day_m3)
    df.columns = df.columns.str.strip()
    return df


def calculate_ac_multiplier(temp_max):
    """Calculate AC energy multiplier based on maximum temperature.

    Logic:
    - Below 25C: No AC needed, base demand only (multiplier = 0.6)
    - 25-30C: Light AC use (multiplier = 0.8)
    - 30-35C: Moderate AC use (multiplier = 1.0, baseline)
    - 35-40C: Heavy AC use (multiplier = 1.2)
    - Above 40C: Full AC use (multiplier = 1.4)

    These multipliers affect the AC portion of energy use (~40-60% of household energy).
    """
    if temp_max < 25:
        return 0.6
    elif temp_max < 30:
        return 0.8
    elif temp_max < 35:
        return 1.0
    elif temp_max < 40:
        return 1.2
    else:
        return 1.4


def calculate_water_multiplier(temp_max):
    """Calculate water demand multiplier based on temperature.

    Logic:
    - Below 25C: Slightly reduced water use (multiplier = 0.95)
    - 25-35C: Normal water use (multiplier = 1.0)
    - Above 35C: Increased water use (multiplier = 1.1)
    """
    if temp_max < 25:
        return 0.95
    elif temp_max < 35:
        return 1.0
    else:
        return 1.1


def generate_household_demand():
    """Generate daily household energy and water demand files."""
    print("Loading weather data...")
    weather = load_weather_data()

    print("Loading housing data...")
    housing = load_housing_data()

    # Base energy and water values per household type (from factors file)
    kwh_col = "energy_per_household_per_day_kWh"
    m3_col = "water_per_household_per_day_m3"
    small_base_kwh = housing[housing["category"] == "small_household"][kwh_col].values[0]
    medium_base_kwh = housing[housing["category"] == "medium_household"][kwh_col].values[0]
    large_base_kwh = housing[housing["category"] == "large_household"][kwh_col].values[0]

    small_base_m3 = housing[housing["category"] == "small_household"][m3_col].values[0]
    medium_base_m3 = housing[housing["category"] == "medium_household"][m3_col].values[0]
    large_base_m3 = housing[housing["category"] == "large_household"][m3_col].values[0]

    # Household counts (from housing data assumptions: 6 small, 12 medium, 15 large)
    small_count = 6
    medium_count = 12
    large_count = 15

    # AC fraction of energy use (based on equipment lists in housing data)
    # AC is roughly 50% of daily energy for most households
    ac_fraction = 0.50

    print(f"Processing {len(weather)} days of weather data...")

    # Calculate daily values
    dates = weather["date"].tolist()
    temp_max_values = weather["temp_max_c"].tolist()

    energy_data = []
    water_data = []

    for date, temp_max in zip(dates, temp_max_values):
        ac_mult = calculate_ac_multiplier(temp_max)
        water_mult = calculate_water_multiplier(temp_max)

        # Energy: base non-AC portion + AC portion adjusted by multiplier
        non_ac_fraction = 1 - ac_fraction

        small_kwh = small_base_kwh * (non_ac_fraction + ac_fraction * ac_mult)
        medium_kwh = medium_base_kwh * (non_ac_fraction + ac_fraction * ac_mult)
        large_kwh = large_base_kwh * (non_ac_fraction + ac_fraction * ac_mult)

        total_community_kwh = (small_count * small_kwh +
                               medium_count * medium_kwh +
                               large_count * large_kwh)

        energy_data.append({
            "date": date,
            "small_household_kwh": round(small_kwh, 2),
            "medium_household_kwh": round(medium_kwh, 2),
            "large_household_kwh": round(large_kwh, 2),
            "total_community_kwh": round(total_community_kwh, 2),
        })

        # Water: adjusted by temperature multiplier
        small_m3 = small_base_m3 * water_mult
        medium_m3 = medium_base_m3 * water_mult
        large_m3 = large_base_m3 * water_mult

        total_community_m3 = (small_count * small_m3 +
                              medium_count * medium_m3 +
                              large_count * large_m3)

        water_data.append({
            "date": date,
            "small_household_m3": round(small_m3, 3),
            "medium_household_m3": round(medium_m3, 3),
            "large_household_m3": round(large_m3, 3),
            "total_community_m3": round(total_community_m3, 2),
        })

    # Create DataFrames
    energy_df = pd.DataFrame(energy_data)
    water_df = pd.DataFrame(water_data)

    # Write output files
    output_dir = get_project_root() / "data/building_demands"
    output_dir.mkdir(parents=True, exist_ok=True)

    energy_path = output_dir / "household_energy_kwh_per_day-toy.csv"
    water_path = output_dir / "household_water_m3_per_day-toy.csv"

    # Energy file with metadata
    energy_header = """# SOURCE: Generated from weather and housing data
# DATE: {date}
# DESCRIPTION: Daily household energy demand adjusted for temperature (AC usage)
# UNITS: date (YYYY-MM-DD), *_kwh (kWh/day per household or total)
# LOGIC: Base energy from housing specs, AC portion (50%) adjusted by temperature multiplier
# DEPENDENCIES: daily_weather_scenario_001-toy.csv, housing_energy_water_factors-toy.csv
# ASSUMPTIONS: Household counts: 6 small, 12 medium, 15 large (33 total, ~150 people)
""".format(date=datetime.now().strftime("%Y-%m-%d"))

    with open(energy_path, "w") as f:
        f.write(energy_header)
        energy_df.to_csv(f, index=False)

    # Water file with metadata
    water_header = """# SOURCE: Generated from weather and housing data
# DATE: {date}
# DESCRIPTION: Daily household water demand adjusted for temperature
# UNITS: date (YYYY-MM-DD), *_m3 (m3/day per household or total)
# LOGIC: Base water from housing specs, adjusted by temperature multiplier (higher in hot weather)
# DEPENDENCIES: daily_weather_scenario_001-toy.csv, housing_energy_water_factors-toy.csv
# ASSUMPTIONS: Household counts: 6 small, 12 medium, 15 large (33 total, ~150 people)
""".format(date=datetime.now().strftime("%Y-%m-%d"))

    with open(water_path, "w") as f:
        f.write(water_header)
        water_df.to_csv(f, index=False)

    print(f"\nGenerated files:")
    print(f"  - {energy_path}")
    print(f"  - {water_path}")

    # Summary statistics
    print(f"\nEnergy summary (kWh/day):")
    print(f"  Small household: {energy_df['small_household_kwh'].min():.1f} - {energy_df['small_household_kwh'].max():.1f}")
    print(f"  Medium household: {energy_df['medium_household_kwh'].min():.1f} - {energy_df['medium_household_kwh'].max():.1f}")
    print(f"  Large household: {energy_df['large_household_kwh'].min():.1f} - {energy_df['large_household_kwh'].max():.1f}")
    print(f"  Community total: {energy_df['total_community_kwh'].min():.1f} - {energy_df['total_community_kwh'].max():.1f}")

    print(f"\nWater summary (m3/day):")
    print(f"  Small household: {water_df['small_household_m3'].min():.3f} - {water_df['small_household_m3'].max():.3f}")
    print(f"  Medium household: {water_df['medium_household_m3'].min():.3f} - {water_df['medium_household_m3'].max():.3f}")
    print(f"  Large household: {water_df['large_household_m3'].min():.3f} - {water_df['large_household_m3'].max():.3f}")
    print(f"  Community total: {water_df['total_community_m3'].min():.2f} - {water_df['total_community_m3'].max():.2f}")

    return energy_df, water_df


def main():
    """Main entry point."""
    print("Generating seasonal household demand files...")
    print("=" * 50)
    generate_household_demand()
    print("\nDone.")


if __name__ == "__main__":
    main()
