"""Generate missing processed product price files.

Reads fresh crop prices and processing_specs-research.csv to create
missing processed price CSVs with value-add multipliers and ±10% noise.
"""
import pandas as pd
import numpy as np
from pathlib import Path

BASE = Path("/Users/dpbirge/GITHUB/community-agri-pv")
CROPS_DIR = BASE / "data/prices/crops"
PROCESSED_DIR = BASE / "data/prices/processed"
SPECS_PATH = BASE / "data/parameters/crops/processing_specs-research.csv"

# Missing files to generate: (processing_type, crop_name)
MISSING = [
    ("dried", "potato"),
    ("dried", "onion"),
    ("dried", "cucumber"),
    ("canned", "potato"),
    ("canned", "kale"),
    ("canned", "cucumber"),
]

def load_processing_specs():
    """Load processing specs and return dict of (crop, type) -> value_add_multiplier."""
    df = pd.read_csv(SPECS_PATH, comment="#")
    return {
        (row.crop_name, row.processing_type): row.value_add_multiplier
        for _, row in df.iterrows()
    }

def load_fresh_prices(crop_name):
    """Load fresh crop price CSV, returning DataFrame."""
    path = CROPS_DIR / f"historical_{crop_name}_prices-toy.csv"
    return pd.read_csv(path, comment="#")

def make_header(processing_type, crop_name):
    """Build metadata header matching existing file conventions."""
    # Determine LOGIC multiplier range text based on processing type
    multiplier_ranges = {
        "canned": "1.5-2.0x",
        "dried": "2.0-3.0x",
    }
    mult_range = multiplier_ranges.get(processing_type, "1.5-2.0x")

    return (
        f"# SOURCE: Synthetic data derived from raw {crop_name} prices\n"
        f"# DATE: 2026-02-18\n"
        f"# DESCRIPTION: Monthly wholesale {processing_type} {crop_name} prices (USD/kg)\n"
        f"# UNITS: usd_per_kg (USD per kilogram, wholesale)\n"
        f"# LOGIC: Base crop price x value-add multiplier ({mult_range}) with stochastic spread\n"
        f"# DEPENDENCIES: historical_{crop_name}_prices-toy.csv\n"
        f"# ASSUMPTIONS: Processing adds value through preservation, convenience, reduced spoilage\n"
        f"# GENERATION_METHOD: Multiplicative from raw prices with processing cost variation\n"
        f"# CURRENCY: All prices in USD\n"
    )

def generate_processed_prices(fresh_df, multiplier, seed):
    """Apply value-add multiplier with ±10% seeded noise to fresh prices."""
    rng = np.random.default_rng(seed)
    noise = rng.uniform(0.90, 1.10, size=len(fresh_df))
    processed_df = fresh_df.copy()
    processed_df["usd_per_kg"] = (fresh_df["usd_per_kg"] * multiplier * noise).round(4)
    return processed_df

def main():
    specs = load_processing_specs()

    for i, (proc_type, crop) in enumerate(MISSING):
        multiplier = specs[(crop, proc_type)]
        fresh_df = load_fresh_prices(crop)
        seed = 42 + i  # reproducible but different per file
        processed_df = generate_processed_prices(fresh_df, multiplier, seed)

        filename = f"historical_{proc_type}_{crop}_prices-toy.csv"
        outpath = PROCESSED_DIR / filename
        header = make_header(proc_type, crop)

        with open(outpath, "w") as f:
            f.write(header)
            processed_df.to_csv(f, index=False)

        print(f"Created: {filename}  (multiplier={multiplier}, rows={len(processed_df)})")

if __name__ == "__main__":
    main()
