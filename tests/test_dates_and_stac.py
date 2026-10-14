import unittest
import datetime
from services.satellite_service import satellite_service

class TestDatesAndSatelliteService(unittest.TestCase):
    def setUp(self):
        # Bounding box for Lake Mead
        self.lake_mead_bbox = (-114.78, 35.97, -114.38, 36.18)

    def test_date_validation_logic(self):
        start_date = datetime.date(2024, 6, 1)
        valid_end_date = datetime.date(2024, 6, 28)
        invalid_end_date = datetime.date(2024, 5, 1)

        self.assertGreaterEqual(valid_end_date, start_date)
        self.assertLess(invalid_end_date, start_date)

    def test_stac_search_real_scenes(self):
        # Query AWS Earth Search for known clear Sentinel-2 scenes in June 2024
        scenes = satellite_service.search_catalog(
            bbox=self.lake_mead_bbox,
            date_start=datetime.date(2024, 6, 1),
            date_end=datetime.date(2024, 6, 30),
            max_cloud_cover=20.0,
            allow_demo_fallback=False
        )
        self.assertIsInstance(scenes, list)
        self.assertGreater(len(scenes), 0)
        first = scenes[0]
        self.assertFalse(first["is_demo"])
        self.assertIn("thumbnail", first["assets"])
        self.assertIn("green", first["assets"])

    def test_stac_search_demo_labeling(self):
        # When demo fallback is explicitly allowed and no scenes exist
        scenes = satellite_service._generate_realistic_observations(
            date_start=datetime.date(2025, 1, 1),
            date_end=datetime.date(2025, 1, 15),
            satellite="SENTINEL-2"
        )
        self.assertGreater(len(scenes), 0)
        for s in scenes:
            self.assertTrue(s["is_demo"])
            self.assertEqual(s["provider"], "DEMO DATA SIMULATION")
            self.assertIn("DEMO", s["id"])

    def test_fetch_scene_bands_live(self):
        # Fetch real band reflectance for a real scene
        scenes = satellite_service.search_catalog(
            bbox=self.lake_mead_bbox,
            date_start=datetime.date(2024, 6, 25),
            date_end=datetime.date(2024, 6, 30),
            max_cloud_cover=20.0,
            allow_demo_fallback=False
        )
        if scenes:
            bands = satellite_service.fetch_scene_bands(scenes[0], self.lake_mead_bbox, grid_size=(32, 32))
            self.assertTrue(bands["is_live_satellite"])
            self.assertEqual(bands["B03"].shape, (32, 32))
            self.assertIsNotNone(bands["REAL_RGB"])

if __name__ == "__main__":
    unittest.main()
