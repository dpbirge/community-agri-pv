# Policy Specifications

## Overview

This document specifies the decision logic for all 23 simulation policies across 6 domains. Each policy is fully defined in plain English and pseudocode. The translation from this specification to code is left to the implementer.

**Policy scope:** Policies operate at three distinct levels, described below. For the full configuration schema (YAML structure, parameter wiring), see `structure.md`.

### Policy levels

1. **Farm level**: Each farm can have its own policy for any domain (water, energy, crop, food processing, market, economic). Per-farm policies are configured in the scenario YAML under each farm's definition. Crop plans (what to plant, when, how much area) are ALWAYS per-farm regardless of policy level -- policies determine decision logic, not crop selection.

2. **Collective farm override** (default for most policies): When a policy is set at the `collective_farm_override` level in the scenario YAML, the policy name and its parameters are stamped into every farm's policy slot during setup (before the simulation loop begins). If a farm also has a per-farm setting for the same domain, the collective override wins -- the farm-level setting is overwritten. This is the most common configuration: the community agrees on a shared approach for water, energy, food processing, market, or economic policy, while each farm retains its own crop plan. Policy parameters follow the policy -- when set at the collective level, parameters come from the collective level too.

3. **Community level**: Applies only to residential households and community building water and energy policies. These are separate from farm-level and collective-override policies. Available household policies are limited to: water policy `max_groundwater` or `max_municipal`; energy policy `microgrid`, `renewable_first`, or `all_grid`. Configured in the scenario YAML under `household_policies`. Community-level policies do not affect farm operations (crop production, food processing, market timing, etc.).

When `collective_farm_override` is set for a domain, any per-farm setting for that domain is overwritten during pre-loop initialization. See `simulation_flow.md` (Pre-Loop Initialization) for the stamping algorithm.

For calculation formulas, see `calculations.md`.

### How to read this document

Each policy domain (water, food processing, market, energy, crop, economic) follows the same structure:

1. **Context (inputs)** — Named fields the simulation passes to the policy each time it is called. The simulation assembles these from current state.

2. **Decision (outputs)** — Named fields the policy returns. The simulation applies these to update state.

3. **Policy logic** — Plain English description followed by pseudocode for each policy. Pseudocode uses `ctx` to reference context fields (e.g., `ctx.demand_m3`).

### Common patterns

All policy domains share these structural conventions:

- **Lookup by name**: Policies are referenced by name strings in scenario YAML files (e.g., `water_policy: cheapest_source`). Each domain provides a factory function that takes a name string and returns the corresponding policy.

- **Decision reasons**: Every policy returns a `decision_reason` string explaining why the decision was made (e.g., `"gw_cheaper"`, `"quota_exhausted"`). These enable filtering and grouping in analysis and debugging.

- **Constraint clipping**: When a policy requests more of a resource than is physically available, the request is clipped to the physical limit and the shortfall is met from an alternative source. The binding constraint is recorded in the decision.

- **Method names**: Each domain uses a canonical method name matching the code in `src/policies/`:

  | Domain | Method | Factory function |
  |---|---|---|
  | Water | `allocate_water(ctx)` | `get_water_policy(name)` |
  | Energy | `allocate_energy(ctx)` | `get_energy_policy(name)` |
  | Crop | `decide(ctx)` | `get_crop_policy(name)` |
  | Food processing | `allocate(ctx)` | `get_food_policy(name)` |
  | Market | `decide(ctx)` | `get_market_policy(name)` |
  | Economic | `decide(ctx)` | `get_economic_policy(name)` |

- **Policy name field**: Every policy decision dataclass includes a `policy_name: str` field that matches the policy's registry key (e.g., `"cheapest_source"`, `"balanced_mix"`). This field is not listed in each output table below to avoid repetition, but is always present.

- **Configurable parameters**: Some policies accept tuning parameters (e.g., threshold multipliers, reserve targets). Parameters are set at instantiation from the scenario YAML and remain fixed for the run. Defaults are noted in each policy description. See `structure.md` Section 3.1 (Policy parameter wiring) for the full YAML-to-constructor pipeline.

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

## Water Policies

**Scope:** Each farm selects a water source allocation strategy. Typically set via `collective_farm_override` so all farms use the same water strategy, though per-farm overrides are supported. Household and shared facility operations also apply water policies to their non-farm water needs (community-level policies, see Overview). The policy is called daily to split water demand between treated groundwater and purchased municipal water. See `structure.md` Section 3 for the YAML schema.

