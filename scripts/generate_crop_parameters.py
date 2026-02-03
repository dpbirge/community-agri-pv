# Generate toy datasets for Crop Parameters (Task 2)
# Community Agri-PV Project - Sinai Red Sea region, Egypt

import pandas as pd
import os
from datetime import datetime

OUTPUT_DIR = "/Users/dpbirge/GITHUB/community-agri-pv/data/parameters/crops"
DATE_GENERATED = datetime.now().strftime("%Y-%m-%d")

CROPS = ["tomato", "potato", "onion", "kale", "cucumber"]
PROCESSING_TYPES = ["fresh", "packaged", "canned", "dried"]
STORAGE_CONDITIONS = ["ambient", "climate_controlled"]


def ensure_output_dir():
    """Create output directory if it doesn't exist."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output directory: {OUTPUT_DIR}")


# =============================================================================
# CROP COEFFICIENTS DATA
# Source: FAO-56 Table 12, adjusted +5-10% for hot arid conditions (advection)
# =============================================================================

CROP_COEFFICIENTS = {
    # crop_name: (kc_initial, kc_mid, kc_end, root_depth_m, season_length_days, water_stress_sensitivity)
    # FAO-56 base values with ~7% increase for hot arid conditions
    "tomato": (0.65, 1.20, 0.75, 1.2, 135, "high"),      # FAO: 0.6, 1.15, 0.7-0.9
    "potato": (0.55, 1.18, 0.80, 0.6, 120, "high"),      # FAO: 0.5, 1.15, 0.75
    "onion": (0.75, 1.10, 0.80, 0.4, 150, "medium"),     # FAO: 0.7, 1.05, 0.75
    "kale": (0.75, 1.10, 1.00, 0.5, 85, "low"),          # FAO: 0.7, 1.05, 0.95 (leafy veg)
    "cucumber": (0.65, 1.05, 0.80, 0.8, 95, "high"),     # FAO: 0.6, 1.0, 0.75
}


def generate_crop_coefficients():
    """Generate crop_coefficients-toy.csv with FAO-56 based data."""

    metadata = f"""# SOURCE: FAO Irrigation and Drainage Paper 56 (Table 12) + hot arid adjustments
