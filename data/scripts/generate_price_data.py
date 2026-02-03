# Price Time-Series Data Generator for Community Agri-PV Project
# Generates synthetic toy price datasets for Egypt/Sinai Red Sea region
# Uses sinusoidal seasonality + AR(1) process + random shocks

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

np.random.seed(42)

# Configuration
START_DATE = "2015-01-01"
END_DATE = "2024-12-31"
# BASE_PATH points to data/prices/ from scripts/ directory
BASE_PATH = Path(__file__).parent.parent / "data" / "prices"

# Exchange rate history (EGP to USD) - reflecting gradual devaluation 2015-2024
EGP_USD_RATES = {
    2015: 7.63, 2016: 9.10, 2017: 17.78, 2018: 17.83, 2019: 16.55,
    2020: 15.76, 2021: 15.66, 2022: 19.16, 2023: 30.85, 2024: 48.50
}

# Crop price configurations (wholesale USD/kg)
CROP_CONFIGS = {
    "tomato": {"min": 0.50, "max": 1.20, "harvest_months": [3, 4, 5, 9, 10, 11], "volatility": 0.25},
    "potato": {"min": 0.30, "max": 0.80, "harvest_months": [3, 4, 5, 10, 11], "volatility": 0.20},
    "onion": {"min": 0.25, "max": 0.70, "harvest_months": [4, 5, 6, 11, 12], "volatility": 0.18},
    "kale": {"min": 1.50, "max": 3.00, "harvest_months": [10, 11, 12, 1, 2, 3], "volatility": 0.22},
    "cucumber": {"min": 0.60, "max": 1.40, "harvest_months": [4, 5, 6, 7, 8, 9], "volatility": 0.23}
}

# Processing value-add multipliers
VALUE_ADD_MULTIPLIERS = {
    "dried": {"min": 2.0, "max": 3.0},
    "canned": {"min": 1.5, "max": 2.0},
    "packaged": {"min": 1.2, "max": 1.4}
}


def get_season(month):
    """Determine season from month (Northern hemisphere)."""
    if month in [12, 1, 2]:
        return "winter"
    elif month in [3, 4, 5]:
        return "spring"
    elif month in [6, 7, 8]:
        return "summer"
    return "fall"


def get_market_condition(price, low_thresh, high_thresh):
    """Classify market condition based on price relative to thresholds."""
    if price <= low_thresh:
        return "low"
    elif price >= high_thresh:
        return "high"
    return "medium"


def generate_crop_prices(crop_name, config, dates):
    """
    Generate synthetic crop prices using sinusoidal seasonality + AR(1) + random shocks.

    Prices are lower during harvest months (supply high) and higher off-season.
    """
    n = len(dates)
    price_min, price_max = config["min"], config["max"]
    harvest_months = config["harvest_months"]
    volatility = config["volatility"]

    # Mean price and amplitude for seasonal variation
    mean_price = (price_min + price_max) / 2
    amplitude = (price_max - price_min) / 3  # Seasonal swing ~2/3 of range

    # Generate base seasonal pattern (prices LOW during harvest, HIGH off-season)
    seasonal = []
    for d in dates:
        month = d.month
        # Calculate distance from nearest harvest month
        harvest_effect = min([min(abs(month - hm), abs(month - hm + 12), abs(month - hm - 12))
                             for hm in harvest_months])
        # Normalize: 0 = harvest (low price), 6 = farthest from harvest (high price)
        seasonal_factor = (harvest_effect / 6) * amplitude
        seasonal.append(mean_price + seasonal_factor)

    seasonal = np.array(seasonal)

    # Add AR(1) process for persistence
    ar_coef = 0.7  # Persistence coefficient
    ar_term = np.zeros(n)
    for i in range(1, n):
        ar_term[i] = ar_coef * ar_term[i-1] + np.random.normal(0, volatility * 0.3)

    # Add random shocks (occasionally large, e.g., supply disruptions)
    shocks = np.random.normal(0, volatility * 0.2, n)

    # Add rare large shocks (5% of months)
    large_shock_indices = np.random.choice(n, size=int(n * 0.05), replace=False)
    shocks[large_shock_indices] += np.random.normal(0, volatility * 0.5, len(large_shock_indices))

    # Add gradual trend (slight upward drift due to inflation)
    trend = np.linspace(0, 0.10, n)  # 10% increase over 10 years

    # Combine all components
    prices = seasonal * (1 + ar_term + shocks + trend)

    # Clip to realistic bounds
    prices = np.clip(prices, price_min * 0.9, price_max * 1.1)

    return prices