### Context (inputs)

| Field | Description |
| --- | --- |
| `demand_m3` | Total water demand today (m3) |
| `treatment_kwh_per_m3` | Energy to desalinate 1 m3 of groundwater |
| `pumping_kwh_per_m3` | Energy to pump 1 m3 from well to surface |
| `conveyance_kwh_per_m3` | Energy to convey 1 m3 from well/treatment to farm |
| `gw_maintenance_per_m3` | O&M cost per m3 of groundwater treatment (USD). Derived from annual O&M in `costs.operating` registry entry, divided by `system_capacity_m3_day × 365` to yield per-m3 cost |
| `municipal_price_per_m3` | Current municipal water price (USD/m3) |
| `energy_price_per_kwh` | Current energy price (USD/kWh) |
| `max_groundwater_m3` | Maximum daily groundwater extraction (well capacity / num_farms) |
| `max_treatment_m3` | Maximum daily treatment throughput (treatment capacity / num_farms) |
| `cumulative_gw_year_m3` | Groundwater used so far this year (for quota policy) |
| `cumulative_gw_month_m3` | Groundwater used so far this month (for quota policy) |
| `current_month` | Current month 1-12 (for quota policy) |
| `groundwater_tds_ppm` | Current measured salinity of available groundwater (for min_water_quality policy) |
| `municipal_tds_ppm` | Salinity of municipal water supply (for min_water_quality policy) |

**Note on \****`energy_price_per_kwh`**\*\*:** The water policy executes before the energy policy (step 2 vs step 3 in the daily execution order). The energy price used here is the current grid tariff from pricing configuration — it represents the marginal cost of the next kWh regardless of dispatch strategy. This is consistent with the operational independence principle: energy availability never constrains water, but the grid tariff affects groundwater cost comparisons.

**Note on \****`municipal_price_per_m3`**\*\*:** The simulation resolves the applicable price upstream based on consumer type (agricultural or community) before passing it to the policy. Farm water demands use the agricultural pricing regime; household and community building demands use the community pricing regime. See pricing configuration in `structure.md`.

### Decision (outputs)

| Field | Description |
| --- | --- |
| `groundwater_m3` | Volume allocated from treated groundwater |
| `municipal_m3` | Volume allocated from municipal supply |
| `energy_used_kwh` | Energy consumed for groundwater pumping + conveyance + treatment |
| `cost_usd` | Water cost excluding energy (municipal purchase + GW maintenance only). Used in daily accounting. |
| `economic_cost_usd` | Full economic cost including energy (for policy comparison logging only, NOT used in accounting) |
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

# Economic cost (for policy source-comparison logic — NOT used in accounting)
economic_cost_usd = (groundwater_m3 * gw_cost_per_m3) + (municipal_m3 * municipal_price_per_m3)

# Cash cost (for daily accounting — excludes energy, which flows through dispatch)
cash_cost_per_m3 = gw_maintenance_per_m3
cost_usd = (groundwater_m3 * cash_cost_per_m3) + (municipal_m3 * municipal_price_per_m3)
```

### Policy Options

#### `max_groundwater`

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

#### `max_municipal`

Maximize municipal water. All demand is met from municipal supply. Groundwater is used only if municipal water is physically unavailable (the simulation currently does not model municipal supply interruption, so this policy is functionally 100% municipal).

```
groundwater = 0
municipal = demand
energy_used = 0
cost = municipal * municipal_price_per_m3
reason = "muni_preferred"
```

#### `min_water_quality`

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
economic_cost_usd = (groundwater_m3 * gw_cost_per_m3) + (municipal_m3 * municipal_price_per_m3)
cost_usd = (groundwater_m3 * gw_maintenance_per_m3) + (municipal_m3 * municipal_price_per_m3)
```

**Resulting water quality after mixing:**

```
mixed_tds_ppm = (groundwater_m3 * groundwater_tds_ppm + municipal_m3 * municipal_tds_ppm)
                / (groundwater_m3 + municipal_m3)
// Note: mixed_tds_ppm will always be <= target_tds_ppm because municipal is always cleaner
```

---

#### `cheapest_source`

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

#### `conserve_groundwater`

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

