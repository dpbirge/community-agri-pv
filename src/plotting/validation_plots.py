"""
Validation plots for verifying precomputed data against expected physical behavior.

Each public plot_*_validation() function produces a standalone multi-panel figure
that reads only from CSV data files and reproduces the same calculations used in
the simulation code, so results can be visually cross-checked without running a
full simulation.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import yaml
import matplotlib.pyplot as plt


def _registry_path(project_root, *keys):
    """Resolve a file path from data_registry.yaml by dotted key lookup."""
    reg_file = Path(project_root) / "settings/data_registry.yaml"
    with open(reg_file) as f:
        registry = yaml.safe_load(f)
    node = registry
    for k in keys:
        node = node[k]
    return Path(project_root) / node


TURBINE_COLORS = {'small': '#1f77b4', 'medium': '#ff7f0e', 'large': '#2ca02c'}
DENSITY_COLORS = {'low': '#e74c3c', 'medium': '#f39c12', 'high': '#27ae60'}
CROP_COLORS = {
    'tomato': '#e74c3c', 'potato': '#8b4513', 'onion': '#9b59b6',
    'kale': '#27ae60', 'cucumber': '#2ecc71',
}
PATHWAY_COLORS = {
    'fresh': '#27ae60', 'packaged': '#3498db',
    'canned': '#e67e22', 'dried': '#c0392b',
}
PATHWAY_STYLES = {'fresh': '-', 'packaged': '--', 'canned': '-.', 'dried': ':'}


def _load_wind_turbine_specs(project_root):
    """Load wind turbine specs from the parameter CSV (single source of truth)."""
    csv_path = _registry_path(project_root, 'equipment', 'wind_turbines')
    df = pd.read_csv(csv_path, comment='#')
    specs = {}
    for _, row in df.iterrows():
        specs[row['turbine_name']] = {
            'rated_kw': row['rated_capacity_kw'],
            'cut_in_ms': row['cut_in_speed_ms'],
            'rated_ms': row['rated_speed_ms'],
            'cut_out_ms': row['cut_out_speed_ms'],
            'hub_height_m': row['hub_height_m'],
        }
    return specs


def _power_curve(v, v_in, v_rated, v_out):
    """Normalized power output (0-1) for a given wind speed array."""
    power = np.zeros_like(v, dtype=float)
    cubic = (v >= v_in) & (v < v_rated)
    rated = (v >= v_rated) & (v <= v_out)
    power[cubic] = ((v[cubic] - v_in) / (v_rated - v_in)) ** 3
    power[rated] = 1.0
    return power


def _load_wind_csv(project_root):
    """Load precomputed wind power CSV, skipping metadata header lines."""
    path = _registry_path(project_root, 'power', 'wind')
    with open(path) as f:
        skip = sum(1 for line in f if line.startswith('#'))
    df = pd.read_csv(path, skiprows=skip)
    df['date'] = pd.to_datetime(df['date'])
    return df


def plot_wind_validation(project_root="."):
    """3-panel wind turbine validation figure.

    Panel 1: Power curves (kW vs wind speed) using the same cubic power curve
        equation used inside the generation model.
    Panel 2: Monthly mean capacity factors from precomputed data.
    Panel 3: Daily capacity factor time series (first 2 years) showing seasonal pattern.
    """
    turbines = _load_wind_turbine_specs(project_root)
    wind_df = _load_wind_csv(project_root)
    variant_names = list(turbines.keys())

    fig, axes = plt.subplots(3, 1, figsize=(10, 12))

    # --- Panel 1: Power curves (kW output vs instantaneous wind speed) ---
    ax = axes[0]
    v = np.linspace(0, 28, 500)
    for name in variant_names:
        specs = turbines[name]
        color = TURBINE_COLORS.get(name, None)
        power_kw = _power_curve(v, specs['cut_in_ms'], specs['rated_ms'], specs['cut_out_ms']) * specs['rated_kw']
        label = (f"{name} ({specs['rated_kw']:.0f}kW, "
                 f"v_in={specs['cut_in_ms']}, v_r={specs['rated_ms']} m/s)")
        ax.plot(v, power_kw, color=color, label=label, linewidth=1.5)
    ax.set_xlabel('Wind speed (m/s)')
    ax.set_ylabel('Power output (kW)')
    ax.set_title('Turbine power curves (used inside Weibull integration)')
    ax.legend(fontsize=7)
    ax.set_xlim(0, 28)
    ax.set_ylim(bottom=-1)
    ax.grid(True, alpha=0.3)

    # --- Panel 2: Monthly mean capacity factors ---
    ax = axes[1]
    wind_df['month'] = wind_df['date'].dt.month
    for name in variant_names:
        color = TURBINE_COLORS.get(name, None)
        subset = wind_df[wind_df['turbine_variant'] == name]
        monthly = subset.groupby('month')['capacity_factor'].mean()
        ax.plot(monthly.index, monthly.values, 'o-', color=color,
                label=f"{name} (mean={subset['capacity_factor'].mean():.2f})", linewidth=1.5, markersize=4)
    ax.set_xlabel('Month')
    ax.set_ylabel('Capacity factor')
    ax.set_title('Monthly mean capacity factors')
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'])
    ax.legend(fontsize=7)
    ax.set_ylim(0, None)
    ax.grid(True, alpha=0.3)

    # --- Panel 3: Daily CF time series (first 2 years) ---
    ax = axes[2]
    cutoff = wind_df['date'].min() + pd.DateOffset(years=2)
    for name in variant_names:
        color = TURBINE_COLORS.get(name, None)
        subset = wind_df[(wind_df['turbine_variant'] == name) & (wind_df['date'] < cutoff)]
        ax.plot(subset['date'], subset['capacity_factor'], color=color,
                alpha=0.5, linewidth=0.5, label=name)
    ax.set_xlabel('Date')
    ax.set_ylabel('Capacity factor')
    ax.set_title('Daily capacity factors (first 2 years)')
    ax.legend(fontsize=7)
    ax.set_ylim(0, 1)
    ax.grid(True, alpha=0.3)

    fig.suptitle('Wind turbine validation: power curves, seasonal patterns, daily output', fontsize=11)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Water system validation
# ---------------------------------------------------------------------------

def _load_csv_skip_metadata(path):
    """Load a CSV that has # metadata header lines."""
    with open(path) as f:
        skip = sum(1 for line in f if line.startswith('#'))
    return pd.read_csv(path, skiprows=skip)


