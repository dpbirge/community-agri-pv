# Policy Specifications

## 1. Overview

This document specifies the decision logic for all 23 simulation policies across 6 domains. Each policy is fully defined in plain English and pseudocode. The translation from this specification to code is left to the implementer.

**Policy scope:** Policies operate at three distinct levels:
- **Farm-level** (default): Each farm selects its own policy for each domain (water, energy, crop, food processing, market, economic)
- **Community-override** (optional): If all farms agree, a universal community policy can override individual farm selections
- **Household and shared facilities**: Non-farm operations (residential households and community buildings) use water and energy policies for their operational needs only. These apply only to water and energy demands, not to crop production or food processing. Available household policies are limited to: water policy `max_groundwater` or `max_municipal`; energy policy `microgrid`, `renewable_first`, or `all_grid`. Configured in the scenario YAML under `household_policies`.

For configuration schemas and parameter definitions, see `structure.md`. For calculation formulas, see `calculations.md`.

### How to read this document

Each policy domain (water, food processing, market, energy, crop, economic) follows the same structure:

1. **Context (inputs)** — Named fields the simulation passes to the policy each time it is called. The simulation assembles these from current state.

2. **Decision (outputs)** — Named fields the policy returns. The simulation applies these to update state.

3. **Policy logic** — Plain English description followed by pseudocode for each policy. Pseudocode uses `ctx` to reference context fields (e.g., `ctx.demand_m3`).

### Common patterns

All policy domains share these structural conventions:

- **Lookup by name**: Policies are referenced by name strings in scenario YAML files (e.g., `water_policy: cheapest_source`). Each domain provides a factory function that takes a name string and returns the corresponding policy.

- **Policy name**: Every policy output includes a `policy_name: str` field identifying which policy produced the decision (e.g., `"cheapest_source"`, `"hold_for_peak"`). This enables unambiguous attribution when analyzing results across farms with different policy selections.

- **Decision reasons**: Every policy returns a `decision_reason` string explaining why the decision was made (e.g., `"gw_cheaper"`, `"quota_exhausted"`). These enable filtering and grouping in analysis and debugging.

- **Constraint clipping**: When a policy requests more of a resource than is physically available, the request is clipped to the physical limit and the shortfall is met from an alternative source. The binding constraint is recorded in the decision.

- **Configurable parameters**: Some policies accept tuning parameters (e.g., threshold multipliers, reserve targets). Parameters are set at instantiation from the scenario YAML and remain fixed for the run. Defaults are noted in each policy description.

- **Sigmoid function**: Policies that map a continuous input to a bounded output range (e.g., `adaptive` market policy) use a shared sigmoid definition:

  ```
  sigmoid(x, min_val, max_val, k, midpoint) = min_val + (max_val - min_val) / (1 + exp(-k * (x - midpoint)))
  ```

  Where `x` is the input value, `min_val` and `max_val` bound the output range, `k` controls steepness (higher = sharper transition), and `midpoint` is the input value where the output is halfway between min_val and max_val.

### Error handling

All policies follow these conventions for invalid or degenerate inputs:

- **Zero-demand inputs**: When demand is zero (e.g., `demand_m3 = 0`, `harvest_yield_kg = 0`), return an allocation with zero quantities and `decision_reason = "zero_demand"`. Do not proceed to cost calculations or constraint checks.
- **NaN/negative inputs**: Raise `ValueError` immediately. Policies must fail explicitly on malformed inputs rather than silently producing incorrect results.
- **Division by zero**: Guard with a zero-demand early return before any division. For example, check `available_kg > 0` before computing `store_fraction = storage_capacity_kg / available_kg`.

### Execution order

Policies execute in this order each simulation day:

1. **Crop** — Adjusts irrigation water demand based on crop stage and weather
2. **Water** — Allocates water between groundwater and municipal sources
3. **Energy** — Sets dispatch strategy for energy sources
4. **Food processing** — Splits harvest across processing pathways and updates total storage (runs only on harvest days; skipped when no harvest occurs)
4b. **Forced sales** — After storage is updated, checks all tranches for expiry and overflow; forced sales execute here before market policy runs
5. **Market** — Determines when to sell or store remaining inventory (forced sales have already occurred, so market policy operates freely)
6. **Economic** — Sets reserve targets and inventory decisions (monthly or at year boundaries)

### Operational independence

Water and energy systems are operationally decoupled. There is always a fallback source for both water (municipal) and energy (grid), so neither system can physically constrain the other. A farm can always get water and always get energy — the question is what it costs.

The coupling between systems is **economic only**: the energy price affects the cost of groundwater treatment, which affects water policy cost comparisons. But energy availability never limits water allocation, and water demand never limits energy dispatch.

