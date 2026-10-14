import unittest
import numpy as np
from services.water_analysis import water_analysis_service

class TestWaterAnalysis(unittest.TestCase):

    def test_water_extraction_and_area(self):
        # 10x10 synthetic grid
        rows, cols = 10, 10
        green = np.zeros((rows, cols))
        swir1 = np.ones((rows, cols))
        # Top-left 5x5 is water (high green, low swir)
        green[:5, :5] = 0.5
        swir1[:5, :5] = 0.05

        bands = {"B03": green, "B11": swir1}
        bbox = (-114.6, 36.0, -114.4, 36.2)

        res = water_analysis_service.extract_water(bands, bbox, threshold=0.0)
        self.assertIn("water_mask", res)
        self.assertIn("water_area_km2", res)
        self.assertTrue(res["water_pixels"] >= 10)
        self.assertTrue(res["water_area_km2"] > 0)

if __name__ == "__main__":
    unittest.main()