def _load_irrigation_csv(project_root, crop):
    """Load precomputed irrigation demand CSV for one crop."""
    path = Path(project_root) / f"data/precomputed/irrigation_demand/irrigation_m3_per_ha_{crop}-toy.csv"
    df = _load_csv_skip_metadata(path)
    df['calendar_date'] = pd.to_datetime(df['calendar_date'])
    return df


def _load_weather_csv(project_root):
    """Load daily weather CSV."""
    path = Path(project_root) / "data/precomputed/weather/daily_weather_scenario_001-toy.csv"
    df = pd.read_csv(path, comment='#')
    df['date'] = pd.to_datetime(df['date'])
    return df


def _load_water_treatment_specs(project_root):
    """Load BWRO water treatment specs from equipment CSV."""
    path = Path(project_root) / "data/parameters/equipment/water_treatment-toy.csv"
    return pd.read_csv(path, comment='#')


def _calculate_pumping_energy(well_depth_m, flow_rate_m3_day=100.0,
                              horizontal_distance_km=0.3, pipe_diameter_m=0.1,
                              pump_efficiency=0.60):
    """Pumping energy calculation — mirrors src/settings/calculations.calculate_pumping_energy()."""
    WATER_DENSITY = 1025
    GRAVITY = 9.81
    FRICTION_FACTOR = 0.02
    PI = 3.14159

    lift_energy = (WATER_DENSITY * GRAVITY * well_depth_m) / (pump_efficiency * 3.6e6)

    pipe_area = PI * (pipe_diameter_m / 2) ** 2
    velocity = (flow_rate_m3_day / 86400) / pipe_area
    horiz_m = horizontal_distance_km * 1000
    friction_head = FRICTION_FACTOR * (horiz_m / pipe_diameter_m) * (velocity ** 2 / (2 * GRAVITY))
    friction_energy = (WATER_DENSITY * GRAVITY * friction_head) / (pump_efficiency * 3.6e6)

    return lift_energy, friction_energy


def plot_water_validation(project_root="."):
    """3-panel water system validation figure.

    Panel 1: Irrigation equation check — verifies the FAO relationship
        ETc = ET0 * Kc and irrigation = ETc * 10 / 0.90 for a single tomato
        growing season by overlaying the precomputed CSV data with the
        equation recomputed from its ET0 and Kc columns.
    Panel 2: Pumping energy vs well depth — sweeps well depth from 10-150 m
        using the same Darcy-Weisbach calculation from calculations.py and
        shows lift vs friction components as stacked areas.
    Panel 3: Treatment energy by salinity level — bar chart of BWRO energy
        requirements from the equipment CSV with annotated recovery rates.
    """
    root = Path(project_root)

    # Load data
    tomato_df = _load_irrigation_csv(project_root, 'tomato')
    treatment_specs = _load_water_treatment_specs(project_root)

    # Use the first planting date only for a clean single-season view
    first_planting = tomato_df['planting_date'].iloc[0]
    season = tomato_df[tomato_df['planting_date'] == first_planting].copy()

    fig, axes = plt.subplots(3, 1, figsize=(10, 12))

    # --- Panel 1: Irrigation equation verification ---
    ax = axes[0]

    # Recompute irrigation from the raw ET0 and Kc columns in the CSV
    recomputed_irrigation = season['et0_mm'] * season['kc'] * 10 / 0.90

    ax.plot(season['crop_day'], season['irrigation_m3_per_ha_per_day'],
            'b-', linewidth=1.5, label='Precomputed CSV value')
    ax.plot(season['crop_day'], recomputed_irrigation,
            'r--', linewidth=1.5, alpha=0.8, label='Recomputed: ET0 × Kc × 10 / 0.90')

    # Shade growth stages
    stage_colors = {'initial': '#a8d8ea', 'development': '#aa96da', 'mid': '#fcbad3', 'late': '#ffffd2'}
    prev_day = season['crop_day'].iloc[0]
    for stage in ['initial', 'development', 'mid', 'late']:
        stage_rows = season[season['growth_stage'] == stage]
        if not stage_rows.empty:
            ax.axvspan(stage_rows['crop_day'].min(), stage_rows['crop_day'].max(),
                       alpha=0.15, color=stage_colors.get(stage, '#cccccc'), label=stage)

    ax2_kc = ax.twinx()
    ax2_kc.plot(season['crop_day'], season['kc'], 'g:', linewidth=1, alpha=0.7, label='Kc')
    ax2_kc.set_ylabel('Crop coefficient (Kc)', color='g', fontsize=8)
    ax2_kc.tick_params(axis='y', labelcolor='g', labelsize=7)
    ax2_kc.set_ylim(0, 1.5)

    ax.set_xlabel('Crop day (days since planting)')
    ax.set_ylabel('Irrigation demand (m³/ha/day)')
    ax.set_title(f'Tomato irrigation equation check (planting {first_planting})')
    ax.legend(fontsize=7, loc='upper left')
    ax.grid(True, alpha=0.3)

    # --- Panel 2: Pumping energy vs well depth ---
    ax = axes[1]
    depths = np.arange(10, 151, 5)
    lifts = np.zeros_like(depths, dtype=float)
    frictions = np.zeros_like(depths, dtype=float)

    for i, d in enumerate(depths):
        lifts[i], frictions[i] = _calculate_pumping_energy(float(d))

    totals = lifts + frictions
    ax.fill_between(depths, 0, lifts, alpha=0.4, color='#3498db', label='Lift energy')
    ax.fill_between(depths, lifts, totals, alpha=0.4, color='#e67e22', label='Friction losses')
    ax.plot(depths, totals, 'k-', linewidth=1.5, label='Total pumping energy')

    # Annotate the reference point (50m well from scenario)
    ref_lift, ref_fric = _calculate_pumping_energy(50.0)
    ax.annotate(f'50m well: {ref_lift + ref_fric:.3f} kWh/m³',
                xy=(50, ref_lift + ref_fric), xytext=(80, ref_lift + ref_fric + 0.1),
                arrowprops=dict(arrowstyle='->', color='black'),
                fontsize=8, bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))

    ax.set_xlabel('Well depth (m)')
    ax.set_ylabel('Pumping energy (kWh/m³)')
    ax.set_title('Pumping energy: Darcy-Weisbach calculation (100 m³/day, 0.3 km pipe)')
    ax.legend(fontsize=7)
    ax.set_xlim(10, 150)
    ax.set_ylim(0, None)
    ax.grid(True, alpha=0.3)

    # --- Panel 3: Treatment energy by salinity ---
    ax = axes[2]
    x_pos = np.arange(len(treatment_specs))
    bars = ax.bar(x_pos, treatment_specs['energy_kwh_per_m3'],
                  color=['#27ae60', '#f39c12', '#e74c3c'], width=0.5, alpha=0.8)

    for i, row in treatment_specs.iterrows():
        ax.text(i, row['energy_kwh_per_m3'] + 0.1,
                f"{row['energy_kwh_per_m3']} kWh/m³\n"
                f"Recovery: {row['recovery_rate_pct']}%\n"
                f"O&M: ${row['maintenance_cost_per_m3']}/m³",
                ha='center', fontsize=8)

    ax.set_xticks(x_pos)
    ax.set_xticklabels([f"{row['salinity_level']}\n({row['tds_ppm']} TDS)"
                        for _, row in treatment_specs.iterrows()])
    ax.set_ylabel('BWRO energy requirement (kWh/m³)')
    ax.set_title('Water treatment energy by salinity level (from equipment CSV)')
    ax.set_ylim(0, treatment_specs['energy_kwh_per_m3'].max() * 1.5)
    ax.grid(True, alpha=0.3, axis='y')

    fig.suptitle('Water system validation: irrigation demand, pumping energy, treatment specs', fontsize=11)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Solar PV validation
