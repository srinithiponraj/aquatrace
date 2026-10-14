import unittest
import json
from database.connection import init_db, get_db
from database.models import Lake

class TestDatabase(unittest.TestCase):

    def setUp(self):
        init_db()

    def test_lake_query_and_seeding(self):
        with get_db() as db:
            lakes = db.query(Lake).all()
            self.assertTrue(len(lakes) >= 1)
            first_lake = lakes[0]
            self.assertIsNotNone(first_lake.name)
            self.assertIsNotNone(first_lake.centroid_lat)
            self.assertIsNotNone(first_lake.boundary_geojson)
            # Verify boundary is valid GeoJSON
            geom = json.loads(first_lake.boundary_geojson)
            self.assertIn("type", geom)
            self.assertIn("coordinates", geom)

if __name__ == "__main__":
    unittest.main()
