# Water Policy Extensions — Implementation Plan

## Overview

Four extensions to the water policy layer, ranked by implementation order.
Items 1 and 4 are narrow changes; items 2 and 3 are broader.

| # | Extension | Scope | Files Touched |
|---|-----------|-------|---------------|
| 1 | Brine disposal cost | Config + 3 lines | `water_systems_base.yaml`, `src/water.py` |
| 2 | Tiered municipal water pricing | Config + policy + dispatch | `water_policy_base.yaml`, `src/water.py`, `src/water_balance.py` |
| 3 | Growth-stage deficit irrigation | Data + generator + demand + yield | `yield_response_factors-research.csv`, `generate_crop_lookup.py`, `src/irrigation_demand.py`, `src/crop_yield.py`, `water_policy_base.yaml` |
| 4 | Agrivoltaic ET reduction | None — already implemented | (verification only) |

---

## 1. Brine Disposal Cost

### Current State

`src/water.py` already tracks brine volume as `treatment_reject_m3` per day. The
volume is computed from BWRO feed minus product. However, no cost is assigned to
disposing this brine — it is treated as a free externality.

### What Changes

**`settings/water_systems_base.yaml`** — add one field to the treatment section:

```yaml
treatment:
  type: bwro
  throughput_m3_hr: 50
  goal_output_tds_ppm: 400
  brine_disposal_cost_per_m3: 1.50   # NEW — USD per m3 of reject
```

**`src/water.py` — `_compute_gw_energy_and_cost()`** — add brine cost to
groundwater cost:

```python
# After computing treatment_reject_m3 (existing code around line 251):
brine_cost = row.get('treatment_reject_m3', 0.0) * treatment.get('brine_disposal_cost_per_m3', 0.0)
row['brine_disposal_cost'] = brine_cost
row['groundwater_cost'] = row.get('groundwater_cost', 0.0) + brine_cost
```

This requires threading the new config value through to the treatment dict. In
`compute_water_supply()`, add `brine_disposal_cost_per_m3` to the `treatment`
dict built from system config (around line 831).

**`src/water.py` — `_dispatch_day()`** — add `brine_disposal_cost` to the
default row dict (line ~569) with initial value `0.0`.

**Output columns** — `brine_disposal_cost` becomes a new column in
`daily_water_supply.csv`. The existing `groundwater_cost` and `total_water_cost`
columns automatically include it since groundwater_cost feeds into total.

**`src/water_balance.py`** — no changes needed. `groundwater_cost` already flows
into `total_water_cost` in the balance output. Optionally surface
`brine_disposal_cost` as a separate column for transparency.

### Parameters

| Parameter | Location | Default |
|-----------|----------|---------|
| `brine_disposal_cost_per_m3` | `water_systems_base.yaml` → treatment | 0.0 (backwards compatible) |

### Validation

Run `src/water.py` as `__main__`. Confirm `brine_disposal_cost` column appears,
is zero when no treatment occurs, and equals `treatment_reject_m3 * cost_per_m3`
on treatment days. Confirm `total_water_cost` increases by the brine cost amount.

---

## 2. Tiered Municipal Water Pricing

### Current State

Municipal water uses a flat `cost_per_m3: 0.50` from `water_systems_base.yaml`.
The simulation multiplies volume by this constant in two places:

- `src/water.py` line 518: `row['municipal_cost'] = muni_vol * municipal['cost_per_m3']`
- `src/water_balance.py` line 128: `result['municipal_community_cost'] = ... * muni_cost_per_m3`

Tiered pricing data already exists in
`data/prices/water/historical_municipal_water_prices-research.csv` with 3 USD
tiers per year (2015-2024), but is not connected to the simulation.

### Design Decisions

**Tier boundaries** — Egypt's municipal tiers are defined per-household
per-month (0-10, 11-20, 21-30 m3). For a community farm, the relevant unit is
total monthly municipal consumption for the irrigation system. Tier boundaries
should be configurable in absolute m3/month terms, not per-household.

**Tier scope** — Two separate municipal streams exist: irrigation
(`municipal_to_tank_m3`) and community buildings (`municipal_community_m3`).
Options:

- (a) Tier them jointly (single meter) — simpler, more realistic for a small community
- (b) Tier them independently — cleaner separation

Recommend (a): joint metering. Community building water is relatively small and
constant; combining them reflects a single municipal connection point.

**Time basis** — Tiers reset monthly, matching the existing `monthly_cap_m3`
enforcement cycle.

### What Changes

**`settings/water_policy_base.yaml`** — replace flat pricing with tiered config:

```yaml
# --- Municipal Pricing ---
# Tiered block pricing: cost per m3 increases with monthly consumption.
# Boundaries are cumulative monthly volume thresholds (m3).
# The rate applies to all volume within that block.
# Final tier rate applies to all volume above the last boundary.
municipal_pricing:
  mode: tiered            # flat | tiered
  flat_rate: 0.50         # used when mode=flat (backwards compatible)
  tiers:
    - { up_to_m3: 200, cost_per_m3: 0.30 }
    - { up_to_m3: 500, cost_per_m3: 0.50 }
    - { up_to_m3: null, cost_per_m3: 0.80 }   # null = unlimited
```

**`src/water.py`** — new internal helper:

```python
def _tiered_cost(volume_m3, used_this_month, tiers):
    """Compute cost for a volume increment under tiered pricing.

    Args:
        volume_m3: Volume to price (today's municipal draw).
        used_this_month: Municipal volume already consumed this month.
        tiers: List of dicts with up_to_m3 and cost_per_m3.

    Returns:
        Total cost for this volume increment.
    """
```

The function walks through tier boundaries, prices each slice of volume at the
applicable rate based on where `used_this_month` falls in the tier schedule, and
returns the total cost.

**`src/water.py` — `_dispatch_day()` and `_source_water()`** — replace
`muni_vol * municipal['cost_per_m3']` with `_tiered_cost(muni_vol,
muni_used_month, tiers)`. This requires passing the monthly municipal
accumulator and tier config into `_dispatch_day` via the existing
`muni_cap_state` dict (add `tiers` and `pricing_mode` keys).

**`src/water.py` — `_run_simulation()`** — load tier config from policy and
thread it through the simulation loop. The `muni_used_month` accumulator already
exists (line 747).

**`src/water.py` — `compute_water_supply()`** — parse the new
`municipal_pricing` section from water_policy.yaml when present. Fall back to
flat pricing when absent or `mode: flat`.

**`src/water_balance.py`** — community municipal cost also needs tiered pricing.
Since community water goes through the same municipal connection, its cost should
be computed using the same tiered function with the cumulative monthly volume
that includes irrigation municipal draws. This requires either:

- Passing the daily irrigation municipal volume back to the balance module so it
  can compute the combined tier position, or
- Computing community municipal cost inside `src/water.py` as part of the
  dispatch loop (preferred — keeps all pricing logic in one place)

Recommend: add `community_water_demand_m3` as an optional column in
`irrigation_demand_df` (or a separate argument). The dispatch loop prices both
irrigation and community municipal draws through the same tiered function.

### Parameters

| Parameter | Location | Default |
|-----------|----------|---------|
| `municipal_pricing.mode` | `water_policy_base.yaml` | `flat` |
| `municipal_pricing.flat_rate` | `water_policy_base.yaml` | 0.50 |
| `municipal_pricing.tiers[].up_to_m3` | `water_policy_base.yaml` | — |
| `municipal_pricing.tiers[].cost_per_m3` | `water_policy_base.yaml` | — |

### Output Columns

No new columns. `municipal_cost` (renamed `municipal_irrigation_cost` in
water_balance) and `municipal_community_cost` remain the same columns but now
reflect tiered pricing. Optionally add `municipal_effective_rate` (cost / volume)
to surface the blended rate for analysis.

### Validation

1. `mode: flat` produces identical results to current baseline (regression check)
2. With 3 tiers, monthly cost accumulates non-linearly — verify by computing
   expected cost for a known monthly volume against the tier schedule
3. Verify tier resets at month boundaries
4. Verify combined irrigation + community volume hits higher tiers than either alone

---

## 3. Growth-Stage Deficit Irrigation (RDI)