Resilience metrics (energy self-sufficiency %, water self-sufficiency %) are descriptive — they measure how dependent the community is on external sources as a proxy for vulnerability, but the simulation does not model grid failure or municipal supply interruption.

### Dependencies

- Food processing policies depend on infrastructure capacity (equipment types and throughput from system configuration)
- Market policies depend on storage capacity and product shelf life
- Economic policies depend on revenue (from crop sales) and costs (from all other systems)
- Water and energy policies are coupled only through energy price (affects groundwater cost calculation)

---

## 2. Water Policies

**Scope:** Each farm selects a water source allocation strategy (unless overridden by community policy). Household and shared facility operations also apply water policies to their non-farm water needs. The policy is called daily to split water demand between treated groundwater and purchased municipal water.

### Context (inputs)

| Field | Description |
|---|---|
| `demand_m3` | Total water demand today (m3) |
| `treatment_kwh_per_m3` | Energy to desalinate 1 m3 of groundwater |
| `pumping_kwh_per_m3` | Energy to pump 1 m3 from well to surface |
| `conveyance_kwh_per_m3` | Energy to convey 1 m3 from well/treatment to farm |
| `gw_maintenance_per_m3` | O&M cost per m3 of groundwater treatment (USD) |
| `municipal_price_per_m3` | Current municipal water price (USD/m3) |
| `energy_price_per_kwh` | Current energy price (USD/kWh) |
| `max_groundwater_m3` | Maximum daily groundwater extraction (well capacity / num_farms) |
| `max_treatment_m3` | Maximum daily treatment throughput (treatment capacity / num_farms) |
| `cumulative_gw_year_m3` | Groundwater used so far this year (for quota policy) |
| `cumulative_gw_month_m3` | Groundwater used so far this month (for quota policy) |
| `current_month` | Current month 1-12 (for quota policy) |
| `groundwater_tds_ppm` | Current measured salinity of available groundwater (for min_water_quality policy) |
| `municipal_tds_ppm` | Salinity of municipal water supply (for min_water_quality policy) |

**Note on `energy_price_per_kwh`:** The water policy executes before the energy policy (step 2 vs step 3 in the daily execution order). The energy price used here is the current grid tariff from pricing configuration — it represents the marginal cost of the next kWh regardless of dispatch strategy. This is consistent with the operational independence principle: energy availability never constrains water, but the grid tariff affects groundwater cost comparisons.

**Note on `municipal_price_per_m3`:** The simulation resolves the applicable price upstream based on consumer type (agricultural or domestic) before passing it to the policy. Farm water demands use the agricultural pricing regime; household/shared facility demands use the domestic pricing regime. See pricing configuration in `structure.md`.

### Decision (outputs)

| Field | Description |
|---|---|
| `groundwater_m3` | Volume allocated from treated groundwater |
| `municipal_m3` | Volume allocated from municipal supply |
| `energy_used_kwh` | Energy consumed for groundwater pumping + conveyance + treatment |
| `cost_usd` | Total water cost this day |
| `decision_reason` | Why this allocation was chosen |
| `constraint_hit` | Which physical constraint limited groundwater: `"well_limit"`, `"treatment_limit"`, or None |

### Shared logic: groundwater cost

All policies that compare groundwater vs municipal cost use the same formula:

```
gw_cost_per_m3 = (pumping_kwh_per_m3 + conveyance_kwh_per_m3 + treatment_kwh_per_m3)
                 * energy_price_per_kwh
                 + gw_maintenance_per_m3
```

### Shared logic: physical constraint check

All policies that use groundwater clip the requested volume to the minimum of two physical limits:

1. **Well capacity**: `max_groundwater_m3` (daily extraction rate shared across farms)
2. **Treatment throughput**: `max_treatment_m3` (daily desalination capacity shared across farms)

Energy is always available from some source (renewables, grid, generator) so it does not constrain water treatment. If either physical limit reduces the allocation below what was requested, the shortfall is met with municipal water and the binding constraint is recorded.

### Shared logic: energy consumed and total cost

```
energy_used = groundwater_m3 * (pumping_kwh_per_m3 + conveyance_kwh_per_m3 + treatment_kwh_per_m3)
cost_usd    = (groundwater_m3 * gw_cost_per_m3) + (municipal_m3 * municipal_price_per_m3)
```

### 2.1 `max_groundwater`

Maximize groundwater extraction up to physical limits (well capacity, treatment throughput, water storage buffer). Municipal water is used as fallback when groundwater is physically constrained. This policy does not enforce quotas — use `quota_enforced` for hard extraction limits.

```
Request all demand as groundwater
Apply constraint check -> actual_gw, constraint_hit
municipal = demand - actual_gw

IF constraint_hit:
    reason = "gw_preferred_but_{constraint}"
ELSE IF municipal > 0:
    reason = "gw_preferred_partial"
ELSE:
    reason = "gw_preferred"
```

