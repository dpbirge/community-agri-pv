# Policy Specifications

## 1. Overview

This document specifies the decision logic for all active simulation policies across 5 domains: crop, water, energy, food processing, and market. Economic policies are deferred. Each policy is defined in plain English and pseudocode. The translation to code is left to the implementer.

Related documents:

- `structure.md` — Configuration schema, dataclass definitions, enumerated types
- `simulation_flow.md` — Execution sequence and integration
- `calculations.md` — Calculation methodologies and formulas

**Cross-reference convention:** `→ spec_file.md § Section_Number`

---

## 2. Policy Framework

### 2.1 Policy Levels

1. **Farm level:** Per-farm policies via `farms[i].policies.<domain>`.
2. **Collective farm override (default):** `collective_farm_override.policies` stamps uniform policies into all farms at setup time. If a farm also has a setting for the same domain, the collective override wins.
3. **Community level:** Non-farm operations (households, buildings) use limited water/energy policies via `household_policies`. Available: water `max_groundwater` or `max_municipal`; energy `microgrid`, `renewable_first`, or `all_grid`.

Crop plans (what to plant, when, how much area) are ALWAYS per-farm regardless of policy level — policies control decision logic, not crop selection.

→ structure.md § 2.11 for YAML schema and parameter wiring pipeline

### 2.2 Common Patterns

All policy domains share these conventions:

- **Lookup by name:** Policies referenced by name strings in YAML. Each domain has a factory function: `get_<domain>_policy(name, **kwargs)`.
- **Decision reasons:** Every output includes `decision_reason` string for debugging and analysis (diagnostic — not consumed by simulation loop).
- **Constraint clipping:** When a request exceeds physical capacity, it is clipped and the binding constraint is recorded.
- **Policy name field:** Every decision dataclass includes `policy_name: str` matching the registry key. Not listed in output tables below to avoid repetition.
- **Method names:**

| Domain | Method | Factory function |
|--------|--------|-----------------|
| Crop | `decide(ctx)` | `get_crop_policy(name)` |
| Water | `allocate_water(ctx)` | `get_water_policy(name)` |
| Energy | `allocate_energy(ctx)` | `get_energy_policy(name)` |
| Food (food processing) | `allocate(ctx)` | `get_food_policy(name)` |
| Market | `decide(ctx)` | `get_market_policy(name)` |

- **Configurable parameters:** Set at instantiation from scenario YAML, fixed for the run. Defaults noted in each policy.
- **Sigmoid function** (used by `adaptive` market policy):

```
sigmoid(x, min_val, max_val, k, midpoint) =
    min_val + (max_val - min_val) / (1 + exp(-k * (x - midpoint)))
```

### 2.3 Error Handling

- **Zero-demand:** Return allocation with zero quantities and `decision_reason = "zero_demand"`. Do not proceed to cost calculations.
- **NaN/negative inputs:** Raise `ValueError` immediately.
- **Division by zero:** Guard with zero-demand early return before any division.

### 2.4 Execution Order

Policies execute in this order each day:

0. **Setup** — Load weather, prices, crop stages; monthly/yearly resets
1. **Crop** — Adjust irrigation demand
2. **Water** — Allocate between groundwater and municipal
3. **Pre-harvest clearance** — Forced sales of expired inventory (FIFO)
4. **Food processing** — Split harvest across pathways (harvest days only)
5. **Sales/inventory** — (a) Overflow forced sales, (b) Market policy voluntary sales
6. **Energy dispatch** — Merit-order allocation; grid is infinite backstop
7. **Accounting** — Costs, revenue, cash update

→ simulation_flow.md § 3 for detailed step-by-step sequence

### 2.5 Operational Independence

Water and energy are operationally decoupled. Both have fallback sources (municipal water, grid electricity), so neither constrains the other. The coupling is **economic only**: energy price affects groundwater treatment cost, which affects water policy cost comparisons.

The simulation does not model grid failure or municipal supply interruption. Resilience metrics (self-sufficiency %) are descriptive proxies for vulnerability.