# ---------------------------------------------------------------------------

def _load_pv_csv(project_root):
    """Load precomputed PV power CSV."""
    path = Path(project_root) / "data/precomputed/pv_power/pv_normalized_kwh_per_kw_daily-toy.csv"
    df = _load_csv_skip_metadata(path)
    df['date'] = pd.to_datetime(df['date'])
    return df


def _calculate_pv_output(solar_irradiance, temp_max, temp_min, density_variant):
    """PV output calculation — mirrors data/scripts/generate_power_data.calculate_pv_output()."""
    PV_SPECS = {
        'temp_coefficient': -0.004,
        'temp_reference_c': 25,
        'system_losses': 0.15,
    }
    DENSITY_ADJ = {
        'low': {'temp_adjustment_c': 2.0, 'irradiance_factor': 1.0},
        'medium': {'temp_adjustment_c': 0.0, 'irradiance_factor': 1.0},
        'high': {'temp_adjustment_c': -2.0, 'irradiance_factor': 1.0},
    }
    adj = DENSITY_ADJ[density_variant]

    temp_avg = (temp_max + temp_min) / 2
    temp_cell = temp_avg + 25 + adj['temp_adjustment_c']
    temp_diff = temp_cell - PV_SPECS['temp_reference_c']
    temp_factor = 1 + PV_SPECS['temp_coefficient'] * temp_diff
    temp_factor = np.clip(temp_factor, 0.5, 1.1)

    tilt_factor = 1.05
    effective_irradiance = solar_irradiance * tilt_factor * adj['irradiance_factor']
    kwh_per_kw = effective_irradiance * temp_factor * (1 - PV_SPECS['system_losses'])
    kwh_per_kw = np.clip(kwh_per_kw, 0, 10)
    capacity_factor = kwh_per_kw / 24.0
    return kwh_per_kw, capacity_factor


