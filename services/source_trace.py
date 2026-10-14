import math
from collections import deque
import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from utils.logger import logger
from utils.geo_utils import pixel_to_latlon, latlon_to_pixel

class SourceTraceService:
    """
    AquaTrace Signature Feature — Pollution Source Trace
    Connects detected lake hotspots to upstream terrain, flow pathways,
    and land-cover pressure characteristics.
    """

    # D8 Direction offsets: (d_row, d_col, distance)
    # 0: E, 1: SE, 2: S, 3: SW, 4: W, 5: NW, 6: N, 7: NE
    D8_OFFSETS = [
        (0, 1, 1.0),            # E
        (1, 1, 1.41421356),     # SE
        (1, 0, 1.0),            # S
        (1, -1, 1.41421356),    # SW
        (0, -1, 1.0),           # W
        (-1, -1, 1.41421356),   # NW
        (-1, 0, 1.0),           # N
        (-1, 1, 1.41421356)     # NE
    ]

    def trace_hotspot_source(
        self,
        hotspot: Dict[str, Any],
        bands: Dict[str, np.ndarray],
        indices: Dict[str, Any],
        bbox: Tuple[float, float, float, float],
        pixel_area_km2: float
    ) -> Dict[str, Any]:
        """
        Execute full end-to-end source tracing for a candidate hotspot:
        1. Identify nearest shoreline entry point
        2. Process DEM elevation & compute D8 hydrological flow routing
        3. Delineate upstream contributing watershed
        4. Analyze land cover proxies (NDBI, NDVI, BSI) inside catchment
        5. Formulate transparent source-pressure hypotheses
        6. Generate prioritized field inspection recommendations
        """
        rows, cols = indices["water_mask"].shape
        dem = bands.get("DEM")
        water_mask = indices["water_mask"]

        # Step A: Locate hotspot center pixel
        h_lat, h_lon = hotspot["center_lat"], hotspot["center_lon"]
        hs_row, hs_col = latlon_to_pixel(h_lat, h_lon, bbox, rows, cols)

        # Step B: Identify Candidate Shoreline Entry Point
        entry_row, entry_col = self._find_nearest_shoreline(hs_row, hs_col, water_mask)
        entry_lat, entry_lon = pixel_to_latlon(entry_row, entry_col, bbox, rows, cols)

        # Step C: Hydrological Catchment Delineation
        if dem is not None and not np.all(dem == 0):
            try:
                flow_dir = self._calculate_d8_flow_direction(dem)
                catchment_mask = self._delineate_upstream_basin(flow_dir, entry_row, entry_col, water_mask)
                terrain_method = "Copernicus DEM 30m (D8 Flow Routing)"
                is_fallback = False
            except Exception as e:
                logger.warning(f"D8 catchment delineation failed: {e}. Using buffer fallback.")
                catchment_mask = self._shoreline_buffer_fallback(entry_row, entry_col, (rows, cols), radius_pixels=18)
                terrain_method = "Shoreline Buffer Proximity Fallback (DEM Routing Unavailable)"
                is_fallback = True
        else:
            catchment_mask = self._shoreline_buffer_fallback(entry_row, entry_col, (rows, cols), radius_pixels=18)
            terrain_method = "Shoreline Buffer Proximity Fallback (DEM Unavailable)"
            is_fallback = True

        # Catchment area
        catchment_pixels = int(np.sum(catchment_mask))
        catchment_area_km2 = round(catchment_pixels * pixel_area_km2, 2)

        # Step D: Land Cover & Pressure Analysis within Catchment
        land_analysis = self._analyze_catchment_land_cover(
            catchment_mask=catchment_mask,
            indices=indices
        )

        # Step E: Source Pressure Assessment
        pressure_summary, recommendations = self._formulate_source_hypothesis(
            hotspot=hotspot,
            land_analysis=land_analysis,
            entry_coords=(entry_lat, entry_lon),
            is_fallback=is_fallback
        )

        # Step F: Watershed Boundary Polygon GeoJSON
        watershed_geojson = self._create_catchment_geojson(catchment_mask, bbox, (rows, cols))

        # Flow pathway line connecting entry to hotspot
        pathway_geojson = {
            "type": "LineString",
            "coordinates": [
                [h_lon, h_lat],
                [entry_lon, entry_lat]
            ]
        }

        return {
            "hotspot_id": hotspot["hotspot_id"],
            "candidate_entry_lat": round(entry_lat, 5),
            "candidate_entry_lon": round(entry_lon, 5),
            "entry_pixel": (entry_row, entry_col),
            "contributing_area_km2": catchment_area_km2,
            "catchment_pixels": catchment_pixels,
            "built_up_pct": land_analysis["built_up_pct"],
            "agriculture_pct": land_analysis["agriculture_pct"],
            "bare_soil_pct": land_analysis["bare_soil_pct"],
            "vegetation_pct": land_analysis["vegetation_pct"],
            "primary_source_pressure": pressure_summary["primary_pressure"],
            "secondary_source_pressure": pressure_summary["secondary_pressure"],
            "pressure_rationale": pressure_summary["rationale"],
            "terrain_method": terrain_method,
            "is_fallback": is_fallback,
            "inspection_recommendations": recommendations,
            "catchment_mask": catchment_mask,
            "watershed_geojson": watershed_geojson,
            "pathway_geojson": pathway_geojson,
            "limitations": [
                "Catchment derived from 30m DEM; small culverts, stormwater pipes, and municipal sewers are not resolved.",
                "Spectral land-cover proxies (NDBI/NDVI/BSI) provide surface pressure indications, not certified discharge permits.",
                "In situ sampling required to verify presence of specific chemical contaminants or biological pathogens."
            ]
        }

    def _find_nearest_shoreline(self, hs_row: int, hs_col: int, water_mask: np.ndarray) -> Tuple[int, int]:
        """Find the nearest land pixel directly bordering the lake (shoreline entry point)."""
        rows, cols = water_mask.shape
        # Land pixels that have at least one water neighbor
        land_mask = ~water_mask
        
        # Simple distance search from hotspot center outwards
        best_dist = float("inf")
        best_pt = (hs_row, hs_col)

        # Check neighborhood within 40 pixels
        r_min, r_max = max(0, hs_row - 40), min(rows, hs_row + 41)
        c_min, c_max = max(0, hs_col - 40), min(cols, hs_col + 41)

        for r in range(r_min, r_max):
            for c in range(c_min, c_max):
                if land_mask[r, c]:
                    # Check if borders water
                    has_water_adj = False
                    for dr, dc, _ in self.D8_OFFSETS:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < rows and 0 <= nc < cols and water_mask[nr, nc]:
                            has_water_adj = True
                            break
                    if has_water_adj:
                        d2 = (r - hs_row) ** 2 + (c - hs_col) ** 2
                        if d2 < best_dist:
                            best_dist = d2
                            best_pt = (r, c)

        return best_pt

    def _calculate_d8_flow_direction(self, elevation: np.ndarray) -> np.ndarray:
        """
        Compute D8 flow direction for each cell to its steepest downhill neighbor.
        Values 0-7 correspond to D8_OFFSETS index; 255 represents pit / sink.
        """
        rows, cols = elevation.shape
        flow_dir = np.full((rows, cols), 255, dtype=np.uint8)

        # Depressions / pit smoothing
        smooth_elev = elevation.copy()

        for r in range(1, rows - 1):
            for c in range(1, cols - 1):
                cur_z = smooth_elev[r, c]
                max_slope = 0.0
                best_dir = 255

                for d_idx, (dr, dc, dist) in enumerate(self.D8_OFFSETS):
                    nr, nc = r + dr, c + dc
                    drop = cur_z - smooth_elev[nr, nc]
                    if drop > 0:
                        slope = drop / dist
                        if slope > max_slope:
                            max_slope = slope
                            best_dir = d_idx

                flow_dir[r, c] = best_dir

        return flow_dir

    def _delineate_upstream_basin(
        self,
        flow_dir: np.ndarray,
        outlet_row: int,
        outlet_col: int,
        water_mask: np.ndarray
    ) -> np.ndarray:
        """
        Delineate all upstream cells draining into the outlet cell using reverse flow traversal.
        """
        rows, cols = flow_dir.shape
        basin = np.zeros((rows, cols), dtype=bool)

        # Seed queue with outlet and immediate terrestrial buffer
        queue = deque([(outlet_row, outlet_col)])
        basin[outlet_row, outlet_col] = True

        visited = set()
        visited.add((outlet_row, outlet_col))

        max_basin_cells = int(rows * cols * 0.25)  # Cap realistic catchment at 25% of scene

        while queue and len(visited) < max_basin_cells:
            curr_r, curr_c = queue.popleft()

            # Inspect all 8 neighbors: does neighbor flow into curr_r, curr_c?
            for d_idx, (dr, dc, _) in enumerate(self.D8_OFFSETS):
                nr, nc = curr_r - dr, curr_c - dc  # Opposite direction
                if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in visited:
                    # Don't extend basin into open lake water
                    if water_mask[nr, nc]:
                        continue
                    
                    # If neighbor's flow direction points towards curr_r, curr_c
                    neighbor_dir = flow_dir[nr, nc]
                    if neighbor_dir == d_idx:
                        basin[nr, nc] = True
                        visited.add((nr, nc))
                        queue.append((nr, nc))

        # If catchment is too tiny (< 15 cells due to DEM flatness), expand gentle uphill cone
        if np.sum(basin) < 20:
            for dr in range(-12, 13):
                for dc in range(-12, 13):
                    r, c = outlet_row + dr, outlet_col + dc
                    if 0 <= r < rows and 0 <= c < cols and not water_mask[r, c]:
                        if dr**2 + dc**2 <= 144:
                            basin[r, c] = True

        return basin

    def _shoreline_buffer_fallback(self, r: int, c: int, shape: Tuple[int, int], radius_pixels: int = 15) -> np.ndarray:
        """Proximity buffer fallback when DEM flow routing is unavailable."""
        rows, cols = shape
        mask = np.zeros((rows, cols), dtype=bool)
        for dr in range(-radius_pixels, radius_pixels + 1):
            for dc in range(-radius_pixels, radius_pixels + 1):
                if dr**2 + dc**2 <= radius_pixels**2:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        mask[nr, nc] = True
        return mask

    def _analyze_catchment_land_cover(
        self,
        catchment_mask: np.ndarray,
        indices: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Analyze land-cover composition within the upstream contributing area:
        - Built-up (NDBI > 0.05)
        - Agricultural (NDVI > 0.40 and not deep forest)
        - Bare Soil (BSI > 0.08)
        - Natural Vegetation (NDVI > 0.25)
        """
        ndbi = indices["ndbi"]
        ndvi = indices["ndvi"]
        bsi = indices["bsi"]

        c_ndbi = ndbi[catchment_mask]
        c_ndvi = ndvi[catchment_mask]
        c_bsi = bsi[catchment_mask]

        total = len(c_ndbi)
        if total == 0:
            return {"built_up_pct": 25.0, "agriculture_pct": 25.0, "bare_soil_pct": 25.0, "vegetation_pct": 25.0}

        built_pixels = np.sum(c_ndbi > 0.04)
        agri_pixels = np.sum((c_ndvi > 0.38) & (c_ndbi <= 0.04))
        soil_pixels = np.sum((c_bsi > 0.05) & (c_ndbi <= 0.04))
        veg_pixels = np.sum((c_ndvi > 0.20) & (c_ndvi <= 0.38))

        # Normalize to 100%
        sum_p = built_pixels + agri_pixels + soil_pixels + veg_pixels
        if sum_p == 0:
            sum_p = 1

        return {
            "built_up_pct": round(float(built_pixels) / sum_p * 100.0, 1),
            "agriculture_pct": round(float(agri_pixels) / sum_p * 100.0, 1),
            "bare_soil_pct": round(float(soil_pixels) / sum_p * 100.0, 1),
            "vegetation_pct": round(float(veg_pixels) / sum_p * 100.0, 1)
        }

    def _formulate_source_hypothesis(
        self,
        hotspot: Dict[str, Any],
        land_analysis: Dict[str, float],
        entry_coords: Tuple[float, float],
        is_fallback: bool
    ) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
        """
        Synthesize transparent, rule-based source pressure hypotheses
        and targeted field inspection actions.
        """
        built = land_analysis["built_up_pct"]
        agri = land_analysis["agriculture_pct"]
        soil = land_analysis["bare_soil_pct"]
        veg = land_analysis["vegetation_pct"]
        ind_type = hotspot["indicator_type"]

        # Determine dominant land cover pressure
        pressures = [
            ("Urban / Impervious Runoff", built, "High built-up density (NDBI proxy) upstream. Investigate municipal storm outfalls and urban surface drainage."),
            ("Agricultural Nutrient Influx", agri, "Extensive cultivated / high-biomass coverage upstream. Investigate fertilizer runoff, irrigation return flows, or livestock proximity."),
            ("Sediment Erosion / Disturbance", soil, "Elevated bare soil (BSI proxy) in drainage path. Investigate construction earthworks, riverbank erosion, or unpaved tracks."),
            ("Vegetated Buffer Zone", veg, "Riparian vegetation dominant. Buffer zone may moderate runoff; check for localized point discharges or tributary bypass.")
        ]
        pressures.sort(key=lambda x: x[1], reverse=True)
        primary_pressure, primary_val, primary_rationale = pressures[0]
        secondary_pressure, _, _ = pressures[1]

        # Specific indicator alignment
        if ind_type == "NDCI_ALGAE" and agri > 25.0:
            primary_rationale += " Elevated NDCI chlorophyll bloom signal strongly aligns with suspected nitrogen/phosphorus enrichment."
        elif ind_type == "NDTI_TURBIDITY" and soil > 20.0:
            primary_rationale += " High NDTI turbidity signal correlates with upstream exposed bare soil and sediment transport."

        # Field recommendations
        recs = [
            {
                "step": 1,
                "title": "Shoreline Outfall Inspection",
                "location": f"Lat: {entry_coords[0]:.5f}, Lon: {entry_coords[1]:.5f}",
                "action": "Inspect the candidate shoreline entry zone for physical discharge pipes, culverts, or natural creek inlets.",
                "priority": "High"
            },
            {
                "step": 2,
                "title": "Water Quality Grab Sampling",
                "location": f"At shoreline entry point and hotspot core (Lat: {hotspot['center_lat']:.5f}, Lon: {hotspot['center_lon']:.5f})",
                "action": "Collect samples for laboratory analysis: Total Nitrogen (TN), Total Phosphorus (TP), Chlorophyll-a, and Turbidity (NTU).",
                "priority": "High"
            },
            {
                "step": 3,
                "title": "Upstream Drainage Corridor Survey",
                "location": f"Upstream contributing basin ({primary_pressure})",
                "action": f"Trace drainage channels upstream into the {primary_pressure.lower()} sector to locate direct point discharges or non-point overland flow.",
                "priority": "Medium"
            }
        ]

        summary = {
            "primary_pressure": primary_pressure,
            "secondary_pressure": secondary_pressure,
            "rationale": primary_rationale
        }

        return summary, recs

    def _create_catchment_geojson(
        self,
        catchment_mask: np.ndarray,
        bbox: Tuple[float, float, float, float],
        shape: Tuple[int, int]
    ) -> Dict[str, Any]:
        """Convert binary catchment grid into a GeoJSON bounding polygon."""
        rows, cols = shape
        r_indices, c_indices = np.where(catchment_mask)
        if len(r_indices) == 0:
            return {"type": "Polygon", "coordinates": []}

        min_r, max_r = int(np.min(r_indices)), int(np.max(r_indices))
        min_c, max_c = int(np.min(c_indices)), int(np.max(c_indices))

        top_lat, left_lon = pixel_to_latlon(min_r, min_c, bbox, rows, cols)
        bot_lat, right_lon = pixel_to_latlon(max_r, max_c, bbox, rows, cols)

        return {
            "type": "Polygon",
            "coordinates": [[
                [left_lon, top_lat],
                [right_lon, top_lat],
                [right_lon, bot_lat],
                [left_lon, bot_lat],
                [left_lon, top_lat]
            ]]
        }

source_trace_service = SourceTraceService()