**Note on \****`limiting_factor`***\* vs \****`constraint_hit`**\*\*:** All water policies return `constraint_hit` (shared output field, values: `"well_limit"`, `"treatment_limit"`, or None) which records only infrastructure constraints. The `conserve_groundwater` policy additionally returns `limiting_factor` (values: `"ratio_cap"`, `"well_limit"`, `"treatment_limit"`, or None), which is a superset of `constraint_hit` — it includes both the shared infrastructure constraint values AND the policy's own ratio cap. When `limiting_factor = "ratio_cap"`, the allocation was limited by the conservation policy's `max_gw_ratio` parameter, not by physical infrastructure. When `limiting_factor` matches an infrastructure constraint, it mirrors `constraint_hit`. This enables analysis of whether a farm is conservation-limited or infrastructure-limited.

#### `quota_enforced`

Hard annual groundwater limit with monthly variance controls. When the annual quota is exhausted, forces 100% municipal for the remainder of the year. Monthly controls prevent front-loading extraction.

**Scope:** `annual_quota_m3` is the per-farm extraction limit. Each farm tracks its own
`cumulative_gw_year_m3` and `cumulative_gw_month_m3` against its own quota. The community
total is the sum of all farm quotas (annual_quota_m3 * num_farms) but is not enforced
as a separate constraint — farm-level enforcement is sufficient because all farms use
the same quota when set via collective_farm_override.

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

## Food Processing Policies

**Scope:** Each farm's food processing policy determines how harvested crop is split across four processing pathways: fresh, packaged, canned, and dried. Typically set via `collective_farm_override` so all farms use the same processing strategy. Called during harvest processing in the simulation loop. See `structure.md` Section 3 for the YAML schema.

**Pooled processing resources:** Processing capacity (drying, canning, packaging equipment) and storage are pooled community resources, not per-farm. All farms contribute their harvest to the shared processing pool. The food processing policy determines how the pooled harvest is allocated across fresh/packaged/canned/dried pathways. Capacity clipping (Section "Shared logic: capacity clipping" below) operates on the pooled throughput, not per-farm throughput. See `simulation_flow.md` Section 4 for details on how harvests are pooled and processed.

### Umbrella rule: forced sale and FIFO tracking

This rule applies to ALL food processing policies and overrides normal storage behavior. It executes after food processing updates total storage for the day (step 4b in execution order), before the market policy runs (step 5).

1. **Tranche tracking**: Each harvest batch is tracked as a discrete unit (tranche) with an entry date and product type. This enables first-in, first-out (FIFO) ordering.

2. **Storage-life expiry**: When any tranche reaches its storage life limit, it must be sold immediately regardless of market conditions or policy preferences. Storage life data is sourced from `data/parameters/crops/storage_spoilage_rates-toy.csv` (per crop, per product type). CSV schema: `crop_name, product_type, shelf_life_days`.

3. **Storage overflow**: When storage is full and new production needs space, sell the oldest tranche first, then the next oldest, until enough space is freed. This ensures proper FIFO inventory management.

4. **Execution timing**: After food processing allocates today's harvest and updates storage totals, the umbrella rule checks all tranches for expiry and overflow. Forced sales execute immediately. Then the market policy runs on remaining inventory without forced-sale constraints.

### Context (inputs)

| Field | Description |
| --- | --- |
| `harvest_yield_kg` | Total harvest yield before processing (kg) |
| `crop_name` | Name of crop being processed |
| `fresh_price_per_kg` | Current fresh farmgate price (USD/kg) |
| `drying_capacity_kg` | Daily drying capacity (kg); infinite if unconstrained |
| `canning_capacity_kg` | Daily canning capacity (kg); infinite if unconstrained |
| `packaging_capacity_kg` | Daily packaging capacity (kg); infinite if unconstrained |

### Decision (outputs)

| Field | Description |
| --- | --- |
| `fresh_fraction` | Fraction sold as fresh produce (0-1) |
| `packaged_fraction` | Fraction sent to packaging (0-1) |
| `canned_fraction` | Fraction sent to canning (0-1) |
| `dried_fraction` | Fraction sent to drying (0-1) |
| `decision_reason` | Why this split was chosen |

**Constraint:** Fractions must sum to 1.0.

### Shared logic: capacity clipping

**Contract:** The food processing **policy class** MUST return mathematically pure fractions summing to 1.0, with no knowledge of equipment capacity constraints. The **simulation loop** (not the policy class) takes those fractions and applies capacity clipping as a post-processing step. This separation keeps policies testable in isolation and ensures capacity limits are enforced uniformly regardless of which policy is active. See `simulation_flow.md` Section 5.4 for the simulation loop integration.

