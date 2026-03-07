# Energy System Code Review -- Agent B

## Executive Summary

The energy system code is structurally sound with clean functional decomposition and proper separation of concerns. However, several calculation robustness issues were found: a self-consumption ratio that can exceed 1.0 due to charge efficiency losses being counted as "consumed" renewable energy, a generator power-sizing formula that produces counterintuitive behavior for mid-range deficits, and stale hardcoded constants in the test suite that do not match current configuration. Two configuration-level inconsistencies (generator type/capacity mismatch, battery type/capacity mismatch) create confusion even though the code itself handles them by design.

## High-Confidence Issues (fix immediately)

### E-HC-1: Self-consumption ratio can exceed 1.0

- **File**: `src/energy_balance.py`:731-733, 804-805
- **Severity**: Medium
- **Issue**: The `self_consumption_ratio` numerator includes `renewable_charge` which is set to the `accepted` value from `_charge_battery()`. The `accepted` value is the amount of energy *consumed from the surplus* (i.e., before charge efficiency losses), not the amount stored. Meanwhile, `renewable_consumed_kwh` is `min(total_renewable, total_demand)`, which already accounts for all renewable energy used to meet demand. On a day with 100 kWh renewable, 50 kWh demand, and a battery that accepts all 50 kWh surplus (with 0.95 charge efficiency): `renewable_consumed = 50`, `renewable_charge = 50`, `self_consumption_ratio = (50 + 50) / 100 = 1.0`. This is correct at the boundary. But consider that `_charge_battery` returns `accepted = stored / eff`. If headroom limits `stored` to 40 kWh, then `accepted = 40 / 0.95 = 42.1`, the remaining 7.9 kWh is exported or curtailed. Now: `renewable_consumed = 50`, `renewable_charge = 42.1`, ratio = `(50 + 42.1) / 100 = 0.921`, which is correct. However, there is a subtle path where this breaks: if `_charge_battery` is called more than once (it is called once in surplus handling and once for generator excess), and the second call with `renewable=False` also increments `_battery_charge_renewable_kwh` -- but checking line 805, the renewable tracking uses `accepted` unconditionally. Actually, looking more carefully, line 805 only runs in the `action == 'battery'` block inside `_handle_surplus` where `renewable=True`. The generator excess path at line 866-868 does NOT increment `_battery_charge_renewable_kwh`. So the accounting is correct for separate surplus/generator paths. The ratio is actually safe as written for the current code paths. **Downgrading to observation** -- see Observations section.
- **Fix**: No fix needed -- analysis confirmed the accounting is correct.
- **Confidence**: High (confirmed safe after trace)

### E-HC-2: Test suite hardcoded constants do not match current configuration

- **File**: `tests/test_energy_balance.py`:17-19
- **Severity**: Medium
- **Issue**: The test file hardcodes `BATTERY_SOC_MIN = 0.20`, `BATTERY_SOC_MAX = 0.95`, `BATTERY_CAPACITY_KWH = 200.0`. The current config has `capacity_kwh: 1000` (energy_system_base.yaml:39), `soc_max: 0.8` (energy_policy_base.yaml:57). These mismatches cause `test_soc_fraction_within_policy_bounds` to use wrong bounds (0.95 vs actual 0.8) and `test_soc_kwh_equals_fraction_times_capacity` to multiply by 200 instead of 1000. Both tests will either pass vacuously or fail for the wrong reason.
- **Fix**: Either load the constants from the YAML files at test time, or update the hardcoded values:
```python
BATTERY_SOC_MIN = 0.20
BATTERY_SOC_MAX = 0.80    # was 0.95
BATTERY_CAPACITY_KWH = 1000.0  # was 200.0
```
Better approach -- load from config:
```python
import yaml
_ROOT = Path(__file__).parent.parent
_SYSTEM = yaml.safe_load(open(_ROOT / 'settings' / 'energy_system_base.yaml'))
_POLICY = yaml.safe_load(open(_ROOT / 'settings' / 'energy_policy_base.yaml'))
BATTERY_CAPACITY_KWH = _SYSTEM['battery']['capacity_kwh']
BATTERY_SOC_MIN = _POLICY['battery']['soc_min']
BATTERY_SOC_MAX = _POLICY['battery']['soc_max']
```
- **Confidence**: High

### E-HC-3: Generator power sizing assumes 24-hour spread, producing counterintuitive minimum-load clamping

