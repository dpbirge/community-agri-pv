# Food Processing and Storage Specification

---

## Purpose

Convert raw harvest yields into market-ready products (fresh, packaged, canned,
dried) and track their storage inventory until sale. The module is a
**post-harvest observer** — it reads the daily harvest CSV produced by
`crop_yield.py` and applies processing decisions, but never modifies upstream
crop growth, irrigation, or water balance calculations.

Key outputs: daily processing throughput (kg), daily energy consumption (kWh),
daily labor hours by worker category, storage inventory levels (kg) with daily
spoilage losses, and final product weights in sale-ready units (accounting for
dehydration, trimming, and handling losses).

---

## Implementation Status

### Complete

**Data files** (`data/food_processing/`):

- `processing_specs-research.csv` — 20 rows (5 crops x 4 processing types);
  energy (kWh/kg), labor (hrs/kg), weight loss (%), value-add multiplier,
  processing time (hrs), storage life (days). Research-grade from FAO/USDA.
- `handling_loss_rates-research.csv` — 20 rows (5 crops x 4 pathways); waste
  loss percentages separate from processing weight change. Research-grade.
- `processing_equipment-toy.csv` — 9 equipment types across 4 categories
  (packaging, drying, canning, fresh_packaging) with capacity (kg/day),
  continuous power (kW), labor (hrs/kg), capital cost, maintenance, lifespan.
- `storage_spoilage_rates-toy.csv` — 40 rows (5 crops x 4 product types x
  2 storage conditions); daily spoilage rate (%) and shelf life (days).
- `fresh_packaging-toy.csv` — 5 packaging types for fresh produce with cost,
  labor, energy, and shelf life extension.
- `processed_packaging-toy.csv` — 4 packaging types for canned/dried products.

**Labor data** (`data/labor/`):

- `processing_labor-research.csv` — per-kg labor by crop and processing type
  with worker category assignments.
- `storage_labor-research.csv` — recurring monthly per-ton storage labor and
  one-time loading/curing labor by crop and storage type.

**Price data** (`data/prices/crops/`):

- `historical_{crop}_prices-toy.csv` — 10-year monthly wholesale and farmgate
  price series for all 5 crops. Used by the market module (not this module)
  but value-add multipliers in processing_specs reference these ratios.

**Harvest input** (`simulation/`):

- `daily_harvest_yields.csv` — daily harvest output from `crop_yield.py`.
  Already produced by `save_harvest_yields()` in `src/crop_yield.py` and
  called from `notebooks/simulation.ipynb`. Columns match this spec:
  `day`, `{field}_{crop}_harvest_kg`, `total_harvest_kg`.

### Not Yet Implemented

- `settings/food_processing_base.yaml` — processing policy configuration
- `src/food_processing.py` — processing and storage engine
- Scenario file entry (`food_processing:` line in `scenario_base.yaml`)
- Data registry entries for food processing files

---

## Architecture

### Module Position in Data Flow

```
crop_yield.py                    (upstream — produces daily_harvest_yields.csv)
    |
    v
food_processing.py               (this module — reads harvest CSV)
    |
    ├── processing queues         (daily throughput limited by equipment)
    ├── weight conversion         (fresh → processed weight)
    ├── storage inventory         (daily tracking with spoilage)
    ├── energy demand             (processing + cold storage)
    └── labor demand              (processing + storage handling)
    |
    v
market module (future)           (downstream — decides when/what to sell)
```

The food processing module reads `simulation/daily_harvest_yields.csv` — a daily
CSV produced by `crop_yield.py` with one row per day and per-field harvest
columns. It never reaches back into crop growth, irrigation, or water balance
logic. Its outputs (inventory, energy, labor) feed forward into energy balance
aggregation and labor demand reporting, and eventually into a market/sales module.

### Functional Programming Approach

Same patterns as all `src/` modules:

- Internal helpers prefixed with `_` (e.g., `_load_processing_specs`)
- Public API uses keyword arguments with defaults
- No classes; DataFrames and dicts are the only data containers
- Pure functions where possible; processing queue state carried via DataFrame
  columns, not mutable objects

---

## Harvest Input

### Daily Harvest CSV