The pseudocode below runs in the **simulation loop**, after the policy's `allocate()` call returns. If the allocated kg for any pathway exceeds its daily capacity, the excess is redirected to fresh. Fresh has no practical capacity limit (requires only washing/sorting) and serves as the overflow sink:

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

### Policy Options

> **Note on processing fractions:** The fresh/packaged/canned/dried splits shown below are the policy's **fixed allocation logic**, not configurable parameters. The scenario YAML specifies a policy by name (e.g., `food: balanced_mix`); the policy implementation determines the split. The only configurable parameter across all food processing policies is `market_responsive.price_threshold`, which controls the price level at which the policy switches between its two fixed split tables.

#### `all_fresh`

Sell 100% of harvest as fresh produce. No processing.

| Fresh | Packaged | Canned | Dried |
| --- | --- | --- | --- |
| 100% | 0% | 0% | 0% |

#### `maximize_storage`

Maximize storage duration by processing most of the harvest into shelf-stable products. Only 20% goes to fresh sale (shortest storage life).

| Fresh | Packaged | Canned | Dried |
| --- | --- | --- | --- |
| 20% | 10% | 35% | 35% |

#### `balanced_mix`

Moderate mix. Half the harvest sold fresh, half processed across three pathways.

| Fresh | Packaged | Canned | Dried |
| --- | --- | --- | --- |
| 50% | 20% | 15% | 15% |

#### `market_responsive`

Adjusts processing mix based on current fresh prices relative to reference farmgate prices. When fresh prices are low, shifts harvest into processing (value-add pathways). When fresh prices are normal or high, sells more fresh.

**Trigger:** Fresh price falls below 80% of the crop's reference farmgate price.

**Reference farmgate prices** are loaded from crop price data files in `data/prices/crops/`. Example values (USD/kg) for illustration only — actual values come from data files:
- tomato: ~0.30
- potato: ~0.25
- onion: ~0.20
- kale: ~0.40
- cucumber: ~0.35

```
# Reference farmgate price: the MEAN of the crop's fresh price time series
# across the full simulation period. Computed once at scenario load time and
# cached per crop.
reference_price = MEAN(all prices in data/prices/crops/<crop>-toy.csv)

IF fresh_price_per_kg < reference_price * 0.80:
    // Low prices: shift toward processing
    Fresh=30%, Packaged=20%, Canned=25%, Dried=25%
ELSE:
    // Normal/high prices: sell more fresh
    Fresh=65%, Packaged=15%, Canned=10%, Dried=10%
```

| Condition | Fresh | Packaged | Canned | Dried |
| --- | --- | --- | --- | --- |
| Price < 80% of reference | 30% | 20% | 25% | 25% |
| Price >= 80% of reference | 65% | 15% | 10% | 10% |

---

## Market Policies (Selling)

**Scope:** The market policy determines when processed food is sold. Typically set via `collective_farm_override` so all farms use the same selling strategy. See `structure.md` Section 3 for the YAML schema.

**Pooled inventory and revenue attribution:** Market policies operate on the pooled community inventory. The community sells as a bloc -- individual farms do not negotiate separate sales. Revenue from each sale is attributed back to individual farms proportional to their kg contribution per crop. Specifically: each crop has its own revenue pool, and each farm's share of that crop's revenue equals the farm's kg input to that crop divided by the total kg of that crop from all farms. This attribution happens at the point of sale, not at harvest. See `simulation_flow.md` Section 4.9 for the revenue attribution algorithm.

**Separation of concerns:** Food processing policies entirely determine HOW food is processed (the fresh/packaged/canned/dried split). Market policies entirely determine WHEN food is sold. The only exception is forced sales from the food processing umbrella rule (storage full or storage-life expired).

### Context (inputs)

