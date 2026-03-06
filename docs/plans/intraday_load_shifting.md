# Intraday Load Shifting: Water System Demand Response

## Context

The intraday battery adequacy estimate (`src/intraday_estimate.py`) identifies days where the battery SOC hits its floor during pre-dawn/evening deficit hours, causing unmet demand that requires grid import. On these days, water system energy (pumping + treatment) is scheduled during daytime hours (06:00-18:00 via the water demand shape factor), but the bulk of it runs in the morning (06:00-10:00) — before peak solar generation arrives.

## Feature Request

Add a load-shifting analysis to `src/intraday_estimate.py` that, for each day flagged as insufficient, tests whether shifting the water/irrigation demand shape later in the day eliminates or reduces the unmet deficit.

## Approach

1. Define 2-3 alternative water demand shapes that shift the load toward peak solar hours:
   - `water_midday`: concentrate pumping/treatment into 10:00-16:00 (peak solar window)
   - `water_afternoon`: spread pumping into 12:00-18:00 (delayed start)
   - Keep the original `water_morning` (06:00-10:00 heavy) as baseline

2. For each insufficient day, re-run the hourly SOC simulation with each alternative water shape while keeping solar, wind, and building shapes unchanged. Record whether the shifted schedule eliminates the unmet deficit.

3. Output a summary DataFrame with columns:
   - `day`, `baseline_unmet_kwh`, `midday_unmet_kwh`, `afternoon_unmet_kwh`
   - `best_schedule` (which shape eliminates or minimizes unmet deficit)
   - `savings_kwh` (reduction in unmet deficit vs baseline)

4. Add a simple plot showing the number of insufficient days that become sufficient under each schedule, and the total unmet deficit reduction.

## Constraints

- Only analyze days already flagged as insufficient (unmet_deficit_kwh > 0) — skip sufficient days entirely.
- The shifted water shape must still deliver the same daily total water energy — only the hourly distribution changes.
- This is a screening estimate, not an operational scheduler. It answers: "would flexible pump scheduling meaningfully reduce grid dependence?"
- Keep it standalone within `src/intraday_estimate.py` — no changes to the daily simulation engine.
