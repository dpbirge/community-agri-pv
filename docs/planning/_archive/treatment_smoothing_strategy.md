# Treatment Smoothing Strategy — Implementation Plan

**Date:** 2026-03-03
**Scope:** New `maximize_treatment_efficiency` dispatch strategy for `src/water.py`

## Problem Statement

BWRO treatment plants operate most efficiently at 70-85% utilization (the "sweet
spot"). The current dispatch logic is reactive — it treats only enough water to
meet each day's demand. Because irrigation demand varies widely (peak days 2-3x
average, fallow days at zero), treatment utilization swings across the full
efficiency curve, incurring energy penalties up to 1.4x and maintenance penalties
up to 1.3x on off-target days.

A storage tank can decouple treatment production rate from field consumption rate.
By running the treatment plant at a steady rate and letting the tank absorb the
daily variance, most treatment days land in the sweet spot.

## Design Principles

1. **Zero changes to existing strategies.** The three demand-matching strategies
   (`minimize_cost`, `minimize_treatment`, `minimize_draw`) must produce
   bit-identical output before and after this change. All new code is additive.

2. **Strategy controls volume, not plumbing.** The only thing that differs between
   demand-matching and treatment-smoothing is *how much* water is sourced each day.
   All shared infrastructure (tank model, TDS blending, flushes, cap enforcement,
   energy/cost accounting) is reused without modification.

3. **Source priority is a separate parameter.** Treatment smoothing determines the
   daily source volume. Which taps open first (GW vs. municipal) is controlled by
   a `source_priority` field that defaults to `minimize_cost`. This lets users
   combine smoothing with any source ordering.

4. **Pre-computation is explicit.** The target treatment rate is computed once
   before the simulation loop from the full demand series. It is stored in the
   policy dict and passed through the existing plumbing — no new global state.

## Architecture Overview

```
_run_simulation()
  │
  ├─ PRE-COMPUTATION (new, smoothing only)
  │   └─ _compute_treatment_target(demand_df, wells, treatment, tank_capacity, policy)
  │       → policy['_treatment_target_m3']   # daily treatment feed target
  │
  └─ DAILY LOOP (existing structure, one new branch point)
      │
      ├─ Step 1: Safety flush                          ← SHARED, unchanged
      ├─ Step 2: Draw from tank                        ← SHARED, unchanged
      ├─ Step 3: Compute source volume                 ← STRATEGY BRANCH
      │   ├─ demand-matching: source_vol = demand_remaining
      │   └─ smoothing: source_vol = _effective_treatment_target(target, tank, demand_remaining)
      ├─ Step 4: _source_water(source_vol, ..., priority)  ← SHARED, unchanged
      ├─ Step 5: Draw fresh from tank                  ← SHARED, unchanged
      ├─ Step 6: Surplus/prefill                       ← MINOR BRANCH
      │   ├─ demand-matching: _prefill_tank (existing)
      │   └─ smoothing: no-op (surplus already in tank from step 3)
      └─ Step 7: Look-ahead drain                      ← SHARED, unchanged
```

Only steps 3 and 6 have strategy-dependent branches. Everything else is shared.

## File-by-File Changes

### 1. `settings/water_policy_base.yaml` — Config additions

Add treatment smoothing parameters alongside existing policy fields. These are
only read when `strategy: maximize_treatment_efficiency`.

```yaml
strategy: minimize_cost     # unchanged default

# Treatment smoothing parameters.
# Read only when strategy = maximize_treatment_efficiency.
# Ignored by demand-matching strategies.
treatment_smoothing:
  target_utilization: 0.80        # fraction of rated BWRO capacity (0.0-1.0)
  source_priority: minimize_cost  # source ordering: minimize_cost | minimize_treatment | minimize_draw
  fallow_treatment: true          # continue treating during fallow days to build buffer
  fallow_horizon_days: 14         # only treat through fallow if next active day is within N days
  tank_feedback:
    high_mark: 0.90               # tank fill fraction above which treatment throttles down
    low_mark: 0.15                # tank fill fraction below which treatment boosts up
```

**Backwards compatibility:** Existing policy files without `treatment_smoothing`
work unchanged — the section is only parsed when the strategy requires it.

