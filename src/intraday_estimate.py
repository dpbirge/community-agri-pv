"""Intraday battery adequacy estimation from daily energy balance totals.

Uses normalized hourly shape factors to decompose daily generation and demand
totals into estimated hourly profiles, then computes the minimum battery
capacity needed to handle within-day timing mismatches between solar/wind
generation and community/water demand.

Completely standalone — no imports from other src/ modules. Takes a daily
energy balance DataFrame as input and produces an independent hourly estimate
DataFrame and daily adequacy summary.

The cumulative-net-energy method is a standard storage sizing technique:
for each day, the hourly net load (demand minus generation) is cumulatively
summed, and the range (max - min) of that cumulative curve gives the minimum
battery energy capacity needed to fully bridge the intraday mismatch. Days
where the required swing exceeds usable battery capacity are flagged as
insufficient.

Limitations:
    Shape factors are fixed approximations of typical diurnal profiles.
    Real cloud transients, wind gusts, and demand spikes are invisible.
    This is a screening tool ("is the battery clearly undersized?"), not a
    replacement for hourly simulation.

Usage:
    from src.intraday_estimate import estimate_intraday_balance, plot_intraday_adequacy

    hourly_df, daily_df = estimate_intraday_balance(
        energy_balance_df=energy_df,
        battery_capacity_kwh=500,
        soc_min=0.2,
        soc_max=0.8,
        years=1,
    )
    fig = plot_intraday_adequacy(daily_df)
"""

import warnings
from datetime import datetime

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch


# ---------------------------------------------------------------------------
# Hourly shape factors (24-element arrays, normalized to sum to 1.0)
# ---------------------------------------------------------------------------

def _make_solar_shape():
    """Sinusoidal bell for solar generation, 6am–6pm, peak at noon.

    Appropriate for Sinai Peninsula (~27 N latitude). Generation window
    spans hours 6–18 with a raised-cosine envelope.
    """
    shape = np.zeros(24)
    for h in range(6, 19):
        shape[h] = np.cos((h - 12) / 6.5 * np.pi / 2) ** 2
    return shape / shape.sum()


def _make_wind_shape():
    """Mild diurnal wind profile with slight afternoon peak.

    Desert sites see modestly higher winds in afternoon from thermal
    convection. Variation is ~15% around the mean.
    """
    shape = np.array([1.0 + 0.15 * np.sin((h - 6) / 24 * 2 * np.pi)
                       for h in range(24)])
    return shape / shape.sum()


def _make_building_demand_shape():
    """Bimodal residential/commercial demand: morning and evening peaks."""
    shape = np.array([
        0.02, 0.02, 0.02, 0.02, 0.02, 0.03,
        0.04, 0.06, 0.07, 0.06, 0.05, 0.04,
        0.04, 0.04, 0.04, 0.04, 0.05, 0.06,
        0.07, 0.08, 0.07, 0.06, 0.04, 0.03,
    ], dtype=float)
    return shape / shape.sum()


def _make_water_demand_shape():
    """Daytime pumping/irrigation block, 6am–6pm, morning-weighted."""
    shape = np.zeros(24)
    shape[6:18] = 1.0
    shape[6:10] = 1.3
    return shape / shape.sum()


def _make_water_midday_shape():
    """Pumping concentrated into 10:00–16:00 peak solar window."""
    shape = np.zeros(24)
    shape[10:16] = 1.0
    return shape / shape.sum()


def _make_water_afternoon_shape():
    """Pumping spread across 12:00–18:00, delayed start."""
    shape = np.zeros(24)
    shape[12:18] = 1.0
    return shape / shape.sum()


_SOLAR = _make_solar_shape()
_WIND = _make_wind_shape()
_BUILDING = _make_building_demand_shape()
_WATER = _make_water_demand_shape()
_WATER_MIDDAY = _make_water_midday_shape()
_WATER_AFTERNOON = _make_water_afternoon_shape()

_WATER_SCHEDULES = {
    'morning': _WATER,
    'midday': _WATER_MIDDAY,
    'afternoon': _WATER_AFTERNOON,
}


# ---------------------------------------------------------------------------
# Core estimation
# ---------------------------------------------------------------------------

def _subset_years(df, years):
    """Subset DataFrame to first N years. None returns all data."""
    if years is None:
        return df.copy()
    start_year = df['day'].dt.year.min()
    return df[df['day'].dt.year < start_year + years].copy()


