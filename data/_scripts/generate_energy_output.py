#!/usr/bin/env python3
"""
Generate daily energy output for wind turbines and PV systems from weather data.

Reads wind turbine and PV system specifications, applies physics-based models
to daily weather data, and produces two output files:
  daily_wind_output-research.csv   (kWh per turbine per day)
  daily_pv_output-research.csv     (kWh per hectare per day)

Wind model:
  - Power-law wind shear from 10m to hub height (alpha=0.14)
  - Cubic power curve: P = P_rated * (v³ - v_cin³) / (v_rated³ - v_cin³)
  - Zero output below cut-in or above cut-out speed

PV model:
  - Installed panel area per hectare from ground coverage ratio
  - Temperature derating from daily average air temp + density offset
  - System losses, shading, tilt, and irradiance factors

Usage:
    python generate_energy_output.py
    python generate_energy_output.py --weather data/weather/daily_weather_openfield-research.csv
    python generate_energy_output.py --turbines data/energy_gen/wind_turbines-research.csv
"""
from __future__ import annotations

import argparse
from datetime import datetime
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd

WIND_SHEAR_EXPONENT = 0.14
REFERENCE_HEIGHT_M = 10.0
HECTARE_M2 = 10_000
HOURS_PER_DAY = 24


def _repo_root() -> Path:
    """Return repository root (parent of data/)."""
    return Path(__file__).resolve().parent.parent.parent


def read_csv_with_comments(path: Path) -> tuple[list[str], pd.DataFrame]:
    """Read CSV file, returning comment lines and data DataFrame."""
    comments: list[str] = []
    data_lines: list[str] = []

    with open(path) as f:
        for line in f:
            s = line.rstrip("\n")
            if s.startswith("#"):
                comments.append(s)
            else:
                data_lines.append(s)

    if not data_lines:
        raise ValueError(f"No data rows in {path}")

    df = pd.read_csv(
        StringIO("\n".join(data_lines)),
        dtype={"weather_scenario_id": str},
    )
    return comments, df


# ---------------------------------------------------------------------------
# Wind turbine model
# ---------------------------------------------------------------------------


def wind_speed_at_hub(v_ref: np.ndarray, hub_height_m: float) -> np.ndarray:
    """Extrapolate wind speed from reference height to hub height via power law."""
    return v_ref * (hub_height_m / REFERENCE_HEIGHT_M) ** WIND_SHEAR_EXPONENT


def wind_power_curve(
    v_hub: np.ndarray,
    rated_capacity_kw: float,
    cut_in_ms: float,
    rated_ms: float,
    cut_out_ms: float,
) -> np.ndarray:
    """
    Cubic power curve for a wind turbine.

    P(v) = P_rated * (v³ - v_cin³) / (v_rated³ - v_cin³)   for v_cin ≤ v ≤ v_rated
    P(v) = P_rated                                           for v_rated < v ≤ v_cout
    P(v) = 0                                                 otherwise
    """
    power = np.zeros_like(v_hub, dtype=float)

    cubic_mask = (v_hub >= cut_in_ms) & (v_hub <= rated_ms)
    power[cubic_mask] = rated_capacity_kw * (
        (v_hub[cubic_mask] ** 3 - cut_in_ms**3)
        / (rated_ms**3 - cut_in_ms**3)
    )

    rated_mask = (v_hub > rated_ms) & (v_hub <= cut_out_ms)
    power[rated_mask] = rated_capacity_kw

    return power


def compute_wind_output(
    weather_df: pd.DataFrame,
    turbines_df: pd.DataFrame,
) -> pd.DataFrame:
    """Compute daily wind energy output (kWh/turbine/day) for each turbine size."""
    result = weather_df[["date", "weather_scenario_id"]].copy()
    v_10m = weather_df["wind_speed_ms"].values

    for _, turbine in turbines_df.iterrows():
        v_hub = wind_speed_at_hub(v_10m, turbine["hub_height_m"])
        avg_power_kw = wind_power_curve(
            v_hub,
            turbine["rated_capacity_kw"],
            turbine["cut_in_speed_ms"],
            turbine["rated_speed_ms"],
            turbine["cut_out_speed_ms"],
        )
        col = f"{turbine['turbine_name']}_kwh"
        result[col] = np.round(avg_power_kw * HOURS_PER_DAY, 2)

    return result


