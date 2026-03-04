"""Unified daily water balance for community irrigation and buildings.

Composes irrigation demand, water supply dispatch, and community demand
into a single daily DataFrame showing all demands, all sources, energy
breakdown, cost breakdown, and tank state.

Community building water is always supplied from municipal water (separate
from the irrigation municipal cap). Irrigation application energy is
computed per field based on irrigation system type.

Usage:
    from src.water_balance import compute_daily_water_balance, save_daily_water_balance

    df = compute_daily_water_balance(
        farm_profiles_path='settings/farm_profile_base.yaml',
        water_systems_path='settings/water_systems_base.yaml',
        water_policy_path='settings/water_policy_base.yaml',
        community_config_path='settings/community_demands_base.yaml',
        registry_path='settings/data_registry_base.yaml',
    )
    save_daily_water_balance(df, output_dir='simulation/')
"""

from pathlib import Path

import pandas as pd
import yaml

from src.community_demand import compute_daily_demands
from src.irrigation_demand import compute_irrigation_demand, get_field_irrigation_specs
from src.water import compute_water_supply


def _load_yaml(path):
    """Load and parse a YAML file."""
    with open(path) as f:
        return yaml.safe_load(f)


def _order_balance_columns(result):
    """Reorder columns in the water balance DataFrame for output.

    Groups columns into semantic sections: metadata, demand, source,
    delivery, quality, energy, cost, tank state, diagnostics, policy,
    caps, treatment, wells, and extras. Columns not explicitly listed
    are appended at the end.

    Args:
        result: DataFrame with all water balance columns computed.

    Returns:
        DataFrame with columns reordered.
    """
    meta_cols = ['day']

    demand_section = ['irrigation_demand_m3', 'community_water_demand_m3', 'total_water_demand_m3']
    demand_section += sorted([c for c in result.columns if c.endswith('_demand_m3')
                              and c not in demand_section])
    demand_section += sorted([c for c in result.columns if c.endswith('_etc_m3')])
    # Per-building community water breakdown
    demand_section += sorted([c for c in result.columns if c.startswith('community_')
                              and c.endswith('_water_m3') and c != 'community_water_demand_m3'])

    source_cols = [
        'gw_untreated_to_tank_m3', 'gw_treated_to_tank_m3',
        'municipal_to_tank_m3', 'total_sourced_to_tank_m3',
        'municipal_community_m3',
    ]

    delivery_cols = ['irrigation_delivered_m3', 'tank_flush_delivered_m3',
                     'safety_flush_m3', 'look_ahead_drain_m3', 'deficit_m3']
    delivery_cols += sorted([c for c in result.columns if c.endswith('_delivered_m3')
                             and c not in delivery_cols])

    quality_cols = ['delivered_tds_ppm', 'sourced_tds_ppm',
                    'crop_tds_requirement_ppm', 'tds_exceedance_ppm']

    energy_cols = ['pumping_energy_kwh', 'treatment_energy_kwh', 'application_energy_kwh']
    energy_cols += sorted([c for c in result.columns if c.endswith('_application_energy_kwh')])
    energy_cols += sorted([c for c in result.columns if c.endswith('_pumping_kwh')])
    energy_cols += ['total_water_energy_kwh']

    cost_cols = ['municipal_irrigation_cost', 'municipal_community_cost',
                 'groundwater_cost', 'total_water_cost']

    tank_cols = ['tank_volume_m3', 'tank_tds_ppm', 'prefill_m3']

    balance_cols = ['over_delivery_m3', 'balance_check']

    policy_cols = ['policy_strategy', 'policy_primary_source', 'policy_flush_reason', 'policy_deficit']

    # Monthly cap tracking
    cap_cols = ['gw_cap_used_month_m3', 'muni_cap_used_month_m3',
                'gw_monthly_cap_m3', 'muni_monthly_cap_m3']

    # Treatment throughput utilization
    treatment_cols = ['treatment_feed_m3', 'treatment_max_feed_m3', 'treatment_reject_m3']

    # Well columns from supply
    well_cols = [c for c in result.columns if c.endswith('_extraction_m3') or
                 (c.endswith('_tds_ppm') and c not in quality_cols + tank_cols)]

    extra_cols = ['total_groundwater_extracted_m3']

    ordered = meta_cols + demand_section + source_cols + delivery_cols + quality_cols
    ordered += energy_cols + cost_cols + tank_cols + balance_cols + policy_cols
    ordered += cap_cols + treatment_cols + well_cols + extra_cols

    # Only include columns that exist
    ordered = [c for c in ordered if c in result.columns]
    # Add any remaining columns not yet included
    remaining = [c for c in result.columns if c not in ordered]
    ordered += remaining

    return result[ordered]