`crop_yield.py` produces `simulation/daily_harvest_yields.csv` — a daily CSV
covering the full simulation period. Most days have zero values; harvest days
carry the total field harvest in kg.

**Columns:**

| Column | Description |
|--------|-------------|
| `day` | Date |
| `{field}_{crop}_harvest_kg` | Harvest arriving on this day (kg fresh weight) |
| `total_harvest_kg` | Sum across all fields |

Each harvest value is already `yield_kg_per_ha * area_ha` — the food processing
module reads these totals directly without needing farm profile metadata.

### Harvest Event Behavior

A harvest arrives on a single day — the last day of the crop's growing season.
The processing module treats this as a **batch arrival**: a potentially large
volume of produce lands on one day and must be processed over subsequent days
based on equipment throughput capacity.

Multiple fields may harvest on the same day or on different days. The module
handles overlapping processing queues from concurrent harvests.

---

## Processing Pathways

Four processing types, each producing a distinct product with different weight,
shelf life, and value characteristics:

| Pathway   | Description                          | Weight Change | Shelf Life   | Value-Add  |
|-----------|--------------------------------------|---------------|--------------|------------|
| fresh     | Wash, sort, package for sale          | 2–5% loss     | 7–21 days    | 1.0x       |
| packaged  | Wash, sort, grade, box               | 2–5% loss     | 10–25 days   | 1.15–1.3x  |
| canned    | Thermal processing / pickling        | 8–20% loss    | 730 days     | 1.3–2.0x   |
| dried     | Solar or mechanical dehydration      | 78–95% loss   | 350–500 days | 5–24x      |

Weight loss for `dried` is dominated by moisture removal, not waste. The output
weight is the **sale weight** — dried tomato prices are per kg of dried product,
so the 93% weight loss is already embedded in the 24x value-add multiplier.

### Two-Step Loss Model

Each kilogram of harvested crop passes through two independent loss stages:

1. **Handling loss** (from `handling_loss_rates-research.csv`) — waste from
   sorting rejects, bruising, spillage, and spoilage between harvest and the
   start of processing. Applied **at queue entry** so that queue weights
   reflect only usable product.

2. **Processing weight change** (from `processing_specs-research.csv`,
   `weight_loss_pct` column) — mass change from the processing itself
   (dehydration, peeling, trimming, liquid addition for canning). Applied
   when product is dequeued and processed.

```
queue_entry_kg = harvest_allocated_kg * (1 - handling_loss_pct / 100)
product_kg     = dequeued_kg * (1 - weight_loss_pct / 100)
```

Example — dried tomato from 1000 kg allocated to drying:
```
queue_entry = 1000 * (1 - 3/100)  = 970 kg   (3% dried-pathway handling loss)
product_kg  = 970  * (1 - 93/100) =  67.9 kg  (93% moisture removal)
```

### Adding New Processing Types

To add a new processing type (e.g., `frozen`, `juiced`):

1. Add rows to `processing_specs-research.csv` for each crop
2. Add rows to `handling_loss_rates-research.csv` for each crop
3. Add rows to `storage_spoilage_rates-toy.csv` for each crop × storage condition
4. Add equipment to `processing_equipment-toy.csv` if new machinery is needed
5. No code changes required — the module reads processing types from the data

---

## Processing Policy Configuration

### `settings/food_processing_base.yaml`

```yaml
# Food Processing Policy
# Defines how harvested crops are allocated to processing pathways,
# which equipment is used, and storage conditions.

config_name: baseline_processing

# --- Processing Allocation ---
# Fraction of each crop's harvest routed to each pathway.
# Fractions must sum to 1.0 for each crop.
processing_allocation:
  tomato:
    fresh: 0.30
    packaged: 0.20
    canned: 0.20
    dried: 0.30
  potato:
    fresh: 0.40
    packaged: 0.40
    canned: 0.10
    dried: 0.10
  onion:
    fresh: 0.35
    packaged: 0.35
    canned: 0.15
    dried: 0.15
  kale:
    fresh: 0.50
    packaged: 0.30
    canned: 0.10
    dried: 0.10
  cucumber:
    fresh: 0.35
    packaged: 0.25
    canned: 0.25
    dried: 0.15

# --- Equipment Selection ---
# Which equipment type to use for each processing category.
# Must match equipment_type values in processing_equipment-toy.csv.
equipment:
  drying: solar_tunnel_dryer
  canning: simple_retort
  packaging: packaged
  fresh_packaging: washing_sorting_line

# --- Storage Conditions ---
# Storage method for each product type.
# Options: ambient | climate_controlled
storage_conditions:
  fresh: climate_controlled
  packaged: climate_controlled
  canned: ambient
  dried: ambient

# --- Cold Storage ---
# Continuous power draw for climate-controlled storage.
cold_storage:
  energy_kwh_per_m3_per_day: 2.4     # refrigerated warehouse, ~5C
  kg_per_m3_storage: 300             # storage density (produce in crates)

# --- Working Schedule ---
# Processing does not run every day.
working_days_per_week: 6             # Sunday–Friday (Egypt standard)
working_hours_per_day: 8
```

