import numpy as np
from typing import Dict, Any, Optional
from utils.logger import logger

class HealthScoreService:
    """
    Computes an experimental, multi-criteria Lake Health Score (0 - 100)
    with transparent mathematical component weighting and data completeness tracking.
    """

    WEIGHTS = {
        "water_extent": 0.30,
        "chlorophyll_ndci": 0.25,
        "turbidity_ndti": 0.20,
        "floating_scum_fai": 0.15,
        "watershed_buffer": 0.10
    }

    def compute_health_score(
        self,
        water_metrics: Dict[str, Any],
        indices: Dict[str, Any],
        source_trace: Optional[Dict[str, Any]] = None,
        typical_area_km2: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate transparent Lake Health Score.
        Returns:
        - overall_score (0 - 100)
        - letter_grade (A, B, C, D, F)
        - component_scores (dict)
        - data_completeness_pct (float)
        - interpretation (str)
        """
        components = {}
        missing_components = []

        # 1. Water Extent Stability (Weight: 30%)
        # Evaluates stability relative to typical/baseline area
        current_area = water_metrics.get("water_area_km2", 0.0)
        ref_area = typical_area_km2 or current_area
        if ref_area > 0:
            area_ratio = current_area / ref_area
            # Perfect stability = 1.0; penalize loss < 0.85 or flood > 1.3
            if 0.90 <= area_ratio <= 1.10:
                s_extent = 100.0
            elif area_ratio < 0.90:
                s_extent = max(10.0, 100.0 - (0.90 - area_ratio) * 180.0)
            else:
                s_extent = max(40.0, 100.0 - (area_ratio - 1.10) * 120.0)
            components["water_extent"] = {
                "name": "Water Extent Stability",
                "score": round(float(s_extent), 1),
                "weight": self.WEIGHTS["water_extent"],
                "value_str": f"{current_area:.2f} km² (Ratio: {area_ratio:.2f})",
                "status": "Optimal" if s_extent >= 80 else ("Moderate" if s_extent >= 50 else "Severe Contraction")
            }
        else:
            missing_components.append("Water Extent Baseline")
            components["water_extent"] = {"name": "Water Extent Stability", "score": 70.0, "weight": 0.30, "value_str": "No Reference", "status": "Estimated"}

        # 2. Chlorophyll-a State (NDCI) (Weight: 25%)
        ndci_water = indices.get("ndci_water")
        if ndci_water is not None:
            valid_ndci = ndci_water[~np.isnan(ndci_water)]
            if len(valid_ndci) > 0:
                mean_ndci = float(np.mean(valid_ndci))
                # NDCI < 0.05 is pristine clear water (100 pts)
                # NDCI = 0.15 is moderate bloom (65 pts)
                # NDCI > 0.30 is severe toxic scum (< 30 pts)
                if mean_ndci <= 0.05:
                    s_ndci = 100.0
                elif mean_ndci >= 0.35:
                    s_ndci = 10.0
                else:
                    s_ndci = 100.0 - ((mean_ndci - 0.05) / 0.30) * 90.0
                
                components["chlorophyll_ndci"] = {
                    "name": "Chlorophyll-a / Algal State",
                    "score": round(float(s_ndci), 1),
                    "weight": self.WEIGHTS["chlorophyll_ndci"],
                    "value_str": f"Mean NDCI: {mean_ndci:.3f}",
                    "status": "Clear" if mean_ndci < 0.10 else ("Elevated Bloom" if mean_ndci < 0.22 else "Severe Bloom")
                }
            else:
                missing_components.append("Chlorophyll NDCI")
        else:
            missing_components.append("Chlorophyll NDCI")

        # 3. Water Clarity / Turbidity (NDTI) (Weight: 20%)
        ndti_water = indices.get("ndti_water")
        if ndti_water is not None:
            valid_ndti = ndti_water[~np.isnan(ndti_water)]
            if len(valid_ndti) > 0:
                mean_ndti = float(np.mean(valid_ndti))
                # NDTI < 0.0 is clear water (100 pts)
                # NDTI > 0.15 is heavy sediment / turbidity (< 30 pts)
                if mean_ndti <= 0.0:
                    s_ndti = 100.0
                elif mean_ndti >= 0.20:
                    s_ndti = 15.0
                else:
                    s_ndti = 100.0 - (mean_ndti / 0.20) * 85.0

                components["turbidity_ndti"] = {
                    "name": "Water Clarity & Turbidity",
                    "score": round(float(s_ndti), 1),
                    "weight": self.WEIGHTS["turbidity_ndti"],
                    "value_str": f"Mean NDTI: {mean_ndti:.3f}",
                    "status": "Clear" if mean_ndti < 0.04 else ("Moderate Turbidity" if mean_ndti < 0.12 else "Heavy Sediment")
                }
            else:
                missing_components.append("Turbidity NDTI")
        else:
            missing_components.append("Turbidity NDTI")

        # 4. Floating Scum & Macrophytes (FAI) (Weight: 15%)
        fai_water = indices.get("fai_water")
        if fai_water is not None:
            valid_fai = fai_water[~np.isnan(fai_water)]
            if len(valid_fai) > 0:
                mean_fai = float(np.mean(valid_fai))
                # FAI < 0.02 is clean (100 pts)
                # FAI > 0.10 indicates floating mat (25 pts)
                if mean_fai <= 0.02:
                    s_fai = 100.0
                elif mean_fai >= 0.12:
                    s_fai = 20.0
                else:
                    s_fai = 100.0 - ((mean_fai - 0.02) / 0.10) * 80.0

                components["floating_scum_fai"] = {
                    "name": "Surface Scum & Vegetation (FAI)",
                    "score": round(float(s_fai), 1),
                    "weight": self.WEIGHTS["floating_scum_fai"],
                    "value_str": f"Mean FAI: {mean_fai:.3f}",
                    "status": "Clean Surface" if mean_fai < 0.04 else "Surface Matting Detected"
                }
            else:
                missing_components.append("Floating Vegetation FAI")
        else:
            missing_components.append("Floating Vegetation FAI")

        # 5. Watershed Land Cover Buffer (Weight: 10%)
        if source_trace is not None:
            built_pct = source_trace.get("built_up_pct", 25.0)
            veg_pct = source_trace.get("vegetation_pct", 50.0)
            # High vegetative buffer (> 60%) and low urban built-up (< 15%) is favorable
            s_buffer = np.clip(veg_pct * 1.2 - built_pct * 0.8 + 20.0, 15.0, 100.0)
            components["watershed_buffer"] = {
                "name": "Catchment Buffer Integrity",
                "score": round(float(s_buffer), 1),
                "weight": self.WEIGHTS["watershed_buffer"],
                "value_str": f"{veg_pct:.0f}% Veg / {built_pct:.0f}% Built",
                "status": "Protected" if s_buffer >= 75 else ("Moderate Buffer" if s_buffer >= 50 else "High Urban Stress")
            }
        else:
            components["watershed_buffer"] = {
                "name": "Catchment Buffer Integrity",
                "score": 75.0,
                "weight": self.WEIGHTS["watershed_buffer"],
                "value_str": "Standard Regional Baseline",
                "status": "Estimated Baseline"
            }

        # Calculate final weighted score
        total_weight = sum(c["weight"] for c in components.values())
        overall_score = sum(c["score"] * c["weight"] for c in components.values()) / (total_weight or 1.0)
        overall_score = round(float(np.clip(overall_score, 0.0, 100.0)), 1)

        # Assign Grade
        if overall_score >= 85.0:
            grade = "A"
            interp = "Excellent Ecological Health: High water clarity, stable surface extent, and minimal chlorophyll signals."
        elif overall_score >= 70.0:
            grade = "B"
            interp = "Good Ecological State: Minor localized turbidity or seasonal nutrient signals observed."
        elif overall_score >= 50.0:
            grade = "C"
            interp = "Moderate Concern: Elevated algal bloom activity or sediment influx detected in multiple lake sectors."
        elif overall_score >= 35.0:
            grade = "D"
            interp = "Poor Water Condition: Substantial chlorophyll anomalies, persistent turbidity, or significant water surface recession."
        else:
            grade = "F"
            interp = "Critical Ecological Emergency: Severe hypertrophic blooms, extensive floating scum, or critical desiccation."

        data_completeness = round(((5 - len(missing_components)) / 5.0) * 100.0, 1)

        logger.info(f"Lake Health Score calculated: {overall_score} (Grade {grade}, Completeness: {data_completeness}%)")

        return {
            "overall_score": overall_score,
            "letter_grade": grade,
            "components": components,
            "data_completeness_pct": data_completeness,
            "missing_components": missing_components,
            "interpretation": interp,
            "disclaimer": "Experimental decision-support score based on optical satellite proxies. Not a certified laboratory chemical or microbiological assessment."
        }

health_score_service = HealthScoreService()
