import unittest
import os
from services.report_service import report_service

class TestReportService(unittest.TestCase):

    def test_pdf_generation(self):
        lake_data = {
            "name": "Test Lake Unit",
            "region": "Test Region",
            "country": "Test Country",
            "centroid_lat": 12.93,
            "centroid_lon": 77.68,
            "typical_area_km2": 3.5
        }
        analysis_data = {
            "baseline_date": "2025-04-15",
            "comparison_date": "2025-10-10",
            "baseline_water_area_km2": 3.65,
            "comparison_water_area_km2": 3.42,
            "water_area_change_km2": -0.23,
            "water_area_change_pct": -6.3,
            "quality_status": "High Confidence"
        }
        hotspots = [{
            "hotspot_id": "HS-TEST-01",
            "indicator_type": "NDCI_ALGAE",
            "center_lat": 12.935,
            "center_lon": 77.682,
            "area_ha": 4.2,
            "max_val": 0.28,
            "severity": "High",
            "inspection_priority": "Immediate"
        }]

        pdf_path = report_service.generate_pdf_report(lake_data, analysis_data, hotspots)
        self.assertTrue(os.path.exists(pdf_path))
        self.assertTrue(os.path.getsize(pdf_path) > 1000)

if __name__ == "__main__":
    unittest.main()