### 2.2 `max_municipal`

Maximize municipal water. All demand is met from municipal supply. Groundwater is used only if municipal water is physically unavailable (the simulation currently does not model municipal supply interruption, so this policy is functionally 100% municipal).

```
groundwater = 0
municipal = demand
energy_used = 0
cost = municipal * municipal_price_per_m3
reason = "muni_preferred"
```

### 2.3 `min_water_quality`

Mixes groundwater and municipal water to achieve a target water quality (salinity/TDS) that all crops can tolerate. Municipal water is always the highest quality source. If groundwater constraints force a higher municipal fraction than the mixing formula requires, water quality improves (never degrades).

**Parameters:**
- `target_tds_ppm` (e.g., 1500) — maximum acceptable salinity/TDS for the mixed water that all crops can handle (set at policy instantiation from scenario YAML)

**Decision logic:**

First, calculate the required mixing ratio to achieve target TDS. Then, check if enough groundwater is available. If not, the municipal fraction increases and water quality improves above target.

```
IF groundwater_tds_ppm <= target_tds_ppm:
    // Groundwater is clean enough; use it preferentially
    Request all demand as groundwater
    Apply constraint check -> actual_gw, constraint_hit
    municipal = demand - actual_gw
    IF constraint_hit:
        reason = "groundwater_meets_quality_but_{constraint}"
    ELSE:
        reason = "groundwater_meets_quality"

ELSE:
    // Calculate mixing ratio to achieve target salinity
    required_municipal_fraction = (groundwater_tds_ppm - target_tds_ppm)
                                  / (groundwater_tds_ppm - municipal_tds_ppm)

    IF required_municipal_fraction >= 1.0:
        // Groundwater too salty even with maximum mixing; use 100% municipal
        groundwater_m3 = 0
        municipal_m3 = demand
        reason = "groundwater_too_salty_using_municipal"

    ELSE:
        // Blend to achieve target
        groundwater_m3 = demand * (1.0 - required_municipal_fraction)
        municipal_m3 = demand * required_municipal_fraction

        Apply constraint check on groundwater_m3 -> actual_gw, constraint_hit

        IF constraint_hit:
            // Can't get enough groundwater; increase municipal fraction
            // This IMPROVES quality above target (municipal is always cleaner)
            municipal_m3 = demand - actual_gw
            reason = "quality_mixing_but_{constraint}"
        ELSE:
            reason = "quality_mixing_achieved"

energy_used = groundwater_m3 * (pumping_kwh_per_m3 + treatment_kwh_per_m3 + conveyance_kwh_per_m3)
cost_usd = (groundwater_m3 * gw_cost_per_m3) + (municipal_m3 * municipal_price_per_m3)
```

**Resulting water quality after mixing:**

```
mixed_tds_ppm = (groundwater_m3 * groundwater_tds_ppm + municipal_m3 * municipal_tds_ppm)
                / (groundwater_m3 + municipal_m3)
// Note: mixed_tds_ppm will always be <= target_tds_ppm because municipal is always cleaner
```

---

### 2.4 `cheapest_source`

Daily cost comparison between groundwater and municipal. Whichever is cheaper gets 100% of demand (subject to physical constraints).

```
Calculate gw_cost_per_m3
muni_cost_per_m3 = ctx.municipal_price_per_m3

IF gw_cost_per_m3 < muni_cost_per_m3:
    Request all demand as groundwater
    Apply constraint check -> actual_gw, constraint_hit
    municipal = demand - actual_gw
    IF constraint_hit:
        reason = "gw_cheaper_but_{constraint}"
    ELSE:
        reason = "gw_cheaper"
ELSE:
    groundwater = 0
    municipal = demand
    reason = "muni_cheaper"
```

### 2.5 `conserve_groundwater`

Prefer municipal to conserve the aquifer. Switch to groundwater only when the municipal price exceeds a configurable threshold relative to groundwater cost. Even then, limit groundwater to a fraction of demand.

**Parameters:**
- `price_threshold_multiplier` (default 1.5) — municipal price must exceed gw_cost_per_m3 * this value to trigger groundwater use
- `max_gw_ratio` (default 0.30) — maximum fraction of demand from groundwater

```
Calculate gw_cost_per_m3
muni_cost_per_m3 = ctx.municipal_price_per_m3
threshold = gw_cost_per_m3 * price_threshold_multiplier

IF muni_cost_per_m3 > threshold:
    requested_gw = demand * max_gw_ratio
    Apply constraint check on requested_gw -> actual_gw, constraint_hit
    municipal = demand - actual_gw

    // Track what actually limited the groundwater allocation
    IF constraint_hit:
        limiting_factor = constraint_hit  // "well_limit" or "treatment_limit"
        reason = "threshold_exceeded_but_{constraint}"
    ELSE:
        limiting_factor = "ratio_cap"
        reason = "threshold_exceeded"
ELSE:
    groundwater = 0
    municipal = demand
    limiting_factor = None
    reason = "threshold_not_met"
```