### Validation Rules

- `processing_allocation` fractions must sum to 1.0 (± 0.001 tolerance) per crop
- `equipment` types must exist in `processing_equipment-toy.csv`
- `storage_conditions` values must be `ambient` or `climate_controlled`
- Any crop present in `farm_profile_base.yaml` must have an allocation entry

---

## Processing Queue Model

### Problem: Throughput Limits

A harvest may deliver thousands of kilograms in a single day, but equipment has
a finite daily capacity (kg/day). The processing queue spreads work across
multiple days.

### Queue Logic

On each harvest day, the module splits the harvest by the allocation fractions,
applies handling loss, and adds the post-loss amounts to per-pathway queues:

```
for pathway in [fresh, packaged, canned, dried]:
    allocated_kg  = harvest_kg * allocation[pathway]
    handling_loss  = allocated_kg * handling_loss_pct[crop][pathway] / 100
    queue[pathway] += allocated_kg - handling_loss
```

All four pathways go through queues — fresh produce must pass through the
washing/sorting line (capacity-limited like any other equipment).

### Capacity Sharing Across Crops

Each equipment category has a single daily capacity shared across all crops.
When multiple crops compete for the same equipment, capacity is allocated
**proportionally to queue size**:

```
total_queue = sum(queue[crop] for all crops using this equipment)
for each crop:
    crop_share      = queue[crop] / total_queue
    processed_today = min(queue[crop], capacity * crop_share)
    queue[crop]    -= processed_today
```

### Queue Spoilage

Produce sitting in a processing queue is **unprocessed fresh product** and
spoils at that crop's fresh ambient spoilage rate from
`storage_spoilage_rates-toy.csv` (e.g., tomato = 3.5%/day, kale = 4.0%/day),
regardless of destination pathway. The queue shrinks daily due to both
spoilage and processing:

```
queue_spoilage  = queue * fresh_ambient_spoilage_rate_per_day
queue          -= queue_spoilage
processed_today = min(queue, available_capacity)
queue          -= processed_today
```

This creates a realistic pressure to process quickly — large harvests that
exceed equipment capacity lose product to spoilage while waiting.

### Non-Working Days

On non-working days (based on `working_days_per_week`), no processing occurs
but queue spoilage still applies. The rest day is Saturday, which maps to
Python's `date.weekday() == 5`. The `_is_working_day` helper returns `False`
when `date.weekday() == 5` and `working_days_per_week == 6`.

---

## Storage Inventory Model

### Daily Inventory Tracking

Each product type × crop combination maintains a storage inventory (kg):

```
inventory[crop][product_type] += newly_processed_kg_today
inventory[crop][product_type] -= spoilage_today
inventory[crop][product_type] -= sold_today   (future: set by market module)
```

Until the market module exists, `sold_today` is zero — product accumulates
and spoils. The market module will draw down inventory.

### Spoilage in Storage

Storage spoilage is a daily percentage loss from `storage_spoilage_rates-toy.csv`,
selected by crop, product type, and the configured storage condition:

```
spoilage_kg = inventory * spoilage_rate_pct_per_day / 100
inventory  -= spoilage_kg
```

### Cohort Tracking and Shelf Life Expiry

Every batch of processed product is tracked as a **cohort** with a production
date. Each day's processed output for a given crop × pathway is one cohort.
On each simulation day, any cohort that has exceeded its `shelf_life_days`
is discarded entirely — this applies to **all product types** including
canned and dried.

