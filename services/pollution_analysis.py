import numpy as np
from typing import Dict, Any, Optional
from utils.logger import logger

class PollutionAnalysisService:
    """
    Computes potential pollution indicator indices on Sentinel-2 Level-2A imagery:
    - NDCI (Normalized Difference Chlorophyll Index)
    - NDTI (Normalized Difference Turbidity Index)
    - FAI (Floating Algae Index)
    - NDBI (Normalized Difference Built-up Index)
    - NDVI (Normalized Difference Vegetation Index)
    - BSI (Bare Soil Index)
    """

    EPS = 1e-6

    @classmethod
    def calculate_ndci(cls, red_edge: np.ndarray, red: np.ndarray) -> np.ndarray:
        """
        Normalized Difference Chlorophyll Index (NDCI):
        Formula: (RedEdge1 - Red) / (RedEdge1 + Red)
        Sentinel-2: (B05 - B04) / (B05 + B04)
        Identifies candidate areas consistent with elevated chlorophyll-a / phytoplankton activity.
        """
        denom = red_edge + red
        denom = np.where(denom == 0, cls.EPS, denom)
        ndci = (red_edge - red) / denom
        return np.clip(ndci, -1.0, 1.0)

    @classmethod
    def calculate_ndti(cls, red: np.ndarray, green: np.ndarray) -> np.ndarray:
        """
        Normalized Difference Turbidity Index (NDTI):
        Formula: (Red - Green) / (Red + Green)
        Sentinel-2: (B04 - B03) / (B04 + B03)
        Identifies candidate areas with patterns consistent with suspended sediment and turbidity.
        """
        denom = red + green
        denom = np.where(denom == 0, cls.EPS, denom)
        ndti = (red - green) / denom
        return np.clip(ndti, -1.0, 1.0)

    @classmethod
    def calculate_fai(cls, nir: np.ndarray, red: np.ndarray, swir1: np.ndarray) -> np.ndarray:
        """
        Floating Algae Index (FAI):
        Formula: NIR - (Red + (SWIR1 - Red) * ((lambda_NIR - lambda_Red) / (lambda_SWIR1 - lambda_Red)))
        Sentinel-2: B08 - (B04 + (B11 - B04) * 0.1873)
        Identifies floating surface vegetation, macro-algae, and water hyacinth scums.
        """
        # Baseline lambda: Red=665nm, NIR=842nm, SWIR1=1610nm
        # slope_weight = (842 - 665) / (1610 - 665) = 177 / 945 = 0.1873016
        baseline = red + (swir1 - red) * 0.1873016
        fai = nir - baseline
        return np.clip(fai, -1.0, 1.0)

    @classmethod
    def calculate_ndbi(cls, swir1: np.ndarray, nir: np.ndarray) -> np.ndarray:
        """
        Normalized Difference Built-up Index (NDBI):
        Formula: (SWIR1 - NIR) / (SWIR1 + NIR)
        Sentinel-2: (B11 - B08) / (B11 + B08)
        Built-up and impervious surface proxy.
        """
        denom = swir1 + nir
        denom = np.where(denom == 0, cls.EPS, denom)
        ndbi = (swir1 - nir) / denom
        return np.clip(ndbi, -1.0, 1.0)

    @classmethod
    def calculate_ndvi(cls, nir: np.ndarray, red: np.ndarray) -> np.ndarray:
        """
        Normalized Difference Vegetation Index (NDVI):
        Formula: (NIR - Red) / (NIR + Red)
        Sentinel-2: (B08 - B04) / (B08 + B04)
        Terrestrial and shoreline vegetation proxy.
        """
        denom = nir + red
        denom = np.where(denom == 0, cls.EPS, denom)
        ndvi = (nir - red) / denom
        return np.clip(ndvi, -1.0, 1.0)

    @classmethod
    def calculate_bsi(cls, swir1: np.ndarray, red: np.ndarray, nir: np.ndarray, blue: np.ndarray) -> np.ndarray:
        """
        Bare Soil Index (BSI):
        Formula: ((SWIR1 + Red) - (NIR + Blue)) / ((SWIR1 + Red) + (NIR + Blue))
        Sentinel-2: ((B11 + B04) - (B08 + B02)) / ((B11 + B04) + (B08 + B02))
        """
        numer = (swir1 + red) - (nir + blue)
        denom = (swir1 + red) + (nir + blue)
        denom = np.where(denom == 0, cls.EPS, denom)
        bsi = numer / denom
        return np.clip(bsi, -1.0, 1.0)

    def compute_all_indices(
        self,
        bands: Dict[str, np.ndarray],
        water_mask: np.ndarray
    ) -> Dict[str, Any]:
        """
        Computes all spectral indicators masked to the lake water surface,
        as well as catchment land cover indices.
        """
        b02 = bands["B02"]
        b03 = bands["B03"]
        b04 = bands["B04"]
        b05 = bands["B05"]
        b08 = bands["B08"]
        b11 = bands["B11"]

        # Water indices
        ndci = self.calculate_ndci(b05, b04)
        ndti = self.calculate_ndti(b04, b03)
        fai = self.calculate_fai(b08, b04, b11)

        # Land cover proxies
        ndbi = self.calculate_ndbi(b11, b08)
        ndvi = self.calculate_ndvi(b08, b04)
        bsi = self.calculate_bsi(b11, b04, b08, b02)

        # Mask water-specific indices outside water
        ndci_water = np.where(water_mask, ndci, np.nan)
        ndti_water = np.where(water_mask, ndti, np.nan)
        fai_water = np.where(water_mask, fai, np.nan)

        return {
            "ndci": ndci,
            "ndti": ndti,
            "fai": fai,
            "ndci_water": ndci_water,
            "ndti_water": ndti_water,
            "fai_water": fai_water,
            "ndbi": ndbi,
            "ndvi": ndvi,
            "bsi": bsi,
            "water_mask": water_mask
        }

pollution_analysis_service = PollutionAnalysisService()
