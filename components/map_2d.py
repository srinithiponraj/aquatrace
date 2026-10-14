import json
import folium
from folium import plugins
from typing import Dict, Any, List, Optional, Tuple
import streamlit as st
from streamlit_folium import st_folium

def render_folium_lake_map(
    lake_geojson: Dict[str, Any],
    centroid: Tuple[float, float],
    zoom_start: int = 12,
    hotspots: Optional[List[Dict[str, Any]]] = None,
    source_trace: Optional[Dict[str, Any]] = None,
    show_watershed: bool = True,
    enable_drawing: bool = False,
    key: str = "folium_main_map"
) -> Any:
    """
    Renders Folium 2D interactive map with clean light & satellite tiles,
    optional polygon drawing tools, boundary outline, hotspot markers, and catchment overlays.
    """
    lat, lon = centroid
    m = folium.Map(
        location=[lat, lon],
        zoom_start=zoom_start,
        tiles=None,
        control_scale=True
    )

    # Base layers: Clean Light (Default for Light Theme), Esri Satellite, & OpenStreetMap (Free, zero API key required)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Topo (Public / Free)",
        name="Clean Light Basemap",
        overlay=False,
        control=True
    ).add_to(m)

    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery (Public / Free)",
        name="🛰️ Satellite Imagery",
        overlay=False,
        control=True
    ).add_to(m)

    folium.TileLayer(
        tiles="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        name="🌐 OpenStreetMap",
        overlay=False,
        control=True
    ).add_to(m)

    # Optional Polygon Drawing Plugin (Requirement 7)
    if enable_drawing:
        plugins.Draw(
            export=True,
            filename="custom_boundary.geojson",
            position="topleft",
            draw_options={
                "polyline": False,
                "circlemarker": False,
                "circle": False,
                "marker": True,
                "polygon": {"allowIntersection": False, "showArea": True},
                "rectangle": True
            }
        ).add_to(m)

    # 1. Lake Boundary Polygon with glowing cyan outline
    if lake_geojson:
        folium.GeoJson(
            lake_geojson,
            name="Water Body Boundary",
            style_function=lambda feature: {
                "fillColor": "#0284c7",
                "fillOpacity": 0.30,
                "color": "#0284c7",
                "weight": 2.5,
                "dashArray": "2, 4"
            },
            tooltip="Monitored Water Boundary"
        ).add_to(m)

    # 2. Watershed Basin Catchment Overlay (from Source Trace)
    if source_trace and show_watershed and source_trace.get("watershed_geojson"):
        w_geo = source_trace["watershed_geojson"]
        if w_geo.get("coordinates"):
            folium.GeoJson(
                w_geo,
                name="Upstream Contributing Catchment",
                style_function=lambda feature: {
                    "fillColor": "#f59e0b",
                    "fillOpacity": 0.20,
                    "color": "#d97706",
                    "weight": 2.0,
                    "dashArray": "5, 5"
                },
                tooltip=f"Catchment ({source_trace.get('contributing_area_km2', 0)} km²) — Primary Pressure: {source_trace.get('primary_source_pressure')}"
            ).add_to(m)

    # 3. Flow Pathway Line (Shoreline entry to Hotspot)
    if source_trace and source_trace.get("pathway_geojson"):
        p_geo = source_trace["pathway_geojson"]
        coords = [[pt[1], pt[0]] for pt in p_geo.get("coordinates", [])]
        if len(coords) == 2:
            folium.PolyLine(
                locations=coords,
                color="#f43f5e",
                weight=3.5,
                dash_array="6, 6",
                tooltip="Inferred Runoff Inflow Pathway"
            ).add_to(m)

    # 4. Candidate Shoreline Entry Marker
    if source_trace:
        e_lat = source_trace.get("candidate_entry_lat")
        e_lon = source_trace.get("candidate_entry_lon")
        if e_lat and e_lon:
            folium.Marker(
                location=[e_lat, e_lon],
                popup=folium.Popup(
                    f"<b>Candidate Shoreline Inflow</b><br>Lat: {e_lat:.5f}, Lon: {e_lon:.5f}<br>Pressure: {source_trace.get('primary_source_pressure')}",
                    max_width=250
                ),
                icon=folium.Icon(color="orange", icon="tint", prefix="fa"),
                tooltip="Candidate Shoreline Inflow Zone"
            ).add_to(m)

    # 5. Hotspot Clusters
    if hotspots:
        for h in hotspots:
            h_lat = h["center_lat"]
            h_lon = h["center_lon"]
            sev = h.get("severity", "Moderate")
            
            color_map = {
                "Severe": "#ef4444",
                "High": "#f97316",
                "Moderate": "#0284c7",
                "Low": "#10b981"
            }
            m_color = color_map.get(sev, "#0284c7")

            folium.CircleMarker(
                location=[h_lat, h_lon],
                radius=7 + min(10, h.get("area_ha", 1.0) / 2.0),
                color="#ffffff",
                weight=2,
                fill=True,
                fill_color=m_color,
                fill_opacity=0.85,
                popup=folium.Popup(
                    f"""
                    <b>{h['hotspot_id']}</b><br>
                    Type: {h['indicator_type'].replace('_', ' ')}<br>
                    Severity: <b>{sev}</b> ({h.get('inspection_priority')} Priority)<br>
                    Affected Area: {h['area_ha']} ha ({h['pixel_count']} pixels)<br>
                    Max Indicator: {h['max_val']:.3f}
                    """,
                    max_width=260
                ),
                tooltip=f"{h['hotspot_id']} ({sev})"
            ).add_to(m)

    # Fullscreen & Layer Controls
    plugins.Fullscreen(position="topright").add_to(m)
    folium.LayerControl(position="bottomright").add_to(m)

    return st_folium(m, height=520, use_container_width=True, key=key)

