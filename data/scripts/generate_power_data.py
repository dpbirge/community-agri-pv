"""
Generate PV and Wind Power toy datasets for Community Agri-PV project.

Task 8 of the data generation orchestration plan.
Reads weather data and computes normalized power output for:
- PV: 3 density variants (low/medium/high)
- Wind: 3 turbine variants (small/medium/large)
"""

import pandas as pd
import numpy as np
import yaml
from datetime import datetime
from pathlib import Path


# === Configuration ===

# PV System Specs
PV_SPECS = {
    'tilt_angle_deg': 28,
    'azimuth_deg': 180,  # south-facing
    'module_efficiency': 0.19,
    'temp_coefficient': -0.004,  # -0.4%/C
    'temp_reference_c': 25,
    'system_losses': 0.15,  # 15%
}

# Microclimate adjustments for agri-PV density variants
# Higher density = more shading = lower temp but also lower irradiance on panels
PV_DENSITY_ADJUSTMENTS = {
    'low': {
        'ground_coverage_pct': 30,
        'temp_adjustment_c': 2.0,      # panels get hotter (less shading effect)
        'irradiance_factor': 1.0,      # full irradiance on panels
    },
    'medium': {
        'ground_coverage_pct': 50,
        'temp_adjustment_c': 0.0,      # baseline
        'irradiance_factor': 1.0,      # full irradiance
    },
    'high': {
        'ground_coverage_pct': 80,
        'temp_adjustment_c': -2.0,     # panels cooler (shading/ventilation effect)
        'irradiance_factor': 1.0,      # panels still get full sun (they're above)
    },
}

def _load_wind_turbine_specs(base_path):
    """Load wind turbine specs from data_registry.yaml (single source of truth)."""
    reg_file = base_path / 'settings/data_registry.yaml'
    with open(reg_file) as f:
        registry = yaml.safe_load(f)
    csv_path = base_path / registry['equipment']['wind_turbines']
    df = pd.read_csv(csv_path, comment='#')
    specs = {}
    for _, row in df.iterrows():
        specs[row['turbine_name']] = {
            'rated_kw': row['rated_capacity_kw'],
            'cut_in_ms': row['cut_in_speed_ms'],
            'rated_ms': row['rated_speed_ms'],
            'cut_out_ms': row['cut_out_speed_ms'],
            'hub_height_m': row['hub_height_m'],
            'capacity_factor_typical': row['capacity_factor_typical'],
        }
    return specs


def calculate_pv_output(solar_irradiance, temp_max, temp_min, density_variant):
    """
    Calculate normalized PV output (kWh/kW/day) based on weather data.

    Uses simplified PV model:
    - Base output from irradiance (kWh/m2/day -> kWh/kW/day at reference conditions)
    - Temperature derating based on cell temperature
    - System losses applied

    Args:
        solar_irradiance: Daily solar irradiance in kWh/m2/day
        temp_max: Daily maximum temperature in Celsius
        temp_min: Daily minimum temperature in Celsius
        density_variant: 'low', 'medium', or 'high'

    Returns:
        tuple: (kwh_per_kw_per_day, capacity_factor)
    """
    adj = PV_DENSITY_ADJUSTMENTS[density_variant]

    # Estimate cell temperature (simplified model)
    # Cell temp is roughly ambient + 25-30C under irradiance
    # Using average daily temp as proxy for operating temp
    temp_avg = (temp_max + temp_min) / 2
    temp_cell = temp_avg + 25 + adj['temp_adjustment_c']

    # Temperature derating
    temp_diff = temp_cell - PV_SPECS['temp_reference_c']
    temp_factor = 1 + PV_SPECS['temp_coefficient'] * temp_diff
    temp_factor = np.clip(temp_factor, 0.5, 1.1)  # reasonable bounds

    # Effective irradiance on tilted surface
    # For fixed-tilt at latitude angle (28deg), annual factor is ~1.0-1.1x horizontal
    # Simplified: assume tilted surface receives ~5% more than horizontal on average
    tilt_factor = 1.05
    effective_irradiance = solar_irradiance * tilt_factor * adj['irradiance_factor']

    # Convert irradiance to power output
    # 1 kWh/m2/day on a 1 kW system at STC (1000 W/m2) = 1 peak sun hour
    # So kWh/m2/day ~= peak sun hours ~= kWh/kW/day at STC
    kwh_per_kw = effective_irradiance * temp_factor * (1 - PV_SPECS['system_losses'])

    # Theoretical max is 24 hours * 1 kW = 24 kWh/kW/day, but realistic max ~8 kWh/kW/day
    kwh_per_kw = np.clip(kwh_per_kw, 0, 10)

    # Capacity factor (fraction of theoretical max)
    # Max hours at full rated power = 24, but realistic reference is ~4-6 hours
    capacity_factor = kwh_per_kw / 24.0

    return kwh_per_kw, capacity_factor


