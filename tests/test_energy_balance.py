"""Integration tests for energy balance simulation outputs.

Validates daily_energy_balance.csv and daily_energy_generation.csv against
physical constraints that must always hold. Tests use real simulation output,
not mocked data.
"""

import pandas as pd
import pytest
from pathlib import Path

SIMULATION_DIR = Path(__file__).parent.parent / "simulation"
BALANCE_PATH = SIMULATION_DIR / "daily_energy_balance.csv"
GENERATION_PATH = SIMULATION_DIR / "daily_energy_generation.csv"

# Battery policy constants (from current config)
BATTERY_SOC_MIN = 0.20
BATTERY_SOC_MAX = 0.95
BATTERY_CAPACITY_KWH = 200.0

# Floating-point tolerance for energy conservation checks
TOLERANCE_KWH = 0.01


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def balance():
    return pd.read_csv(BALANCE_PATH, parse_dates=["day"])


@pytest.fixture(scope="module")
def generation():
    return pd.read_csv(GENERATION_PATH, parse_dates=["day"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_battery_columns(df):
    required = [
        "battery_soc_kwh", "battery_soc_fraction",
        "battery_charge_kwh", "battery_discharge_kwh",
        "battery_renewable_fraction",
    ]
    return all(col in df.columns for col in required)


def _has_generator_columns(df):
    required = ["generator_kwh", "generator_fuel_liters", "generator_runtime_hours"]
    return all(col in df.columns for col in required)


def _solar_columns(df):
    """Return all individual solar/agripv generation columns (exclude totals)."""
    return [
        c for c in df.columns
        if (c.endswith("_solar_kwh") or c.endswith("_agripv_kwh"))
        and c != "total_solar_kwh"
    ]


def _wind_columns(df):
    """Return all individual wind generation columns (exclude totals)."""
    return [
        c for c in df.columns
        if c.endswith("_wind_kwh") and c != "total_wind_kwh"
        and c != "total_renewable_kwh"
    ]


# ---------------------------------------------------------------------------
# Energy conservation tests (daily_energy_balance.csv)
# ---------------------------------------------------------------------------

class TestEnergyConservation:
    """Energy balance must close on every day."""

    def test_surplus_day_conservation(self, balance):
        """On surplus days: total_renewable = consumed + charge + export + curtailed."""
        surplus = balance[balance["renewable_surplus_kwh"] > 0]
        if surplus.empty:
            pytest.skip("No surplus days in dataset")

        supply_side = surplus["total_renewable_kwh"]
        demand_side = (
            surplus["renewable_consumed_kwh"]
            + surplus["battery_charge_kwh"]
            + surplus["grid_export_kwh"]
            + surplus["curtailed_kwh"]
        )
        diff = (supply_side - demand_side).abs()
        violations = surplus[diff > TOLERANCE_KWH]
        assert violations.empty, (
            f"{len(violations)} surplus days violate conservation. "
            f"Max error: {diff.max():.4f} kWh. "
            f"First violation: {violations.iloc[0]['day']}"
        )

    def test_deficit_day_conservation(self, balance):
        """On deficit days: total_demand = consumed + discharge + import + generator + deficit."""
        deficit_mask = (
            (balance["deficit_kwh"] > 0)
            | (balance["battery_discharge_kwh"] > 0)
            | (balance["grid_import_kwh"] > 0)
            | (balance["generator_kwh"] > 0)
        )
        deficit = balance[deficit_mask]
        if deficit.empty:
            pytest.skip("No deficit days in dataset")

        demand_side = deficit["total_demand_kwh"]
        supply_side = (
            deficit["renewable_consumed_kwh"]
            + deficit["battery_discharge_kwh"]
            + deficit["grid_import_kwh"]
            + deficit["generator_kwh"]
            + deficit["deficit_kwh"]
        )
        diff = (demand_side - supply_side).abs()
        violations = deficit[diff > TOLERANCE_KWH]
        assert violations.empty, (
            f"{len(violations)} deficit days violate conservation. "
            f"Max error: {diff.max():.4f} kWh. "
            f"First violation: {violations.iloc[0]['day']}"
        )

    def test_total_demand_composition(self, balance):
        """total_demand = community_energy_demand + water_energy_demand (exact)."""
        expected = (
            balance["community_energy_demand_kwh"]
            + balance["water_energy_demand_kwh"]
        )
        pd.testing.assert_series_equal(
            balance["total_demand_kwh"], expected,
            check_names=False,
            obj="total_demand_kwh",
        )

    def test_total_renewable_composition(self, balance):
        """total_renewable = total_solar + total_wind (exact)."""
        expected = balance["total_solar_kwh"] + balance["total_wind_kwh"]
        pd.testing.assert_series_equal(
            balance["total_renewable_kwh"], expected,
            check_names=False,
            obj="total_renewable_kwh",
        )


# ---------------------------------------------------------------------------
# Battery physics tests
# ---------------------------------------------------------------------------

class TestBatteryPhysics:
    """Battery state must respect physical and policy bounds."""

    def test_soc_fraction_within_policy_bounds(self, balance):
        if not _has_battery_columns(balance):
            pytest.skip("No battery columns present")
        soc = balance["battery_soc_fraction"]
        violations = balance[(soc < BATTERY_SOC_MIN - 1e-9) | (soc > BATTERY_SOC_MAX + 1e-9)]
        assert violations.empty, (
            f"{len(violations)} days with SOC fraction outside "
            f"[{BATTERY_SOC_MIN}, {BATTERY_SOC_MAX}]. "
            f"Range: [{soc.min():.4f}, {soc.max():.4f}]"
        )

    def test_battery_renewable_fraction_bounds(self, balance):
        if not _has_battery_columns(balance):
            pytest.skip("No battery columns present")
        frac = balance["battery_renewable_fraction"]
        violations = balance[(frac < -1e-9) | (frac > 1.0 + 1e-9)]
        assert violations.empty, (
            f"{len(violations)} days with battery_renewable_fraction outside [0, 1]. "
            f"Range: [{frac.min():.4f}, {frac.max():.4f}]"
        )

    def test_soc_kwh_equals_fraction_times_capacity(self, balance):
        if not _has_battery_columns(balance):
            pytest.skip("No battery columns present")
        expected = balance["battery_soc_fraction"] * BATTERY_CAPACITY_KWH
        diff = (balance["battery_soc_kwh"] - expected).abs()
        violations = balance[diff > TOLERANCE_KWH]
        assert violations.empty, (
            f"{len(violations)} days where battery_soc_kwh != "
            f"battery_soc_fraction * {BATTERY_CAPACITY_KWH}. "
            f"Max error: {diff.max():.4f} kWh"
        )


# ---------------------------------------------------------------------------
# Generator physics tests
# ---------------------------------------------------------------------------

class TestGeneratorPhysics:
    """Generator output must be physically consistent."""

    def test_fuel_liters_non_negative(self, balance):
        if not _has_generator_columns(balance):
            pytest.skip("No generator columns present")
        violations = balance[balance["generator_fuel_liters"] < -1e-9]
        assert violations.empty, (
            f"{len(violations)} days with negative generator_fuel_liters. "
            f"Min: {balance['generator_fuel_liters'].min():.4f}"
        )

    def test_runtime_hours_in_range(self, balance):
        if not _has_generator_columns(balance):
            pytest.skip("No generator columns present")
        hours = balance["generator_runtime_hours"]
        violations = balance[(hours < -1e-9) | (hours > 24.0 + 1e-9)]
        assert violations.empty, (
            f"{len(violations)} days with runtime_hours outside [0, 24]. "
            f"Range: [{hours.min():.4f}, {hours.max():.4f}]"
        )

    def test_zero_generation_implies_zero_fuel_and_runtime(self, balance):
        if not _has_generator_columns(balance):
            pytest.skip("No generator columns present")
        idle = balance[balance["generator_kwh"] == 0.0]
        if idle.empty:
            pytest.skip("Generator runs every day; no idle days to check")
        fuel_violations = idle[idle["generator_fuel_liters"] != 0.0]
        runtime_violations = idle[idle["generator_runtime_hours"] != 0.0]
        assert fuel_violations.empty, (
            f"{len(fuel_violations)} days with zero generation but nonzero fuel"
        )
        assert runtime_violations.empty, (
            f"{len(runtime_violations)} days with zero generation but nonzero runtime"
        )


# ---------------------------------------------------------------------------
# Metric bounds tests
# ---------------------------------------------------------------------------

class TestMetricBounds:
    """Ratio metrics must stay within [0, 1]."""

    @pytest.mark.parametrize("col", [
        "self_sufficiency_ratio",
        "self_consumption_ratio",
        "renewable_fraction",
    ])
    def test_ratio_in_unit_interval(self, balance, col):
        if col not in balance.columns:
            pytest.skip(f"Column {col} not present")
        values = balance[col]
        violations = balance[(values < -1e-9) | (values > 1.0 + 1e-9)]
        assert violations.empty, (
            f"{len(violations)} days with {col} outside [0, 1]. "
            f"Range: [{values.min():.4f}, {values.max():.4f}]"
        )


# ---------------------------------------------------------------------------
# Non-negative constraints
# ---------------------------------------------------------------------------

class TestNonNegativeEnergy:
    """All kWh columns (except total_energy_cost) must be >= 0."""

    def test_kwh_columns_non_negative(self, balance):
        kwh_cols = [
            c for c in balance.columns
            if c.endswith("_kwh") and c != "total_energy_cost"
        ]
        for col in kwh_cols:
            violations = balance[balance[col] < -1e-9]
            assert violations.empty, (
                f"Column {col} has {len(violations)} negative values. "
                f"Min: {balance[col].min():.4f}"
            )


# ---------------------------------------------------------------------------
# Energy generation tests (daily_energy_generation.csv)
# ---------------------------------------------------------------------------

class TestEnergyGeneration:
    """Generation file must satisfy accounting identities and physical bounds."""

    def test_total_solar_is_sum_of_components(self, generation):
        solar_cols = _solar_columns(generation)
        assert solar_cols, "No individual solar/agripv columns found"
        expected = generation[solar_cols].sum(axis=1)
        diff = (generation["total_solar_kwh"] - expected).abs()
        violations = generation[diff > TOLERANCE_KWH]
        assert violations.empty, (
            f"{len(violations)} days where total_solar_kwh != sum of components. "
            f"Max error: {diff.max():.4f} kWh. Columns: {solar_cols}"
        )

    def test_total_renewable_is_solar_plus_wind(self, generation):
        expected = generation["total_solar_kwh"] + generation["total_wind_kwh"]
        diff = (generation["total_renewable_kwh"] - expected).abs()
        violations = generation[diff > TOLERANCE_KWH]
        assert violations.empty, (
            f"{len(violations)} days where total_renewable != solar + wind. "
            f"Max error: {diff.max():.4f} kWh"
        )

    def test_all_generation_columns_non_negative(self, generation):
        numeric_cols = [c for c in generation.columns if c != "day"]
        for col in numeric_cols:
            violations = generation[generation[col] < -1e-9]
            assert violations.empty, (
                f"Generation column {col} has {len(violations)} negative values. "
                f"Min: {generation[col].min():.4f}"
            )

    def test_solar_degradation_over_time(self, generation):
        """Average solar output in the last year should be lower than the first year."""
        gen = generation.copy()
        gen["year"] = gen["day"].dt.year
        first_year = gen["year"].min()
        last_year = gen["year"].max()
        if first_year == last_year:
            pytest.skip("Only one year of data; cannot test degradation")

        first_avg = gen[gen["year"] == first_year]["total_solar_kwh"].mean()
        last_avg = gen[gen["year"] == last_year]["total_solar_kwh"].mean()
        assert last_avg < first_avg, (
            f"Solar degradation not observed: first year avg = {first_avg:.2f} kWh, "
            f"last year avg = {last_avg:.2f} kWh"
        )


# ---------------------------------------------------------------------------
# Cross-file consistency tests
# ---------------------------------------------------------------------------

class TestCrossFileConsistency:
    """Balance and generation files must agree on overlapping columns."""

    @pytest.mark.parametrize("col", [
        "total_solar_kwh",
        "total_wind_kwh",
        "total_renewable_kwh",
    ])
    def test_matching_values_for_overlapping_dates(self, balance, generation, col):
        merged = pd.merge(balance, generation, on="day", suffixes=("_bal", "_gen"))
        if merged.empty:
            pytest.skip("No overlapping dates between balance and generation files")

        col_bal = f"{col}_bal"
        col_gen = f"{col}_gen"
        diff = (merged[col_bal] - merged[col_gen]).abs()
        violations = merged[diff > TOLERANCE_KWH]
        assert violations.empty, (
            f"{len(violations)} days where {col} differs between balance and generation. "
            f"Max error: {diff.max():.4f} kWh. "
            f"First mismatch: {violations.iloc[0]['day']}"
        )