### 2. `src/water.py` — Core dispatch changes

#### 2a. New internal helper: `_compute_treatment_target`

Location: new function, placed after `_prefill_tank` (around line 703).

Purpose: Pre-compute the daily treatment feed target from the full demand series
before the simulation loop starts. Called once, not per-day.

```
def _compute_treatment_target(demand_df, raw_gw_tds, treatment, tank_capacity_m3,
                               smoothing_cfg):
    """Compute the steady-state daily treatment feed target.

    Analyzes the full demand series to find a constant treatment rate that:
    - Produces enough treated water to meet season-total treated demand
    - Falls within the BWRO sweet spot (70-85% of rated capacity)
    - Is feasible given tank capacity as buffer

    Args:
        demand_df: Full demand DataFrame with total_demand_m3, crop_tds_requirement_ppm.
        raw_gw_tds: Volume-weighted raw groundwater TDS across all wells.
        treatment: Treatment config dict (goal_output_tds_ppm, throughput_m3_hr, lookup_df).
        tank_capacity_m3: Storage tank capacity.
        smoothing_cfg: Dict from policy['treatment_smoothing'].

    Returns:
        Daily treatment feed target (m3). This is feed volume, not product volume.
    """
```

Logic:
1. Compute f_treat from raw_gw_tds vs. strictest crop TDS requirement and
   treatment goal TDS (same formula as `_gw_source`).
2. Compute recovery rate from treatment lookup for the raw GW TDS band.
3. Total season treated product = sum(daily_demand * f_treat) for active days.
4. Total season feed = total_treated_product / recovery_rate.
5. Divide by total days (including fallow if `fallow_treatment: true`, else
   active days only) to get avg_daily_feed.
6. Clamp to sweet spot: max(0.70 * max_daily_feed, min(0.85 * max_daily_feed,
   avg_daily_feed)).
7. Validate: check that tank_capacity is sufficient to buffer the cumulative
   surplus. Log a warning if the tank is undersized but do not fail — the
   tank feedback loop handles overflow gracefully.

#### 2b. New internal helper: `_effective_treatment_target`

Location: new function, placed after `_compute_treatment_target`.

Purpose: Modulate the pre-computed target rate based on current tank level.
Called once per day during the dispatch loop.

```
def _effective_treatment_target(base_target_m3, tank, demand_remaining,
                                 max_daily_feed_m3, smoothing_cfg):
    """Adjust treatment target based on tank fill level.

    Uses proportional feedback to prevent tank overflow (throttle when full)
    and tank depletion (boost when empty). On fallow days, sources at target
    rate if fallow_treatment is enabled and horizon check passes.

    Args:
        base_target_m3: Pre-computed daily treatment feed target.
        tank: Current tank state dict (fill_m3, capacity_m3).
        demand_remaining: Today's unmet demand after tank draw.
        max_daily_feed_m3: Treatment rated capacity * 24.
        smoothing_cfg: Dict with tank_feedback.high_mark, low_mark.

    Returns:
        Effective source volume for today (m3). This is the volume
        passed to _source_water — it includes both treated and untreated
        GW product plus any municipal needed for TDS correction.
    """
```