def calculate_wind_output(wind_speed, turbine_specs):
    """
    Calculate normalized wind output (kWh/kW/day) using Weibull-integrated power curve model.

    Instead of using the daily average wind speed directly in the power curve (which
    grossly underestimates output), we model the hourly wind distribution as Weibull
    with shape k=2 (Rayleigh) and scale based on daily average, then integrate the
    power curve over this distribution.

    Also applies wind shear correction to adjust from 10m measurement height to hub height.

    Power curve model:
    - Below cut-in: 0 power
    - Cut-in to rated: cubic relationship (power ~ wind^3)
    - Rated to cut-out: full rated power
    - Above cut-out: 0 power (safety shutdown)

    Args:
        wind_speed: Daily average wind speed in m/s (assumed at 10m height)
        turbine_specs: Dict with keys cut_in_ms, rated_ms, cut_out_ms, hub_height_m

    Returns:
        tuple: (kwh_per_kw_per_day, capacity_factor)
    """
    specs = turbine_specs
    v_in = specs['cut_in_ms']
    v_rated = specs['rated_ms']
    v_out = specs['cut_out_ms']
    hub_height = specs['hub_height_m']

    # Wind shear correction: adjust wind speed from measurement height (10m) to hub height
    # Power law: v(z) = v(z_ref) * (z / z_ref)^alpha
    # Alpha = 0.14 for flat terrain, 0.20 for rural, 0.25 for suburban
    # Using 0.17 for semi-arid agricultural area with some structures
    measurement_height = 10.0  # standard meteorological measurement height
    wind_shear_alpha = 0.17
    hub_wind_speed = wind_speed * (hub_height / measurement_height) ** wind_shear_alpha

    # Weibull parameters: k=2 (Rayleigh), scale derived from mean
    # For Rayleigh: mean = scale * sqrt(pi/2), so scale = mean / sqrt(pi/2)
    k = 2.0
    if hub_wind_speed > 0:
        scale = hub_wind_speed / np.sqrt(np.pi / 2)
    else:
        return 0.0, 0.0

    # Numerical integration of power curve over Weibull distribution
    # Using discrete wind speed bins from 0 to 30 m/s
    v_bins = np.linspace(0, 30, 301)  # 0.1 m/s resolution
    dv = v_bins[1] - v_bins[0]

    # Weibull PDF: f(v) = (k/c) * (v/c)^(k-1) * exp(-(v/c)^k)
    pdf = (k / scale) * (v_bins / scale) ** (k - 1) * np.exp(-(v_bins / scale) ** k)
    pdf[0] = 0  # avoid division issues at v=0

    # Power curve for each wind speed bin
    power = np.zeros_like(v_bins)
    mask_cubic = (v_bins >= v_in) & (v_bins < v_rated)
    mask_rated = (v_bins >= v_rated) & (v_bins <= v_out)

    power[mask_cubic] = ((v_bins[mask_cubic] - v_in) / (v_rated - v_in)) ** 3
    power[mask_rated] = 1.0

    # Expected power = integral of power(v) * pdf(v) dv
    expected_power_fraction = np.sum(power * pdf * dv)

    # Cap at 1.0 (shouldn't exceed but numerical integration might overshoot slightly)
    expected_power_fraction = min(expected_power_fraction, 1.0)

    # Daily output: 24 hours at expected power fraction
    kwh_per_kw = 24.0 * expected_power_fraction

    # Capacity factor
    capacity_factor = expected_power_fraction

    return kwh_per_kw, capacity_factor


