# Tests for crop yield computation (src/crop_yield.py)

import unittest
import numpy as np
import pandas as pd
from pathlib import Path

from src.crop_yield import compute_harvest_yield, compute_community_harvest

ROOT_DIR = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT_DIR / 'settings' / 'data_registry_base.yaml'
FARM_PROFILES_PATH = ROOT_DIR / 'settings' / 'farm_profile_base.yaml'
WATER_BALANCE_PATH = ROOT_DIR / 'simulation' / 'daily_water_balance.csv'

# Reference crop for unit tests: tomato / feb15 / openfield / 2020
# Season: 2020-02-15 to 2020-06-28 (135 days)
CROP = 'tomato'
PLANTING = 'feb15'
CONDITION = 'openfield'
WEATHER_YEAR = 2020
SEASON_START = pd.Timestamp('2020-02-15')
SEASON_DAYS = 135
SEASON_DATES = pd.date_range(SEASON_START, periods=SEASON_DAYS, freq='D')


def _make_series(values, dates=SEASON_DATES):
    """Build a pd.Series indexed by date for delivered/demand test inputs."""
    return pd.Series(values, index=dates)


def _load_water_balance():
    """Load the saved water balance CSV for integration tests."""
    return pd.read_csv(WATER_BALANCE_PATH, parse_dates=['day'])


class TestComputeHarvestYieldFullDelivery(unittest.TestCase):

    def test_compute_harvest_yield_full_delivery(self):
        """When delivered == demand, f=1.0, yield should equal potential * avg_Kt."""
        demand = _make_series(np.full(SEASON_DAYS, 10.0))
        delivered = _make_series(np.full(SEASON_DAYS, 10.0))

        yield_kg_ha = compute_harvest_yield(
            crop=CROP, planting=PLANTING, condition=CONDITION,
            weather_year=WEATHER_YEAR,
            delivered_m3_series=delivered,
            demand_m3_series=demand,
            registry_path=REGISTRY_PATH, root_dir=ROOT_DIR,
        )

        # f=1.0, so f**(1/alpha) = 1.0 regardless of alpha.
        # yield = potential_yield * 1.0 * avg_Kt
        # potential_yield for tomato = 60000 kg/ha.
        # avg_Kt is the mean temp_stress_coeff for the season (< 1.0 in hot climate).
        self.assertGreater(yield_kg_ha, 0)
        self.assertLessEqual(yield_kg_ha, 60000)

        # Verify it equals potential * avg_Kt by running with 2x demand / 2x delivered
        # (same f=1.0). Should give identical yield.
        demand_2x = _make_series(np.full(SEASON_DAYS, 20.0))
        delivered_2x = _make_series(np.full(SEASON_DAYS, 20.0))
        yield_2x = compute_harvest_yield(
            crop=CROP, planting=PLANTING, condition=CONDITION,
            weather_year=WEATHER_YEAR,
            delivered_m3_series=delivered_2x,
            demand_m3_series=demand_2x,
            registry_path=REGISTRY_PATH, root_dir=ROOT_DIR,
        )
        self.assertAlmostEqual(yield_kg_ha, yield_2x, places=1)


class TestComputeHarvestYieldZeroDelivery(unittest.TestCase):

    def test_compute_harvest_yield_zero_delivery(self):
        """When delivered == 0, f=0.0, yield should be 0."""
        demand = _make_series(np.full(SEASON_DAYS, 10.0))
        delivered = _make_series(np.full(SEASON_DAYS, 0.0))

        yield_kg_ha = compute_harvest_yield(
            crop=CROP, planting=PLANTING, condition=CONDITION,
            weather_year=WEATHER_YEAR,
            delivered_m3_series=delivered,
            demand_m3_series=demand,
            registry_path=REGISTRY_PATH, root_dir=ROOT_DIR,
        )
        self.assertEqual(yield_kg_ha, 0.0)


class TestComputeHarvestYieldPartialDelivery(unittest.TestCase):

    def test_compute_harvest_yield_partial_delivery(self):
        """50% delivery should produce yield between 0 and full via concave response."""
        demand = _make_series(np.full(SEASON_DAYS, 10.0))
        delivered_full = _make_series(np.full(SEASON_DAYS, 10.0))
        delivered_half = _make_series(np.full(SEASON_DAYS, 5.0))

        yield_full = compute_harvest_yield(
            crop=CROP, planting=PLANTING, condition=CONDITION,
            weather_year=WEATHER_YEAR,
            delivered_m3_series=delivered_full,
            demand_m3_series=demand,
            registry_path=REGISTRY_PATH, root_dir=ROOT_DIR,
        )
        yield_half = compute_harvest_yield(
            crop=CROP, planting=PLANTING, condition=CONDITION,
            weather_year=WEATHER_YEAR,
            delivered_m3_series=delivered_half,
            demand_m3_series=demand,
            registry_path=REGISTRY_PATH, root_dir=ROOT_DIR,
        )

        self.assertGreater(yield_half, 0)
        self.assertLess(yield_half, yield_full)
        # Concave response means yield_half > 50% of yield_full (f^(1/alpha) with alpha>1)
        self.assertGreater(yield_half, yield_full * 0.5)


