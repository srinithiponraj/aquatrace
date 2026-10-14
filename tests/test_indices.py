import unittest
import numpy as np
from services.pollution_analysis import PollutionAnalysisService
from services.water_analysis import WaterAnalysisService

class TestSpectralIndices(unittest.TestCase):

    def test_mndwi_calculation(self):
        # Green = 0.4, SWIR1 = 0.1 -> (0.4 - 0.1) / (0.4 + 0.1) = 0.3 / 0.5 = 0.6
        green = np.array([0.4])
        swir1 = np.array([0.1])
        mndwi = WaterAnalysisService.calculate_mndwi(green, swir1)
        self.assertAlmostEqual(mndwi[0], 0.6, places=4)

    def test_ndci_calculation(self):
        # RedEdge = 0.3, Red = 0.1 -> (0.3 - 0.1) / (0.3 + 0.1) = 0.2 / 0.4 = 0.5
        red_edge = np.array([0.3])
        red = np.array([0.1])
        ndci = PollutionAnalysisService.calculate_ndci(red_edge, red)
        self.assertAlmostEqual(ndci[0], 0.5, places=4)

    def test_ndti_calculation(self):
        # Red = 0.25, Green = 0.15 -> (0.25 - 0.15) / (0.25 + 0.15) = 0.1 / 0.4 = 0.25
        red = np.array([0.25])
        green = np.array([0.15])
        ndti = PollutionAnalysisService.calculate_ndti(red, green)
        self.assertAlmostEqual(ndti[0], 0.25, places=4)

    def test_fai_calculation(self):
        nir = np.array([0.35])
        red = np.array([0.05])
        swir1 = np.array([0.15])
        fai = PollutionAnalysisService.calculate_fai(nir, red, swir1)
        # baseline = 0.05 + (0.15 - 0.05) * 0.1873016 = 0.05 + 0.01873 = 0.06873
        # fai = 0.35 - 0.06873 = 0.28127
        self.assertTrue(fai[0] > 0.2)

    def test_ndbi_and_ndvi(self):
        swir1 = np.array([0.3])
        nir = np.array([0.1])
        red = np.array([0.05])
        ndbi = PollutionAnalysisService.calculate_ndbi(swir1, nir)
        ndvi = PollutionAnalysisService.calculate_ndvi(nir, red)
        # NDBI = (0.3 - 0.1)/(0.3 + 0.1) = 0.5
        self.assertAlmostEqual(ndbi[0], 0.5, places=4)
        # NDVI = (0.1 - 0.05)/(0.1 + 0.05) = 0.3333
        self.assertAlmostEqual(ndvi[0], 0.3333, places=3)

if __name__ == "__main__":
    unittest.main()