def plot_pv_validation(project_root="."):
    """3-panel solar PV validation figure.

    Panel 1: GHI-to-output relationship — scatter of solar irradiance vs
        precomputed kWh/kW/day for each density variant, overlaid with the
        theoretical line from the PV model at 20°C ambient (no temp derating).
    Panel 2: Temperature derating effect — recalculates the temp factor from
        weather data for each density variant showing how hot days reduce output.
    Panel 3: Monthly mean capacity factors by density variant from precomputed data.
    """
    root = Path(project_root)
    pv_df = _load_pv_csv(project_root)
    weather_df = _load_weather_csv(project_root)

    # Merge weather into PV data for scatter analysis
    merged = pv_df.merge(weather_df[['date', 'solar_irradiance_kwh_m2', 'temp_max_c', 'temp_min_c']],
                         on='date', how='left')

    fig, axes = plt.subplots(3, 1, figsize=(10, 12))

    # --- Panel 1: GHI vs output scatter with theoretical line ---
    ax = axes[0]
    ghi_range = np.linspace(2, 8, 100)

    for density in ['low', 'medium', 'high']:
        color = DENSITY_COLORS[density]
        subset = merged[merged['density_variant'] == density]

        # Downsample for scatter readability (every 10th point)
        sample = subset.iloc[::10]
        ax.scatter(sample['solar_irradiance_kwh_m2'], sample['kwh_per_kw_per_day'],
                   s=3, alpha=0.3, color=color)

        # Theoretical line at 20°C ambient (moderate day, no extreme derating)
        theoretical, _ = _calculate_pv_output(ghi_range, 30.0, 10.0, density)
        ax.plot(ghi_range, theoretical, '-', color=color, linewidth=1.5,
                label=f'{density} (line: 20°C ambient)')

    ax.set_xlabel('Solar irradiance (kWh/m²/day)')
    ax.set_ylabel('PV output (kWh/kW/day)')
    ax.set_title('GHI to PV output: precomputed data (dots) vs model equation (lines)')
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)

    # --- Panel 2: Temperature derating effect ---
    ax = axes[1]

    for density in ['low', 'medium', 'high']:
        color = DENSITY_COLORS[density]
        temp_adj = {'low': 2.0, 'medium': 0.0, 'high': -2.0}[density]

        # Recalculate temperature factor from weather data
        temp_avg = (weather_df['temp_max_c'] + weather_df['temp_min_c']) / 2
        temp_cell = temp_avg + 25 + temp_adj
        temp_factor = 1 + (-0.004) * (temp_cell - 25)
        temp_factor = np.clip(temp_factor, 0.5, 1.1)

        # Monthly average temperature factor
        monthly_tf = temp_factor.groupby(weather_df['date'].dt.month).mean()
        ax.plot(monthly_tf.index, monthly_tf.values, 'o-', color=color,
                linewidth=1.5, markersize=4, label=f'{density} (adj={temp_adj:+.0f}°C)')

    ax.axhline(y=1.0, color='black', linestyle=':', linewidth=0.8, alpha=0.5, label='No derating (STC 25°C)')
    ax.set_xlabel('Month')
    ax.set_ylabel('Temperature factor (1.0 = no derating)')
    ax.set_title('Temperature derating factor by month and density variant')
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'])
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)

    # --- Panel 3: Monthly mean capacity factors ---
    ax = axes[2]
    pv_df['month'] = pv_df['date'].dt.month

    for density in ['low', 'medium', 'high']:
        color = DENSITY_COLORS[density]
        subset = pv_df[pv_df['density_variant'] == density]
        monthly = subset.groupby('month')['capacity_factor'].mean()
        ax.plot(monthly.index, monthly.values, 'o-', color=color,
                linewidth=1.5, markersize=4,
                label=f'{density} (mean CF={subset["capacity_factor"].mean():.3f})')

    ax.set_xlabel('Month')
    ax.set_ylabel('Capacity factor')
    ax.set_title('Monthly mean PV capacity factors from precomputed data')
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'])
    ax.legend(fontsize=7)
    ax.set_ylim(0, None)
    ax.grid(True, alpha=0.3)

    fig.suptitle('Solar PV validation: GHI-output relationship, temperature derating, seasonal CF', fontsize=11)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Battery system validation
# ---------------------------------------------------------------------------

def _load_battery_specs(project_root):
    """Load battery equipment specs from parameter CSV."""
    path = Path(project_root) / "data/parameters/equipment/batteries-toy.csv"
    return pd.read_csv(path, comment='#')