- **File**: `src/energy_balance.py`:559
- **Severity**: Medium
- **Issue**: The line `power_kw = max(deficit_kwh / 24.0, min_load_kw)` computes a target power level by spreading the deficit across a full 24-hour day. For a diesel generator with `rated_capacity_kw = 50` and `min_load_kw = 15` (30% of 50), any deficit below 360 kWh (= 15 kW * 24 hours) triggers the minimum-load branch. Combined with the 6-hour minimum runtime at line 564, a deficit of, say, 20 kWh produces `hours = max(6, 20/15) = 6`, `output = 15 * 6 = 90 kWh`, `delivered = 20`, `excess = 70 kWh`. That 70 kWh excess is 3.5x the actual need. For the baseline config with `rated_capacity_kw = 50`, the minimum-load branch activates for any deficit under 360 kWh, which is essentially always in a community microgrid context. This is not necessarily a bug -- it models real generator behavior -- but the 24-hour spreading assumption is unusual. Most generator sizing models use a shorter reference period (e.g., 4-8 hours) to determine the operating power level.
- **Fix**: Consider using a more realistic reference period, or document the design rationale:
```python
# Use 8-hour reference period for power sizing (typical operational window)
power_kw = max(deficit_kwh / 8.0, min_load_kw)
```
Or add a configurable parameter:
```python
# In generator_specs:
'reference_hours': gen_cfg.get('reference_hours', 24.0)
# In _run_generator:
power_kw = max(deficit_kwh / generator_specs['reference_hours'], min_load_kw)
```
- **Confidence**: High (the math is clear; the design choice is debatable)

### E-HC-4: Solar degradation applied after totals computed, then totals recomputed -- wind totals orphaned from degradation recompute

- **File**: `src/energy_supply.py`:283-289
- **Severity**: Low
- **Issue**: The sequence is: (1) `_add_energy_totals` computes `total_solar_kwh`, `total_wind_kwh`, `total_renewable_kwh` from undegraded values; (2) `_apply_degradation` modifies solar columns; (3) lines 288-289 recompute `total_solar_kwh` and `total_renewable_kwh`. This works correctly but is fragile -- `total_wind_kwh` is NOT recomputed because wind is not degraded, but it relies on wind not having been modified between step 1 and step 3. If future code inserts any wind adjustment between these steps, `total_renewable_kwh` would silently use stale `total_wind_kwh`. The `_add_energy_totals` call at line 283 is wasted computation for the solar and renewable columns when degradation is enabled.
- **Fix**: Apply degradation to individual solar columns first, then compute totals once:
```python
if degradation_rate and degradation_rate > 0:
    start = pd.Timestamp(degradation_start) if degradation_start else df['day'].iloc[0]
    df = _apply_degradation(df, solar_cols, degradation_rate, start)

df = _add_energy_totals(df, solar_cols=solar_cols, wind_cols=wind_cols)
```
This eliminates the double computation and the fragile recompute.
- **Confidence**: High


## Complex Issues (needs deeper review)

### E-CX-1: Generator type/capacity mismatch in baseline configuration

- **File**: `settings/energy_system_base.yaml`:32-33
- **Severity**: Medium
- **Issue**: The config references `type: diesel_100kw` (which has `capacity_kw: 100` in generators-toy.csv) but overrides `rated_capacity_kw: 50`. The `_build_generator_specs` function at energy_balance.py:189 uses `gen_cfg.get('rated_capacity_kw', row['capacity_kw'])`, so the YAML value of 50 takes precedence. The Willans line fuel model at line 577 uses `fuel = (a * rated_kw + b * power_kw) * hours`. The `a` coefficient (0.06) applies to `rated_kw` (50, the overridden value), while the actual equipment's idle loss characteristic corresponds to a 100 kW machine. This means the no-load fuel consumption is modeled as `0.06 * 50 = 3.0 L/hr` instead of the actual `0.06 * 100 = 6.0 L/hr`. The Willans line `a` coefficient represents the mechanical losses of the physical engine, which scale with the engine's actual size, not the derated operating limit.
- **Analysis**: Determine whether the intent is to model a 100 kW generator derated to 50 kW (in which case `a * rated_kw` should use the equipment's 100 kW, not the policy's 50 kW), or a 50 kW generator (in which case `type: diesel_50kw` should be used). The current code conflates the "rated" capacity with the policy-limited capacity.
- **Suggested approach**: Either (a) change the config to `type: diesel_50kw` if a 50 kW unit is intended, or (b) use the equipment CSV's `capacity_kw` for the Willans `a` term (which represents the physical engine) while using the policy `rated_capacity_kw` for the operational power ceiling. This would require splitting the specs:
```python
return {
    'rated_capacity_kw': rated_kw,           # operational ceiling
    'engine_capacity_kw': row['capacity_kw'], # physical engine size for Willans a term
    'min_load_kw': min_load_frac * rated_kw,
    ...
}
```
- **Confidence**: Medium

