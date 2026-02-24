# Generate daily community building energy and water demand factors (per m²)
# Layer 1: Pre-computation
#
# Generates daily per-m² factors for community building energy and water demand based on weather.
# Office, meeting hall, workshop: cooling/ventilation multiplier model.
# Warehouses: physics-based degree-day model for conditioned types; ventilation multiplier for non-conditioned.
# Warehouse types: non_conditioned, climate_controlled (68°F/20°C), chilled (50°F/10°C).
# No area assumptions—downstream consumers multiply factors by their own building areas.

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


def load_building_data():
    """Load community building energy and water baseline data from building_demands factors."""
    building_path = get_project_root() / "data/building_demands/community_buildings_energy_water_factors-toy.csv"

    with open(building_path, "r") as f:
        lines = f.readlines()

    header_idx = 0
    for i, line in enumerate(lines):
        if not line.startswith("#"):
            header_idx = i
            break

    df = pd.read_csv(building_path, skiprows=header_idx)
    df.columns = df.columns.str.strip()
    return df


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


# Warehouse energy models (physics-based, reasonably insulated construction)
# Ref: ASHRAE/industry norms. U-values W/m²K, COP for cooling/refrigeration.
# Cooling load = U * (T_ambient - T_setpoint) * 24h / (COP * 1000) kWh/m²/day per °C above setpoint.

def calculate_non_conditioned_warehouse_kwh(base_kwh, temp_max):
    """Non-conditioned warehouse: ventilation-only. Base load with mild temp multiplier.

    Fans run more in hot weather. Multiplier 0.90 (cool) to 1.15 (hot).
    """
    if temp_max < 20:
        vent_mult = 0.90
    elif temp_max < 28:
        vent_mult = 1.0
    elif temp_max < 35:
        vent_mult = 1.08
    else:
        vent_mult = 1.15
    return base_kwh * vent_mult


def calculate_conditioned_warehouse_kwh(base_non_cooling_kwh, setpoint_c, cooling_coef, temp_max):
    """Conditioned warehouse cooling load: Q = base + coef * max(0, T_ambient - T_setpoint).

    coef derived from U (W/m²K), COP: k = U * 24 / (COP * 1000) kWh/m²/°C/day.
    Climate-controlled (20°C): U~0.55, COP 2.5 → 0.0053. Chilled (10°C): U~0.45, COP 2.0 → 0.0054.
    """
    degree_days_above = max(0.0, temp_max - setpoint_c)
    cooling_kwh = cooling_coef * degree_days_above
    return base_non_cooling_kwh + cooling_kwh


# Warehouse parameters (reasonably insulated: R-10 to R-20 equivalent)
# Setpoints: 68°F=20°C (climate-controlled), 50°F=10°C (chilled)
WAREHOUSE_CONFIG = {
    'non_conditioned_warehouse': {
        'model': 'ventilation',
        'base_kwh': 0.020,  # Lighting, fans, equipment (no HVAC)
    },
    'climate_controlled_warehouse': {
        'model': 'conditioned',
        'setpoint_c': 20,   # 68°F
        'base_kwh': 0.020, # Lighting, equipment, ventilation
        'cooling_coef': 0.0053,  # U=0.55 W/m²K, COP=2.5
    },
    'chilled_warehouse': {
        'model': 'conditioned',
        'setpoint_c': 10,   # 50°F
        'base_kwh': 0.040, # Lighting, equipment, refrigeration aux
        'cooling_coef': 0.0054,  # U=0.45 W/m²K, COP=2.0
    },
}


