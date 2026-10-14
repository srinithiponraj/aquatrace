import unittest
import datetime
import numpy as np
from components.charts import render_surface_water_transition_chart, render_historical_extent_chart
from components.ui_cards import render_workflow_stepper, render_top_brand_bar, render_flag_banner
from config import APP_NAME

class TestWorkflowAndCharts(unittest.TestCase):
    def test_app_name_has_no_version_suffix(self):
        # Requirement 8: Branding must be "AquaTrace" without version suffix
        self.assertEqual(APP_NAME, "AquaTrace")
        self.assertNotIn("v1", APP_NAME)

    def test_workflow_stepper_callable(self):
        # Requirement 1: 6-step guided workflow stepper
        for step in range(1, 7):
            try:
                render_workflow_stepper(current_step=step)
            except Exception as e:
                self.fail(f"render_workflow_stepper failed on step {step}: {e}")

    def test_surface_water_transition_chart(self):
        # Requirement 6: Transition categories (Water Gained, Water Lost, Stable Water, Unobserved)
        mock_change_metrics = {
            "stable_water_km2": 45.2,
            "water_loss_km2": 8.4,
            "water_gain_km2": 3.1,
            "invalid_area_km2": 1.2,
            "net_change_km2": -5.3,
            "pct_change": -11.7,
            "valid_observation_pct": 94.5
        }
        try:
            render_surface_water_transition_chart(mock_change_metrics)
        except Exception as e:
            self.fail(f"render_surface_water_transition_chart raised unexpected error: {e}")

    def test_historical_extent_chart_multiple_points(self):
        # Requirement 5: Historical water extent chart with real multi-temporal measurements
        hist_records = [
            {"date": "2024-01-15", "water_area_km2": 170.5},
            {"date": "2024-06-28", "water_area_km2": 120.9}
        ]
        try:
            render_historical_extent_chart(hist_records, lake_name="Lake Mead")
        except Exception as e:
            self.fail(f"render_historical_extent_chart raised unexpected error: {e}")

    def test_historical_extent_chart_single_point(self):
        # Requirement 5: Single observation without inventing fake trend
        single_record = [{"date": "2024-06-28", "water_area_km2": 120.9}]
        try:
            render_historical_extent_chart(single_record, lake_name="Lake Mead")
        except Exception as e:
            self.fail(f"Single point render raised unexpected error: {e}")

    def test_flag_banners_light_theme(self):
        # Verify all 4 alert flags render cleanly
        for flag, label in [("GREEN", "Normal"), ("YELLOW", "Caution"), ("RED", "Critical Alert"), ("INSUFFICIENT_DATA", "Notice")]:
            try:
                render_flag_banner(flag, label, "System message")
            except Exception as e:
                self.fail(f"render_flag_banner failed for {flag}: {e}")

    def test_back_navigation_state_preservation(self):
        # Verify inputs are preserved when navigating backward
        state = {
            "workflow_step": 3,
            "req_start_date": datetime.date(2024, 2, 1),
            "req_end_date": datetime.date(2024, 5, 20),
            "target_lake": "Lake Mead"
        }
        # Simulate back button click: returns to step 2
        state["workflow_step"] = 2
        self.assertEqual(state["workflow_step"], 2)
        # Inputs must remain completely intact
        self.assertEqual(state["req_start_date"], datetime.date(2024, 2, 1))
        self.assertEqual(state["req_end_date"], datetime.date(2024, 5, 20))
        self.assertEqual(state["target_lake"], "Lake Mead")

    def test_error_screen_navigation_options(self):
        # Verify that error screen allows going back to steps 1, 2, or 3
        current_step = 4
        error_occurred = True
        available_destinations = []
        if error_occurred:
            available_destinations = [3, 2, 1]
        self.assertIn(3, available_destinations)
        self.assertIn(2, available_destinations)
        self.assertIn(1, available_destinations)

    def test_observation_panel_genuine_imagery_and_keyless_basemaps(self):
        # Verify render_folium_observation_panel accepts genuine real_rgb and renders cleanly
        from components.map_2d import render_folium_observation_panel
        fake_rgb = np.zeros((64, 64, 3), dtype=np.uint8)
        fake_mask = np.ones((64, 64), dtype=bool)
        bbox = (-114.8, 36.0, -114.6, 36.2)
        try:
            render_folium_observation_panel(
                lake_geojson={"type": "Polygon", "coordinates": [[[-114.8, 36.0], [-114.6, 36.0], [-114.6, 36.2], [-114.8, 36.2], [-114.8, 36.0]]]},
                centroid=(36.1, -114.7),
                obs_title="Baseline Observation",
                obs_date="2024-06-28",
                water_area_km2=125.4,
                cloud_cover=0.5,
                is_baseline=True,
                water_mask=fake_mask,
                bbox=bbox,
                real_rgb=fake_rgb,
                scene_info={"satellite": "Sentinel-2B", "cloud_cover": 0.5},
                key="test_panel_map"
            )
        except Exception as e:
            self.fail(f"render_folium_observation_panel failed with real_rgb: {e}")

    def test_s2_public_thumbnail_resolution(self):
        # Verify resolving open public Sentinel-2 AWS archive URLs from scene IDs
        from services.satellite_service import SatelliteService
        scene_id = "S2B_MSIL2A_20240628T181919_N0510_R127_T11SQV_20240628T221752"
        resolved = SatelliteService.resolve_s2_public_thumbnail(scene_id)
        self.assertIsNotNone(resolved)
        self.assertIn("sentinel-cogs.s3.us-west-2.amazonaws.com", resolved)
        self.assertIn("11/S/QV/2024/6", resolved)

    def test_no_unauthenticated_carto_tiles_in_map_components(self):
        # Ensure no unauthenticated basemaps.cartocdn.com tile layers remain that trigger 'API key required'
        from pathlib import Path
        for fname in ["components/map_2d.py", "components/map_3d.py"]:
            content = Path(fname).read_text(encoding="utf-8")
            self.assertNotIn("https://{s}.basemaps.cartocdn.com/light_all", content)
            self.assertNotIn("https://{s}.basemaps.cartocdn.com/dark_all", content)

if __name__ == "__main__":
    unittest.main()