def create_crop_csv(crop_name, config):
    """Create and save a crop price CSV file with metadata header."""
    dates = pd.date_range(start=START_DATE, end=END_DATE, freq="MS")
    prices = generate_crop_prices(crop_name, config, dates)

    # Calculate thresholds for market condition classification
    price_33 = np.percentile(prices, 33)
    price_67 = np.percentile(prices, 67)

    df = pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "usd_per_kg": np.round(prices, 4),
        "season": [get_season(d.month) for d in dates],
        "market_condition": [get_market_condition(p, price_33, price_67) for p in prices]
    })

    # Create metadata header
    metadata = f'''# SOURCE: Synthetic data generated for Community Agri-PV model
# DATE: {datetime.now().strftime("%Y-%m-%d")}
# DESCRIPTION: Monthly wholesale {crop_name} prices (USD/kg) for Egypt/MENA region
# UNITS: usd_per_kg (USD per kilogram, wholesale)
# LOGIC: Sinusoidal seasonality (low prices at harvest) + AR(1) persistence + random shocks
# DEPENDENCIES: None
# ASSUMPTIONS: Harvest months {config["harvest_months"]}, price range ${config["min"]:.2f}-${config["max"]:.2f}/kg
# GENERATION_METHOD: Synthetic with realistic seasonal and market dynamics
# CURRENCY: All prices in USD; reference FAO/USDA global commodity prices
'''

    filepath = BASE_PATH / "crops" / f"historical_{crop_name}_prices-toy.csv"
    with open(filepath, "w") as f:
        f.write(metadata)
        df.to_csv(f, index=False)

    return df, filepath


def create_processed_csv(crop_name, processing_type, base_prices, dates, multiplier_range):
    """Create processed product price CSV based on raw crop prices."""
    # Apply value-add multiplier with some variation
    mult_mean = (multiplier_range["min"] + multiplier_range["max"]) / 2
    mult_std = (multiplier_range["max"] - multiplier_range["min"]) / 4

    # Add stochastic variation to processing spread
    multipliers = np.random.normal(mult_mean, mult_std, len(dates))
    multipliers = np.clip(multipliers, multiplier_range["min"], multiplier_range["max"])

    processed_prices = base_prices * multipliers

    price_33 = np.percentile(processed_prices, 33)
    price_67 = np.percentile(processed_prices, 67)

    df = pd.DataFrame({
        "date": dates,
        "usd_per_kg": np.round(processed_prices, 4),
        "season": [get_season(pd.Timestamp(d).month) for d in dates],
        "market_condition": [get_market_condition(p, price_33, price_67) for p in processed_prices]
    })

    product_name = f"{processing_type}_{crop_name}"
    metadata = f'''# SOURCE: Synthetic data derived from raw {crop_name} prices
# DATE: {datetime.now().strftime("%Y-%m-%d")}
# DESCRIPTION: Monthly wholesale {processing_type} {crop_name} prices (USD/kg)
# UNITS: usd_per_kg (USD per kilogram, wholesale)
# LOGIC: Base crop price x value-add multiplier ({multiplier_range["min"]:.1f}-{multiplier_range["max"]:.1f}x) with stochastic spread
# DEPENDENCIES: historical_{crop_name}_prices-toy.csv
# ASSUMPTIONS: Processing adds value through preservation, convenience, reduced spoilage
# GENERATION_METHOD: Multiplicative from raw prices with processing cost variation
# CURRENCY: All prices in USD
'''

    filepath = BASE_PATH / "processed" / f"historical_{product_name}_prices-toy.csv"
    with open(filepath, "w") as f:
        f.write(metadata)
        df.to_csv(f, index=False)

    return df, filepath