def generate_community_building_demand():
    """Generate daily per-m² energy and water demand factors for community building types."""
    print("Loading weather data...")
    weather = load_weather_data()

    print("Loading building specifications...")
    buildings = load_building_data()

    # Get base energy and water values per building type (per m²) from factors file
    building_specs = {}
    for _, row in buildings.iterrows():
        building_specs[row['building_type']] = {
            'kwh_per_m2': row['energy_per_m2_per_day_kwh'],
            'm3_per_m2': row['water_per_m2_per_day_m3']
        }

    building_types = [
        'office_admin',
        'non_conditioned_warehouse',
        'climate_controlled_warehouse',
        'chilled_warehouse',
        'meeting_hall',
        'workshop_maintenance',
    ]

    # Cooling/ventilation fraction for non-warehouse types
    cooling_fractions = {
        'office_admin': 0.50,
        'meeting_hall': 0.35,
        'workshop_maintenance': 0.35,
    }

    print(f"Processing {len(weather)} days of weather data...")
    print("Output: per-m² factors only (no area assumptions)")
    print("Warehouse types: non-conditioned, climate-controlled (20°C), chilled (10°C)")

    # Calculate daily factors
    dates = weather["date"].tolist()
    temp_max_values = weather["temp_max_c"].tolist()

    energy_data = []
    water_data = []

    for date, temp_max in zip(dates, temp_max_values):
        cooling_mult = calculate_cooling_multiplier(temp_max)
        water_mult = calculate_water_multiplier(temp_max)

        daily_energy = {"date": date}
        daily_water = {"date": date}

        for building_type in building_types:
            specs = building_specs[building_type]

            # Energy: warehouse types use physics-based model; others use cooling fraction
            if building_type in WAREHOUSE_CONFIG:
                cfg = WAREHOUSE_CONFIG[building_type]
                if cfg['model'] == 'ventilation':
                    adjusted_kwh_per_m2 = calculate_non_conditioned_warehouse_kwh(
                        cfg['base_kwh'], temp_max
                    )
                else:
                    adjusted_kwh_per_m2 = calculate_conditioned_warehouse_kwh(
                        cfg['base_kwh'],
                        cfg['setpoint_c'],
                        cfg['cooling_coef'],
                        temp_max,
                    )
            else:
                cooling_frac = cooling_fractions[building_type]
                non_cooling_frac = 1 - cooling_frac
                base_kwh_per_m2 = specs['kwh_per_m2']
                adjusted_kwh_per_m2 = base_kwh_per_m2 * (
                    non_cooling_frac + cooling_frac * cooling_mult
                )

            # Water factor: adjusted by temperature multiplier
            adjusted_m3_per_m2 = specs['m3_per_m2'] * water_mult

            daily_energy[f"{building_type}_kwh_per_m2"] = round(adjusted_kwh_per_m2, 4)
            daily_water[f"{building_type}_m3_per_m2"] = round(adjusted_m3_per_m2, 6)

        energy_data.append(daily_energy)
        water_data.append(daily_water)

    # Create DataFrames
    energy_df = pd.DataFrame(energy_data)
    water_df = pd.DataFrame(water_data)

    # Write output files
    output_dir = get_project_root() / "data/building_demands"
    output_dir.mkdir(parents=True, exist_ok=True)

    energy_path = output_dir / "community_buildings_energy_kwh_per_day-toy.csv"
    water_path = output_dir / "community_buildings_water_m3_per_day-toy.csv"

    # Energy file with metadata
    energy_header = """# SOURCE: Generated from weather and community building data
# DATE: {}
# DESCRIPTION: Daily per-m² energy demand factors. Warehouses: non-conditioned, climate-controlled (20°C), chilled (10°C).
# UNITS: date (YYYY-MM-DD), *_kwh_per_m2 (kWh/m²/day). Multiply by building area to get total kWh/day.
# LOGIC: Office/meeting/workshop: cooling fraction model. Warehouses: degree-day physics (non-conditioned; climate 20°C; chilled 10°C).
# DEPENDENCIES: daily_weather_scenario_001-toy.csv, community_buildings_energy_water_factors-toy.csv
# ASSUMPTIONS: None—factors only. Downstream consumers apply their own building areas.
""".format(datetime.now().strftime("%Y-%m-%d"))

    with open(energy_path, "w") as f:
        f.write(energy_header)
        energy_df.to_csv(f, index=False)

    # Water file with metadata
    water_header = """# SOURCE: Generated from weather and community building data
# DATE: {}
# DESCRIPTION: Daily per-m² water demand factors adjusted for temperature
# UNITS: date (YYYY-MM-DD), *_m3_per_m2 (m³/m²/day). Multiply by building area to get total m³/day.
# LOGIC: Base water from building specs, adjusted by temperature multiplier (higher in hot weather for cleaning)
# DEPENDENCIES: daily_weather_scenario_001-toy.csv, community_buildings_energy_water_factors-toy.csv
# ASSUMPTIONS: None—factors only. Downstream consumers apply their own building areas.
""".format(datetime.now().strftime("%Y-%m-%d"))

    with open(water_path, "w") as f:
        f.write(water_header)
        water_df.to_csv(f, index=False)

    print(f"\nGenerated files:")
    print(f"  - {energy_path}")
    print(f"  - {water_path}")

    # Summary statistics (per m²)
    print(f"\nEnergy factors (kWh/m²/day):")
    print(f"  Office/admin: {energy_df['office_admin_kwh_per_m2'].min():.4f} - {energy_df['office_admin_kwh_per_m2'].max():.4f}")
    print(f"  Non-conditioned warehouse: {energy_df['non_conditioned_warehouse_kwh_per_m2'].min():.4f} - {energy_df['non_conditioned_warehouse_kwh_per_m2'].max():.4f}")
    print(f"  Climate-controlled warehouse (20°C): {energy_df['climate_controlled_warehouse_kwh_per_m2'].min():.4f} - {energy_df['climate_controlled_warehouse_kwh_per_m2'].max():.4f}")
    print(f"  Chilled warehouse (10°C): {energy_df['chilled_warehouse_kwh_per_m2'].min():.4f} - {energy_df['chilled_warehouse_kwh_per_m2'].max():.4f}")
    print(f"  Meeting hall: {energy_df['meeting_hall_kwh_per_m2'].min():.4f} - {energy_df['meeting_hall_kwh_per_m2'].max():.4f}")
    print(f"  Workshop/maintenance: {energy_df['workshop_maintenance_kwh_per_m2'].min():.4f} - {energy_df['workshop_maintenance_kwh_per_m2'].max():.4f}")

    print(f"\nWater factors (m³/m²/day):")
    print(f"  Office/admin: {water_df['office_admin_m3_per_m2'].min():.6f} - {water_df['office_admin_m3_per_m2'].max():.6f}")
    print(f"  Non-conditioned warehouse: {water_df['non_conditioned_warehouse_m3_per_m2'].min():.6f} - {water_df['non_conditioned_warehouse_m3_per_m2'].max():.6f}")
    print(f"  Climate-controlled warehouse: {water_df['climate_controlled_warehouse_m3_per_m2'].min():.6f} - {water_df['climate_controlled_warehouse_m3_per_m2'].max():.6f}")
    print(f"  Chilled warehouse: {water_df['chilled_warehouse_m3_per_m2'].min():.6f} - {water_df['chilled_warehouse_m3_per_m2'].max():.6f}")
    print(f"  Meeting hall: {water_df['meeting_hall_m3_per_m2'].min():.6f} - {water_df['meeting_hall_m3_per_m2'].max():.6f}")
    print(f"  Workshop/maintenance: {water_df['workshop_maintenance_m3_per_m2'].min():.6f} - {water_df['workshop_maintenance_m3_per_m2'].max():.6f}")

    return energy_df, water_df


def main():
    """Main entry point."""
    print("Generating community building demand factors...")
    print("=" * 60)
    generate_community_building_demand()
    print("\nDone.")


if __name__ == "__main__":
    main()
