# Generate daily community building energy and water demand files
# Layer 1: Pre-computation
#
# Generates daily community building energy and water demand based on weather data.
# Energy demand includes cooling/ventilation multiplier based on temperature.
# Water demand includes slight increase in hot weather for additional cleaning.

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime


def get_project_root():
    """Get project root directory."""
    return Path(__file__).parent.parent.parent


def load_weather_data():
    """Load daily weather data."""
    weather_path = get_project_root() / "data/precomputed/weather/daily_weather_scenario_001-toy.csv"

    # Skip metadata header
    with open(weather_path, "r") as f:
        lines = f.readlines()

    header_idx = 0
    for i, line in enumerate(lines):
        if not line.startswith("#"):
            header_idx = i
            break

    return pd.read_csv(weather_path, skiprows=header_idx)


def load_building_data():
    """Load community building energy and water baseline data."""
    building_path = get_project_root() / "data/parameters/community/community_buildings_energy_water-toy.csv"

    with open(building_path, "r") as f:
        lines = f.readlines()

    header_idx = 0
    for i, line in enumerate(lines):
        if not line.startswith("#"):
            header_idx = i
            break

    return pd.read_csv(building_path, skiprows=header_idx)


def calculate_cooling_multiplier(temp_max):
    """Calculate cooling/ventilation energy multiplier based on maximum temperature.

    Logic:
    - Below 20C: Minimal cooling needed (multiplier = 0.5)
    - 20-25C: Light ventilation (multiplier = 0.7)
    - 25-30C: Moderate cooling (multiplier = 0.9)
    - 30-35C: Normal cooling (multiplier = 1.0, baseline)
    - 35-40C: Heavy cooling (multiplier = 1.3)
    - Above 40C: Maximum cooling (multiplier = 1.6)

    These multipliers affect the cooling/ventilation portion (~40% of building energy).
    """
    if temp_max < 20:
        return 0.5
    elif temp_max < 25:
        return 0.7
    elif temp_max < 30:
        return 0.9
    elif temp_max < 35:
        return 1.0
    elif temp_max < 40:
        return 1.3
    else:
        return 1.6


def calculate_water_multiplier(temp_max):
    """Calculate water demand multiplier based on temperature.

    Logic:
    - Below 25C: Normal water use (multiplier = 1.0)
    - 25-35C: Slightly increased for cleaning (multiplier = 1.05)
    - Above 35C: Increased water use (multiplier = 1.15)
    """
    if temp_max < 25:
        return 1.0
    elif temp_max < 35:
        return 1.05
    else:
        return 1.15


