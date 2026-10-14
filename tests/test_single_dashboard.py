import unittest
import datetime
import numpy as np

from database.connection import init_db
from services.waterbody_service import waterbody_service
from services.satellite_service import satellite_service
from services.water_analysis import water_analysis_service
from services.change_detection import change_detection_service
from services.pollution_analysis import pollution_analysis_service
from services.hotspot_analysis import hotspot_analysis_service
from services.source_trace import source_trace_service
from services.health_score import health_score_service
from services.report_service import report_service
from components.ui_cards import (
    render_executive_summary_card,
    render_flag_banner,
    render_metric_cards_row,
    render_top_brand_bar
)
from components.charts import (
    render_surface_water_transition_chart,
    render_historical_extent_chart
)

class TestSingleDashboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_executive_summary_card_rendering(self):
        """Test executive summary card with contraction and severe hotspot."""
        mock_analysis = {
            "change_metrics": {
                "net_change_km2": -12.4,
                "pct_change": -8.5,
                "stable_water_km2": 130.0,
                "water_loss_km2": 14.0,
                "water_gain_km2": 1.6,
                "valid_observation_pct": 98.2
            },
            "hotspots": [
                {
                    "hotspot_id": "HS-01",
                    "indicator_type": "Chlorophyll_Bloom",
                    "center_lat": 36.14,
                    "center_lon": -114.42,
                    "area_ha": 45.2,
                    "severity": "Severe",
                    "inspection_priority": "High"
                }
            ],
            "health_score": {"overall_score": 62.5, "letter_grade": "C"},
            "base_scene": {"satellite": "Sentinel-2A", "cloud_cover": 2.1, "date_str": "2024-01-15 10:30 UTC"},
            "comp_scene": {"satellite": "Sentinel-2B", "cloud_cover": 3.4, "date_str": "2024-06-28 10:35 UTC"}
        }
        mock_wb = {
            "name": "Lake Mead",
            "type": "Reservoir",
            "centroid_lat": 36.14,
            "centroid_lon": -114.42,
            "typical_area_km2": 640.0,
            "boundary_source": "Official"
        }
        try:
            render_executive_summary_card(mock_analysis, mock_wb)
        except Exception as e:
            self.fail(f"render_executive_summary_card raised an exception: {e}")

    def test_single_dashboard_full_pipeline_data_structure(self):
        """Verify that a single pipeline run produces all required sections for the unified dashboard."""
        target_wb = waterbody_service.create_point_waterbody("Single Dash Pond", 36.15, -114.40, "Pond", 1.0)
        bbox = (-114.45, 36.10, -114.35, 36.20)

        # 1. Base bands
        base_scene = {
            "id": "S2A_TEST_01",
            "date": datetime.date(2024, 1, 15),
            "date_str": "2024-01-15 10:30 UTC",
            "cloud_cover": 1.5,
            "satellite": "SENTINEL-2A",
            "is_demo": True
        }
        base_bands = satellite_service.fetch_scene_bands(base_scene, bbox, grid_size=(32, 32))
        base_water = water_analysis_service.extract_water(base_bands, bbox)

        # 2. Comp bands
        comp_scene = {
            "id": "S2B_TEST_02",
            "date": datetime.date(2024, 6, 28),
            "date_str": "2024-06-28 10:35 UTC",
            "cloud_cover": 2.0,
            "satellite": "SENTINEL-2B",
            "is_demo": True
        }
        comp_bands = satellite_service.fetch_scene_bands(comp_scene, bbox, grid_size=(32, 32))
        comp_water = water_analysis_service.extract_water(comp_bands, bbox)

        # 3. Change metrics (Section C)
        change_metrics = change_detection_service.analyze_change(
            baseline_water_mask=base_water["water_mask"],
            comparison_water_mask=comp_water["water_mask"],
            pixel_area_km2=base_water["pixel_area_km2"]
        )
        self.assertIn("stable_water_km2", change_metrics)
        self.assertIn("water_loss_km2", change_metrics)
        self.assertIn("water_gain_km2", change_metrics)
        self.assertIn("pct_change", change_metrics)

        # 4. Indices (Section D)
        indices = pollution_analysis_service.compute_all_indices(comp_bands, comp_water["water_mask"])
        self.assertIn("mndwi", comp_water)
        self.assertIn("ndci_water", indices)
        self.assertIn("ndti_water", indices)
        self.assertIn("fai_water", indices)

        # 5. Hotspots (Section E)
        hotspots = hotspot_analysis_service.detect_hotspots(indices, bbox, base_water["pixel_area_km2"])
        self.assertIsInstance(hotspots, list)

        # 6. Source Trace (Section F)
        source_trace = None
        if hotspots:
            source_trace = source_trace_service.trace_hotspot_source(
                hotspot=hotspots[0],
                bands=comp_bands,
                indices=indices,
                bbox=bbox,
                pixel_area_km2=base_water["pixel_area_km2"]
            )
            self.assertIn("primary_source_pressure", source_trace)
            self.assertIn("built_up_pct", source_trace)

        # 7. Health score
        health_score = health_score_service.compute_health_score(comp_water, indices, source_trace)
        self.assertIn("overall_score", health_score)
        self.assertIn("letter_grade", health_score)

        # 8. Report compilation (Section I)
        analysis_data = {
            "baseline_date": "2024-01-15",
            "comparison_date": "2024-06-28",
            "base_water": base_water,
            "comp_water": comp_water,
            "change_metrics": change_metrics,
            "indices": indices,
            "is_demo": True
        }
        pdf_path = report_service.generate_pdf_report(
            lake_data=target_wb,
            analysis_data=analysis_data,
            hotspots=hotspots,
            source_trace=source_trace,
            health_score=health_score
        )
        self.assertTrue(pdf_path.endswith(".pdf"))

    def test_nearby_observation_suggestions_on_tight_cloud(self):
        """Verify that when cloud threshold is tight, nearby observation dates are recommended."""
        bbox = (-114.6, 36.0, -114.4, 36.2)
        suggestions = satellite_service.get_nearby_available_observations(
            bbox=bbox,
            center_date=datetime.date(2024, 6, 28),
            window_days=30
        )
        self.assertIsInstance(suggestions, list)

if __name__ == "__main__":
    unittest.main()
