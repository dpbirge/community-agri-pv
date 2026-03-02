"""Tests for farm profile validation."""

import unittest
from pathlib import Path

from src.farm_profile import validate_no_overlap, normalize_plantings, planting_code_to_mmdd


class TestPlantingCodeToMmdd(unittest.TestCase):
    def test_oct01(self):
        self.assertEqual(planting_code_to_mmdd("oct01"), "10-01")

    def test_feb15(self):
        self.assertEqual(planting_code_to_mmdd("feb15"), "02-15")


class TestNormalizePlantings(unittest.TestCase):
    def test_single_date_per_crop(self):
        field = {"plantings": [{"crop": "kale", "plantings": ["oct01"]}]}
        out = normalize_plantings(field)
        self.assertEqual(out, [{"crop": "kale", "planting": "oct01"}])

    def test_multiple_dates_per_crop(self):
        field = {"plantings": [{"crop": "cucumber", "plantings": ["feb15", "sep01"]}]}
        out = normalize_plantings(field)
        self.assertEqual(
            out,
            [{"crop": "cucumber", "planting": "feb15"}, {"crop": "cucumber", "planting": "sep01"}],
        )


class TestValidateNoOverlap(unittest.TestCase):
    @property
    def _root(self):
        return Path(__file__).parent.parent

    def _registry(self):
        import yaml
        path = self._root / "settings" / "data_registry_base.yaml"
        return yaml.safe_load(path.read_text())

    def test_valid_config_passes(self):
        import yaml
        path = self._root / "settings" / "farm_profile_base.yaml"
        config = yaml.safe_load(path.read_text())
        validate_no_overlap(config, self._registry(), self._root)

    def test_overlapping_plantings_raises(self):
        config = {
            "farms": [
                {
                    "fields": [
                        {
                            "name": "bad_field",
                            "plantings": [
                                {"crop": "kale", "plantings": ["oct01"]},
                                {"crop": "kale", "plantings": ["dec01"]},
                            ],
                        }
                    ]
                }
            ]
        }
        # kale oct01: 85 days -> Oct 1 to ~Dec 25
        # kale dec01: 85 days -> Dec 1 to ~Feb 24
        # These overlap (Dec 1 - Dec 25)
        with self.assertRaises(ValueError) as ctx:
            validate_no_overlap(config, self._registry(), self._root)
        self.assertIn("overlapping plantings", str(ctx.exception))
        self.assertIn("bad_field", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
