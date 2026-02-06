"""
Plotting and table functions for interactive notebook analysis.
"""

import datetime

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def create_summary_table(simulation_state):
    """Create summary table from simulation state."""
    summary_data = []
    for farm in simulation_state.farms:
        total_water = farm.cumulative_groundwater_m3 + farm.cumulative_municipal_m3
        if total_water > 0:
            self_suff = 100 * farm.cumulative_groundwater_m3 / total_water
        else:
            self_suff = 0
        
        summary_data.append({
            'Farm': farm.farm_name,
            'Policy': farm.water_policy_name,
            'Total Water (m³)': f"{total_water:,.0f}",
            'Total Cost (USD)': f"${farm.cumulative_water_cost_usd:,.2f}",
            'Crop Yield (kg)': f"{farm.cumulative_yield_kg:,.0f}",
            'Crop Revenue (USD)': f"${farm.cumulative_crop_revenue_usd:,.2f}",
            'Self-Sufficiency (%)': f"{self_suff:.1f}%"
        })

    return pd.DataFrame(summary_data)


def create_monthly_metrics_table(all_metrics):
    """Create monthly metrics dataframe."""
    return pd.DataFrame([{
        'Year': m.year,
        'Month': m.month,
        'Farm': m.farm_name,
        'Water (m³)': m.total_water_m3,
        'Groundwater (m³)': m.groundwater_m3,
        'Municipal (m³)': m.municipal_m3,
        'Cost (USD)': m.total_water_cost_usd,
        'Yield (kg)': m.total_yield_kg,
        'Revenue (USD)': m.total_crop_revenue_usd,
        'Self-Suff (%)': m.self_sufficiency_pct
    } for m in all_metrics['monthly_metrics']])


def create_yearly_metrics_table(all_metrics):
    """Create yearly metrics dataframe."""
    return pd.DataFrame([{
        'Year': m.year,
        'Farm': m.farm_name,
        'Policy': m.water_policy,
        'Water (m³)': m.total_water_m3,
        'Cost (USD)': m.total_water_cost_usd,
        'Yield (kg)': m.total_yield_kg,
        'Revenue (USD)': m.total_crop_revenue_usd,
        'Self-Suff (%)': m.self_sufficiency_pct
    } for m in all_metrics['farm_metrics']])


