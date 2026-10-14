import numpy as np
from typing import Dict, Any, Optional
from utils.logger import logger

class ChangeDetectionService:
    """
    Computes before-and-after spatial and statistical water change metrics:
    - Stable water
    - Water loss (drying / recession)
    - Water gain (flooding / expansion)
    - Stable dry land
    - Invalid / unobserved pixels
    """

    # Categorical classification codes
    CLASS_STABLE_LAND = 0
    CLASS_STABLE_WATER = 1
    CLASS_WATER_LOSS = 2
    CLASS_WATER_GAIN = 3
    CLASS_INVALID = 4

    def analyze_change(
        self,
        baseline_water_mask: np.ndarray,
        comparison_water_mask: np.ndarray,
        pixel_area_km2: float,
        baseline_cloud_mask: Optional[np.ndarray] = None,
        comparison_cloud_mask: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """
        Compare two observations and compute detailed spatial change metrics.
        """
        assert baseline_water_mask.shape == comparison_water_mask.shape, "Mask shapes must match"
        rows, cols = baseline_water_mask.shape
        total_pixels = rows * cols

        # Invalid mask (clouds or missing data)
        invalid_mask = np.zeros((rows, cols), dtype=bool)
        if baseline_cloud_mask is not None:
            invalid_mask |= baseline_cloud_mask
        if comparison_cloud_mask is not None:
            invalid_mask |= comparison_cloud_mask

        # Valid observation mask
        valid_mask = ~invalid_mask

        b_water = baseline_water_mask & valid_mask
        c_water = comparison_water_mask & valid_mask

        stable_water = b_water & c_water
        water_loss = b_water & (~c_water)
        water_gain = (~b_water) & c_water
        stable_land = (~b_water) & (~c_water) & valid_mask

        # Construct change map
        change_map = np.full((rows, cols), self.CLASS_STABLE_LAND, dtype=np.uint8)
        change_map[stable_water] = self.CLASS_STABLE_WATER
        change_map[water_loss] = self.CLASS_WATER_LOSS
        change_map[water_gain] = self.CLASS_WATER_GAIN
        change_map[invalid_mask] = self.CLASS_INVALID

        # Calculate areas in km²
        stable_water_km2 = round(float(np.sum(stable_water)) * pixel_area_km2, 3)
        water_loss_km2 = round(float(np.sum(water_loss)) * pixel_area_km2, 3)
        water_gain_km2 = round(float(np.sum(water_gain)) * pixel_area_km2, 3)
        invalid_area_km2 = round(float(np.sum(invalid_mask)) * pixel_area_km2, 3)
        baseline_total_km2 = round(float(np.sum(b_water)) * pixel_area_km2, 3)
        comparison_total_km2 = round(float(np.sum(c_water)) * pixel_area_km2, 3)

        net_change_km2 = round(comparison_total_km2 - baseline_total_km2, 3)
        if baseline_total_km2 > 0:
            pct_change = round((net_change_km2 / baseline_total_km2) * 100.0, 2)
        else:
            pct_change = 0.0

        valid_pct = round(float(np.sum(valid_mask)) / total_pixels * 100.0, 1)

        # Quality warning assessment
        warnings = []
        if valid_pct < 85.0:
            warnings.append(f"High cloud or no-data coverage ({100.0 - valid_pct:.1f}% unobserved). Comparison uncertainty elevated.")
        if abs(pct_change) > 40.0:
            warnings.append(f"Significant water area divergence ({pct_change:+.1f}%). Verify potential seasonal or boundary discrepancy.")

        logger.info(f"Change detection: Baseline={baseline_total_km2} km², Comp={comparison_total_km2} km², Net={net_change_km2:+} km² ({pct_change:+}%)")

        return {
            "change_map": change_map,
            "baseline_area_km2": baseline_total_km2,
            "comparison_area_km2": comparison_total_km2,
            "net_change_km2": net_change_km2,
            "pct_change": pct_change,
            "stable_water_km2": stable_water_km2,
            "water_loss_km2": water_loss_km2,
            "water_gain_km2": water_gain_km2,
            "invalid_area_km2": invalid_area_km2,
            "valid_observation_pct": valid_pct,
            "warnings": warnings,
            "counts": {
                "stable_water_pixels": int(np.sum(stable_water)),
                "water_loss_pixels": int(np.sum(water_loss)),
                "water_gain_pixels": int(np.sum(water_gain)),
                "stable_land_pixels": int(np.sum(stable_land)),
                "invalid_pixels": int(np.sum(invalid_mask))
            }
        }

change_detection_service = ChangeDetectionService()