### Current State

**What exists:**

- `growth_stage` column in all 72 crop growth CSVs (values: `initial`,
  `development`, `mid`, `late`)
- Stage durations in `crop_coefficients-research.csv` (days per stage per crop)
- Whole-season Ky in `yield_response_factors-research.csv` (one scalar per crop)
- 5 static irrigation policies with uniform season-long fractions:
  `full_eto` (1.0), `optimal_deficit` (crop-specific, 0.75-0.85),
  `deficit_80` (0.80), `deficit_60` (0.60), `rainfed` (0.00)
- Generator script applies fraction uniformly across all growth stages

**What's missing:**

- Per-stage Ky values as structured data (mentioned in notes text only)
- Stage-variable irrigation fractions in the generator
- Stage-weighted yield penalty in `src/crop_yield.py`
- RDI policy option in `water_policy_base.yaml`

### Design

RDI works by restricting water during stress-tolerant stages (initial, late) and
providing full irrigation during stress-sensitive stages (development, mid for
most crops; flowering/fruit-set specifically). The implementation has two layers:

**Layer A: Pre-computed RDI lookup tables (generator script)**

Add a new irrigation policy `rdi` (regulated deficit irrigation) to the
generator. Instead of a single fraction, use a per-stage fraction dict:

```python
RDI_STAGE_FRACTIONS = {
    "tomato":   {"initial": 0.70, "development": 1.00, "mid": 1.00, "late": 0.60},
    "potato":   {"initial": 0.75, "development": 1.00, "mid": 1.00, "late": 0.65},
    "onion":    {"initial": 0.70, "development": 1.00, "mid": 1.00, "late": 0.70},
    "kale":     {"initial": 0.60, "development": 0.90, "mid": 1.00, "late": 0.60},
    "cucumber": {"initial": 0.70, "development": 1.00, "mid": 1.00, "late": 0.60},
}
```

The generator's `simulate_season()` function (line ~323) replaces:
```python
water_from_irrig = etc * irrig_fraction
```
with:
```python
water_from_irrig = etc * stage_fractions[current_growth_stage]
```

This produces new rows in every crop growth CSV with `irrigation_policy = rdi`.

**Layer B: Per-stage Ky for dynamic yield computation**

Add per-stage Ky columns to `yield_response_factors-research.csv`:

```csv
crop, ky_whole_season, ky_initial, ky_development, ky_mid, ky_late, wue_curvature, source, notes
tomato,    1.05,            0.40,       0.70,            1.10,   0.20,    3.5,           FAO 33, Table 12
potato,    1.10,            0.45,       0.70,            0.80,   0.20,    3.5,           FAO 33, Table 12
onion,     1.10,            0.45,       0.70,            0.80,   0.30,    3.5,           FAO 33, Table 12
kale,      0.95,            0.35,       0.60,            1.00,   0.20,    3.5,           estimated from leafy greens
cucumber,  1.00,            0.40,       0.65,            1.00,   0.20,    3.5,           estimated from cucurbits
```

Values sourced from FAO Irrigation and Drainage Paper 33, Table 12
(Doorenbos & Kassam 1979). Per-stage Ky reflects the crop's sensitivity to
water stress during that specific growth period.

**Layer C: Stage-weighted yield penalty in `src/crop_yield.py`**

Currently `compute_harvest_yield()` computes a single whole-season f = ETa/ETc
and applies:

```python
yield_kg_ha = potential_yield * f**(1/alpha) * avg_Kt
```

For stage-weighted computation, split the season into stages and compute per-stage
stress ratios:

```python
# For each stage s in [initial, development, mid, late]:
#   f_s = ETa_stage_s / ETc_stage_s
#   ya_s = (1 - ky_s * (1 - f_s))      # FAO 33 multiplicative form
# Combined: yield_factor = product(ya_s for all stages)
# yield_kg_ha = potential_yield * yield_factor * avg_Kt
```

This uses the multiplicative FAO 33 formulation for multi-stage deficit, where
yield reductions from each stage compound. The whole-season power-law form
(currently used) remains available as a fallback when per-stage Ky data is absent.

**Layer D: Policy configuration**