def plot_monthly_water_use(all_metrics):
    """Plot monthly water use by type."""
    fig, ax = plt.subplots(figsize=(14, 5))
    
    months = [f"{m.year}-{m.month:02d}" for m in all_metrics['monthly_metrics']]
    agri = [m.agricultural_water_m3 for m in all_metrics['monthly_metrics']]
    comm = [m.community_water_m3 for m in all_metrics['monthly_metrics']]
    
    x = range(len(months))
    ax.fill_between(x, 0, agri, label='Agricultural', alpha=0.7, color='#2E86AB')
    ax.fill_between(x, agri, [a+c for a,c in zip(agri, comm)], 
                     label='Community', alpha=0.7, color='#FCA311')
    
    ax.set_xlabel('Month')
    ax.set_ylabel('Water Use (m³)')
    ax.set_title('Monthly Water Use by Type')
    ax.legend()
    
    tick_indices = list(range(0, len(months), max(1, len(months)//12)))
    ax.set_xticks(tick_indices)
    ax.set_xticklabels([months[i] for i in tick_indices], rotation=45, ha='right')
    
    plt.tight_layout()
    plt.show()


def plot_monthly_self_sufficiency(all_metrics):
    """Plot monthly self-sufficiency."""
    fig, ax = plt.subplots(figsize=(14, 5))
    
    months = [f"{m.year}-{m.month:02d}" for m in all_metrics['monthly_metrics']]
    self_suff = [m.self_sufficiency_pct for m in all_metrics['monthly_metrics']]
    
    x = range(len(months))
    ax.plot(x, self_suff, marker='o', linewidth=2, color='#28A745', markersize=4)
    ax.fill_between(x, 0, self_suff, alpha=0.3, color='#28A745')
    
    ax.set_xlabel('Month')
    ax.set_ylabel('Self-Sufficiency (%)')
    ax.set_title('Monthly Groundwater Self-Sufficiency')
    ax.set_ylim(0, 105)
    
    tick_indices = list(range(0, len(months), max(1, len(months)//12)))
    ax.set_xticks(tick_indices)
    ax.set_xticklabels([months[i] for i in tick_indices], rotation=45, ha='right')
    
    plt.tight_layout()
    plt.show()


def plot_monthly_crop_yields(all_metrics):
    """Plot monthly crop yields by type."""
    # Get all unique crops
    all_crops = set()
    for m in all_metrics['monthly_metrics']:
        all_crops.update(m.crop_yields_kg.keys())
    all_crops = sorted(all_crops)
    
    if not all_crops:
        print("No crop yield data available yet.")
        return
    
    fig, ax = plt.subplots(figsize=(14, 5))
    
    months = [f"{m.year}-{m.month:02d}" for m in all_metrics['monthly_metrics']]
    x = range(len(months))
    
    colors = {'tomato': '#E63946', 'potato': '#A8DADC', 'onion': '#9B59B6',
              'kale': '#52B788', 'cucumber': '#06A77D'}
    
    for crop in all_crops:
        yields = [m.crop_yields_kg.get(crop, 0) / 1000 for m in all_metrics['monthly_metrics']]
        ax.plot(x, yields, marker='o', linewidth=2, label=crop.capitalize(),
                color=colors.get(crop, '#888888'), markersize=4)
    
    ax.set_xlabel('Month')
    ax.set_ylabel('Yield (thousand kg)')
    ax.set_title('Monthly Crop Yields by Type')
    ax.legend()
    
    tick_indices = list(range(0, len(months), max(1, len(months)//12)))
    ax.set_xticks(tick_indices)
    ax.set_xticklabels([months[i] for i in tick_indices], rotation=45, ha='right')
    
    plt.tight_layout()
    plt.show()


def plot_monthly_costs(all_metrics):
    """Plot monthly water costs."""
    fig, ax = plt.subplots(figsize=(14, 5))
    
    months = [f"{m.year}-{m.month:02d}" for m in all_metrics['monthly_metrics']]
    costs = [m.total_water_cost_usd for m in all_metrics['monthly_metrics']]
    
    x = range(len(months))
    ax.plot(x, costs, marker='o', linewidth=2, color='#2E86AB', markersize=4)
    ax.fill_between(x, 0, costs, alpha=0.3, color='#2E86AB')
    
    ax.set_xlabel('Month')
    ax.set_ylabel('Cost (USD)')
    ax.set_title('Monthly Water Costs')
    
    tick_indices = list(range(0, len(months), max(1, len(months)//12)))
    ax.set_xticks(tick_indices)
    ax.set_xticklabels([months[i] for i in tick_indices], rotation=45, ha='right')
    
    plt.tight_layout()
    plt.show()


def plot_monthly_revenue(all_metrics):
    """Plot monthly crop revenue."""
    fig, ax = plt.subplots(figsize=(14, 5))
    
    months = [f"{m.year}-{m.month:02d}" for m in all_metrics['monthly_metrics']]
    revenue = [m.total_crop_revenue_usd for m in all_metrics['monthly_metrics']]
    
    x = range(len(months))
    ax.plot(x, revenue, marker='o', linewidth=2, color='#28A745', markersize=4)
    ax.fill_between(x, 0, revenue, alpha=0.3, color='#28A745')
    
    ax.set_xlabel('Month')
    ax.set_ylabel('Revenue (USD)')
    ax.set_title('Monthly Crop Revenue')
    
    tick_indices = list(range(0, len(months), max(1, len(months)//12)))
    ax.set_xticks(tick_indices)
    ax.set_xticklabels([months[i] for i in tick_indices], rotation=45, ha='right')
    
    plt.tight_layout()
    plt.show()


def plot_yearly_comparison(all_metrics):
    """Plot yearly metrics comparison."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    years = [m.year for m in all_metrics['farm_metrics']]
    
    # Water use
    ax = axes[0, 0]
    water = [m.total_water_m3 for m in all_metrics['farm_metrics']]
    ax.bar(years, water, color='#2E86AB', alpha=0.7)
    ax.set_ylabel('Water Use (m³)')
    ax.set_title('Yearly Water Use')
    
    # Self-sufficiency
    ax = axes[0, 1]
    self_suff = [m.self_sufficiency_pct for m in all_metrics['farm_metrics']]
    ax.plot(years, self_suff, marker='o', linewidth=2, color='#28A745')
    ax.set_ylabel('Self-Sufficiency (%)')
    ax.set_title('Yearly Self-Sufficiency')
    ax.set_ylim(0, 105)
    
    # Costs
    ax = axes[1, 0]
    costs = [m.total_water_cost_usd for m in all_metrics['farm_metrics']]
    ax.bar(years, costs, color='#E63946', alpha=0.7)
    ax.set_xlabel('Year')
    ax.set_ylabel('Cost (USD)')
    ax.set_title('Yearly Water Costs')
    
    # Revenue
    ax = axes[1, 1]
    revenue = [m.total_crop_revenue_usd for m in all_metrics['farm_metrics']]
    ax.bar(years, revenue, color='#28A745', alpha=0.7)
    ax.set_xlabel('Year')
    ax.set_ylabel('Revenue (USD)')
    ax.set_title('Yearly Crop Revenue')
    
    plt.tight_layout()
    plt.show()


# --- Phase 1 additions ---

CROP_COLORS = {
    'tomato': '#E63946',
    'potato': '#A8DADC',
    'onion': '#9B59B6',
    'kale': '#52B788',
    'cucumber': '#06A77D',
}


def plot_crop_price_history(data_loader, start_year=2015, end_year=2024):
    """Plot farmgate price history for all crops.

    Args:
        data_loader: SimulationDataLoader with loaded crop prices
        start_year: First year to plot (default 2015)
        end_year: Last year to plot (default 2024)

    Returns:
        matplotlib Figure
    """
    crops = ['tomato', 'potato', 'onion', 'kale', 'cucumber']
    years = list(range(start_year, end_year + 1))
    dates = [datetime.date(y, 1, 1) for y in years]

    fig, ax = plt.subplots(figsize=(14, 6))

    for crop in crops:
        prices = []
        for d in dates:
            price = data_loader.get_crop_price_usd_kg(crop, d, "farmgate")
            prices.append(price)
        ax.plot(years, prices, marker='o', linewidth=2, markersize=5,
                label=crop.capitalize(), color=CROP_COLORS.get(crop, '#888888'))

    ax.set_xlabel('Year')
    ax.set_ylabel('Farmgate Price (USD/kg)')
    ax.set_title('Crop Price History (Farmgate)')
    ax.legend()

    plt.tight_layout()
    return fig


def plot_monthly_revenue_by_crop(all_metrics):
    """Plot stacked area chart of monthly revenue per crop.

    Args:
        all_metrics: Output from compute_all_metrics()

    Returns:
        matplotlib Figure
    """
    monthly_metrics = all_metrics['monthly_metrics']

    # Collect all unique crops
    all_crops = set()
    for m in monthly_metrics:
        all_crops.update(m.crop_revenues_usd.keys())
    all_crops = sorted(all_crops)

    if not all_crops:
        fig, ax = plt.subplots(figsize=(14, 6))
        ax.set_title('Monthly Revenue by Crop (no data)')
        plt.tight_layout()
        return fig

    # Build data arrays
    months = [f"{m.year}-{m.month:02d}" for m in monthly_metrics]
    x = list(range(len(months)))

    crop_data = []
    crop_labels = []
    crop_colors = []
    for crop in all_crops:
        revenues = [m.crop_revenues_usd.get(crop, 0.0) for m in monthly_metrics]
        crop_data.append(revenues)
        crop_labels.append(crop.capitalize())
        crop_colors.append(CROP_COLORS.get(crop, '#888888'))

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.stackplot(x, *crop_data, labels=crop_labels, colors=crop_colors, alpha=0.8)

    ax.set_xlabel('Month')
    ax.set_ylabel('Revenue (USD)')
    ax.set_title('Monthly Revenue by Crop')
    ax.legend(loc='upper left')

    # X-axis tick spacing consistent with other monthly plots
    tick_indices = list(range(0, len(months), max(1, len(months) // 12)))
    ax.set_xticks(tick_indices)
    ax.set_xticklabels([months[i] for i in tick_indices], rotation=45, ha='right')

    plt.tight_layout()
    return fig


def create_revenue_diversification_table(all_metrics, data_loader, scenario):
    """Create a revenue diversification summary table.

    Returns a DataFrame with one row per crop showing area allocation,
    total yield, total revenue, revenue share, and price variability.

    Args:
        all_metrics: Output from compute_all_metrics()
        data_loader: SimulationDataLoader with loaded crop prices
        scenario: Loaded Scenario object

    Returns:
        pandas DataFrame
    """
    # Get area fractions from first farm (single-farm scenario)
    farm = scenario.farms[0]
    area_fractions = {crop.name: crop.area_fraction for crop in farm.crops}

    # Aggregate per-crop yield and revenue from monthly metrics
    crop_yield_totals = {}
    crop_revenue_totals = {}
    for m in all_metrics['monthly_metrics']:
        for crop, kg in m.crop_yields_kg.items():
            crop_yield_totals[crop] = crop_yield_totals.get(crop, 0.0) + kg
        for crop, usd in m.crop_revenues_usd.items():
            crop_revenue_totals[crop] = crop_revenue_totals.get(crop, 0.0) + usd

    grand_total_revenue = sum(crop_revenue_totals.values())

    # All crops from area fractions (ensures we show all configured crops)
    all_crops = sorted(area_fractions.keys())

    # Compute Price CV for each crop using farmgate prices across available years
    years = list(range(2015, 2025))
    dates = [datetime.date(y, 1, 1) for y in years]

    rows = []
    for crop in all_crops:
        area_frac = area_fractions.get(crop, 0.0)
        total_yield = crop_yield_totals.get(crop, 0.0)
        total_revenue = crop_revenue_totals.get(crop, 0.0)

        if grand_total_revenue > 0:
            revenue_share = (total_revenue / grand_total_revenue) * 100
        else:
            revenue_share = 0.0

        # Compute price CV (coefficient of variation = std/mean)
        prices = []
        for d in dates:
            try:
                p = data_loader.get_crop_price_usd_kg(crop, d, "farmgate")
                prices.append(p)
            except (KeyError, Exception):
                pass

        if len(prices) > 1:
            price_mean = np.mean(prices)
            price_std = np.std(prices)
            price_cv = (price_std / price_mean) if price_mean > 0 else 0.0
        else:
            price_cv = 0.0

        rows.append({
            'Crop': crop.capitalize(),
            'Area Fraction': f"{area_frac:.2f}",
            'Annual Yield (kg)': f"{total_yield:,.0f}",
            'Fresh Revenue (USD)': f"${total_revenue:,.0f}",
            'Revenue Share (%)': f"{revenue_share:.1f}",
            'Price CV': f"{price_cv:.3f}",
        })

    return pd.DataFrame(rows)


def plot_effective_vs_market_cost(blended_costs, market_prices, years, farm_id=None):
    """Plot effective (self-owned blended) vs. market (government municipal) water cost.

    2-panel figure: Panel 1 shows water cost comparison with savings fill,
    Panel 2 is a placeholder for energy (not yet implemented).

    Args:
        blended_costs: {year: {farm_id: cost_per_m3}} from compute_blended_water_cost_per_m3
        market_prices: {year: price_per_m3} from compute_market_water_price_per_m3
        years: List of years to plot
        farm_id: Farm to plot (default: first farm in first year)

    Returns:
        matplotlib Figure
    """
    # Resolve farm_id if not specified
    if farm_id is None:
        first_year = years[0]
        farm_id = list(blended_costs[first_year].keys())[0]

    blended_values = [blended_costs[y].get(farm_id, 0.0) for y in years]
    market_values = [market_prices[y] for y in years]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # --- Panel 1: Water ---
    ax1.plot(years, blended_values, marker='o', linewidth=2, color='#2E86AB',
             label='Self-Owned (Blended)')
    ax1.plot(years, market_values, marker='s', linewidth=2, color='#E15D44',
             label='Government (Municipal)')

    # Fill between to highlight savings
    blended_arr = np.array(blended_values)
    market_arr = np.array(market_values)
    ax1.fill_between(years, blended_arr, market_arr,
                     where=(blended_arr < market_arr),
                     interpolate=True, alpha=0.2, color='#28A745',
                     label='Savings')

    ax1.set_xlabel('Year')
    ax1.set_ylabel('Cost (USD/m³)')
    ax1.set_title('Water: Self-Owned vs. Government')
    ax1.legend()

    # --- Panel 2: Energy (placeholder) ---
    ax2.set_facecolor('#f0f0f0')
    ax2.text(0.5, 0.5,
             'Energy policy not yet implemented\n(Coming in Phase 4+)',
             transform=ax2.transAxes, ha='center', va='center',
             fontsize=14, color='gray')
    ax2.set_title('Energy: Self-Owned vs. Government')
    ax2.set_xticks([])
    ax2.set_yticks([])

    plt.tight_layout()
    return fig


def create_cost_comparison_table(yearly_metrics, counterfactual, blended_costs,
                                 market_prices, years, farm_id=None):
    """Create a yearly cost comparison table: self-owned vs. government water.

    Args:
        yearly_metrics: List of YearlyFarmMetrics from simulation_state.yearly_metrics
        counterfactual: Output from compute_counterfactual_water_cost()
        blended_costs: Output from compute_blended_water_cost_per_m3()
        market_prices: Output from compute_market_water_price_per_m3()
        years: List of years
        farm_id: Farm to report (default: first farm)

    Returns:
        pandas DataFrame with columns: Year, Self-Owned Water (USD),
        Government Water (USD), Water Savings (%), Self-Owned Energy,
        Government Energy, Energy Savings
    """
    if farm_id is None:
        farm_id = yearly_metrics[0].farm_id

    rows = []
    for year in years:
        # Self-owned cost from yearly_metrics
        year_farm_metrics = [
            m for m in yearly_metrics
            if m.year == year and m.farm_id == farm_id
        ]
        if year_farm_metrics:
            self_owned_water = year_farm_metrics[0].total_water_cost_usd
        else:
            self_owned_water = 0.0

        # Government cost from counterfactual
        govt_water = counterfactual["yearly_costs"].get(year, {}).get(farm_id, 0.0)

        # Savings percentage
        if govt_water > 0:
            savings_pct = (govt_water - self_owned_water) / govt_water * 100
        else:
            savings_pct = 0.0

        rows.append({
            'Year': year,
            'Self-Owned Water (USD)': f"${self_owned_water:,.2f}",
            'Government Water (USD)': f"${govt_water:,.2f}",
            'Water Savings (%)': f"{savings_pct:.1f}%",
            'Self-Owned Energy': 'N/A',
            'Government Energy': 'N/A',
            'Energy Savings': 'N/A',
        })

    return pd.DataFrame(rows)


def plot_input_price_index(data_loader, base_year=2015, end_year=2024):
    """Plot input prices normalized to base year = 100.

    Shows 4 series: Municipal Water, Grid Electricity, Diesel, Fertilizer.
    All normalized so base_year value = 100. Divergence from 100 shows
    relative price change.

    Args:
        data_loader: SimulationDataLoader with loaded price data
        base_year: Year to use as index base (value = 100)
        end_year: Last year to plot

    Returns:
        matplotlib Figure
    """
    years = list(range(base_year, end_year + 1))

    # Collect raw prices for each series
    water_prices = []
    electricity_prices = []
    diesel_prices = []
    fertilizer_costs = []

    for year in years:
        water_prices.append(
            data_loader.get_municipal_price_usd_m3(year, tier=3, pricing_regime="subsidized")
        )
        electricity_prices.append(
            data_loader.get_electricity_price_usd_kwh(datetime.date(year, 7, 1))
        )
        diesel_prices.append(
            data_loader.get_diesel_price_usd_liter(datetime.date(year, 7, 1))
        )
        fertilizer_costs.append(
            data_loader.get_fertilizer_cost_usd_ha(datetime.date(year, 7, 1))
        )

    # Normalize each series: index = value / base_value * 100
    def normalize(values):
        base = values[0]
        if base == 0:
            return [0.0] * len(values)
        return [v / base * 100 for v in values]

    water_index = normalize(water_prices)
    electricity_index = normalize(electricity_prices)
    diesel_index = normalize(diesel_prices)
    fertilizer_index = normalize(fertilizer_costs)

    # Plot
    fig, ax = plt.subplots(figsize=(14, 6))

    ax.plot(years, water_index, marker='o', linewidth=2, markersize=5,
            label='Municipal Water', color='#2E86AB')
    ax.plot(years, electricity_index, marker='s', linewidth=2, markersize=5,
            label='Grid Electricity', color='#FCA311')
    ax.plot(years, diesel_index, marker='^', linewidth=2, markersize=5,
            label='Diesel', color='#A23B72')
    ax.plot(years, fertilizer_index, marker='D', linewidth=2, markersize=5,
            label='Fertilizer', color='#28A745')

    # Reference line at base = 100
    ax.axhline(y=100, color='gray', linestyle='--', linewidth=1, alpha=0.7)

    ax.set_xlabel('Year')
    ax.set_ylabel(f'Price Index (base year {base_year} = 100)')
    ax.set_title('Input Price Index')
    ax.legend()

    plt.tight_layout()
    return fig


def plot_net_farm_income(all_metrics):
    """Plot revenue vs. operating costs with net income shading.

    Shows:
    - Green line: monthly crop revenue
    - Red line: monthly total operating costs
    - Green shading where revenue > cost (profit months)
    - Red shading where cost > revenue (loss months)
    - Horizontal dashed black line at y=0 for break-even reference

    Args:
        all_metrics: Output from compute_all_metrics()

    Returns:
        matplotlib Figure
    """
    monthly_metrics = all_metrics['monthly_metrics']

    months = [f"{m.year}-{m.month:02d}" for m in monthly_metrics]
    x = np.arange(len(months))

    revenue = np.array([m.total_crop_revenue_usd for m in monthly_metrics])
    costs = np.array([m.total_operating_cost_usd for m in monthly_metrics])

    fig, ax = plt.subplots(figsize=(14, 6))

    ax.plot(x, revenue, marker='o', markersize=4, linewidth=2,
            color='#28A745', label='Crop Revenue')
    ax.plot(x, costs, marker='s', markersize=4, linewidth=2,
            color='#E15D44', label='Operating Costs')

    # Green fill where revenue >= cost (profit months)
    ax.fill_between(x, revenue, costs,
                    where=(revenue >= costs),
                    interpolate=True, alpha=0.3, color='#28A745',
                    label='Profit')
    # Red fill where cost > revenue (loss months)
    ax.fill_between(x, revenue, costs,
                    where=(costs > revenue),
                    interpolate=True, alpha=0.3, color='#E15D44',
                    label='Loss')

    # Break-even reference line
    ax.axhline(y=0, color='black', linestyle='--', linewidth=0.5)

    ax.set_xlabel('Month')
    ax.set_ylabel('Amount (USD)')
    ax.set_title('Net Farm Income: Revenue vs. Operating Costs')
    ax.legend()

    # X-axis tick spacing consistent with other monthly plots
    tick_indices = list(range(0, len(months), max(1, len(months) // 12)))
    ax.set_xticks(tick_indices)
    ax.set_xticklabels([months[i] for i in tick_indices], rotation=45, ha='right')

    plt.tight_layout()
    return fig


def plot_tornado_sensitivity(sensitivity_results):
    """Plot tornado chart showing sensitivity of net income to input price changes.

    Horizontal bars for each parameter, sorted by total swing (widest at top).
    Bars extend left/right from baseline (0 = no change from base income).
    Positive deltas colored green, negative deltas colored red.

    Args:
        sensitivity_results: Output from run_sensitivity_analysis()

    Returns:
        matplotlib Figure
    """
    params = sensitivity_results["parameters"]
    base_income = sensitivity_results["base_income"]

    # Sort by total_swing descending (widest bars at top of chart)
    sorted_params = sorted(params.items(), key=lambda kv: kv[1]["total_swing"], reverse=True)

    labels = [v["label"] for _, v in sorted_params]
    low_deltas = [v["low_delta"] for _, v in sorted_params]
    high_deltas = [v["high_delta"] for _, v in sorted_params]

    y_pos = np.arange(len(labels))

    # Color: positive deltas green, negative deltas red
    low_colors = ["#28A745" if d >= 0 else "#E15D44" for d in low_deltas]
    high_colors = ["#28A745" if d >= 0 else "#E15D44" for d in high_deltas]

    fig, ax = plt.subplots(figsize=(14, 8))

    # Draw bars from 0 to each delta
    ax.barh(y_pos, low_deltas, align='center', height=0.4, color=low_colors, alpha=0.85,
            label='Price −20%')
    ax.barh(y_pos, high_deltas, align='center', height=0.4, color=high_colors, alpha=0.85,
            label='Price +20%')

    # Vertical line at x=0
    ax.axvline(x=0, color='black', linewidth=0.8)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()  # Widest bar at top
    ax.set_xlabel('Change in Net Income (USD)')
    ax.set_title('Profit Sensitivity to ±20% Price Changes')

    # Annotation with base income
    ax.annotate(f'Base Net Income: ${base_income:,.0f}',
                xy=(0.98, 0.02), xycoords='axes fraction',
                ha='right', va='bottom', fontsize=10,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='wheat', alpha=0.7))

    # Custom legend: green = income increases, red = income decreases
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#28A745', alpha=0.85, label='Income Increases'),
        Patch(facecolor='#E15D44', alpha=0.85, label='Income Decreases'),
    ]
    ax.legend(handles=legend_elements, loc='lower right')

    plt.tight_layout()
    return fig


def plot_monthly_cost_breakdown(all_metrics):
    """Plot stacked area chart of monthly operating costs by category.

    Five layers: Water, Energy, Diesel, Fertilizer, Labor.
    Water cost = total_water_cost_usd - energy_cost_usd (avoids double
    counting with the energy layer).

    Args:
        all_metrics: Output from compute_all_metrics()

    Returns:
        matplotlib Figure
    """
    monthly_metrics = all_metrics['monthly_metrics']

    months = [f"{m.year}-{m.month:02d}" for m in monthly_metrics]
    x = list(range(len(months)))

    # Build data arrays for each cost category
    water_costs = [
        m.total_water_cost_usd - m.energy_cost_usd for m in monthly_metrics
    ]
    energy_costs = [m.energy_cost_usd for m in monthly_metrics]
    diesel_costs = [m.diesel_cost_usd for m in monthly_metrics]
    fertilizer_costs = [m.fertilizer_cost_usd for m in monthly_metrics]
    labor_costs = [m.labor_cost_usd for m in monthly_metrics]

    fig, ax = plt.subplots(figsize=(14, 6))

    ax.stackplot(
        x,
        water_costs,
        energy_costs,
        diesel_costs,
        fertilizer_costs,
        labor_costs,
        labels=['Water', 'Energy', 'Diesel', 'Fertilizer', 'Labor'],
        colors=['#2E86AB', '#FCA311', '#999999', '#28A745', '#E67E22'],
        alpha=0.85,
    )

    ax.set_xlabel('Month')
    ax.set_ylabel('Operating Cost (USD)')
    ax.set_title('Monthly Input Cost Breakdown')
    ax.legend(loc='upper left')

    # X-axis tick spacing consistent with other monthly plots
    tick_indices = list(range(0, len(months), max(1, len(months) // 12)))
    ax.set_xticks(tick_indices)
    ax.set_xticklabels([months[i] for i in tick_indices], rotation=45, ha='right')

    plt.tight_layout()
    return fig