def estimate_intraday_balance(energy_balance_df, *, battery_capacity_kwh,
                               soc_min=0.2, soc_max=0.8, years=1):
    """Estimate hourly energy profiles and battery adequacy from daily totals.

    Decomposes daily solar, wind, building demand, and water demand into
    estimated hourly values using canonical shape factors. Runs an hour-by-hour
    battery SOC simulation for each day to determine whether the battery can
    cover all deficit hours (demand > generation) without hitting its SOC floor.

    Surplus that exceeds battery capacity is flagged separately as uncaptured
    (it would go to grid export or curtailment), which is normal for
    grid-connected systems and does not count as a battery failure.

    Args:
        energy_balance_df: DataFrame with columns: day, total_solar_kwh,
            total_wind_kwh, community_energy_demand_kwh,
            water_energy_demand_kwh.
        battery_capacity_kwh: Total battery capacity in kWh.
        soc_min: Minimum SOC fraction (default 0.2).
        soc_max: Maximum SOC fraction (default 0.8).
        years: Number of years from start to analyze. None for all.

    Returns:
        Tuple of (hourly_df, daily_df) where:
            hourly_df: 24 rows per day with estimated hourly generation,
                demand, net energy, and simulated battery SOC.
            daily_df: One row per day with adequacy metrics. Key columns:
                intraday_sufficient — True if battery never hits SOC floor
                    (all deficit hours covered without grid import).
                unmet_deficit_kwh — energy the battery could not discharge
                    because SOC hit the floor (would require grid import).
                uncaptured_surplus_kwh — surplus the battery could not absorb
                    because SOC hit the ceiling (would go to grid export).
                intraday_swing_kwh — total cumulative range (theoretical
                    minimum battery for zero grid interaction).
    """
    sub = _subset_years(energy_balance_df, years)

    soc_max_kwh = battery_capacity_kwh * soc_max
    soc_min_kwh = battery_capacity_kwh * soc_min
    usable = soc_max_kwh - soc_min_kwh
    soc_init_kwh = (soc_min_kwh + soc_max_kwh) / 2

    hourly_rows = []
    daily_rows = []

    for _, row in sub.iterrows():
        day = row['day']
        solar_daily = row['total_solar_kwh']
        wind_daily = row['total_wind_kwh']
        building_daily = row['community_energy_demand_kwh']
        water_daily = row['water_energy_demand_kwh']

        # Decompose to hourly via shape factors
        solar_h = solar_daily * _SOLAR
        wind_h = wind_daily * _WIND
        gen_h = solar_h + wind_h

        building_h = building_daily * _BUILDING
        water_h = water_daily * _WATER
        demand_h = building_h + water_h

        # Positive net = deficit (demand > generation), negative = surplus
        net_h = demand_h - gen_h
        cumulative = np.cumsum(net_h)
        swing = cumulative.max() - cumulative.min()

        # Hour-by-hour SOC simulation
        soc = soc_init_kwh
        unmet_deficit = 0.0
        uncaptured_surplus = 0.0
        floor_hours = 0
        ceiling_hours = 0

        for h in range(24):
            if net_h[h] > 0:
                # Deficit: discharge battery
                available = soc - soc_min_kwh
                discharged = min(net_h[h], available)
                unmet = net_h[h] - discharged
                soc -= discharged
                unmet_deficit += unmet
            else:
                # Surplus: charge battery
                headroom = soc_max_kwh - soc
                absorbed = min(-net_h[h], headroom)
                uncaptured = (-net_h[h]) - absorbed
                soc += absorbed
                uncaptured_surplus += uncaptured
                unmet = 0.0

            if soc <= soc_min_kwh + 0.01:
                floor_hours += 1
            if soc >= soc_max_kwh - 0.01:
                ceiling_hours += 1

            hourly_rows.append({
                'day': day,
                'hour': h,
                'est_solar_kwh': solar_h[h],
                'est_wind_kwh': wind_h[h],
                'est_generation_kwh': gen_h[h],
                'est_building_demand_kwh': building_h[h],
                'est_water_demand_kwh': water_h[h],
                'est_demand_kwh': demand_h[h],
                'est_net_kwh': net_h[h],
                'est_cumulative_net_kwh': cumulative[h],
                'est_battery_soc_kwh': soc,
            })

        daily_rows.append({
            'day': day,
            'intraday_swing_kwh': swing,
            'usable_capacity_kwh': usable,
            'unmet_deficit_kwh': unmet_deficit,
            'uncaptured_surplus_kwh': uncaptured_surplus,
            'intraday_sufficient': unmet_deficit < 0.01,
            'floor_hours': floor_hours,
            'ceiling_hours': ceiling_hours,
            'peak_surplus_kw': max(-net_h.min(), 0),
            'peak_deficit_kw': max(net_h.max(), 0),
            'daily_generation_kwh': solar_daily + wind_daily,
            'daily_demand_kwh': building_daily + water_daily,
        })

    hourly_df = pd.DataFrame(hourly_rows)
    daily_df = pd.DataFrame(daily_rows)

    return hourly_df, daily_df


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------

