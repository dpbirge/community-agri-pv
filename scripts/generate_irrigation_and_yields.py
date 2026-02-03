# Generate irrigation demand and crop yield datasets for Task 9
"""
Script for generating irrigation demand and crop yield toy datasets.

Uses FAO Penman-Monteith simplified ET0 formula with crop coefficients to compute
daily irrigation requirements, and applies weather stress factors to compute yields.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import math

# Paths
BASE_DIR = Path("/Users/dpbirge/GITHUB/community-agri-pv")
WEATHER_FILE = BASE_DIR / "data/precomputed/weather/daily_weather_scenario_001-toy.csv"
CROP_COEFF_FILE = BASE_DIR / "data/parameters/crops/crop_coefficients-toy.csv"
GROWTH_STAGES_FILE = BASE_DIR / "data/parameters/crops/growth_stages-toy.csv"
IRRIGATION_OUTPUT_DIR = BASE_DIR / "data/precomputed/irrigation_demand"
YIELD_OUTPUT_DIR = BASE_DIR / "data/precomputed/crop_yields"

# Constants
LATITUDE = 28.0  # Sinai Peninsula
DRIP_EFFICIENCY = 0.90

# Baseline yields (kg/ha)
BASELINE_YIELDS = {
    "tomato": 70000,
    "potato": 35000,
    "onion": 45000,
    "kale": 20000,
    "cucumber": 50000,
}

# Planting dates to model (3-4 per crop spread throughout year)
PLANTING_DATES = {
    "tomato": ["2010-02-15", "2010-05-01", "2010-08-15", "2010-11-01"],
    "potato": ["2010-01-15", "2010-04-15", "2010-09-01", "2010-11-15"],
    "onion": ["2010-02-01", "2010-06-01", "2010-09-15"],
    "kale": ["2010-01-01", "2010-03-15", "2010-07-01", "2010-10-01"],
    "cucumber": ["2010-03-01", "2010-06-15", "2010-09-01", "2010-11-15"],
}


def load_weather_data():
    """Load weather data, skipping metadata header lines."""
    with open(WEATHER_FILE, "r") as f:
        lines = f.readlines()

    # Find header row (first non-comment line)
    header_idx = 0
    for i, line in enumerate(lines):
        if not line.startswith("#"):
            header_idx = i
            break

    df = pd.read_csv(WEATHER_FILE, skiprows=header_idx)
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_crop_coefficients():
    """Load crop coefficients, skipping metadata header lines."""
    with open(CROP_COEFF_FILE, "r") as f:
        lines = f.readlines()

    header_idx = 0
    for i, line in enumerate(lines):
        if not line.startswith("#"):
            header_idx = i
            break

    return pd.read_csv(CROP_COEFF_FILE, skiprows=header_idx)


def load_growth_stages():
    """Load growth stages, skipping metadata header lines."""
    with open(GROWTH_STAGES_FILE, "r") as f:
        lines = f.readlines()

    header_idx = 0
    for i, line in enumerate(lines):
        if not line.startswith("#"):
            header_idx = i
            break

    return pd.read_csv(GROWTH_STAGES_FILE, skiprows=header_idx)


def calculate_ra(doy, lat_rad):
    """
    Calculate extraterrestrial radiation Ra (MJ/m2/day).

    Uses standard FAO formulas for daily extraterrestrial radiation based on
    day of year and latitude.
    """
    # Solar constant
    Gsc = 0.0820  # MJ/m2/min

    # Inverse relative distance Earth-Sun
    dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)

    # Solar declination
    delta = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)

    # Sunset hour angle
    ws = math.acos(-math.tan(lat_rad) * math.tan(delta))

    # Extraterrestrial radiation
    Ra = (24 * 60 / math.pi) * Gsc * dr * (
        ws * math.sin(lat_rad) * math.sin(delta) +
        math.cos(lat_rad) * math.cos(delta) * math.sin(ws)
    )

    return Ra


def calculate_et0_hargreaves(tmax, tmin, ra):
    """
    Calculate reference ET0 using Hargreaves-Samani equation.

    ET0 = 0.0023 * (Tmean + 17.8) * (Tmax - Tmin)^0.5 * Ra

    Ra is in MJ/m2/day, result is in mm/day.
    """
    tmean = (tmax + tmin) / 2
    tdiff = max(tmax - tmin, 0)  # Ensure non-negative

    # Convert Ra from MJ/m2/day to mm/day equivalent (divide by latent heat ~2.45 MJ/kg)
    ra_mm = ra / 2.45

    et0 = 0.0023 * (tmean + 17.8) * (tdiff ** 0.5) * ra_mm
    return max(et0, 0)


def get_growth_stage_and_kc(crop_name, crop_day, growth_stages_df, crop_coeff_df):
    """
    Determine growth stage and interpolated Kc for a given crop day.

    Uses linear interpolation within each stage to transition between Kc values.
    """
    crop_stages = growth_stages_df[growth_stages_df["crop_name"] == crop_name].copy()
    crop_coeff = crop_coeff_df[crop_coeff_df["crop_name"] == crop_name].iloc[0]

    # Build cumulative day ranges for each stage
    cumulative_days = 0
    for _, stage in crop_stages.iterrows():
        stage_start = cumulative_days
        stage_end = cumulative_days + stage["duration_days"]

        if stage_start < crop_day <= stage_end:
            stage_name = stage["stage"]
            stage_kc = stage["kc"]

            # Calculate position within stage (0 to 1)
            days_into_stage = crop_day - stage_start
            stage_progress = days_into_stage / stage["duration_days"]

            # Get Kc values for interpolation
            if stage_name == "initial":
                kc_start = crop_coeff["kc_initial"]
                kc_end = stage_kc
            elif stage_name == "development":
                kc_start = crop_coeff["kc_initial"]
                kc_end = crop_coeff["kc_mid"]
            elif stage_name == "mid":
                kc_start = crop_coeff["kc_mid"]
                kc_end = crop_coeff["kc_mid"]
            else:  # late
                kc_start = crop_coeff["kc_mid"]
                kc_end = crop_coeff["kc_end"]

            kc = kc_start + (kc_end - kc_start) * stage_progress
            return stage_name, kc

        cumulative_days = stage_end

    # Default to late stage if beyond expected duration
    return "late", crop_coeff["kc_end"]


def calculate_weather_stress_factor(weather_during_season, crop_name):
    """
    Calculate weather stress factor based on growing season conditions.

    Returns a factor between 0.85 and 1.15 based on temperature extremes.
    Crops are stressed by extreme heat (>40C) and benefit from moderate temps.
    """
    avg_tmax = weather_during_season["temp_max_c"].mean()
    extreme_heat_days = (weather_during_season["temp_max_c"] > 40).sum()
    cool_days = (weather_during_season["temp_max_c"] < 25).sum()
    total_days = len(weather_during_season)

    # Base stress factor
    stress = 1.0

    # Penalty for extreme heat days (proportional to fraction of season)
    if extreme_heat_days > 0:
        heat_penalty = 0.15 * (extreme_heat_days / total_days) * 2  # Up to 15% reduction
        stress -= min(heat_penalty, 0.15)

    # Slight benefit for cool days (less stress) but not too many
    cool_fraction = cool_days / total_days
    if 0.1 < cool_fraction < 0.4:
        stress += 0.05  # Slight boost for moderate conditions

    # Add small random variation
    np.random.seed(hash(crop_name + str(weather_during_season["date"].iloc[0])) % (2**32))
    stress += np.random.uniform(-0.03, 0.03)

    return max(0.85, min(1.15, stress))


def generate_irrigation_data(crop_name, planting_dates, weather_df, crop_coeff_df, growth_stages_df):
    """Generate irrigation demand data for a single crop."""
    crop_coeff = crop_coeff_df[crop_coeff_df["crop_name"] == crop_name].iloc[0]
    season_length = int(crop_coeff["season_length_days"])
    lat_rad = math.radians(LATITUDE)

    all_rows = []

    # Generate for multiple years worth of planting dates
    for base_date in planting_dates:
        base_date_parsed = pd.to_datetime(base_date)

        # Generate for all years in dataset
        for year_offset in range(15):  # 2010-2024
            planting_date = base_date_parsed + pd.DateOffset(years=year_offset)

            # Skip if season would extend beyond weather data
            harvest_date = planting_date + timedelta(days=season_length)
            if harvest_date > weather_df["date"].max():
                continue
            if planting_date < weather_df["date"].min():
                continue

            for crop_day in range(1, season_length + 1):
                calendar_date = planting_date + timedelta(days=crop_day - 1)

                # Get weather for this day
                weather_row = weather_df[weather_df["date"] == calendar_date]
                if len(weather_row) == 0:
                    continue
                weather_row = weather_row.iloc[0]

                # Calculate ET0
                doy = calendar_date.timetuple().tm_yday
                ra = calculate_ra(doy, lat_rad)
                et0 = calculate_et0_hargreaves(
                    weather_row["temp_max_c"],
                    weather_row["temp_min_c"],
                    ra
                )

                # Get growth stage and Kc
                stage, kc = get_growth_stage_and_kc(
                    crop_name, crop_day, growth_stages_df, crop_coeff_df
                )

                # Calculate ETc
                etc = et0 * kc

                # Calculate irrigation (mm to m3/ha, accounting for drip efficiency)
                # 1 mm on 1 ha = 10 m3, divide by efficiency
                irrigation_m3_per_ha = (etc * 10) / DRIP_EFFICIENCY

                all_rows.append({
                    "weather_scenario_id": "001",
                    "planting_date": planting_date.strftime("%Y-%m-%d"),
                    "crop_day": crop_day,
                    "calendar_date": calendar_date.strftime("%Y-%m-%d"),
                    "growth_stage": stage,
                    "kc": round(kc, 3),
                    "et0_mm": round(et0, 2),
                    "etc_mm": round(etc, 2),
                    "irrigation_m3_per_ha_per_day": round(irrigation_m3_per_ha, 2),
                })

    return pd.DataFrame(all_rows)


def generate_yield_data(crop_name, planting_dates, weather_df, crop_coeff_df):
    """Generate crop yield data for a single crop."""
    crop_coeff = crop_coeff_df[crop_coeff_df["crop_name"] == crop_name].iloc[0]
    season_length = int(crop_coeff["season_length_days"])
    baseline_yield = BASELINE_YIELDS[crop_name]

    all_rows = []

    for base_date in planting_dates:
        base_date_parsed = pd.to_datetime(base_date)

        for year_offset in range(15):  # 2010-2024
            planting_date = base_date_parsed + pd.DateOffset(years=year_offset)
            harvest_date = planting_date + timedelta(days=season_length)

            # Skip if season would extend beyond weather data
            if harvest_date > weather_df["date"].max():
                continue
            if planting_date < weather_df["date"].min():
                continue

            # Get weather during growing season
            season_mask = (weather_df["date"] >= planting_date) & (weather_df["date"] < harvest_date)
            season_weather = weather_df[season_mask]

            if len(season_weather) < season_length * 0.9:
                continue

            # Calculate weather stress factor
            weather_stress = calculate_weather_stress_factor(season_weather, crop_name)

            # Assume full irrigation (water stress = 1.0)
            water_stress = 1.0

            # Calculate final yield
            final_yield = baseline_yield * weather_stress * water_stress

            all_rows.append({
                "weather_scenario_id": "001",
                "planting_date": planting_date.strftime("%Y-%m-%d"),
                "harvest_date": harvest_date.strftime("%Y-%m-%d"),
                "yield_kg_per_ha": round(final_yield, 0),
                "season_length_actual_days": season_length,
                "weather_stress_factor": round(weather_stress, 3),
                "water_stress_factor": round(water_stress, 3),
            })

    return pd.DataFrame(all_rows)


def write_irrigation_file(crop_name, df):
    """Write irrigation demand CSV with metadata header."""
    output_path = IRRIGATION_OUTPUT_DIR / f"irrigation_m3_per_ha_{crop_name}-toy.csv"

    metadata = f"""# SOURCE: Computed from FAO Penman-Monteith ET0 (Hargreaves-Samani simplified) + FAO-56 crop coefficients