**Note on `limiting_factor` vs `constraint_hit`:** All water policies return `constraint_hit` (shared output field, values: `"well_limit"`, `"treatment_limit"`, or None) which records only infrastructure constraints. The `conserve_groundwater` policy additionally returns `limiting_factor` (values: `"ratio_cap"`, `"well_limit"`, `"treatment_limit"`, or None), which is a superset of `constraint_hit` — it includes both the shared infrastructure constraint values AND the policy's own ratio cap. When `limiting_factor = "ratio_cap"`, the allocation was limited by the conservation policy's `max_gw_ratio` parameter, not by physical infrastructure. When `limiting_factor` matches an infrastructure constraint, it mirrors `constraint_hit`. This enables analysis of whether a farm is conservation-limited or infrastructure-limited.

### 2.6 `quota_enforced`

Hard annual groundwater limit with monthly variance controls. When the annual quota is exhausted, forces 100% municipal for the remainder of the year. Monthly controls prevent front-loading extraction.

**Parameters:**
- `annual_quota_m3` — maximum groundwater extraction per year
- `monthly_variance_pct` (default 0.15) — allowed deviation from equal monthly distribution (15% means the monthly cap is 115% of one-twelfth of the annual quota)

```
remaining_annual = MAX(0, annual_quota - cumulative_gw_year)
monthly_target = annual_quota / 12
monthly_max = monthly_target * (1 + monthly_variance_pct)
remaining_monthly = MAX(0, monthly_max - cumulative_gw_month)
quota_limit = MIN(remaining_annual, remaining_monthly)

IF remaining_annual <= 0:
    groundwater = 0, municipal = demand
    reason = "quota_exhausted"

ELSE IF remaining_monthly <= 0:
    groundwater = 0, municipal = demand
    reason = "quota_monthly_limit"

ELSE:
    requested = MIN(demand, quota_limit)
    Apply constraint check -> actual_gw, constraint_hit
    municipal = demand - actual_gw

    IF constraint_hit:
        reason = "quota_available_but_{constraint}"
    ELSE IF actual_gw < demand AND actual_gw >= quota_limit:
        reason = "quota_available_partial"
    ELSE:
        reason = "quota_available"
```

---

## 3. Food Processing Policies

**Scope:** Farm-level only. Each farm selects a food processing strategy that determines how harvested crop is split across four processing pathways: fresh, packaged, canned, and dried. Community-override policies are supported—if set, all farms adopt that policy. Called during harvest processing in the simulation loop. Policy behavior is always applied at the farm level.

### Umbrella rule: forced sale and FIFO tracking

This rule applies to ALL food processing policies and overrides normal storage behavior. It executes after food processing updates total storage for the day (step 4b in execution order), before the market policy runs (step 5).

1. **Tranche tracking**: Each harvest batch is tracked as a discrete unit (tranche) with an entry date and product type. This enables first-in, first-out (FIFO) ordering.

2. **Storage-life expiry**: When any tranche reaches its storage life limit, it must be sold immediately regardless of market conditions or policy preferences. Storage life data is sourced from `data/parameters/crops/spoilage_rates-toy.csv` (per crop, per product type). CSV schema: `crop_name, product_type, shelf_life_days`.

3. **Storage overflow**: When storage is full and new production needs space, sell the oldest tranche first, then the next oldest, until enough space is freed. This ensures proper FIFO inventory management.

4. **Execution timing**: After food processing allocates today's harvest and updates storage totals, the umbrella rule checks all tranches for expiry and overflow. Forced sales execute immediately. Then the market policy runs on remaining inventory without forced-sale constraints.

### Context (inputs)

| Field | Description |
|---|---|
| `harvest_yield_kg` | Total harvest yield before processing (kg) |
| `crop_name` | Name of crop being processed |
| `fresh_price_per_kg` | Current fresh farmgate price (USD/kg) |
| `drying_capacity_kg` | Daily drying capacity (kg); infinite if unconstrained |
| `canning_capacity_kg` | Daily canning capacity (kg); infinite if unconstrained |
| `packaging_capacity_kg` | Daily packaging capacity (kg); infinite if unconstrained |

### Decision (outputs)

| Field | Description |
|---|---|
| `fresh_fraction` | Fraction sold as fresh produce (0-1) |
| `packaged_fraction` | Fraction sent to packaging (0-1) |
| `canned_fraction` | Fraction sent to canning (0-1) |
| `dried_fraction` | Fraction sent to drying (0-1) |
| `decision_reason` | Why this split was chosen |