Logic:
1. Compute tank_fill_fraction = tank['fill_m3'] / tank['capacity_m3'].
2. If fill_fraction > high_mark: proportionally reduce target toward
   demand_remaining (don't overfill).
   `throttle = (1.0 - fill_fraction) / (1.0 - high_mark)`
   `effective = demand_remaining + (base_target - demand_remaining) * throttle`
3. If fill_fraction < low_mark: proportionally boost toward max capacity.
   `boost = (low_mark - fill_fraction) / low_mark`
   `effective = base_target + (max_daily_feed - base_target) * boost`
4. Otherwise: use base_target.
5. Ensure effective >= demand_remaining (always try to meet today's demand).
6. Cap at tank headroom (can't source more than the tank can hold).

#### 2c. Modified `_dispatch_day` — One branch point at step 3

Location: lines 841-844 of current code (the "source shortfall" block).

Current code:
```python
# Source only the shortfall — never fill past today's demand
if demand_remaining > 0:
    _source_water(demand_remaining, tds_req, wells, treatment, municipal,
                  tank, gw_cap_state, muni_cap_state, row, strategy)
```

New code (replaces the above block):
```python
# Step 3: Compute source volume — strategy-dependent
if strategy == 'maximize_treatment_efficiency':
    source_vol = _effective_treatment_target(
        policy['_treatment_target_m3'], tank, demand_remaining,
        treatment['throughput_m3_hr'] * 24, policy.get('treatment_smoothing', {}))
    source_priority = policy.get('treatment_smoothing', {}).get(
        'source_priority', 'minimize_cost')
else:
    source_vol = demand_remaining
    source_priority = strategy

if source_vol > 0:
    _source_water(source_vol, tds_req, wells, treatment, municipal,
                  tank, gw_cap_state, muni_cap_state, row, source_priority)
```

This is the only change to `_dispatch_day`'s main flow. The existing strategies
pass through identically — `source_vol = demand_remaining` and
`source_priority = strategy` reproduce the current behavior exactly.

**Fallow day handling:** The current early-return on fallow days (line 804) must
be modified for smoothing. When `fallow_treatment: true`, fallow days should
still source water at the target rate (with zero demand). Add a condition:

```python
if demand_m3 <= 0 or math.isnan(tds_req):
    if strategy != 'maximize_treatment_efficiency' or not policy.get(
            'treatment_smoothing', {}).get('fallow_treatment', False):
        return row, tank
    # Smoothing: continue to source at target rate even on fallow days.
    # Use the last known TDS requirement for blending.
```

The fallow horizon check (`fallow_horizon_days`) scans ahead to verify that
active irrigation resumes within N days. If not, skip treatment on this fallow
day to avoid wasting energy on water that will sit too long or overflow.

#### 2d. Modified step 6 — Skip prefill for smoothing

The existing prefill block (lines 858-867) should be skipped when using the
smoothing strategy, since the target-rate sourcing in step 3 already handles
buffer accumulation:

```python
# Look-ahead prefill: buffer water for upcoming peak days
if strategy != 'maximize_treatment_efficiency':
    prefill_vol = 0.0
    if (policy.get('prefill_enabled', False)
            and upcoming_demands
            and tank['capacity_m3'] - tank['fill_m3'] > 1.0):
        prefill_vol = _prefill_tank(...)
    row['prefill_m3'] = prefill_vol
```

#### 2e. Modified `_run_simulation` — Pre-computation step

Location: lines 901-928, before the daily loop.

Add after existing setup (line 928, before `for i, ...`):

```python
# Pre-compute treatment target for smoothing strategy
if policy.get('strategy') == 'maximize_treatment_efficiency':
    raw_gw_tds = _volume_weighted_tds(wells, sum(w['max_daily_m3'] for w in wells))
    smoothing_cfg = policy.get('treatment_smoothing', {})
    policy['_treatment_target_m3'] = _compute_treatment_target(
        demand_df, raw_gw_tds, treatment, tank['capacity_m3'], smoothing_cfg)
    logger.info('Treatment smoothing target: %.1f m3/day feed (%.0f%% utilization)',
                policy['_treatment_target_m3'],
                policy['_treatment_target_m3'] / (treatment['throughput_m3_hr'] * 24) * 100)
```

#### 2f. Modified `compute_water_supply` — Parse smoothing config

Location: the public `compute_water_supply` function, where it builds the
policy dict from YAML.

Add parsing for the `treatment_smoothing` section:

```python
policy = {
    'strategy': water_policy.get('strategy', 'minimize_cost'),
    'prefill_enabled': water_policy.get('prefill', {}).get('enabled', False),
    'prefill_look_ahead_days': water_policy.get('prefill', {}).get('look_ahead_days', 3),
}

# Treatment smoothing config (only used by maximize_treatment_efficiency)
if policy['strategy'] == 'maximize_treatment_efficiency':
    smoothing = water_policy.get('treatment_smoothing', {})
    policy['treatment_smoothing'] = {
        'target_utilization': smoothing.get('target_utilization', 0.80),
        'source_priority': smoothing.get('source_priority', 'minimize_cost'),
        'fallow_treatment': smoothing.get('fallow_treatment', True),
        'fallow_horizon_days': smoothing.get('fallow_horizon_days', 14),
        'tank_feedback': smoothing.get('tank_feedback', {
            'high_mark': 0.90,
            'low_mark': 0.15,
        }),
    }
```

### 3. `src/water_sizing.py` — Storage sizing for smoothing

No changes required for phase 1. The existing `_size_storage` formula works
because the tank feedback loop in `_effective_treatment_target` handles
undersized tanks gracefully (throttles treatment when full, boosts when empty).

Phase 2 (optional follow-up): Add `_size_storage_for_smoothing` that computes
required capacity from the cumulative surplus/deficit curve. This would be called
by `optimize_water_system` when the strategy is `maximize_treatment_efficiency`.

### 4. `src/water_balance.py` — No changes

The orchestrator calls `compute_water_supply` and composes its output. It is
strategy-agnostic — it reads whatever columns the supply module produces. No
changes needed.

### 5. Output columns — No new columns

The smoothing strategy produces the same output columns as demand-matching
strategies. The observable differences are:

- `treatment_feed_m3` is steadier (less variance day-to-day)
- `tank_volume_m3` shows larger swings (buffer accumulation and depletion)
- `prefill_m3` is 0 (smoothing doesn't use prefill)
- `policy_strategy` reads `maximize_treatment_efficiency`

Optionally add two diagnostic columns for smoothing analysis:
- `treatment_target_m3` — the pre-computed target for this day
- `treatment_utilization_pct` — actual feed / max feed * 100

These are useful for plotting but not required for correctness.

## Fallow Day Logic — Detail

The trickiest part of the implementation is handling fallow days (no irrigation
demand, TDS requirement is NaN).

**Current behavior:** `_dispatch_day` returns immediately on fallow days. The
tank sits idle.

**Smoothing behavior:** Treatment continues on fallow days to build buffer,
subject to two guards:

1. **Horizon check:** Scan forward from current day. If no active irrigation day
   exists within `fallow_horizon_days`, skip treatment. This prevents treating
   water during long off-seasons when the tank would overflow or water would
   stagnate.

2. **TDS requirement:** Fallow days have NaN TDS requirement. Use the *next
   active day's* TDS requirement for blending decisions. If no future TDS
   requirement is known, use the treatment goal TDS (400 ppm) — the strictest
   practical value — as a conservative fallback.

3. **Tank overflow guard:** `_effective_treatment_target` already caps source
   volume at tank headroom. On fallow days with a full tank, treatment
   naturally stops.

Implementation: Modify the early-return block in `_dispatch_day` (line 804).
For the smoothing strategy, instead of returning, set `demand_m3 = 0` and
`tds_req = next_known_tds_req` and continue through the dispatch flow. The
tank draw steps (2 and 5) naturally produce zero draws when demand is zero.
Step 3 sources at the target rate. The surplus stays in the tank.

## TDS Transition Handling — Detail

When the crop TDS requirement changes (e.g., wheat at 2000 ppm followed by
tomatoes at 1200 ppm), the existing look-ahead drain (step 7) flushes the
tank if its TDS exceeds the next day's requirement.

For smoothing, this creates a tension: the strategy accumulates buffer water,
but a TDS transition dumps it all. To mitigate:

1. **Approach the transition with a low tank level.** In the days before a
   TDS transition, `_effective_treatment_target` could detect the upcoming
   stricter requirement and gradually reduce the target rate. This is a
   phase 2 enhancement — not required for initial implementation.

2. **Accept the flush as the cost of smoothing.** The flushed water still
   irrigates (it goes to the fields), so it's not truly wasted. The energy
   cost of treating water that gets flushed early is the price of running at
   a steady rate. For most scenarios this is a small fraction of total
   treatment volume.

Initial implementation: do nothing special. Let the existing flush logic
handle transitions. Log a diagnostic when smoothing water is flushed so users
can evaluate the tradeoff.

## Testing Strategy

### Regression: Existing strategies unchanged

1. Run the water balance notebook with `strategy: minimize_cost` before and
   after the change. Output DataFrames must be identical (use
   `pd.testing.assert_frame_equal`).
2. Repeat for `minimize_treatment` and `minimize_draw`.
3. Run `python -m src.water` standalone — same output check.

### New strategy: Basic correctness

4. Set `strategy: maximize_treatment_efficiency` in policy YAML.
5. Run the water balance. Verify:
   - No deficit days that don't also exist under `minimize_cost`
   - `treatment_feed_m3` has lower coefficient of variation than minimize_cost
   - `tank_volume_m3` shows accumulation during low-demand periods and
     depletion during high-demand periods
   - `total_delivered_m3.sum()` matches or exceeds the minimize_cost total

### New strategy: Sweet spot fraction

6. Compute daily treatment utilization = `treatment_feed_m3 / (throughput * 24)`.
7. Count days in 70-85% band. This fraction should be significantly higher than
   under minimize_cost.
8. Compute efficiency-weighted energy using the efficiency curve. Total energy
   should be lower than minimize_cost despite treating the same (or more) total
   volume.

### New strategy: Tank feedback

9. Set tank capacity very small (50 m3). Verify that treatment throttles down
   and the system doesn't overflow or produce excessive deficits.
10. Set tank capacity very large (5000 m3). Verify that treatment stays at
    target rate and the tank accumulates a large buffer.

### New strategy: Fallow handling

11. Set `fallow_treatment: false`. Verify zero treatment on fallow days.
12. Set `fallow_treatment: true` with `fallow_horizon_days: 7`. Verify treatment
    continues for up to 7 fallow days before an active period and stops for
    longer fallow stretches.

### Parameter sensitivity

13. Vary `target_utilization` from 0.70 to 0.85. Verify that the sweet spot
    fraction peaks near 0.80 and that energy/cost metrics improve monotonically
    as more days land in the sweet spot.
14. Vary `tank_feedback.high_mark` and `low_mark`. Verify that tighter bounds
    cause more throttling/boosting and wider bounds allow steadier treatment.

## Implementation Steps

```
Step 1: Add treatment_smoothing section to water_policy_base.yaml (commented out,
        strategy remains minimize_cost). Backwards compatible — no behavior change.

Step 2: Add _compute_treatment_target() to src/water.py. Pure function, no side
        effects, not called yet. Unit-testable in isolation.

Step 3: Add _effective_treatment_target() to src/water.py. Pure function, no side
        effects, not called yet. Unit-testable in isolation.

Step 4: Modify _dispatch_day() step 3 with the strategy branch. The demand-matching
        path is identical to current code. The smoothing path calls the new helpers.
        This is the integration point.

Step 5: Modify _dispatch_day() fallow day handling for smoothing. Add the horizon
        check and TDS fallback logic.

Step 6: Modify _dispatch_day() step 6 to skip prefill for smoothing strategy.

Step 7: Modify _run_simulation() to call _compute_treatment_target before the
        daily loop when strategy is maximize_treatment_efficiency.

Step 8: Modify compute_water_supply() to parse treatment_smoothing config from
        policy YAML.

Step 9: Run regression tests — verify minimize_cost, minimize_treatment,
        minimize_draw produce identical output.

Step 10: Switch policy to maximize_treatment_efficiency. Run water balance
         notebook. Verify correctness checks from testing strategy above.

Step 11: Add optional diagnostic columns (treatment_target_m3,
         treatment_utilization_pct) behind a flag or always-on.
```

Steps 1-3 are safe to implement and commit independently (no behavior change).
Steps 4-8 are the integration — implement together as one commit.
Steps 9-11 are validation.

## Lines of Code Estimate

| Component | New Lines | Modified Lines |
|-----------|-----------|----------------|
| `_compute_treatment_target` | ~40 | 0 |
| `_effective_treatment_target` | ~30 | 0 |
| `_dispatch_day` step 3 branch | 0 | ~10 (replace 3 lines with 10) |
| `_dispatch_day` fallow handling | 0 | ~15 (extend early-return block) |
| `_dispatch_day` step 6 branch | 0 | ~3 (wrap existing prefill in if) |
| `_run_simulation` pre-computation | ~8 | 0 |
| `compute_water_supply` config parsing | ~15 | 0 |
| `water_policy_base.yaml` | ~15 | 0 |
| **Total** | **~108** | **~28** |

No existing lines are deleted. ~28 lines are modified (extended with branches).
~108 lines are purely additive.