| Field | Description |
| --- | --- |
| `crop_name` | Crop being considered for sale (e.g., "tomato", "potato") |
| `product_type` | Processing type: "fresh", "packaged", "canned", or "dried" |
| `available_kg` | Total kg across ALL tranches of this crop+product_type in community storage |
| `current_price_per_kg` | Today's market price for this crop+product_type (USD/kg). Loaded from per-product price files in `data/prices/` |
| `avg_price_per_kg` | Average price for this crop+product_type over recent history. Computed from historical price data files in `data/prices/` (rolling 12-month mean of the per-product time series), not from runtime sales records. When fewer than 12 months of price data precede the current date, use all available months as the window. For the very first simulation day, use the full time series mean as the initial average. |
| `days_in_storage` | Age of the OLDEST tranche of this crop+product_type (days since harvest). Represents the most urgent inventory. |
| `storage_life_days` | Maximum storage duration for this crop+product_type (from storage_spoilage_rates CSV) |
| `storage_capacity_kg` | REMAINING storage capacity for this product_type: capacity - currently_stored_kg (across all crops of this product_type) |

### Decision (outputs)

| Field | Description |
| --- | --- |
| `sell_fraction` | Fraction to sell now (0-1) |
| `store_fraction` | Fraction to keep in storage (0-1) |
| `target_price_per_kg` | Minimum acceptable price; 0 means accept any price |
| `decision_reason` | Why this decision was made |

**Constraint:** sell_fraction + store_fraction = 1.0

### Policy Options

#### `sell_all_immediately`

Once crops are processed into their final state (fresh, canned, etc.) they are immediately sold to market. Storage is only used to hold products briefly before they can be sold to market. This allows minimal storage capacity. The logic applies to all product types equally.

```
sell_fraction = 1.0
store_fraction = 0.0
target_price_per_kg = 0
reason = "sell_immediately"
```

#### `hold_for_peak`

Crops are processed according to the food processing policy. The maximum amount is stored until prices rise above a threshold relative to the average price. Storage-life expiry and overflow are handled by the umbrella rule (see Food Processing Policies) before this policy executes.

**Parameters:**
- `price_threshold_multiplier` (default 1.2) — factor above average price that triggers sales. Sell when current price >= avg_price * 1.2 (20% above average). Configurable via scenario YAML.

Note: Storage-life expiry and storage overflow from pre-existing tranches are handled by the umbrella rule (see Food Processing Policies), not by this policy. The umbrella rule executes before market policy decisions. The storage capacity checks below serve a different purpose: they govern this policy's own hold-vs-sell decision by checking whether remaining capacity can accommodate what the policy wants to hold. This is distinct from the umbrella rule, which forces sales of already-stored tranches that have expired or overflowed.

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

#### `adaptive`

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

sell_fraction = sigmoid(price_ratio, min_sell, max_sell, steepness, midpoint)
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

### Shared logic: tranche selection for voluntary sales

When a market policy returns `sell_fraction < 1.0`, the simulation must determine which tranches to sell. Voluntary sales follow the same FIFO order as forced sales — oldest tranches are sold first:

```text
sell_remaining_kg = available_kg * sell_fraction
FOR each tranche in community_storage (oldest first, same crop + product_type):
    IF sell_remaining_kg <= 0: BREAK
    IF tranche.kg <= sell_remaining_kg:
        sell entire tranche
        sell_remaining_kg -= tranche.kg
    ELSE:
        sell partial tranche (sell_remaining_kg)
        tranche.kg -= sell_remaining_kg
        sell_remaining_kg = 0
```

This ensures older inventory is liquidated before newer inventory, preventing spoilage buildup from always selling the freshest product.

---

## Energy Policies

**Scope:** Each farm selects an energy source dispatch strategy. Typically set via `collective_farm_override` so all farms use the same dispatch strategy, though per-farm overrides are supported. Household and shared facility operations also apply energy policies to their non-farm energy needs (community-level policies, see Overview). The policy is called daily and returns flags that parameterize the energy dispatch function. The dispatch function itself (not the policy) performs the kWh-by-kWh allocation across sources. See `structure.md` Section 3 for the YAML schema.

### Context (inputs)

| Field | Description |
| --- | --- |
| `total_demand_kwh` | Total energy demand today (irrigation, processing, housing) |
| `pv_available_kwh` | PV generation available today |
| `wind_available_kwh` | Wind generation available today |
| `battery_soc` | Current battery state of charge (0-1) |
| `battery_capacity_kwh` | Total battery capacity |
| `grid_price_per_kwh` | Current grid electricity price (USD/kWh); resolved upstream from pricing configuration based on consumer type (agricultural or community) |
| `diesel_price_per_L` | Current diesel fuel price (USD/L) |
| `generator_capacity_kw` | Backup generator nameplate capacity |

### Decision (outputs)