Daily spoilage rates degrade each cohort continuously, and the shelf life
cutoff removes whatever remains at expiry. Both mechanisms run together.

The number of active cohorts stays manageable because harvests occur only a
few times per year per crop (typically 1–4 plantings), so even long-lived
products like canned (730 days) accumulate at most ~8–16 active cohorts
across a 15-year simulation.

### Cohort Data Structure

Cohorts are stored as a plain dict of lists, keyed by `(crop, pathway)`.
Each list entry is a dict with `production_date` and `remaining_kg`. This
structure is passed into and returned from `_step_day()` — no mutable
global state, consistent with the functional programming pattern used by
all other `src/` modules.

```python
# Example cohort state
cohorts = {
    ('tomato', 'dried'): [
        {'production_date': Timestamp('2015-06-10'), 'remaining_kg': 42.1},
        {'production_date': Timestamp('2015-06-11'), 'remaining_kg': 38.7},
    ],
    ('tomato', 'canned'): [
        {'production_date': Timestamp('2015-06-10'), 'remaining_kg': 155.0},
    ],
}
```

On each day, `_step_day()` receives the current `cohorts` dict and returns
an updated copy. Expired cohorts (where `day - production_date > shelf_life_days`)
are removed. Daily spoilage reduces `remaining_kg` in place before the copy
is returned.

---

## Energy Tracking

### Processing Energy

Energy consumed during processing, per day:

```
processing_energy_kwh = sum across all crops and pathways of:
    processed_kg_today * energy_kwh_per_kg
```

Where `energy_kwh_per_kg` comes from `processing_specs-research.csv` for the
crop × processing_type combination. This is the **single source** for
processing energy — it represents total electrical energy per kg of fresh
input, already accounting for the equipment type's efficiency.

The `energy_kw_continuous` column in `processing_equipment-toy.csv` is the
machine's power rating, retained for peak demand sizing and capital planning
but **not used** in the daily energy calculation (using both would double-count).

**Data update required:** The `fresh` rows in `processing_specs-research.csv`
currently have `energy_kwh_per_kg = 0.0`, but fresh produce passes through
the `washing_sorting_line` (5 kW continuous, 3000 kg/day capacity, 8 hrs/day).
The implied per-kg energy is `5 kW × 8 hrs / 3000 kg ≈ 0.013 kWh/kg`. Update
the five `fresh` rows in `processing_specs-research.csv` to `energy_kwh_per_kg
= 0.013` and `labor_hours_per_kg = 0.06` (matching the equipment spec) before
implementation so that fresh processing is not silently zero-energy.

### Cold Storage Energy

For products stored under `climate_controlled` conditions:

```
storage_volume_m3  = total_climate_controlled_inventory_kg / kg_per_m3_storage
cold_storage_kwh   = storage_volume_m3 * energy_kwh_per_m3_per_day
```

Cold storage energy is continuous — it runs every day including non-working days.

### Total Daily Energy

```
total_processing_energy_kwh = sum of processing_energy_kwh across all pathways
total_storage_energy_kwh    = cold_storage_kwh
total_food_energy_kwh       = total_processing_energy_kwh + total_storage_energy_kwh
```

### Energy Balance Integration

The food processing module's `total_food_processing_energy_kwh` column feeds
into `compute_daily_energy_balance()` in `src/energy_balance.py` as a third
demand component alongside community building demand and water system demand.

**Required changes to `src/energy_balance.py`:**

1. Add a `food_processing_df` keyword argument to `compute_daily_energy_balance()`,
   defaulting to `None` (backwards-compatible with existing callers).

2. When provided, extract a daily energy series from the DataFrame's
   `total_food_processing_energy_kwh` column, merge on `day`, and add it
   to `total_demand_kwh`:

   ```python
   total_demand = community_demand + water_demand + food_processing_demand
   ```

3. Add a `food_processing_energy_demand_kwh` column to the output DataFrame
   and include it in `_order_energy_balance_columns()`.

4. For tariff assignment, food processing energy uses the agricultural tariff
   (same as water energy) since the processing facility is part of the farm
   operation. The existing `_compute_grid_import_cost()` tariff split logic
   should treat food processing demand like water demand.