def create_electricity_csv():
    """Generate electricity price time series for Egypt agricultural tariff."""
    dates = pd.date_range(start=START_DATE, end=END_DATE, freq="MS")
    n = len(dates)

    # Target USD range: $0.06-$0.12/kWh for agricultural users
    # Generate prices in USD with gradual increase over the decade
    usd_price_min, usd_price_max = 0.06, 0.12
    usd_mean = (usd_price_min + usd_price_max) / 2

    records = []
    for i, d in enumerate(dates):
        year = d.year
        month = d.month
        exchange_rate = EGP_USD_RATES[year]

        # Gradual increase from low to high end of range over 10 years
        trend_factor = i / (n - 1)  # 0 to 1 over the period
        base_usd = usd_price_min + (usd_price_max - usd_price_min) * trend_factor * 0.7

        # Add seasonal variation (summer ~5% higher due to demand)
        seasonal_mult = 1.0 + 0.05 * np.sin(2 * np.pi * (month - 3) / 12)

        # Add small monthly noise
        monthly_noise = np.random.normal(1.0, 0.03)

        usd_avg = base_usd * seasonal_mult * monthly_noise
        usd_avg = np.clip(usd_avg, usd_price_min * 0.95, usd_price_max * 1.05)

        # Peak/off-peak differential (peak ~1.25x off-peak)
        usd_offpeak = usd_avg * 0.85
        usd_peak = usd_avg * 1.15

        # Back-calculate EGP for documentation
        egp_avg = usd_avg * exchange_rate

        # Seasonal rate schedule
        rate_schedule = "summer" if month in [6, 7, 8, 9] else "standard"

        records.append({
            "date": d.strftime("%Y-%m-%d"),
            "usd_per_kwh_offpeak": round(usd_offpeak, 4),
            "usd_per_kwh_peak": round(usd_peak, 4),
            "usd_per_kwh_avg_daily": round(usd_avg, 4),
            "rate_schedule": rate_schedule,
            "egp_per_kwh_original": round(egp_avg, 4),
            "usd_egp_exchange_rate": exchange_rate
        })

    df = pd.DataFrame(records)

    metadata = f'''# SOURCE: Synthetic data based on Egyptian Electricity Holding Company tariff trends
# DATE: {datetime.now().strftime("%Y-%m-%d")}
# DESCRIPTION: Monthly electricity prices for agricultural users in Egypt
# UNITS: usd_per_kwh (USD per kilowatt-hour), egp_per_kwh_original (Egyptian Pounds)
# LOGIC: Base rates follow Egyptian subsidy removal program 2015-2024, peak/off-peak differential 1.25/0.75
# DEPENDENCIES: None
# ASSUMPTIONS: Agricultural tariff category, gradual subsidy removal reflected in rising EGP prices
# GENERATION_METHOD: Annual EGP base rates with monthly variation, USD conversion at historical rates
# CURRENCY: Primary USD, original EGP documented with exchange rates
# EXCHANGE_RATE_SOURCE: Central Bank of Egypt historical averages
'''

    filepath = BASE_PATH / "electricity" / "historical_grid_electricity_prices-toy.csv"
    with open(filepath, "w") as f:
        f.write(metadata)
        df.to_csv(f, index=False)

    return df, filepath