| Field | Description |
| --- | --- |
| `use_renewables` | Use PV/wind generation for self-consumption (bool) |
| `use_battery` | Use battery for charge/discharge (bool) |
| `grid_import` | Import electricity from grid (bool) |
| `grid_export` | Export surplus to grid (bool) |
| `use_generator` | Backup generator is available (bool) |
| `sell_renewables_to_grid` | Route renewable output to grid export (net metering) instead of self-consumption (bool) |
| `battery_reserve_pct` | Minimum battery state-of-charge to maintain (0-1). Effective floor = `max(SOC_min_hardware, battery_reserve_pct)`. Cannot override hardware SOC_min (0.10 for LFP). Each policy sets its own value: `microgrid` and `renewable_first` use 0.20, `all_grid` uses 0.0. See `simulation_flow.md` Section 5.4 and `calculations_energy.md` Battery Storage Dynamics for the `effective_soc_floor` computation. |
| `decision_reason` | Dispatch strategy explanation |

### Policy Options

#### `microgrid`

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

#### `renewable_first`

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

#### `all_grid`

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

## Crop Policies

**Scope:** Each farm selects a crop management strategy (irrigation adjustment) that controls how much water is requested based on crop growth stage and weather conditions. Can be set via `collective_farm_override` or per-farm. Note: crop plans (what to plant, when, how much area) are always per-farm regardless of policy level -- the crop policy only adjusts irrigation demand, not crop selection. Called daily before the water policy. The output (adjusted demand) becomes the water demand input to the water policy. See `structure.md` Section 3 for the YAML schema.

### Context (inputs)

| Field | Description |
| --- | --- |
| `crop_name` | Name of crop |
| `growth_stage` | Current growth stage (CropStage enum): INITIAL, DEVELOPMENT, MID_SEASON, LATE_SEASON |
| `days_since_planting` | Days since planting |
| `total_growing_days` | Total days in growing cycle |
| `base_demand_m3` | Standard irrigation demand for today from precomputed data (m3) |
| `temperature_c` | Ambient temperature (C) |
| `available_water_m3` | Water available in storage at start of day, before today's allocation (m3). Represents carryover from previous days, not today's water policy output. |

> **MVP simplification:** Water stress ratio is not tracked as a policy input. Yield reduction from water deficit is computed at harvest using the FAO-33 formula (see `calculations_crop.md` Section 1) but does not feed back into daily crop policy decisions.

### Decision (outputs)

| Field | Description |
| --- | --- |
| `adjusted_demand_m3` | How much water to request (m3) |
| `demand_multiplier` | Multiplier applied to base demand (for tracking) |
| `decision_reason` | Why this adjustment was made |

### Policy Options

#### `fixed_schedule`

Apply 100% of standard irrigation demand every day regardless of weather, crop stage, or water availability.

```
multiplier = 1.0
adjusted_demand = base_demand_m3
reason = "Fixed schedule: full irrigation demand"
```

#### `deficit_irrigation`

Controlled deficit strategy. Full irrigation during crop establishment (initial, development stages). Reduced irrigation during mid-season and late-season to conserve water while managing yield impact.

**Parameters:**
- `deficit_fraction` (default 0.80) — fraction of full demand applied during mid-season

**Reduction schedule:**
- Initial stage: 100%
- Development stage: 100%
- Mid-season: deficit_fraction (default 80%)
- Late-season: deficit_fraction * 0.9 (default 72%)

```
IF growth_stage == MID_SEASON:
    multiplier = deficit_fraction
    reason = "Deficit: {multiplier} during MID_SEASON"

ELSE IF growth_stage == LATE_SEASON:
    multiplier = deficit_fraction * 0.9
    reason = "Deficit: {multiplier} during LATE_SEASON"

ELSE:
    multiplier = 1.0
    reason = "Full irrigation during {growth_stage}"

adjusted_demand = base_demand_m3 * multiplier
```

#### `weather_adaptive`

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

## Economic Policies

**Scope:** Each farm selects a financial management strategy governing cash reserve targets. Typically set via `collective_farm_override` so all farms use the same financial strategy, though per-farm overrides are supported. Called monthly or at year boundaries. See `structure.md` Section 3 for the YAML schema.

> **MVP simplification — debt service:** Debt service is fixed monthly payments per financing profile (see `calculations_economic.md`). No accelerated repayment or debt pay-down policies in MVP.

### Context (inputs)