### 2.6 Dependencies

- Crop policies set adjusted irrigation demand → input to water policies
- Water and energy coupled only through energy price (affects groundwater cost)
- Forced sales depend on storage capacity and shelf life
- Market policies operate on inventory remaining after forced sales

---

## 3. Crop Policies

**Scope:** Irrigation adjustment strategy. Controls how much water is requested based on crop growth stage and weather. Called daily before water policy. Output (adjusted demand) becomes water demand input.

### Context (inputs)

| Field | Description |
|-------|-------------|
| `crop_name` | Name of crop |
| `growth_stage` | Current stage (CropStage enum) → structure.md § 2.10 |
| `days_since_planting` | Days since planting |
| `total_growing_days` | Total days in growing cycle |
| `base_demand_m3` | Standard irrigation demand from precomputed data (m3) |
| `temperature_c` | Ambient temperature (C) |
| `available_water_m3` | Water in storage at start of day (m3) |

### Decision (outputs)

| Field | Description |
|-------|-------------|
| `adjusted_demand_m3` | How much water to request (m3) |
| `demand_multiplier` | Multiplier applied to base demand (diagnostic) |
| `decision_reason` | Why this adjustment was made |

### `fixed_schedule`

Apply 100% of standard irrigation demand every day regardless of conditions.

```
multiplier = 1.0
adjusted_demand = base_demand_m3
reason = "Fixed schedule: full irrigation demand"
```

### `deficit_irrigation`

Full irrigation during establishment, reduced during mid and late season to conserve water.

**Parameters:**

- `deficit_fraction` (default 0.80) — fraction applied during mid-season

**Reduction schedule:**

| Stage | Multiplier |
|-------|-----------|
| Initial | 1.0 |
| Development | 1.0 |
| Mid-season | deficit_fraction (default 0.80) |
| Late-season | deficit_fraction * 0.9 (default 0.72) |

```
IF growth_stage == MID_SEASON:
    multiplier = deficit_fraction
ELSE IF growth_stage == LATE_SEASON:
    multiplier = deficit_fraction * 0.9
ELSE:
    multiplier = 1.0
adjusted_demand = base_demand_m3 * multiplier
```

### `weather_adaptive`

Temperature-responsive irrigation. Increases water on hot days, decreases on cool days.

| Condition | Multiplier |
|-----------|-----------|
| > 40C | 1.15 (+15%) |
| > 35C | 1.05 (+5%) |
| < 20C | 0.85 (-15%) |
| 20-35C | 1.0 |

```
IF temperature_c > 40:
    multiplier = 1.15
ELSE IF temperature_c > 35:
    multiplier = 1.05
ELSE IF temperature_c < 20:
    multiplier = 0.85
ELSE:
    multiplier = 1.0
adjusted_demand = base_demand_m3 * multiplier
```

---

## 4. Water Policies

**Scope:** Water source allocation. Splits demand between treated groundwater and purchased municipal water. Called daily. Typically set via collective override.

### Context (inputs)

| Field | Description |
|-------|-------------|
| `demand_m3` | Total water demand today (m3) |
| `treatment_kwh_per_m3` | Energy to desalinate 1 m3 groundwater |
| `pumping_kwh_per_m3` | Energy to pump 1 m3 from well |
| `conveyance_kwh_per_m3` | Energy to convey 1 m3 |
| `gw_maintenance_per_m3` | O&M cost per m3 GW treatment (USD) |
| `municipal_price_per_m3` | Current municipal price (USD/m3) |
| `energy_price_per_kwh` | Current energy price (USD/kWh) |
| `max_groundwater_m3` | Daily max GW extraction (well capacity / num_farms) |
| `max_treatment_m3` | Daily max treatment throughput (capacity / num_farms) |
| `cumulative_gw_year_m3` | GW used this year (for quota policy) |
| `cumulative_gw_month_m3` | GW used this month (for quota policy) |
| `current_month` | Current month 1-12 |
| `groundwater_tds_ppm` | Raw groundwater salinity (for min_water_quality) |
| `municipal_tds_ppm` | Municipal supply salinity (for min_water_quality) |

