# Plan: Replace Linear FAO-33 Yield Formula with Nonlinear Water-Yield Response

## Problem

The current yield calculation in `generate_crop_lookup.py` uses the FAO Paper 33 linear model:

```
Y_fresh = Y_potential × (1 − Ky × deficit) × avg_Kt
```

Where `deficit = 1 − ETactual / ETcrop`.

With Ky near 1.0, this produces constant water use efficiency (WUE = yield / water) across all irrigation policies. Field evidence and FAO Paper 66 (AquaCrop) confirm that the yield-water relationship is concave — moderate deficit irrigation increases WUE, not preserves it. The linear model is a known simplification that FAO itself replaced in 2012.

## Current Implementation

**File:** `data/_scripts/generate_crop_lookup.py`, lines 342-348

```python
if d == season_length - 1:
    deficit = (max(0.0, 1.0 - season_et_actual / season_et_crop)
               if season_et_crop > 0 else 0.0)
    ky_factor = max(0.0, 1.0 - ky * deficit)
    avg_kt = (season_sum_kt / season_day_count
              if season_day_count > 0 else 1.0)
    yield_fresh = potential_yield * ky_factor * avg_kt
```

**Current Ky values** (`crop_params/yield_response_factors-research.csv`):

| Crop     | Ky   | WUE behavior        |
|----------|------|---------------------|
| tomato   | 1.05 | Nearly constant     |
| potato   | 1.10 | Slight decrease     |
| onion    | 1.10 | Slight decrease     |
| kale     | 0.95 | Slight increase     |
| cucumber | 1.00 | Exactly constant    |

Even where Ky ≠ 1.0, the response is still linear — it tilts the line but never produces diminishing returns.

## Proposed Replacement: Quadratic Water Production Function

### Why Quadratic

| Option | Pros | Cons |
|--------|------|------|
| **Quadratic** | Simple, 1-2 params, captures concavity, well-established (Hexem & Heady 1978, Vaux & Pruitt 1983) | Less mechanistic than AquaCrop |
| Jensen multiplicative | Better for stage-specific stress interaction | Requires per-stage Ky values we don't currently use; adds complexity |
| Full AquaCrop (WP*) | Mechanistically correct, FAO-endorsed | Major rewrite; separating E/T requires soil water balance model |
| Sigmoidal (Gompertz) | Best fit for extreme deficit ranges | Overfitting risk; 3+ parameters; less literature support for vegetables |

The quadratic model is the best fit for this project's scope: educational simulation, single-season yield, existing parameter infrastructure.

### Formula

Replace the linear `ky_factor` with a quadratic water response function:

```
f = ETactual / ETcrop          (water satisfaction ratio, 0 to 1)
ky_factor = a × f² + b × f    (quadratic, forced through origin)
```

**Constraints:**
- `ky_factor(0) = 0` — zero water, zero yield (satisfied by no constant term)
- `ky_factor(1) = 1` — full water, full potential yield → `a + b = 1`
- `ky_factor'(1) = Ky` — slope at full irrigation matches FAO-33 Ky (preserves existing parameter meaning)

Solving: `2a + b = Ky` and `a + b = 1` gives:

```
a = Ky - 1
b = 2 - Ky
```

So the formula becomes:

```
ky_factor = (Ky - 1) × f² + (2 - Ky) × f
```

**Behavior by crop:**

| Crop     | Ky   | a     | b    | Shape                                          |
|----------|------|-------|------|-------------------------------------------------|
| cucumber | 1.00 | 0.00  | 1.00 | Degenerate: reduces to `f` (linear, same as now)|
| kale     | 0.95 | −0.05 | 1.05 | Concave — WUE peaks at moderate deficit         |
| tomato   | 1.05 | 0.05  | 0.95 | Slightly convex — WUE decreases under deficit   |
| potato   | 1.10 | 0.10  | 0.90 | Convex — WUE decreases under deficit            |
| onion    | 1.10 | 0.10  | 0.90 | Same as potato                                  |

**Problem:** For Ky ≥ 1.0 (tomato, potato, onion, cucumber), the quadratic is convex or linear — it does not produce the concave diminishing-returns curve that field data shows. The quadratic only helps for Ky < 1.0 (kale).

### Revised Formula: Exponent-Based Concave Model

Use a power function that always produces a concave curve:

```
f = ETactual / ETcrop
ky_factor = f ^ (1 / alpha)
```

Where `alpha` is a crop-specific curvature parameter > 1. Higher `alpha` = more concave = larger WUE gains under deficit.

**Deriving alpha from literature WUE data:**

From Daryanto et al. (2021) meta-analysis, vegetables at ~70% irrigation show ~15% WUE increase on average. Calibrating:

```
At f = 0.70: ky_factor = 0.70^(1/alpha)
WUE ratio = ky_factor / f = f^(1/alpha - 1)

For WUE_ratio(0.70) = 1.15:
0.70^(1/alpha - 1) = 1.15
(1/alpha - 1) × ln(0.70) = ln(1.15)
1/alpha - 1 = ln(1.15) / ln(0.70) = 0.1398 / (-0.3567) = -0.392
1/alpha = 0.608
alpha = 1.64
```

This gives a baseline curvature parameter. Crop-specific adjustment using Ky:

```
alpha = 1 + beta × (1.15 - Ky)
```