def plot_battery_validation(project_root="."):
    """3-panel battery system validation figure.

    Uses the same charge/discharge logic from simulation.dispatch_energy()
    applied to a synthetic 30-day demand/generation scenario to verify:

    Panel 1: SOC evolution with bounds — runs the battery through daily
        surplus/deficit cycles and checks that SOC stays within [SOC_min,
        SOC_max] = [0.10, 0.90]. Shows the charge/discharge decisions.
    Panel 2: Round-trip efficiency verification — tracks cumulative energy
        charged vs discharged, confirming that output energy < input energy
        by the expected round-trip loss factor (0.95 * 0.95 = 0.9025).
    Panel 3: Equipment specs comparison — bar chart of battery chemistries
        from the CSV showing capacity, round-trip efficiency, and cycle life.
    """
    root = Path(project_root)
    battery_specs = _load_battery_specs(project_root)

    # Simulation parameters (from initialize_energy_state in simulation.py)
    CAPACITY_KWH = 200.0
    SOC_MIN = 0.10
    SOC_MAX = 0.90
    ETA_CHARGE = 0.95
    ETA_DISCHARGE = 0.95
    # Start at SOC_MIN so every kWh discharged must first have been charged.
    # Starting at 0.50 would pre-load 100 kWh, inflating cumulative OUT vs IN.
    INITIAL_SOC = SOC_MIN

    # Synthetic 30-day scenario: alternating 5-day surplus / 5-day deficit blocks
    # to exercise full charge-then-discharge cycles for round-trip measurement
    np.random.seed(42)
    days = 30
    generation = np.zeros(days)
    demand = np.full(days, 150.0)
    for block in range(days // 5):
        start = block * 5
        if block % 2 == 0:
            generation[start:start + 5] = 250 + np.random.normal(0, 10, 5)
        else:
            generation[start:start + 5] = 80 + np.random.normal(0, 10, 5)
    generation = np.clip(generation, 0, None)

    # Run dispatch logic (mirrors dispatch_energy from simulation.py)
    soc = np.zeros(days + 1)
    soc[0] = INITIAL_SOC
    charge_kwh = np.zeros(days)
    discharge_kwh = np.zeros(days)
    energy_stored = np.zeros(days)
    energy_removed = np.zeros(days)

    for d in range(days):
        net = generation[d] - demand[d]
        ch = 0.0
        dis = 0.0

        if net >= 0:
            # Surplus → charge battery
            surplus = net
            available_room = (SOC_MAX - soc[d]) * CAPACITY_KWH
            max_charge_input = available_room / ETA_CHARGE
            ch = min(surplus, max(0.0, max_charge_input))
        else:
            # Deficit → discharge battery
            deficit = -net
            available_stored = (soc[d] - SOC_MIN) * CAPACITY_KWH
            max_discharge_output = available_stored * ETA_DISCHARGE
            dis = min(deficit, max(0.0, max_discharge_output))

        # Update SOC (same formula as simulation.py line 692)
        stored = ch * ETA_CHARGE
        removed = dis / ETA_DISCHARGE
        soc_delta = (stored - removed) / CAPACITY_KWH
        soc[d + 1] = max(SOC_MIN, min(SOC_MAX, soc[d] + soc_delta))

        charge_kwh[d] = ch
        discharge_kwh[d] = dis
        energy_stored[d] = stored
        energy_removed[d] = removed

    day_nums = np.arange(1, days + 1)

    fig, axes = plt.subplots(3, 1, figsize=(10, 12))

    # --- Panel 1: SOC evolution with charge/discharge bars ---
    ax = axes[0]
    ax.plot(np.arange(0, days + 1), soc * 100, 'b-', linewidth=1.5, label='Battery SOC')
    ax.axhline(y=SOC_MAX * 100, color='red', linestyle='--', linewidth=0.8, label=f'SOC max ({SOC_MAX*100:.0f}%)')
    ax.axhline(y=SOC_MIN * 100, color='red', linestyle='--', linewidth=0.8, label=f'SOC min ({SOC_MIN*100:.0f}%)')
    ax.fill_between(np.arange(0, days + 1), SOC_MIN * 100, SOC_MAX * 100,
                    alpha=0.05, color='green', label='Operating range')

    ax2_bar = ax.twinx()
    ax2_bar.bar(day_nums - 0.15, charge_kwh, width=0.3, color='#27ae60', alpha=0.6, label='Charge')
    ax2_bar.bar(day_nums + 0.15, -discharge_kwh, width=0.3, color='#e74c3c', alpha=0.6, label='Discharge')
    ax2_bar.set_ylabel('Charge(+) / Discharge(-) kWh', fontsize=8)
    ax2_bar.tick_params(axis='y', labelsize=7)

    ax.set_xlabel('Day')
    ax.set_ylabel('State of Charge (%)')
    ax.set_title(f'Battery SOC evolution ({CAPACITY_KWH:.0f} kWh, η_ch={ETA_CHARGE}, η_dis={ETA_DISCHARGE})')
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2_bar.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=7, loc='upper right')
    ax.set_xlim(0, days)
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3)

    # --- Panel 2: Round-trip efficiency verification ---
    ax = axes[1]
    cum_charge_in = np.cumsum(charge_kwh)
    cum_discharge_out = np.cumsum(discharge_kwh)

    ax.plot(day_nums, cum_charge_in, 'b-', linewidth=2, label='Cumulative energy IN (charge)')
    ax.plot(day_nums, cum_discharge_out, 'r-', linewidth=2, label='Cumulative energy OUT (discharge)')
    ax.fill_between(day_nums, cum_discharge_out, cum_charge_in,
                    alpha=0.15, color='purple', label='Round-trip loss')

    # Annotate round-trip ratio
    total_in = cum_charge_in[-1]
    total_out = cum_discharge_out[-1]
    if total_in > 0:
        measured_rte = total_out / total_in
        loss_kwh = total_in - total_out
        ax.annotate(
            f'OUT/IN = {total_out:.0f}/{total_in:.0f} = {measured_rte:.3f}\n'
            f'Expected η = {ETA_CHARGE}×{ETA_DISCHARGE} = {ETA_CHARGE * ETA_DISCHARGE:.4f}\n'
            f'Total loss: {loss_kwh:.0f} kWh',
            xy=(days, (total_in + total_out) / 2), xytext=(days * 0.45, total_in * 0.85),
            arrowprops=dict(arrowstyle='->', color='black'),
            fontsize=9, bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow', alpha=0.9))

    ax.set_xlabel('Day')
    ax.set_ylabel('Cumulative energy (kWh)')
    ax.set_title('Round-trip efficiency: energy IN must always exceed energy OUT')
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)

    # --- Panel 3: Battery chemistry comparison from equipment CSV ---
    ax = axes[2]
    x_pos = np.arange(len(battery_specs))
    bar_width = 0.25

    # Normalize values for grouped bar chart
    cap_norm = battery_specs['capacity_kwh'] / battery_specs['capacity_kwh'].max()
    rte_vals = battery_specs['round_trip_efficiency'] * 100
    cycle_norm = battery_specs['cycle_life'] / battery_specs['cycle_life'].max() * 100

    bars1 = ax.bar(x_pos - bar_width, cap_norm * 100, bar_width, label='Capacity (% of max)', color='#3498db', alpha=0.8)
    bars2 = ax.bar(x_pos, rte_vals, bar_width, label='Round-trip efficiency (%)', color='#2ecc71', alpha=0.8)
    bars3 = ax.bar(x_pos + bar_width, cycle_norm, bar_width, label='Cycle life (% of max)', color='#e67e22', alpha=0.8)

    # Add value annotations on efficiency bars
    for i, row in battery_specs.iterrows():
        ax.text(i, rte_vals.iloc[i] + 1, f'{rte_vals.iloc[i]:.0f}%', ha='center', fontsize=7, fontweight='bold')
        ax.text(i - bar_width, cap_norm.iloc[i] * 100 + 1, f'{row["capacity_kwh"]:.0f}\nkWh', ha='center', fontsize=6)

    labels = [t.replace('_', '\n') for t in battery_specs['battery_type']]
    ax.set_xticks(x_pos)
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylabel('Normalized value (%)')
    ax.set_title('Battery chemistry comparison (from equipment CSV)')
    ax.legend(fontsize=7)
    ax.set_ylim(0, 115)
    ax.grid(True, alpha=0.3, axis='y')

    fig.suptitle('Battery validation: SOC bounds, round-trip efficiency, equipment specs', fontsize=11)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Food processing validation
