import json
import streamlit as st
import streamlit.components.v1 as components
from typing import Dict, Any, List, Optional, Tuple

def render_maplibre_3d(
    lake_geojson: Dict[str, Any],
    centroid: Tuple[float, float],
    lake_name: str,
    hotspots: Optional[List[Dict[str, Any]]] = None,
    source_trace: Optional[Dict[str, Any]] = None,
    water_type: str = "Lake",
    height: int = 580
):
    """
    Renders MapLibre GL JS 3D geospatial component with genuine 3D terrain mesh (DEM),
    pitch/rotation, satellite and light basemaps, lake boundary glow, and hotspot markers.
    """
    lat, lon = centroid
    lake_json_str = json.dumps(lake_geojson) if lake_geojson else "{}"
    hotspots_json_str = json.dumps(hotspots or [])
    watershed_json_str = json.dumps(source_trace.get("watershed_geojson") if source_trace else {})
    pathway_json_str = json.dumps(source_trace.get("pathway_geojson") if source_trace else {})

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8" />
        <title>AquaTrace 3D Terrain</title>
        <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no" />
        <link href="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css" rel="stylesheet" />
        <script src="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js"></script>
        <style>
            body {{ margin: 0; padding: 0; background: #f0f7ff; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
            #map {{ position: absolute; top: 0; bottom: 0; width: 100%; height: 100%; border-radius: 12px; border: 1.5px solid #bae6fd; }}
            
            .map-controls {{
                position: absolute;
                top: 14px;
                left: 14px;
                z-index: 10;
                background: rgba(11, 19, 41, 0.88);
                backdrop-filter: blur(12px);
                border: 1px solid #1e293b;
                border-radius: 10px;
                padding: 8px 12px;
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
            }}

            .ctrl-btn {{
                background: #0f172a;
                color: #38bdf8;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 700;
                cursor: pointer;
                transition: all 0.2s ease;
                box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
            }}

            .ctrl-btn:hover {{
                background: #0284c7;
                color: #ffffff;
                border-color: #38bdf8;
                box-shadow: 0 0 12px rgba(56, 189, 248, 0.5);
            }}

            .ctrl-btn.active {{
                background: linear-gradient(135deg, #0284c7, #0891b2);
                color: #ffffff;
                border-color: #00e5ff;
                box-shadow: 0 0 12px rgba(0, 229, 255, 0.4);
            }}

            .map-legend {{
                position: absolute;
                bottom: 24px;
                right: 14px;
                z-index: 10;
                background: rgba(11, 19, 41, 0.90);
                backdrop-filter: blur(12px);
                border: 1.5px solid #1e293b;
                border-radius: 10px;
                padding: 10px 14px;
                font-size: 11px;
                color: #f8fafc;
                line-height: 1.6;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
            }}

            .legend-item {{
                display: flex;
                align-items: center;
                gap: 8px;
                font-weight: 600;
                color: #cbd5e1;
            }}

            .legend-dot {{
                width: 10px;
                height: 10px;
                border-radius: 50%;
            }}

            .pulse-marker {{
                width: 18px;
                height: 18px;
                background: rgba(244, 63, 94, 0.9);
                border: 2px solid #ffffff;
                border-radius: 50%;
                cursor: pointer;
                box-shadow: 0 0 14px #f43f5e;
                animation: pulse 1.8s infinite;
            }}

            @keyframes pulse {{
                0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(244, 63, 94, 0.8); }}
                70% {{ transform: scale(1.15); box-shadow: 0 0 0 12px rgba(244, 63, 94, 0); }}
                100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(244, 63, 94, 0); }}
            }}

            #terrain-status {{
                position: absolute;
                bottom: 24px;
                left: 14px;
                z-index: 10;
                background: rgba(11, 19, 41, 0.90);
                backdrop-filter: blur(8px);
                border: 1px solid #1e293b;
                padding: 4px 10px;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 700;
                color: #38bdf8;
                box-shadow: 0 4px 14px rgba(0, 0, 0, 0.4);
            }}
        </style>
    </head>
    <body>
        <div id="map"></div>

        <div class="map-controls">
            <button class="ctrl-btn active" id="btn-3d" onclick="toggle3DPerspective()">📐 3D Terrain View</button>
            <button class="ctrl-btn" id="btn-exag" onclick="toggleExaggeration()">⛰️ Exaggeration: 1.8x</button>
            <button class="ctrl-btn" id="btn-sat" onclick="toggleSatelliteBasemap()">🛰️ Toggle Satellite</button>
            <button class="ctrl-btn" onclick="rotateCamera()">🔄 Rotate 360°</button>
            <button class="ctrl-btn" onclick="resetCamera()">🎯 Center Water Body</button>
        </div>

        <div id="terrain-status">⛰️ 3D Elevation Mesh: Active (Terrarium DEM)</div>

        <div class="map-legend">
            <div style="font-weight: 800; color: #0284c7; margin-bottom: 4px;">AquaTrace 3D Layers</div>
            <div class="legend-item"><span class="legend-dot" style="background: #0284c7;"></span> {water_type} Boundary</div>
            <div class="legend-item"><span class="legend-dot" style="background: #f43f5e;"></span> Severe/High Hotspots</div>
            <div class="legend-item"><span class="legend-dot" style="background: #f59e0b;"></span> Upstream Catchment Basin</div>
            <div class="legend-item"><span class="legend-dot" style="background: #a855f7;"></span> Runoff Inflow Pathway</div>
        </div>

        <script>
            const lakeLat = {lat};
            const lakeLon = {lon};
            const lakeName = "{lake_name}";
            const lakeGeom = {lake_json_str};
            const hotspotsData = {hotspots_json_str};
            const watershedGeom = {watershed_json_str};
            const pathwayGeom = {pathway_json_str};

            let is3D = true;
            let isSatellite = true;
            let rotating = false;
            let currentExag = 1.8;

            const map = new maplibregl.Map({{
                container: 'map',
                style: {{
                    version: 8,
                    sources: {{
                        'esri-sat': {{
                            type: 'raster',
                            tiles: [
                                'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}'
                            ],
                            tileSize: 256,
                            attribution: 'Esri World Imagery'
                        }},
                        'topo-light': {{
                            type: 'raster',
                            tiles: [
                                'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{{z}}/{{y}}/{{x}}'
                            ],
                            tileSize: 256,
                            attribution: 'Esri World Topographic (Public / Free)'
                        }},
                        'terrain-dem': {{
                            type: 'raster-dem',
                            tiles: [
                                'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{{z}}/{{x}}/{{y}}.png'
                            ],
                            encoding: 'terrarium',
                            tileSize: 256,
                            maxzoom: 15
                        }}
                    }},
                    layers: [
                        {{
                            id: 'sat-layer',
                            type: 'raster',
                            source: 'esri-sat',
                            paint: {{ 'raster-opacity': 0.95 }}
                        }},
                        {{
                            id: 'topo-layer',
                            type: 'raster',
                            source: 'topo-light',
                            layout: {{ visibility: 'none' }},
                            paint: {{ 'raster-opacity': 0.95 }}
                        }}
                    ]
                }},
                center: [lakeLon, lakeLat],
                zoom: 12.5,
                pitch: 58,
                bearing: -20,
                maxPitch: 85,
                antialias: true
            }});

            map.addControl(new maplibregl.NavigationControl({{ visualizePitch: true }}), 'top-right');

            map.on('load', () => {{
                // Enable 3D Terrain DEM mesh
                try {{
                    map.setTerrain({{ source: 'terrain-dem', exaggeration: currentExag }});
                }} catch (e) {{
                    console.warn("Terrain DEM failed to activate:", e);
                    document.getElementById('terrain-status').innerText = '⛰️ 3D Terrain: Perspective Fallback';
                }}

                // 1. Add Water Body Boundary Polygon draped over 3D terrain
                if (lakeGeom && lakeGeom.coordinates) {{
                    map.addSource('lake-source', {{
                        type: 'geojson',
                        data: {{
                            type: 'Feature',
                            geometry: lakeGeom
                        }}
                    }});

                    map.addLayer({{
                        id: 'lake-fill',
                        type: 'fill',
                        source: 'lake-source',
                        paint: {{
                            'fill-color': '#0284c7',
                            'fill-opacity': 0.40
                        }}
                    }});

                    map.addLayer({{
                        id: 'lake-line-glow',
                        type: 'line',
                        source: 'lake-source',
                        paint: {{
                            'line-color': '#22d3ee',
                            'line-width': 4.5,
                            'line-blur': 2
                        }}
                    }});

                    map.addLayer({{
                        id: 'lake-line-crisp',
                        type: 'line',
                        source: 'lake-source',
                        paint: {{
                            'line-color': '#ffffff',
                            'line-width': 2
                        }}
                    }});
                }}

                // 2. Add Watershed Catchment Basin if available
                if (watershedGeom && watershedGeom.coordinates && watershedGeom.coordinates.length > 0) {{
                    map.addSource('watershed-source', {{
                        type: 'geojson',
                        data: {{
                            type: 'Feature',
                            geometry: watershedGeom
                        }}
                    }});

                    map.addLayer({{
                        id: 'watershed-fill',
                        type: 'fill',
                        source: 'watershed-source',
                        paint: {{
                            'fill-color': '#f59e0b',
                            'fill-opacity': 0.25
                        }}
                    }});

                    map.addLayer({{
                        id: 'watershed-line',
                        type: 'line',
                        source: 'watershed-source',
                        paint: {{
                            'line-color': '#d97706',
                            'line-width': 2.5,
                            'line-dasharray': [4, 2]
                        }}
                    }});
                }}

                // 3. Add Flow Pathway Line if available
                if (pathwayGeom && pathwayGeom.coordinates && pathwayGeom.coordinates.length > 0) {{
                    map.addSource('pathway-source', {{
                        type: 'geojson',
                        data: {{
                            type: 'Feature',
                            geometry: pathwayGeom
                        }}
                    }});

                    map.addLayer({{
                        id: 'pathway-line',
                        type: 'line',
                        source: 'pathway-source',
                        paint: {{
                            'line-color': '#f43f5e',
                            'line-width': 3.5,
                            'line-dasharray': [2, 2]
                        }}
                    }});
                }}

                // 4. Add 3D Hotspot Markers
                hotspotsData.forEach(h => {{
                    const el = document.createElement('div');
                    el.className = 'pulse-marker';
                    if (h.severity === 'Severe') {{
                        el.style.backgroundColor = '#ef4444';
                    }} else if (h.severity === 'High') {{
                        el.style.backgroundColor = '#f97316';
                    }} else {{
                        el.style.backgroundColor = '#0284c7';
                    }}

                    const popup = new maplibregl.Popup({{ offset: 15 }}).setHTML(`
                        <div style="font-family: sans-serif; font-size: 12px; color: #0f172a; padding: 4px;">
                            <strong style="color: #0284c7; font-size: 13px;">${{h.hotspot_id}}</strong><br>
                            Type: <b>${{h.indicator_type.replace('_', ' ')}}</b><br>
                            Severity: <b style="color: red;">${{h.severity}}</b> (${{h.inspection_priority}} Priority)<br>
                            Affected Area: ${{h.area_ha}} ha<br>
                            Max Value: ${{h.max_val.toFixed(3)}}
                        </div>
                    `);

                    new maplibregl.Marker({{ element: el }})
                        .setLngLat([h.center_lon, h.center_lat])
                        .setPopup(popup)
                        .addTo(map);
                }});
            }});

            function toggle3DPerspective() {{
                is3D = !is3D;
                const btn = document.getElementById('btn-3d');
                if (is3D) {{
                    map.easeTo({{ pitch: 58, bearing: -20, duration: 1000 }});
                    map.setTerrain({{ source: 'terrain-dem', exaggeration: currentExag }});
                    btn.classList.add('active');
                }} else {{
                    map.easeTo({{ pitch: 0, bearing: 0, duration: 1000 }});
                    map.setTerrain(null);
                    btn.classList.remove('active');
                }}
            }}

            function toggleExaggeration() {{
                if (currentExag === 1.8) {{
                    currentExag = 3.0;
                }} else if (currentExag === 3.0) {{
                    currentExag = 1.0;
                }} else {{
                    currentExag = 1.8;
                }}
                document.getElementById('btn-exag').innerText = `⛰️ Exaggeration: ${{currentExag}}x`;
                if (is3D) {{
                    map.setTerrain({{ source: 'terrain-dem', exaggeration: currentExag }});
                }}
            }}

            function toggleSatelliteBasemap() {{
                isSatellite = !isSatellite;
                const btn = document.getElementById('btn-sat');
                if (isSatellite) {{
                    map.setLayoutProperty('sat-layer', 'visibility', 'visible');
                    map.setLayoutProperty('topo-layer', 'visibility', 'none');
                    btn.classList.remove('active');
                }} else {{
                    map.setLayoutProperty('sat-layer', 'visibility', 'none');
                    map.setLayoutProperty('topo-layer', 'visibility', 'visible');
                    btn.classList.add('active');
                }}
            }}

            function rotateCamera() {{
                rotating = !rotating;
                function rotate() {{
                    if (rotating) {{
                        map.rotateTo((map.getBearing() + 0.4) % 360, {{ duration: 0 }});
                        requestAnimationFrame(rotate);
                    }}
                }}
                if (rotating) rotate();
            }}

            function resetCamera() {{
                rotating = false;
                map.flyTo({{
                    center: [lakeLon, lakeLat],
                    zoom: 12.5,
                    pitch: 58,
                    bearing: -20,
                    duration: 1500
                }});
            }}
        </script>
    </body>
    </html>
    """

    components.html(html_code, height=height)