Where `beta` is a scaling constant. With `beta ≈ 3.5` and the meta-analysis baseline:

| Crop     | Ky   | alpha | WUE at 70% irrigation | WUE at 50% irrigation |
|----------|------|-------|-----------------------|-----------------------|
| kale     | 0.95 | 1.70  | +17%                  | +31%                  |
| cucumber | 1.00 | 1.53  | +13%                  | +24%                  |
| tomato   | 1.05 | 1.35  | +9%                   | +17%                  |
| potato   | 1.10 | 1.18  | +5%                   | +9%                   |
| onion    | 1.10 | 1.18  | +5%                   | +9%                   |

This produces:
- All crops show concave response (WUE increases under deficit), matching field evidence
- More drought-tolerant crops (lower Ky) show greater WUE gains, matching literature
- At full irrigation (f=1), `ky_factor = 1` — no change to maximum yield
- At zero irrigation (f=0), `ky_factor = 0` — zero yield preserved

### Recommended Approach: Power Function

The power function `f^(1/alpha)` is simpler than the quadratic, always concave for alpha > 1, and maps naturally to the existing Ky parameter through the alpha conversion. It requires no new CSV columns — alpha is derived from Ky at generation time.

## Implementation Steps

### Step 1: Update yield_response_factors-research.csv

Add a `wue_curvature` column (the `beta` scaling constant) alongside existing `ky_whole_season`. Default value 3.5 for all crops, adjustable per crop if calibration data warrants it.

```
crop,ky_whole_season,wue_curvature,source,notes
tomato,1.05,3.5,FAO Paper 33,"..."
potato,1.10,3.5,FAO Paper 33,"..."
onion,1.10,3.5,FAO Paper 33,"..."
kale,0.95,3.5,FAO Paper 33 cabbage proxy,"..."
cucumber,1.00,3.5,Literature consensus,"..."
```

### Step 2: Update generate_crop_lookup.py

**a) Read the new parameter** in the yield_response loading section (~line 497):

```python
crop_yield_resp = {"ky_whole_season": row["ky_whole_season"],
                   "wue_curvature": row.get("wue_curvature", 3.5)}
```

**b) Replace the linear ky_factor calculation** (~lines 342-348):

```python
if d == season_length - 1:
    f = (season_et_actual / season_et_crop
         if season_et_crop > 0 else 0.0)
    f = min(f, 1.0)  # cap at 1.0 (excess water doesn't boost yield)
    alpha = 1.0 + wue_beta * (1.15 - ky)
    alpha = max(alpha, 1.0)  # floor at 1.0 (never convex)
    ky_factor = f ** (1.0 / alpha)
    avg_kt = (season_sum_kt / season_day_count
              if season_day_count > 0 else 1.0)
    yield_fresh = potential_yield * ky_factor * avg_kt
```

**c) Pass `wue_beta` into `simulate_season()`** alongside the existing `yield_response` dict. Extract at the top of the function:

```python
ky = yield_response.get("ky_whole_season", 1.0)
wue_beta = yield_response.get("wue_curvature", 3.5)
```

**d) Update the CSV comment header** to reflect the new formula:

```
#   Yield = potential_yield * (ETa/ETc)^(1/alpha) * avg_Kt
#   where alpha = 1 + beta*(1.15 - Ky), producing concave water-yield response.
#   Replaces FAO Paper 33 linear model. See docs/planning/nonlinear_yield_model.md.
```

### Step 3: Regenerate all crop lookup tables

```bash
python data/_scripts/generate_crop_lookup.py
```

This regenerates all `data/crops/crop_daily_growth/**/*-research.csv` files with the new yield values. Daily biomass columns are unaffected — only the final-day `yield_fresh_kg_ha` changes.

### Step 4: Verify with plotting notebook

Run `data/_plotting/crop_daily_growth_check.ipynb` for each crop. The harvest yield bar chart and WUE panel should now show differentiation across irrigation policies:
- WUE should peak at moderate deficit (60-80% irrigation)
- More drought-tolerant crops (kale) should show larger WUE gains
- Full irrigation yield should be unchanged

### Step 5: Update specs/compute_flow.md

Update the Layer 3 yield specification to reference the power function model instead of the linear FAO-33 formula, and note the `wue_curvature` parameter.

## Files Modified

| File | Change |
|------|--------|
| `data/crops/crop_params/yield_response_factors-research.csv` | Add `wue_curvature` column |
| `data/_scripts/generate_crop_lookup.py` | Replace linear ky_factor with power function |
| `data/crops/crop_daily_growth/**/*.csv` | Regenerated (final yield values change) |
| `specs/compute_flow.md` | Update yield formula reference |

## References

- Doorenbos & Kassam (1979). FAO Irrigation & Drainage Paper 33.
- Steduto et al. (2012). FAO Irrigation & Drainage Paper 66 (AquaCrop).
- Fereres & Soriano (2007). Deficit irrigation for reducing agricultural water use. *J. Exp. Bot.* 58(2):147-159.
- Daryanto et al. (2021). Global meta-analysis of yield and water productivity responses of vegetables to deficit irrigation. *Sci. Rep.* 11:22095.
- Hexem & Heady (1978). Water Production Functions for Irrigated Agriculture.
- Vaux & Pruitt (1983). Crop-water production functions. *Adv. Irrigation* 2:61-97.
