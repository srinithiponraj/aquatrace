import unittest
from services.waterbody_service import waterbody_service

class TestWaterbodyService(unittest.TestCase):
    def test_search_pond(self):
        res = waterbody_service.search_waterbodies("Walden Pond", limit=2)
        self.assertGreater(len(res), 0)
        self.assertEqual(res[0]["type"], "Pond")
        self.assertIn("Walden", res[0]["name"])

    def test_search_lake(self):
        res = waterbody_service.search_waterbodies("Dal Lake", limit=2)
        self.assertGreater(len(res), 0)
        self.assertEqual(res[0]["type"], "Lake")

    def test_search_tank(self):
        res = waterbody_service.search_waterbodies("Sankey Tank", limit=2)
        self.assertGreater(len(res), 0)
        self.assertEqual(res[0]["type"], "Tank")

    def test_search_reservoir(self):
        res = waterbody_service.search_waterbodies("Lake Powell", limit=2)
        self.assertGreater(len(res), 0)
        self.assertEqual(res[0]["type"], "Reservoir")

    def test_coordinates_input(self):
        res = waterbody_service.search_waterbodies("19.6853, 85.2503")
        self.assertEqual(len(res), 1)
        self.assertAlmostEqual(res[0]["centroid_lat"], 19.6853, places=3)
        self.assertAlmostEqual(res[0]["centroid_lon"], 85.2503, places=3)
        self.assertIsNotNone(res[0]["boundary"])

    def test_point_fallback_geometry(self):
        wb = waterbody_service.create_point_waterbody("Test Pond", 12.9716, 77.5946, "Pond")
        self.assertEqual(wb["type"], "Pond")
        self.assertIn("Polygon", wb["boundary"]["type"])

if __name__ == "__main__":
    unittest.main()