**Note:** `energy_price_per_kwh` is the current grid tariff, resolved upstream by consumer type (agricultural for farms, community for households).

→ simulation_flow.md § 5 for pricing resolution

### Decision (outputs)

| Field | Description |
|-------|-------------|
| `groundwater_m3` | Volume from treated groundwater |
| `municipal_m3` | Volume from municipal supply |
| `irrigation_delivered_m3` | Total water delivered = groundwater_m3 + municipal_m3 |
| `energy_used_kwh` | Energy for GW pumping + conveyance + treatment |
| `cost_usd` | Cash water cost (GW maintenance + municipal purchase; excludes energy) |
| `economic_cost_usd` | Full economic cost including energy (for comparison logging, NOT accounting) |
| `decision_reason` | Why this allocation was chosen |
| `constraint_hit` | `ConstraintHit.WELL_LIMIT`, `.TREATMENT_LIMIT`, or None (`.value` strings: `"well_limit"`, `"treatment_limit"`) |

### Shared Logic: Groundwater Cost

```
gw_cost_per_m3 = (pumping_kwh + conveyance_kwh + treatment_kwh) * energy_price + gw_maintenance
```

→ calculations_water.md § 1-3 for pumping, treatment, and conveyance formulas

### Shared Logic: Physical Constraint Check

All policies using groundwater clip to the minimum of:

1. `max_groundwater_m3` (well capacity)
2. `max_treatment_m3` (treatment throughput)

Shortfall is met with municipal. Binding constraint is recorded. Energy is always available (grid backstop), so it does not constrain treatment.

### Shared Logic: Energy and Cost

```
energy_used = groundwater_m3 * (pumping_kwh + conveyance_kwh + treatment_kwh)
economic_cost = (groundwater_m3 * gw_cost_per_m3) + (municipal_m3 * municipal_price)
cost_usd = (groundwater_m3 * gw_maintenance) + (municipal_m3 * municipal_price)
```

### `max_groundwater`

Maximize GW extraction up to physical limits. Municipal fallback when constrained.

```
Request all demand as groundwater
Apply constraint check → actual_gw, constraint_hit
municipal = demand - actual_gw
```

### `max_municipal`

100% municipal. GW only if municipal physically unavailable (not modeled, so functionally always 100% municipal).

```
groundwater = 0
municipal = demand
energy_used = 0
cost = municipal * municipal_price
```

### `min_water_quality`

Mix GW and municipal to achieve target salinity. Municipal is always highest quality. If GW constraints force a higher municipal fraction, quality improves above target.

**Parameters:**

- `target_tds_ppm` (e.g., 1500) — maximum acceptable mixed-water TDS

```
IF groundwater_tds <= target_tds:
    # GW clean enough, use preferentially
    Request all as groundwater, apply constraint check
    municipal = demand - actual_gw

ELSE:
    # Calculate mixing ratio for target TDS
    required_municipal_fraction = (gw_tds - target_tds) / (gw_tds - muni_tds)

    IF required_municipal_fraction >= 1.0:
        groundwater = 0, municipal = demand  # GW too salty

    ELSE:
        groundwater = demand * (1 - required_municipal_fraction)
        municipal = demand * required_municipal_fraction
        Apply constraint check on groundwater
        IF constrained: municipal = demand - actual_gw  # improves quality
```

**Mixed water quality (diagnostic):**

```
mixed_tds = (gw_m3 * gw_tds + muni_m3 * muni_tds) / (gw_m3 + muni_m3)
# Always <= target_tds because municipal is always cleaner
```

### `cheapest_source`

Daily cost comparison. Whichever is cheaper gets 100% (subject to constraints).

```
IF gw_cost_per_m3 < municipal_price:
    Request all as groundwater, apply constraint check
    municipal = demand - actual_gw
ELSE:
    groundwater = 0, municipal = demand
```

### `conserve_groundwater`

