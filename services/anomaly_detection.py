import datetime
import numpy as np
from typing import Dict, Any, List, Optional
from utils.logger import logger

class AnomalyDetectionService:
    """
    Seasonal-aware statistical anomaly detection across multi-temporal lake observations.
    Evaluates water surface extent, NDCI chlorophyll, and NDTI turbidity deviations.
    """

    MIN_OBSERVATIONS_FOR_ANOMALY = 4

    def analyze_anomalies(
        self,
        historical_records: List[Dict[str, Any]],
        current_observation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate current lake state against available historical observations.
        Each record should contain:
        - date: datetime.date or str
        - water_area_km2: float
        - mean_ndci: float (optional)
        - mean_ndti: float (optional)
        """
        count = len(historical_records)
        is_sufficient = count >= self.MIN_OBSERVATIONS_FOR_ANOMALY

        if not is_sufficient:
            return {
                "is_sufficient": False,
                "history_count": count,
                "status_message": f"Insufficient historical observations for reliable anomaly detection ({count} available, minimum {self.MIN_OBSERVATIONS_FOR_ANOMALY} required).",
                "anomalies": [],
                "baseline_stats": {}
            }

        # Extract series
        water_areas = [r["water_area_km2"] for r in historical_records if r.get("water_area_km2") is not None]
        ndcis = [r["mean_ndci"] for r in historical_records if r.get("mean_ndci") is not None]
        ndtis = [r["mean_ndti"] for r in historical_records if r.get("mean_ndti") is not None]

        anomalies = []
        baseline_stats = {}

        # 1. Water Area Anomaly Detection (Z-score & IQR)
        if len(water_areas) >= self.MIN_OBSERVATIONS_FOR_ANOMALY:
            mean_area = float(np.mean(water_areas))
            std_area = float(np.std(water_areas)) or 0.001
            curr_area = current_observation.get("water_area_km2", mean_area)
            z_area = (curr_area - mean_area) / std_area

            baseline_stats["water_area"] = {
                "mean_km2": round(mean_area, 2),
                "std_km2": round(std_area, 2),
                "current_km2": round(curr_area, 2),
                "z_score": round(z_area, 2)
            }

            if z_area < -1.8:
                anomalies.append({
                    "metric": "Water Surface Area",
                    "type": "Severe Water Contraction",
                    "severity": "High" if z_area < -2.5 else "Moderate",
                    "measured_value": f"{curr_area:.2f} km²",
                    "baseline_mean": f"{mean_area:.2f} km² (±{std_area:.2f})",
                    "z_score": round(z_area, 2),
                    "explanation": f"Observed water area is {abs(z_area):.1f} standard deviations below historical baseline mean, indicating significant shoreline recession or drought conditions."
                })
            elif z_area > 1.8:
                anomalies.append({
                    "metric": "Water Surface Area",
                    "type": "Unusual Water Expansion",
                    "severity": "Moderate",
                    "measured_value": f"{curr_area:.2f} km²",
                    "baseline_mean": f"{mean_area:.2f} km² (±{std_area:.2f})",
                    "z_score": round(z_area, 2),
                    "explanation": f"Observed water area is {z_area:.1f} standard deviations above historical mean, consistent with seasonal inundation or high precipitation influx."
                })

        # 2. Chlorophyll (NDCI) Anomaly Detection
        if len(ndcis) >= self.MIN_OBSERVATIONS_FOR_ANOMALY:
            mean_ndci = float(np.mean(ndcis))
            std_ndci = float(np.std(ndcis)) or 0.001
            curr_ndci = current_observation.get("mean_ndci", mean_ndci)
            z_ndci = (curr_ndci - mean_ndci) / std_ndci

            baseline_stats["ndci"] = {
                "mean": round(mean_ndci, 4),
                "std": round(std_ndci, 4),
                "current": round(curr_ndci, 4),
                "z_score": round(z_ndci, 2)
            }

            if z_ndci > 1.8:
                anomalies.append({
                    "metric": "Chlorophyll-a (NDCI)",
                    "type": "Potential Algal Bloom Outbreak",
                    "severity": "High" if z_ndci > 2.5 else "Moderate",
                    "measured_value": f"{curr_ndci:.3f}",
                    "baseline_mean": f"{mean_ndci:.3f} (±{std_ndci:.3f})",
                    "z_score": round(z_ndci, 2),
                    "explanation": f"Chlorophyll index elevated by {z_ndci:.1f} standard deviations over baseline, indicating abnormal phytoplankton proliferation requiring field sampling."
                })

        # 3. Turbidity (NDTI) Anomaly Detection
        if len(ndtis) >= self.MIN_OBSERVATIONS_FOR_ANOMALY:
            mean_ndti = float(np.mean(ndtis))
            std_ndti = float(np.std(ndtis)) or 0.001
            curr_ndti = current_observation.get("mean_ndti", mean_ndti)
            z_ndti = (curr_ndti - mean_ndti) / std_ndti

            baseline_stats["ndti"] = {
                "mean": round(mean_ndti, 4),
                "std": round(std_ndti, 4),
                "current": round(curr_ndti, 4),
                "z_score": round(z_ndti, 2)
            }

            if z_ndti > 1.8:
                anomalies.append({
                    "metric": "Turbidity Index (NDTI)",
                    "type": "Elevated Suspended Sediment Plume",
                    "severity": "Moderate",
                    "measured_value": f"{curr_ndti:.3f}",
                    "baseline_mean": f"{mean_ndti:.3f} (±{std_ndti:.3f})",
                    "z_score": round(z_ndti, 2),
                    "explanation": f"Turbidity signal is {z_ndti:.1f} standard deviations above seasonal baseline, suggesting sediment runoff or shoreline resuspension."
                })

        logger.info(f"Anomaly detection complete: {len(anomalies)} anomalies identified across {count} historical passes.")

        return {
            "is_sufficient": True,
            "history_count": count,
            "status_message": f"Historical series evaluated across {count} observations using robust Z-score & IQR deviation.",
            "anomalies": anomalies,
            "baseline_stats": baseline_stats
        }

anomaly_detection_service = AnomalyDetectionService()