**Constraint:** Fractions must sum to 1.0.

### Shared logic: capacity clipping

All food processing policies apply capacity clipping after computing their target fractions. If the allocated kg for any pathway exceeds its daily capacity, the excess is redistributed to fresh. Fresh is explicitly excluded from capacity clipping — it has no practical capacity limit (requires only washing/sorting) and serves as the overflow sink for all capacity-constrained pathways:

```
// Fresh is never clipped — it absorbs all excess from constrained pathways
FOR each pathway in [packaged, canned, dried]:
    allocated_kg = harvest_yield_kg * pathway_fraction
    IF allocated_kg > pathway_capacity_kg:
        excess_kg = allocated_kg - pathway_capacity_kg
        pathway_fraction = pathway_capacity_kg / harvest_yield_kg
        fresh_fraction += excess_kg / harvest_yield_kg
        constraint_hit = true
```

If capacity clipping occurs, `decision_reason` is appended with `"_capacity_clipped"`.

### 3.1 `all_fresh`

Sell 100% of harvest as fresh produce. No processing.

| Fresh | Packaged | Canned | Dried |
|---|---|---|---|
| 100% | 0% | 0% | 0% |

### 3.2 `maximize_storage`

Maximize storage duration by processing most of the harvest into shelf-stable products. Only 20% goes to fresh sale (shortest storage life).

| Fresh | Packaged | Canned | Dried |
|---|---|---|---|
| 20% | 10% | 35% | 35% |

### 3.3 `balanced`

Moderate mix. Half the harvest sold fresh, half processed across three pathways.

| Fresh | Packaged | Canned | Dried |
|---|---|---|---|
| 50% | 20% | 15% | 15% |

### 3.4 `market_responsive`

Adjusts processing mix based on current fresh prices relative to reference farmgate prices. When fresh prices are low, shifts harvest into processing (value-add pathways). When fresh prices are normal or high, sells more fresh.

**Trigger:** Fresh price falls below 80% of the crop's reference farmgate price.

**Reference farmgate prices** are loaded from crop price data files in `data/prices/crops/`. Example values (USD/kg) for illustration only — actual values come from data files:
- tomato: ~0.30
- potato: ~0.25
- onion: ~0.20
- kale: ~0.40
- cucumber: ~0.35

```
reference_price = lookup crop reference price from data file

IF fresh_price_per_kg < reference_price * 0.80:
    // Low prices: shift toward processing
    Fresh=30%, Packaged=20%, Canned=25%, Dried=25%
ELSE:
    // Normal/high prices: sell more fresh
    Fresh=65%, Packaged=15%, Canned=10%, Dried=10%
```

| Condition | Fresh | Packaged | Canned | Dried |
|---|---|---|---|---|
| Price < 80% of reference | 30% | 20% | 25% | 25% |
| Price >= 80% of reference | 65% | 15% | 10% | 10% |

---

## 4. Market Policies (Selling)

**Scope:** Farm-level only. Each farm selects a sales policy that determines when processed food is sold. Community-override policies are supported.

**Separation of concerns:** Food processing policies entirely determine HOW food is processed (the fresh/packaged/canned/dried split). Market policies entirely determine WHEN food is sold. The only exception is forced sales from the food processing umbrella rule (storage full or storage-life expired).

### Context (inputs)

| Field | Description |
|---|---|
| `crop_name` | Crop being considered for sale (e.g., "tomato", "potato") |
| `product_type` | Processing type: "fresh", "packaged", "canned", or "dried" |
| `available_kg` | Quantity available to sell (kg) |
| `current_price_per_kg` | Today's market price for this crop+product_type (USD/kg). Loaded from per-product price files in `data/prices/` |
| `avg_price_per_kg` | Average price for this crop+product_type over recent history |
| `days_in_storage` | How long this product has been stored |
| `storage_life_days` | Maximum storage duration (days) before product must be sold. Loaded from `data/parameters/crops/spoilage_rates-toy.csv` per crop and product type |
| `storage_capacity_kg` | Available storage space (kg) |

### Decision (outputs)

| Field | Description |
|---|---|
| `sell_fraction` | Fraction to sell now (0-1) |
| `store_fraction` | Fraction to keep in storage (0-1) |
| `target_price_per_kg` | Minimum acceptable price; 0 means accept any price |
| `decision_reason` | Why this decision was made |

**Constraint:** sell_fraction + store_fraction = 1.0

### 4.1 `sell_all_immediately`

Once crops are processed into their final state (fresh, canned, etc.) they are immediately sold to market. Storage is only used to hold products briefly before they reach the point of sale. This allows minimal storage capacity.

