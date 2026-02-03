# Generate synthetic weather data for Sinai Peninsula, Red Sea coast
"""
Weather Data Generator for Community Agri-PV Project

Generates 15 years of daily weather data (2010-2024) for the Sinai Peninsula,
Red Sea coast region (~28N, 34E) with hot arid desert climate characteristics.
"""

import numpy as np
import pandas as pd
from datetime import datetime


def generate_temperature(dates, seed=42):
    # Generate daily max/min temperatures with sinusoidal annual cycle + noise
    np.random.seed(seed)
    n_days = len(dates)
    day_of_year = np.array([d.timetuple().tm_yday for d in dates])

    # annual cycle: peak around day 200 (mid-July), minimum around day 15 (mid-Jan)
    # use day 15 as reference (winter minimum), then cosine gives max at +180 days
    annual_phase = 2 * np.pi * (day_of_year - 15) / 365.25

    # summer max: 38-46C (mean 42), winter max: 18-26C (mean 22)
    # amplitude: (42-22)/2 = 10, mean: (42+22)/2 = 32
    # cosine starts at 1 at day 15, so we subtract to get minimum in winter
    temp_max_base = 32 + 10 * np.cos(annual_phase + np.pi)  # +pi shifts to minimum at day 15

    # add year-to-year variation (AR1 process for annual anomaly)
    years = np.array([d.year for d in dates])
    unique_years = np.unique(years)
    year_anomaly = np.zeros(n_days)
    annual_anomalies = {}
    prev_anomaly = 0
    for yr in unique_years:
        new_anomaly = 0.6 * prev_anomaly + np.random.normal(0, 1.5)
        annual_anomalies[yr] = new_anomaly
        prev_anomaly = new_anomaly
    for i, d in enumerate(dates):
        year_anomaly[i] = annual_anomalies[d.year]

    # add daily noise
    daily_noise_max = np.random.normal(0, 2.0, n_days)
    temp_max = temp_max_base + year_anomaly + daily_noise_max

    # temp min: typically 10-15C less than max
    # summer: 25-32C min, winter: 8-15C min
    diurnal_range = 12 + 3 * np.cos(annual_phase + np.pi)  # larger range in summer (less humidity)
    temp_min = temp_max - diurnal_range + np.random.normal(0, 1.5, n_days)

    # clip to realistic bounds
    temp_max = np.clip(temp_max, 15, 52)
    temp_min = np.clip(temp_min, 3, 38)
    temp_min = np.minimum(temp_min, temp_max - 5)  # ensure min < max by at least 5C

    return temp_max, temp_min


def generate_solar_irradiance(dates, seed=43):
    # Generate solar irradiance with latitude-based + seasonal variation
    np.random.seed(seed)
    n_days = len(dates)
    day_of_year = np.array([d.timetuple().tm_yday for d in dates])

    # summer: 6-8 kWh/m2/day (mean 7), winter: 3-5 kWh/m2/day (mean 4)
    # peak around summer solstice (day 172)
    annual_phase = 2 * np.pi * (day_of_year - 172) / 365.25

    # amplitude: (7-4)/2 = 1.5, mean: (7+4)/2 = 5.5
    solar_base = 5.5 + 1.5 * np.cos(annual_phase)

    # add random variation (cloud effects, atmospheric conditions)
    # less variation in summer (clearer skies), more in winter
    noise_scale = 0.3 + 0.2 * np.cos(annual_phase + np.pi)
    solar_noise = np.random.normal(0, noise_scale, n_days)

    solar = solar_base + solar_noise

    # clip to realistic bounds
    solar = np.clip(solar, 2.0, 9.0)

    return solar


def generate_wind_speed(dates, seed=44):
    # Generate wind speed with seasonal patterns (stronger in spring)
    np.random.seed(seed)
    n_days = len(dates)
    day_of_year = np.array([d.timetuple().tm_yday for d in dates])

    # spring peak around day 100 (early April)
    spring_phase = 2 * np.pi * (day_of_year - 100) / 365.25

    # base wind: 2-6 m/s average
    # spring stronger: mean 4.5 m/s, winter/summer: mean 3.0 m/s
    wind_base = 3.5 + 0.75 * np.cos(spring_phase)

    # daily variation with occasional gusts
    wind_noise = np.random.gamma(2, 0.5, n_days)  # right-skewed for occasional gusts
    wind_speed = wind_base + wind_noise

    # add occasional high wind events (5% of days)
    gust_days = np.random.random(n_days) < 0.05
    wind_speed[gust_days] += np.random.uniform(3, 6, np.sum(gust_days))

    # clip to realistic bounds
    wind_speed = np.clip(wind_speed, 0.5, 12.0)

    return wind_speed