def generate_community_building_demand(
    office_area_m2=500,
    storage_area_m2=1000,
    meeting_area_m2=300,
    workshop_area_m2=200
):
    """Generate daily community building energy and water demand files.

    Args:
        office_area_m2: Square meters of office/admin space
        storage_area_m2: Square meters of storage/warehouse space
        meeting_area_m2: Square meters of meeting hall space
        workshop_area_m2: Square meters of workshop/maintenance space
    """
    print("Loading weather data...")
    weather = load_weather_data()

    print("Loading building specifications...")
    buildings = load_building_data()

    # Get base energy and water values per building type (per m²)
    building_specs = {}
    for _, row in buildings.iterrows():
        building_specs[row['building_type']] = {
            'kwh_per_m2': row['kwh_per_m2_per_day'],
            'm3_per_m2': row['m3_per_m2_per_day']
        }

    # Building areas
    areas = {
        'office_admin': office_area_m2,
        'storage_warehouse': storage_area_m2,
        'meeting_hall': meeting_area_m2,
        'workshop_maintenance': workshop_area_m2
    }

    # Cooling/ventilation fraction of energy use
    # Office has highest (50%), storage lowest (20%), meeting/workshop moderate (35%)
    cooling_fractions = {
        'office_admin': 0.50,
        'storage_warehouse': 0.20,
        'meeting_hall': 0.35,
        'workshop_maintenance': 0.35
    }

    print(f"Processing {len(weather)} days of weather data...")
    print(f"Building areas: Office {office_area_m2}m², Storage {storage_area_m2}m², "
          f"Meeting {meeting_area_m2}m², Workshop {workshop_area_m2}m²")

    # Calculate daily values
    dates = weather["date"].tolist()
    temp_max_values = weather["temp_max_c"].tolist()

    energy_data = []
    water_data = []

    for date, temp_max in zip(dates, temp_max_values):
        cooling_mult = calculate_cooling_multiplier(temp_max)
        water_mult = calculate_water_multiplier(temp_max)

        daily_energy = {}
        daily_water = {}
        total_energy = 0.0
        total_water = 0.0

        for building_type, area in areas.items():
            specs = building_specs[building_type]
            cooling_frac = cooling_fractions[building_type]
            non_cooling_frac = 1 - cooling_frac

            # Energy: base non-cooling portion + cooling portion adjusted by multiplier
            base_kwh_per_m2 = specs['kwh_per_m2']
            adjusted_kwh_per_m2 = base_kwh_per_m2 * (non_cooling_frac + cooling_frac * cooling_mult)
            building_kwh = area * adjusted_kwh_per_m2

            # Water: adjusted by temperature multiplier
            building_m3 = area * specs['m3_per_m2'] * water_mult

            daily_energy[f"{building_type}_kwh"] = round(building_kwh, 2)
            daily_water[f"{building_type}_m3"] = round(building_m3, 3)

            total_energy += building_kwh
            total_water += building_m3

        energy_data.append({
            "date": date,
            **daily_energy,
            "total_community_buildings_kwh": round(total_energy, 2)
        })

        water_data.append({
            "date": date,
            **daily_water,
            "total_community_buildings_m3": round(total_water, 3)
        })

    # Create DataFrames
    energy_df = pd.DataFrame(energy_data)
    water_df = pd.DataFrame(water_data)

    # Write output files
    output_dir = get_project_root() / "data/precomputed/community_buildings"
    output_dir.mkdir(parents=True, exist_ok=True)

    energy_path = output_dir / "community_buildings_energy_kwh_per_day-toy.csv"
    water_path = output_dir / "community_buildings_water_m3_per_day-toy.csv"

    # Energy file with metadata
    energy_header = f"""# SOURCE: Generated from weather and community building data
# DATE: {datetime.now().strftime("%Y-%m-%d")}
# DESCRIPTION: Daily community building energy demand adjusted for temperature (cooling/ventilation)
# UNITS: date (YYYY-MM-DD), *_kwh (kWh/day per building type or total)
# LOGIC: Base energy from building specs, cooling portion (20-50% depending on type) adjusted by temperature multiplier
# DEPENDENCIES: daily_weather_scenario_001-toy.csv, community_buildings_energy_water-toy.csv
# ASSUMPTIONS: Building areas: Office {office_area_m2}m², Storage {storage_area_m2}m², Meeting {meeting_area_m2}m², Workshop {workshop_area_m2}m² = {sum(areas.values())}m² total
"""

    with open(energy_path, "w") as f:
        f.write(energy_header)
        energy_df.to_csv(f, index=False)

    # Water file with metadata
    water_header = f"""# SOURCE: Generated from weather and community building data
# DATE: {datetime.now().strftime("%Y-%m-%d")}
# DESCRIPTION: Daily community building water demand adjusted for temperature
# UNITS: date (YYYY-MM-DD), *_m3 (m³/day per building type or total)
# LOGIC: Base water from building specs, adjusted by temperature multiplier (higher in hot weather for cleaning)
# DEPENDENCIES: daily_weather_scenario_001-toy.csv, community_buildings_energy_water-toy.csv
# ASSUMPTIONS: Building areas: Office {office_area_m2}m², Storage {storage_area_m2}m², Meeting {meeting_area_m2}m², Workshop {workshop_area_m2}m² = {sum(areas.values())}m² total
"""

    with open(water_path, "w") as f:
        f.write(water_header)
        water_df.to_csv(f, index=False)

    print(f"\nGenerated files:")
    print(f"  - {energy_path}")
    print(f"  - {water_path}")

    # Summary statistics
    print(f"\nEnergy summary (kWh/day):")
    print(f"  Office/admin: {energy_df['office_admin_kwh'].min():.1f} - {energy_df['office_admin_kwh'].max():.1f}")
    print(f"  Storage/warehouse: {energy_df['storage_warehouse_kwh'].min():.1f} - {energy_df['storage_warehouse_kwh'].max():.1f}")
    print(f"  Meeting hall: {energy_df['meeting_hall_kwh'].min():.1f} - {energy_df['meeting_hall_kwh'].max():.1f}")
    print(f"  Workshop/maintenance: {energy_df['workshop_maintenance_kwh'].min():.1f} - {energy_df['workshop_maintenance_kwh'].max():.1f}")
    print(f"  Total community buildings: {energy_df['total_community_buildings_kwh'].min():.1f} - {energy_df['total_community_buildings_kwh'].max():.1f}")

    print(f"\nWater summary (m³/day):")
    print(f"  Office/admin: {water_df['office_admin_m3'].min():.3f} - {water_df['office_admin_m3'].max():.3f}")
    print(f"  Storage/warehouse: {water_df['storage_warehouse_m3'].min():.3f} - {water_df['storage_warehouse_m3'].max():.3f}")
    print(f"  Meeting hall: {water_df['meeting_hall_m3'].min():.3f} - {water_df['meeting_hall_m3'].max():.3f}")
    print(f"  Workshop/maintenance: {water_df['workshop_maintenance_m3'].min():.3f} - {water_df['workshop_maintenance_m3'].max():.3f}")
    print(f"  Total community buildings: {water_df['total_community_buildings_m3'].min():.3f} - {water_df['total_community_buildings_m3'].max():.3f}")

    return energy_df, water_df


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Generate community building demand files')
    parser.add_argument('--office', type=float, default=500, help='Office area in m² (default: 500)')
    parser.add_argument('--storage', type=float, default=1000, help='Storage area in m² (default: 1000)')
    parser.add_argument('--meeting', type=float, default=300, help='Meeting hall area in m² (default: 300)')
    parser.add_argument('--workshop', type=float, default=200, help='Workshop area in m² (default: 200)')

    args = parser.parse_args()

    print("Generating community building demand files...")
    print("=" * 60)
    generate_community_building_demand(
        office_area_m2=args.office,
        storage_area_m2=args.storage,
        meeting_area_m2=args.meeting,
        workshop_area_m2=args.workshop
    )
    print("\nDone.")


if __name__ == "__main__":
    main()