Prefer municipal to reduce groundwater extraction. Use GW only when municipal price exceeds a threshold.

**Parameters:**

- `price_threshold_multiplier` (default 1.5)
- `max_gw_ratio` (default 0.30) — max fraction of demand from GW

```
threshold = gw_cost_per_m3 * price_threshold_multiplier

IF municipal_price > threshold:
    requested_gw = demand * max_gw_ratio
    Apply constraint check → actual_gw, constraint_hit
    municipal = demand - actual_gw
    limiting_factor = constraint_hit or "ratio_cap"
ELSE:
    groundwater = 0, municipal = demand
    limiting_factor = None
```

**Note:** `limiting_factor` is a superset of `constraint_hit` — it includes both infrastructure constraints AND the policy's own ratio cap. When `limiting_factor = "ratio_cap"`, the allocation was limited by the conservation policy, not by physical infrastructure.

### `quota_enforced`

Hard annual GW limit with monthly variance controls. 100% municipal when quota exhausted.

**Parameters:**

- `annual_quota_m3` — max yearly extraction per farm
- `monthly_variance_pct` (default 0.15) — allowed deviation from equal monthly share

```
remaining_annual = MAX(0, annual_quota - cumulative_gw_year)
monthly_max = (annual_quota / 12) * (1 + monthly_variance_pct)
remaining_monthly = MAX(0, monthly_max - cumulative_gw_month)
quota_limit = MIN(remaining_annual, remaining_monthly)

IF remaining_annual <= 0:
    groundwater = 0, municipal = demand, reason = "quota_exhausted"
ELSE IF remaining_monthly <= 0:
    groundwater = 0, municipal = demand, reason = "quota_monthly_limit"
ELSE:
    requested = MIN(demand, quota_limit)
    Apply constraint check → actual_gw, constraint_hit
    municipal = demand - actual_gw
```

---

## 5. Energy Policies

**Scope:** Energy dispatch strategy. Returns flags that parameterize the dispatch function. The dispatch function (not the policy) performs kWh-by-kWh allocation. Called daily.

→ calculations_energy.md § 5 for the dispatch algorithm

### Context (inputs)

| Field | Description |
|-------|-------------|
| `total_demand_kwh` | Total energy demand today |
| `pv_available_kwh` | PV generation available today |
| `wind_available_kwh` | Wind generation available today |
| `battery_soc` | Current battery SOC (0-1) |
| `battery_capacity_kwh` | Total battery capacity |
| `grid_price_per_kwh` | Current grid price (USD/kWh) |
| `diesel_price_per_L` | Current diesel price (USD/L) |
| `generator_capacity_kw` | Generator nameplate capacity |

### Decision (outputs)

| Field | Description |
|-------|-------------|
| `use_renewables` | Use PV/wind for self-consumption (bool) |
| `use_battery` | Use battery for charge/discharge (bool) |
| `grid_import` | Import from grid when needed (bool) |
| `grid_export` | Export surplus to grid (bool) |
| `use_generator` | Backup generator available (bool) |
| `sell_renewables_to_grid` | Route all renewables to export (bool) |
| `battery_reserve_pct` | Minimum battery SOC to maintain (0-1) |
| `decision_reason` | Dispatch strategy explanation |

`battery_reserve_pct` note: Effective floor = `max(SOC_min_hardware, battery_reserve_pct)`. Cannot override hardware SOC_min.

### `microgrid`

No grid connection. Renewable → battery → generator. Unmet demand is recorded.

**Merit order:** PV → Wind → Battery → Generator

```
use_renewables = true, use_battery = true
grid_import = false, grid_export = false
use_generator = true, sell_renewables_to_grid = false
battery_reserve_pct = 0.20
```

**Dispatch behavior:**

1. PV → demand
2. Wind → remaining demand
3. Battery charge from surplus; discharge for remaining (down to reserve)
4. Generator for remaining shortfall
5. Unmet demand recorded if generator insufficient

### `renewable_first`

Prioritize renewables with battery, then grid. Generator not dispatched.

**Merit order:** PV → Wind → Battery → Grid

