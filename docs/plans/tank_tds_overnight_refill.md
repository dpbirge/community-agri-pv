# Tank TDS Overnight Refill — Implementation Plan

## Problem

The current water dispatch model handles day-to-day TDS transitions by **draining the
entire tank** when tomorrow's crop needs stricter (lower) TDS than the current tank holds.
This wastes water — 47 drain events totaling ~12,775 m3 in the baseline scenario. The
safety flush (for same-day TDS exceedance) never triggers in practice but adds complexity.

## Proposed Solution

Replace drain-and-refill with **mass-balance overnight remixing**. After today's irrigation
draw, refill the tank with water of the appropriate quality so the blended result meets
tomorrow's TDS target. No water is wasted.

### Mass Balance Formula

Given remaining tank water (`V_remain` at `TDS_tank`) and a target TDS (`TDS_target`),
the volume of refill water needed at `TDS_refill` is:

```
V_refill = V_remain × (TDS_tank - TDS_target) / (TDS_target - TDS_refill)
```

- **TDS needs to decrease** (stricter tomorrow): refill with treated water or municipal
  (`TDS_refill` < `TDS_target`). Uses BWRO product (~50 ppm) or municipal (~200 ppm).
- **TDS needs to increase** (relaxed tomorrow): refill with untreated groundwater
  (`TDS_refill` > `TDS_target`). Uses raw GW (~2400 ppm).
- **TDS already acceptable**: skip the adjustment step, proceed to normal prefill if enabled.

### Overnight Window Constraint