def _dark_mode_style():
    """Dark theme after 6 PM, default otherwise."""
    if datetime.now().hour >= 18:
        dark_params = {**plt.style.library['dark_background'],
                       'figure.facecolor': '#333333', 'axes.facecolor': '#333333'}
        return plt.style.context(dark_params)
    return plt.style.context('default')


def plot_intraday_adequacy(daily_df, *, hspace=0.35):
    """Plot intraday battery adequacy: unmet deficit, uncaptured surplus, and strip.

    Top panel: daily unmet deficit (red, energy battery couldn't discharge)
    and uncaptured surplus (blue, energy battery couldn't absorb) as stacked
    area fills. Unmet deficit requires grid import; uncaptured surplus goes
    to grid export — normal for grid-connected systems.

    Bottom panel: heatmap strip showing sufficient (green) vs insufficient
    (red) days. A day is insufficient only when the battery hits its SOC
    floor and cannot cover demand (unmet deficit > 0).

    Args:
        daily_df: Daily summary DataFrame from estimate_intraday_balance.
        hspace: Vertical spacing between subplots.

    Returns:
        matplotlib Figure.
    """
    with _dark_mode_style():
        fig, (ax_main, ax_strip) = plt.subplots(
            2, 1, figsize=(14, 4.5), sharex=False,
            gridspec_kw={'height_ratios': [3, 0.5], 'hspace': hspace}
        )

        # --- Top: unmet deficit and uncaptured surplus ---
        has_deficit = daily_df['unmet_deficit_kwh'].max() > 0.01
        has_surplus = daily_df['uncaptured_surplus_kwh'].max() > 0.01

        if has_deficit:
            ax_main.fill_between(
                daily_df['day'], daily_df['unmet_deficit_kwh'],
                color='#ef5350', alpha=0.5, label='Unmet Deficit (needs grid import)'
            )
            ax_main.plot(daily_df['day'], daily_df['unmet_deficit_kwh'],
                         color='#ef5350', linewidth=0.6)

        if has_surplus:
            ax_main.fill_between(
                daily_df['day'], daily_df['uncaptured_surplus_kwh'],
                color='#42a5f5', alpha=0.3, label='Uncaptured Surplus (to grid export)'
            )
            ax_main.plot(daily_df['day'], daily_df['uncaptured_surplus_kwh'],
                         color='#42a5f5', linewidth=0.6)

        if not has_deficit and not has_surplus:
            ax_main.text(0.5, 0.5, 'Battery handles all intraday balancing',
                         transform=ax_main.transAxes, ha='center', va='center',
                         fontsize=12, color='#66bb6a')

        ax_main.set_ylabel('Energy (kWh)')
        ax_main.set_ylim(bottom=0)
        ax_main.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda x, _: f'{x:,.0f}')
        )
        ax_main.grid(True, which='major', axis='both',
                      linestyle='--', linewidth=0.5, alpha=0.7)
        ax_main.legend(loc='upper right', fontsize=8)
        ax_main.set_title('Intraday Battery Adequacy — SOC Simulation')

        # --- Bottom: sufficient/insufficient strip ---
        categories = ['Sufficient', 'Insufficient']
        colors = ['#66bb6a', '#ef5350']
        cmap = ListedColormap(colors)
        norm = BoundaryNorm([0, 1, 2], cmap.N)

        vals = (~daily_df['intraday_sufficient']).astype(int).values

        ax_strip.imshow(
            vals.reshape(1, -1), aspect='auto', interpolation='nearest',
            cmap=cmap, norm=norm,
            extent=[mdates.date2num(daily_df['day'].iloc[0]),
                    mdates.date2num(daily_df['day'].iloc[-1]), 0, 1]
        )
        ax_strip.set_yticks([])
        ax_strip.set_ylabel('Adequate', fontsize=7)
        ax_strip.set_facecolor('white')
        patches = [Patch(facecolor=c, label=cat) for c, cat in zip(colors, categories)]
        ax_strip.legend(handles=patches, loc='upper right', fontsize=7, ncol=2)

        # Month labels on both panels
        for ax in (ax_main, ax_strip):
            if ax == ax_strip:
                ax.xaxis_date()
                ax.set_xlim(mdates.date2num(daily_df['day'].iloc[0]),
                            mdates.date2num(daily_df['day'].iloc[-1]))
            else:
                ax.set_xlim(daily_df['day'].min(), daily_df['day'].max())
            ax.xaxis.set_major_locator(mdates.MonthLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
            plt.setp(ax.get_xticklabels(), rotation=45, ha='right', fontsize=10.5)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            fig.tight_layout()
        return fig


def plot_hourly_profiles():
    """Plot the four normalized hourly shape factors used for decomposition.

    Shows solar generation, wind generation, building demand, and water/pumping
    demand profiles on a single axes with hours 0–23 on the x-axis and fraction
    of daily total on the y-axis.

    Returns:
        matplotlib Figure.
    """
    hours = np.arange(24)

    with _dark_mode_style():
        fig, ax = plt.subplots(figsize=(10, 4.5))

        ax.fill_between(hours, _SOLAR, alpha=0.15, color='#ffa726')
        ax.plot(hours, _SOLAR, color='#ffa726', linewidth=2, label='Solar Generation')

        ax.fill_between(hours, _WIND, alpha=0.15, color='#42a5f5')
        ax.plot(hours, _WIND, color='#42a5f5', linewidth=2, label='Wind Generation')

        ax.plot(hours, _BUILDING, color='#ef5350', linewidth=2,
                linestyle='--', label='Building Demand')
        ax.plot(hours, _WATER, color='#66bb6a', linewidth=2,
                linestyle='--', label='Water/Pumping Demand')

        ax.set_xlim(0, 23)
        ax.set_xticks(hours)
        ax.set_xticklabels([f'{h:02d}:00' if h % 3 == 0 else '' for h in hours])
        ax.set_xlabel('Hour of Day')
        ax.set_ylabel('Fraction of Daily Total')
        ax.set_ylim(bottom=0)
        ax.set_title('Hourly Shape Factor Assumptions')
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, which='major', axis='both',
                linestyle='--', linewidth=0.5, alpha=0.7)
        fig.tight_layout()

    return fig