# ---------------------------------------------------------------------------
# PV system model
# ---------------------------------------------------------------------------


def compute_pv_output(
    weather_df: pd.DataFrame,
    pv_df: pd.DataFrame,
) -> pd.DataFrame:
    """Compute daily PV energy output (kWh/hectare/day) for each density level."""
    result = weather_df[["date", "weather_scenario_id"]].copy()

    ghi = weather_df["solar_irradiance_kwh_m2"].values
    t_avg = (weather_df["temp_max_c"].values + weather_df["temp_min_c"].values) / 2

    for _, pv in pv_df.iterrows():
        panel_area_per_ha = (pv["ground_coverage_pct"] / 100) * HECTARE_M2
        t_cell = t_avg + pv["temp_adjustment_c"]
        temp_derate = 1 + pv["temp_coefficient_per_c"] * (t_cell - pv["temp_reference_c"])

        daily_kwh = (
            ghi
            * panel_area_per_ha
            * pv["module_efficiency"]
            * pv["tilt_factor"]
            * pv["irradiance_factor"]
            * temp_derate
            * (1 - pv["system_losses_pct"] / 100)
            * pv["shading_factor"]
        )

        col = f"{pv['density_name']}_kwh_per_ha"
        result[col] = np.round(daily_kwh, 2)

    return result


# ---------------------------------------------------------------------------
# Metadata headers
# ---------------------------------------------------------------------------


def wind_metadata_header(turbines_df: pd.DataFrame, date_str: str) -> str:
    turbine_specs = "; ".join(
        f"{r['turbine_name']}={r['product_name']} "
        f"({r['rated_capacity_kw']}kW, hub {r['hub_height_m']}m, "
        f"rotor {r['rotor_diameter_m']}m)"
        for _, r in turbines_df.iterrows()
    )
    cols = ", ".join(f"{r['turbine_name']}_kwh" for _, r in turbines_df.iterrows())
    return (
        f"# SOURCE: Derived from wind_turbines-research.csv and daily_weather_openfield-research.csv\n"
        f"# DATE: {date_str}\n"
        f"# DESCRIPTION: Daily wind energy output per turbine for small/medium/large distributed-scale turbines\n"
        f"# UNITS: date=YYYY-MM-DD, {cols}=kWh/turbine/day\n"
        f"# LOGIC: Wind speed extrapolated from 10m to hub height using power law (alpha={WIND_SHEAR_EXPONENT}). "
        f"Power curve: P = P_rated * (v^3 - v_cin^3) / (v_rated^3 - v_cin^3) for v_cin <= v <= v_rated; "
        f"P_rated for v_rated < v <= v_cout; 0 otherwise. Daily energy = avg_power_kw * 24h.\n"
        f"# DEPENDENCIES: data/energy_gen/wind_turbines-research.csv, data/weather/daily_weather_openfield-research.csv\n"
        f"# ASSUMPTIONS: (1) Power-law wind shear exponent {WIND_SHEAR_EXPONENT} for open coastal terrain. "
        f"(2) Daily avg wind speed applied directly to power curve (no sub-daily Weibull correction — "
        f"underestimates output due to Jensen's inequality on cubic curve). "
        f"(3) No air density correction for altitude/temperature.\n"
        f"# TURBINES: {turbine_specs}\n"
    )