```
use_renewables = true, use_battery = true
grid_import = true, grid_export = true
use_generator = false, sell_renewables_to_grid = false
battery_reserve_pct = 0.20
```

**Dispatch behavior:**

1. PV → demand
2. Wind → remaining demand
3. Battery charge from surplus; discharge for remaining
4. Grid import for remaining shortfall
5. Export surplus renewable generation to grid

### `all_grid`

All demand from grid. Renewables net-metered to grid.

```
use_renewables = false, use_battery = false
grid_import = true, grid_export = true
use_generator = false, sell_renewables_to_grid = true
battery_reserve_pct = 0.0
```

**Dispatch behavior:**

1. Import all demand from grid
2. Export all PV/wind generation (net metering revenue)
3. Battery not used

---

## 6. Food Processing Policies

**Scope:** Determines how harvested crop is split across four pathways: fresh, packaged, canned, dried. Operates on the pooled community harvest. Processing throughput is unlimited (no capacity clipping); the only physical constraint is storage capacity. Called on harvest days only.

→ simulation_flow.md § 3 (Step 4) for harvest pooling and tranche creation
→ structure.md § 2.5 for equipment, weight loss, and storage capacity

### Context (inputs)

| Field | Description |
|-------|-------------|
| `harvest_available_kg` | Post-handling-loss quantity entering the food policy (kg) |
| `crop_name` | Name of crop |
| `fresh_price_per_kg` | Current fresh farmgate price (USD/kg) |

### Decision (outputs)

| Field | Description |
|-------|-------------|
| `fresh_fraction` | Fraction as fresh produce (0-1) |
| `packaged_fraction` | Fraction to packaging (0-1) |
| `canned_fraction` | Fraction to canning (0-1) |
| `dried_fraction` | Fraction to drying (0-1) |
| `decision_reason` | Why this split was chosen |

**Constraint:** Fractions must sum to 1.0.

### `all_fresh`

100% fresh. No processing.

| Fresh | Packaged | Canned | Dried |
|-------|----------|--------|-------|
| 100% | 0% | 0% | 0% |

### `maximize_storage`

Maximize shelf-stable products. Only 20% goes fresh.

| Fresh | Packaged | Canned | Dried |
|-------|----------|--------|-------|
| 20% | 10% | 35% | 35% |

### `balanced_mix`

Half fresh, half processed.

| Fresh | Packaged | Canned | Dried |
|-------|----------|--------|-------|
| 50% | 20% | 15% | 15% |

### `market_responsive`

Binary switch based on current fresh price vs reference farmgate price.

**Parameters:**

- `price_threshold` (default 0.80) — fraction of reference price that triggers low-price split

```
reference_price = MEAN(all prices in crop's fresh price time series)

IF fresh_price < reference_price * price_threshold:
    Fresh=30%, Packaged=20%, Canned=25%, Dried=25%
ELSE:
    Fresh=65%, Packaged=15%, Canned=10%, Dried=10%
```

| Condition | Fresh | Packaged | Canned | Dried |
|-----------|-------|----------|--------|-------|
| Price < threshold * reference | 30% | 20% | 25% | 25% |
| Price >= threshold * reference | 65% | 15% | 10% | 10% |

---

## 7. Forced Sales

**Scope:** Simulation loop mechanics, NOT a configurable policy. No factory function or YAML selection. Runs unconditionally at two points in the daily loop regardless of which food or market policy is active.

→ simulation_flow.md § 3 (Steps 3 and 5a) for execution timing

### Triggers

1. **Storage-life expiry:** Tranche at or past `shelf_life_days` must be sold immediately. Shelf life from `storage_spoilage_rates-toy.csv`.
2. **Storage overflow:** Total stored exceeds physical capacity. Sell oldest first (FIFO) until storage fits.

### Execution Timing

- **Step 3 (pre-harvest):** Sell all expired tranches (FIFO) before new harvest enters storage.
- **Step 5a (post-harvest):** After food processing adds new inventory, sell oldest (FIFO) until storage fits capacity.
- **Step 5b:** Market policy runs on remaining inventory after forced sales.

