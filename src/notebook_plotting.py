"""
Plotting and table functions for interactive notebook analysis.
"""

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
