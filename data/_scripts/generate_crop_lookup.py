#!/usr/bin/env python3
"""
Generate daily crop growth & water demand lookup tables.

Produces one CSV per (crop, planting_date, condition) combination, organized
into per-crop folders:

  data/crops/crop_daily_growth/
    tomato/
      tomato_feb15_openfield-research.csv
      tomato_feb15_underpv_low-research.csv
      ...
    potato/
      ...

Each file contains all irrigation policies × weather years for that specific
crop + planting date + microclimate condition.  The simulation picks a file
by the user's configuration and reads it — no further calculation needed.

Output columns:
  irrigation_policy, weather_scenario_id, weather_year,
  day_of_season, date, growth_stage, kc, fpar, eto_mm, etc_mm,
  water_applied_mm, water_stress_coeff, temp_stress_coeff, biomass_kg_ha,
  cumulative_biomass_kg_ha, yield_fresh_kg_ha

The final day_of_season row for each (irrigation_policy, weather_year) group
has the harvest yield in yield_fresh_kg_ha.

Models:
  - ETo: Hargreaves (FAO-56 Eq. 52)
  - ETc: Kc × ETo_ref × (1 − ET_reduction).  Under PV, ETo_ref is computed
    at openfield temperatures to avoid double-counting the temperature-driven
    ETo reduction that Hargreaves already captures from the weather file
  - Canopy interception: fPAR ramps from ~0.10 (seedling) to crop-specific
    maximum (~0.60–0.85) following growth stage progression
  - Water stress: Ks = min(1, water_applied / ETc) — applied daily to biomass
  - Temperature stress: Kt piecewise linear from crop cardinal temperatures
  - Biomass: RUE × incident_PAR × fPAR × Ks × Kt (daily accumulation)
  - Yield: potential_yield × (ETa/ETc)^(1/alpha) × avg_Kt
    where alpha = 1 + beta*(1.15 - Ky), producing concave water-yield response.
    Yield is decoupled from cumulative biomass to avoid the dm_frac
    amplification problem (crops with >95% water content produce unrealistic
    fresh yields from any reasonable dry biomass).  Light and water
    attenuation under agri-PV panels are captured via condition-specific
    weather files (reduced PAR, temperature) and ET reduction multiplier.

Usage:
    python generate_crop_lookup.py
    python generate_crop_lookup.py --crop tomato
    python generate_crop_lookup.py --crop kale --planting 10-01
"""

import argparse
import math
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd

LATITUDE_DEG = 28.0
SOLAR_CONSTANT = 0.0820  # MJ m-2 min-1
PAR_FRACTION = 0.48
KWH_TO_MJ = 3.6

IRRIGATION_POLICIES = {
    "full_eto": 1.00,
    "optimal_deficit": None,
    "deficit_80": 0.80,
    "deficit_60": 0.60,
    "rainfed": 0.00,
}

OPTIMAL_DEFICIT_FRACTIONS = {
    "tomato": 0.80,
    "potato": 0.85,
    "onion": 0.80,
    "kale": 0.75,
    "cucumber": 0.80,
}

MAX_FPAR = {
    "tomato": 0.85,
    "potato": 0.80,
    "onion": 0.60,
    "kale": 0.75,
    "cucumber": 0.75,
}

CONDITIONS = ["openfield", "underpv_low", "underpv_medium", "underpv_high"]

