import unittest

class TestMapComponents(unittest.TestCase):
    def test_imports_from_components_map_2d(self):
        # Test direct import from components.map_2d
        from components.map_2d import render_folium_lake_map, render_folium_observation_panel
        self.assertTrue(callable(render_folium_lake_map))
        self.assertTrue(callable(render_folium_observation_panel))

    def test_imports_from_components_package(self):
        # Test import from components package __init__.py
        from components import (
            render_folium_lake_map,
            render_folium_observation_panel,
            render_maplibre_3d,
            render_top_brand_bar,
            render_metric_cards_row,
            render_flag_banner,
            render_scientific_disclaimer
        )
        self.assertTrue(callable(render_folium_lake_map))
        self.assertTrue(callable(render_folium_observation_panel))
        self.assertTrue(callable(render_maplibre_3d))
        self.assertTrue(callable(render_top_brand_bar))
        self.assertTrue(callable(render_metric_cards_row))
        self.assertTrue(callable(render_flag_banner))
        self.assertTrue(callable(render_scientific_disclaimer))

    def test_app_py_syntax_and_imports(self):
        # Ensure app.py line 42 and all imports compile cleanly
        import py_compile
        compiled = py_compile.compile("app.py", doraise=True)
        self.assertIsNotNone(compiled)

if __name__ == "__main__":
    unittest.main()
