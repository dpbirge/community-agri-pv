# Session Prompt: Implement Energy Balance Module

Implement `src/energy_balance.py` — the daily energy balance dispatch module — as
specified in `specs/energy_system_specification.md`. Read that file first. It contains
the full architecture, function signatures, output columns, dispatch logic, and design
decisions.

## Reference Architecture

`src/water.py` and `src/water_balance.py` are the reference implementation. The energy
balance module mirrors their patterns exactly:

- `src/water.py` → `src/energy_balance.py` (dispatch engine with daily loop)
- `src/water_balance.py` → the orchestrator role is handled by
  `compute_daily_energy_balance()` inside the same module (simpler than water
  because there is no separate sizing module)

Read `src/water.py` (especially `_run_simulation`, `_dispatch_day`, and
`compute_water_supply`) and `src/water_balance.py` (especially
`compute_daily_water_balance`) for the patterns to follow. Also read
`src/energy_supply.py` and `src/community_demand.py` — your module calls both.

## Files Touched

| File | Action |
|---|---|
| `src/energy_balance.py` | **Create** — the entire module |

No changes to existing source modules, data files, or config files. Everything
needed is already in place from the preparation phase.

## Implementation Steps

Follow these in order. Each step should produce working code before moving to
the next.

### Step 1: Module skeleton and internal helpers

Create `src/energy_balance.py` with:

- Module docstring following the `src/water.py` pattern
- Imports: `yaml`, `pandas`, `math`, `logging`, `calendar`, `Path` from pathlib
- `logger = logging.getLogger(__name__)`
- Section-commented helper groups following the `src/water.py` layout
- `_load_yaml(path)` and `_load_csv(path)` — identical to other modules
- `_resolve_energy_balance_paths(registry, root_dir)` — resolves paths from
  `energy_equipment`, `electricity_pricing`, and `fuel_pricing` registry sections
  into a flat dict of absolute Paths

### Step 2: Price loading helpers

- `_load_price_series(csv_path, column)` — loads a monthly price CSV with
  `comment='#'`, parses the `date` column, returns a Series indexed by date
  with the specified column's values. Used for agricultural tariff, commercial
  tariff, and diesel prices. The column to use is `usd_per_kwh_avg_daily` for
  electricity and `usd_per_liter` for diesel.
- `_daily_price_lookup(price_series, dates)` — takes a monthly Series and a
  DatetimeIndex of simulation dates, returns a Series of daily rates via
  forward-fill (`reindex` + `ffill`). Raises `ValueError` if the first
  simulation date precedes the first price entry.

### Step 3: Equipment spec builders

- `_load_equipment_specs(csv_path, type_id)` — loads equipment CSV with
  `comment='#'`, finds the row where `type_id` matches, returns that row as a
  dict. Raises `ValueError` if no match found.
- `_build_battery_specs(energy_system_config, policy_config, equipment_path)` —
  returns `None` when `has_battery: false`. Otherwise loads the battery row by
  `type_id`, then builds the `battery_specs` dict using **policy SOC limits**
  (not CSV SOC limits): `capacity_kwh`, `soc_min_kwh`, `soc_max_kwh`,
  `max_charge_kwh` (= `power_kw × 24`), `max_discharge_kwh` (same),
  `charge_efficiency`, `discharge_efficiency`.
- `_build_generator_specs(energy_system_config, policy_config, equipment_path)` —
  returns `None` when `has_generator: false`. Otherwise loads the generator row
  by `type_id`, then builds: `rated_capacity_kw`, `min_load_kw`
  (= `min_load_fraction × rated_capacity_kw`), `sfc_coefficient_a`,
  `sfc_coefficient_b`.

### Step 4: Grid validation and export rate resolution

- `_validate_grid_config(grid_connection, grid_mode)` — checks the compatibility
  table from the spec. Raises `ValueError` for invalid combinations.
- `_resolve_export_rate(policy_grid, registry_paths)` — when
  `mode == feed_in_tariff`: if `export_rate_usd_kwh` is set, return it;
  otherwise load `feed_in_tariff_rates-toy.csv`, match `capacity_tier` to
  `project_size_category`, return the `rate_usd_kwh_effective` value. For all
  other modes, return `0.0`.

### Step 5: Monthly cap and daily allowance

- `_daily_cap_allowance(monthly_cap, used, day, look_ahead)` — calculates the
  available allowance for today. When `monthly_cap` is None, return `math.inf`.
  When `look_ahead` is True: `(monthly_cap - used) / days_remaining` (including
  today). When False: `monthly_cap - used`. Mirror the pattern from
  `src/water.py`.