def generate_pv_power_data(weather_df):
    """Generate PV power dataset for all density variants."""
    records = []

    for _, row in weather_df.iterrows():
        for density in ['low', 'medium', 'high']:
            kwh, cf = calculate_pv_output(
                row['solar_irradiance_kwh_m2'],
                row['temp_max_c'],
                row['temp_min_c'],
                density
            )
            records.append({
                'weather_scenario_id': row['weather_scenario_id'],
                'date': row['date'],
                'density_variant': density,
                'kwh_per_kw_per_day': round(kwh, 4),
                'capacity_factor': round(cf, 4),
            })

    return pd.DataFrame(records)


def generate_wind_power_data(weather_df, wind_turbines):
    """Generate wind power dataset for all turbine variants."""
    records = []

    for _, row in weather_df.iterrows():
        for turbine in wind_turbines:
            kwh, cf = calculate_wind_output(
                row['wind_speed_ms'],
                wind_turbines[turbine]
            )
            records.append({
                'weather_scenario_id': row['weather_scenario_id'],
                'date': row['date'],
                'turbine_variant': turbine,
                'kwh_per_kw_per_day': round(kwh, 4),
                'capacity_factor': round(cf, 4),
            })

    return pd.DataFrame(records)


def create_pv_metadata():
    """Generate metadata header for PV power file."""
    return f"""# SOURCE: Computed from weather data using simplified PV model
# DATE: {datetime.now().strftime('%Y-%m-%d')}
# DESCRIPTION: Normalized daily PV power output per kW of installed capacity for three agri-PV density variants (low/medium/high ground coverage)
# UNITS: date=YYYY-MM-DD, density_variant=text, kwh_per_kw_per_day=kWh/kW/day, capacity_factor=dimensionless(0-1)
# LOGIC: PV output = solar_irradiance * tilt_factor(1.05) * temp_factor * (1-system_losses). Temp factor uses cell temp model: T_cell = T_avg + 25C + density_adjustment. Temperature coefficient = -0.4%/C from 25C reference. System losses = 15%.
# DEPENDENCIES: data/precomputed/weather/daily_weather_scenario_001-toy.csv
# ASSUMPTIONS: Fixed-tilt 28deg south-facing panels. Module efficiency ~19%. High density panels run 2C cooler (shading effect), low density run 2C hotter. All panels receive full irradiance (panels above crops, not shaded by each other). Tilt factor approximate; full pvlib model would be more accurate.
"""


def create_wind_metadata(wind_turbines):
    """Generate metadata header for wind power file."""
    turbine_descs = []
    for name, s in wind_turbines.items():
        turbine_descs.append(
            f"{name.capitalize()} turbine ({s['rated_kw']:.0f}kW): "
            f"cut-in {s['cut_in_ms']} m/s, rated {s['rated_ms']} m/s, "
            f"cut-out {s['cut_out_ms']} m/s, hub {s['hub_height_m']:.0f}m"
        )
    desc_str = ". ".join(turbine_descs)
    variant_summary = ", ".join(
        f"{name} {s['rated_kw']:.0f}kW" for name, s in wind_turbines.items()
    )
    return f"""# SOURCE: Computed from weather data using Weibull-integrated power curve model
# DATE: {datetime.now().strftime('%Y-%m-%d')}
# DESCRIPTION: Normalized daily wind power output per kW of rated capacity for turbine variants ({variant_summary})
# UNITS: date=YYYY-MM-DD, turbine_variant=text, kwh_per_kw_per_day=kWh/kW/day, capacity_factor=dimensionless(0-1)
# LOGIC: Power curve model with cut-in/rated/cut-out speeds integrated over Weibull (Rayleigh, k=2) wind speed distribution. Below cut-in: 0. Cut-in to rated: cubic relationship. Rated to cut-out: full power. Above cut-out: 0. Wind shear correction applied (alpha=0.17) to scale from 10m measurement height to hub height. Weibull scale parameter derived from hub-height daily average wind speed.
# DEPENDENCIES: data/precomputed/weather/daily_weather_scenario_001-toy.csv, settings/data_registry.yaml (equipment.wind_turbines)
# ASSUMPTIONS: Turbines designed for low-wind sites (IEC Class III/IV). {desc_str}. Wind at measurement height (10m) scaled to hub height using power law (alpha=0.17). Hourly wind speeds follow Rayleigh distribution (Weibull k=2).
"""


