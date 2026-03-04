# Deficit Irrigation Policies Do Not Reduce Water Demand

**Date**: 2026-03-04
**Status**: Bug confirmed
**Severity**: High -- deficit irrigation policies have no effect on water system sizing, cost, or energy in static mode
**Discovered via**: Stress test W13 (deficit_60 policy produces identical water demand to full_eto)

## Summary

When `irrigation.mode = static` and `irrigation.static_policy = deficit_60` (or `deficit_80`, `optimal_deficit`, `rainfed`), the irrigation demand module requests the same water volume as `full_eto`. The deficit policy filters the correct rows from the crop growth CSV but then reads the `etc_mm` column (biological crop water need, identical across all policies) instead of `water_applied_mm` (actual water the deficit policy delivers). As a result, the water dispatch system sources, treats, pumps, and stores full crop water requirements regardless of the chosen deficit policy. The deficit policy only affects post-harvest yield computation in `src/crop_yield.py`, which is a separate module that runs after the water balance.

## Detailed Code Trace

### 1. Policy resolution: `_load_water_policy()` (irrigation_demand.py, lines 39-49)

When `mode = static`, this function correctly returns the `static_policy` value (e.g., `'deficit_60'`). This string is passed through `compute_irrigation_demand()` (line 190) to `_compute_field_demand()` (line 208) and finally to `_load_daily_etc()` (line 110-111).

### 2. The bug: `_load_daily_etc()` (irrigation_demand.py, lines 77-88)

```python
def _load_daily_etc(growth_dir, crop, planting, condition, irrigation_policy):
    path = growth_dir / crop / f"{crop}_{planting}_{condition}-research.csv"
    df = pd.read_csv(path, comment='#', parse_dates=['date'])
    df = df[df['irrigation_policy'] == irrigation_policy]  # line 85: filters correctly
    result = df[['date', 'etc_mm']].copy()                 # line 86: BUG -- reads etc_mm
    result['crop'] = crop
    return result
```

Line 85 correctly filters to the `deficit_60` rows. But line 86 extracts `etc_mm`, which is the **biological crop evapotranspiration** -- a property of the crop, weather, and growth stage that does not vary by irrigation policy. The column that varies is `water_applied_mm`.

### 3. Verified: `etc_mm` is identical across policies

From the crop growth CSV `data/crops/crop_daily_growth/tomato/tomato_feb15_openfield-research.csv`:

| irrigation_policy | date       | etc_mm | water_applied_mm |
|-------------------|------------|--------|------------------|
| full_eto          | 2010-02-15 | 3.71   | 3.71             |
| deficit_60        | 2010-02-15 | 3.71   | 2.22             |

The `etc_mm` column is identical (3.71 mm) across all five irrigation policies. The `water_applied_mm` column reflects the policy: deficit_60 applies approximately 60% of ETc (2.22 / 3.71 = 0.598).

### 4. Demand scaling: `_compute_field_demand()` (irrigation_demand.py, lines 91-127)

```python
combined[col_demand] = (combined['etc_mm'] * area_ha * 10 / efficiency).round(3)  # line 124
```

This uses the `etc_mm` values from `_load_daily_etc()`, so the demand is identical for all policies.

### 5. Water dispatch consumes this demand unchanged

In `src/water_balance.py` (line 207-213), `compute_irrigation_demand()` feeds directly into `compute_water_supply()`. The water dispatch system in `src/water.py` (line 1329) receives `demand_row['total_demand_m3']` as the daily demand to fulfill. It has no knowledge of the irrigation policy and no way to reduce the demand.

### 6. Crop yield uses a separate pathway

In `src/crop_yield.py`, `compute_harvest_yield()` (line 109-180) takes `delivered_m3_series` and `demand_m3_series` from the water balance. It computes `f = ETa_season / ETc_season` (line 165). Since the water system supplies full ETc and the tank delivers it all, `f` approaches 1.0 regardless of the chosen deficit policy. The deficit policy has no effect on yield either.

## Impact

For static mode with deficit policies:

- **Water cost**: Overstated. The system sources, treats, and pumps 100% of crop water need instead of 60% (for deficit_60).
- **Energy**: Overstated. Pumping, treatment, and application energy scale with volume.
- **Tank sizing**: Oversized. Peak demand that drives tank capacity is inflated.
- **Yield**: Incorrect. The yield model receives `delivered = demand` (near-100% delivery) when the deficit policy should produce 60% delivery, leading to full yield instead of the reduced yield the deficit policy is designed to produce.
- **Scenario comparisons**: All deficit policies produce identical results to `full_eto`, making static-mode policy comparisons meaningless.

## Contradiction in Documentation

The YAML comment in `settings/water_policy_base.yaml` (line 11) states:

> `ETc demand reflects the chosen policy`

This implies that when using `deficit_60`, the demand presented to the water system should be 60% of ETc. But the code reads `etc_mm` (100% ETc) regardless of policy. The specification in `specs/farming_crop_yield_specification.md` (line 461) documents the current (buggy) behavior:

> Extracts the `etc_mm` column (daily crop evapotranspiration).

The YAML comment describes the intended behavior. The specification describes the actual (buggy) behavior.

## Root Cause

The function `_load_daily_etc()` was likely written with only the `full_eto` policy in mind, where `etc_mm == water_applied_mm`. When deficit policies were added to the crop growth CSVs, the demand module was not updated to use `water_applied_mm`. The function name itself -- `_load_daily_etc` -- reveals the assumption: it was always intended to load ETc, not the policy-adjusted water application.

## Recommended Fix

In `src/irrigation_demand.py`, modify `_load_daily_etc()` to read `water_applied_mm` instead of `etc_mm`. This is the column that reflects the irrigation policy's actual water delivery:

```python
def _load_daily_etc(growth_dir, crop, planting, condition, irrigation_policy):
    path = growth_dir / crop / f"{crop}_{planting}_{condition}-research.csv"
    df = pd.read_csv(path, comment='#', parse_dates=['date'])
    df = df[df['irrigation_policy'] == irrigation_policy]
    result = df[['date', 'water_applied_mm']].copy()
    result = result.rename(columns={'water_applied_mm': 'etc_mm'})  # keep downstream column name
    result['crop'] = crop
    return result
```

Alternatively, rename the internal column to `water_mm` or `applied_mm` throughout and update `_compute_field_demand()` accordingly, since the value is no longer pure ETc when a deficit policy is active.

Additional changes required:

1. **Rename function**: `_load_daily_etc` should become `_load_daily_water_applied` or similar to reflect its actual purpose.
2. **Update module docstring** (line 8): Change `Delivery demand = ETc (mm/ha) * area (ha) * 10 / irrigation_efficiency` to reference `water_applied_mm`.
3. **Update column naming**: The output column `{field}_etc_mm_per_ha` is misleading when the value is `water_applied_mm`. Consider renaming to `{field}_water_applied_mm_per_ha` or `{field}_irrigation_mm_per_ha`.
4. **Update spec**: `specs/farming_crop_yield_specification.md` line 461 and 466 should reference `water_applied_mm`.
5. **Crop yield integration**: Verify that `compute_community_harvest()` in `src/crop_yield.py` still works correctly. It reads `{field}_demand_m3` and `{field}_delivered_m3` from the water balance. With the fix, `demand_m3` will already reflect the deficit policy, so the yield model's `f = ETa/ETc` ratio will need adjustment -- the demand column will no longer represent pure ETc. This requires careful design consideration: should the yield model receive full_eto demand as its ETc reference regardless of policy? If so, both the full_eto demand and the policy-adjusted demand need to be available in the water balance output.

## Design Consideration for the Fix

There is a subtlety in how the yield model uses demand. Currently `compute_harvest_yield()` (crop_yield.py, line 126-127) documents:

> `demand_m3_series`: pd.Series of **full_eto demand** for field (m3/day).

The FAO yield response function requires the ratio `ETa_actual / ETc_potential`. If the demand column is changed to reflect `water_applied_mm` (deficit-adjusted), then the yield model would need a separate column carrying the full_eto ETc for its denominator. The cleanest approach is:

- **Demand column** (`{field}_demand_m3`): Use `water_applied_mm` -- this is what the water system should source.
- **New reference column** (`{field}_etc_m3`): Use `etc_mm` -- this is the biological ETc the yield model needs as its denominator.

This ensures the water system sources only what the deficit policy requires, while the yield model still has access to the full crop water need for computing the water-yield response.