---

## Labor Tracking

### Processing Labor

```
processing_labor_hrs = processed_kg_today * labor_hours_per_kg
```

The authoritative source for processing labor is
`processing_labor-research.csv` (`data/labor/`), which provides both
`labor_hours_per_kg` and `worker_category` per crop × processing_type.
The `labor_hours_per_kg` column in `processing_specs-research.csv` is a
convenience duplicate retained for human reference — the module reads labor
data exclusively from `processing_labor-research.csv`.

### Storage Labor

From `storage_labor-research.csv`. The CSV has a richer structure than
the simple formula below — the aggregation logic handles it as follows.

**Recurring monthly labor** (unit = `per_ton_per_month`). The CSV lists
separate activity types (temperature_monitoring, quality_inspection,
inventory_management, cleaning, pest_monitoring, moisture_monitoring),
each with its own `hours_per_unit` and `worker_category`. The module
sums all `per_ton_per_month` activities for the matching crop and
storage type, then converts to a daily rate:

```
monthly_rate = sum of hours_per_unit for all per_ton_per_month activities
               matching (crop, storage_type)
daily_storage_labor_hrs = inventory_tons * monthly_rate / 30
```

**Wildcard crop entries.** Rows with crop values `fresh_all`, `canned_all`,
`dried_all`, or `all` apply to every crop in that product category. When
loading, expand these into per-crop entries. For example, `canned_all`
maps to all five crops' canned inventory.

**One-time loading/unloading labor** (unit = `per_ton_per_turnover`):
applied on the day product enters or leaves storage.

```
loading_labor_hrs = newly_stored_tons * loading_rate_hrs_per_ton
```

**Facility-level labor** (units = `per_day`, `per_week`,
`per_cold_room_per_month`). These are fixed overhead not tied to inventory
volume. Convert each to a daily rate:
- `per_day`: use directly
- `per_week`: divide by 7
- `per_cold_room_per_month`: multiply by number of cold rooms (assume 2
  at community scale) and divide by 30

Add facility-level labor to the daily total on every day that has any
inventory in the corresponding storage type (cold or ambient).

### Curing Labor

Potatoes and onions require curing before long-term storage. From
`storage_labor-research.csv`:

```
curing_labor_hrs = batch_tons * curing_rate_hrs_per_ton
```

Applied once per harvest batch on the first day of storage.

### Labor Output Columns

Labor is reported by worker category matching `storage_labor-research.csv` and
`processing_labor-research.csv`, enabling costing via `labor_wages-research.csv`:

- `processing_worker_hours` — processing line labor (packaged, canned, dried)
- `field_worker_hours` — loading/unloading, cleaning, general handling
- `field_supervisor_hours` — inventory management, curing operations
- `quality_inspector_hours` — quality inspection, moisture monitoring
- `irrigation_technician_hours` — cold storage temperature monitoring
- `maintenance_technician_hours` — equipment monitoring

---

## Daily Output Columns

The output DataFrame has one row per day for the full simulation period.
Days with no processing or storage activity have zeros.

### Harvest (carried from input CSV)

| Column | Description |
|--------|-------------|
| `total_harvest_kg` | Sum of all harvest columns for this day |

### Processing Throughput

| Column | Description |
|--------|-------------|
| `{crop}_fresh_processed_kg` | Fresh produce moved to storage (kg) |
| `{crop}_packaged_processed_kg` | Packaged output (kg post-loss) |
| `{crop}_canned_processed_kg` | Canned output (kg post-loss) |
| `{crop}_dried_processed_kg` | Dried output (kg post-loss) |
| `total_processed_kg` | Sum across all crops and pathways |

### Processing Queues

| Column | Description |
|--------|-------------|
| `{crop}_fresh_queue_kg` | End-of-day queue for washing/sorting (kg) |
| `{crop}_packaged_queue_kg` | End-of-day queue for packaging (kg) |
| `{crop}_canned_queue_kg` | End-of-day queue for canning (kg) |
| `{crop}_dried_queue_kg` | End-of-day queue for drying (kg) |
| `total_queue_kg` | Sum across all queues |
| `queue_spoilage_kg` | Product lost to spoilage while in queue today |