def _select_days_by_category(hourly_df, daily_df, soc_min_kwh, soc_max_kwh, n_per_cat=10):
    """Select days from three SOC categories using terciles of min SOC.

    Splits sufficient days (no unmet deficit) into upper and lower halves
    by their minimum SOC reached during the day. Insufficient days (unmet
    deficit > 0) form the third category.

    Args:
        hourly_df: Hourly DataFrame with est_battery_soc_kwh.
        daily_df: Daily summary DataFrame with unmet_deficit_kwh.
        soc_min_kwh: SOC floor in kWh.
        soc_max_kwh: SOC ceiling in kWh.
        n_per_cat: Max days to select per category.

    Returns:
        List of (category_label, day_values) tuples.
    """
    min_soc = hourly_df.groupby('day')['est_battery_soc_kwh'].min()
    daily_with_soc = daily_df.set_index('day').assign(min_soc_kwh=min_soc)

    # Separate insufficient days first
    insufficient = daily_with_soc[daily_with_soc['unmet_deficit_kwh'] > 0.01]
    insufficient = insufficient.sort_values('unmet_deficit_kwh', ascending=False)

    sufficient = daily_with_soc[daily_with_soc['unmet_deficit_kwh'] <= 0.01]

    # Split sufficient days at median min-SOC
    if len(sufficient) > 0:
        median_soc = sufficient['min_soc_kwh'].median()
        high_soc = sufficient[sufficient['min_soc_kwh'] >= median_soc]
        high_soc = high_soc.sort_values('min_soc_kwh', ascending=False)
        low_soc = sufficient[sufficient['min_soc_kwh'] < median_soc]
        low_soc = low_soc.sort_values('min_soc_kwh', ascending=True)
    else:
        high_soc = sufficient
        low_soc = sufficient

    categories = []
    for label, subset in [
        (f'Low stress — high min SOC ({len(high_soc)} days)', high_soc),
        (f'Moderate stress — low min SOC ({len(low_soc)} days)', low_soc),
        (f'Battery insufficient — unmet deficit ({len(insufficient)} days)', insufficient),
    ]:
        n = min(n_per_cat, len(subset))
        if n > 0:
            indices = np.linspace(0, len(subset) - 1, n, dtype=int)
            days = subset.index[indices].values
            categories.append((label, days))

    return categories