# DATE: {datetime.now().strftime("%Y-%m-%d")}
# DESCRIPTION: Daily irrigation demand for {crop_name} crops in Sinai Red Sea region
# UNITS:
#   - weather_scenario_id: Scenario identifier (text)
#   - planting_date: Date crop was planted (YYYY-MM-DD)
#   - crop_day: Days since planting (1 to season_length)
#   - calendar_date: Actual calendar date (YYYY-MM-DD)
#   - growth_stage: Crop growth stage (initial/development/mid/late)
#   - kc: Crop coefficient for this day (dimensionless)
#   - et0_mm: Reference evapotranspiration (mm/day)
#   - etc_mm: Crop evapotranspiration = ET0 x Kc (mm/day)
#   - irrigation_m3_per_ha_per_day: Water requirement per hectare (m3/ha/day)
# LOGIC: ET0 = 0.0023 * (Tmean + 17.8) * (Tmax - Tmin)^0.5 * Ra; ETc = ET0 x Kc; Irrigation = ETc x 10 / 0.9 (90% drip efficiency)
# DEPENDENCIES: daily_weather_scenario_001-toy.csv, crop_coefficients-toy.csv, growth_stages-toy.csv
# ASSUMPTIONS: Drip irrigation at 90% efficiency, no rainfall credit, no soil water storage
"""

    with open(output_path, "w") as f:
        f.write(metadata)
        df.to_csv(f, index=False)

    return output_path


def write_yield_file(crop_name, df):
    """Write crop yield CSV with metadata header."""
    output_path = YIELD_OUTPUT_DIR / f"yield_kg_per_ha_{crop_name}-toy.csv"

    metadata = f"""# SOURCE: Computed from baseline yields adjusted for weather stress