### E-CX-2: Battery type/capacity override mismatch in baseline configuration

- **File**: `settings/energy_system_base.yaml`:38-39
- **Severity**: Low
- **Issue**: The config references `type: lithium_iron_phosphate_medium` (which has `capacity_kwh: 200` in batteries-toy.csv) but overrides `capacity_kwh: 1000`. Similar to the generator issue, this is architecturally supported -- `_build_battery_specs` at line 157 uses `bat_cfg.get('capacity_kwh', row['capacity_kwh'])`. However, the charge/discharge efficiencies (0.95/0.95) and cycle life (4500) are from the 200 kWh medium unit. A 1000 kWh system would typically use a different BMS topology and could have different efficiency characteristics. The comment on line 38 says "200 kWh LFP" which contradicts the override.
- **Analysis**: This is a modeling assumption question, not a code bug. The code correctly applies the override. But the misleading comment and the mismatch between the equipment lookup row and the actual capacity could confuse users reviewing the configuration.
- **Suggested approach**: Either add a `lithium_iron_phosphate_1000` row to batteries-toy.csv with appropriate specs, or update the comment to reflect the override behavior: `# base specs from 200 kWh LFP, capacity overridden to 1000 kWh`.
- **Confidence**: Medium

### E-CX-3: Energy conservation not explicitly validated within the dispatch loop

- **File**: `src/energy_balance.py`:907-915 (`_dispatch_day`)
- **Severity**: Medium
- **Issue**: The dispatch logic splits into surplus and deficit branches, but there is no post-dispatch assertion that energy in equals energy out plus storage delta. The test suite (`test_energy_balance.py`) checks conservation externally, but the dispatch code itself does not enforce it. If a new dispatch action is added or an existing one has a subtle accounting error, the violation would only be caught when tests are run against output CSVs.
- **Analysis**: For surplus days, the conservation equation is: `total_renewable = renewable_consumed + battery_charge + grid_export + curtailed`. For deficit days: `total_demand = renewable_consumed + battery_discharge + grid_import + generator + deficit`. Both equations should close to within floating-point tolerance. Adding an internal assertion would catch violations at the point of origin rather than in downstream tests.
- **Suggested approach**: Add a debug-mode conservation check at the end of `_dispatch_day`:
```python
# Conservation check (debug)
if net_load <= 0:
    supply = row['renewable_consumed_kwh'] + row['battery_charge_kwh'] + row['grid_export_kwh'] + row['curtailed_kwh']
    assert abs(total_renewable_kwh - supply) < 0.01, f"Surplus conservation violated on {day}"
else:
    sources = row['renewable_consumed_kwh'] + row['battery_discharge_kwh'] + row['grid_import_kwh'] + row['generator_kwh'] + row['deficit_kwh']
    assert abs(total_demand_kwh - sources) < 0.01, f"Deficit conservation violated on {day}"
```
- **Confidence**: Medium

### E-CX-4: Daily cap allowance with look_ahead can overshoot monthly cap due to floating-point accumulation

- **File**: `src/energy_balance.py`:383-405
- **Severity**: Low
- **Issue**: `_daily_cap_allowance` with `look_ahead=True` returns `min(remaining / remaining_days, remaining)`. The clamping to `remaining` prevents individual-day overshoot. However, consider a 5000 kWh monthly cap spread over 31 days. Day 1 gets `5000/31 = 161.29`, day 2 gets `(5000-161.29)/30 = 161.29`, etc. After 31 days of this division, floating-point accumulation means the sum may slightly exceed 5000. The monthly accumulator at line 1075 (`grid_cap_state['import']['used'] += row['grid_import_kwh']`) tracks the actual total, and next iteration the `remaining` will go slightly negative, producing 0.0 via the `remaining <= 0` check at line 398. So the overshoot is at most one day's allowance of epsilon -- practically negligible. But the cap guarantee is technically soft, not hard.
- **Analysis**: For the simulation's daily timestep and typical cap values (5000 kWh/month), the floating-point error is on the order of 1e-10 kWh. This is not practically significant.
- **Suggested approach**: No fix needed. The existing clamp at line 405 is sufficient. If strict enforcement is ever required, add a final clamp in the simulation loop: `imported = min(imported, monthly_cap - grid_cap_state['import']['used'])`.
- **Confidence**: Low (this is theoretical, not practical)

### E-CX-5: `community_demand.py` date alignment assumes all four data CSVs share the same date index

