import unittest
import numpy as np
from services.source_trace import source_trace_service

class TestSourceTrace(unittest.TestCase):

    def test_d8_flow_direction(self):
        # 5x5 elevation grid sloping downhill from top-left (100m) to center (50m)
        elev = np.array([
            [100, 90, 80, 70, 60],
            [90,  75, 65, 55, 50],
            [80,  65, 50, 45, 40],
            [70,  55, 45, 35, 30],
            [60,  50, 40, 30, 20]
        ], dtype=float)

        flow_dir = source_trace_service._calculate_d8_flow_direction(elev)
        self.assertEqual(flow_dir.shape, (5, 5))
        # Inner cells should have valid directions (< 8)
        self.assertTrue(np.all(flow_dir[1:4, 1:4] < 8))

    def test_catchment_delineation_and_fallback(self):
        shape = (40, 40)
        fallback_mask = source_trace_service._shoreline_buffer_fallback(20, 20, shape, radius_pixels=10)
        self.assertEqual(fallback_mask.shape, shape)
        self.assertTrue(np.sum(fallback_mask) > 50)
        self.assertTrue(fallback_mask[20, 20])

if __name__ == "__main__":
    unittest.main()