def plot_intraday_detail(hourly_df, daily_df, *, n_per_category=10,
                          battery_capacity_kwh=None, soc_min=0.2, soc_max=0.8):
    """Plot absolute hourly supply, demand, and battery SOC for selected days.

    Organizes days into three rows by SOC behavior:
        Row 1: SOC stays near full (low stress days).
        Row 2: SOC reaches mid-range (moderate cycling).
        Row 3: Battery insufficient — SOC hits floor, unmet deficit (if any).

    Each subplot shows stacked generation (solar + wind), total demand line,
    and a simulated battery SOC trace on a secondary axis.

    Args:
        hourly_df: Hourly DataFrame from estimate_intraday_balance.
        daily_df: Daily summary DataFrame from estimate_intraday_balance.
        n_per_category: Number of days to display per category (default 10).
        battery_capacity_kwh: Battery capacity for SOC simulation. If None,
            derived from daily_df usable_capacity / (soc_max - soc_min).
        soc_min: Minimum SOC fraction for SOC trace.
        soc_max: Maximum SOC fraction for SOC trace.

    Returns:
        matplotlib Figure.
    """
    if battery_capacity_kwh is None:
        battery_capacity_kwh = daily_df['usable_capacity_kwh'].iloc[0] / (soc_max - soc_min)

    soc_max_kwh = battery_capacity_kwh * soc_max
    soc_min_kwh = battery_capacity_kwh * soc_min

    categories = _select_days_by_category(
        hourly_df, daily_df, soc_min_kwh, soc_max_kwh, n_per_category
    )

    if not categories:
        fig, ax = plt.subplots(figsize=(10, 3))
        ax.text(0.5, 0.5, 'No days to display', transform=ax.transAxes,
                ha='center', va='center', fontsize=12)
        return fig

    nrows = len(categories)
    ncols = max(len(days) for _, days in categories)
    hours = np.arange(24)

    with _dark_mode_style():
        fig, axes = plt.subplots(nrows, ncols,
                                  figsize=(3.2 * ncols, 3.2 * nrows),
                                  squeeze=False)

        for row_idx, (cat_label, selected_days) in enumerate(categories):
            # Row label on leftmost subplot y-axis
            axes[row_idx][0].set_ylabel(cat_label, fontsize=7, fontweight='bold')

            for col_idx in range(ncols):
                ax = axes[row_idx][col_idx]

                if col_idx >= len(selected_days):
                    ax.set_visible(False)
                    continue

                day = selected_days[col_idx]
                day_h = hourly_df[hourly_df['day'] == day]

                solar = day_h['est_solar_kwh'].values
                wind = day_h['est_wind_kwh'].values
                demand = day_h['est_demand_kwh'].values
                soc_trace = day_h['est_battery_soc_kwh'].values

                # Stacked generation
                ax.fill_between(hours, 0, solar, alpha=0.5, color='#ffa726', label='Solar')
                ax.fill_between(hours, solar, solar + wind, alpha=0.5,
                                color='#42a5f5', label='Wind')
                ax.plot(hours, demand, color='#ef5350', linewidth=1.5, label='Demand')

                # Battery SOC on secondary axis
                ax2 = ax.twinx()
                ax2.plot(hours, soc_trace, color='black', linewidth=1.2, alpha=0.8)
                ax2.axhline(soc_max_kwh, color='black', linewidth=0.5,
                            linestyle=':', alpha=0.4)
                ax2.axhline(soc_min_kwh, color='black', linewidth=0.5,
                            linestyle=':', alpha=0.4)
                ax2.set_ylim(0, battery_capacity_kwh)
                ax2.tick_params(axis='y', labelsize=5, colors='black')
                if col_idx == len(selected_days) - 1:
                    ax2.set_ylabel('SOC kWh', fontsize=5, color='black')

                # Title with date and key metric
                d_row = daily_df[daily_df['day'] == day].iloc[0]
                sufficient = d_row['intraday_sufficient']
                title_color = '#66bb6a' if sufficient else '#ef5350'
                unmet = d_row['unmet_deficit_kwh']
                subtitle = (f"unmet {unmet:.0f}" if unmet > 0.01
                            else f"min SOC {soc_trace.min():.0f}")
                ax.set_title(f"{pd.Timestamp(day).strftime('%b %d')}\n{subtitle}",
                             fontsize=7, color=title_color)

                ax.set_xlim(0, 23)
                ax.set_xticks([0, 6, 12, 18, 23])
                ax.set_xticklabels(['0', '6', '12', '18', '23'], fontsize=5)
                ax.tick_params(axis='y', labelsize=5)
                ax.set_ylim(bottom=0)
                ax.grid(True, linestyle='--', linewidth=0.3, alpha=0.5)

        # Legend on first subplot only
        axes[0][0].legend(fontsize=5, loc='upper left')

        fig.suptitle(f'Intraday Detail by SOC Category '
                     f'(battery {battery_capacity_kwh:.0f} kWh, '
                     f'usable {soc_min_kwh:.0f}\u2013{soc_max_kwh:.0f} kWh)',
                     fontsize=10)
        fig.tight_layout(rect=[0, 0, 1, 0.95])

    return fig