def validate_pv_data(df):
    """Validate PV power data against expected ranges."""
    issues = []

    # Check for missing values
    if df.isnull().any().any():
        issues.append("Missing values found in PV data")

    # Check capacity factor range
    if (df['capacity_factor'] < 0).any() or (df['capacity_factor'] > 1).any():
        issues.append("Capacity factor outside 0-1 range")

    # Check kwh_per_kw range (realistic max ~8-9 kWh/kW/day)
    if (df['kwh_per_kw_per_day'] < 0).any():
        issues.append("Negative kWh/kW values found")
    if (df['kwh_per_kw_per_day'] > 10).any():
        issues.append("Unrealistically high kWh/kW values (>10)")

    # Check density variant completeness
    for d in ['low', 'medium', 'high']:
        if d not in df['density_variant'].values:
            issues.append(f"Missing density variant: {d}")

    return issues


def validate_wind_data(df, wind_turbines):
    """Validate wind power data against expected ranges."""
    issues = []

    if df.isnull().any().any():
        issues.append("Missing values found in wind data")

    if (df['capacity_factor'] < 0).any() or (df['capacity_factor'] > 1).any():
        issues.append("Capacity factor outside 0-1 range")

    if (df['kwh_per_kw_per_day'] < 0).any():
        issues.append("Negative kWh/kW values found")
    if (df['kwh_per_kw_per_day'] > 24).any():
        issues.append("Unrealistically high kWh/kW values (>24)")

    for t in wind_turbines:
        if t not in df['turbine_variant'].values:
            issues.append(f"Missing turbine variant: {t}")

    for turbine, specs in wind_turbines.items():
        subset = df[df['turbine_variant'] == turbine]
        mean_cf = subset['capacity_factor'].mean()
        cf_typical = specs['capacity_factor_typical']
        if mean_cf < cf_typical * 0.5 or mean_cf > cf_typical * 2.0:
            issues.append(
                f"Mean capacity factor for {turbine} ({mean_cf:.3f}) "
                f"far from typical ({cf_typical})"
            )

    return issues


def compute_statistics(pv_df, wind_df):
    """Compute summary statistics for reporting."""
    stats = {}

    # PV statistics
    stats['pv'] = {}
    for density in ['low', 'medium', 'high']:
        subset = pv_df[pv_df['density_variant'] == density]
        stats['pv'][density] = {
            'mean_kwh': subset['kwh_per_kw_per_day'].mean(),
            'min_kwh': subset['kwh_per_kw_per_day'].min(),
            'max_kwh': subset['kwh_per_kw_per_day'].max(),
            'mean_cf': subset['capacity_factor'].mean(),
            'annual_kwh_per_kw': subset['kwh_per_kw_per_day'].mean() * 365,
        }

    # Wind statistics
    stats['wind'] = {}
    for turbine in ['small', 'medium', 'large']:
        subset = wind_df[wind_df['turbine_variant'] == turbine]
        stats['wind'][turbine] = {
            'mean_kwh': subset['kwh_per_kw_per_day'].mean(),
            'min_kwh': subset['kwh_per_kw_per_day'].min(),
            'max_kwh': subset['kwh_per_kw_per_day'].max(),
            'mean_cf': subset['capacity_factor'].mean(),
            'annual_kwh_per_kw': subset['kwh_per_kw_per_day'].mean() * 365,
        }

    return stats