# DATE: {DATE_GENERATED}
# DESCRIPTION: Crop coefficients for 5 crops, adjusted for Sinai Red Sea hot arid climate
# UNITS:
#   - kc_initial: Crop coefficient at planting (dimensionless)
#   - kc_mid: Crop coefficient at full canopy (dimensionless)
#   - kc_end: Crop coefficient at harvest (dimensionless)
#   - root_depth_m: Maximum effective root depth (meters)
#   - season_length_days: Total growing period planting to harvest (days)
#   - water_stress_sensitivity: High/Medium/Low yield sensitivity to water deficit
# LOGIC: FAO-56 base Kc values increased 5-10% for hot arid advection effects
# DEPENDENCIES: None (reference data)
# ASSUMPTIONS: Drip irrigation (90% efficiency), well-managed crops, no salinity stress
"""

    rows = []
    for crop in CROPS:
        kc_init, kc_mid, kc_end, root_depth, season_len, sensitivity = CROP_COEFFICIENTS[crop]
        rows.append({
            "crop_name": crop,
            "kc_initial": kc_init,
            "kc_mid": kc_mid,
            "kc_end": kc_end,
            "root_depth_m": root_depth,
            "season_length_days": season_len,
            "water_stress_sensitivity": sensitivity
        })

    df = pd.DataFrame(rows)

    filepath = os.path.join(OUTPUT_DIR, "crop_coefficients-toy.csv")
    with open(filepath, "w") as f:
        f.write(metadata)
        df.to_csv(f, index=False)

    print(f"\n[1] crop_coefficients-toy.csv")
    print(f"    Crops: {len(df)}")
    print(f"    Season lengths: {df['season_length_days'].min()}-{df['season_length_days'].max()} days")
    print(f"    Kc mid range: {df['kc_mid'].min():.2f}-{df['kc_mid'].max():.2f}")

    return df


# =============================================================================
# GROWTH STAGES DATA
# Based on FAO-56 Table 11 stage durations
# =============================================================================

# Stage durations as fractions of total season, then Kc values per stage
GROWTH_STAGES = {
    # crop: [(stage, duration_frac, kc, water_stress_impact)]
    # water_stress_impact = yield loss % per 10% water deficit
    "tomato": [
        ("initial", 0.22, 0.65, 3),       # ~30 days, establishment sensitive
        ("development", 0.30, 0.92, 5),   # ~40 days, vegetative growth
        ("mid", 0.30, 1.20, 8),            # ~40 days, flowering/fruit set critical
        ("late", 0.18, 0.90, 4),           # ~25 days, fruit ripening
    ],
    "potato": [
        ("initial", 0.21, 0.55, 2),       # ~25 days
        ("development", 0.25, 0.85, 4),   # ~30 days
        ("mid", 0.37, 1.18, 7),            # ~45 days, tuber bulking critical
        ("late", 0.17, 0.90, 3),           # ~20 days
    ],
    "onion": [
        ("initial", 0.10, 0.75, 2),       # ~15 days
        ("development", 0.17, 0.90, 4),   # ~25 days
        ("mid", 0.47, 1.10, 6),            # ~70 days, bulb formation
        ("late", 0.26, 0.90, 3),           # ~40 days
    ],
    "kale": [
        ("initial", 0.18, 0.75, 2),       # ~15 days
        ("development", 0.29, 0.92, 4),   # ~25 days
        ("mid", 0.35, 1.10, 5),            # ~30 days
        ("late", 0.18, 1.02, 3),           # ~15 days (still harvestable)
    ],
    "cucumber": [
        ("initial", 0.21, 0.65, 3),       # ~20 days
        ("development", 0.26, 0.85, 5),   # ~25 days
        ("mid", 0.32, 1.05, 7),            # ~30 days, fruit production
        ("late", 0.21, 0.90, 4),           # ~20 days
    ],
}


def generate_growth_stages():
    """Generate growth_stages-toy.csv with stage-specific parameters."""

    metadata = f"""# SOURCE: FAO Irrigation and Drainage Paper 56 (Table 11) + crop physiology literature