Refill happens during a 12-hour overnight window (fields don't irrigate at night).
All throughput limits are halved: well pumping, treatment feed, municipal flow.

### Graceful Degradation

When the required `V_refill` exceeds overnight sourcing capacity or tank headroom, the
system sources as much as it can. The tank TDS may not hit the exact target — this is
acceptable as a 1-day transition. The next morning's dispatch will use the tank as-is
(possibly with a small TDS overshoot) and the overnight step tries again.

## Implementation Steps

### Step 1: Add `_overnight_tds_refill()` helper

New function in `src/water.py`. Pure logic: computes the refill volume and quality needed,
then calls `_source_water()` with halved throughput limits.

**Signature:**
```python
def _overnight_tds_refill(tank, next_tds_req, wells, treatment, municipal,
                          gw_cap_state, muni_cap_state, row, strategy):
```

**Logic:**
1. If `next_tds_req` is NaN or tank is empty → return 0.0 (no adjustment needed).
2. If `tank['tds_ppm'] <= next_tds_req` → return 0.0 (already acceptable).
3. Compute `V_refill` from mass balance formula.
4. Choose refill source based on direction:
   - TDS too high → source treated GW or municipal (low TDS refill).
   - TDS too low → source untreated GW (high TDS refill, rare edge case).
5. Cap `V_refill` at tank headroom (`capacity_m3 - fill_m3`).
6. Cap sourcing at overnight throughput (12h window = half of 24h limits).
7. Call `_source_water()` with `target_vol=V_refill` and `tds_req=next_tds_req`.
8. Record refill volume in row as `overnight_refill_m3`.
9. Return actual volume refilled.

**Key detail — overnight throughput limits:**
Create temporary copies of `wells` and `municipal` with `max_daily_m3` and
`throughput_m3_hr` halved, OR pass an `overnight_factor=0.5` scaling param to
`_source_water`. The simpler approach is to scale `target_vol` down if it exceeds
the 12h capacity, since `_source_water` already respects per-source limits internally.
The overnight cap should be: `min(V_refill, 12h_total_capacity)` where
`12h_total_capacity = 0.5 × (sum(well.max_daily_m3) + municipal.throughput_m3_hr × 24)`.

### Step 2: Remove `_look_ahead_drain()`

- Delete the function entirely.
- Remove the call in `_dispatch_day()` (currently step 7, line ~1228).
- Remove `drain_vol` / `drain_tds` from the `deliveries` dict.
- Remove `look_ahead_drain_m3` from `_init_dispatch_row()` and `_finalize_dispatch_row()`.

### Step 3: Remove safety flush logic

- Delete lines 1139-1145 in `_dispatch_day()` (the `if tank['tds_ppm'] > tds_req` block).
- Remove `safety_flush_m3` from `_init_dispatch_row()`.
- The overnight refill from the previous day should prevent this case. If TDS is still
  slightly over (transition day), the draw proceeds anyway — the small overshoot is
  acceptable for one day.

### Step 4: Add overnight refill call to `_dispatch_day()`

Insert the new step **after prefill** (step 6) and **before finalization**:

```
# Current steps 1-6 remain the same
# ...
# 7. Overnight TDS refill for tomorrow
overnight_vol = _overnight_tds_refill(
    tank, next_tds_req, wells, treatment, municipal,
    gw_cap_state, muni_cap_state, row, source_priority)
row['overnight_refill_m3'] = overnight_vol
```

### Step 5: Update `_finalize_dispatch_row()`

- Remove references to `drain_vol`, `drain_tds`, `flush_vol`, `flush_tds`.
- Simplify `deliveries` dict to just `draw_existing` and `draw_fresh`.
- Remove `tank_flush_delivered_m3`, `safety_flush_m3`, `look_ahead_drain_m3` columns.
- Add `overnight_refill_m3` column.
- Simplify `crop_delivered = draw_existing + draw_fresh`.
- Update `policy_flush_reason` → remove or repurpose as `policy_tds_action` with values
  like `none`, `overnight_refill`, `transition_day`.

### Step 6: Update `_init_dispatch_row()`

- Remove `tank_flush_delivered_m3`, `safety_flush_m3`, `look_ahead_drain_m3` keys.
- Add `overnight_refill_m3: 0.0` key.

### Step 7: Update `src/water_balance.py`

- Remove `look_ahead_drain_m3` from `balance_check` formula (line ~177). The overnight
  refill stays in the tank (it doesn't leave), so the conservation equation becomes:
  ```
  tank[t-1] + sourced[t] - delivered[t] - tank[t] ≈ 0
  ```
  where `sourced[t]` now includes overnight refill volume.
- Remove `safety_flush_m3` and `look_ahead_drain_m3` from `_order_balance_columns()`.
- Add `overnight_refill_m3` to the appropriate column group.

### Step 8: Update output column ordering

In `compute_water_supply()` (end of `src/water.py`), update the `agg_cols` list:
- Remove `safety_flush_m3`, `look_ahead_drain_m3`, `tank_flush_delivered_m3`.
- Add `overnight_refill_m3`.

### Step 9: Validate

1. Run the water balance standalone: `python -m src.water_balance`
2. Check balance_check max ≈ 0 (conservation holds).
3. Check deficit totals (should be similar or lower than before — no more wasted water).
4. Verify no `look_ahead_drain_m3` or `safety_flush_m3` references remain.
5. Run notebook: `jupyter nbconvert --execute notebooks/simulation.ipynb`
6. Run tests: `python -m pytest tests/`

## Edge Cases to Handle

1. **Tank nearly full after irrigation**: Very little headroom for refill → accept 1-day
   transition. The overnight step sources what it can; tomorrow's dispatch draws from tank
   at slightly wrong TDS.

2. **Fallow day → active day transition**: Next day has a TDS requirement but today was
   fallow. The overnight refill still runs — it reads `next_tds_req` regardless of today's
   demand.

3. **Large TDS step-down** (e.g., new crop planted with strict TDS): May require more
   refill than one overnight window can provide. The system does its best; subsequent
   nights continue adjusting.

4. **GW TDS is already below target**: No treatment needed — untreated GW is the refill
   source and `V_refill` may be 0 or very small.

5. **Monthly cap exhaustion**: If GW or municipal caps are hit, overnight refill is
   limited. Accept transition day.

## Columns Changed

| Removed                    | Added                  |
|----------------------------|------------------------|
| `look_ahead_drain_m3`      | `overnight_refill_m3`  |
| `safety_flush_m3`          | `policy_tds_action`    |
| `tank_flush_delivered_m3`  |                        |

## Files Modified

| File                      | Changes                                           |
|---------------------------|---------------------------------------------------|
| `src/water.py`            | Add `_overnight_tds_refill()`, remove `_look_ahead_drain()`, remove safety flush, update `_dispatch_day()`, `_init_dispatch_row()`, `_finalize_dispatch_row()`, `compute_water_supply()` |
| `src/water_balance.py`    | Update `balance_check`, `_order_balance_columns()` |
| `notebooks/simulation.ipynb` | Re-run to update outputs                       |

## Not Changed

- `src/energy_balance.py` — no dependency on drain/flush columns
- `settings/water_policy_base.yaml` — no new policy keys needed (overnight refill is
  always-on behavior, not a policy toggle)
- Prefill logic — remains as-is, runs before overnight refill
- Treatment smoothing / `maximize_treatment_efficiency` strategy — unaffected