def render_folium_observation_panel(
    lake_geojson: Dict[str, Any],
    centroid: Tuple[float, float],
    obs_title: str,
    obs_date: str,
    water_area_km2: float,
    cloud_cover: float,
    is_baseline: bool = True,
    water_mask: Optional[Any] = None,
    bbox: Optional[Tuple[float, float, float, float]] = None,
    real_rgb: Optional[Any] = None,
    scene_info: Optional[Dict[str, Any]] = None,
    zoom_start: int = 12,
    key: str = "obs_map",
    **kwargs
) -> Any:
    """
    Renders an individual observation panel map for side-by-side Before/After comparison
    featuring genuine Sentinel-2 true-color satellite imagery for the selected date,
    MNDWI multi-spectral water detection mask, and 100% free keyless basemaps (Esri & OSM).
    Never displays 'API key required' watermarks.
    """
    import numpy as np
    lat, lon = centroid
    m = folium.Map(
        location=[lat, lon],
        zoom_start=zoom_start,
        tiles=None,
        control_scale=True
    )

    # 1. High-Resolution Reference Satellite Basemap (Esri - Free, zero API key required)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery (Public / Free)",
        name="🛰️ Satellite Basemap",
        overlay=False,
        control=True
    ).add_to(m)

    # 2. Clean Topographical Basemap (Esri Topo - Free, zero API key required)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Topo (Public / Free)",
        name="🗺️ Clean Topo Basemap",
        overlay=False,
        control=True
    ).add_to(m)

    # 3. OpenStreetMap Community Standard (Free, zero API key required)
    folium.TileLayer(
        tiles="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        name="🌐 OpenStreetMap",
        overlay=False,
        control=True
    ).add_to(m)

    # 4. Genuine Sentinel-2 Satellite True-Color Image Overlay (if available for this pass)
    if real_rgb is not None and bbox is not None:
        try:
            # Map float reflectance array [0, 1] to uint8 RGB [0, 255]
            if isinstance(real_rgb, np.ndarray):
                if real_rgb.dtype != np.uint8:
                    rgb_uint8 = (np.clip(real_rgb, 0.0, 1.0) * 255).astype(np.uint8)
                else:
                    rgb_uint8 = real_rgb

                bounds = [[bbox[1], bbox[0]], [bbox[3], bbox[2]]]
                folium.raster_layers.ImageOverlay(
                    image=rgb_uint8,
                    bounds=bounds,
                    name=f"🛰️ Genuine Sentinel-2 Pass ({obs_date})",
                    opacity=0.95,
                    interactive=True
                ).add_to(m)
        except Exception:
            pass

    # 5. Observed Sentinel-2 MNDWI Water Mask Overlay (if computed)
    if water_mask is not None and bbox is not None:
        try:
            h, w = water_mask.shape
            rgba_mask = np.zeros((h, w, 4), dtype=np.uint8)
            # High-contrast electric cyan for comparison or deep royal blue for baseline
            color_rgb = [0, 229, 255] if not is_baseline else [2, 132, 199]
            rgba_mask[water_mask] = [*color_rgb, 190]
            
            # Bbox format: (min_lon, min_lat, max_lon, max_lat)
            bounds = [[bbox[1], bbox[0]], [bbox[3], bbox[2]]]
            folium.raster_layers.ImageOverlay(
                image=rgba_mask,
                bounds=bounds,
                name="💧 Observed Water Mask (MNDWI)",
                opacity=0.80,
                interactive=False
            ).add_to(m)
        except Exception:
            pass

    # 6. Lake Boundary Polygon outline
    fill_col = "#0284c7" if is_baseline else "#00e5ff"
    if lake_geojson:
        folium.GeoJson(
            lake_geojson,
            name="Water Body Boundary",
            style_function=lambda feature: {
                "fillColor": fill_col,
                "fillOpacity": 0.20,
                "color": "#38bdf8",
                "weight": 2.5
            },
            tooltip=f"{obs_title} (Observed Area: {water_area_km2:.2f} km²)"
        ).add_to(m)

    # 7. Center marker with metadata popup
    platform_name = scene_info.get("satellite", "Sentinel-2") if scene_info else "Sentinel-2"
    folium.CircleMarker(
        location=[lat, lon],
        radius=5,
        color="#ffffff",
        fill=True,
        fill_color="#00e5ff" if not is_baseline else "#0284c7",
        fill_opacity=1.0,
        popup=folium.Popup(
            f"""
            <b>{obs_title}</b><br>
            📅 Date: <b>{obs_date}</b><br>
            ☁️ Cloud Cover: <b>{cloud_cover:.1f}%</b><br>
            🛰️ Platform: <b>{platform_name}</b><br>
            💧 Water Surface: <b>{water_area_km2:.2f} km²</b>
            """,
            max_width=240
        ),
        tooltip=f"{obs_title} — {obs_date}"
    ).add_to(m)

    folium.LayerControl(position="topright").add_to(m)
    return st_folium(m, height=420, use_container_width=True, key=key)

