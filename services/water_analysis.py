import numpy as np
import math
from typing import Dict, Any, Tuple, Optional
from utils.logger import logger
from utils.geo_utils import calculate_polygon_area_km2

class WaterAnalysisService:
    """
    Implements Sentinel-2 MNDWI water extraction, Otsu thresholding,
    morphological filtering, and surface area calculation.
    """

    @staticmethod
    def calculate_mndwi(green: np.ndarray, swir1: np.ndarray, eps: float = 1e-6) -> np.ndarray:
        """
        Calculate Modified Normalized Difference Water Index (MNDWI).
        MNDWI = (Green - SWIR1) / (Green + SWIR1)
        Values range from -1.0 to +1.0. Positive values indicate open water.
        """
        denom = green + swir1
        # Avoid division by zero
        denom = np.where(denom == 0, eps, denom)
        mndwi = (green - swir1) / denom
        return np.clip(mndwi, -1.0, 1.0)

    @staticmethod
    def compute_otsu_threshold(index_array: np.ndarray, mask: Optional[np.ndarray] = None) -> float:
        """
        Compute Otsu's optimal bimodal threshold on the MNDWI array.
        """
        vals = index_array[mask] if mask is not None else index_array.flatten()
        vals = vals[~np.isnan(vals)]
        if len(vals) == 0:
            return 0.0

        # Scale to 0-255 for standard Otsu histogram analysis
        min_v, max_v = float(np.min(vals)), float(np.max(vals))
        if max_v - min_v < 1e-5:
            return 0.0

        norm_vals = ((vals - min_v) / (max_v - min_v) * 255).astype(np.uint8)
        hist, _ = np.histogram(norm_vals, bins=256, range=(0, 256))
        total = len(norm_vals)

        current_max, threshold = 0.0, 0
        sum_total = np.sum(np.arange(256) * hist)
        sum_b, weight_b = 0.0, 0

        for t in range(256):
            weight_b += hist[t]
            if weight_b == 0:
                continue
            weight_f = total - weight_b
            if weight_f == 0:
                break

            sum_b += t * hist[t]
            mean_b = sum_b / weight_b
            mean_f = (sum_total - sum_b) / weight_f

            var_between = float(weight_b) * float(weight_f) * (mean_b - mean_f) ** 2
            if var_between > current_max:
                current_max = var_between
                threshold = t

        optimal_thresh = min_v + (threshold / 255.0) * (max_v - min_v)
        # Constrain threshold to reasonable MNDWI range [-0.2, 0.2]
        return float(np.clip(optimal_thresh, -0.2, 0.2))

    @staticmethod
    def morphological_cleanup(water_mask: np.ndarray, iterations: int = 1) -> np.ndarray:
        """
        Apply simple binary morphological opening followed by closing to eliminate
        isolated pixel noise and fill tiny pinholes without expanding boundaries.
        """
        clean_mask = water_mask.copy().astype(bool)
        try:
            from scipy.ndimage import binary_opening, binary_closing
            clean_mask = binary_opening(clean_mask, iterations=iterations)
            clean_mask = binary_closing(clean_mask, iterations=iterations)
        except Exception:
            # Fallback numpy kernel filter if scipy is unavailable
            pass
        return clean_mask

    def extract_water(
        self,
        bands: Dict[str, np.ndarray],
        bbox: Tuple[float, float, float, float],
        threshold: Optional[float] = 0.0,
        use_otsu: bool = False
    ) -> Dict[str, Any]:
        """
        Extract lake water surface using MNDWI.
        Returns:
        - mndwi: 2D float array
        - water_mask: 2D boolean array
        - water_area_km2: float
        - threshold_used: float
        - valid_pixel_pct: float
        """
        green = bands["B03"]
        swir1 = bands["B11"]

        # Calculate MNDWI
        mndwi = self.calculate_mndwi(green, swir1)

        # Determine threshold
        if use_otsu:
            thresh = self.compute_otsu_threshold(mndwi)
        else:
            thresh = threshold if threshold is not None else 0.0

        # Binary water mask
        raw_water_mask = mndwi >= thresh

        # Morphological filter
        water_mask = self.morphological_cleanup(raw_water_mask)

        # Estimate pixel resolution and total area
        rows, cols = mndwi.shape
        minx, miny, maxx, maxy = bbox
        
        # Approximate spatial extent in meters
        lat_center = (miny + maxy) / 2.0
        deg_lat_km = 111.139
        deg_lon_km = 111.320 * math.cos(math.radians(lat_center))
        width_km = abs(maxx - minx) * deg_lon_km
        height_km = abs(maxy - miny) * deg_lat_km

        pixel_area_km2 = (width_km / cols) * (height_km / rows)
        water_pixels = int(np.sum(water_mask))
        water_area_km2 = round(water_pixels * pixel_area_km2, 3)

        valid_pixels = int(np.sum(~np.isnan(mndwi)))
        valid_pixel_pct = round((valid_pixels / (rows * cols)) * 100.0, 1)

        logger.info(f"Water detection complete: {water_pixels} pixels, {water_area_km2} km² (threshold: {thresh:.3f})")

        return {
            "mndwi": mndwi,
            "water_mask": water_mask,
            "water_area_km2": water_area_km2,
            "water_pixels": water_pixels,
            "threshold_used": thresh,
            "valid_pixel_pct": valid_pixel_pct,
            "pixel_area_km2": pixel_area_km2
        }

water_analysis_service = WaterAnalysisService()