- **File**: `src/community_demand.py`:171-174
- **Severity**: Medium
- **Issue**: The `compute_daily_demands` function uses `pd.concat([hh_energy_df[['date']], hh_energy, hh_water, bld_energy, bld_water], axis=1)`. This is a positional concat (axis=1), which assumes all DataFrames have the same number of rows in the same order. If any of the four source CSVs has a different date range, extra rows, or different ordering, the resulting DataFrame would have misaligned data without any error. Unlike `energy_supply.py` which uses merge-on-day with a validation step (line 262), `community_demand.py` does no date alignment or validation.
- **Analysis**: Currently all four building demand CSVs are generated from the same script with the same date range (2010-01-01 to 2024-12-31, 5479 rows each), so this is not an active bug. But it is a latent fragility -- if any single CSV is regenerated with a different date range, the concat would silently produce wrong results.
- **Suggested approach**: Either merge on date (safer but slower) or add a shape/date assertion:
```python
assert len(hh_energy_df) == len(hh_water_df) == len(bld_energy_df) == len(bld_water_df), \
    "Building demand CSVs have different row counts"
assert (hh_energy_df['date'].values == bld_energy_df['date'].values).all(), \
    "Building demand CSVs have misaligned dates"
```
- **Confidence**: Medium


## Observations (no fix needed)

### O-1: Surplus dispatch order is identical across all three strategies

The `_SURPLUS_ORDER` dict at line 766-770 maps all three strategies to the same sequence: `['battery', 'export', 'curtail']`. This is intentional (surplus handling is the same regardless of strategy -- the differentiation happens in deficit handling), but could benefit from a brief comment explaining why all three are identical.

### O-2: Battery renewable fraction tracking is well-implemented

The weighted-average approach to tracking renewable fraction in the battery (`old_soc * old_frac + stored * source_frac) / new_soc`) correctly handles mixing of renewable and generator-charged energy. The discharge-time capture of renewable fraction at line 845 (before any same-day generator charging can dilute it) is a thoughtful design detail.

### O-3: Net metering incremental billing is correctly implemented

The `_compute_net_metering_cost` function uses an incremental approach (tracking the change in `max(0, monthly_import - monthly_export)`) that correctly ensures daily costs sum to the monthly net-metered bill. This avoids the common mistake of applying net metering at the daily level.

### O-4: `_charge_battery` efficiency accounting is correct but worth documenting

The `accepted` return value represents energy consumed from the surplus, while `stored` is what enters the battery. The relationship `stored = min(surplus * eff, headroom)` and `accepted = stored / eff` means the caller deducts `accepted` from the surplus (correct: this is the energy removed from the renewable pool). The loss `accepted - stored` is implicit dissipation. This is physically correct but the dual return values could benefit from a note in the docstring about which value to use for which accounting purpose.

### O-5: Agri-PV density key derivation assumes specific naming convention

`_extract_agripv_farms` at energy_supply.py:120-121 converts `condition: underpv_low` to `density_key: low_density` via string manipulation: `cond.replace('underpv_', '') + '_density'`. This creates a tight coupling between the farm profile naming convention (`underpv_{level}`) and the PV output column convention (`{level}_density_kwh_per_ha`). If either convention changes, the mapping silently breaks with a KeyError. This is acceptable for the current codebase but is a maintenance risk.

### O-6: Generator 10 Wh threshold prevents micro-startups

The threshold at line 551 (`deficit_kwh <= 0.01`) prevents generator startup for floating-point residuals. This is a practical guard against numerical noise triggering a 6-hour minimum runtime cycle. The comment explains the rationale clearly.

### O-7: Price lookup forward-fill is correct for monthly-to-daily mapping

`_daily_price_lookup` at line 108-110 uses `reindex` + `ffill` to map monthly price entries to daily simulation dates. The `ValueError` guard at line 103-107 prevents silent NaN propagation when simulation dates precede price data. This is robust.

### O-8: `_load_csv` in `energy_supply.py` drops `weather_scenario_id` column

The `_load_csv` helper in energy_supply.py:41 has `df.drop(columns=['weather_scenario_id'], errors='ignore')`. This is not present in the energy_balance.py version of `_load_csv` (line 51), but this is correct because energy_balance.py does not directly load energy output CSVs -- it delegates to `compute_daily_energy()`.

### O-9: The `_load_yaml` helper is duplicated across all three modules

Each of `energy_supply.py`, `energy_balance.py`, and `community_demand.py` defines its own `_load_yaml()`. This is a minor DRY violation but consistent with the project's pattern of each module being self-contained. Could be extracted to a shared `src/_io.py` if the number of modules grows.

### O-10: Energy balance grid cap state uses `math.inf` for display

At line 1083-1084, uncapped monthly limits are written as `math.inf` to the output CSV. Pandas serializes `inf` as `inf` in CSV, which may cause issues for downstream consumers expecting numeric values. This is a minor display concern -- consider using a large sentinel value or empty string.