### Storage Inventory

| Column | Description |
|--------|-------------|
| `{crop}_fresh_inventory_kg` | End-of-day fresh inventory (kg) |
| `{crop}_packaged_inventory_kg` | End-of-day packaged inventory (kg) |
| `{crop}_canned_inventory_kg` | End-of-day canned inventory (kg) |
| `{crop}_dried_inventory_kg` | End-of-day dried inventory (kg) |
| `total_inventory_kg` | Sum across all products |
| `storage_spoilage_kg` | Product lost to spoilage in storage today |
| `total_spoilage_kg` | Queue spoilage + storage spoilage |

### Energy

| Column | Description |
|--------|-------------|
| `processing_energy_kwh` | Energy consumed by processing today |
| `cold_storage_energy_kwh` | Cold storage refrigeration energy today |
| `total_food_processing_energy_kwh` | Processing + cold storage |

### Labor

| Column | Description |
|--------|-------------|
| `processing_labor_hours` | Processing line labor today |
| `storage_labor_hours` | Storage handling/monitoring labor today |
| `total_food_labor_hours` | Processing + storage labor |

### Cumulative Metrics

| Column | Description |
|--------|-------------|
| `cumulative_harvest_kg` | Running total of all harvests |
| `cumulative_processed_kg` | Running total of all processed output |
| `cumulative_spoilage_kg` | Running total of all losses (queue + storage) |
| `spoilage_pct` | `cumulative_spoilage_kg / cumulative_harvest_kg * 100` |

---

## Module API

### Public Functions

```python
def compute_food_processing(*,
                            harvest_path='simulation/daily_harvest_yields.csv',
                            registry_path,
                            processing_policy_path,
                            root_dir=None):
    """Simulate daily food processing and storage for all harvested crops.

    Args:
        harvest_path: path to daily harvest CSV from crop_yield.py, with columns
            day, {field}_{crop}_harvest_kg, total_harvest_kg
        registry_path: path to data_registry_base.yaml
        processing_policy_path: path to food_processing_base.yaml
        root_dir: repository root; defaults to registry_path.parent.parent

    Returns:
        DataFrame with one row per day, columns as documented above.
    """
```

```python
def save_food_processing(df, *, output_path='simulation/daily_food_processing.csv'):
    """Write processing results to CSV."""
```

```python
def load_food_processing(*, output_path='simulation/daily_food_processing.csv'):
    """Read previously saved processing results.

    Uses parse_dates=['day'] for consistency with all other load_*()
    functions in the codebase (e.g., load_daily_water_balance,
    load_energy, load_demands).
    """
```

### Internal Helpers

| Function | Purpose |
|----------|---------|
| `_load_processing_specs(registry, root_dir)` | Load and index processing_specs CSV by (crop, type) |
| `_load_handling_losses(registry, root_dir)` | Load handling_loss_rates CSV by (crop, pathway) |
| `_load_equipment(registry, root_dir)` | Load equipment specs CSV |
| `_load_spoilage_rates(registry, root_dir)` | Load storage spoilage CSV by (crop, type, condition) |
| `_build_processing_queues(harvest_events, allocation)` | Initialize queues from harvest batches |
| `_step_day(queues, inventory, equipment, specs, day)` | Advance one day: process, spoil, store |
| `_compute_product_weight(fresh_kg, crop, pathway, specs, losses)` | Two-step loss calculation |
| `_is_working_day(date, working_days_per_week)` | Check if processing runs today |

### Orchestration Steps

1. Load harvest CSV, processing specs, handling losses, equipment, spoilage rates
2. Load and validate processing policy YAML
3. Parse harvest CSV columns to identify crop and field names
4. Initialize empty queues and inventory (cohorts)
5. For each day in the harvest CSV date range:
   a. Read harvest columns for today; for non-zero harvests, split by
      allocation fractions, apply handling loss, add post-loss kg to queues
   b. Apply queue spoilage (fresh ambient rate) to all queues
   c. If working day: process from each queue up to equipment capacity,
      sharing proportionally across crops; apply processing weight loss
      to dequeued product
   d. Add processed product to storage inventory as new cohort
   e. Apply daily storage spoilage to all cohorts
   f. Remove expired cohorts (past shelf life)
   g. Compute daily energy (processing + cold storage)
   h. Compute daily labor by worker category (processing + storage + loading)
   i. Record all values as one row in output DataFrame