def create_water_csv():
    """Generate municipal water price time series for Egypt."""
    dates = pd.date_range(start=START_DATE, end=END_DATE, freq="MS")
    n = len(dates)

    # Target USD range: $0.20-$0.80/m3 for municipal water in water-scarce regions
    usd_price_min, usd_price_max = 0.20, 0.80

    records = []
    for i, d in enumerate(dates):
        year = d.year
        month = d.month
        exchange_rate = EGP_USD_RATES[year]

        # Gradual increase due to water scarcity management
        trend_factor = i / (n - 1)
        base_usd = usd_price_min + (usd_price_max - usd_price_min) * trend_factor * 0.85

        # Seasonal variation (summer ~10% higher due to scarcity)
        seasonal_mult = 1.0 + 0.10 * np.sin(2 * np.pi * (month - 3) / 12)

        # Monthly noise
        monthly_noise = np.random.normal(1.0, 0.03)

        usd_price = base_usd * seasonal_mult * monthly_noise
        usd_price = np.clip(usd_price, usd_price_min * 0.95, usd_price_max * 1.05)

        # Back-calculate EGP for documentation
        egp_price = usd_price * exchange_rate

        records.append({
            "date": d.strftime("%Y-%m-%d"),
            "usd_per_m3": round(usd_price, 4),
            "egp_per_m3_original": round(egp_price, 4),
            "usd_egp_exchange_rate": exchange_rate,
            "rate_category": "agricultural_bulk"
        })

    df = pd.DataFrame(records)

    metadata = f'''# SOURCE: Synthetic data based on Egyptian water authority pricing trends
# DATE: {datetime.now().strftime("%Y-%m-%d")}
# DESCRIPTION: Monthly municipal water prices for agricultural bulk users in Egypt
# UNITS: usd_per_m3 (USD per cubic meter), egp_per_m3_original (Egyptian Pounds)
# LOGIC: Base rates increase with water scarcity management policy, slight seasonal variation (summer premium)
# DEPENDENCIES: None
# ASSUMPTIONS: Agricultural bulk rate category, gradual price increases for conservation
# GENERATION_METHOD: Annual EGP base rates with seasonal variation, USD conversion at historical rates
# CURRENCY: Primary USD, original EGP documented with exchange rates
# EXCHANGE_RATE_SOURCE: Central Bank of Egypt historical averages
'''

    filepath = BASE_PATH / "water" / "historical_municipal_water_prices-toy.csv"
    with open(filepath, "w") as f:
        f.write(metadata)
        df.to_csv(f, index=False)

    return df, filepath


def create_diesel_csv():
    """Generate diesel fuel price time series for Egypt."""
    dates = pd.date_range(start=START_DATE, end=END_DATE, freq="MS")
    n = len(dates)

    # Target USD range: $0.40-$1.00/liter (varies with oil prices and subsidies)
    usd_price_min, usd_price_max = 0.40, 1.00

    # Global oil price influence pattern (normalized Brent crude proxy)
    oil_price_factor = {
        2015: 0.75, 2016: 0.60, 2017: 0.70, 2018: 0.95,
        2019: 0.85, 2020: 0.55, 2021: 0.90, 2022: 1.30,
        2023: 1.10, 2024: 1.00
    }

    records = []
    for i, d in enumerate(dates):
        year = d.year
        month = d.month
        exchange_rate = EGP_USD_RATES[year]
        oil_factor = oil_price_factor[year]

        # Base price with gradual subsidy removal trend
        trend_factor = i / (n - 1)
        base_usd = usd_price_min + (usd_price_max - usd_price_min) * trend_factor * 0.5

        # Apply oil price factor (normalized so mean ~ 1.0)
        oil_adjusted = base_usd * (0.7 + 0.3 * oil_factor)

        # Monthly variation from global oil markets
        monthly_oil_var = np.random.normal(1.0, 0.06)

        usd_price = oil_adjusted * monthly_oil_var
        usd_price = np.clip(usd_price, usd_price_min * 0.95, usd_price_max * 1.05)

        # Back-calculate EGP for documentation
        egp_price = usd_price * exchange_rate

        records.append({
            "date": d.strftime("%Y-%m-%d"),
            "usd_per_liter": round(usd_price, 4),
            "egp_per_liter_original": round(egp_price, 4),
            "usd_egp_exchange_rate": exchange_rate
        })

    df = pd.DataFrame(records)

    metadata = f'''# SOURCE: Synthetic data based on Egyptian petroleum authority and global oil prices
# DATE: {datetime.now().strftime("%Y-%m-%d")}
# DESCRIPTION: Monthly diesel fuel prices in Egypt
# UNITS: usd_per_liter (USD per liter), egp_per_liter_original (Egyptian Pounds)
# LOGIC: Base EGP rates follow subsidy removal program, modulated by global Brent crude price trends
# DEPENDENCIES: None
# ASSUMPTIONS: Subsidized diesel for agricultural use, gradual subsidy reduction 2015-2024
# GENERATION_METHOD: Annual EGP base x global oil factor with monthly variation
# CURRENCY: Primary USD, original EGP documented with exchange rates
# EXCHANGE_RATE_SOURCE: Central Bank of Egypt historical averages
# OIL_PRICE_REFERENCE: World Bank Commodity Price Data (Brent Crude)
'''

    filepath = BASE_PATH / "diesel" / "historical_diesel_prices-toy.csv"
    with open(filepath, "w") as f:
        f.write(metadata)
        df.to_csv(f, index=False)

    return df, filepath