### FIFO Sell Order

```
# Step 3: Expiry clearance
FOR each tranche in community_storage (oldest first):
    IF current_date >= tranche.expiry_date:
        sell entire tranche at current market price
        reason = "storage_life_expired"

# Step 5a: Overflow clearance (runs per product_type)
IF total_stored_kg[product_type] > storage_capacities_kg[product_type]:
    excess_kg = total_stored_kg[product_type] - storage_capacities_kg[product_type]
    FOR each tranche of this product_type (oldest first):
        IF excess_kg <= 0: BREAK
        IF tranche.kg <= excess_kg:
            sell entire tranche; excess_kg -= tranche.kg
        ELSE:
            sell partial tranche (excess_kg); tranche.kg -= excess_kg; excess_kg = 0
        reason = "storage_overflow"
```

### Revenue Attribution

Forced sale revenue follows the same attribution as voluntary sales — via `farm_shares` on each tranche.

→ simulation_flow.md § 6.2 for farm_shares attribution algorithm

### Pricing

Forced sales execute at current market price. No discount. The product is still within its usable window. Price is the daily resolved value from Step 0 — fresh product uses the crop price CSV; processed products use the processed price CSV.

→ simulation_flow.md § 5 for price resolution by product_type

---

## 8. Market Policies

**Scope:** When to sell processed food. Operates on pooled community inventory. The community sells as a bloc. Called daily on remaining inventory after forced sales (Step 5b).

**Separation of concerns:** Food processing policies determine HOW food is processed. Market policies determine WHEN it is sold. Forced sales (Section 7) take priority.

### Context (inputs)

| Field | Description |
|-------|-------------|
| `crop_name` | Crop being considered |
| `product_type` | "fresh", "packaged", "canned", or "dried" |
| `available_kg` | Total kg of this crop+product_type in storage |
| `current_price_per_kg` | Today's market price (USD/kg) |
| `avg_price_per_kg` | Rolling 12-month mean from price data files (not runtime sales) |
| `storage_capacity_kg` | REMAINING capacity (total_capacity - current_stored) for this product_type; computed before calling policy |

### Decision (outputs)

| Field | Description |
|-------|-------------|
| `sell_fraction` | Fraction to sell now (0-1) |
| `store_fraction` | Fraction to keep (0-1) |
| `target_price_per_kg` | Minimum acceptable price; 0 = any price (diagnostic) |
| `decision_reason` | Why this decision was made |

**Constraint:** sell_fraction + store_fraction = 1.0

### Shared Logic: Tranche Selection

Voluntary sales follow FIFO order. The `decide()` method returns `sell_fraction`; the simulation loop (Step 5b) executes the FIFO tranche iteration that reduces `tranche.kg` and attributes revenue via `farm_shares`.

→ simulation_flow.md § 3 (Step 5b) for the FIFO sell loop

### `sell_all_immediately`

Sell everything as soon as it is processed. Minimal storage needed.

```
sell_fraction = 1.0, store_fraction = 0.0
target_price = 0
reason = "sell_immediately"
```

### `hold_for_peak`

Store until prices rise above a threshold relative to average.

**Parameters:**

- `price_threshold_multiplier` (default 1.2) — sell when price >= avg * this value

```
target_price = avg_price * price_threshold_multiplier

IF current_price >= target_price:
    sell_fraction = 1.0, reason = "price_above_threshold"
ELSE IF storage_capacity_kg >= available_kg:
    sell_fraction = 0.0, reason = "holding_for_peak"
ELSE IF storage_capacity_kg > 0:
    store_fraction = storage_capacity_kg / available_kg
    sell_fraction = 1.0 - store_fraction, reason = "holding_partial_storage_full"
ELSE:
    sell_fraction = 1.0, reason = "no_storage_capacity"
```

### `adaptive`

Sigmoid maps price ratio to sell fraction. Sell more when prices are high, store more when low.

**Parameters:**