# ---------------------------------------------------------------------------

def _load_processing_specs(project_root):
    """Load research-grade processing specs (per data_registry.yaml)."""
    path = Path(project_root) / "data/parameters/crops/processing_specs-research.csv"
    return pd.read_csv(path, comment='#')


def _load_post_harvest_losses(project_root):
    """Load research-grade post-harvest losses (per data_registry.yaml)."""
    path = Path(project_root) / "data/parameters/crops/post_harvest_losses-research.csv"
    return pd.read_csv(path, comment='#')


def _load_fresh_crop_prices(project_root, crop):
    """Load monthly fresh crop price time series."""
    path = Path(project_root) / f"data/prices/crops/historical_{crop}_prices-toy.csv"
    df = pd.read_csv(path, comment='#')
    df['date'] = pd.to_datetime(df['date'])
    return df


def _load_electricity_prices(project_root):
    """Load monthly grid electricity price time series."""
    path = Path(project_root) / "data/prices/electricity/historical_grid_electricity_prices-toy.csv"
    df = pd.read_csv(path, comment='#')
    df['date'] = pd.to_datetime(df['date'])
    return df


def plot_food_processing_validation(project_root="."):
    """5-panel food processing profit validation figure.

    For each crop, plots monthly net profit per kg fresh input for all 4
    processing pathways (fresh, packaged, canned, dried) over the 2015-2024
    price history.

    Revenue mirrors simulation.process_harvests():
        output_wt = (1 - weight_loss_pct / 100)
        sellable_wt = output_wt * (1 - post_harvest_loss / 100)
        revenue = sellable_wt * fresh_price * value_add_multiplier

    Full cost model per kg fresh input:
        1. Processing energy:  energy_kwh_per_kg * electricity_price
        2. Processing labor:   labor_hours_per_kg * wage
        3. Equipment O&M:      per-kg maintenance (operating_costs CSV)
        4. Packaging material:  container cost per kg output (packaging CSVs)
        5. Packaging labor:    packing labor per kg output * wage
        6. Packaging energy:   sealing energy per kg output * electricity_price

    Note: Storage/inventory holding costs not included (MVP spec per
    calculations.md line 1597).
    """
    crops = ['tomato', 'potato', 'onion', 'kale', 'cucumber']
    pathways = ['fresh', 'packaged', 'canned', 'dried']

    # --- Pathway → packaging type mapping ---
    # fresh: cardboard boxes for market transport (fresh_packaging CSV)
    # packaged/dried: sealed bags (processed_packaging CSV)
    # canned: metal cans (processed_packaging CSV)
    PATHWAY_PKG_TYPE = {
        'fresh': 'cardboard_box',
        'packaged': 'sealed_bag',
        'canned': 'metal_can',
        'dried': 'sealed_bag',
    }
    # Pathway → equipment O&M category (operating_costs CSV)
    PATHWAY_OM_KEY = {
        'fresh': None,
        'packaged': 'processing_packaging',
        'canned': 'processing_canning',
        'dried': 'processing_drying',
    }

    root = Path(project_root)

    # Load processing specs and post-harvest losses (research grade)
    proc_specs = _load_processing_specs(project_root)
    phl = _load_post_harvest_losses(project_root)
    elec_df = _load_electricity_prices(project_root)

    # Processing worker wage
    labor_df = pd.read_csv(root / "data/parameters/labor/labor_wages-research.csv", comment='#')
    labor_wage = labor_df.loc[
        labor_df['worker_category'] == 'processing_worker', 'usd_per_hour'
    ].iloc[0]

    # Equipment O&M costs per kg input
    om_df = pd.read_csv(root / "data/parameters/costs/operating_costs-toy.csv", comment='#')
    om_costs = {}
    for pathway, om_key in PATHWAY_OM_KEY.items():
        if om_key is None:
            om_costs[pathway] = 0.0
        else:
            om_costs[pathway] = om_df.loc[
                om_df['equipment_type'] == om_key, 'usd_per_unit'
            ].iloc[0]

    # Packaging cost lookup: {pathway: {material, labor_hrs, energy_kwh}} per kg output
    proc_pkg = pd.read_csv(root / "data/parameters/equipment/processed_packaging-toy.csv", comment='#')
    fresh_pkg = pd.read_csv(root / "data/parameters/equipment/fresh_packaging-toy.csv", comment='#')

    pkg_lookup = {}
    for pathway, pkg_type in PATHWAY_PKG_TYPE.items():
        src_df = fresh_pkg if pathway == 'fresh' else proc_pkg
        row = src_df[src_df['packaging_type'] == pkg_type].iloc[0]
        pkg_lookup[pathway] = {
            'material': row['material_cost_per_kg'],
            'labor_hrs': row['labor_hours_per_kg'],
            'energy_kwh': row['energy_kwh_per_kg'],
        }

    fig, axes = plt.subplots(5, 1, figsize=(12, 20))

    for idx, crop in enumerate(crops):
        ax = axes[idx]
        crop_prices = _load_fresh_crop_prices(project_root, crop)

        merged = crop_prices.merge(
            elec_df[['date', 'usd_per_kwh_avg_daily']], on='date', how='left'
        )
        elec_price = merged['usd_per_kwh_avg_daily']

        for pathway in pathways:
            spec = proc_specs[
                (proc_specs['crop_name'] == crop)
                & (proc_specs['processing_type'] == pathway)
            ].iloc[0]

            phl_row = phl[
                (phl['crop_name'] == crop) & (phl['pathway'] == pathway)
            ]
            loss_pct = phl_row['loss_pct'].iloc[0] if not phl_row.empty else 0.0

            output_wt = 1.0 - spec['weight_loss_pct'] / 100.0
            sellable_wt = output_wt * (1.0 - loss_pct / 100.0)
            revenue = sellable_wt * merged['usd_per_kg'] * spec['value_add_multiplier']

            # --- Full cost per kg fresh input ---
            # 1-2. Processing energy + labor (from processing_specs)
            proc_energy = spec['energy_kwh_per_kg'] * elec_price
            proc_labor = spec['labor_hours_per_kg'] * labor_wage

            # 3. Equipment O&M (from operating_costs, per kg input)
            equip_om = om_costs[pathway]

            # 4-6. Packaging: material + labor + energy
            pkg = pkg_lookup[pathway]
            if pathway == 'fresh':
                # Fresh packaging costs are already per kg of produce
                pkg_material = pkg['material']
                pkg_labor = pkg['labor_hrs'] * labor_wage
                pkg_energy = pkg['energy_kwh'] * elec_price
            else:
                # Processed packaging costs are per kg output; scale to per kg input
                pkg_material = pkg['material'] * output_wt
                pkg_labor = pkg['labor_hrs'] * labor_wage * output_wt
                pkg_energy = pkg['energy_kwh'] * elec_price * output_wt

            total_cost = (proc_energy + proc_labor + equip_om
                          + pkg_material + pkg_labor + pkg_energy)
            profit = revenue - total_cost

            mean_profit = profit.mean()
            ax.plot(
                merged['date'], profit,
                color=PATHWAY_COLORS[pathway],
                linestyle=PATHWAY_STYLES[pathway],
                linewidth=1.5, alpha=0.85,
                label=f'{pathway} (avg ${mean_profit:.3f}/kg)',
            )

        ax.set_ylabel('Profit (USD/kg input)')
        ax.set_title(
            f'{crop.capitalize()} \u2014 net profit by processing pathway',
            color=CROP_COLORS.get(crop, '#333333'),
        )
        ax.legend(fontsize=7, loc='best')
        ax.grid(True, alpha=0.3)
        ax.axhline(y=0, color='black', linewidth=0.5, alpha=0.3)

    axes[-1].set_xlabel('Date')
    fig.suptitle(
        'Food processing profit per kg fresh input\n'
        'Costs: processing energy + labor + equipment O&M + packaging (material + labor + energy)',
        fontsize=10,
    )
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Community buildings validation
# ---------------------------------------------------------------------------