```
sell_fraction = 1.0
store_fraction = 0.0
target_price_per_kg = 0
reason = "sell_immediately"
```

### 4.2 `hold_for_peak`

Crops are processed according to the food processing policy. The maximum amount is stored until prices rise above a threshold relative to the average price. Storage-life expiry and overflow are handled by the umbrella rule (Section 3) before this policy executes.

**Parameters:**
- `price_threshold_multiplier` (default 1.2) — factor above average price that triggers sales. Sell when current price >= avg_price * 1.2 (20% above average). Configurable via scenario YAML.

Note: Storage-life expiry and storage overflow from pre-existing tranches are handled by the umbrella rule (Section 3), not by this policy. The umbrella rule executes before market policy decisions. The storage capacity checks below serve a different purpose: they govern this policy's own hold-vs-sell decision by checking whether remaining capacity can accommodate what the policy wants to hold. This is distinct from the umbrella rule, which forces sales of already-stored tranches that have expired or overflowed.

```
// Note: Spoilage-based forced sales are handled by the umbrella rule before
// this policy runs. This policy does not check days_in_storage or storage_life_days.

target_price = avg_price_per_kg * price_threshold_multiplier

IF current_price >= target_price:
    // Price above threshold: sell everything
    sell_fraction = 1.0
    reason = "price_above_threshold"

ELSE IF storage_capacity_kg >= available_kg:
    // Room to store all: hold everything
    // Note: this checks REMAINING capacity after umbrella rule has already
    // freed space from expired/overflowed tranches
    sell_fraction = 0.0, store_fraction = 1.0
    reason = "holding_for_peak"

ELSE IF storage_capacity_kg > 0:
    // Partial storage: store what fits, sell the rest
    store_fraction = storage_capacity_kg / available_kg
    sell_fraction = 1.0 - store_fraction
    reason = "holding_partial_storage_full"

ELSE:
    // No remaining storage space: sell everything
    sell_fraction = 1.0
    reason = "no_storage_capacity"
```

### 4.3 `adaptive`

Uses a sigmoid function to determine what portion of food to sell based on the ratio of current price to historical average price. When prices are high relative to history, sell more. When prices are low, store more and wait.

**Parameters (all configurable via scenario YAML):**
- `midpoint` (default 1.0) — price ratio at sigmoid midpoint (1.0 = current price equals average)
- `steepness` (default 5.0) — sigmoid steepness; higher = sharper transition
- `min_sell` (default 0.2) — minimum sell fraction when prices are very low
- `max_sell` (default 1.0) — maximum sell fraction when prices are very high

**Behavior:**

```
price_ratio = current_price_per_kg / avg_price_per_kg

// Sigmoid maps price_ratio to sell_fraction
// Output range: [min_sell, max_sell] (e.g., 0.2 to 1.0)
// Midpoint: price_ratio = 1.0 (current price equals average)
// When price_ratio >> 1.0 (prices high): sell_fraction approaches max_sell
// When price_ratio << 1.0 (prices low): sell_fraction approaches min_sell

sell_fraction = sigmoid(price_ratio, midpoint, steepness, min_sell, max_sell)
store_fraction = 1.0 - sell_fraction

// Clip store_fraction to available storage capacity
IF store_fraction * available_kg > storage_capacity_kg AND storage_capacity_kg > 0:
    store_fraction = storage_capacity_kg / available_kg
    sell_fraction = 1.0 - store_fraction
ELSE IF storage_capacity_kg <= 0:
    sell_fraction = 1.0
    store_fraction = 0.0

IF sell_fraction > 0.9:
    reason = "high_price_selling"
ELSE IF sell_fraction < 0.3:
    reason = "low_price_storing"
ELSE:
    reason = "moderate_price_partial_sale"
```

---

## 5. Energy Policies

**Scope:** Each farm selects an energy source dispatch strategy (unless overridden by community policy). Household and shared facility operations also apply energy policies to their non-farm energy needs. The policy is called daily and returns flags that parameterize the energy dispatch function. The dispatch function itself (not the policy) performs the kWh-by-kWh allocation across sources.

### Context (inputs)

| Field | Description |
|---|---|
| `total_demand_kwh` | Total energy demand today (irrigation, processing, housing) |
| `pv_available_kwh` | PV generation available today |
| `wind_available_kwh` | Wind generation available today |
| `battery_soc` | Current battery state of charge (0-1) |
| `battery_capacity_kwh` | Total battery capacity |
| `grid_price_per_kwh` | Current grid electricity price (USD/kWh); resolved upstream from pricing configuration based on consumer type (agricultural or domestic) |
| `diesel_price_per_L` | Current diesel fuel price (USD/L) |
| `generator_capacity_kw` | Backup generator nameplate capacity |

### Decision (outputs)