def _compute_delivery_and_energy(result, field_specs):
    """Compute per-field delivery volumes, application energy, and cost rollups.

    Modifies result DataFrame in place.

    Args:
        result: Merged water balance DataFrame.
        field_specs: Dict of field irrigation specs from get_field_irrigation_specs.
    """
    for field_name in field_specs:
        demand_col = f'{field_name}_demand_m3'
        delivered_col = f'{field_name}_delivered_m3'
        energy_col = f'{field_name}_application_energy_kwh'
        if demand_col in result.columns:
            irrig_demand = result['irrigation_demand_m3']
            delivery_ratio = result['irrigation_delivered_m3'].where(
                irrig_demand > 0, 0.0) / irrig_demand.where(irrig_demand > 0, 1.0)
            result[delivered_col] = (result[demand_col] * delivery_ratio).round(3)
            rate = field_specs[field_name]['application_energy_kwh_per_m3']
            result[energy_col] = (result[delivered_col] * rate).round(3)

    app_energy_cols = [c for c in result.columns if c.endswith('_application_energy_kwh')]
    result['application_energy_kwh'] = result[app_energy_cols].sum(axis=1).round(3) if app_energy_cols else 0.0

    for col in ['pumping_energy_kwh', 'treatment_energy_kwh', 'application_energy_kwh']:
        result[col] = result[col].round(3)
    result['total_water_energy_kwh'] = (
        result['pumping_energy_kwh'] +
        result['treatment_energy_kwh'] +
        result['application_energy_kwh']
    ).round(3)

    for col in ['municipal_irrigation_cost', 'municipal_community_cost', 'groundwater_cost']:
        result[col] = result[col].round(3)
    result['total_water_cost'] = (
        result['municipal_irrigation_cost'] +
        result['municipal_community_cost'] +
        result['groundwater_cost']
    ).round(3)


def _compute_balance_diagnostics(result):
    """Compute over-delivery and physical tank conservation check.

    Modifies result DataFrame in place.

    Args:
        result: Merged water balance DataFrame with delivery and demand columns.
    """
    result['over_delivery_m3'] = (
        result['irrigation_delivered_m3'] -
        result['irrigation_demand_m3'] +
        result['deficit_m3']
    ).clip(lower=0.0).round(3)

    result['balance_check'] = (
        result['tank_volume_m3'].shift(1)
        + result['total_sourced_to_tank_m3']
        - result['irrigation_delivered_m3']
        - result['tank_volume_m3']
    ).round(6)


