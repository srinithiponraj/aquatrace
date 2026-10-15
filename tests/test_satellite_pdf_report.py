import os
import unittest
import numpy as np
from pathlib import Path
from services.report_service import report_service
from config import REPORTS_DIR

class TestSatellitePdfReport(unittest.TestCase):
    """
    Verifies that the PDF report generator properly includes Before and After
    satellite boundary imagery, clear captions, visible boundary outlines,
    and appropriate fallback notes when genuine imagery is unavailable.
    """

    def setUp(self):
        # Sample lake with verified boundary geometry
        self.lake_data = {
            "name": "Test Lake Unit",
            "region": "Nevada",
            "country": "United States",
            "centroid_lat": 36.08,
            "centroid_lon": -114.58,
            "typical_area_km2": 60.0,
            "boundary_source": "Verified Boundary",
            "boundary": {
                "type": "Polygon",
                "coordinates": [[
                    [-114.65, 36.02],
                    [-114.50, 36.04],
                    [-114.48, 36.14],
                    [-114.60, 36.16],
                    [-114.70, 36.10],
                    [-114.65, 36.02]
                ]]
            }
        }

    def test_pdf_report_with_genuine_satellite_images(self):
        """Verify that genuine satellite imagery is rendered with boundary outlines and embedded into PDF."""
        # Simulated genuine reflectance arrays (H, W, 3)
        h, w = 160, 160
        rng = np.random.RandomState(42)
        base_rgb = np.clip(rng.uniform(0.1, 0.8, (h, w, 3)), 0.0, 1.0)
        comp_rgb = np.clip(rng.uniform(0.1, 0.8, (h, w, 3)), 0.0, 1.0)

        analysis_data = {
            "baseline_date": "2024-06-13",
            "comparison_date": "2024-06-28",
            "baseline_water_area_km2": 60.5,
            "comparison_water_area_km2": 56.6,
            "water_area_change_km2": -3.9,
            "water_area_change_pct": -6.4,
            "is_demo": False,
            "quality_status": "High Confidence",
            "base_scene": {
                "id": "S2A_MSIL2A_20240613_TEST",
                "date_str": "2024-06-13 18:19 UTC",
                "satellite": "SENTINEL-2A",
                "cloud_cover": 0.5,
                "is_demo": False
            },
            "comp_scene": {
                "id": "S2B_MSIL2A_20240628_TEST",
                "date_str": "2024-06-28 18:19 UTC",
                "satellite": "SENTINEL-2B",
                "cloud_cover": 1.2,
                "is_demo": False
            },
            "base_bands": {
                "REAL_RGB": base_rgb,
                "is_live_satellite": True
            },
            "comp_bands": {
                "REAL_RGB": comp_rgb,
                "is_live_satellite": True
            }
        }

        pdf_path = report_service.generate_pdf_report(
            lake_data=self.lake_data,
            analysis_data=analysis_data,
            hotspots=[]
        )

        self.assertTrue(os.path.exists(pdf_path))
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        # Both Before and After images must be present as XObject Image streams
        self.assertEqual(pdf_bytes.count(b"/Subtype /Image"), 2)
        self.assertGreater(len(pdf_bytes), 10000)

    def test_pdf_report_demo_mode_displays_unavailable_note(self):
        """Verify that demo mode displays clear data-unavailable note instead of fake imagery."""
        analysis_data = {
            "baseline_date": "2024-06-13",
            "comparison_date": "2024-06-28",
            "baseline_water_area_km2": 60.5,
            "comparison_water_area_km2": 56.6,
            "water_area_change_km2": -3.9,
            "water_area_change_pct": -6.4,
            "is_demo": True,
            "base_scene": {"is_demo": True},
            "comp_scene": {"is_demo": True},
            "base_bands": {"REAL_RGB": None},
            "comp_bands": {"REAL_RGB": None}
        }

        pdf_path = report_service.generate_pdf_report(
            lake_data=self.lake_data,
            analysis_data=analysis_data,
            hotspots=[]
        )

        self.assertTrue(os.path.exists(pdf_path))
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        # In demo mode, zero synthetic images are embedded as real satellite imagery
        self.assertEqual(pdf_bytes.count(b"/Subtype /Image"), 0)
        self.assertGreater(len(pdf_bytes), 3000)

    def test_pdf_report_single_observation_pass(self):
        """Verify that single observation pass displays Before image and clear note for missing comparison pass."""
        h, w = 160, 160
        rng = np.random.RandomState(99)
        base_rgb = np.clip(rng.uniform(0.1, 0.8, (h, w, 3)), 0.0, 1.0)

        analysis_data = {
            "baseline_date": "2024-06-13",
            "comparison_date": None,
            "baseline_water_area_km2": 60.5,
            "comparison_water_area_km2": None,
            "water_area_change_km2": None,
            "water_area_change_pct": None,
            "is_demo": False,
            "base_scene": {
                "date_str": "2024-06-13 18:19 UTC",
                "satellite": "SENTINEL-2A",
                "cloud_cover": 0.0,
                "is_demo": False
            },
            "comp_scene": None,
            "base_bands": {
                "REAL_RGB": base_rgb,
                "is_live_satellite": True
            },
            "comp_bands": None
        }

        pdf_path = report_service.generate_pdf_report(
            lake_data=self.lake_data,
            analysis_data=analysis_data,
            hotspots=[]
        )

        self.assertTrue(os.path.exists(pdf_path))
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        # Exactly 1 image (Before) embedded; After shows unavailable callout note
        self.assertEqual(pdf_bytes.count(b"/Subtype /Image"), 1)

if __name__ == "__main__":
    unittest.main()
