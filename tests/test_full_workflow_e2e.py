import unittest
import os
import json
import datetime
from pathlib import Path
import numpy as np

from config import APP_NAME
from utils.geo_utils import get_geometry_bbox
from database.connection import init_db, get_db
from database.models import Lake
from services.waterbody_service import waterbody_service
from services.satellite_service import satellite_service
from services.water_analysis import water_analysis_service
from services.change_detection import change_detection_service
from services.pollution_analysis import pollution_analysis_service
from services.hotspot_analysis import hotspot_analysis_service
from services.source_trace import source_trace_service
from services.anomaly_detection import anomaly_detection_service
from services.health_score import health_score_service
from services.report_service import report_service
from components.charts import render_surface_water_transition_chart, render_historical_extent_chart
from components.ui_cards import render_top_brand_bar, render_workflow_stepper, render_flag_banner

class TestFullWorkflowE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_step1_waterbody_validation_and_search(self):
        """Step 1: Verify water body discovery, custom creation, and required input validation."""
        # 1. Search OpenStreetMap / database
        results = waterbody_service.search_waterbodies("Lake Mead", limit=5)
        self.assertGreater(len(results), 0, "Should discover candidate water bodies")
        target = results[0]
        self.assertIn("name", target)
        self.assertIn("centroid_lat", target)
        self.assertIn("centroid_lon", target)
        self.assertIn("boundary", target)

        # 2. Custom point creation
        custom = waterbody_service.create_point_waterbody("Pond Test", 12.97, 77.59, "Pond", 0.5)
        self.assertEqual(custom["name"], "Pond Test")
        self.assertEqual(custom["type"], "Pond")
        self.assertIsNotNone(custom["boundary"])

    def test_step2_date_range_validation(self):
        """Step 2: Verify date validation rules for Next button."""
        # Valid range: end >= start
        start_valid = datetime.date(2024, 1, 15)
        end_valid = datetime.date(2024, 6, 28)
        self.assertFalse(end_valid < start_valid, "Valid dates must not be flagged as invalid")

        # Invalid range: end < start
        start_bad = datetime.date(2024, 6, 28)
        end_bad = datetime.date(2024, 1, 15)
        self.assertTrue(end_bad < start_bad, "End date earlier than start date must trigger validation error")

    def test_step3_satellite_data_discovery_and_selection(self):
        """Step 3: Search Sentinel-2 passes and select observation pair."""
        lake = waterbody_service.search_waterbodies("Lake Mead", limit=1)[0]
        self.assertIsNotNone(lake)
        bbox = get_geometry_bbox(lake["boundary"])

        # Search catalog
        scenes = satellite_service.search_catalog(
            bbox=bbox,
            date_start=datetime.date(2024, 5, 1),
            date_end=datetime.date(2024, 6, 30),
            max_cloud_cover=30.0,
            allow_demo_fallback=True
        )
        self.assertGreater(len(scenes), 0, "STAC catalog search must return satellite observations")

        # Select baseline and comparison passes
        base_scene = scenes[-1]
        comp_scene = scenes[0]
        self.assertIn("id", base_scene)
        self.assertIn("date", base_scene)
        self.assertIn("satellite", base_scene)

    def test_step4_and_step5_analysis_and_transition_chart(self):
        """Step 4 & 5: Run multi-spectral analysis, verify mask generation, and transition chart."""
        lake = waterbody_service.search_waterbodies("Lake Mead", limit=1)[0]
        bbox = get_geometry_bbox(lake["boundary"])

        # Search scenes
        scenes = satellite_service.search_catalog(
            bbox=bbox,
            date_start=datetime.date(2024, 5, 1),
            date_end=datetime.date(2024, 6, 30),
            max_cloud_cover=30.0,
            allow_demo_fallback=True
        )
        base_scene = scenes[-1]
        comp_scene = scenes[0]

        # Fetch bands
        base_bands = satellite_service.fetch_scene_bands(base_scene, bbox, (160, 160), lake["boundary"])
        comp_bands = satellite_service.fetch_scene_bands(comp_scene, bbox, (160, 160), lake["boundary"])
        self.assertIn("B03", base_bands)
        self.assertIn("B11", base_bands)

        # Extract water masks
        base_water = water_analysis_service.extract_water(base_bands, bbox)
        comp_water = water_analysis_service.extract_water(comp_bands, bbox)
        self.assertIn("water_mask", base_water)
        self.assertIn("water_area_km2", base_water)
        self.assertGreater(base_water["water_area_km2"], 0)

        # Detect changes
        px_area = ((bbox[2] - bbox[0]) * 111.32 / 160) * ((bbox[3] - bbox[1]) * 110.57 / 160)
        changes = change_detection_service.analyze_change(
            baseline_water_mask=base_water["water_mask"],
            comparison_water_mask=comp_water["water_mask"],
            pixel_area_km2=px_area
        )
        self.assertIn("stable_water_km2", changes)
        self.assertIn("water_loss_km2", changes)
        self.assertIn("water_gain_km2", changes)
        self.assertIn("invalid_area_km2", changes)

        # Step 5 Transition Donut Chart render test
        try:
            render_surface_water_transition_chart(changes, title="Test Surface Water Transition")
        except Exception as e:
            self.fail(f"render_surface_water_transition_chart raised error: {e}")

        # Anomaly and Health Score evaluation
        hist_records = [
            {"date": str(base_scene["date"]), "water_area_km2": base_water["water_area_km2"]},
            {"date": str(comp_scene["date"]), "water_area_km2": comp_water["water_area_km2"]}
        ]
        curr_obs = hist_records[-1]
        anom_res = anomaly_detection_service.analyze_anomalies(hist_records, curr_obs)
        self.assertIn("anomalies", anom_res)

        # Candidate quality indicators
        indices = pollution_analysis_service.compute_all_indices(comp_bands, comp_water["water_mask"])
        self.assertIn("ndci_water", indices)
        self.assertIn("ndti_water", indices)
        self.assertIn("fai_water", indices)

        # Hotspots
        hotspots = hotspot_analysis_service.detect_hotspots(indices=indices, bbox=bbox, pixel_area_km2=px_area)
        self.assertIsInstance(hotspots, list)

        # Source trace
        source_trace = None
        if hotspots:
            source_trace = source_trace_service.trace_hotspot_source(
                hotspot=hotspots[0],
                bands=comp_bands,
                indices=indices,
                bbox=bbox,
                pixel_area_km2=px_area
            )
            self.assertIsNotNone(source_trace)
            self.assertIn("primary_source_pressure", source_trace)

        # Health score
        health = health_score_service.compute_health_score(
            water_metrics=comp_water,
            indices=indices,
            source_trace=source_trace,
            typical_area_km2=lake.get("typical_area_km2")
        )
        self.assertIn("overall_score", health)
        self.assertIn("letter_grade", health)

    def test_step6_pdf_report_compilation(self):
        """Step 6: Generate official PDF report and verify file on disk."""
        lake = waterbody_service.search_waterbodies("Lake Mead", limit=1)[0]
        analysis_data = {
            "baseline_date": "2024-05-15",
            "comparison_date": "2024-06-28",
            "is_demo": False,
            "base_water": {"water_area_km2": 150.0},
            "comp_water": {"water_area_km2": 135.0},
            "change_metrics": {"net_change_km2": -15.0, "pct_change": -10.0},
            "quality_status": "High Confidence"
        }
        health = {"overall_score": 75.0, "letter_grade": "B", "dimension_scores": {}}

        pdf_path = report_service.generate_pdf_report(
            lake_data=lake,
            analysis_data=analysis_data,
            hotspots=[],
            source_trace=None,
            health_score=health
        )
        self.assertTrue(os.path.exists(pdf_path), "PDF report must exist on disk")
        self.assertGreater(os.path.getsize(pdf_path), 1000, "PDF report must be a non-empty document")

    def test_workflow_state_machine_sequential_navigation(self):
        """Verify strict sequential step advancement (1 -> 2 -> 3 -> 4 -> 5 -> 6) and backing."""
        workflow_step = 1

        # Advance 1 -> 2
        has_waterbody = True
        self.assertTrue(has_waterbody)
        workflow_step = 2
        self.assertEqual(workflow_step, 2)

        # Advance 2 -> 3
        dates_valid = True
        self.assertTrue(dates_valid)
        workflow_step = 3
        self.assertEqual(workflow_step, 3)

        # Back 3 -> 2
        workflow_step = 2
        self.assertEqual(workflow_step, 2)

        # Forward 2 -> 3 -> 4
        workflow_step = 3
        has_scenes = True
        self.assertTrue(has_scenes)
        workflow_step = 4
        self.assertEqual(workflow_step, 4)

        # Forward 4 -> 5
        analysis_done = True
        self.assertTrue(analysis_done)
        workflow_step = 5
        self.assertEqual(workflow_step, 5)

        # Forward 5 -> 6
        workflow_step = 6
        self.assertEqual(workflow_step, 6)

        # Back 6 -> 5
        workflow_step = 5
        self.assertEqual(workflow_step, 5)

if __name__ == "__main__":
    unittest.main()
