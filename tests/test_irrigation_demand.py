# Tests for irrigation demand computation (src/irrigation_demand.py)

import unittest
import numpy as np
import pandas as pd
from pathlib import Path

from src.irrigation_demand import (
    compute_irrigation_demand,
    get_field_irrigation_specs,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT_DIR / 'settings' / 'data_registry_base.yaml'
FARM_PROFILES_PATH = ROOT_DIR / 'settings' / 'farm_profile_base.yaml'
WATER_POLICY_PATH = ROOT_DIR / 'settings' / 'water_policy_base.yaml'


def _get_demand_df():
    """Run compute_irrigation_demand with baseline config."""
    return compute_irrigation_demand(
        farm_profiles_path=FARM_PROFILES_PATH,
        registry_path=REGISTRY_PATH,
        root_dir=ROOT_DIR,
    )


class TestComputeIrrigationDemandColumns(unittest.TestCase):

    def test_compute_irrigation_demand_returns_expected_columns(self):
        """Output should have day, per-field etc/demand/crop cols, total, tds."""
        df = _get_demand_df()

        self.assertIn('day', df.columns)
        self.assertIn('total_demand_m3', df.columns)
        self.assertIn('crop_tds_requirement_ppm', df.columns)

        # Baseline has 4 fields: north_field, south_field, east_field, west_field
        for field in ['north_field', 'south_field', 'east_field', 'west_field']:
            self.assertIn(f'{field}_irrigation_mm_per_ha', df.columns)
            self.assertIn(f'{field}_demand_m3', df.columns)
            self.assertIn(f'{field}_crop', df.columns)


class TestDemandScalingFormula(unittest.TestCase):

    def test_demand_scaling_formula(self):
        """Verify demand_m3 = etc_mm * area_ha * 10 / efficiency for a known field.

        Uses north_field: area_ha=1, irrigation_system=drip (efficiency=0.90).
        On any active day, demand_m3 should equal etc_mm * 1 * 10 / 0.90.
        """
        df = _get_demand_df()
        active = df[df['north_field_crop'] != 'none']
        self.assertGreater(len(active), 0)

        # Check first 10 active days
        for _, row in active.head(10).iterrows():
            etc_mm = row['north_field_irrigation_mm_per_ha']
            demand_m3 = row['north_field_demand_m3']
            expected = round(etc_mm * 1.0 * 10 / 0.90, 3)
            self.assertAlmostEqual(demand_m3, expected, places=2,
                                   msg=f"day={row['day']}")

    def test_demand_scaling_sprinkler(self):
        """Verify demand scaling for west_field which uses sprinkler (efficiency=0.75)."""
        df = _get_demand_df()
        active = df[df['west_field_crop'] != 'none']
        self.assertGreater(len(active), 0)

        for _, row in active.head(10).iterrows():
            etc_mm = row['west_field_irrigation_mm_per_ha']
            demand_m3 = row['west_field_demand_m3']
            expected = round(etc_mm * 1.0 * 10 / 0.75, 3)
            self.assertAlmostEqual(demand_m3, expected, places=2,
                                   msg=f"day={row['day']}")


class TestFallowDaysAreZero(unittest.TestCase):

    def test_fallow_days_are_zero(self):
        """Days with no active crop should have 0 demand and 'none' crop label."""
        df = _get_demand_df()

        # north_field has fallow days (between kale and tomato seasons)
        fallow = df[df['north_field_crop'] == 'none']
        self.assertGreater(len(fallow), 0, "Expected fallow days for north_field")

        # All fallow days should have zero demand and zero ETc
        self.assertTrue((fallow['north_field_demand_m3'] == 0.0).all())
        self.assertTrue((fallow['north_field_irrigation_mm_per_ha'] == 0.0).all())


class TestTotalDemandEqualsSumOfFields(unittest.TestCase):

    def test_total_demand_equals_sum_of_fields(self):
        """total_demand_m3 should equal sum of all field _demand_m3 columns."""
        df = _get_demand_df()
        demand_cols = [c for c in df.columns if c.endswith('_demand_m3') and c != 'total_demand_m3']

        computed_total = df[demand_cols].sum(axis=1).round(3)
        np.testing.assert_allclose(
            df['total_demand_m3'].values,
            computed_total.values,
            atol=0.01,
        )


class TestTdsRequirementIsMinAcrossActiveCrops(unittest.TestCase):

    def test_tds_requirement_is_min_across_active_crops(self):
        """On days with multiple active crops, TDS should be the minimum threshold.

        TDS thresholds from crop_growth_params-research.csv:
            tomato:   1070 ppm
            potato:    730 ppm
            onion:     510 ppm
            kale:      770 ppm
            cucumber: 1070 ppm
        """
        tds_lookup = {
            'tomato': 1070, 'potato': 730, 'onion': 510,
            'kale': 770, 'cucumber': 1070,
        }

        df = _get_demand_df()
        crop_cols = [c for c in df.columns if c.endswith('_crop')]

        # Check 50 active days
        active = df[df['crop_tds_requirement_ppm'].notna()]
        for _, row in active.head(50).iterrows():
            active_crops = [row[c] for c in crop_cols if row[c] != 'none']
            expected_tds = min(tds_lookup[crop] for crop in active_crops)
            self.assertEqual(
                row['crop_tds_requirement_ppm'], expected_tds,
                msg=f"day={row['day']}, crops={active_crops}",
            )


class TestGetFieldIrrigationSpecs(unittest.TestCase):

    def test_get_field_irrigation_specs_returns_all_fields(self):
        """Should return one entry per field linked to the water system."""
        specs = get_field_irrigation_specs(
            farm_profiles_path=FARM_PROFILES_PATH,
            registry_path=REGISTRY_PATH,
            root_dir=ROOT_DIR,
        )

        # Baseline has 4 fields on main_irrigation
        expected_fields = {'north_field', 'south_field', 'east_field', 'west_field'}
        self.assertEqual(set(specs.keys()), expected_fields)

        # Each entry should have irrigation_system and application_energy_kwh_per_m3
        for field_name, field_spec in specs.items():
            self.assertIn('irrigation_system', field_spec)
            self.assertIn('application_energy_kwh_per_m3', field_spec)
            self.assertIsInstance(field_spec['application_energy_kwh_per_m3'], float)

        # Verify known values: drip = 0.06 kwh/m3, sprinkler = 0.12 kwh/m3
        self.assertEqual(specs['north_field']['irrigation_system'], 'drip')
        self.assertAlmostEqual(specs['north_field']['application_energy_kwh_per_m3'], 0.06)
        self.assertEqual(specs['west_field']['irrigation_system'], 'sprinkler')
        self.assertAlmostEqual(specs['west_field']['application_energy_kwh_per_m3'], 0.12)


if __name__ == '__main__':
    unittest.main()