# DATE: {datetime.now().strftime("%Y-%m-%d")}
# DESCRIPTION: Crop yields for {crop_name} in Sinai Red Sea region under various planting dates
# UNITS:
#   - weather_scenario_id: Scenario identifier (text)
#   - planting_date: Date crop was planted (YYYY-MM-DD)
#   - harvest_date: Date crop was harvested (YYYY-MM-DD)
#   - yield_kg_per_ha: Total harvest yield (kg/ha)
#   - season_length_actual_days: Actual growing season duration (days)
#   - weather_stress_factor: Yield multiplier from weather conditions (0.85-1.15)
#   - water_stress_factor: Yield multiplier from water availability (1.0 = full irrigation)
# LOGIC: yield = baseline_yield x weather_stress x water_stress; weather_stress based on extreme heat days and temperature averages
# DEPENDENCIES: daily_weather_scenario_001-toy.csv, crop_coefficients-toy.csv
# ASSUMPTIONS: Full irrigation (water_stress=1.0), no pest/disease losses, professional farm management
"""

    with open(output_path, "w") as f:
        f.write(metadata)
        df.to_csv(f, index=False)

    return output_path


def main():
    print("Loading input data...")
    weather_df = load_weather_data()
    crop_coeff_df = load_crop_coefficients()
    growth_stages_df = load_growth_stages()

    print(f"Weather data: {len(weather_df)} days ({weather_df['date'].min()} to {weather_df['date'].max()})")
    print(f"Crops: {list(crop_coeff_df['crop_name'])}")

    crops = ["tomato", "potato", "onion", "kale", "cucumber"]

    irrigation_stats = {}
    yield_stats = {}

    for crop in crops:
        print(f"\nProcessing {crop}...")

        # Generate irrigation data
        irrigation_df = generate_irrigation_data(
            crop, PLANTING_DATES[crop], weather_df, crop_coeff_df, growth_stages_df
        )
        irrigation_path = write_irrigation_file(crop, irrigation_df)
        irrigation_stats[crop] = {
            "rows": len(irrigation_df),
            "planting_dates": irrigation_df["planting_date"].nunique(),
            "avg_irrigation_m3": irrigation_df["irrigation_m3_per_ha_per_day"].mean(),
            "max_irrigation_m3": irrigation_df["irrigation_m3_per_ha_per_day"].max(),
            "avg_et0": irrigation_df["et0_mm"].mean(),
            "path": str(irrigation_path),
        }
        print(f"  Irrigation: {len(irrigation_df)} rows, {irrigation_stats[crop]['planting_dates']} planting dates")

        # Generate yield data
        yield_df = generate_yield_data(
            crop, PLANTING_DATES[crop], weather_df, crop_coeff_df
        )
        yield_path = write_yield_file(crop, yield_df)
        yield_stats[crop] = {
            "rows": len(yield_df),
            "avg_yield": yield_df["yield_kg_per_ha"].mean(),
            "min_yield": yield_df["yield_kg_per_ha"].min(),
            "max_yield": yield_df["yield_kg_per_ha"].max(),
            "avg_weather_stress": yield_df["weather_stress_factor"].mean(),
            "path": str(yield_path),
        }
        print(f"  Yield: {len(yield_df)} rows, avg yield {yield_stats[crop]['avg_yield']:.0f} kg/ha")

    print("\n" + "="*60)
    print("IRRIGATION DEMAND SUMMARY")
    print("="*60)
    for crop, stats in irrigation_stats.items():
        print(f"\n{crop.upper()}:")
        print(f"  File: {stats['path']}")
        print(f"  Total rows: {stats['rows']:,}")
        print(f"  Unique planting dates: {stats['planting_dates']}")
        print(f"  Avg daily irrigation: {stats['avg_irrigation_m3']:.2f} m3/ha")
        print(f"  Max daily irrigation: {stats['max_irrigation_m3']:.2f} m3/ha")
        print(f"  Avg ET0: {stats['avg_et0']:.2f} mm/day")

    print("\n" + "="*60)
    print("CROP YIELD SUMMARY")
    print("="*60)
    for crop, stats in yield_stats.items():
        print(f"\n{crop.upper()}:")
        print(f"  File: {stats['path']}")
        print(f"  Total rows: {stats['rows']}")
        print(f"  Yield range: {stats['min_yield']:,.0f} - {stats['max_yield']:,.0f} kg/ha")
        print(f"  Avg yield: {stats['avg_yield']:,.0f} kg/ha")
        print(f"  Avg weather stress factor: {stats['avg_weather_stress']:.3f}")

    print("\nGeneration complete!")


if __name__ == "__main__":
    main()
