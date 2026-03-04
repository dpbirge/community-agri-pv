# Compare minimize_draw vs minimize_treatment with tight municipal cap
"""
Differentiates minimize_draw from minimize_treatment by using:
  1. Low-TDS wells (300/450 ppm) so untreated GW meets crop TDS requirements
  2. A tight municipal cap (150 m3/month) with look-ahead enforcement

When blended GW TDS < crop TDS, the strategy ordering matters:
  - minimize_treatment: untreated GW first, then municipal, then treated GW
  - minimize_draw: municipal first, then GW (treated or untreated)

With high-TDS wells (e.g. balanced system with 1400/3500/6500 ppm), both
strategies converge because TDS correction forces the same municipal usage
regardless of strategy ordering.
"""
import sys
from pathlib import Path

repo_root = Path('/Users/dpbirge/GITHUB/community-agri-pv')
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / 'stress_testing'))

from run_test import run
import pandas as pd

st = repo_root / 'stress_testing' / 'baseline'

common_kwargs = dict(
    farm_profiles_path=st / 'farm_profile.yaml',
    water_systems_path=st / 'water_systems_low_tds.yaml',
    community_config_path=st / 'community_demands.yaml',
    energy_config_path=repo_root / 'settings' / 'energy_system_base.yaml',
    energy_policy_path=repo_root / 'settings' / 'energy_policy_base.yaml',
    registry_path=repo_root / 'settings' / 'data_registry_base.yaml',
)


def summarize(df, label, cap_m3=150):
    """Print key annual metrics from a water balance DataFrame."""
    print(f"\n--- {label} ---")
    cols = df.columns.tolist()

    for col, desc in [
        ('municipal_to_tank_m3', 'Municipal to tank (annual)'),
        ('total_groundwater_extracted_m3', 'Groundwater extracted (annual)'),
        ('gw_untreated_to_tank_m3', 'GW untreated to tank (annual)'),
        ('gw_treated_to_tank_m3', 'GW treated to tank (annual)'),
        ('treatment_feed_m3', 'Treatment feed (annual)'),
        ('pumping_energy_kwh', 'Pumping energy (annual)'),
    ]:
        if col in cols:
            print(f"  {desc + ':':45s} {df[col].sum():>12,.1f} m3")

    for col, desc in [
        ('municipal_irrigation_cost', 'Municipal irrigation cost'),
        ('groundwater_cost', 'Groundwater cost'),
        ('total_water_cost', 'Total water cost'),
    ]:
        if col in cols:
            print(f"  {desc + ':':45s} ${df[col].sum():>11,.2f}")

    if 'deficit_m3' in cols:
        total_def = df['deficit_m3'].sum()
        days_def = (df['deficit_m3'] > 0.01).sum()
        print(f"  {'Deficit (annual):':45s} {total_def:>12,.1f} m3 ({days_def} days)")

    if 'delivered_tds_ppm' in cols:
        print(f"  {'Mean delivered TDS:':45s} {df['delivered_tds_ppm'].mean():>12,.1f} ppm")

    if 'muni_cap_used_month_m3' in cols:
        df_temp = df.copy()
        df_temp['month'] = pd.to_datetime(df_temp['day']).dt.month
        monthly = df_temp.groupby('month')['muni_cap_used_month_m3'].last()
        print(f"\n  Monthly municipal cap usage (cap={cap_m3} m3):")
        for month, val in monthly.items():
            pct = val / cap_m3 * 100
            bar = '#' * int(pct / 5) + '.' * (20 - int(pct / 5))
            print(f"    Month {month:2d}: {val:>6.1f} / {cap_m3} m3  [{bar}] {pct:.0f}%")


# --- Run both strategies ---
print("=" * 70)
print("Running minimize_draw with tight municipal cap (150 m3/month)")
print("=" * 70)
draw_water, draw_energy = run(
    water_policy_path=st / 'water_policy_draw_tight_cap.yaml',
    output_dir=repo_root / 'stress_testing' / 'results' / 'W_draw_low_tds',
    **common_kwargs,
)

