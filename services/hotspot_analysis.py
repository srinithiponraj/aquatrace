import json
import numpy as np
from typing import Dict, Any, List, Tuple
from sklearn.cluster import DBSCAN
from utils.logger import logger
from utils.geo_utils import pixel_to_latlon
from config import (
    DEFAULT_NDCI_BLOOM_THRESHOLD,
    DEFAULT_NDTI_TURBIDITY_THRESHOLD,
    DEFAULT_FAI_ALGAE_THRESHOLD,
    DEFAULT_HOTSPOT_MIN_PIXELS,
    DEFAULT_HOTSPOT_DBSCAN_EPS,
    DEFAULT_HOTSPOT_DBSCAN_MIN_SAMPLES
)

class HotspotAnalysisService:
    """
    Identifies spatial clusters of candidate water pollution signals
    using DBSCAN unsupervised spatial clustering.
    """

    def detect_hotspots(
        self,
        indices: Dict[str, np.ndarray],
        bbox: Tuple[float, float, float, float],
        pixel_area_km2: float,
        ndci_threshold: float = DEFAULT_NDCI_BLOOM_THRESHOLD,
        ndti_threshold: float = DEFAULT_NDTI_TURBIDITY_THRESHOLD,
        fai_threshold: float = DEFAULT_FAI_ALGAE_THRESHOLD,
        min_pixels: int = DEFAULT_HOTSPOT_MIN_PIXELS
    ) -> List[Dict[str, Any]]:
        """
        Run DBSCAN spatial clustering on candidate anomaly pixels for
        NDCI (Chlorophyll/Algal bloom), NDTI (Turbidity), and FAI (Floating Algae).
        """
        hotspots = []
        rows, cols = indices["water_mask"].shape
        ha_per_pixel = pixel_area_km2 * 100.0  # 1 km² = 100 hectares

        # 1. Algae / Chlorophyll signals (NDCI)
        ndci_water = indices["ndci_water"]
        algae_mask = (ndci_water >= ndci_threshold) & (~np.isnan(ndci_water))
        hs_algae = self._cluster_pixels(
            mask=algae_mask,
            value_grid=ndci_water,
            indicator_type="NDCI_ALGAE",
            label_prefix="ALG",
            bbox=bbox,
            grid_shape=(rows, cols),
            ha_per_pixel=ha_per_pixel,
            min_pixels=min_pixels,
            severity_rules={
                "Severe": 0.35,
                "High": 0.22,
                "Moderate": 0.14,
                "Low": 0.08
            }
        )
        hotspots.extend(hs_algae)

        # 2. Turbidity / Suspended sediment signals (NDTI)
        ndti_water = indices["ndti_water"]
        turbid_mask = (ndti_water >= ndti_threshold) & (~np.isnan(ndti_water))
        hs_turbid = self._cluster_pixels(
            mask=turbid_mask,
            value_grid=ndti_water,
            indicator_type="NDTI_TURBIDITY",
            label_prefix="TRB",
            bbox=bbox,
            grid_shape=(rows, cols),
            ha_per_pixel=ha_per_pixel,
            min_pixels=min_pixels,
            severity_rules={
                "Severe": 0.25,
                "High": 0.15,
                "Moderate": 0.08,
                "Low": 0.03
            }
        )
        hotspots.extend(hs_turbid)

        # 3. Floating Vegetation / Macrophytes (FAI)
        fai_water = indices["fai_water"]
        fai_mask = (fai_water >= fai_threshold) & (~np.isnan(fai_water))
        hs_fai = self._cluster_pixels(
            mask=fai_mask,
            value_grid=fai_water,
            indicator_type="FAI_FLOATING_VEG",
            label_prefix="FAI",
            bbox=bbox,
            grid_shape=(rows, cols),
            ha_per_pixel=ha_per_pixel,
            min_pixels=min_pixels,
            severity_rules={
                "Severe": 0.20,
                "High": 0.12,
                "Moderate": 0.06,
                "Low": 0.02
            }
        )
        hotspots.extend(hs_fai)

        # Sort hotspots by severity and affected area
        priority_rank = {"Immediate": 3, "Elevated": 2, "Routine": 1}
        hotspots.sort(key=lambda h: (priority_rank.get(h["inspection_priority"], 0), h["area_ha"]), reverse=True)

        logger.info(f"Hotspot clustering complete: identified {len(hotspots)} candidate spatial clusters.")
        return hotspots

    def _cluster_pixels(
        self,
        mask: np.ndarray,
        value_grid: np.ndarray,
        indicator_type: str,
        label_prefix: str,
        bbox: Tuple[float, float, float, float],
        grid_shape: Tuple[int, int],
        ha_per_pixel: float,
        min_pixels: int,
        severity_rules: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        rows, cols = grid_shape
        y_indices, x_indices = np.where(mask)
        if len(y_indices) < min_pixels:
            return []

        # Coordinate feature matrix for DBSCAN
        coords = np.column_stack((y_indices, x_indices))
        db = DBSCAN(eps=DEFAULT_HOTSPOT_DBSCAN_EPS, min_samples=DEFAULT_HOTSPOT_DBSCAN_MIN_SAMPLES).fit(coords)
        cluster_labels = db.labels_

        unique_labels = set(cluster_labels) - {-1}  # Exclude noise points
        clusters = []

        for idx, lbl in enumerate(unique_labels, start=1):
            mask_lbl = (cluster_labels == lbl)
            pts = coords[mask_lbl]
            px_count = len(pts)
            if px_count < min_pixels:
                continue

            vals = value_grid[pts[:, 0], pts[:, 1]]
            mean_val = float(np.mean(vals))
            max_val = float(np.max(vals))

            # Center pixel
            cy = float(np.mean(pts[:, 0]))
            cx = float(np.mean(pts[:, 1]))
            lat, lon = pixel_to_latlon(int(cy), int(cx), bbox, rows, cols)

            area_ha = round(px_count * ha_per_pixel, 2)

            # Determine severity
            if max_val >= severity_rules["Severe"]:
                severity = "Severe"
                priority = "Immediate"
            elif max_val >= severity_rules["High"]:
                severity = "High"
                priority = "Immediate" if area_ha > 5.0 else "Elevated"
            elif max_val >= severity_rules["Moderate"]:
                severity = "Moderate"
                priority = "Elevated"
            else:
                severity = "Low"
                priority = "Routine"

            # Bounding box polygon for hotspot geometry
            min_r, min_c = int(np.min(pts[:, 0])), int(np.min(pts[:, 1]))
            max_r, max_c = int(np.max(pts[:, 0])), int(np.max(pts[:, 1]))
            top_lat, left_lon = pixel_to_latlon(min_r, min_c, bbox, rows, cols)
            bot_lat, right_lon = pixel_to_latlon(max_r, max_c, bbox, rows, cols)

            geom_geojson = {
                "type": "Polygon",
                "coordinates": [[
                    [left_lon, top_lat],
                    [right_lon, top_lat],
                    [right_lon, bot_lat],
                    [left_lon, bot_lat],
                    [left_lon, top_lat]
                ]]
            }

            clusters.append({
                "hotspot_id": f"HS-{label_prefix}-{idx:02d}",
                "indicator_type": indicator_type,
                "center_lat": round(lat, 5),
                "center_lon": round(lon, 5),
                "center_pixel": (int(cy), int(cx)),
                "pixel_count": px_count,
                "area_ha": area_ha,
                "mean_val": round(mean_val, 4),
                "max_val": round(max_val, 4),
                "severity": severity,
                "inspection_priority": priority,
                "confidence_score": round(min(0.95, 0.65 + (px_count / 100.0) * 0.3), 2),
                "geometry": geom_geojson,
                "pixel_indices": pts.tolist()
            })

        return clusters

hotspot_analysis_service = HotspotAnalysisService()