### Step 6: Battery helpers

- `_charge_battery(surplus_kwh, battery_specs, battery_state, renewable=True)` —
  computes how much energy is accepted into the battery. Caps by
  `max_charge_kwh`, available headroom `(soc_max_kwh - soc_kwh)`, and applies
  `charge_efficiency`. Updates `battery_state['soc_kwh']` in place. Updates
  `battery_state['renewable_fraction']` as a weighted blend:
  `new_frac = (old_soc × old_frac + stored × source_frac) / new_soc` where
  `source_frac` is `1.0` when `renewable=True` and `0.0` when `False`.
  Returns `(accepted_kwh, stored_kwh)` where `accepted_kwh` is the surplus
  consumed and `stored_kwh` is what actually entered the battery
  (`accepted × efficiency`).
- `_discharge_battery(deficit_kwh, battery_specs, battery_state)` — computes
  how much energy is delivered from the battery. Caps by `max_discharge_kwh`,
  available energy `(soc_kwh - soc_min_kwh)`, and applies
  `discharge_efficiency`. Updates `battery_state['soc_kwh']` in place.
  Computes `renewable_delivered = delivered × battery_state['renewable_fraction']`.
  Returns `(delivered_kwh, soc_draw_kwh, renewable_delivered_kwh)`.

### Step 7: Grid helpers

- `_grid_import_available(grid_mode, grid_cap_state)` — returns daily import
  allowance. Returns `0.0` for `off_grid`. Otherwise calls
  `_daily_cap_allowance` using `grid_cap_state['import']`.
- `_grid_export_available(grid_mode, grid_cap_state)` — returns daily export
  allowance. Returns `0.0` for `off_grid`, `self_consumption`, `limited_grid`.
  Otherwise calls `_daily_cap_allowance` using `grid_cap_state['export']`.

### Step 8: Generator helper

- `_run_generator(deficit_kwh, generator_specs, fuel_cap_state)` — generator
  runs at `power_kw = max(deficit_kwh / 24, min_load_kw)`, capped by
  `rated_capacity_kw`. Hours = `deficit_kwh / power_kw` (but if running at
  min load, hours = 24 and output = `min_load_kw × 24`; then
  `delivered = min(output, deficit_kwh)`, `excess = output - delivered`).
  Fuel via Willans line: `fuel = (a × rated_kw + b × power_kw) × hours`.
  Check monthly fuel cap — if fuel would exceed remaining cap, scale hours
  down proportionally. Returns `(delivered_kwh, excess_kwh, fuel_liters,
  runtime_hours)`.

### Step 9: Cost and metrics helpers

- `_compute_grid_import_cost(import_kwh, community_kwh, water_kwh, total_kwh,
  ag_tariff, commercial_tariff)` — splits import proportionally by demand
  share: `water_share = water_kwh / total_kwh` (guard against zero total),
  cost = `import × (water_share × ag_tariff + community_share × commercial_tariff)`.
- `_compute_net_metering_cost(...)` — when mode is `net_metering`: tracks
  cumulative monthly import/export in `net_metering_state`. If net monthly
  position is credit (export > import), daily cost is 0. Otherwise uses
  standard weighted cost. At June settlement month, excess credits become
  revenue at `excess_buyback_usd_kwh`. For non-net-metering modes, falls
  through to standard cost.
- `_init_energy_dispatch_row(...)` — creates a zeroed dict with all output
  column keys. Sets pass-through values (day, demands, generation totals).
- `_finalize_energy_dispatch_row(row, battery_specs, battery_state)` —
  computes `self_sufficiency_ratio`, `self_consumption_ratio`,
  `renewable_fraction`, `total_energy_cost`. Sets policy columns.

### Step 10: Dispatch day function

`_dispatch_day(...)` — the core per-day dispatch. Follow the spec's dispatch
pseudocode exactly:

1. Init row via `_init_energy_dispatch_row`
2. Compute `net_load`, `renewable_consumed`, `renewable_surplus`
3. Strategy-dependent action lists:
   ```
   SURPLUS_ORDER = {
       'minimize_cost':              ['battery', 'export', 'curtail'],
       'minimize_grid_reliance':  ['battery', 'curtail'],
       'minimize_generator':         ['battery', 'export', 'curtail'],
   }
   DEFICIT_ORDER = {
       'minimize_cost':              ['battery', 'grid', 'generator'],
       'minimize_grid_reliance':  ['battery', 'generator', 'grid'],
       'minimize_generator':         ['battery', 'grid', 'generator'],
   }
   ```