def compute_daily_water_balance(farm_profiles_path, water_systems_path,
                                water_policy_path, community_config_path,
                                registry_path, *,
                                water_system_name='main_irrigation',
                                root_dir=None):
    """Compute unified daily water balance for the community.

    Orchestrates irrigation demand, water supply dispatch, and community
    demand into a single daily output covering all demands, sources,
    energy, cost, and tank state.

    Args:
        farm_profiles_path: Path to farm_profiles.yaml.
        water_systems_path: Path to water_systems.yaml.
        water_policy_path: Path to water_policy.yaml.
        community_config_path: Path to community_demands.yaml.
        registry_path: Path to data_registry.yaml.
        water_system_name: Name of the water system to simulate.
        root_dir: Repository root. Defaults to parent of settings/.

    Returns:
        DataFrame with unified daily water balance columns.
    """
    if root_dir is None:
        root_dir = Path(registry_path).parent.parent

    # 1. Irrigation demand
    irrig_df = compute_irrigation_demand(
        farm_profiles_path=farm_profiles_path,
        registry_path=registry_path,
        water_system_name=water_system_name,
        water_policy_path=water_policy_path,
        root_dir=root_dir,
    )

    # 2. Water supply dispatch (central mixing tank)
    supply_df = compute_water_supply(
        water_systems_path=water_systems_path,
        registry_path=registry_path,
        irrigation_demand_df=irrig_df,
        water_policy_path=water_policy_path,
        water_system_name=water_system_name,
        root_dir=root_dir,
    )

    # 3. Community demand
    community_df = compute_daily_demands(
        config_path=community_config_path,
        registry_path=registry_path,
        root_dir=root_dir,
    )

    # 4. Per-field irrigation specs for application energy
    field_specs = get_field_irrigation_specs(
        farm_profiles_path=farm_profiles_path,
        registry_path=registry_path,
        water_system_name=water_system_name,
        root_dir=root_dir,
    )

    # 5. Get municipal cost per m3 from water systems config
    ws_config = _load_yaml(water_systems_path)
    system = next(s for s in ws_config['systems'] if s['name'] == water_system_name)
    muni_cost_per_m3 = system['municipal_source']['cost_per_m3']

    # --- Build unified output ---

    # Start with supply_df (has day + all water supply columns)
    result = supply_df.copy()
    result = result.drop(columns=['total_sourcing_energy_kwh'], errors='ignore')

    # Merge irrigation demand (total, per-field demand, and per-field ETc reference)
    result = result.rename(columns={'total_delivered_m3': 'irrigation_delivered_m3'})
    irrig_cols_to_merge = ['day', 'total_demand_m3']
    demand_cols = [c for c in irrig_df.columns if c.endswith('_demand_m3') and c != 'total_demand_m3']
    etc_m3_cols = [c for c in irrig_df.columns if c.endswith('_etc_m3')]
    irrig_cols_to_merge += demand_cols + etc_m3_cols
    result = result.merge(
        irrig_df[irrig_cols_to_merge].rename(columns={'total_demand_m3': 'irrigation_demand_m3'}),
        on='day', how='left',
    )

    # Merge community water demand (total + per-building breakdown)
    building_water_cols = [c for c in community_df.columns
                           if c.endswith('_water_m3') and c != 'total_water_m3']
    community_water = community_df[['day', 'total_water_m3'] + building_water_cols].rename(
        columns={'total_water_m3': 'community_water_demand_m3'})
    building_rename = {c: f'community_{c}' for c in building_water_cols}
    community_water = community_water.rename(columns=building_rename)
    result = result.merge(community_water, on='day', how='left')
    result['community_water_demand_m3'] = result['community_water_demand_m3'].fillna(0.0)

    # Community water is always municipal (separate from irrigation cap)
    result['municipal_community_m3'] = result['community_water_demand_m3']
    result['municipal_community_cost'] = result['municipal_community_m3'] * muni_cost_per_m3

    # Total water demand
    result['total_water_demand_m3'] = result['irrigation_demand_m3'] + result['community_water_demand_m3']

    # Rename irrigation municipal cost for clarity
    result = result.rename(columns={'municipal_cost': 'municipal_irrigation_cost'})

    _compute_delivery_and_energy(result, field_specs)
    _compute_balance_diagnostics(result)

    return _order_balance_columns(result)


def save_daily_water_balance(df, output_dir, *, filename='daily_water_balance.csv', decimals=3):
    """Save daily water balance DataFrame to CSV.

    Args:
        df: DataFrame returned by compute_daily_water_balance.
        output_dir: Directory to write the output file. Created if needed.
        filename: Output file name.
        decimals: Decimal places for numeric columns.

    Returns:
        Path to the saved CSV file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    df.round(decimals).to_csv(path, index=False)
    return path


def load_daily_water_balance(path):
    """Load a saved water balance CSV.

    Args:
        path: Path to the water balance CSV file.

    Returns:
        DataFrame with the same structure as compute_daily_water_balance output.
    """
    return pd.read_csv(path, parse_dates=['day'])


# ---------------------------------------------------------------------------
# Entry point for quick verification
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    root = Path(__file__).parent.parent
    df = compute_daily_water_balance(
        farm_profiles_path=root / 'settings' / 'farm_profile_base.yaml',
        water_systems_path=root / 'settings' / 'water_systems_base.yaml',
        water_policy_path=root / 'settings' / 'water_policy_base.yaml',
        community_config_path=root / 'settings' / 'community_demands_base.yaml',
        registry_path=root / 'settings' / 'data_registry_base.yaml',
    )
    out = save_daily_water_balance(df, output_dir=root / 'simulation')
    print(f'Saved {len(df)} rows to {out}')
    print(f'Irrigation demand: {df["irrigation_demand_m3"].sum():.0f} m3')
    print(f'Community water:   {df["community_water_demand_m3"].sum():.0f} m3')
    print(f'Total delivered:   {df["irrigation_delivered_m3"].sum():.0f} m3')
    print(f'Total deficit:     {df["deficit_m3"].sum():.0f} m3')
    print(f'Total energy:      {df["total_water_energy_kwh"].sum():.1f} kWh')
    print(f'Total cost:        {df["total_water_cost"].sum():.2f} USD')
    print(f'Balance check max: {df["balance_check"].dropna().abs().max():.6f}')
    print(df.head(2).to_string())