# ---------------------------------------------------------------------------
# Load-shifting analysis
# ---------------------------------------------------------------------------

def _simulate_day_unmet(solar_daily, wind_daily, building_daily, water_daily,
                        water_shape, soc_init_kwh, soc_min_kwh, soc_max_kwh):
    """Run one day's hourly SOC simulation and return unmet deficit kWh."""
    gen_h = solar_daily * _SOLAR + wind_daily * _WIND
    demand_h = building_daily * _BUILDING + water_daily * water_shape
    net_h = demand_h - gen_h

    soc = soc_init_kwh
    unmet_deficit = 0.0
    for h in range(24):
        if net_h[h] > 0:
            available = soc - soc_min_kwh
            discharged = min(net_h[h], available)
            soc -= discharged
            unmet_deficit += net_h[h] - discharged
        else:
            headroom = soc_max_kwh - soc
            soc += min(-net_h[h], headroom)
    return unmet_deficit


def analyze_load_shifting(energy_balance_df, *, battery_capacity_kwh,
                          soc_min=0.2, soc_max=0.8, years=1):
    """Test whether shifting water pump scheduling reduces unmet battery deficit.

    For each day where the baseline (morning-weighted) water schedule causes
    unmet deficit, re-runs the hourly SOC simulation with midday and afternoon
    water shapes. Reports which schedule minimizes or eliminates grid import.

    Args:
        energy_balance_df: DataFrame with day, total_solar_kwh, total_wind_kwh,
            community_energy_demand_kwh, water_energy_demand_kwh.
        battery_capacity_kwh: Total battery capacity in kWh.
        soc_min: Minimum SOC fraction (default 0.2).
        soc_max: Maximum SOC fraction (default 0.8).
        years: Number of years from start to analyze. None for all.

    Returns:
        DataFrame with one row per insufficient day. Columns:
            day, baseline_unmet_kwh, midday_unmet_kwh, afternoon_unmet_kwh,
            best_schedule, savings_kwh.
    """
    # Run baseline to identify insufficient days
    _, daily_df = estimate_intraday_balance(
        energy_balance_df, battery_capacity_kwh=battery_capacity_kwh,
        soc_min=soc_min, soc_max=soc_max, years=years,
    )
    insufficient = daily_df[daily_df['unmet_deficit_kwh'] > 0.01].copy()

    if insufficient.empty:
        return pd.DataFrame(columns=[
            'day', 'baseline_unmet_kwh', 'midday_unmet_kwh',
            'afternoon_unmet_kwh', 'best_schedule', 'savings_kwh',
        ])

    sub = _subset_years(energy_balance_df, years)
    sub = sub.set_index('day')

    soc_max_kwh = battery_capacity_kwh * soc_max
    soc_min_kwh = battery_capacity_kwh * soc_min
    soc_init_kwh = (soc_min_kwh + soc_max_kwh) / 2

    rows = []
    for _, d_row in insufficient.iterrows():
        day = d_row['day']
        src = sub.loc[day]
        solar = src['total_solar_kwh']
        wind = src['total_wind_kwh']
        building = src['community_energy_demand_kwh']
        water = src['water_energy_demand_kwh']

        results = {}
        for name, shape in _WATER_SCHEDULES.items():
            results[name] = _simulate_day_unmet(
                solar, wind, building, water, shape,
                soc_init_kwh, soc_min_kwh, soc_max_kwh,
            )

        best = min(results, key=results.get)
        rows.append({
            'day': day,
            'baseline_unmet_kwh': results['morning'],
            'midday_unmet_kwh': results['midday'],
            'afternoon_unmet_kwh': results['afternoon'],
            'best_schedule': best,
            'savings_kwh': results['morning'] - results[best],
        })

    return pd.DataFrame(rows)