def pv_metadata_header(pv_df: pd.DataFrame, date_str: str) -> str:
    density_specs = "; ".join(
        f"{r['density_name']}=GCR {r['ground_coverage_pct']}%, "
        f"shading {r['shading_factor']}, temp_adj {r['temp_adjustment_c']:+.1f}C"
        for _, r in pv_df.iterrows()
    )
    cols = ", ".join(f"{r['density_name']}_kwh_per_ha" for _, r in pv_df.iterrows())
    return (
        f"# SOURCE: Derived from pv_systems-toy.csv and daily_weather_openfield-research.csv\n"
        f"# DATE: {date_str}\n"
        f"# DESCRIPTION: Daily PV energy output per hectare for low/medium/high density agri-PV systems\n"
        f"# UNITS: date=YYYY-MM-DD, {cols}=kWh/hectare/day\n"
        f"# LOGIC: Energy = GHI * panel_area_per_ha * module_efficiency * tilt_factor * irradiance_factor "
        f"* temp_derate * (1 - system_losses/100) * shading_factor. "
        f"Cell temp estimated as (T_max+T_min)/2 + temp_adjustment_c. "
        f"Temp derate = 1 + temp_coeff * (T_cell - T_ref).\n"
        f"# DEPENDENCIES: data/energy_gen/pv_systems-toy.csv, data/weather/daily_weather_openfield-research.csv\n"
        f"# ASSUMPTIONS: (1) Cell temperature approximated from daily avg air temp + density-dependent offset. "
        f"(2) GHI used as proxy for plane-of-array irradiance (tilt_factor applied as multiplier). "
        f"(3) No hourly decomposition — daily totals only.\n"
        f"# DENSITIES: {density_specs}\n"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(
    weather_path: Path | None = None,
    turbines_path: Path | None = None,
    pv_path: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    root = _repo_root()
    date_str = datetime.now().strftime("%Y-%m-%d")

    weather_path = weather_path or root / "data/weather/daily_weather_openfield-research.csv"
    turbines_path = turbines_path or root / "data/energy_gen/wind_turbines-research.csv"
    pv_path = pv_path or root / "data/energy_gen/pv_systems-toy.csv"

    for p in (weather_path, turbines_path, pv_path):
        if not p.exists():
            raise FileNotFoundError(f"Input file not found: {p}")

    _, weather_df = read_csv_with_comments(weather_path)
    turbines_df = pd.read_csv(turbines_path, comment="#")
    pv_df = pd.read_csv(pv_path, comment="#")

    stem = weather_path.stem
    suffix = stem.split("-", 1)[1] if "-" in stem else "research"
    output_dir = root / "data/energy_gen"
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Wind output ---
    wind_result = compute_wind_output(weather_df, turbines_df)
    wind_out = output_dir / f"daily_wind_output-{suffix}.csv"
    with open(wind_out, "w") as f:
        f.write(wind_metadata_header(turbines_df, date_str))
    wind_result.to_csv(wind_out, mode="a", index=False)
    print(f"Wind output: {len(wind_result)} rows -> {wind_out}")

    # --- PV output ---
    pv_result = compute_pv_output(weather_df, pv_df)
    pv_out = output_dir / f"daily_pv_output-{suffix}.csv"
    with open(pv_out, "w") as f:
        f.write(pv_metadata_header(pv_df, date_str))
    pv_result.to_csv(pv_out, mode="a", index=False)
    print(f"PV output:   {len(pv_result)} rows -> {pv_out}")

    return wind_result, pv_result


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate daily wind and PV energy output from weather and equipment specs.",
    )
    parser.add_argument(
        "--weather",
        type=Path,
        default=None,
        help="Path to daily weather CSV (default: data/weather/daily_weather_openfield-research.csv)",
    )
    parser.add_argument(
        "--turbines",
        type=Path,
        default=None,
        help="Path to wind turbines CSV (default: data/energy_gen/wind_turbines-research.csv)",
    )
    parser.add_argument(
        "--pv",
        type=Path,
        default=None,
        help="Path to PV systems CSV (default: data/energy_gen/pv_systems-toy.csv)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(
        weather_path=args.weather,
        turbines_path=args.turbines,
        pv_path=args.pv,
    )
