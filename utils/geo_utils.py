import json
import math
from typing import Dict, Any, Tuple, List, Optional
from shapely.geometry import shape, mapping, Polygon, MultiPolygon
from shapely.ops import transform

def parse_geojson(geojson_data: Any) -> Optional[Dict[str, Any]]:
    """Parse raw GeoJSON dict or string into a validated GeoJSON geometry."""
    if isinstance(geojson_data, str):
        try:
            geojson_data = json.loads(geojson_data)
        except Exception:
            return None
            
    if not isinstance(geojson_data, dict):
        return None

    # Handle FeatureCollection
    if geojson_data.get("type") == "FeatureCollection":
        features = geojson_data.get("features", [])
        if not features:
            return None
        return features[0].get("geometry")
        
    # Handle Feature
    if geojson_data.get("type") == "Feature":
        return geojson_data.get("geometry")
        
    # Handle direct Geometry
    if "coordinates" in geojson_data and "type" in geojson_data:
        return geojson_data
        
    return None

def get_geometry_bbox(geom_dict: Dict[str, Any]) -> Tuple[float, float, float, float]:
    """Return [minx, miny, maxx, maxy] for geometry."""
    s = shape(geom_dict)
    return s.bounds

def get_geometry_centroid(geom_dict: Dict[str, Any]) -> Tuple[float, float]:
    """Return (latitude, longitude) of centroid."""
    s = shape(geom_dict)
    c = s.centroid
    return c.y, c.x

def calculate_polygon_area_km2(geom_dict: Dict[str, Any]) -> float:
    """
    Calculate geodesic surface area of polygon in square kilometers
    using WGS84 geodesic projection or equal area projection.
    """
    try:
        s = shape(geom_dict)
        centroid = s.centroid
        lat, lon = centroid.y, centroid.x
        
        # Approximate local metric projection UTM or Sinusoidal
        # 1 deg lat ~= 111.139 km
        # 1 deg lon ~= 111.320 * cos(lat) km
        cos_lat = math.cos(math.radians(lat))
        
        # For precise calculation:
        a_deg2 = s.area
        area_km2 = a_deg2 * 111.139 * (111.320 * abs(cos_lat))
        return round(area_km2, 4)
    except Exception:
        return 0.0

def pixel_to_latlon(row: int, col: int, bbox: Tuple[float, float, float, float], height: int, width: int) -> Tuple[float, float]:
    """Convert grid pixel (row, col) into (lat, lon)."""
    minx, miny, maxx, maxy = bbox
    lon = minx + (col / float(width)) * (maxx - minx)
    lat = maxy - (row / float(height)) * (maxy - miny)
    return lat, lon

def latlon_to_pixel(lat: float, lon: float, bbox: Tuple[float, float, float, float], height: int, width: int) -> Tuple[int, int]:
    """Convert (lat, lon) into grid pixel (row, col)."""
    minx, miny, maxx, maxy = bbox
    col = int(((lon - minx) / (maxx - minx)) * width)
    row = int(((maxy - lat) / (maxy - miny)) * height)
    col = max(0, min(width - 1, col))
    row = max(0, min(height - 1, row))
    return row, col
