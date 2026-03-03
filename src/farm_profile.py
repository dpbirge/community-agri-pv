"""Farm profile utilities: normalize plantings and validate no overlap.

Each field has plantings as a list of {crop, plantings: [date, ...]}.
Planting dates use codes like oct01, feb15 matching crop growth filenames.

Usage:
    from src.farm_profile import normalize_plantings, validate_no_overlap

    flat = normalize_plantings(field_dict)
    validate_no_overlap(farm_config, registry, root_dir)
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


def planting_code_to_mmdd(code):
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


def _load_season_lengths(registry, root_dir):
    """Load (crop, mmdd) -> expected_season_length_days from planting_windows."""
    windows_path = root_dir / registry["crops"]["planting_windows"]
    df = pd.read_csv(windows_path, comment="#")
    lookup = {}
    for _, row in df.iterrows():
        lookup[(row["crop"], row["planting_date_mmdd"])] = int(row["expected_season_length_days"])
    return lookup


def normalize_plantings(field):
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


def validate_no_overlap(farm_config, registry, root_dir):
    """Raise ValueError if any field has overlapping growing seasons.

    Uses planting_windows-research.csv for expected_season_length_days.
    Checks across two consecutive reference years (2020 and 2021) so that
    a late-year planting wrapping into the next year is tested against
    early-year plantings on the same field.
    """
    season_lookup = _load_season_lengths(registry, root_dir)
    ref_years = [2020, 2021]

    def date_ranges(crop, planting_code):
        """Return intervals for two consecutive years to catch cross-year overlap."""
        mmdd = planting_code_to_mmdd(planting_code)
        key = (crop, mmdd)
        if key not in season_lookup:
            raise ValueError(
                f"Unknown (crop, planting) {key}; "
                f"must exist in planting_windows-research.csv"
            )
        length = season_lookup[key]
        intervals = []
        for y in ref_years:
            start = datetime.strptime(f"{y}-{mmdd}", "%Y-%m-%d")
            end = start + timedelta(days=length)
            intervals.append((start, end))
        return intervals

    def ranges_overlap(a, b):
        """Intervals (start, end) overlap iff start_a < end_b and start_b < end_a."""
        return a[0] < b[1] and b[0] < a[1]

    errors = []
    for farm in farm_config.get("farms", []):
        for field in farm.get("fields", []):
            name = field.get("name", "?")
            flat = normalize_plantings(field)
            # Collect (crop, planting_code, interval) for all plantings x both years
            all_intervals = []
            for p in flat:
                try:
                    intervals = date_ranges(p["crop"], p["planting"])
                    for interval in intervals:
                        all_intervals.append((p["crop"], p["planting"], interval))
                except ValueError as e:
                    errors.append(f"Field {name}: {e}")
            # Check all pairs (skip same planting in different years against itself
            # only when both crop and planting_code match -- same annual event)
            reported = set()
            for i, (c1, pl1, r1) in enumerate(all_intervals):
                for c2, pl2, r2 in all_intervals[i + 1:]:
                    if c1 == c2 and pl1 == pl2:
                        # Same planting in year N vs year N+1 -- not an overlap
                        continue
                    if ranges_overlap(r1, r2):
                        pair_key = tuple(sorted([(c1, pl1), (c2, pl2)]))
                        if pair_key not in reported:
                            reported.add(pair_key)
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
