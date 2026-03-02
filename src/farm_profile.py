"""Farm profile utilities: normalize plantings and validate no overlap.

Each field has plantings as a list of {crop, plantings: [date, ...]}.
Planting dates use codes like oct01, feb15 matching crop growth filenames.
"""

import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# Planting code (e.g. oct01) -> MM for conversion to mmdd
_MONTH_ABBREV_TO_MM = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


def planting_code_to_mmdd(code: str) -> str:
    """Convert planting code (e.g. oct01, feb15) to MM-DD (e.g. 10-01, 02-15)."""
    code = code.lower().strip()
    if len(code) < 4:
        raise ValueError(f"Invalid planting code '{code}': expected e.g. oct01, feb15")
    month_str = code[:-2]
    day_str = code[-2:]
    mm = _MONTH_ABBREV_TO_MM.get(month_str)
    if mm is None:
        raise ValueError(f"Unknown month '{month_str}' in planting code '{code}'")
    try:
        d = int(day_str)
    except ValueError:
        raise ValueError(f"Invalid day '{day_str}' in planting code '{code}'")
    if not (1 <= d <= 31):
        raise ValueError(f"Day must be 01-31 in planting code '{code}'")
    return f"{mm}-{day_str}"


def _load_season_lengths(registry, root_dir: Path) -> dict[tuple[str, str], int]:
    """Load (crop, mmdd) -> expected_season_length_days from planting_windows."""
    growth_path = root_dir / registry["crops"]["growth_params"]
    windows_path = growth_path.parent / "planting_windows-research.csv"
    df = pd.read_csv(windows_path, comment="#")
    lookup = {}
    for _, row in df.iterrows():
        crop = row["crop"]
        mmdd = row["planting_date_mmdd"]
        length = int(row["expected_season_length_days"])
        lookup[(crop, mmdd)] = length
    return lookup


def normalize_plantings(field: dict) -> list[dict]:
    """Expand field plantings to flat list of {crop, planting}.

    Each entry in field['plantings'] has crop and plantings: [date, ...].
    Returns one {crop, planting} per (crop, date) pair.
    """
    out = []
    for p in field.get("plantings", []):
        crop = p["crop"]
        dates = p["plantings"]
        for planting in dates:
            out.append({"crop": crop, "planting": planting})
    return out


def validate_no_overlap(
    farm_config: dict,
    registry: dict,
    root_dir: Path,
) -> None:
    """Raise ValueError if any field has overlapping growing seasons.

    Uses planting_windows-research.csv for expected_season_length_days.
    Seasons are computed in a reference year; cross-year seasons handled.
    """
    season_lookup = _load_season_lengths(registry, root_dir)
    ref_year = 2020  # arbitrary, seasons wrap across Dec 31 as needed

    def date_range(crop: str, planting_code: str) -> tuple[datetime, datetime]:
        mmdd = planting_code_to_mmdd(planting_code)
        key = (crop, mmdd)
        if key not in season_lookup:
            raise ValueError(
                f"Unknown (crop, planting) {key}; "
                f"must exist in planting_windows-research.csv"
            )
        length = season_lookup[key]
        start = datetime.strptime(f"{ref_year}-{mmdd}", "%Y-%m-%d")
        end = start + timedelta(days=length)
        return start, end

    def ranges_overlap(a: tuple, b: tuple) -> bool:
        """Intervals (start, end) overlap iff start_a < end_b and start_b < end_a."""
        start_a, end_a = a
        start_b, end_b = b
        return start_a < end_b and start_b < end_a

    errors = []
    for farm in farm_config.get("farms", []):
        for field in farm.get("fields", []):
            name = field.get("name", "?")
            flat = normalize_plantings(field)
            ranges = []
            for p in flat:
                try:
                    r = date_range(p["crop"], p["planting"])
                    ranges.append((p["crop"], p["planting"], r))
                except ValueError as e:
                    errors.append(f"Field {name}: {e}")
            # Check all pairs
            for i, (c1, pl1, r1) in enumerate(ranges):
                for (c2, pl2, r2) in ranges[i + 1:]:
                    if ranges_overlap(r1, r2):
                        errors.append(
                            f"Field {name}: overlapping plantings "
                            f"{c1} {pl1} and {c2} {pl2}"
                        )

    if errors:
        raise ValueError(
            "Farm profile has overlapping plantings:\n  " + "\n  ".join(errors)
        )


# ---------------------------------------------------------------------------
# Entry point for standalone validation
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import yaml

    root = Path(__file__).parent.parent
    farm_path = root / "settings" / "farm_profile_base.yaml"
    registry_path = root / "settings" / "data_registry_base.yaml"

    farm_config = yaml.safe_load(farm_path.read_text())
    registry = yaml.safe_load(registry_path.read_text())
    validate_no_overlap(farm_config, registry, root)
    print("OK: No overlapping plantings")