def main():
    """Generate all price datasets."""
    print("Generating Price Time-Series Data for Community Agri-PV Project")
    print("=" * 60)

    results = {}

    # Generate crop prices
    print("\n1. Generating crop price datasets...")
    crop_data = {}
    for crop_name, config in CROP_CONFIGS.items():
        df, filepath = create_crop_csv(crop_name, config)
        crop_data[crop_name] = {"df": df, "prices": df["usd_per_kg"].values}
        print(f"   - {filepath.name}: {len(df)} records, "
              f"${df['usd_per_kg'].min():.2f}-${df['usd_per_kg'].max():.2f}/kg")
        results[filepath.name] = df

    # Generate processed product prices
    print("\n2. Generating processed product price datasets...")
    dates = pd.date_range(start=START_DATE, end=END_DATE, freq="MS").strftime("%Y-%m-%d")

    # Dried products: tomato, kale
    for crop in ["tomato", "kale"]:
        df, filepath = create_processed_csv(
            crop, "dried", crop_data[crop]["prices"], dates, VALUE_ADD_MULTIPLIERS["dried"]
        )
        print(f"   - {filepath.name}: {len(df)} records, "
              f"${df['usd_per_kg'].min():.2f}-${df['usd_per_kg'].max():.2f}/kg")
        results[filepath.name] = df

    # Canned products: tomato, onion
    for crop in ["tomato", "onion"]:
        df, filepath = create_processed_csv(
            crop, "canned", crop_data[crop]["prices"], dates, VALUE_ADD_MULTIPLIERS["canned"]
        )
        print(f"   - {filepath.name}: {len(df)} records, "
              f"${df['usd_per_kg'].min():.2f}-${df['usd_per_kg'].max():.2f}/kg")
        results[filepath.name] = df

    # Packaged products: all crops for export
    for crop in CROP_CONFIGS.keys():
        df, filepath = create_processed_csv(
            crop, "packaged", crop_data[crop]["prices"], dates, VALUE_ADD_MULTIPLIERS["packaged"]
        )
        print(f"   - {filepath.name}: {len(df)} records, "
              f"${df['usd_per_kg'].min():.2f}-${df['usd_per_kg'].max():.2f}/kg")
        results[filepath.name] = df

    # Pickled cucumber
    df, filepath = create_processed_csv(
        "cucumber", "pickled", crop_data["cucumber"]["prices"], dates,
        {"min": 1.4, "max": 1.8}  # Similar to canned
    )
    print(f"   - {filepath.name}: {len(df)} records, "
          f"${df['usd_per_kg'].min():.2f}-${df['usd_per_kg'].max():.2f}/kg")
    results[filepath.name] = df

    # Generate utility prices
    print("\n3. Generating electricity price dataset...")
    df, filepath = create_electricity_csv()
    print(f"   - {filepath.name}: {len(df)} records, "
          f"${df['usd_per_kwh_avg_daily'].min():.4f}-${df['usd_per_kwh_avg_daily'].max():.4f}/kWh")
    results[filepath.name] = df

    print("\n4. Generating water price dataset...")
    df, filepath = create_water_csv()
    print(f"   - {filepath.name}: {len(df)} records, "
          f"${df['usd_per_m3'].min():.4f}-${df['usd_per_m3'].max():.4f}/m3")
    results[filepath.name] = df

    print("\n5. Generating diesel price dataset...")
    df, filepath = create_diesel_csv()
    print(f"   - {filepath.name}: {len(df)} records, "
          f"${df['usd_per_liter'].min():.4f}-${df['usd_per_liter'].max():.4f}/liter")
    results[filepath.name] = df

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total files generated: {len(results)}")
    print(f"Time range: {START_DATE} to {END_DATE} (120 months)")

    return results


if __name__ == "__main__":
    main()