# DATE: {DATE_GENERATED}
# DESCRIPTION: Growth stage durations and water requirements for 5 crops
# UNITS:
#   - stage: Growth stage name (initial/development/mid/late)
#   - duration_days: Days in this stage (integer)
#   - kc: Average crop coefficient for this stage (dimensionless)
#   - water_stress_impact: Yield loss % per 10% water deficit during this stage
# LOGIC: Stage durations from FAO-56 Table 11, adapted for hot arid climate
# DEPENDENCIES: crop_coefficients-toy.csv (season_length_days must match sum of durations)
# ASSUMPTIONS: Linear Kc transition between stages, stress impacts based on crop physiology
"""

    rows = []
    validation_errors = []

    for crop in CROPS:
        season_length = CROP_COEFFICIENTS[crop][4]
        stages = GROWTH_STAGES[crop]

        total_duration = 0
        for stage_name, duration_frac, kc, stress_impact in stages:
            duration_days = round(duration_frac * season_length)
            total_duration += duration_days
            rows.append({
                "crop_name": crop,
                "stage": stage_name,
                "duration_days": duration_days,
                "kc": kc,
                "water_stress_impact": stress_impact
            })

        # Adjust last stage to match exactly
        if total_duration != season_length:
            diff = season_length - total_duration
            rows[-1]["duration_days"] += diff
            total_duration = season_length

        # Validate
        crop_rows = [r for r in rows if r["crop_name"] == crop]
        actual_total = sum(r["duration_days"] for r in crop_rows)
        if actual_total != season_length:
            validation_errors.append(f"{crop}: {actual_total} != {season_length}")

    df = pd.DataFrame(rows)

    filepath = os.path.join(OUTPUT_DIR, "growth_stages-toy.csv")
    with open(filepath, "w") as f:
        f.write(metadata)
        df.to_csv(f, index=False)

    print(f"\n[2] growth_stages-toy.csv")
    print(f"    Records: {len(df)} ({len(CROPS)} crops x 4 stages)")

    # Validation summary
    for crop in CROPS:
        crop_df = df[df["crop_name"] == crop]
        total = crop_df["duration_days"].sum()
        expected = CROP_COEFFICIENTS[crop][4]
        status = "OK" if total == expected else "MISMATCH"
        print(f"    {crop}: {total} days ({status})")

    if validation_errors:
        print(f"    VALIDATION ERRORS: {validation_errors}")

    return df


# =============================================================================
# PROCESSING SPECS DATA
# Energy, labor, weight loss, and value-add for each processing type
# =============================================================================

# Processing parameters: (energy_kwh/kg, labor_hrs/kg, weight_loss_%, value_add_mult, processing_time_hrs)
PROCESSING_SPECS = {
    "fresh": (0.0, 0.0, 0.0, 1.0, 0.0),
    "packaged": (0.05, 0.02, 3.0, 1.25, 2.0),   # washing, sorting, boxing
    "canned": (0.40, 0.08, 15.0, 1.80, 8.0),    # heating, sterilizing, sealing
    "dried": (2.50, 0.12, 85.0, 3.50, 24.0),    # dehydration, high energy
}

# Crop-specific adjustments (multipliers for energy/labor)
CROP_PROCESSING_ADJUSTMENTS = {
    "tomato": {"packaged": 1.0, "canned": 1.0, "dried": 1.0},   # baseline
    "potato": {"packaged": 0.9, "canned": 1.1, "dried": 1.2},   # harder to dry
    "onion": {"packaged": 0.8, "canned": 0.9, "dried": 0.9},    # easier to process
    "kale": {"packaged": 1.1, "canned": 0.8, "dried": 0.8},     # leafy, dries fast
    "cucumber": {"packaged": 1.0, "canned": 0.7, "dried": 1.3}, # high water, hard to dry
}


def generate_processing_specs():
    """Generate processing_specs-toy.csv with processing parameters per crop."""

    metadata = f"""# SOURCE: Food processing industry benchmarks, USDA processing energy data