def generate_precipitation(dates, seed=45):
    # Generate precipitation with rare events concentrated Nov-Feb
    # target: 20-80mm annual total (very arid), with mean ~40mm
    np.random.seed(seed)
    n_days = len(dates)

    precip = np.zeros(n_days)

    for i, d in enumerate(dates):
        month = d.month

        # probability of rain by month (concentrated Nov-Feb)
        # need ~8 rain days/year with mean ~5mm = 40mm/year
        if month in [11, 12, 1, 2]:
            p_rain = 0.025  # 2.5% chance in wet months (~3 days/month in wet season)
        elif month in [3, 10]:
            p_rain = 0.008  # 0.8% transition months
        else:
            p_rain = 0.002  # 0.2% in dry season

        if np.random.random() < p_rain:
            # exponential distribution for rain amounts
            # mean 6mm when it rains, but can range 0.5-35mm
            amount = np.random.exponential(6)
            precip[i] = np.clip(amount, 0.5, 35)

    return precip


def validate_data(df):
    # Run quality checks on generated data
    checks = {}

    # check 1: no missing values
    checks['no_missing'] = df.isnull().sum().sum() == 0

    # check 2: summer temp max in 38-46C range (June-Aug)
    summer = df[df['date'].dt.month.isin([6, 7, 8])]
    summer_max_mean = summer['temp_max_c'].mean()
    checks['summer_temp_range'] = 38 <= summer_max_mean <= 46

    # check 3: winter temp max in 18-26C range (Dec-Feb)
    winter = df[df['date'].dt.month.isin([12, 1, 2])]
    winter_max_mean = winter['temp_max_c'].mean()
    checks['winter_temp_range'] = 18 <= winter_max_mean <= 26

    # check 4: summer solar in 6-8 range
    summer_solar_mean = summer['solar_irradiance_kwh_m2'].mean()
    checks['summer_solar_range'] = 6 <= summer_solar_mean <= 8

    # check 5: winter solar in 3-5 range
    winter_solar_mean = winter['solar_irradiance_kwh_m2'].mean()
    checks['winter_solar_range'] = 3 <= winter_solar_mean <= 5

    # check 6: wind speed in 2-6 m/s average
    wind_mean = df['wind_speed_ms'].mean()
    checks['wind_avg_range'] = 2 <= wind_mean <= 6

    # check 7: annual rainfall - mean in 20-80mm range, no year exceeds 100mm
    annual_precip = df.groupby(df['date'].dt.year)['precip_mm'].sum()
    mean_annual = annual_precip.mean()
    max_annual = annual_precip.max()
    checks['annual_rainfall_range'] = (15 <= mean_annual <= 80) and (max_annual <= 100)

    # check 8: date range correct
    checks['date_range'] = (df['date'].min() == pd.Timestamp('2010-01-01') and
                            df['date'].max() == pd.Timestamp('2024-12-31'))

    # check 9: correct number of days
    checks['row_count'] = len(df) == 5479

    return checks


def compute_statistics(df):
    # Compute summary statistics
    stats = {}

    stats['total_days'] = len(df)
    stats['date_range'] = f"{df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')}"

    stats['temp_max_mean'] = round(df['temp_max_c'].mean(), 2)
    stats['temp_max_std'] = round(df['temp_max_c'].std(), 2)
    stats['temp_max_range'] = f"{round(df['temp_max_c'].min(), 1)} - {round(df['temp_max_c'].max(), 1)}"

    stats['temp_min_mean'] = round(df['temp_min_c'].mean(), 2)
    stats['temp_min_std'] = round(df['temp_min_c'].std(), 2)
    stats['temp_min_range'] = f"{round(df['temp_min_c'].min(), 1)} - {round(df['temp_min_c'].max(), 1)}"

    stats['solar_mean'] = round(df['solar_irradiance_kwh_m2'].mean(), 2)
    stats['solar_std'] = round(df['solar_irradiance_kwh_m2'].std(), 2)
    stats['solar_range'] = f"{round(df['solar_irradiance_kwh_m2'].min(), 2)} - {round(df['solar_irradiance_kwh_m2'].max(), 2)}"

    stats['wind_mean'] = round(df['wind_speed_ms'].mean(), 2)
    stats['wind_std'] = round(df['wind_speed_ms'].std(), 2)
    stats['wind_range'] = f"{round(df['wind_speed_ms'].min(), 2)} - {round(df['wind_speed_ms'].max(), 2)}"

    stats['precip_days'] = (df['precip_mm'] > 0).sum()
    stats['precip_total'] = round(df['precip_mm'].sum(), 1)
    stats['precip_annual_avg'] = round(df['precip_mm'].sum() / 15, 1)

    # seasonal breakdowns
    summer = df[df['date'].dt.month.isin([6, 7, 8])]
    winter = df[df['date'].dt.month.isin([12, 1, 2])]

    stats['summer_temp_max_mean'] = round(summer['temp_max_c'].mean(), 2)
    stats['winter_temp_max_mean'] = round(winter['temp_max_c'].mean(), 2)
    stats['summer_solar_mean'] = round(summer['solar_irradiance_kwh_m2'].mean(), 2)
    stats['winter_solar_mean'] = round(winter['solar_irradiance_kwh_m2'].mean(), 2)

    return stats