def plot_load_shifting(shift_df):
    """Plot load-shifting analysis: days resolved and total deficit reduction.

    Left panel: bar chart of insufficient days that become sufficient under
    each schedule. Right panel: total unmet deficit by schedule.

    Args:
        shift_df: DataFrame from analyze_load_shifting.

    Returns:
        matplotlib Figure.
    """
    if shift_df.empty:
        with _dark_mode_style():
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.text(0.5, 0.5, 'No insufficient days — load shifting not needed',
                    transform=ax.transAxes, ha='center', va='center',
                    fontsize=12, color='#66bb6a')
            return fig

    schedules = ['morning', 'midday', 'afternoon']
    col_map = {
        'morning': 'baseline_unmet_kwh',
        'midday': 'midday_unmet_kwh',
        'afternoon': 'afternoon_unmet_kwh',
    }
    colors = {'morning': '#ef5350', 'midday': '#ffa726', 'afternoon': '#42a5f5'}
    n_total = len(shift_df)

    # Count days resolved (unmet < 0.01) and total unmet per schedule
    resolved = {s: (shift_df[col_map[s]] < 0.01).sum() for s in schedules}
    total_unmet = {s: shift_df[col_map[s]].sum() for s in schedules}

    with _dark_mode_style():
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.5))

        # Left: days resolved
        bars = ax1.bar(schedules, [resolved[s] for s in schedules],
                       color=[colors[s] for s in schedules], alpha=0.8)
        ax1.set_ylabel('Days Resolved (deficit eliminated)')
        ax1.set_title(f'Insufficient Days Resolved\n({n_total} insufficient total)')
        ax1.set_ylim(0, max(n_total, 1) * 1.15)
        for bar, val in zip(bars, [resolved[s] for s in schedules]):
            ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                     str(val), ha='center', fontsize=10, fontweight='bold')

        # Right: total unmet deficit
        bars2 = ax2.bar(schedules, [total_unmet[s] for s in schedules],
                        color=[colors[s] for s in schedules], alpha=0.8)
        ax2.set_ylabel('Total Unmet Deficit (kWh)')
        ax2.set_title('Aggregate Unmet Deficit by Schedule')
        ax2.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda x, _: f'{x:,.0f}')
        )
        for bar, val in zip(bars2, [total_unmet[s] for s in schedules]):
            ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                     f'{val:,.0f}', ha='center', va='bottom', fontsize=8)

        fig.suptitle('Water Pump Load Shifting — Impact on Battery Adequacy',
                     fontsize=11, fontweight='bold')
        fig.tight_layout(rect=[0, 0, 1, 0.93])

    return fig


if __name__ == '__main__':
    print("Hourly shape factors (sum to 1.0):")
    for name, shape in [('Solar', _SOLAR), ('Wind', _WIND),
                         ('Building', _BUILDING), ('Water', _WATER),
                         ('Water Midday', _WATER_MIDDAY),
                         ('Water Afternoon', _WATER_AFTERNOON)]:
        print(f"  {name}: sum={shape.sum():.4f}, "
              f"peak hour={shape.argmax()}, peak={shape.max():.4f}")