Add `rdi` as a valid `static_policy` value in `water_policy_base.yaml`:

```yaml
irrigation:
  mode: static
  static_policy: rdi        # NEW — regulated deficit irrigation
```

For dynamic mode, add an optional `rdi_schedule` section:

```yaml
irrigation:
  mode: dynamic
  rdi_schedule:             # optional — only used in dynamic mode
    tomato:
      initial: 0.70
      development: 1.00
      mid: 1.00
      late: 0.60
```

When `rdi_schedule` is present in dynamic mode, the demand baseline uses
stage-variable fractions instead of full_eto. The water system then delivers
what it can, and `compute_harvest_yield()` uses per-stage Ky for the yield
penalty.

### Implementation Steps

1. Add per-stage Ky columns to `yield_response_factors-research.csv`
2. Add `RDI_STAGE_FRACTIONS` dict and `rdi` policy to `generate_crop_lookup.py`
3. Modify `simulate_season()` to accept stage-keyed fractions
4. Regenerate all 72 crop growth CSVs (adds `rdi` rows to each file)
5. Add `rdi` to valid `static_policy` values in `_load_water_policy()` in
   `src/irrigation_demand.py`
6. Modify `compute_harvest_yield()` in `src/crop_yield.py` to support
   stage-weighted yield penalty when per-stage Ky is available
7. Update `water_policy_base.yaml` comments to document `rdi` option
8. Update `specs/water_system_specification.md` to document the RDI extension

### Parameters

| Parameter | Location | Default |
|-----------|----------|---------|
| `ky_initial` | `yield_response_factors-research.csv` | crop-specific |
| `ky_development` | `yield_response_factors-research.csv` | crop-specific |
| `ky_mid` | `yield_response_factors-research.csv` | crop-specific |
| `ky_late` | `yield_response_factors-research.csv` | crop-specific |
| `rdi_schedule` | `water_policy_base.yaml` | None (optional) |

### Validation

1. `static_policy: rdi` produces lower total demand than `full_eto` but higher
   than `deficit_80` (RDI targets ~85-90% of full demand by protecting sensitive
   stages)
2. Yield under `rdi` is higher than `deficit_80` despite similar total water use
   (this is the value proposition of RDI)
3. Per-stage ETa/ETc ratios in the crop growth CSVs vary by stage (not uniform)
4. `static_policy: full_eto` remains unchanged (regression check)
5. Dynamic mode with `rdi_schedule` produces stage-variable demand baselines

---

## 4. Agrivoltaic ET Reduction — Verification Only

### Finding

ETc is already fully precomputed for all four growing conditions:

- `openfield` — unshaded reference
- `underpv_low` — 30% panel ground coverage
- `underpv_medium` — 50% panel ground coverage
- `underpv_high` — 80% panel ground coverage

The pipeline works end-to-end:

1. `data/weather/pv_microclimate_factors-research.csv` provides per-density
   ET reduction multipliers and temperature adjustments
2. `data/_scripts/generate_crop_lookup.py` applies these to compute
   condition-specific ETc using a double-counting-safe formula
3. Each crop has 4 CSV variants per planting date (one per condition)
4. `settings/farm_profile_base.yaml` assigns conditions per field
5. `src/irrigation_demand.py` loads the correct condition-specific CSV via
   the filename pattern `{crop}_{planting}_{condition}-research.csv`

ETc differences are substantial. Example (tomato, day 1, full_eto):

| Condition | etc_mm |
|-----------|--------|
| openfield | 7.14 |
| underpv_low | 6.07 |
| underpv_high | 3.93 |

### Action

No code changes needed. Verify by running the simulation with fields set to
different conditions and confirming demand varies accordingly.

---

## Implementation Order

```
1. Brine disposal cost        (smallest change, self-contained)
2. Tiered municipal pricing   (moderate, touches dispatch loop)
3. Growth-stage deficit / RDI (largest, touches data pipeline + yield model)
4. Agrivoltaic ET reduction   (verification only)
```

Items 1 and 2 are independent and can be implemented in parallel.
Item 3 depends on regenerating crop growth CSVs, so it has a longer lead time.