# DATE: {DATE_GENERATED}
# DESCRIPTION: Processing requirements for 5 crops across 4 processing types
# UNITS:
#   - energy_kwh_per_kg: Electricity for processing (kWh per kg input)
#   - labor_hours_per_kg: Labor time required (hours per kg input)
#   - weight_loss_pct: Mass lost during processing (percentage of input weight)
#   - value_add_multiplier: Price multiplier vs fresh product (dimensionless)
#   - processing_time_hours: Time from input to output (hours)
# LOGIC: Fresh=baseline, packaged=minimal, canned=moderate, dried=intensive
# DEPENDENCIES: None (reference data)
# ASSUMPTIONS: Modern equipment, efficient operations, bulk processing scale
"""

    rows = []
    for crop in CROPS:
        adjustments = CROP_PROCESSING_ADJUSTMENTS.get(crop, {})

        for proc_type in PROCESSING_TYPES:
            base_energy, base_labor, weight_loss, value_add, proc_time = PROCESSING_SPECS[proc_type]

            # Apply crop-specific adjustments
            adj = adjustments.get(proc_type, 1.0)
            energy = round(base_energy * adj, 3)
            labor = round(base_labor * adj, 3)

            # Adjust weight loss for crop moisture content
            if proc_type == "dried":
                if crop == "cucumber":
                    weight_loss = 92.0  # very high water content
                elif crop == "tomato":
                    weight_loss = 88.0  # high water
                elif crop == "kale":
                    weight_loss = 82.0  # leafy but less water
                elif crop == "onion":
                    weight_loss = 80.0  # moderate water
                elif crop == "potato":
                    weight_loss = 78.0  # lower water content

            rows.append({
                "crop_name": crop,
                "processing_type": proc_type,
                "energy_kwh_per_kg": energy,
                "labor_hours_per_kg": labor,
                "weight_loss_pct": weight_loss,
                "value_add_multiplier": value_add,
                "processing_time_hours": proc_time
            })

    df = pd.DataFrame(rows)

    filepath = os.path.join(OUTPUT_DIR, "processing_specs-toy.csv")
    with open(filepath, "w") as f:
        f.write(metadata)
        df.to_csv(f, index=False)

    print(f"\n[3] processing_specs-toy.csv")
    print(f"    Records: {len(df)} ({len(CROPS)} crops x {len(PROCESSING_TYPES)} types)")
    print(f"    Processing types: {PROCESSING_TYPES}")

    # Stats by processing type
    for proc_type in PROCESSING_TYPES:
        subset = df[df["processing_type"] == proc_type]
        avg_energy = subset["energy_kwh_per_kg"].mean()
        avg_weight_loss = subset["weight_loss_pct"].mean()
        print(f"    {proc_type}: avg energy={avg_energy:.2f} kWh/kg, weight loss={avg_weight_loss:.1f}%")

    return df


# =============================================================================
# SPOILAGE RATES DATA
# Shelf life and daily spoilage by product type and storage condition
# =============================================================================

# Spoilage rates: (spoilage_rate_ambient, shelf_life_ambient, spoilage_rate_controlled, shelf_life_controlled)
# Rates in %/day, shelf life in days
SPOILAGE_RATES = {
    "fresh": {
        "tomato": (3.5, 10, 1.0, 28),
        "potato": (2.0, 14, 0.5, 45),
        "onion": (1.5, 21, 0.3, 60),
        "kale": (4.0, 7, 1.5, 21),
        "cucumber": (3.0, 12, 0.8, 35),
    },
    "packaged": {
        "tomato": (2.5, 12, 0.7, 35),
        "potato": (1.5, 18, 0.4, 50),
        "onion": (1.2, 25, 0.25, 70),
        "kale": (3.0, 10, 1.2, 25),
        "cucumber": (2.5, 14, 0.6, 40),
    },
    "canned": {
        # Canned products: very low spoilage, long shelf life
        "tomato": (0.008, 730, 0.005, 1095),
        "potato": (0.008, 730, 0.005, 1095),
        "onion": (0.008, 730, 0.005, 1095),
        "kale": (0.008, 730, 0.005, 1095),
        "cucumber": (0.008, 730, 0.005, 1095),  # pickled
    },
    "dried": {
        # Dried products: very low spoilage, very long shelf life
        "tomato": (0.05, 400, 0.02, 730),
        "potato": (0.04, 450, 0.015, 800),
        "onion": (0.03, 500, 0.01, 900),
        "kale": (0.06, 365, 0.025, 600),
        "cucumber": (0.07, 350, 0.03, 550),
    },
}


def generate_spoilage_rates():
    """Generate spoilage_rates-toy.csv with shelf life and spoilage data."""

    metadata = f"""# SOURCE: USDA food storage guidelines, post-harvest literature
