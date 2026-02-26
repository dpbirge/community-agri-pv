"""Stacked area plots for community daily energy and water demands."""

import matplotlib.pyplot as plt


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

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
    fig = _stacked_area(df, cols, '_kwh', 'Energy (kWh/day)', title, years)
    plt.close(fig)
    return fig


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