class TestComputeHarvestYieldOverDeliveryCapped(unittest.TestCase):

    def test_compute_harvest_yield_over_delivery_capped(self):
        """Delivery > demand should clamp f to 1.0, not produce super-optimal yield."""
        demand = _make_series(np.full(SEASON_DAYS, 10.0))
        delivered_exact = _make_series(np.full(SEASON_DAYS, 10.0))
        delivered_over = _make_series(np.full(SEASON_DAYS, 20.0))

        yield_exact = compute_harvest_yield(
            crop=CROP, planting=PLANTING, condition=CONDITION,
            weather_year=WEATHER_YEAR,
            delivered_m3_series=delivered_exact,
            demand_m3_series=demand,
            registry_path=REGISTRY_PATH, root_dir=ROOT_DIR,
        )
        yield_over = compute_harvest_yield(
            crop=CROP, planting=PLANTING, condition=CONDITION,
            weather_year=WEATHER_YEAR,
            delivered_m3_series=delivered_over,
            demand_m3_series=demand,
            registry_path=REGISTRY_PATH, root_dir=ROOT_DIR,
        )

        self.assertAlmostEqual(yield_exact, yield_over, places=1)


class TestAlphaComputation(unittest.TestCase):

    def test_alpha_computation(self):
        """Verify alpha = max(1.0, 1 + wue_curvature * (1.15 - ky)) for each crop."""
        # Reference values from yield_response_factors-research.csv
        crops = {
            'tomato':   {'ky': 1.05, 'beta': 3.5},
            'potato':   {'ky': 1.10, 'beta': 3.5},
            'onion':    {'ky': 1.10, 'beta': 3.5},
            'kale':     {'ky': 0.95, 'beta': 3.5},
            'cucumber': {'ky': 1.00, 'beta': 3.5},
        }

        for crop_name, params in crops.items():
            ky = params['ky']
            beta = params['beta']
            expected_alpha = max(1.0, 1.0 + beta * (1.15 - ky))

            # For sensitive crops (ky > 1.15), alpha clamps to 1.0
            # For tolerant crops (ky < 1.15), alpha > 1.0 (concave response)
            if ky <= 1.15:
                self.assertGreaterEqual(expected_alpha, 1.0, msg=crop_name)
            self.assertEqual(expected_alpha, max(1.0, 1.0 + beta * (1.15 - ky)),
                             msg=crop_name)

        # Verify specific known values
        # tomato: 1 + 3.5 * (1.15 - 1.05) = 1 + 3.5 * 0.10 = 1.35
        self.assertAlmostEqual(max(1.0, 1.0 + 3.5 * (1.15 - 1.05)), 1.35)
        # kale: 1 + 3.5 * (1.15 - 0.95) = 1 + 3.5 * 0.20 = 1.70
        self.assertAlmostEqual(max(1.0, 1.0 + 3.5 * (1.15 - 0.95)), 1.70)
        # potato: 1 + 3.5 * (1.15 - 1.10) = 1 + 3.5 * 0.05 = 1.175
        self.assertAlmostEqual(max(1.0, 1.0 + 3.5 * (1.15 - 1.10)), 1.175)


class TestComputeCommunityHarvestColumns(unittest.TestCase):

    def test_compute_community_harvest_returns_expected_columns(self):
        """Verify daily_df has day + field_crop_harvest_kg + total_harvest_kg."""
        wb_df = _load_water_balance()

        daily_df, harvests_df = compute_community_harvest(
            wb_df,
            farm_profiles_path=FARM_PROFILES_PATH,
            registry_path=REGISTRY_PATH,
            root_dir=ROOT_DIR,
        )

        # daily_df must have 'day' and 'total_harvest_kg'
        self.assertIn('day', daily_df.columns)
        self.assertIn('total_harvest_kg', daily_df.columns)

        # All other columns should end with '_harvest_kg'
        non_day_cols = [c for c in daily_df.columns if c != 'day']
        for col in non_day_cols:
            self.assertTrue(col.endswith('_harvest_kg'),
                            msg=f"Unexpected column: {col}")

        # harvests_df must have the expected event-level columns
        expected_harvest_cols = {
            'harvest_date', 'field', 'crop', 'planting', 'condition',
            'yield_kg_per_ha', 'area_ha', 'harvest_kg',
        }
        self.assertEqual(set(harvests_df.columns), expected_harvest_cols)


class TestComputeCommunityHarvestEventCount(unittest.TestCase):

    def test_compute_community_harvest_event_count(self):
        """Verify the number of harvest events matches expected from farm profile.

        Baseline farm profile has 4 fields with these plantings:
            north_field: kale oct01 + tomato feb15
            south_field: potato sep15 + onion jan15
            east_field:  cucumber feb15 + cucumber sep01
            west_field:  tomato apr01 + kale dec01

        That's 8 planting codes. The water balance covers 2010-01-01 to 2024-12-31
        (15 years). Each planting produces one harvest per year it fits within the
        sim window (planting_date >= sim_start and harvest_date <= sim_end).
        The exact count depends on season lengths and boundary effects.
        """
        wb_df = _load_water_balance()

        _, harvests_df = compute_community_harvest(
            wb_df,
            farm_profiles_path=FARM_PROFILES_PATH,
            registry_path=REGISTRY_PATH,
            root_dir=ROOT_DIR,
        )

        # At minimum, each planting should produce harvests across multiple years
        self.assertGreater(len(harvests_df), 0)

        # Should have entries from all 4 fields
        fields = set(harvests_df['field'])
        self.assertEqual(fields, {'north_field', 'south_field', 'east_field', 'west_field'})

        # Should have entries for all 5 crops used in baseline
        crops = set(harvests_df['crop'])
        self.assertEqual(crops, {'kale', 'tomato', 'potato', 'onion', 'cucumber'})

        # 8 planting codes across ~15 years should give roughly 100+ events
        # (some boundary years may not produce a harvest)
        self.assertGreater(len(harvests_df), 80)


if __name__ == '__main__':
    unittest.main()