| Field | Description |
| --- | --- |
| `cash_reserves_usd` | Current cash on hand |
| `monthly_revenue_usd` | Revenue this period |
| `monthly_operating_cost_usd` | Operating costs this period |
| `total_debt_usd` | Outstanding debt principal |
| `debt_service_monthly_usd` | Required monthly debt payment |
| `crop_inventory_kg` | Current stored/unsold inventory |
| `months_of_reserves` | Cash / average monthly operating costs |

### Decision (outputs)

| Field | Description |
| --- | --- |
| `reserve_target_months` | Target months of cash reserves |
| `sell_inventory` | Whether to liquidate stored inventory now (bool) |
| `decision_reason` | Why this strategy was chosen |

> **MVP simplification:** Equipment maintenance and upgrades are included in annual OPEX. No separate investment mechanism in MVP.

**Configurable parameter:** `min_cash_months` — minimum months of operating costs to maintain as cash reserves. Passed at policy instantiation from scenario YAML (`community_policy_parameters.<policy_name>.min_cash_months`). Defaults by policy: `aggressive_growth` = 1, `conservative` = 6, `risk_averse` = 3. Not applicable to `balanced_finance` (hardcoded 3-month target).

### Summary

| Policy | Reserve target | Behavior |
| --- | --- | --- |
| `balanced_finance` | 3 months | Adaptive: sell inventory if < 1 month reserves, hold otherwise |
| `aggressive_growth` | 1 month | Minimize reserves, sell inventory immediately |
| `conservative` | 6 months | Maintain high safety buffer, hold inventory |
| `risk_averse` | 6+ months | Maximize reserves, sell inventory immediately to lock in revenue |

### Policy Options

#### `balanced_finance`

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

#### `aggressive_growth`

Minimize cash reserves. Sell all inventory immediately to free up capital. Caps the total months of inventory held to prevent over-accumulation of stored product.

**Parameters:**

- `min_cash_months` (default 1) -- minimum months of operating costs to maintain as cash reserves
- `max_inventory_months` (default 6) -- maximum months of inventory to hold before forcing liquidation

```
reserve_target = 1.0 month
sell_inventory = true
reason = "Aggressive: 1 month target, sell immediately"
```

#### `conservative`

Maintain high cash reserves.

```
reserve_target = 6.0 months
sell_inventory = false

IF months_of_reserves < reserve_target:
    reason = "Conservative: under {target} months reserves"
ELSE:
    reason = "Conservative: {months} months reserves, adequate"
```

#### `risk_averse`

Maximum caution. Build large reserves, liquidate inventory to lock in revenue.

```
reserve_target = MAX(6.0, min_cash_months)
sell_inventory = true

IF months_of_reserves < 3.0:
    reason = "Risk averse: critically low ({months} months)"
ELSE:
    reason = "Risk averse: {months} months, target {target}"
```

---

## How to Add a New Policy

This section describes the steps to add a new policy to any domain. The registration
mechanism is a simple name-to-class dictionary inside each domain's factory function.

### Step 1: Define context and decision compatibility

Verify that the existing context and decision dataclasses for the domain cover your
policy's needs. All policies within a domain share the same context (input) and
decision (output) dataclass.

- If your policy needs a new context field, add it to the domain's context dataclass
  and update the simulation loop (in `simulation_flow.md`) to populate it. All
  existing policies in the domain must gracefully ignore the new field.
- If your policy returns a new output field, add it to the decision dataclass. Set a
  sensible default (e.g., `None`) so existing policies do not break.
- Prefer using existing fields over adding new ones. The `decision_reason` string is
  designed to carry policy-specific diagnostic information.

### Step 2: Implement the policy class

Create a new class that inherits from the domain's base class and implements the
required method:

| Domain | Base class | Method to implement |
|--------|-----------|-------------------|
| Water | `BaseWaterPolicy` | `allocate_water(ctx) -> WaterAllocation` |
| Energy | `BaseEnergyPolicy` | `allocate_energy(ctx) -> EnergyAllocation` |
| Crop | `BaseCropPolicy` | `decide(ctx) -> CropDecision` |
| Food | `BaseFoodPolicy` | `allocate(ctx) -> ProcessingAllocation` |
| Market | `BaseMarketPolicy` | `decide(ctx) -> MarketDecision` |
| Economic | `BaseEconomicPolicy` | `decide(ctx) -> EconomicDecision` |

