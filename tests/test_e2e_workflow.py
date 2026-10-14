import datetime
import json
import os
import unittest
from database.connection import init_db, get_db
from database.models import Lake
from utils.geo_utils import get_geometry_bbox
from app import run_analysis_pipeline
from services.report_service import report_service
from services.waterbody_service import waterbody_service

class TestE2EWorkflow(unittest.TestCase):
    def setUp(self):
        init_db()
        with get_db() as db:
            lake = db.query(Lake).filter(Lake.name.like('%Mead%')).first()
            self.lake_dict = {
                'id': lake.id,
                'name': lake.name,
                'type': 'Reservoir',
                'country': lake.country,
                'region': lake.region,
                'centroid_lat': lake.centroid_lat,
                'centroid_lon': lake.centroid_lon,
                'typical_area_km2': lake.typical_area_km2,
                'boundary': json.loads(lake.boundary_geojson),
                'boundary_source': 'Pre-configured Official Boundary'
            }

    def test_search_lake_not_in_demo_list(self):
        # Requirement 10: Search for a lake that is not in the demo list
        results = waterbody_service.search_waterbodies("Dal Lake", limit=2)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["type"], "Lake")
        self.assertIn("Dal", results[0]["name"])

    def test_search_pond_and_tank_distinct_types(self):
        # Requirement 10: Search for a pond and verify that its type is displayed separately
        pond_res = waterbody_service.search_waterbodies("Walden Pond", limit=2)
        self.assertGreater(len(pond_res), 0)
        self.assertEqual(pond_res[0]["type"], "Pond")

        tank_res = waterbody_service.search_waterbodies("Sankey Tank", limit=2)
        self.assertGreater(len(tank_res), 0)
        self.assertEqual(tank_res[0]["type"], "Tank")

    def test_end_to_end_analysis_and_report(self):
        # Date validation logic
        d_base = datetime.date(2024, 6, 1)
        d_comp = datetime.date(2024, 6, 28)
        self.assertGreaterEqual(d_comp, d_base)

        # Run pipeline with live STAC mode
        res = run_analysis_pipeline(
            waterbody=self.lake_dict,
            baseline_date=d_base,
            comparison_date=d_comp,
            use_demo=False
        )
        self.assertEqual(res["status"], "success")
        self.assertFalse(res["is_demo"])
        self.assertIn("base_bands", res)
        self.assertIn("comp_bands", res)
        self.assertTrue(res["base_bands"]["is_live_satellite"])

        # Validate analytical results
        self.assertGreater(res["base_water"]["water_area_km2"], 0)
        self.assertGreater(res["comp_water"]["water_area_km2"], 0)
        self.assertIn("pct_change", res["change_metrics"])
        self.assertIn("overall_score", res["health_score"])
        self.assertIn("flag_label", res)

        # PDF Report generation
        pdf_path = report_service.generate_pdf_report(
            lake_data=self.lake_dict,
            analysis_data=res,
            hotspots=res["hotspots"],
            source_trace=res["source_trace"],
            health_score=res["health_score"]
        )
        self.assertTrue(os.path.exists(pdf_path))
        self.assertGreater(os.path.getsize(pdf_path), 5000)

if __name__ == "__main__":
    unittest.main()