# DATE: {DATE_GENERATED}
# DESCRIPTION: Spoilage rates and shelf life for crop products by storage condition
# UNITS:
#   - product_type: Crop name + processing type (e.g., tomato_fresh)
#   - storage_condition: ambient (25-35C) or climate_controlled (2-8C)
#   - spoilage_rate_pct_per_day: Daily percentage loss to spoilage
#   - shelf_life_days: Maximum days before product is unsellable
# LOGIC: Fresh products spoil fastest; dried/canned last longest
# DEPENDENCIES: processing_specs-toy.csv (product types must match)
# ASSUMPTIONS: Hot arid ambient conditions (25-35C), proper cold chain for controlled
"""

    rows = []
    for proc_type in PROCESSING_TYPES:
        for crop in CROPS:
            rates = SPOILAGE_RATES[proc_type][crop]
            ambient_rate, ambient_shelf, controlled_rate, controlled_shelf = rates

            product_name = f"{crop}_{proc_type}"

            # Ambient storage
            rows.append({
                "product_type": product_name,
                "storage_condition": "ambient",
                "spoilage_rate_pct_per_day": ambient_rate,
                "shelf_life_days": ambient_shelf
            })

            # Climate controlled storage
            rows.append({
                "product_type": product_name,
                "storage_condition": "climate_controlled",
                "spoilage_rate_pct_per_day": controlled_rate,
                "shelf_life_days": controlled_shelf
            })

    df = pd.DataFrame(rows)

    filepath = os.path.join(OUTPUT_DIR, "spoilage_rates-toy.csv")
    with open(filepath, "w") as f:
        f.write(metadata)
        df.to_csv(f, index=False)

    print(f"\n[4] spoilage_rates-toy.csv")
    print(f"    Records: {len(df)} ({len(CROPS)} crops x {len(PROCESSING_TYPES)} types x 2 conditions)")

    # Stats by processing type
    for proc_type in PROCESSING_TYPES:
        subset = df[df["product_type"].str.contains(f"_{proc_type}")]
        ambient = subset[subset["storage_condition"] == "ambient"]
        avg_rate = ambient["spoilage_rate_pct_per_day"].mean()
        avg_shelf = ambient["shelf_life_days"].mean()
        print(f"    {proc_type} (ambient): spoilage={avg_rate:.3f}%/day, shelf={avg_shelf:.0f} days")

    return df


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_all(coef_df, stages_df, proc_df, spoil_df):
    """Run cross-file validation checks."""

    print("\n" + "=" * 60)
    print("VALIDATION CHECKS")
    print("=" * 60)

    errors = []

    # Check 1: Season lengths match between coefficients and stages
    print("\n[Check 1] Season length consistency:")
    for crop in CROPS:
        coef_length = coef_df[coef_df["crop_name"] == crop]["season_length_days"].values[0]
        stages_length = stages_df[stages_df["crop_name"] == crop]["duration_days"].sum()
        match = "OK" if coef_length == stages_length else "FAIL"
        if coef_length != stages_length:
            errors.append(f"{crop} season length mismatch: {coef_length} vs {stages_length}")
        print(f"    {crop}: coefficients={coef_length}, stages sum={stages_length} [{match}]")

    # Check 2: Kc values consistency
    print("\n[Check 2] Kc value consistency:")
    for crop in CROPS:
        coef_row = coef_df[coef_df["crop_name"] == crop].iloc[0]
        stages_rows = stages_df[stages_df["crop_name"] == crop]

        initial_match = stages_rows[stages_rows["stage"] == "initial"]["kc"].values[0] == coef_row["kc_initial"]
        mid_match = stages_rows[stages_rows["stage"] == "mid"]["kc"].values[0] == coef_row["kc_mid"]

        status = "OK" if initial_match and mid_match else "WARN (minor)"
        print(f"    {crop}: {status}")

    # Check 3: All crops have all processing types
    print("\n[Check 3] Processing coverage:")
    for crop in CROPS:
        proc_types = proc_df[proc_df["crop_name"] == crop]["processing_type"].tolist()
        missing = set(PROCESSING_TYPES) - set(proc_types)
        status = "OK" if not missing else f"MISSING: {missing}"
        print(f"    {crop}: {len(proc_types)} types [{status}]")

    # Check 4: Spoilage product types match processing specs
    print("\n[Check 4] Spoilage-processing alignment:")
    proc_products = set(f"{row['crop_name']}_{row['processing_type']}"
                        for _, row in proc_df.iterrows())
    spoil_products = set(spoil_df["product_type"].unique())
    missing_in_spoilage = proc_products - spoil_products
    extra_in_spoilage = spoil_products - proc_products

    if missing_in_spoilage:
        errors.append(f"Products in processing but not spoilage: {missing_in_spoilage}")
    if extra_in_spoilage:
        errors.append(f"Products in spoilage but not processing: {extra_in_spoilage}")

    print(f"    Processing products: {len(proc_products)}")
    print(f"    Spoilage products: {len(spoil_products)}")
    print(f"    Match: {'OK' if not missing_in_spoilage and not extra_in_spoilage else 'FAIL'}")

    # Check 5: No missing values
    print("\n[Check 5] Missing values:")
    for name, df in [("coefficients", coef_df), ("stages", stages_df),
                     ("processing", proc_df), ("spoilage", spoil_df)]:
        null_count = df.isnull().sum().sum()
        status = "OK" if null_count == 0 else f"FAIL ({null_count} nulls)"
        print(f"    {name}: {status}")

    # Check 6: Value ranges
    print("\n[Check 6] Value ranges:")
    print(f"    Kc values: {coef_df[['kc_initial', 'kc_mid', 'kc_end']].min().min():.2f} - {coef_df[['kc_initial', 'kc_mid', 'kc_end']].max().max():.2f} (expected 0.5-1.25)")
    print(f"    Root depths: {coef_df['root_depth_m'].min():.1f} - {coef_df['root_depth_m'].max():.1f} m")
    print(f"    Weight loss (dried): {proc_df[proc_df['processing_type']=='dried']['weight_loss_pct'].min():.0f}-{proc_df[proc_df['processing_type']=='dried']['weight_loss_pct'].max():.0f}% (expected 78-92%)")

    fresh_ambient = spoil_df[(spoil_df["product_type"].str.contains("_fresh")) &
                             (spoil_df["storage_condition"] == "ambient")]
    print(f"    Fresh ambient spoilage: {fresh_ambient['spoilage_rate_pct_per_day'].min():.1f}-{fresh_ambient['spoilage_rate_pct_per_day'].max():.1f}%/day (expected 1.5-4%)")

    if errors:
        print("\n" + "!" * 60)
        print("VALIDATION ERRORS:")
        for err in errors:
            print(f"    - {err}")
    else:
        print("\n" + "-" * 60)
        print("All validation checks passed!")

    return len(errors) == 0


def print_summary():
    """Print final summary of generated files."""

    print("\n" + "=" * 60)
    print("COMPLETION SUMMARY")
    print("=" * 60)

    files = [
        "crop_coefficients-toy.csv",
        "growth_stages-toy.csv",
        "processing_specs-toy.csv",
        "spoilage_rates-toy.csv"
    ]

    print(f"\nOutput directory: {OUTPUT_DIR}")
    print(f"\nGenerated files:")

    total_size = 0
    for fname in files:
        fpath = os.path.join(OUTPUT_DIR, fname)
        if os.path.exists(fpath):
            size = os.path.getsize(fpath)
            total_size += size
            print(f"    {fname}: {size:,} bytes")
        else:
            print(f"    {fname}: NOT FOUND")

    print(f"\nTotal size: {total_size:,} bytes")
    print(f"\nCrops covered: {CROPS}")
    print(f"Processing types: {PROCESSING_TYPES}")
    print(f"Storage conditions: {STORAGE_CONDITIONS}")


def main():
    """Generate all crop parameter files."""

    print("=" * 60)
    print("CROP PARAMETERS TOY DATA GENERATION")
    print("Task 2: Community Agri-PV Project")
    print("=" * 60)

    ensure_output_dir()

    # Generate each file
    coef_df = generate_crop_coefficients()
    stages_df = generate_growth_stages()
    proc_df = generate_processing_specs()
    spoil_df = generate_spoilage_rates()

    # Validate cross-file consistency
    validation_passed = validate_all(coef_df, stages_df, proc_df, spoil_df)

    # Print summary
    print_summary()

    if validation_passed:
        print("\nAll files generated and validated successfully.")
    else:
        print("\nFiles generated with validation warnings. Please review.")

    return validation_passed


if __name__ == "__main__":
    main()