def main():
    """Main execution function."""
    base_path = Path('/Users/dpbirge/GITHUB/community-agri-pv')

    # Load wind turbine specs from parameter CSV
    wind_turbines = _load_wind_turbine_specs(base_path)
    print(f"Loaded wind turbine specs: {list(wind_turbines.keys())}")

    # Load weather data (skip metadata header lines starting with #)
    weather_path = base_path / 'data/precomputed/weather/daily_weather_scenario_001-toy.csv'
    print(f"Loading weather data from: {weather_path}")
    weather_df = pd.read_csv(weather_path, comment='#', dtype={'weather_scenario_id': str})
    print(f"Loaded {len(weather_df)} days of weather data")

    # Generate PV power data
    print("\nGenerating PV power data...")
    pv_df = generate_pv_power_data(weather_df)
    print(f"Generated {len(pv_df)} PV power records")

    # Generate wind power data
    print("\nGenerating wind power data...")
    wind_df = generate_wind_power_data(weather_df, wind_turbines)
    print(f"Generated {len(wind_df)} wind power records")

    # Validate data
    print("\nValidating data...")
    pv_issues = validate_pv_data(pv_df)
    wind_issues = validate_wind_data(wind_df, wind_turbines)

    if pv_issues:
        print("PV validation issues:")
        for issue in pv_issues:
            print(f"  - {issue}")
    else:
        print("PV data validation: PASSED")

    if wind_issues:
        print("Wind validation issues:")
        for issue in wind_issues:
            print(f"  - {issue}")
    else:
        print("Wind data validation: PASSED")

    # Compute statistics
    stats = compute_statistics(pv_df, wind_df)

    print("\n" + "="*60)
    print("PV Power Statistics (by density variant)")
    print("="*60)
    for density, s in stats['pv'].items():
        print(f"\n{density.upper()} density:")
        print(f"  Mean daily output: {s['mean_kwh']:.3f} kWh/kW/day")
        print(f"  Range: {s['min_kwh']:.3f} - {s['max_kwh']:.3f} kWh/kW/day")
        print(f"  Mean capacity factor: {s['mean_cf']:.3f} ({s['mean_cf']*100:.1f}%)")
        print(f"  Annual production: {s['annual_kwh_per_kw']:.0f} kWh/kW/year")

    print("\n" + "="*60)
    print("Wind Power Statistics (by turbine variant)")
    print("="*60)
    for turbine, s in stats['wind'].items():
        print(f"\n{turbine.upper()} turbine:")
        print(f"  Mean daily output: {s['mean_kwh']:.3f} kWh/kW/day")
        print(f"  Range: {s['min_kwh']:.3f} - {s['max_kwh']:.3f} kWh/kW/day")
        print(f"  Mean capacity factor: {s['mean_cf']:.3f} ({s['mean_cf']*100:.1f}%)")
        print(f"  Annual production: {s['annual_kwh_per_kw']:.0f} kWh/kW/year")

    # Write output files
    pv_output_path = base_path / 'data/precomputed/pv_power/pv_normalized_kwh_per_kw_daily-toy.csv'
    wind_output_path = base_path / 'data/precomputed/wind_power/wind_normalized_kwh_per_kw_daily-toy.csv'

    # Ensure directories exist
    pv_output_path.parent.mkdir(parents=True, exist_ok=True)
    wind_output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write PV file with metadata header
    print(f"\nWriting PV data to: {pv_output_path}")
    with open(pv_output_path, 'w') as f:
        f.write(create_pv_metadata())
        pv_df.to_csv(f, index=False)

    # Write wind file with metadata header
    print(f"Writing wind data to: {wind_output_path}")
    with open(wind_output_path, 'w') as f:
        f.write(create_wind_metadata(wind_turbines))
        wind_df.to_csv(f, index=False)

    # Report file sizes
    print("\n" + "="*60)
    print("Output Files")
    print("="*60)
    print(f"PV power:   {pv_output_path.name} ({pv_output_path.stat().st_size / 1024:.1f} KB)")
    print(f"Wind power: {wind_output_path.name} ({wind_output_path.stat().st_size / 1024:.1f} KB)")

    print("\nGeneration complete!")


if __name__ == '__main__':
    main()
