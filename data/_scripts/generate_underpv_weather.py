#!/usr/bin/env python3
"""
Generate daily weather under PV panels from open-field weather and microclimate factors.

Reads daily_weather_openfield-*.csv and pv_microclimate_factors-*.csv, applies
microclimate adjustments (temperature, irradiance, wind) for each density variant
(low, medium, high) defined in the factors file, and writes three files:
  daily_weather_underpv_low-*.csv
  daily_weather_underpv_medium-*.csv
  daily_weather_underpv_high-*.csv

Precipitation is passed through unchanged (no panel-interception model in microclimate factors).

Usage:
    python generate_underpv_weather.py [--density low|medium|high] [--openfield PATH] [--factors PATH]

Examples:
    python generate_underpv_weather.py                    # Generate all three (low, medium, high)
    python generate_underpv_weather.py --density low      # Generate only low-density file
"""

import argparse
from pathlib import Path

import pandas as pd


def _repo_root() -> Path:
    """Return repository root (parent of data/)."""
    # Script is at data/scripts/; parent.parent = repo root
    return Path(__file__).resolve().parent.parent.parent


def read_csv_with_comments(path: Path) -> tuple[list[str], pd.DataFrame]:
    """Read CSV file, returning comment lines and data DataFrame."""
    comments = []
    data_lines = []

    with open(path, "r") as f:
        for line in f:
            s = line.rstrip("\n")
            if s.startswith("#"):
                comments.append(s)
            else:
                data_lines.append(s)

    if not data_lines:
        raise ValueError(f"No data rows in {path}")

    from io import StringIO

    df = pd.read_csv(
        StringIO("\n".join(data_lines)),
        dtype={"weather_scenario_id": str},
    )
    return comments, df


def generate_metadata_header(
    density_variant: str,
    ground_coverage_pct: int,
    temp_adj: float,
    irr_mult: float,
    wind_mult: float,
    date_str: str,
) -> str:
    """Generate metadata comment block for under-PV weather file."""
    return f"""# SOURCE: Derived from daily_weather_openfield-research.csv and pv_microclimate_factors-research.csv
# DATE: {date_str}
# DESCRIPTION: Daily weather under agri-PV panels (spatial average at crop level). Open-field weather adjusted by microclimate factors for density_variant={density_variant} (GCR={ground_coverage_pct}%).
# UNITS: date=YYYY-MM-DD, temp_max_c=Celsius, temp_min_c=Celsius, solar_irradiance_kwh_m2=kWh/m2/day, wind_speed_ms=m/s, precip_mm=mm/day
# LOGIC: temp_new = temp_openfield + temp_adjustment_c ({temp_adj:+.2f}C); solar_new = solar_openfield * irradiance_multiplier ({irr_mult:.2f}); wind_new = wind_openfield * wind_speed_multiplier ({wind_mult:.2f}). Precipitation passed through unchanged (no panel interception in factors).
# DEPENDENCIES: daily_weather_openfield-*.csv, pv_microclimate_factors-*.csv
# ASSUMPTIONS: Microclimate factors represent spatial average across planted area. Panel height 3m, fixed-tilt 28deg. Values from peer-reviewed agri-PV studies.
# DENSITY_VARIANT: {density_variant} (ground_coverage_pct={ground_coverage_pct})
"""


def apply_microclimate(
    df: pd.DataFrame,
    temp_adjustment_c: float,
    irradiance_multiplier: float,
    wind_speed_multiplier: float,
) -> pd.DataFrame:
    """Apply microclimate adjustments to weather DataFrame."""
    out = df.copy()
    out["temp_max_c"] = (df["temp_max_c"] + temp_adjustment_c).round(2)
    out["temp_min_c"] = (df["temp_min_c"] + temp_adjustment_c).round(2)
    out["solar_irradiance_kwh_m2"] = (
        df["solar_irradiance_kwh_m2"] * irradiance_multiplier
    ).round(2)
    out["wind_speed_ms"] = (df["wind_speed_ms"] * wind_speed_multiplier).round(2)
    # precip_mm unchanged
    return out


def main(
    density_variant: str | None = None,
    openfield_path: Path | None = None,
    factors_path: Path | None = None,
) -> dict[str, pd.DataFrame]:
    """Generate under-PV weather files. If density_variant is None, generate all three (low, medium, high)."""
    from datetime import datetime

    root = _repo_root()

    openfield_path = openfield_path or root / "data/weather/daily_weather_openfield-research.csv"
    factors_path = factors_path or root / "data/weather/pv_microclimate_factors-research.csv"

    if not openfield_path.exists():
        raise FileNotFoundError(f"Open-field weather file not found: {openfield_path}")
    if not factors_path.exists():
        raise FileNotFoundError(f"Microclimate factors file not found: {factors_path}")

    # Infer -research/-toy suffix from openfield filename
    stem = openfield_path.stem  # daily_weather_openfield-research
    suffix = stem.split("-", 1)[1] if "-" in stem else "research"
    output_dir = openfield_path.parent

    # Load microclimate factors (skip comment lines) and select variants to process
    factors_df = pd.read_csv(factors_path, comment="#")
    if density_variant is not None:
        factors_df = factors_df[factors_df["density_variant"] == density_variant]
        if factors_df.empty:
            raise ValueError(
                f"density_variant '{density_variant}' not found in {factors_path}. "
                f"Available: {list(pd.read_csv(factors_path, comment='#')['density_variant'])}"
            )

    # Load open-field weather once
    _, weather_df = read_csv_with_comments(openfield_path)
    date_str = datetime.now().strftime("%Y-%m-%d")

    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, pd.DataFrame] = {}

    for _, row in factors_df.iterrows():
        variant = str(row["density_variant"])
        temp_adj = float(row["temp_adjustment_c"])
        irr_mult = float(row["irradiance_multiplier"])
        wind_mult = float(row["wind_speed_multiplier"])
        gcr = int(row["ground_coverage_pct"])

        result = apply_microclimate(weather_df, temp_adj, irr_mult, wind_mult)
        results[variant] = result

        header = generate_metadata_header(
            density_variant=variant,
            ground_coverage_pct=gcr,
            temp_adj=temp_adj,
            irr_mult=irr_mult,
            wind_mult=wind_mult,
            date_str=date_str,
        )

        output_path = output_dir / f"daily_weather_underpv_{variant}-{suffix}.csv"
        with open(output_path, "w") as f:
            f.write(header)
        result.to_csv(output_path, mode="a", index=False)

        print(f"Wrote {len(result)} rows to {output_path}")
        print(f"  Density: {variant} (GCR {gcr}%)")
        print(f"  Temp adj: {temp_adj:+.2f}C, Irradiance × {irr_mult:.2f}, Wind × {wind_mult:.2f}")

    return results


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate daily weather under PV from open-field weather and microclimate factors."
    )
    parser.add_argument(
        "--density",
        choices=["low", "medium", "high"],
        default=None,
        help="Panel density variant to generate (default: all three: low, medium, high)",
    )
    parser.add_argument(
        "--openfield",
        type=Path,
        default=None,
        help="Path to daily_weather_openfield CSV (default: data/weather/daily_weather_openfield-research.csv)",
    )
    parser.add_argument(
        "--factors",
        type=Path,
        default=None,
        help="Path to pv_microclimate_factors CSV (default: data/weather/pv_microclimate_factors-research.csv)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(
        density_variant=args.density,
        openfield_path=args.openfield,
        factors_path=args.factors,
    )