print("\n" + "=" * 70)
print("Running minimize_treatment with tight municipal cap (150 m3/month)")
print("=" * 70)
treat_water, treat_energy = run(
    water_policy_path=st / 'water_policy_treatment_tight_cap.yaml',
    output_dir=repo_root / 'stress_testing' / 'results' / 'W_treat_low_tds',
    **common_kwargs,
)

# --- Summaries ---
print("\n" + "=" * 70)
print("COMPARISON: minimize_draw vs minimize_treatment")
print("Water system: low-TDS wells (300/450 ppm) | Municipal cap: 150 m3/month")
print("=" * 70)

summarize(draw_water, "minimize_draw")
summarize(treat_water, "minimize_treatment")

# --- Metrics table ---
print("\n\n--- SIDE-BY-SIDE METRICS ---")
metrics = [
    ('municipal_to_tank_m3', 'sum', 'Municipal to tank (m3)'),
    ('total_groundwater_extracted_m3', 'sum', 'GW extracted (m3)'),
    ('gw_untreated_to_tank_m3', 'sum', 'GW untreated to tank (m3)'),
    ('treatment_feed_m3', 'sum', 'Treatment feed (m3)'),
    ('deficit_m3', 'sum', 'Deficit (m3)'),
    ('pumping_energy_kwh', 'sum', 'Pumping energy (kWh)'),
    ('total_water_cost', 'sum', 'Total water cost ($)'),
    ('municipal_irrigation_cost', 'sum', 'Municipal irrig. cost ($)'),
    ('groundwater_cost', 'sum', 'GW cost ($)'),
    ('delivered_tds_ppm', 'mean', 'Mean delivered TDS (ppm)'),
]
print(f"{'Metric':<35} {'minimize_draw':>15} {'minimize_treat':>15} {'Delta':>12}")
print("-" * 80)
for col, agg, label in metrics:
    if col in draw_water.columns:
        d = getattr(draw_water[col], agg)()
        t = getattr(treat_water[col], agg)()
        delta = d - t
        print(f"{label:<35} {d:>15,.2f} {t:>15,.2f} {delta:>+12,.2f}")

# --- Daily-level difference count ---
print("\n\n--- DAILY-LEVEL DIFFERENCES ---")
numeric_cols = draw_water.select_dtypes(include='number').columns
n_diff = 0
for c in numeric_cols:
    daily_diff = (draw_water[c] - treat_water[c]).abs()
    max_diff = daily_diff.max()
    if max_diff > 0.001:
        n_days = (daily_diff > 0.001).sum()
        annual_diff = draw_water[c].sum() - treat_water[c].sum()
        print(f"  {c:<40s} max_diff={max_diff:>10.3f}  days={n_days:>5d}  annual={annual_diff:>+14,.3f}")
        n_diff += 1

if n_diff == 0:
    print("  NO DIFFERENCES FOUND")
else:
    print(f"\n  {n_diff} columns with daily-level differences")

# --- Cost premium ---
draw_cost = draw_water['total_water_cost'].sum()
treat_cost = treat_water['total_water_cost'].sum()
print(f"\n\n--- COST ANALYSIS ---")
print(f"  minimize_draw annual cost:      ${draw_cost:>12,.2f}")
print(f"  minimize_treatment annual cost:  ${treat_cost:>12,.2f}")
print(f"  Cost premium for minimize_draw:  ${draw_cost - treat_cost:>+12,.2f} ({(draw_cost/treat_cost - 1)*100:+.1f}%)")

# --- First active days detail ---
print("\n\n--- FIRST 5 ACTIVE DAYS (January 2010) ---")
cols_show = ['day', 'irrigation_demand_m3', 'municipal_to_tank_m3',
             'gw_untreated_to_tank_m3', 'total_water_cost']
draw_jan = draw_water[pd.to_datetime(draw_water['day']).dt.month == 1]
draw_active = draw_jan[draw_jan['irrigation_demand_m3'] > 0].head(5)
treat_jan = treat_water[pd.to_datetime(treat_water['day']).dt.month == 1]
treat_active = treat_jan[treat_jan['irrigation_demand_m3'] > 0].head(5)
print("\nminimize_draw:")
print(draw_active[cols_show].to_string(index=False))
print("\nminimize_treatment:")
print(treat_active[cols_show].to_string(index=False))