4. Surplus loop: iterate actions, consume remaining surplus
5. Deficit loop: iterate actions, reduce remaining deficit. For generator,
   handle min-load excess → `_charge_battery(..., renewable=False)` then
   curtail remainder
6. Compute costs via `_compute_grid_import_cost` or `_compute_net_metering_cost`
7. Finalize via `_finalize_energy_dispatch_row`
8. Return `(row, battery_state)`

### Step 11: Simulation loop

`_run_simulation(...)` — manages the daily loop. Pattern mirrors
`_run_simulation` in `src/water.py`:

1. Initialize `battery_state = {'soc_kwh': initial_soc, 'renewable_fraction': 1.0}`
2. Initialize monthly tracking dicts:
   - `grid_cap_state = {'import': {'monthly_cap': ..., 'used': 0}, 'export': {'monthly_cap': ..., 'used': 0}, 'look_ahead': ...}`
   - `fuel_cap_state = {'monthly_cap': ..., 'used': 0}`
   - `net_metering_state = {'monthly_import': 0, 'monthly_export': 0, 'credit_balance': 0}`
3. Track `current_month = None`
4. For each day:
   a. Check month boundary — reset `used` counters and net metering monthly
      accumulators when `(year, month)` changes. Handle June settlement.
   b. Look up daily prices (ag_tariff, commercial_tariff, diesel) from
      pre-built daily price Series
   c. Call `_dispatch_day(...)` with all arguments
   d. Update `grid_cap_state['import']['used']` and `['export']['used']`
   e. Update `fuel_cap_state['used']`
   f. Stamp cap tracking columns onto the row
   g. Append row to results list
5. Return `pd.DataFrame(rows)`

### Step 12: Public API

- `compute_daily_energy_balance(...)` — the top-level orchestrator. Follow the
  spec's Orchestration section (steps 1–10). Calls `compute_daily_energy()`,
  `compute_daily_demands()`, handles `water_balance_df`, loads prices, builds
  specs, validates grid config, calls `_run_simulation`, orders columns.
- `save_energy_balance(df, output_dir, *, filename='daily_energy_balance.csv',
  decimals=3)` — identical pattern to `save_energy` in `src/energy_supply.py`.
- `load_energy_balance(path)` — identical pattern to `load_energy`.
- `_order_energy_balance_columns(df)` — groups columns in the order listed in
  the spec's Daily Output Columns section: day, demands, generation, dispatch,
  battery state, generator state, cost, metrics, policy/caps.
- `if __name__ == '__main__':` block per the spec.

### Step 13: Validation

Run these checks in order:

1. `python -m src.energy_balance` — standalone verification. Should produce
   `simulation/daily_energy_balance.csv` and print the first 3 rows without
   error. Note: without `water_balance_df`, water energy demand will be zero.
2. Verify output columns match the spec's Daily Output Columns tables.
3. Verify that with the baseline config (`strategy: minimize_cost`,
   `grid.mode: self_consumption`, `has_battery: false`, `has_generator: true`):
   - Battery columns are absent (has_battery is false)
   - No grid export occurs (self_consumption mode)
   - Generator runs on deficit days
   - `total_demand_kwh = community_energy_demand_kwh + water_energy_demand_kwh`
   - `renewable_consumed + deficit + grid_import + generator + battery_discharge
     = total_demand` (energy conservation)
   - `renewable_consumed + curtailed + grid_export + battery_charge
     = total_renewable` (generation conservation)
4. Run `python -m pytest tests/` to verify no regressions in existing modules.

## Key Constraints

- **Functional programming only** — no classes, no stateful objects. State is
  passed as plain dicts (battery_state, cap states).
- **Internal helpers prefixed with `_`** — public API uses keyword arguments
  with defaults.
- **Policy overrides CSV** — SOC limits from policy, not from equipment CSV.
- **Equipment lookup by `type_id`** — single-column match in both CSVs.
- **All caps are monthly** — `monthly_import_cap_kwh`, `monthly_export_cap_kwh`,
  `monthly_fuel_cap_liters`. Daily allowance computed by `_daily_cap_allowance`.
- **Prices are monthly, forward-filled to daily** — use `usd_per_kwh_avg_daily`
  for electricity, `usd_per_liter` for diesel.
- **No typing annotations** unless critical for avoiding errors.
- **No try/except** — let errors propagate explicitly.
- **Google-style docstrings** for all functions.