BUILDING_COLORS = {
    'office_admin': '#3498db',
    'storage_warehouse': '#95a5a6',
    'meeting_hall': '#9b59b6',
    'workshop_maintenance': '#e67e22',
}


def _load_community_energy_csv(project_root):
    """Load precomputed community building energy demand CSV."""
    path = Path(project_root) / "data/precomputed/community_buildings/community_buildings_energy_kwh_per_day-toy.csv"
    df = _load_csv_skip_metadata(path)
    df['date'] = pd.to_datetime(df['date'])
    return df


def _load_community_water_csv(project_root):
    """Load precomputed community building water demand CSV."""
    path = Path(project_root) / "data/precomputed/community_buildings/community_buildings_water_m3_per_day-toy.csv"
    df = _load_csv_skip_metadata(path)
    df['date'] = pd.to_datetime(df['date'])
    return df


def plot_community_buildings_validation(project_root="."):
    """4-panel community buildings validation figure.

    Panel 1: Daily energy demand by building type (first 2 years) — stacked
        area chart showing the contribution of each building type to total
        community building energy demand, with seasonal variation due to
        temperature-dependent cooling/ventilation loads.
    Panel 2: Daily water demand by building type (first 2 years) — stacked
        area chart showing water consumption across building types, with
        modest temperature-dependent increase in hot weather.
    Panel 3: Monthly mean energy demand by building type — shows the
        seasonal cooling pattern with higher loads in summer months.
    Panel 4: Monthly mean water demand by building type — shows the
        temperature effect on water consumption (cleaning, etc.).
    """
    root = Path(project_root)

    # Load data
    energy_df = _load_community_energy_csv(project_root)
    water_df = _load_community_water_csv(project_root)
    weather_df = _load_weather_csv(project_root)

    # Merge weather for context (temperature)
    energy_merged = energy_df.merge(
        weather_df[['date', 'temp_max_c']], on='date', how='left'
    )
    water_merged = water_df.merge(
        weather_df[['date', 'temp_max_c']], on='date', how='left'
    )

    # Building types and their column names
    building_types = ['office_admin', 'storage_warehouse', 'meeting_hall', 'workshop_maintenance']
    building_labels = {
        'office_admin': 'Office/Admin',
        'storage_warehouse': 'Storage/Warehouse',
        'meeting_hall': 'Meeting Hall',
        'workshop_maintenance': 'Workshop/Maintenance',
    }

    fig, axes = plt.subplots(4, 1, figsize=(12, 16))

    # --- Panel 1: Daily energy demand (first 2 years, stacked area) ---
    ax = axes[0]
    cutoff = energy_df['date'].min() + pd.DateOffset(years=2)
    subset = energy_merged[energy_merged['date'] < cutoff].copy()

    # Prepare data for stacked area chart
    dates = subset['date']
    energy_stack = np.zeros(len(subset))

    for btype in building_types:
        col = f"{btype}_kwh"
        values = subset[col].values
        ax.fill_between(
            dates, energy_stack, energy_stack + values,
            alpha=0.7, color=BUILDING_COLORS[btype],
            label=building_labels[btype]
        )
        energy_stack += values

    # Total line overlay
    ax.plot(dates, subset['total_community_buildings_kwh'],
            'k-', linewidth=1, alpha=0.5, label='Total')

    ax.set_ylabel('Energy demand (kWh/day)')
    ax.set_title('Daily community building energy demand (first 2 years)')
    ax.legend(fontsize=8, loc='upper left')
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_xlim(dates.min(), dates.max())
    ax.set_ylim(0, subset['total_community_buildings_kwh'].max() * 1.1)

    # --- Panel 2: Daily water demand (first 2 years, stacked area) ---
    ax = axes[1]
    subset = water_merged[water_merged['date'] < cutoff].copy()

    # Prepare data for stacked area chart
    dates = subset['date']
    water_stack = np.zeros(len(subset))

    for btype in building_types:
        col = f"{btype}_m3"
        values = subset[col].values
        ax.fill_between(
            dates, water_stack, water_stack + values,
            alpha=0.7, color=BUILDING_COLORS[btype],
            label=building_labels[btype]
        )
        water_stack += values

    # Total line overlay
    ax.plot(dates, subset['total_community_buildings_m3'],
            'k-', linewidth=1, alpha=0.5, label='Total')

    ax.set_ylabel('Water demand (m³/day)')
    ax.set_title('Daily community building water demand (first 2 years)')
    ax.legend(fontsize=8, loc='upper left')
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_xlim(dates.min(), dates.max())
    ax.set_ylim(0, subset['total_community_buildings_m3'].max() * 1.1)

    # --- Panel 3: Monthly mean energy demand ---
    ax = axes[3]
    energy_df['month'] = energy_df['date'].dt.month

    # Stack order: bottom to top
    bottom = np.zeros(12)
    for btype in building_types:
        col = f"{btype}_kwh"
        monthly = energy_df.groupby('month')[col].mean()
        ax.bar(
            monthly.index, monthly.values, bottom=bottom,
            color=BUILDING_COLORS[btype], alpha=0.8,
            label=building_labels[btype], width=0.8
        )
        bottom += monthly.values

    # Total line overlay
    monthly_total = energy_df.groupby('month')['total_community_buildings_kwh'].mean()
    ax.plot(monthly_total.index, monthly_total.values, 'ko-',
            linewidth=2, markersize=5, label='Total', zorder=10)

    # Annotate min/max months
    min_month = monthly_total.idxmin()
    max_month = monthly_total.idxmax()
    ax.annotate(
        f'Min: {monthly_total[min_month]:.0f} kWh/day',
        xy=(min_month, monthly_total[min_month]),
        xytext=(min_month, monthly_total[min_month] - 15),
        ha='center', fontsize=8,
        bbox=dict(boxstyle='round,pad=0.3', facecolor='lightblue', alpha=0.7)
    )
    ax.annotate(
        f'Max: {monthly_total[max_month]:.0f} kWh/day',
        xy=(max_month, monthly_total[max_month]),
        xytext=(max_month, monthly_total[max_month] + 10),
        ha='center', fontsize=8,
        bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow', alpha=0.7)
    )

    ax.set_xlabel('Month')
    ax.set_ylabel('Energy demand (kWh/day)')
    ax.set_title('Monthly mean energy demand (cooling/ventilation varies with temperature)')
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'])
    ax.legend(fontsize=8, loc='upper left')
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim(0, None)

    # --- Panel 4: Monthly mean water demand ---
    ax = axes[2]
    water_df['month'] = water_df['date'].dt.month

    # Stack order: bottom to top
    bottom = np.zeros(12)
    for btype in building_types:
        col = f"{btype}_m3"
        monthly = water_df.groupby('month')[col].mean()
        ax.bar(
            monthly.index, monthly.values, bottom=bottom,
            color=BUILDING_COLORS[btype], alpha=0.8,
            label=building_labels[btype], width=0.8
        )
        bottom += monthly.values

    # Total line overlay
    monthly_total = water_df.groupby('month')['total_community_buildings_m3'].mean()
    ax.plot(monthly_total.index, monthly_total.values, 'ko-',
            linewidth=2, markersize=5, label='Total', zorder=10)

    # Annotate min/max months
    min_month = monthly_total.idxmin()
    max_month = monthly_total.idxmax()
    ax.annotate(
        f'Min: {monthly_total[min_month]:.1f} m³/day',
        xy=(min_month, monthly_total[min_month]),
        xytext=(min_month, monthly_total[min_month] - 0.5),
        ha='center', fontsize=8,
        bbox=dict(boxstyle='round,pad=0.3', facecolor='lightblue', alpha=0.7)
    )
    ax.annotate(
        f'Max: {monthly_total[max_month]:.1f} m³/day',
        xy=(max_month, monthly_total[max_month]),
        xytext=(max_month, monthly_total[max_month] + 0.5),
        ha='center', fontsize=8,
        bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow', alpha=0.7)
    )

    ax.set_xlabel('Month')
    ax.set_ylabel('Water demand (m³/day)')
    ax.set_title('Monthly mean water demand (increases with temperature for cleaning)')
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'])
    ax.legend(fontsize=8, loc='upper left')
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim(0, None)

    fig.suptitle(
        'Community buildings validation: daily energy/water demand by building type',
        fontsize=11
    )
    fig.tight_layout()
    return fig
