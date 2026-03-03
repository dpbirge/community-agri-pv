"""Visualization functions for community energy, water demand, and water balance.

Provides stacked area plots for daily energy/water demands and line/heatmap
plots for water balance analysis (demand by source, supply by source, and
daily policy decision strips).

Usage:
    from src.plots import plot_demands, plot_water_balance_summary

    energy_fig, water_fig = plot_demands(demands_df)
    demand_fig, supply_fig, heatmap_fig = plot_water_balance_summary(balance_df)
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _subset_years(df, years):
    """Subset DataFrame to first N years. None = all years."""
    if years is None:
        return df.copy()
    start_year = df['day'].dt.year.min()
    return df[df['day'].dt.year < start_year + years].copy()


def _demand_cols(df, suffix):
    """Return per-type demand columns for a given suffix, excluding total columns."""
    return [c for c in df.columns if c.endswith(suffix) and not c.startswith('total_')]


def _gen_cols(df):
    """Return individual generation columns, excluding subtotals and grand total.

    Keeps per-source columns (e.g. 'low_density_solar_kwh', 'small_turbine_wind_kwh')
    and drops aggregates ('total_solar_kwh', 'total_wind_kwh', 'total_energy_kwh').
    """
    return [c for c in df.columns if c.endswith('_kwh') and not c.startswith('total_')]


def _prettify_label(col, suffix):
    """Convert a column name to a human-readable legend label.

    Example: 'small_household_energy_kwh' -> 'Small Household'
    """
    return col.replace(suffix, '').replace('_', ' ').strip().title()


def _stacked_area(df, cols, suffix, ylabel, title, years):
    """Render a stacked area chart for a set of demand columns.

    Args:
        df: DataFrame from compute_daily_demands.
        cols: Ordered list of column names to stack.
        suffix: Column suffix stripped for legend labels (e.g., '_energy_kwh').
        ylabel: Y-axis label string.
        title: Plot title string.
        years: Number of years to plot from the start of the data. None plots all.

    Returns:
        matplotlib Figure.
    """
    if years is not None:
        start_year = df['day'].dt.year.min()
        df = df[df['day'].dt.year < start_year + years]
    labels = [_prettify_label(c, suffix) for c in cols]
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.stackplot(df['day'], [df[c] for c in cols], labels=labels)
    ax.set_title(title)
    ax.set_xlabel('Date')
    ax.set_ylabel(ylabel)
    ax.legend(loc='upper left', fontsize=8, ncol=2)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def plot_energy_demands(df, *, title='Community Daily Energy Demand', years=None):
    """Stacked area plot of daily energy demand by building and household type.

    Args:
        df: DataFrame returned by compute_daily_demands.
        title: Plot title.
        years: Number of years to plot from the start of the data. None plots all.

    Returns:
        matplotlib Figure.
    """
    cols = _demand_cols(df, '_energy_kwh')
    return _stacked_area(df, cols, '_energy_kwh', 'Energy (kWh/day)', title, years)


def plot_water_demands(df, *, title='Community Daily Water Demand', years=None):
    """Stacked area plot of daily water demand by building and household type.

    Args:
        df: DataFrame returned by compute_daily_demands.
        title: Plot title.
        years: Number of years to plot from the start of the data. None plots all.

    Returns:
        matplotlib Figure.
    """
    cols = _demand_cols(df, '_water_m3')
    return _stacked_area(df, cols, '_water_m3', 'Water (m\u00b3/day)', title, years)


def plot_energy_generation(df, *, title='Community Daily Energy Generation', years=None):
    """Stacked area plot of daily energy generation by source type.

    Args:
        df: DataFrame returned by compute_daily_energy or load_energy.
        title: Plot title.
        years: Number of years to plot from the start of the data. None plots all.

    Returns:
        matplotlib Figure.
    """
    cols = _gen_cols(df)
    return _stacked_area(df, cols, '_kwh', 'Energy (kWh/day)', title, years)


def plot_demands(df, *, energy_title='Community Daily Energy Demand', water_title='Community Daily Water Demand', years=None):
    """Generate stacked area plots for both energy and water demand.

    Args:
        df: DataFrame returned by compute_daily_demands.
        energy_title: Title for the energy plot.
        water_title: Title for the water plot.
        years: Number of years to plot from the start of the data. None plots all.

    Returns:
        Tuple of (energy_fig, water_fig).
    """
    return plot_energy_demands(df, title=energy_title, years=years), plot_water_demands(df, title=water_title, years=years)


# ---------------------------------------------------------------------------
# Water balance visualization
# ---------------------------------------------------------------------------

def plot_water_demand_by_source(df, *, title='Daily Water Demand by Source', years=1):
    """Line plot of daily water demand by source (irrigation, community).

    Args:
        df: DataFrame from compute_daily_water_balance or load_daily_water_balance.
        title: Plot title.
        years: Number of years to plot from the start. Default 1.

    Returns:
        matplotlib Figure.
    """
    sub = _subset_years(df, years)
    fig, ax = plt.subplots(figsize=(14, 5))
    if 'irrigation_demand_m3' in sub.columns:
        ax.plot(sub['day'], sub['irrigation_demand_m3'], label='Irrigation', linewidth=1.0)
    if 'community_water_demand_m3' in sub.columns:
        ax.plot(sub['day'], sub['community_water_demand_m3'], label='Community', linewidth=1.0)
    if 'total_water_demand_m3' in sub.columns:
        ax.plot(sub['day'], sub['total_water_demand_m3'], label='Total', linewidth=1.0, linestyle='--')
    ax.set_title(title)
    ax.set_xlabel('Date')
    ax.set_ylabel('Water (m\u00b3/day)')
    ax.legend(loc='upper right')
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    return fig


def plot_water_supply_by_source(df, *, title='Daily Water Supply by Source', years=1):
    """Line plot of daily water supply by source (GW untreated, GW treated, municipal).

    Args:
        df: DataFrame from compute_daily_water_balance or load_daily_water_balance.
        title: Plot title.
        years: Number of years to plot from the start. Default 1.

    Returns:
        matplotlib Figure.
    """
    sub = _subset_years(df, years)
    fig, ax = plt.subplots(figsize=(14, 5))
    supply_cols = [
        ('gw_untreated_to_tank_m3', 'GW Untreated'),
        ('gw_treated_to_tank_m3', 'GW Treated'),
        ('municipal_to_tank_m3', 'Municipal (irrigation)'),
    ]
    for col, label in supply_cols:
        if col in sub.columns:
            ax.plot(sub['day'], sub[col], label=label, linewidth=1.0)
    if 'municipal_community_m3' in sub.columns:
        ax.plot(sub['day'], sub['municipal_community_m3'], label='Municipal (community)', linewidth=1.0)
    if 'total_sourced_to_tank_m3' in sub.columns:
        ax.plot(sub['day'], sub['total_sourced_to_tank_m3'], label='Total to tank', linewidth=1.0, linestyle='--')
    ax.set_title(title)
    ax.set_xlabel('Date')
    ax.set_ylabel('Water (m\u00b3/day)')
    ax.legend(loc='upper right')
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    return fig


def plot_water_policy_heatmap(df, *, years=1, figsize=(14, 6)):
    """Strip chart of daily policy decisions: primary source, flush reason, deficit.

    Args:
        df: DataFrame from compute_daily_water_balance or load_daily_water_balance.
        years: Number of years to plot from the start. Default 1.
        figsize: Figure size.

    Returns:
        matplotlib Figure.
    """
    from matplotlib.colors import ListedColormap, BoundaryNorm
    from matplotlib.patches import Patch

    sub = _subset_years(df, years)
    required = ['policy_primary_source', 'policy_flush_reason', 'policy_deficit']
    missing = [c for c in required if c not in sub.columns]
    if missing:
        raise ValueError(f"Water balance DataFrame missing policy columns: {missing}")

    n_days = len(sub)
    days = pd.to_datetime(sub['day'])

    source_categories = ['none', 'tank_stock', 'gw_untreated', 'gw_treated', 'municipal', 'mixed']
    source_colors = ['#d9d9d9', '#9ecae1', '#a1d99b', '#31a354', '#fdae6b', '#9467bd']
    source_map = {cat: i for i, cat in enumerate(source_categories)}
    source_vals = sub['policy_primary_source'].map(lambda x: source_map.get(str(x), 0)).values

    flush_categories = ['none', 'tds_exceedance', 'look_ahead_drain']
    flush_colors = ['#d9d9d9', '#e6550d', '#fdae6b']
    flush_map = {cat: i for i, cat in enumerate(flush_categories)}
    flush_vals = sub['policy_flush_reason'].map(lambda x: flush_map.get(str(x), 0)).values

    deficit_categories = ['No deficit', 'Deficit']
    deficit_colors = ['#d9d9d9', '#de2d26']
    deficit_vals = sub['policy_deficit'].astype(int).values

    fig, axes = plt.subplots(3, 1, figsize=figsize, sharex=True,
                              gridspec_kw={'height_ratios': [1, 1, 1], 'hspace': 0.4})

    n_ticks = min(12, max(2, n_days))
    tick_idx = np.linspace(0, n_days - 1, n_ticks).astype(int)

    rows = [
        (axes[0], source_vals, source_colors, source_categories, 'Primary Source'),
        (axes[1], flush_vals, flush_colors, flush_categories, 'Flush Reason'),
        (axes[2], deficit_vals, deficit_colors, deficit_categories, 'Deficit'),
    ]

    for ax, vals, colors, categories, ylabel in rows:
        cmap = ListedColormap(colors)
        norm = BoundaryNorm(list(range(len(colors) + 1)), cmap.N)
        ax.imshow(vals.reshape(1, -1), aspect='auto', interpolation='nearest',
                  cmap=cmap, norm=norm)
        ax.set_yticks([])
        ax.set_ylabel(ylabel, fontsize=9)
        patches = [Patch(facecolor=c, label=cat) for c, cat in zip(colors, categories)]
        ax.legend(handles=patches, loc='upper left', fontsize=7, ncol=len(categories),
                  bbox_to_anchor=(0, -0.1), frameon=False)

    axes[-1].set_xticks(tick_idx)
    axes[-1].set_xticklabels([days.iloc[i].strftime('%Y-%m-%d') for i in tick_idx],
                              rotation=45, ha='right')
    axes[0].set_title('Daily Water Policy Decisions')
    fig.tight_layout()
    return fig


def plot_water_balance_summary(df, *, years=1):
    """Generate all water balance plots: demand, supply, and policy heatmap.

    Args:
        df: DataFrame from compute_daily_water_balance or load_daily_water_balance.
        years: Number of years to plot. Default 1.

    Returns:
        Tuple of (demand_fig, supply_fig, heatmap_fig).
    """
    demand_fig = plot_water_demand_by_source(df, years=years)
    supply_fig = plot_water_supply_by_source(df, years=years)
    heatmap_fig = plot_water_policy_heatmap(df, years=years)
    return demand_fig, supply_fig, heatmap_fig