6. Append cumulative metrics
7. Return DataFrame

---

## Data Registry Additions

Add to `settings/data_registry_base.yaml`:

```yaml
# --- Food Processing ---
food_processing:
  processing_specs:      data/food_processing/processing_specs-research.csv
  handling_losses:       data/food_processing/handling_loss_rates-research.csv
  processing_equipment:  data/food_processing/processing_equipment-toy.csv
  storage_spoilage:      data/food_processing/storage_spoilage_rates-toy.csv
  fresh_packaging:       data/food_processing/fresh_packaging-toy.csv
  processed_packaging:   data/food_processing/processed_packaging-toy.csv
  processing_labor:      data/labor/processing_labor-research.csv
  storage_labor:         data/labor/storage_labor-research.csv
```

---

## Scenario File Addition

Replace the existing commented-out line in `scenarios/scenario_base.yaml`
(which incorrectly reads `settings/food_processing.yaml` without the `_base`
suffix) with:

```yaml
food_processing: settings/food_processing_base.yaml
```

---

## Standalone Verification

```python
if __name__ == '__main__':
    # Requires simulation/daily_harvest_yields.csv from crop_yield.py
    df = compute_food_processing(
        harvest_path='simulation/daily_harvest_yields.csv',
        registry_path='settings/data_registry_base.yaml',
        processing_policy_path='settings/food_processing_base.yaml',
    )
    print(df[['day', 'total_harvest_kg', 'total_processed_kg',
              'total_inventory_kg', 'total_spoilage_kg',
              'total_food_processing_energy_kwh',
              'total_food_labor_hours']].to_string(index=False))
    print(f"\nCumulative spoilage: {df['cumulative_spoilage_kg'].iloc[-1]:.0f} kg")
    print(f"Spoilage rate: {df['spoilage_pct'].iloc[-1]:.1f}%")
```

---

## Assumptions

- **Single equipment per category.** The policy selects one equipment type per
  processing category. Multiple machines of the same type can be modeled by
  scaling capacity in a future extension.
- **Queue spoilage uses fresh ambient rate.** Produce waiting in a processing
  queue is treated as unrefrigerated fresh product. If the community has staging
  cold storage, this could be reduced — but that is not modeled here.
- **No water consumption.** Processing water (washing, canning liquid) is not
  tracked. It is small relative to irrigation volumes and can be added later.
- **Packaging material costs not tracked.** Material costs from the packaging
  CSVs are available but not included in this module's outputs. The market
  module will handle cost accounting.
- **No transport between processing and storage.** The community facility is
  assumed co-located — processing and storage happen at the same site.
- **Curing is implicit.** Potato and onion curing (a multi-day ambient drying
  step before long-term storage) is accounted for via the processing time and
  handling loss, not as a separate queue stage.
- **Year boundaries.** Inventory carries across calendar year boundaries.
  A 15-year simulation accumulates and decays inventory continuously.

---

## Intentionally Deferred Extensions

The following features are out of scope for the initial implementation but may
be valuable additions:

- **Market/sales module integration** — draw down inventory based on price
  signals, seasonal demand, and shelf life urgency. This is the next module
  after food processing.
- **Multiple equipment units** — model 2x or 3x machines to increase throughput
  capacity. Simple capacity multiplier.
- **Processing water demand** — track water used for washing, canning liquid,
  and cleaning. Feed into water balance.
- **Packaging material cost tracking** — use existing packaging CSVs to compute
  per-product packaging costs.
- **Quality grading** — split harvest into grade A / grade B with different
  processing routing (e.g., grade B → canned, grade A → fresh).
- **Seasonal processing allocation** — vary allocation fractions by month
  (e.g., more drying in summer when solar thermal is abundant, more fresh
  in winter when ambient temperatures are cooler).
- **Cold chain energy optimization** — model shared cold rooms with
  temperature setpoints and door-opening losses.
- **Batch tracking with traceability** — link processed products back to
  specific fields and harvest dates for export certification.
- **Processing waste valorization** — track peels, seeds, and reject produce
  for compost or animal feed.
