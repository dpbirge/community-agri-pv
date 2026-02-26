#!/usr/bin/env python3
"""Generate toy daily irrigation demand profile for a 2-field, 4-crop Egyptian rotation.

Reads pre-computed daily crop growth files, extracts ETc (crop evapotranspiration)
under full-ETo irrigation / openfield conditions, averages across weather years,
and produces a 365-day seasonal demand profile with per-crop demand and daily TDS
requirements.

Rotation:
    Field A: kale (Oct 01, 85d) -> tomato (Feb 15, 135d)
    Field B: potato (Sep 15, 120d) -> onion (Jan 15, 150d)

Output:
    simulation/daily_irrigation_demand-toy.csv

Usage:
    python generate_irrigation_demand.py
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# Two fields with staggered planting, 4 crops total.
# Growth files: {crop}_{planting}_openfield-research.csv
ROTATION = [
    ("kale", "oct01"),      # Field A, fall (Oct 1 - Dec 24)
    ("tomato", "feb15"),    # Field A, winter-spring (Feb 15 - Jul 1)
    ("potato", "sep15"),    # Field B, fall (Sep 15 - Jan 12)
    ("onion", "jan15"),     # Field B, winter (Jan 15 - Jun 14)
]

IRRIGATION_POLICY = "full_eto"
CONDITION = "openfield"


def _repo_root():
    return Path(__file__).resolve().parent.parent.parent


def _load_crop_tds(params_path):
    """Load TDS no-penalty thresholds. Returns {crop_name: tds_ppm}."""
    df = pd.read_csv(params_path, comment="#")
    return dict(zip(df["crop"], df["tds_no_penalty_ppm"]))


def _load_daily_etc(growth_dir, crop, planting):
    """Load daily ETc from growth file, filter to full_eto, average by calendar day.

    Returns:
        DataFrame with columns: month, dom, {crop}_etc_mm_per_ha
    """
    path = growth_dir / crop / f"{crop}_{planting}_{CONDITION}-research.csv"
    df = pd.read_csv(path, comment="#")
    df = df[df["irrigation_policy"] == IRRIGATION_POLICY]

    dates = pd.to_datetime(df["date"])
    col = f"{crop}_etc_mm_per_ha"

    avg = (
        pd.DataFrame({"month": dates.dt.month, "dom": dates.dt.day, col: df["etc_mm"].values})
        .groupby(["month", "dom"])[col]
        .mean()
        .reset_index()
    )
    avg[col] = avg[col].round(2)
    return avg


def _build_calendar():
    """365-day calendar (non-leap year) with month and day-of-month columns."""
    dates = pd.date_range("2023-01-01", "2023-12-31", freq="D")
    return pd.DataFrame({
        "month_day": dates.strftime("%m-%d"),
        "month": dates.month,
        "dom": dates.day,
    })


def build_demand_profile(growth_dir, params_path):
    """Assemble the toy daily irrigation demand profile."""
    crop_tds = _load_crop_tds(params_path)
    cal = _build_calendar()

    etc_cols = []
    for crop, planting in ROTATION:
        avg = _load_daily_etc(growth_dir, crop, planting)
        col = f"{crop}_etc_mm_per_ha"
        etc_cols.append(col)
        cal = cal.merge(avg, on=["month", "dom"], how="left")
        cal[col] = cal[col].fillna(0.0)

    cal["total_etc_mm_per_ha"] = cal[etc_cols].sum(axis=1).round(2)

    # Min TDS requirement: lowest tds_no_penalty among crops active on each day
    tds = np.full(len(cal), np.inf)
    for crop, _ in ROTATION:
        active = cal[f"{crop}_etc_mm_per_ha"].values > 0
        tds[active] = np.minimum(tds[active], crop_tds[crop])
    tds[np.isinf(tds)] = np.nan
    cal["min_tds_requirement_ppm"] = tds

    return cal[["month_day"] + etc_cols + ["total_etc_mm_per_ha", "min_tds_requirement_ppm"]]


def _metadata_header(date_str):
    crops = "; ".join(f"{c} ({p})" for c, p in ROTATION)
    etc_cols = ", ".join(f"{c}_etc_mm_per_ha" for c, _ in ROTATION)
    return (
        f"# SOURCE: Derived from crop daily growth lookup files (data/crops/crop_daily_growth/)\n"
        f"# DATE: {date_str}\n"
        f"# DESCRIPTION: Toy daily irrigation demand profile for a 2-field, 4-crop Egyptian rotation.\n"
        f"#   ETc averaged across weather years 2010-2024 under {IRRIGATION_POLICY} irrigation,\n"
        f"#   {CONDITION} condition. Each crop column is water demand in mm/day per hectare.\n"
        f"#   total_etc_mm_per_ha is the sum across all active crops (assumes 1 ha per crop).\n"
        f"#   min_tds_requirement_ppm is the strictest (lowest) tds_no_penalty_ppm among active crops.\n"
        f"# ROTATION: Field A: kale (Oct 01, 85d) -> tomato (Feb 15, 135d);\n"
        f"#   Field B: potato (Sep 15, 120d) -> onion (Jan 15, 150d)\n"
        f"# CROPS: {crops}\n"
        f"# UNITS: month_day=MM-DD, {etc_cols}=mm/day/ha,\n"
        f"#   total_etc_mm_per_ha=mm/day/ha (sum across crops, assumes 1 ha each),\n"
        f"#   min_tds_requirement_ppm=ppm (NaN when no crop is active)\n"
        f"# LOGIC: ETc = Kc * ETo from pre-computed crop daily growth files (Hargreaves ETo, FAO-56).\n"
        f"#   Averaged across all weather years in dataset for a representative seasonal curve.\n"
        f"# DEPENDENCIES: data/crops/crop_daily_growth/*_{CONDITION}-research.csv,\n"
        f"#   data/crops/crop_params/crop_growth_params-research.csv (TDS thresholds)\n"
    )


def main():
    root = _repo_root()
    growth_dir = root / "data/crops/crop_daily_growth"
    params_path = root / "data/crops/crop_params/crop_growth_params-research.csv"
    output_path = root / "simulation/daily_irrigation_demand-toy.csv"

    result = build_demand_profile(growth_dir, params_path)

    date_str = datetime.now().strftime("%Y-%m-%d")
    with open(output_path, "w") as f:
        f.write(_metadata_header(date_str))
    result.to_csv(output_path, mode="a", index=False)

    active_days = (result["total_etc_mm_per_ha"] > 0).sum()
    peak = result["total_etc_mm_per_ha"].max()
    tds_min = result["min_tds_requirement_ppm"].min()
    tds_max = result["min_tds_requirement_ppm"].max()

    print(f"Irrigation demand: {len(result)} days, {active_days} active -> {output_path}")
    print(f"Peak demand: {peak:.1f} mm/day")
    print(f"TDS requirement range: {tds_min:.0f} - {tds_max:.0f} ppm")


if __name__ == "__main__":
    main()