| Field | Description |
|---|---|
| `use_renewables` | Use PV/wind generation for self-consumption (bool) |
| `use_battery` | Use battery for charge/discharge (bool) |
| `grid_import` | Import electricity from grid (bool) |
| `grid_export` | Export surplus to grid (bool) |
| `use_generator` | Backup generator is available (bool) |
| `sell_renewables_to_grid` | Route renewable output to grid export (net metering) instead of self-consumption (bool) |
| `battery_reserve_pct` | Minimum battery state-of-charge to maintain (0-1) |
| `decision_reason` | Dispatch strategy explanation |

### 5.1 `microgrid`

Deliberately operates without grid connection. Uses renewable sources first with battery buffering, then falls back to the diesel generator as a last resort. This is a policy choice to be fully self-sufficient — grid infrastructure may or may not exist, but the community chooses not to use it.

**Merit order:** PV -> Wind -> Battery -> Generator

```
use_renewables = true
use_battery = true
grid_import = false
grid_export = false
use_generator = true
sell_renewables_to_grid = false
battery_reserve_pct = 0.20
reason = "Microgrid: PV -> Wind -> Battery -> Generator, no grid"
```

**Dispatch behavior:**
1. Use PV generation to meet demand
2. Use wind generation for remaining demand
3. Charge battery from any PV/wind surplus
4. Discharge battery for remaining demand (down to reserve)
5. Run generator for any remaining shortfall
6. If demand still unmet after generator, record as unmet demand

### 5.2 `renewable_first`

Prioritizes renewable sources with battery buffering, then uses grid for any shortfall. Generator exists as a physical asset but is not dispatched under normal operation (the simulation does not model grid failure).

**Merit order:** PV -> Wind -> Battery -> Grid

```
use_renewables = true
use_battery = true
grid_import = true
grid_export = true
use_generator = false
sell_renewables_to_grid = false
battery_reserve_pct = 0.20
reason = "Renewable-first: PV -> Wind -> Battery -> Grid"
```

**Dispatch behavior:**
1. Use PV generation to meet demand
2. Use wind generation for remaining demand
3. Charge battery from PV/wind surplus
4. Discharge battery for remaining demand (down to reserve)
5. Import from grid for remaining shortfall
6. Export any surplus renewable generation to grid

**Resilience note:** The energy self-sufficiency metric (renewable generation / total consumption) measures what fraction of demand the community meets without grid import. This is a descriptive proxy for how vulnerable the community would be to a grid outage, but grid failure is not simulated.

### 5.3 `all_grid`

All energy demand is met from the grid. If renewable sources (PV, wind) are configured in the system, their output is sold directly to the grid via net metering rather than used for self-consumption.

```
use_renewables = false
use_battery = false
grid_import = true
grid_export = true
use_generator = false
sell_renewables_to_grid = true
battery_reserve_pct = 0.0
reason = "All-grid: import all demand, net-meter renewables"
```

**Dispatch behavior:**
1. Import all demand from grid
2. Route all PV/wind generation to grid export (net metering revenue)
3. Battery is not used

---

## 6. Crop Policies

**Scope:** Farm-level only. Each farm selects a crop management strategy (irrigation adjustment) that controls how much water is requested based on crop growth stage and weather conditions. Community-override policies are supported. Called daily before the water policy. The output (adjusted demand) becomes the water demand input to the water policy.

### Context (inputs)

| Field | Description |
|---|---|
| `crop_name` | Name of crop |
| `growth_stage` | Current stage: "initial", "development", "mid_season", "late_season" |
| `days_since_planting` | Days since planting |
| `total_growing_days` | Total days in growing cycle |
| `base_demand_m3` | Standard irrigation demand for today from precomputed data (m3) |
| `temperature_c` | Ambient temperature (C) |
| `available_water_m3` | Water available in storage at start of day, before today's allocation (m3). Represents carryover from previous days, not today's water policy output. |

> **MVP simplification:** Water stress ratio is not tracked as a policy input. Yield reduction from water deficit is computed at harvest using the FAO-33 formula (see `calculations.md`) but does not feed back into daily crop policy decisions.

### Decision (outputs)

| Field | Description |
|---|---|
| `adjusted_demand_m3` | How much water to request (m3) |
| `demand_multiplier` | Multiplier applied to base demand (for tracking) |
| `decision_reason` | Why this adjustment was made |

### 6.1 `fixed_schedule`

Apply 100% of standard irrigation demand every day regardless of weather, crop stage, or water availability.

```
multiplier = 1.0
adjusted_demand = base_demand_m3
reason = "Fixed schedule: full irrigation demand"
```

### 6.2 `deficit_irrigation`

Controlled deficit strategy. Full irrigation during crop establishment (initial, development stages). Reduced irrigation during mid-season and late-season to conserve water while managing yield impact.