- `midpoint` (default 1.0) — price ratio at sigmoid midpoint
- `steepness` (default 5.0) — transition sharpness
- `min_sell` (default 0.2) — minimum sell fraction
- `max_sell` (default 1.0) — maximum sell fraction

```
price_ratio = current_price / avg_price
sell_fraction = sigmoid(price_ratio, min_sell, max_sell, steepness, midpoint)
store_fraction = 1.0 - sell_fraction

# Clip to available storage
IF store_fraction * available_kg > storage_capacity_kg AND storage_capacity_kg > 0:
    store_fraction = storage_capacity_kg / available_kg
    sell_fraction = 1.0 - store_fraction
ELSE IF storage_capacity_kg <= 0:
    sell_fraction = 1.0, store_fraction = 0.0
```

---

## 9. Economic Policies — DEFERRED

**Not used in the current simulation version.** Economic policies (`balanced_finance`, `aggressive_growth`, `conservative`, `risk_averse`) are not called during the daily loop. Cash flows are tracked without intervention — if cash goes negative, no penalty is taken.

| Policy | Reserve Target | Intended Behavior |
|--------|---------------|-------------------|
| `balanced_finance` | 3 months | Sell inventory if < 1 month reserves |
| `aggressive_growth` | 1 month | Minimize reserves, sell immediately |
| `conservative` | 6 months | Maintain high safety buffer, hold |
| `risk_averse` | 6+ months | Maximize reserves, sell to lock in revenue |

---

## 10. How to Add a New Policy

### Step 1: Check context/decision compatibility

Verify the existing context and decision dataclasses cover your policy's needs. All policies in a domain share the same context and decision types.

- New context field → add to dataclass, update simulation loop to populate it
- New output field → add to dataclass with sensible default (e.g., `None`)

### Step 2: Implement the policy class

Inherit from the domain's base class, implement the canonical method:

| Domain | Base Class | Method |
|--------|-----------|--------|
| Crop | `BaseCropPolicy` | `decide(ctx) → CropDecision` |
| Water | `BaseWaterPolicy` | `allocate_water(ctx) → WaterAllocation` |
| Energy | `BaseEnergyPolicy` | `allocate_energy(ctx) → EnergyAllocation` |
| Food | `BaseFoodPolicy` | `allocate(ctx) → ProcessingAllocation` |
| Market | `BaseMarketPolicy` | `decide(ctx) → MarketDecision` |

Constructor accepts `**kwargs` with defaults. Follow error handling conventions (Section 2.3).

### Step 3: Register in factory function

Add policy name and class to the dictionary in `get_<domain>_policy()`.

### Step 4: Add YAML parameters (if configurable)

```yaml
community_policy_parameters:
  my_new_policy:
    my_threshold: 0.5
```

→ structure.md § 2.11 for parameter wiring pipeline

### Step 5: Document the policy

Add a subsection to the appropriate domain section in this file: heading, description, parameters table, pseudocode, decision reasons.

### Step 6: Update validation

Add the new policy name to valid options in `validation.py`.

### Checklist

- [ ] Context/decision dataclass covers needs (or extended)
- [ ] Policy class inherits from base class
- [ ] Constructor accepts kwargs with defaults
- [ ] Factory function dictionary updated
- [ ] YAML `community_policy_parameters` entry (if configurable)
- [ ] Documented in this file
- [ ] Validation updated

---

## 11. Deferred Policy Domains

The following are described in `overview.md` but not specified for implementation:

**Insurance policies:** Crop and equipment insurance as risk management alternatives. Six design questions remain (payout triggers, deductibles, participation model, provider, interaction with pooling, claims timing).

**Collective pooling mechanism:** Reserve fund from farm profits with hardship distribution. Three open questions (advance determination, unrecovered advances, cost allocation beyond `cost_allocation_method`).

**Working capital advances:** Operating advances recouped at sale. Open questions on advance method, recovery, and interaction with pooling. Current model uses `starting_capital_usd` and daily cash tracking as a simplified mechanism.

---

*End of specification.*