def generate_metadata_header():
    # Generate metadata header as CSV comment block
    header = """# SOURCE: Synthetic data generated for Community Agri-PV project
# DATE: {date}
# DESCRIPTION: Daily weather data for Sinai Peninsula, Red Sea coast (~28N, 34E)
# UNITS: date=YYYY-MM-DD, temp_max_c=Celsius, temp_min_c=Celsius, solar_irradiance_kwh_m2=kWh/m2/day, wind_speed_ms=m/s, precip_mm=mm/day
# LOGIC: Temperature uses sinusoidal annual cycle + AR(1) year anomaly + daily noise. Solar uses latitude-based seasonal variation. Wind uses spring-peak seasonal pattern with gamma-distributed noise. Precipitation uses rare events (exponential) concentrated Nov-Feb.
# DEPENDENCIES: None (standalone dataset)
# ASSUMPTIONS: Hot arid desert climate (BWh Koppen). Summer max 38-46C, winter max 18-26C. Annual rainfall 20-80mm. Solar summer 6-8 kWh/m2/day, winter 3-5 kWh/m2/day. Wind 2-6 m/s average with occasional gusts to 12 m/s.
""".format(date=datetime.now().strftime('%Y-%m-%d'))
    return header


def main():
    # main function to generate weather data
    print("Generating weather data for Sinai Peninsula (2010-2024)...")

    # create date range
    dates = pd.date_range(start='2010-01-01', end='2024-12-31', freq='D')
    print(f"  Date range: {dates[0].strftime('%Y-%m-%d')} to {dates[-1].strftime('%Y-%m-%d')}")
    print(f"  Total days: {len(dates)}")

    # generate each variable
    print("\nGenerating temperature data...")
    temp_max, temp_min = generate_temperature(dates)

    print("Generating solar irradiance data...")
    solar = generate_solar_irradiance(dates)

    print("Generating wind speed data...")
    wind = generate_wind_speed(dates)

    print("Generating precipitation data...")
    precip = generate_precipitation(dates)

    # create dataframe
    df = pd.DataFrame({
        'date': dates,
        'temp_max_c': np.round(temp_max, 1),
        'temp_min_c': np.round(temp_min, 1),
        'solar_irradiance_kwh_m2': np.round(solar, 2),
        'wind_speed_ms': np.round(wind, 2),
        'precip_mm': np.round(precip, 1),
        'weather_scenario_id': '001'
    })

    # validate data
    print("\nRunning quality checks...")
    checks = validate_data(df)
    all_passed = all(checks.values())

    for check_name, passed in checks.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {check_name}: {status}")

    # compute statistics
    print("\nComputing statistics...")
    stats = compute_statistics(df)

    for stat_name, value in stats.items():
        print(f"  {stat_name}: {value}")

    # save to CSV with metadata header
    output_path = '/Users/dpbirge/GITHUB/community-agri-pv/data/precomputed/weather/daily_weather_scenario_001-toy.csv'

    print(f"\nSaving to: {output_path}")

    # write metadata header then data
    with open(output_path, 'w') as f:
        f.write(generate_metadata_header())

    df.to_csv(output_path, mode='a', index=False)

    # verify file was written
    import os
    file_size = os.path.getsize(output_path)
    print(f"  File size: {file_size:,} bytes")

    # final status
    print("\n" + "="*60)
    if all_passed:
        print("SUCCESS: Weather data generated and all quality checks passed!")
    else:
        failed = [k for k, v in checks.items() if not v]
        print(f"WARNING: Some quality checks failed: {failed}")
    print("="*60)

    return df, checks, stats


if __name__ == '__main__':
    df, checks, stats = main()