MONTH_ABBREV = {
    "01": "jan", "02": "feb", "03": "mar", "04": "apr",
    "05": "may", "06": "jun", "07": "jul", "08": "aug",
    "09": "sep", "10": "oct", "11": "nov", "12": "dec",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def read_csv_skip_comments(path: Path, **kwargs) -> pd.DataFrame:
    data_lines: list[str] = []
    with open(path) as f:
        for line in f:
            if not line.startswith("#"):
                data_lines.append(line.rstrip("\n"))
    if not data_lines:
        raise ValueError(f"No data rows in {path}")
    return pd.read_csv(StringIO("\n".join(data_lines)), **kwargs)


# ---------------------------------------------------------------------------
# ETo
# ---------------------------------------------------------------------------

def _extraterrestrial_radiation(doy: int, lat_deg: float) -> float:
    """Daily extraterrestrial radiation Ra (MJ/m2/day) — FAO-56 Eq. 21."""
    lat = math.radians(lat_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)
    delta = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
    ws = math.acos(-math.tan(lat) * math.tan(delta))
    ra = (
        (24 * 60 / math.pi)
        * SOLAR_CONSTANT
        * dr
        * (ws * math.sin(lat) * math.sin(delta)
           + math.cos(lat) * math.cos(delta) * math.sin(ws))
    )
    return max(ra, 0.0)


def hargreaves_eto(tmax: float, tmin: float, doy: int,
                   lat_deg: float = LATITUDE_DEG) -> float:
    """Hargreaves ETo (mm/day) — FAO-56 Eq. 52."""
    ra = _extraterrestrial_radiation(doy, lat_deg)
    tmean = (tmax + tmin) / 2.0
    td = max(tmax - tmin, 0.0)
    return 0.0023 * (tmean + 17.8) * (td ** 0.5) * ra


# ---------------------------------------------------------------------------
# Crop growth helpers
# ---------------------------------------------------------------------------

def build_kc_curve(stages: pd.DataFrame) -> np.ndarray:
    """Expand stage-based Kc into a daily array over the full season."""
    total_days = int(stages["days_in_stage"].sum())
    kc_daily = np.zeros(total_days)
    stage_list = stages.to_dict("records")

    day = 0
    for i, stg in enumerate(stage_list):
        n = int(stg["days_in_stage"])
        if stg["stage"] in ("initial", "mid", "late"):
            kc_daily[day: day + n] = stg["kc_value"]
        elif stg["stage"] == "development":
            kc_start = stage_list[i - 1]["kc_value"] if i > 0 else stg["kc_value"]
            kc_end = (stage_list[i + 1]["kc_value"]
                      if i + 1 < len(stage_list) else stg["kc_value"])
            kc_daily[day: day + n] = np.linspace(kc_start, kc_end, n)
        day += n

    late_stg = stage_list[-1]
    mid_stg = stage_list[-2] if len(stage_list) >= 2 else late_stg
    late_start = total_days - int(late_stg["days_in_stage"])
    late_n = int(late_stg["days_in_stage"])
    kc_daily[late_start: late_start + late_n] = np.linspace(
        mid_stg["kc_value"], late_stg["kc_value"], late_n
    )
    return kc_daily


def build_fpar_curve(stages: pd.DataFrame, max_fpar: float = 0.85) -> np.ndarray:
    """Daily fractional PAR interception based on canopy development.

    Seedlings start at ~10% interception, expanding through the development
    stage to crop-specific max_fpar at mid-season, then declining modestly
    during late-stage senescence.  Values approximate Beer-Lambert
    (1 − exp(−k·LAI)) without requiring explicit LAI tracking.
    """
    total_days = int(stages["days_in_stage"].sum())
    fpar = np.full(total_days, max_fpar)

    day = 0
    for _, stg in stages.iterrows():
        n = int(stg["days_in_stage"])
        stage = stg["stage"]

        if stage == "initial":
            fpar[day: day + n] = np.linspace(0.10, 0.10 + max_fpar * 0.15, n)
        elif stage == "development":
            start = fpar[day - 1] if day > 0 else 0.10
            fpar[day: day + n] = np.linspace(start, max_fpar, n)
        elif stage == "mid":
            fpar[day: day + n] = max_fpar
        elif stage == "late":
            fpar[day: day + n] = np.linspace(max_fpar, max_fpar * 0.80, n)

        day += n

    return fpar


def stage_name_on_day(stages: pd.DataFrame, day_idx: int) -> str:
    cum = 0
    for _, row in stages.iterrows():
        cum += int(row["days_in_stage"])
        if day_idx < cum:
            return str(row["stage"])
    return str(stages.iloc[-1]["stage"])


def temperature_stress_factor(
    t_avg: float, t_base: float, t_opt_low: float,
    t_opt_high: float, t_max: float,
) -> float:
    if t_avg <= t_base or t_avg >= t_max:
        return 0.0
    if t_opt_low <= t_avg <= t_opt_high:
        return 1.0
    if t_avg < t_opt_low:
        return (t_avg - t_base) / (t_opt_low - t_base)
    return (t_max - t_avg) / (t_max - t_opt_high)


# ---------------------------------------------------------------------------
# Season simulation
# ---------------------------------------------------------------------------

def simulate_season(
    planting_mmdd: str,
    season_length: int,
    irrig_name: str,
    irrig_fraction: float,
    weather_df: pd.DataFrame,
    kc_stages: pd.DataFrame,
    growth_params: dict,
    yield_response: dict,
    microclimate_effects: dict | None,
) -> pd.DataFrame:
    """Simulate one (condition, irrigation_policy) across all weather years."""

    kc_curve = build_kc_curve(kc_stages)
    fpar_curve = build_fpar_curve(kc_stages, growth_params.get("max_fpar", 0.85))

    if len(kc_curve) < season_length:
        kc_curve = np.pad(kc_curve, (0, season_length - len(kc_curve)),
                          constant_values=kc_curve[-1])
    if len(fpar_curve) < season_length:
        fpar_curve = np.pad(fpar_curve, (0, season_length - len(fpar_curve)),
                            constant_values=fpar_curve[-1])
    kc_curve = kc_curve[:season_length]
    fpar_curve = fpar_curve[:season_length]

    rue = growth_params["rue_g_per_mj"]
    t_base = growth_params["t_base_c"]
    t_opt_lo = growth_params["t_opt_low_c"]
    t_opt_hi = growth_params["t_opt_high_c"]
    t_max = growth_params["t_max_c"]
    potential_yield = growth_params["potential_yield_kg_per_ha"]
    ky = yield_response.get("ky_whole_season", 1.0)
    wue_beta = yield_response.get("wue_curvature", 3.5)

    temp_adj_c = 0.0
    total_et_reduction = 0.0
    if microclimate_effects is not None:
        temp_adj_c = microclimate_effects["temperature_reduction_C"]
        total_et_reduction = microclimate_effects["et_reduction_pct"] / 100.0

    w = weather_df.copy()
    w["date_dt"] = pd.to_datetime(w["date"])
    w = w.set_index("date_dt")

    scenario_ids = sorted(w["weather_scenario_id"].unique())
    rows: list[dict] = []

    for scenario_id in scenario_ids:
        w_scen = w[w["weather_scenario_id"] == scenario_id]
        years = sorted(w_scen.index.year.unique())

        for year in years:
            try:
                planting_date = datetime.strptime(
                    f"{year}-{planting_mmdd}", "%Y-%m-%d")
            except ValueError:
                continue

            cumulative_biomass = 0.0
            season_et_actual = 0.0
            season_et_crop = 0.0
            season_sum_kt = 0.0
            season_day_count = 0

            for d in range(season_length):
                current_date = planting_date + timedelta(days=d)
                if current_date not in w_scen.index:
                    continue

                wr = w_scen.loc[current_date]
                if isinstance(wr, pd.DataFrame):
                    wr = wr.iloc[0]

                tmax = float(wr["temp_max_c"])
                tmin = float(wr["temp_min_c"])
                solar_kwh = float(wr["solar_irradiance_kwh_m2"])
                precip = float(wr["precip_mm"])
                doy = current_date.timetuple().tm_yday

                eto = hargreaves_eto(tmax, tmin, doy)
                kc_val = float(kc_curve[d])
                fpar_val = float(fpar_curve[d])

                if temp_adj_c > 0:
                    eto_ref = hargreaves_eto(
                        tmax + temp_adj_c, tmin + temp_adj_c, doy)
                    etc = kc_val * eto_ref * (1.0 - total_et_reduction)
                else:
                    etc = kc_val * eto

                water_from_irrig = etc * irrig_fraction
                water_applied = water_from_irrig + precip
                water_applied = min(water_applied, etc * 1.1)

                ks = min(1.0, water_applied / etc) if etc > 0 else 1.0

                t_avg = (tmax + tmin) / 2.0
                kt = temperature_stress_factor(
                    t_avg, t_base, t_opt_lo, t_opt_hi, t_max)

                par_mj = solar_kwh * KWH_TO_MJ * PAR_FRACTION
                daily_biomass_kg_ha = rue * par_mj * fpar_val * ks * kt * 10.0

                cumulative_biomass += daily_biomass_kg_ha
                season_et_actual += water_applied
                season_et_crop += etc
                season_sum_kt += kt
                season_day_count += 1

                stage = stage_name_on_day(kc_stages, d)

                if d == season_length - 1:
                    f = (season_et_actual / season_et_crop
                         if season_et_crop > 0 else 0.0)
                    f = min(f, 1.0)
                    alpha = 1.0 + wue_beta * (1.15 - ky)
                    alpha = max(alpha, 1.0)
                    ky_factor = f ** (1.0 / alpha)
                    avg_kt = (season_sum_kt / season_day_count
                              if season_day_count > 0 else 1.0)
                    yield_fresh = potential_yield * ky_factor * avg_kt
                else:
                    yield_fresh = 0.0

                rows.append({
                    "irrigation_policy": irrig_name,
                    "weather_scenario_id": scenario_id,
                    "weather_year": year,
                    "day_of_season": d + 1,
                    "date": current_date.strftime("%Y-%m-%d"),
                    "growth_stage": stage,
                    "kc": round(kc_val, 3),
                    "fpar": round(fpar_val, 3),
                    "eto_mm": round(eto, 2),
                    "etc_mm": round(etc, 2),
                    "water_applied_mm": round(water_applied, 2),
                    "water_stress_coeff": round(ks, 3),
                    "temp_stress_coeff": round(kt, 3),
                    "biomass_kg_ha": round(daily_biomass_kg_ha, 1),
                    "cumulative_biomass_kg_ha": round(cumulative_biomass, 1),
                    "yield_fresh_kg_ha": round(yield_fresh, 0),
                })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------

def planting_to_filename(crop: str, mmdd: str) -> str:
    """Convert e.g. ('tomato', '02-15') -> 'tomato_feb15'."""
    mm, dd = mmdd.split("-")
    return f"{crop}_{MONTH_ABBREV[mm]}{int(dd):02d}"


def generate_header(
    crop: str, planting_mmdd: str, condition: str, season_label: str,
    season_length: int, row_count: int, date_str: str,
    optimal_frac: float | None = None,
) -> str:
    policy_parts: list[str] = []
    for k, v in IRRIGATION_POLICIES.items():
        if k == "optimal_deficit" and optimal_frac is not None:
            policy_parts.append(f"{k} ({optimal_frac * 100:.0f}%)")
        elif v is not None:
            policy_parts.append(f"{k} ({v * 100:.0f}%)")
    irrig_str = ", ".join(policy_parts)
    return (
        f"# SOURCE: Generated from crop parameter files and daily weather data\n"
        f"# DATE: {date_str}\n"
        f"# DESCRIPTION: Daily crop growth lookup for {crop} planted {planting_mmdd}\n"
        f"#   under {condition} ({season_label} season, {season_length} days).\n"
        f"#   One row per day of season for each (irrigation_policy, weather_year) combination.\n"
        f"#   The final day_of_season row contains the harvest yield in yield_fresh_kg_ha.\n"
        f"# ROWS: {row_count}\n"
        f"# CROP: {crop}\n"
        f"# PLANTING_DATE: {planting_mmdd}\n"
        f"# CONDITION: {condition}\n"
        f"# SEASON_LENGTH: {season_length} days\n"
        f"# IRRIGATION_POLICIES: {irrig_str}\n"
        f"# UNITS: eto_mm=mm/day, etc_mm=mm/day, water_applied_mm=mm/day,\n"
        f"#   fpar=fraction (0-1), biomass_kg_ha=kg DM/ha/day,\n"
        f"#   cumulative_biomass_kg_ha=kg DM/ha,\n"
        f"#   yield_fresh_kg_ha=kg fresh weight/ha (final day only)\n"
        f"# LOGIC: ETo via Hargreaves (FAO-56 Eq.52). ETc = Kc * ETo_ref * (1-ET_red).\n"
        f"#   Under PV, ETo_ref uses openfield temps to avoid double-counting.\n"
        f"#   Canopy interception fPAR ramps with growth stage (seedling→full canopy).\n"
        f"#   Daily biomass = RUE * PAR * fPAR * Ks * Kt (tracks growth dynamics).\n"
        f"#   Yield = potential_yield * (ETa/ETc)^(1/alpha) * avg_Kt\n"
        f"#   where alpha = 1 + beta*(1.15 - Ky), producing concave water-yield response.\n"
        f"#   PV light/temp attenuation captured in condition-specific weather files.\n"
        f"# DEPENDENCIES: crop_coefficients-research.csv, crop_growth_params-research.csv,\n"
        f"#   yield_response_factors-research.csv, pv_microclimate_factors-research.csv,\n"
        f"#   planting_windows-research.csv, daily_weather_*-research.csv\n"
    )


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_all_params(root: Path) -> tuple:
    crop_dir = root / "data/crops/crop_params"
    weather_dir = root / "data/weather"

    coeffs = read_csv_skip_comments(crop_dir / "crop_coefficients-research.csv")
    growth = read_csv_skip_comments(crop_dir / "crop_growth_params-research.csv")
    yield_resp = read_csv_skip_comments(crop_dir / "yield_response_factors-research.csv")
    planting = read_csv_skip_comments(crop_dir / "planting_windows-research.csv")
    pv_factors = read_csv_skip_comments(
        weather_dir / "pv_microclimate_factors-research.csv")

    return coeffs, growth, yield_resp, planting, pv_factors


def load_weather_files(root: Path) -> dict[str, pd.DataFrame]:
    weather_dir = root / "data/weather"
    files = {
        "openfield": weather_dir / "daily_weather_openfield-research.csv",
        "underpv_low": weather_dir / "daily_weather_underpv_low-research.csv",
        "underpv_medium": weather_dir / "daily_weather_underpv_medium-research.csv",
        "underpv_high": weather_dir / "daily_weather_underpv_high-research.csv",
    }
    result = {}
    for cond, path in files.items():
        if path.exists():
            result[cond] = read_csv_skip_comments(
                path, dtype={"weather_scenario_id": str})
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(
    filter_crop: str | None = None,
    filter_planting: str | None = None,
) -> None:
    root = _repo_root()
    date_str = datetime.now().strftime("%Y-%m-%d")

    coeffs, growth, yield_resp, planting, pv_factors = load_all_params(root)
    weather_files = load_weather_files(root)

    pv_density_info: dict[str, dict] = {}
    for _, row in pv_factors.iterrows():
        pv_density_info[row["density_variant"]] = {
            "temperature_reduction_C": abs(row["temp_adjustment_c"]),
            "et_reduction_pct": (1.0 - row["evapotranspiration_multiplier"]) * 100.0,
        }

    output_dir = root / "data/crops/crop_daily_growth"
    output_dir.mkdir(parents=True, exist_ok=True)

    crops = sorted(coeffs["crop"].unique())
    if filter_crop:
        crops = [c for c in crops if c == filter_crop]

    conditions = list(weather_files.keys())
    file_count = 0

    for crop_name in crops:
        crop_coeffs = coeffs[coeffs["crop"] == crop_name].copy()
        crop_growth = growth[growth["crop"] == crop_name].iloc[0].to_dict()
        crop_growth["max_fpar"] = MAX_FPAR.get(crop_name, 0.85)

        yr_row = yield_resp[yield_resp["crop_name"] == crop_name]
        crop_yield_resp = (yr_row.iloc[0].to_dict() if len(yr_row) > 0
                           else {"ky_whole_season": 1.0})

        optimal_frac = OPTIMAL_DEFICIT_FRACTIONS.get(crop_name, 0.80)

        crop_plantings = planting[planting["crop"] == crop_name]
        crop_dir = output_dir / crop_name
        crop_dir.mkdir(parents=True, exist_ok=True)

        for _, pw in crop_plantings.iterrows():
            planting_mmdd = pw["planting_date_mmdd"]
            season_len = int(pw["expected_season_length_days"])
            season_label = pw["season_label"]

            if filter_planting and planting_mmdd != filter_planting:
                continue

            for condition in conditions:
                weather_df = weather_files[condition]

                pv_density = None
                if condition.startswith("underpv_"):
                    pv_density = condition.replace("underpv_", "")

                mc_effects = pv_density_info.get(pv_density) if pv_density else None

                file_results: list[pd.DataFrame] = []
                for irrig_name, irrig_frac in IRRIGATION_POLICIES.items():
                    if irrig_name == "optimal_deficit":
                        irrig_frac = optimal_frac
                    result = simulate_season(
                        planting_mmdd=planting_mmdd,
                        season_length=season_len,
                        irrig_name=irrig_name,
                        irrig_fraction=irrig_frac,
                        weather_df=weather_df,
                        kc_stages=crop_coeffs,
                        growth_params=crop_growth,
                        yield_response=crop_yield_resp,
                        microclimate_effects=mc_effects,
                    )
                    if len(result) > 0:
                        file_results.append(result)

                if not file_results:
                    continue

                combined = pd.concat(file_results, ignore_index=True)
                fname = planting_to_filename(crop_name, planting_mmdd)
                output_path = crop_dir / f"{fname}_{condition}-research.csv"

                header = generate_header(
                    crop=crop_name,
                    planting_mmdd=planting_mmdd,
                    condition=condition,
                    season_label=season_label,
                    season_length=season_len,
                    row_count=len(combined),
                    date_str=date_str,
                    optimal_frac=optimal_frac,
                )
                with open(output_path, "w") as f:
                    f.write(header)
                combined.to_csv(output_path, mode="a", index=False)

                file_count += 1

                harvest = combined[combined["yield_fresh_kg_ha"] > 0]
                avg_yield = (harvest["yield_fresh_kg_ha"].mean()
                             if len(harvest) > 0 else 0)
                print(
                    f"  [{file_count:>3d}] {crop_name}/{output_path.name:<45s}  "
                    f"{len(combined):>6,} rows  "
                    f"avg yield {avg_yield:>8,.0f} kg/ha"
                )

    print(f"\nDone: {file_count} files written to {output_dir}/")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate daily crop growth lookup CSVs (one per crop × planting date).",
    )
    parser.add_argument(
        "--crop",
        choices=["tomato", "potato", "onion", "kale", "cucumber"],
        default=None,
        help="Generate for one crop only (default: all)",
    )
    parser.add_argument(
        "--planting",
        default=None,
        help="Generate for one planting date only, e.g. 02-15 (default: all)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(filter_crop=args.crop, filter_planting=args.planting)