The constructor accepts keyword arguments for any configurable parameters with defaults:

```python
class MyNewWaterPolicy(BaseWaterPolicy):
    def __init__(self, my_threshold=0.5):
        self.my_threshold = my_threshold

    def allocate_water(self, ctx):
        # Implementation using ctx fields and self.my_threshold
        ...
        return WaterAllocation(
            groundwater_m3=...,
            municipal_m3=...,
            energy_used_kwh=...,
            cost_usd=...,
            decision_reason="my_reason",
            constraint_hit=...,
            policy_name="my_new_policy",
        )
```

Follow the error handling conventions documented in the "Error handling" section above:
zero-demand early return, `ValueError` on NaN/negative inputs, division-by-zero guards.

### Step 3: Register in the factory function

Add the policy name and class to the dictionary inside the domain's
`get_<domain>_policy()` function:

```python
def get_water_policy(name, **kwargs):
    policies = {
        "max_groundwater": MaxGroundwater,
        "cheapest_source": CheapestSource,
        "conserve_groundwater": ConserveGroundwater,
        "min_water_quality": MinWaterQuality,
        "max_municipal": MaxMunicipal,
        "quota_enforced": QuotaEnforced,
        "my_new_policy": MyNewWaterPolicy,    # <-- add here
    }
    if name not in policies:
        raise ValueError(
            f"Unknown water policy '{name}'. "
            f"Available: {list(policies.keys())}"
        )
    return policies[name](**kwargs)
```

The dictionary key is the policy name string used in scenario YAML files.

### Step 4: Add configurable parameters to YAML (if any)

If the policy accepts constructor parameters, add default values under
`community_policy_parameters` in the scenario YAML:

```yaml
community_policy_parameters:
  my_new_policy:
    my_threshold: 0.5
```

See `structure.md` Section 3.1 (Policy parameter wiring) for the full
YAML-to-constructor pipeline.

### Step 5: Document the policy

Add a subsection to the appropriate domain section of this document (`policies.md`)
following the established format:

1. Policy name heading (e.g., `#### my_new_policy`)
2. Plain-language description of behavior
3. Parameters table (if configurable)
4. Pseudocode block
5. Decision reason values

### Step 6: Update scenario validation

Add the new policy name to the list of valid options for the domain in
`validation.py`. The validation function checks that every farm's policy
name appears in the domain's factory function registry.

### Summary checklist

- [ ] Context/decision dataclass covers policy needs (or extended)
- [ ] Policy class inherits from domain base class
- [ ] Constructor accepts keyword arguments with defaults
- [ ] Policy name added to factory function dictionary
- [ ] YAML `community_policy_parameters` entry added (if configurable)
- [ ] Policy documented in `policies.md`
- [ ] Validation updated with new policy name

---

## Deferred Policy Domains

The following policy domains are described in `overview.md` but are not yet
specified with sufficient detail for implementation. They are explicitly excluded
from MVP.

### Insurance policies

`overview.md` Section 3 describes crop insurance and equipment insurance as risk
management alternatives to collective pooling. Six design questions remain
unresolved (payout triggers, deductibles, mandatory vs. optional participation,
government vs. private products, interaction with pooling mechanism, and claims
timing). Insurance will be specified as a new policy domain when these questions
are answered. No YAML schema, context/decision dataclass, or simulation loop
integration exists for insurance.

### Collective pooling mechanism

`overview.md` Section 3 describes a collective reserve fund where a configurable
percentage of farm profits is pooled annually, with distribution rules for
hardship periods. Three design questions remain open: (1) how operating advances
are determined, (2) how unrecovered advances are handled, and (3) how collective
costs are allocated beyond the existing `cost_allocation_method` parameter.
Pooling will be specified as either an extension to the economic policy domain
or as a standalone community-level mechanism when these questions are answered.
No YAML schema, policy logic, or simulation loop integration currently exists.
See `future_improvements.md` for implementation guidance.

### Working capital advance rules

`overview.md` Section 3 describes operating advances flowing to farmers throughout
the year, recouped when goods are sold. The advance determination method (fixed
amount, area-based, or historical), unrecovered advance handling, and interaction
with collective pooling are all open design questions. Working capital advances
will be specified as part of the economic policy domain when these questions are
answered. The current model uses `starting_capital_usd` and daily cash tracking
as a simplified working capital mechanism. See `future_improvements.md` for
implementation guidance.