**Parameters:**
- `deficit_fraction` (default 0.80) — fraction of full demand applied during mid-season

**Reduction schedule:**
- Initial stage: 100%
- Development stage: 100%
- Mid-season: deficit_fraction (default 80%)
- Late-season: deficit_fraction * 0.9 (default 72%)

```
IF growth_stage == "mid_season":
    multiplier = deficit_fraction
    reason = "Deficit: {multiplier} during mid-season"

ELSE IF growth_stage == "late_season":
    multiplier = deficit_fraction * 0.9
    reason = "Deficit: {multiplier} during late-season"

ELSE:
    multiplier = 1.0
    reason = "Full irrigation during {growth_stage}"

adjusted_demand = base_demand_m3 * multiplier
```

### 6.3 `weather_adaptive`

Temperature-responsive irrigation. Increases water on hot days (higher transpiration), decreases on cool days.

**Temperature thresholds:**
- Above 40C: +15% (extreme heat stress)
- Above 35C: +5% (hot day)
- Below 20C: -15% (cool day, reduced transpiration)
- 20-35C: no adjustment

```
IF temperature_c > 40:
    multiplier = 1.15
    reason = "Heat stress: +15% (T={temperature}C)"

ELSE IF temperature_c > 35:
    multiplier = 1.05
    reason = "Hot day: +5% (T={temperature}C)"

ELSE IF temperature_c < 20:
    multiplier = 0.85
    reason = "Cool day: -15% (T={temperature}C)"

ELSE:
    multiplier = 1.0
    reason = "Normal irrigation (T={temperature}C)"

adjusted_demand = base_demand_m3 * multiplier
```

---

## 7. Economic Policies

**Scope:** Farm-level only. Each farm selects a financial management strategy governing cash reserve targets. Community-override policies are supported. Called monthly or at year boundaries.

> **MVP simplification — debt service:** Debt service is fixed monthly payments per financing profile (see `calculations.md` Section 5). No accelerated repayment or debt pay-down policies in MVP.

### Context (inputs)

| Field | Description |
|---|---|
| `cash_reserves_usd` | Current cash on hand |
| `monthly_revenue_usd` | Revenue this period |
| `monthly_operating_cost_usd` | Operating costs this period |
| `total_debt_usd` | Outstanding debt principal |
| `debt_service_monthly_usd` | Required monthly debt payment |
| `crop_inventory_kg` | Current stored/unsold inventory |
| `months_of_reserves` | Cash / average monthly operating costs |

### Decision (outputs)

| Field | Description |
|---|---|
| `reserve_target_months` | Target months of cash reserves |
| `sell_inventory` | Whether to liquidate stored inventory now (bool) |
| `decision_reason` | Why this strategy was chosen |

> **MVP simplification:** Equipment maintenance and upgrades are included in annual OPEX. No separate investment mechanism (`investment_allowed`) in MVP.

### Summary

| Policy | Reserve target | Behavior |
|---|---|---|
| `balanced` | 3 months | Adaptive: sell inventory if < 1 month reserves, hold otherwise |
| `aggressive_growth` | 1 month | Minimize reserves, sell inventory immediately |
| `conservative` | 6 months | Maintain high safety buffer, hold inventory |
| `risk_averse` | 6+ months | Maximize reserves, sell inventory immediately to lock in revenue |

### 7.1 `balanced`

Adaptive strategy that shifts behavior based on current financial position. Sells inventory when reserves are critically low, holds otherwise.

```
reserve_target = 3.0 months

IF months_of_reserves < 1.0:
    sell_inventory = true
    reason = "Low reserves ({months} months), survival mode"

ELSE IF months_of_reserves < 3.0:
    sell_inventory = false
    reason = "Building reserves ({months}/{target} months)"

ELSE:
    sell_inventory = false
    reason = "Healthy reserves ({months} months), growth mode"
```

### 7.2 `aggressive_growth`

Minimize cash reserves. Sell all inventory immediately to free up capital.

```
reserve_target = 1.0 month
sell_inventory = true
reason = "Aggressive: 1 month target, sell immediately"
```

### 7.3 `conservative`

Maintain high cash reserves.

```
reserve_target = 6.0 months
sell_inventory = false

IF months_of_reserves < reserve_target:
    reason = "Conservative: under {target} months reserves"
ELSE:
    reason = "Conservative: {months} months reserves, adequate"
```

### 7.4 `risk_averse`

Maximum caution. Build large reserves, liquidate inventory to lock in revenue.

```
reserve_target = MAX(6.0, min_cash_months)
sell_inventory = true

IF months_of_reserves < 3.0:
    reason = "Risk averse: critically low ({months} months)"
ELSE:
    reason = "Risk averse: {months} months, target {target}"
```
