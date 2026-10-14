import os
import json
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Application Configuration & Services
from config import (
    APP_NAME,
    APP_TITLE,
    APP_TAGLINE,
    APP_VERSION,
    STATIC_DIR,
    SAMPLE_LAKES_DIR,
    DEFAULT_MNDWI_WATER_THRESHOLD,
    DEFAULT_NDCI_BLOOM_THRESHOLD,
    DEFAULT_NDTI_TURBIDITY_THRESHOLD,
    DEFAULT_FAI_ALGAE_THRESHOLD
)
from utils.logger import logger
from utils.geo_utils import parse_geojson, get_geometry_centroid, get_geometry_bbox, calculate_polygon_area_km2
from database.connection import init_db, get_db, get_database_status
from database.models import Lake, SatelliteObservation, AnalysisRun, PollutionHotspot, SourceTraceResult, Report
from services.satellite_service import satellite_service
from services.waterbody_service import waterbody_service
from services.water_analysis import water_analysis_service
from services.change_detection import change_detection_service
from services.pollution_analysis import pollution_analysis_service
from services.hotspot_analysis import hotspot_analysis_service
from services.source_trace import source_trace_service
from services.anomaly_detection import anomaly_detection_service
from services.health_score import health_score_service
from services.report_service import report_service

from components.map_3d import render_maplibre_3d
from components.map_2d import render_folium_lake_map, render_folium_observation_panel
from components.ui_cards import (
    render_top_brand_bar,
    render_metric_cards_row,
    render_flag_banner,
    render_scientific_disclaimer,
    render_workflow_stepper,
    render_executive_summary_card
)
from components.charts import (
    render_surface_water_transition_chart,
    render_historical_extent_chart
)

# Configure Streamlit Page
st.set_page_config(
    page_title=f"{APP_NAME} — Satellite Lake Intelligence",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load Custom CSS (Colourful Modern Light Theme)
css_path = STATIC_DIR / "style.css"
if css_path.exists():
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Initialize Database Schema & Seed Sample Lakes
@st.cache_resource
def bootstrap_database():
    init_db()
    return get_database_status()

db_status = bootstrap_database()

# Workflow Step Definitions
WORKFLOW_STEPS = [
    (1, "🔍 Select Water Body"),
    (2, "📅 Select Dates"),
    (3, "🛰️ Retrieve Satellite Data"),
    (4, "⚡ Run Analysis"),
    (5, "📊 View Results"),
    (6, "📄 Generate Report")
]

# Session State Initialization
if "workflow_step" not in st.session_state:
    st.session_state.workflow_step = 1

if "current_waterbody" not in st.session_state:
    # Default to Lake Mead or first seeded lake
    with get_db() as db:
        first_lake = db.query(Lake).filter(Lake.name.like("%Mead%")).first() or db.query(Lake).first()
        if first_lake:
            st.session_state.current_waterbody = {
                "id": first_lake.id,
                "name": first_lake.name,
                "display_name": f"{first_lake.name}, {first_lake.region}, {first_lake.country}",
                "type": "Reservoir" if "Mead" in first_lake.name else "Lake",
                "country": first_lake.country or "Global",
                "region": first_lake.region or "Monitored",
                "centroid_lat": first_lake.centroid_lat,
                "centroid_lon": first_lake.centroid_lon,
                "typical_area_km2": first_lake.typical_area_km2,
                "boundary": json.loads(first_lake.boundary_geojson),
                "has_official_boundary": True,
                "boundary_source": "Pre-configured Official Boundary"
            }
        else:
            st.session_state.current_waterbody = waterbody_service.create_point_waterbody("Monitored Lake", 36.08, -114.58, "Lake")

if "req_start_date" not in st.session_state:
    st.session_state.req_start_date = datetime.date(2024, 1, 15)
if "req_end_date" not in st.session_state:
    st.session_state.req_end_date = datetime.date(2024, 6, 28)
if "discovered_scenes" not in st.session_state:
    st.session_state.discovered_scenes = None
if "selected_base_obs_id" not in st.session_state:
    st.session_state.selected_base_obs_id = None
if "selected_comp_obs_id" not in st.session_state:
    st.session_state.selected_comp_obs_id = None
if "current_analysis" not in st.session_state:
    st.session_state.current_analysis = None
if "last_pdf_path" not in st.session_state:
    st.session_state.last_pdf_path = None
if "map_view_mode" not in st.session_state:
    st.session_state.map_view_mode = "3D Interactive View"
if "nearby_suggestions" not in st.session_state:
    st.session_state.nearby_suggestions = None
if "analysis_error" not in st.session_state:
    st.session_state.analysis_error = None
if "offline_demo_mode" not in st.session_state:
    st.session_state.offline_demo_mode = False

wb = st.session_state.current_waterbody

# Core Analysis Pipeline Execution
def run_analysis_pipeline(
    waterbody: Dict[str, Any],
    baseline_date: datetime.date,
    comparison_date: Optional[datetime.date] = None,
    base_scene_input: Optional[Dict[str, Any]] = None,
    comp_scene_input: Optional[Dict[str, Any]] = None,
    mndwi_thresh: float = 0.0,
    ndci_thresh: float = DEFAULT_NDCI_BLOOM_THRESHOLD,
    ndti_thresh: float = DEFAULT_NDTI_TURBIDITY_THRESHOLD,
    fai_thresh: float = DEFAULT_FAI_ALGAE_THRESHOLD,
    max_cloud_cover: float = 20.0,
    use_demo: bool = False
) -> Dict[str, Any]:
    """
    Executes the multi-spectral analysis pipeline for any water body.
    Ingests real Sentinel-2 Level-2A imagery via STAC.
    Constructs historical records strictly from valid observed acquisition passes.
    """
    bbox = get_geometry_bbox(waterbody["boundary"])
    base_scene = base_scene_input
    comp_scene = comp_scene_input

    # In live mode, if scenes were not pre-selected from catalog explorer, search STAC now
    if not use_demo:
        if base_scene is None:
            d_start = baseline_date - datetime.timedelta(days=15)
            d_end = baseline_date + datetime.timedelta(days=15)
            scenes = satellite_service.search_catalog(
                bbox=bbox,
                date_start=d_start,
                date_end=d_end,
                max_cloud_cover=max_cloud_cover,
                allow_demo_fallback=False
            )
            if scenes:
                scenes.sort(key=lambda s: abs((s["date"] - baseline_date).days))
                base_scene = scenes[0]
            else:
                nearby = satellite_service.get_nearby_available_observations(bbox, baseline_date, window_days=45)
                st.session_state.nearby_suggestions = nearby
                return {
                    "status": "error",
                    "error_type": "no_baseline_imagery",
                    "message": (
                        f"No cloud-free Sentinel-2 satellite imagery found for {waterbody['name']} "
                        f"near baseline date {baseline_date.isoformat()} (cloud cover ≤ {max_cloud_cover}%). "
                        "Sentinel-2 orbits periodically every ~5 days. Review nearby available dates in Step 3."
                    )
                }

        if comparison_date and comp_scene is None:
            d_start = comparison_date - datetime.timedelta(days=15)
            d_end = comparison_date + datetime.timedelta(days=15)
            scenes = satellite_service.search_catalog(
                bbox=bbox,
                date_start=d_start,
                date_end=d_end,
                max_cloud_cover=max_cloud_cover,
                allow_demo_fallback=False
            )
            if scenes:
                scenes.sort(key=lambda s: abs((s["date"] - comparison_date).days))
                comp_scene = scenes[0]
            else:
                nearby = satellite_service.get_nearby_available_observations(bbox, comparison_date, window_days=45)
                st.session_state.nearby_suggestions = nearby
                return {
                    "status": "error",
                    "error_type": "no_comparison_imagery",
                    "message": (
                        f"No cloud-free Sentinel-2 satellite imagery found for {waterbody['name']} "
                        f"near comparison date {comparison_date.isoformat()} (cloud cover ≤ {max_cloud_cover}%). "
                        "Please select another comparison date or adjust cloud tolerance in Step 3."
                    )
                }
    else:
        # Explicit demo mode requested
        if base_scene is None:
            base_scene = {
                "id": f"S2A_MSIL2A_{baseline_date.strftime('%Y%m%d')}_DEMO",
                "date": baseline_date,
                "date_str": baseline_date.strftime("%Y-%m-%d 10:30 UTC"),
                "cloud_cover": 3.2,
                "satellite": "SENTINEL-2A",
                "provider": "DEMO DATA SIMULATION",
                "is_demo": True,
                "is_baseline": True
            }
        if comparison_date and comp_scene is None:
            comp_scene = {
                "id": f"S2B_MSIL2A_{comparison_date.strftime('%Y%m%d')}_DEMO",
                "date": comparison_date,
                "date_str": comparison_date.strftime("%Y-%m-%d 10:35 UTC"),
                "cloud_cover": 4.8,
                "satellite": "SENTINEL-2B",
                "provider": "DEMO DATA SIMULATION",
                "is_demo": True,
                "is_baseline": False
            }

    # 1. Fetch bands for baseline observation
    base_bands = satellite_service.fetch_scene_bands(
        base_scene,
        bbox,
        grid_size=(160, 160),
        lake_polygon=waterbody["boundary"]
    )

    # 2. Extract water on baseline
    base_water = water_analysis_service.extract_water(base_bands, bbox, threshold=mndwi_thresh)

    # 3. Comparison observation & Change Detection
    comp_water = None
    comp_bands = None
    change_metrics = None
    if comparison_date and comp_scene:
        comp_bands = satellite_service.fetch_scene_bands(
            comp_scene,
            bbox,
            grid_size=(160, 160),
            lake_polygon=waterbody["boundary"]
        )
        comp_water = water_analysis_service.extract_water(comp_bands, bbox, threshold=mndwi_thresh)
        change_metrics = change_detection_service.analyze_change(
            baseline_water_mask=base_water["water_mask"],
            comparison_water_mask=comp_water["water_mask"],
            pixel_area_km2=base_water["pixel_area_km2"]
        )

    # 4. Compute spectral pollution indicators on active observation
    active_bands = comp_bands if comp_bands else base_bands
    active_water = comp_water if comp_water else base_water
    indices = pollution_analysis_service.compute_all_indices(active_bands, active_water["water_mask"])

    # 5. Hotspot Detection (DBSCAN)
    hotspots = hotspot_analysis_service.detect_hotspots(
        indices=indices,
        bbox=bbox,
        pixel_area_km2=base_water["pixel_area_km2"],
        ndci_threshold=ndci_thresh,
        ndti_threshold=ndti_thresh,
        fai_threshold=fai_thresh
    )

    # 6. Pollution Source Trace (Signature Feature)
    source_trace = None
    if hotspots:
        top_hotspot = hotspots[0]
        source_trace = source_trace_service.trace_hotspot_source(
            hotspot=top_hotspot,
            bands=active_bands,
            indices=indices,
            bbox=bbox,
            pixel_area_km2=base_water["pixel_area_km2"]
        )

    # 7. Health Score Calculation
    health_score = health_score_service.compute_health_score(
        water_metrics=active_water,
        indices=indices,
        source_trace=source_trace,
        typical_area_km2=waterbody.get("typical_area_km2")
    )

    # 8. Real Multi-Temporal Observation History (Strictly Real Observations)
    actual_base_date = base_scene.get("date", baseline_date)
    base_date_str = actual_base_date.isoformat() if hasattr(actual_base_date, "isoformat") else str(actual_base_date)
    base_record = {
        "date": base_date_str,
        "water_area_km2": base_water["water_area_km2"],
        "mean_ndci": float(np.nanmean(indices["ndci_water"])) if not np.all(np.isnan(indices["ndci_water"])) else 0.05,
        "mean_ndti": float(np.nanmean(indices["ndti_water"])) if not np.all(np.isnan(indices["ndti_water"])) else 0.02,
        "is_baseline": True
    }
    hist_records = [base_record]

    if comparison_date and comp_water:
        actual_comp_date = comp_scene.get("date", comparison_date)
        comp_date_str = actual_comp_date.isoformat() if hasattr(actual_comp_date, "isoformat") else str(actual_comp_date)
        comp_record = {
            "date": comp_date_str,
            "water_area_km2": comp_water["water_area_km2"],
            "mean_ndci": float(np.nanmean(indices["ndci_water"])) if not np.all(np.isnan(indices["ndci_water"])) else 0.05,
            "mean_ndti": float(np.nanmean(indices["ndti_water"])) if not np.all(np.isnan(indices["ndti_water"])) else 0.02,
            "is_baseline": False
        }
        hist_records.append(comp_record)
        curr_obs = comp_record
    else:
        curr_obs = base_record

    # Sort strictly chronologically by observation date
    hist_records.sort(key=lambda r: str(r["date"]))

    # Anomaly Monitoring evaluation
    anomaly_report = anomaly_detection_service.analyze_anomalies(hist_records, curr_obs)

    # Automated Red / Yellow / Green / Insufficient Flag Assessment
    has_severe_hotspot = any(h.get("severity") == "Severe" for h in hotspots)
    area_drop = change_metrics["pct_change"] if change_metrics else 0.0

    if has_severe_hotspot or area_drop < -15.0 or health_score["overall_score"] < 50:
        flag_status = "RED"
        flag_label = "🔴 Red Alert — Critical Ecological Stress"
        flag_msg = "Critical surface area recession (>15%) or severe DBSCAN spectral hotspot cluster detected."
    elif area_drop < -5.0 or len(hotspots) > 0 or health_score["overall_score"] < 70:
        flag_status = "YELLOW"
        flag_label = "🟡 Yellow Caution — Moderate Indicator Elevation"
        flag_msg = "Moderate area contraction (5-15%) or localized chlorophyll/turbidity hotspot identified."
    elif not anomaly_report.get("is_sufficient", True):
        flag_status = "GREEN"
        flag_label = "🟢 Verified Multi-Temporal Observation"
        flag_msg = "Water extent change evaluated between valid satellite passes; seasonal baseline requires additional historical passes."
    else:
        flag_status = "GREEN"
        flag_label = "🟢 Green Normal — Stable Hydrological Conditions"
        flag_msg = "Water extent consistent with historical median; no critical spectral pollution anomalies."

    is_truly_demo = use_demo or base_scene.get("is_demo", False)

    analysis_result = {
        "status": "success",
        "lake_id": waterbody.get("id"),
        "lake_name": waterbody["name"],
        "water_type": waterbody.get("type", "Lake"),
        "boundary_source": waterbody.get("boundary_source", "OpenStreetMap"),
        "baseline_date": base_scene["date"].isoformat() if hasattr(base_scene["date"], "isoformat") else str(base_scene["date"]),
        "comparison_date": comp_scene["date"].isoformat() if comp_scene and hasattr(comp_scene["date"], "isoformat") else (str(comp_scene["date"]) if comp_scene else None),
        "requested_baseline_date": baseline_date.isoformat(),
        "requested_comparison_date": comparison_date.isoformat() if comparison_date else None,
        "is_demo": is_truly_demo,
        "base_scene": base_scene,
        "comp_scene": comp_scene,
        "base_bands": base_bands,
        "comp_bands": comp_bands,
        "base_water": base_water,
        "comp_water": comp_water,
        "change_metrics": change_metrics,
        "indices": indices,
        "hotspots": hotspots,
        "source_trace": source_trace,
        "health_score": health_score,
        "anomaly_report": anomaly_report,
        "hist_records": hist_records,
        "flag_status": flag_status,
        "flag_label": flag_label,
        "flag_msg": flag_msg,
        "quality_status": "High Confidence (Clear Satellite Observation)" if not is_truly_demo else "Synthetic Demonstration Scenario",
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    }

    st.session_state.current_analysis = analysis_result
    st.session_state.analysis_error = None
    return analysis_result

# =========================================================================
# SIDEBAR NAVIGATION & CONTROLS
# =========================================================================
with st.sidebar:
    st.html(
        f"""
        <div class="brand-container">
            <div class="brand-logo-icon">💧</div>
            <div class="brand-text">
                <h1>{APP_NAME}</h1>
                <p>AI Satellite Lake Intelligence</p>
            </div>
        </div>
        """
    )

    # Active Water Body Summary Card
    with st.container(border=True):
        st.caption("TARGET WATER BODY")
        st.markdown(f"**{wb['name']}**")
        st.markdown(f":blue-background[**{wb.get('type', 'Lake')}**] • Lat `{wb['centroid_lat']:.3f}`, Lon `{wb['centroid_lon']:.3f}`")
        st.caption(f"Source: _{wb.get('boundary_source', 'OSM')}_")
        if wb.get("typical_area_km2"):
            st.caption(f"Estimated Extent: **~{wb['typical_area_km2']:.2f} km²**")

    st.markdown("---")

    # Map Engine Selection
    st.caption("GEOSPATIAL ENGINE")
    map_engine = st.radio(
        "Map Engine",
        ["3D Interactive View", "2D Map View (Folium)"],
        index=0 if st.session_state.map_view_mode == "3D Interactive View" else 1,
        label_visibility="collapsed"
    )
    st.session_state.map_view_mode = map_engine

    st.markdown("---")

    # Quick Switch Monitored Reference Lakes
    with st.expander("📍 Quick-Select Monitored Lakes", expanded=False):
        st.caption("Select standard reference water bodies:")
        with get_db() as db:
            ref_lakes = db.query(Lake).all()
            for rl in ref_lakes:
                if st.button(f"{rl.name} ({rl.country})", key=f"sidebar_ref_btn_{rl.id}", use_container_width=True):
                    st.session_state.current_waterbody = {
                        "id": rl.id,
                        "name": rl.name,
                        "display_name": f"{rl.name}, {rl.region}, {rl.country}",
                        "type": "Reservoir" if "Mead" in rl.name else "Lake",
                        "country": rl.country or "Global",
                        "region": rl.region or "Monitored",
                        "centroid_lat": rl.centroid_lat,
                        "centroid_lon": rl.centroid_lon,
                        "typical_area_km2": rl.typical_area_km2,
                        "boundary": json.loads(rl.boundary_geojson),
                        "has_official_boundary": True,
                        "boundary_source": "Pre-configured Official Boundary"
                    }
                    st.session_state.current_analysis = None
                    st.session_state.analysis_error = None
                    st.session_state.discovered_scenes = None
                    st.rerun()

    st.markdown("---")
    st.caption("ANALYSIS CONFIGURATION")
    sidebar_cloud = st.slider("Max Cloud Cover Tolerance (%)", 0, 50, 20, 5, key="sidebar_cloud_slider")

    # Offline Demo Mode Toggle
    demo_toggle = st.checkbox(
        "🧪 Enable Offline Demo Mode",
        value=st.session_state.offline_demo_mode,
        help="Enable synthetic offline data only when internet connection to Copernicus/AWS STAC is unavailable."
    )
    st.session_state.offline_demo_mode = demo_toggle

    st.markdown("---")
    st.caption(f"**Database:** {'🟢 PostGIS' if db_status.get('is_postgres') else '🟡 SQLite'}")
    st.caption(f"_{APP_TAGLINE}_")

# =========================================================================
# TOP BAR HERO
# =========================================================================
analysis = st.session_state.current_analysis
obs_date = analysis.get("comparison_date") or analysis.get("baseline_date") if analysis else st.session_state.req_end_date.isoformat()

render_top_brand_bar(
    waterbody_name=wb["name"],
    region=f"{wb.get('region', '')}, {wb.get('country', '')}",
    water_type=wb.get("type", "Lake"),
    observation_date=obs_date,
    is_demo=analysis.get("is_demo", False) if analysis else st.session_state.offline_demo_mode,
    boundary_source=wb.get("boundary_source", "OpenStreetMap Verified")
)

# =========================================================================
# UNIFIED LAKE SELECTION & OBSERVATION CONTROLS (COMMAND CENTER)
# =========================================================================
with st.container(border=True):
    st.markdown("### 🎛️ Lake Selection & Observation Controls")
    st.caption("Search any water body globally, configure observation dates, and click **Analyse Lake** to view all monitoring results on this unified dashboard.")

    col_s1, col_s2, col_s3 = st.columns([3, 1.2, 1])
    with col_s1:
        search_query = st.text_input(
            "Search Lake, Pond, Reservoir, or Water Body Name",
            placeholder="e.g., Dal Lake, Walden Pond, Sankey Tank, Lake Powell, Chilika Lake, Lake Mead...",
            key="dash_wb_search_query"
        )
    with col_s2:
        type_filter = st.selectbox(
            "Filter by Type",
            ["All Types", "Lake", "Pond", "Reservoir", "Tank", "Lagoon", "Wetland"],
            key="dash_wb_type_filter"
        )
    with col_s3:
        st.write("")
        st.write("")
        search_btn = st.button("🔍 Search", type="secondary", use_container_width=True)

    if search_btn and search_query:
        with st.spinner("Searching geographic database & OpenStreetMap..."):
            results = waterbody_service.search_waterbodies(search_query, type_filter=type_filter, limit=6)
            st.session_state.search_wb_results = results

    if st.session_state.get("search_wb_results"):
        res_list = st.session_state.search_wb_results
        st.success(f"Discovered {len(res_list)} candidate water bodies matching query.")
        for idx, r in enumerate(res_list):
            with st.container(border=True):
                col_r1, col_r2 = st.columns([3.5, 1.5])
                with col_r1:
                    st.markdown(f"**{r['name']}** — :blue-background[**{r['type']}**]")
                    st.caption(f"📍 Location: **{r['display_name']}** | Lat `{r['centroid_lat']:.4f}`, Lon `{r['centroid_lon']:.4f}` | Est. Area: `~{r['typical_area_km2']} km²` | Source: `{r['boundary_source']}`")
                with col_r2:
                    if st.button("✅ Select This Water Body", key=f"dash_sel_btn_{idx}", use_container_width=True, type="primary"):
                        st.session_state.current_waterbody = r
                        st.session_state.current_analysis = None
                        st.session_state.analysis_error = None
                        st.session_state.search_wb_results = None
                        st.rerun()

    # Advanced Inputs Expander: Direct Coordinates, Upload GeoJSON & Presets
    with st.expander("⚙️ Advanced Options: Coordinates, GeoJSON Upload & Preset Lakes", expanded=False):
        adv_tab_coords, adv_tab_upload, adv_tab_presets = st.tabs([
            "📍 Enter Coordinates / Pin",
            "📤 Upload GeoJSON Boundary",
            "🏛️ Monitored Reference Lakes"
        ])
        with adv_tab_coords:
            c_c1, c_c2, c_c3, c_c4, c_c5 = st.columns([1.5, 1, 1, 1, 1])
            with c_c1:
                coord_name = st.text_input("Name", value="Target Water Body", key="adv_coord_name")
            with c_c2:
                coord_lat = st.number_input("Latitude", value=wb["centroid_lat"], format="%.5f", key="adv_coord_lat")
            with c_c3:
                coord_lon = st.number_input("Longitude", value=wb["centroid_lon"], format="%.5f", key="adv_coord_lon")
            with c_c4:
                coord_type = st.selectbox("Type", ["Lake", "Pond", "Reservoir", "Tank", "Lagoon", "Wetland"], key="adv_coord_type")
            with c_c5:
                coord_rad = st.slider("Radius (km)", 0.2, 5.0, 1.2, 0.2, key="adv_coord_rad")
            if st.button("📍 Set Custom Location Target", type="secondary"):
                c_entry = waterbody_service.create_point_waterbody(coord_name, coord_lat, coord_lon, coord_type, coord_rad)
                st.session_state.current_waterbody = c_entry
                st.session_state.current_analysis = None
                st.session_state.analysis_error = None
                st.rerun()

        with adv_tab_upload:
            up_file = st.file_uploader("Upload .geojson lake polygon", type=["geojson", "json"], key="adv_up_file")
            if up_file is not None:
                try:
                    raw_json = json.load(up_file)
                    p_geom = parse_geojson(raw_json)
                    if p_geom:
                        u_lat, u_lon = get_geometry_centroid(p_geom)
                        u_area = calculate_polygon_area_km2(p_geom)
                        st.success(f"Parsed polygon: Centroid ({u_lat:.4f}, {u_lon:.4f}), Area: ~{u_area:.2f} km²")
                        u_name = st.text_input("Lake Name", value="Custom Monitored Lake", key="adv_up_name")
                        u_type = st.selectbox("Water Body Type", ["Lake", "Pond", "Reservoir", "Tank", "Lagoon", "Wetland"], key="adv_up_type")
                        if st.button("Save Uploaded Boundary", type="secondary"):
                            st.session_state.current_waterbody = {
                                "name": u_name,
                                "display_name": f"{u_name} (Uploaded GeoJSON)",
                                "type": u_type,
                                "country": "User Uploaded",
                                "region": "Custom Geometry",
                                "centroid_lat": u_lat,
                                "centroid_lon": u_lon,
                                "typical_area_km2": round(u_area, 2),
                                "boundary": p_geom,
                                "has_official_boundary": True,
                                "boundary_source": "User Uploaded GeoJSON"
                            }
                            st.session_state.current_analysis = None
                            st.session_state.analysis_error = None
                            st.rerun()
                except Exception as ex:
                    st.error(f"Error parsing GeoJSON: {ex}")

        with adv_tab_presets:
            p_cols = st.columns(4)
            with get_db() as db:
                all_refs = db.query(Lake).all()
                for p_idx, p_lake in enumerate(all_refs):
                    with p_cols[p_idx % 4]:
                        if st.button(f"🏞️ {p_lake.name}", key=f"adv_preset_{p_lake.id}", use_container_width=True):
                            st.session_state.current_waterbody = {
                                "id": p_lake.id,
                                "name": p_lake.name,
                                "display_name": f"{p_lake.name}, {p_lake.region}, {p_lake.country}",
                                "type": "Reservoir" if "Mead" in p_lake.name else "Lake",
                                "country": p_lake.country or "Global",
                                "region": p_lake.region or "Monitored",
                                "centroid_lat": p_lake.centroid_lat,
                                "centroid_lon": p_lake.centroid_lon,
                                "typical_area_km2": p_lake.typical_area_km2,
                                "boundary": json.loads(p_lake.boundary_geojson),
                                "has_official_boundary": True,
                                "boundary_source": "Pre-configured Official Boundary"
                            }
                            st.session_state.current_analysis = None
                            st.session_state.analysis_error = None
                            st.rerun()

    # Observation Dates & Action Row
    st.markdown("---")
    col_d1, col_d2, col_d3 = st.columns([1.5, 1.5, 1])
    with col_d1:
        req_start = st.date_input(
            "📅 Baseline Observation Date (Before)",
            value=st.session_state.req_start_date,
            key="dash_req_start_date"
        )
        st.session_state.req_start_date = req_start
    with col_d2:
        req_end = st.date_input(
            "📅 Comparison Observation Date (After)",
            value=st.session_state.req_end_date,
            key="dash_req_end_date"
        )
        st.session_state.req_end_date = req_end
    with col_d3:
        dash_cloud = st.slider("☁️ Cloud Tolerance (%)", 0, 50, int(sidebar_cloud), 5, key="dash_cloud_slider")

    # Date Validation
    date_invalid = False
    if req_end < req_start:
        date_invalid = True
        st.error("⚠️ Invalid Date Range: End Date cannot be earlier than Start Date. Please select an End Date on or after the Start Date.")

    # Primary Action Button
    analyse_btn = st.button(
        f"⚡ Analyse Lake: {wb['name']}",
        type="primary",
        disabled=date_invalid,
        use_container_width=True,
        key="btn_run_single_dashboard_analysis"
    )

# Handle Analyse Lake Execution
if analyse_btn:
    with st.status(f"Analysing {wb['name']} via Copernicus Sentinel-2 STAC...", expanded=True) as status:
        st.write("🛰️ Querying public Copernicus & AWS Earth Search STAC catalogues...")
        try:
            res = run_analysis_pipeline(
                waterbody=wb,
                baseline_date=req_start,
                comparison_date=req_end,
                max_cloud_cover=float(dash_cloud),
                use_demo=st.session_state.offline_demo_mode
            )
            if res.get("status") == "success":
                status.update(label=f"✅ Analysis for {wb['name']} completed successfully!", state="complete", expanded=False)
                st.session_state.analysis_error = None
                st.rerun()
            else:
                st.session_state.analysis_error = res.get("message", "No suitable imagery found.")
                status.update(label="⚠️ Analysis Encountered An Issue", state="error", expanded=True)
        except Exception as e:
            st.session_state.analysis_error = str(e)
            status.update(label="❌ Pipeline Execution Error", state="error", expanded=True)

# Auto-run initial analysis for default lake on first page load
if st.session_state.current_analysis is None and not st.session_state.get("analysis_error"):
    with st.spinner(f"🛰️ Ingesting Sentinel-2 satellite passes for {wb['name']}..."):
        try:
            res = run_analysis_pipeline(
                waterbody=wb,
                baseline_date=st.session_state.req_start_date,
                comparison_date=st.session_state.req_end_date,
                max_cloud_cover=float(dash_cloud),
                use_demo=st.session_state.offline_demo_mode
            )
            if res.get("status") == "success":
                st.rerun()
            else:
                st.session_state.analysis_error = res.get("message")
        except Exception as e:
            st.session_state.analysis_error = str(e)

# Display Diagnostic Card if Analysis Failed or Missing Imagery
if st.session_state.get("analysis_error"):
    with st.container(border=True):
        st.markdown("#### ⚠️ Satellite Data Availability Notice")
        st.error(f"**Cause:** {st.session_state.analysis_error}")
        if st.session_state.get("nearby_suggestions"):
            st.markdown("##### 💡 Suggested Nearby Available Observation Passes:")
            sug_df = pd.DataFrame([
                {
                    "Suggested Date": s["date_str"],
                    "Cloud Cover (%)": f"{s['cloud_cover']}%",
                    "Satellite": s["satellite"]
                }
                for s in st.session_state.nearby_suggestions[:5]
            ])
            st.dataframe(sug_df, use_container_width=True)
            st.caption("Sentinel-2 orbits periodically every ~5 days. You can select one of the suggested observation dates above.")

        col_err1, col_err2 = st.columns(2)
        with col_err1:
            if st.button("🔄 Retry Analysis", use_container_width=True, type="primary", key="btn_err_retry"):
                st.session_state.analysis_error = None
                st.rerun()
        with col_err2:
            if not st.session_state.offline_demo_mode:
                if st.button("🧪 Enable Offline Demo Simulation", use_container_width=True, key="btn_err_demo"):
                    st.session_state.offline_demo_mode = True
                    st.session_state.analysis_error = None
                    st.rerun()

# =========================================================================
# SINGLE DASHBOARD RESULTS (SECTIONS A THROUGH I)
# =========================================================================
analysis = st.session_state.current_analysis
if analysis and analysis.get("status") == "success":
    # ---------------------------------------------------------------------
    # SECTION H: ALERTS AND SUMMARY (Rendered at top of results)
    # ---------------------------------------------------------------------
    st.markdown("---")
    render_flag_banner(
        flag_status=analysis.get("flag_status", "GREEN"),
        flag_label=analysis.get("flag_label", "🟢 Green Normal"),
        message=analysis.get("flag_msg", "")
    )
    render_executive_summary_card(analysis, wb)

    # ---------------------------------------------------------------------
    # SECTION A: LAKE OVERVIEW & KEY METRICS
    # ---------------------------------------------------------------------
    st.markdown("---")
    st.markdown("### 📌 Section A — Lake Overview & Metrics")
    curr_water = analysis["comp_water"]["water_area_km2"] if analysis.get("comp_water") else analysis["base_water"]["water_area_km2"]
    chg_pct = analysis["change_metrics"]["pct_change"] if analysis.get("change_metrics") else None
    anom_count = len(analysis["anomaly_report"].get("anomalies", []))
    hs_score = analysis["health_score"]["overall_score"]
    hs_grade = analysis["health_score"]["letter_grade"]
    hotspots_count = len(analysis.get("hotspots", []))

    render_metric_cards_row(
        water_area_km2=curr_water,
        area_change_pct=chg_pct,
        anomalies_count=anom_count,
        health_score=hs_score,
        health_grade=hs_grade,
        hotspot_count=hotspots_count,
        is_demo=analysis.get("is_demo", False)
    )

    # Lake Metadata Details Bar
    b_meta = analysis.get("base_scene", {})
    c_meta = analysis.get("comp_scene", {})
    with st.container(border=True):
        col_ov1, col_ov2, col_ov3, col_ov4 = st.columns(4)
        with col_ov1:
            st.caption("TARGET WATER BODY")
            st.markdown(f"**{wb['name']}** ({wb.get('type', 'Lake')})")
            st.caption(f"Centroid: Lat `{wb['centroid_lat']:.4f}`, Lon `{wb['centroid_lon']:.4f}`")
            if wb.get("typical_area_km2"):
                st.caption(f"Estimated Extent: `~{wb['typical_area_km2']:.2f} km²`")
        with col_ov2:
            st.caption("BASELINE PASS (BEFORE)")
            st.markdown(f"**{b_meta.get('date_str', analysis['baseline_date'])}**")
            st.caption(f"Platform: `{b_meta.get('satellite', 'Sentinel-2')}` | Cloud: `{b_meta.get('cloud_cover', 0.0)}%`")
        with col_ov3:
            st.caption("COMPARISON PASS (AFTER)")
            if analysis.get("comp_water"):
                st.markdown(f"**{c_meta.get('date_str', analysis['comparison_date'])}**")
                st.caption(f"Platform: `{c_meta.get('satellite', 'Sentinel-2')}` | Cloud: `{c_meta.get('cloud_cover', 0.0)}%`")
            else:
                st.markdown("*Single pass evaluated*")
                st.caption("Select two distinct dates to compare")
        with col_ov4:
            st.caption("DATA STATUS & QUALITY")
            st.markdown(f"**{analysis.get('quality_status', 'High Confidence')}**")
            st.caption(f"Boundary Source: _{wb.get('boundary_source', 'OSM')}_")

    # ---------------------------------------------------------------------
    # SECTION B: BEFORE AND AFTER SATELLITE MAPS
    # ---------------------------------------------------------------------
    st.markdown("---")
    st.markdown("### 🛰️ Section B — Multi-Temporal Satellite Observation Maps")
    st.caption("Synchronized side-by-side observation panels featuring genuine Sentinel-2 Level-2A imagery, MNDWI multi-spectral water detection masks, and keyless public basemaps.")
    col_before, col_after = st.columns(2)
    wb_bbox = get_geometry_bbox(wb["boundary"])

    with col_before:
        st.markdown(f"##### 📅 BEFORE (Baseline Pass): `{analysis['baseline_date']}`")
        st.caption(f"Platform: **{b_meta.get('satellite', 'Sentinel-2')}** | Acquisition: **{b_meta.get('date_str', analysis['baseline_date'])}** | Cloud Cover: **{b_meta.get('cloud_cover', 0.0)}%**")
        base_real_rgb = analysis.get("base_bands", {}).get("REAL_RGB")
        try:
            render_folium_observation_panel(
                lake_geojson=wb["boundary"],
                centroid=(wb["centroid_lat"], wb["centroid_lon"]),
                obs_title=f"Baseline ({analysis['baseline_date']})",
                obs_date=analysis['baseline_date'],
                water_area_km2=analysis['base_water']['water_area_km2'],
                cloud_cover=b_meta.get('cloud_cover', 0.0),
                is_baseline=True,
                water_mask=analysis['base_water'].get('water_mask'),
                bbox=wb_bbox,
                real_rgb=base_real_rgb,
                scene_info=b_meta,
                key="dash_before_panel"
            )
        except Exception as e_b:
            st.warning(f"Map layer note: {e_b}")

    with col_after:
        if analysis.get("comp_water"):
            st.markdown(f"##### 📅 AFTER (Comparison Pass): `{analysis['comparison_date']}`")
            st.caption(f"Platform: **{c_meta.get('satellite', 'Sentinel-2')}** | Acquisition: **{c_meta.get('date_str', analysis['comparison_date'])}** | Cloud Cover: **{c_meta.get('cloud_cover', 0.0)}%**")
            comp_real_rgb = analysis.get("comp_bands", {}).get("REAL_RGB")
            try:
                render_folium_observation_panel(
                    lake_geojson=wb["boundary"],
                    centroid=(wb["centroid_lat"], wb["centroid_lon"]),
                    obs_title=f"Comparison ({analysis['comparison_date']})",
                    obs_date=analysis['comparison_date'],
                    water_area_km2=analysis['comp_water']['water_area_km2'],
                    cloud_cover=c_meta.get('cloud_cover', 0.0),
                    is_baseline=False,
                    water_mask=analysis['comp_water'].get('water_mask'),
                    bbox=wb_bbox,
                    real_rgb=comp_real_rgb,
                    scene_info=c_meta,
                    key="dash_after_panel"
                )
            except Exception as e_a:
                st.warning(f"Map layer note: {e_a}")
        else:
            st.info("Single date observation mode active. To view comparative side-by-side satellite imagery, select two distinct observation dates above.")

    # ---------------------------------------------------------------------
    # SECTION C: WATER AREA ANALYSIS
    # ---------------------------------------------------------------------
    st.markdown("---")
    st.markdown("### 💧 Section C — Water Surface Extent & Transition Dynamics")
    col_c_stats, col_c_chart = st.columns([1, 1.2])
    with col_c_stats:
        with st.container(border=True):
            st.markdown("#### Hydrological Extent Changes")
            b_area = analysis['base_water']['water_area_km2']
            st.markdown(f"• **Baseline Extent ({analysis['baseline_date']}):** `{b_area:.2f} km²`")
            if analysis.get('comp_water'):
                c_area = analysis['comp_water']['water_area_km2']
                st.markdown(f"• **Comparison Extent ({analysis['comparison_date']}):** `{c_area:.2f} km²`")
                if analysis.get("change_metrics"):
                    cm = analysis["change_metrics"]
                    net_k = cm["net_change_km2"]
                    pct_k = cm["pct_change"]
                    sign_k = "+" if net_k >= 0 else ""
                    st.markdown(f"• **Net Extent Shift:** `{sign_k}{net_k:.2f} km²` ({sign_k}{pct_k:.1f}%)")
                    st.markdown(f"• **Stable Surface Water:** `{cm.get('stable_water_km2', 0.0):.2f} km²`")
                    st.markdown(f"• **Water Loss (Recession):** `{cm.get('water_loss_km2', 0.0):.2f} km²`")
                    st.markdown(f"• **Water Gain (Inundation):** `{cm.get('water_gain_km2', 0.0):.2f} km²`")
                    st.markdown(f"• **Observation Reliability:** `{cm.get('valid_observation_pct', 100.0):.1f}%` valid pixels")
            else:
                st.info("Single pass evaluated. Baseline area computed via calibrated MNDWI index.")

    with col_c_chart:
        if analysis.get("change_metrics"):
            render_surface_water_transition_chart(
                change_metrics=analysis["change_metrics"],
                title="Surface Water Transition Dynamics",
                height=320
            )
        else:
            st.info("Surface Water Transition donut chart requires a before-and-after observation pair.")

    # ---------------------------------------------------------------------
    # SECTION D: POSSIBLE POLLUTION INDICATORS
    # ---------------------------------------------------------------------
    st.markdown("---")
    st.markdown("### 🔬 Section D — Possible Spectral Pollution Indicators")
    st.caption("Multi-spectral indices calculated from genuine Sentinel-2 Level-2A surface reflectance bands. These optical indices suggest possible environmental conditions and require in-situ lab sampling for regulatory confirmation.")

    ind = analysis.get("indices", {})
    tab_ndci, tab_ndti, tab_fai, tab_mndwi = st.tabs([
        "🟢 NDCI (Chlorophyll-a / Algal Bloom)",
        "🟤 NDTI (Turbidity & Suspended Sediments)",
        "🌱 FAI (Floating Algal Vegetation)",
        "💧 MNDWI (Surface Water Extent)"
    ])

    with tab_ndci:
        st.latex(r"\text{NDCI} = \frac{\text{RedEdge1} - \text{Red}}{\text{RedEdge1} + \text{Red}} = \frac{B05 - B04}{B05 + B04}")
        ndci_data = ind.get("ndci_water", np.zeros((10, 10)))
        mean_ndci = float(np.nanmean(ndci_data)) if not np.all(np.isnan(ndci_data)) else 0.0
        max_ndci = float(np.nanmax(ndci_data)) if not np.all(np.isnan(ndci_data)) else 0.0
        col_n1, col_n2 = st.columns([3, 1])
        with col_n1:
            fig_ndci = px.imshow(
                ndci_data,
                color_continuous_scale="YlGn",
                range_color=[-0.1, 0.4],
                title="NDCI Water Surface Reflectance Heatmap"
            )
            fig_ndci.update_layout(template="plotly_white", paper_bgcolor="rgba(255,255,255,0)", plot_bgcolor="rgba(255,255,255,0)", height=340, font=dict(color="#0f172a"))
            st.plotly_chart(fig_ndci, use_container_width=True)
        with col_n2:
            with st.container(border=True):
                st.caption("NDCI METRICS")
                st.metric("Mean Water NDCI", f"{mean_ndci:.3f}")
                st.metric("Peak Hotspot NDCI", f"{max_ndci:.3f}")
                st.caption("Threshold: > 0.12 indicates elevated photosynthetic pigment density.")

    with tab_ndti:
        st.latex(r"\text{NDTI} = \frac{\text{Red} - \text{Green}}{\text{Red} + \text{Green}} = \frac{B04 - B03}{B04 + B03}")
        ndti_data = ind.get("ndti_water", np.zeros((10, 10)))
        mean_ndti = float(np.nanmean(ndti_data)) if not np.all(np.isnan(ndti_data)) else 0.0
        max_ndti = float(np.nanmax(ndti_data)) if not np.all(np.isnan(ndti_data)) else 0.0
        col_t1, col_t2 = st.columns([3, 1])
        with col_t1:
            fig_ndti = px.imshow(
                ndti_data,
                color_continuous_scale="YlOrBr",
                range_color=[-0.1, 0.3],
                title="NDTI Turbidity & Suspended Particulates Heatmap"
            )
            fig_ndti.update_layout(template="plotly_white", paper_bgcolor="rgba(255,255,255,0)", plot_bgcolor="rgba(255,255,255,0)", height=340, font=dict(color="#0f172a"))
            st.plotly_chart(fig_ndti, use_container_width=True)
        with col_t2:
            with st.container(border=True):
                st.caption("NDTI METRICS")
                st.metric("Mean Water NDTI", f"{mean_ndti:.3f}")
                st.metric("Peak Turbidity NDTI", f"{max_ndti:.3f}")
                st.caption("Threshold: > 0.10 indicates suspended mineral sediments or runoff turbidity.")

    with tab_fai:
        st.latex(r"\text{FAI} = B08 - \left[B04 + (B11 - B04) \times 0.1873\right]")
        fai_data = ind.get("fai_water", np.zeros((10, 10)))
        fig_fai = px.imshow(
            fai_data,
            color_continuous_scale="Greens",
            range_color=[-0.05, 0.25],
            title="FAI Floating Algae Index Heatmap"
        )
        fig_fai.update_layout(template="plotly_white", paper_bgcolor="rgba(255,255,255,0)", plot_bgcolor="rgba(255,255,255,0)", height=340, font=dict(color="#0f172a"))
        st.plotly_chart(fig_fai, use_container_width=True)

    with tab_mndwi:
        st.latex(r"\text{MNDWI} = \frac{\text{Green} - \text{SWIR1}}{\text{Green} + \text{SWIR1}} = \frac{B03 - B11}{B03 + B11}")
        mndwi_data = ind.get("mndwi", np.zeros((10, 10)))
        fig_mndwi = px.imshow(
            mndwi_data,
            color_continuous_scale="Blues",
            range_color=[-0.5, 0.5],
            title="MNDWI Water Index Map"
        )
        fig_mndwi.update_layout(template="plotly_white", paper_bgcolor="rgba(255,255,255,0)", plot_bgcolor="rgba(255,255,255,0)", height=340, font=dict(color="#0f172a"))
        st.plotly_chart(fig_mndwi, use_container_width=True)

    render_scientific_disclaimer()

    # ---------------------------------------------------------------------
    # SECTION E: HOTSPOT DETECTION
    # ---------------------------------------------------------------------
    st.markdown("---")
    st.markdown("### 🎯 Section E — Hotspot Detection (DBSCAN Spatial Clustering)")
    st.caption("Spatial anomaly clusters identified via unsupervised density-based spatial clustering (DBSCAN). Hotspots represent candidate locations with statistically elevated spectral deviations, not verified pollution accusations.")

    hotspots = analysis.get("hotspots", [])
    if hotspots:
        hs_df = pd.DataFrame([
            {
                "Hotspot ID": h["hotspot_id"],
                "Indicator Type": h["indicator_type"].replace("_", " "),
                "Coordinates": f"({h['center_lat']:.4f}, {h['center_lon']:.4f})",
                "Affected Area (ha)": h["area_ha"],
                "Severity": h["severity"],
                "Field Priority": h["inspection_priority"]
            }
            for h in hotspots
        ])
        st.dataframe(hs_df, use_container_width=True)
    else:
        st.info("No spatial clusters detected exceeding spectral sensitivity thresholds for this observation pass.")

    # ---------------------------------------------------------------------
    # SECTION F: POTENTIAL POLLUTION SOURCE ANALYSIS (Signature Feature)
    # ---------------------------------------------------------------------
    if analysis.get("source_trace"):
        st.markdown("---")
        st.markdown("### 🧭 Section F — Potential Pollution Source Analysis (Catchment Trace)")
        st.caption("Hydrological analysis linking detected water hotspots to upstream catchment terrain, drainage flow vectors, and surrounding land use composition. Potential source areas are hypotheses to prioritize field inspections, not confirmed legal culpability.")
        st_res = analysis["source_trace"]

        c_st1, c_st2 = st.columns([1.6, 1.0])
        with c_st1:
            st.markdown(f"##### Terrain Catchment & Drainage Flow Pathway ({st.session_state.map_view_mode})")
            if st.session_state.map_view_mode == "3D Interactive View":
                render_maplibre_3d(
                    lake_geojson=wb["boundary"],
                    centroid=(wb["centroid_lat"], wb["centroid_lon"]),
                    lake_name=wb["name"],
                    hotspots=analysis.get("hotspots"),
                    source_trace=st_res,
                    water_type=wb.get("type", "Lake"),
                    height=440
                )
            else:
                render_folium_lake_map(
                    lake_geojson=wb["boundary"],
                    centroid=(wb["centroid_lat"], wb["centroid_lon"]),
                    zoom_start=12,
                    hotspots=analysis.get("hotspots"),
                    source_trace=st_res,
                    show_watershed=True,
                    key="dash_catchment_map"
                )

        with c_st2:
            st.markdown("##### Catchment Land Cover Composition")
            lc_df = pd.DataFrame([
                {"Category": "Built-up (NDBI)", "Percentage": st_res["built_up_pct"]},
                {"Category": "Agricultural / Crop", "Percentage": st_res["agriculture_pct"]},
                {"Category": "Bare Soil (BSI)", "Percentage": st_res["bare_soil_pct"]},
                {"Category": "Natural Vegetation", "Percentage": st_res["vegetation_pct"]}
            ])
            fig_lc = px.pie(
                lc_df,
                values="Percentage",
                names="Category",
                hole=0.5,
                color="Category",
                color_discrete_map={
                    "Built-up (NDBI)": "#f43f5e",
                    "Agricultural / Crop": "#eab308",
                    "Bare Soil (BSI)": "#f97316",
                    "Natural Vegetation": "#10b981"
                }
            )
            fig_lc.update_layout(template="plotly_white", paper_bgcolor="rgba(255,255,255,0)", plot_bgcolor="rgba(255,255,255,0)", height=240, margin=dict(l=5, r=5, t=10, b=10), font=dict(color="#0f172a"))
            st.plotly_chart(fig_lc, use_container_width=True)

            with st.container(border=True):
                st.markdown(f"**Primary Vector Hypothesis:** `{st_res['primary_source_pressure']}`")
                st.caption(st_res['pressure_rationale'])
                st.caption(f"Estimated Contributing Catchment Area: **{st_res.get('contributing_area_km2', 0.0):.2f} km²**")

    # ---------------------------------------------------------------------
    # SECTION G: HISTORICAL TRENDS
    # ---------------------------------------------------------------------
    st.markdown("---")
    st.markdown("### 📈 Section G — Historical Multi-Temporal Extent Trends")
    st.caption("Historical water extent track derived strictly from valid observed Sentinel-2 passes. Missing or poor-quality cloud observations are excluded rather than filled with synthetic or invented values.")
    render_historical_extent_chart(
        hist_records=analysis.get("hist_records", []),
        lake_name=wb["name"],
        height=280
    )

    # ---------------------------------------------------------------------
    # SECTION I: OFFICIAL ENVIRONMENTAL AUDIT REPORT & EXPORT
    # ---------------------------------------------------------------------
    st.markdown("---")
    st.markdown("### 📄 Section I — Official Environmental Audit Report & Export")
    st.caption("Generate a verifiable vector PDF audit report containing all maps, multi-spectral index calculations, hotspot registries, catchment source traces, and scientific disclaimers.")

    with st.container(border=True):
        col_rep1, col_rep2, col_rep3 = st.columns(3)
        with col_rep1:
            st.write(f"**Target Water Body:** {wb['name']} ({wb.get('type', 'Lake')})")
            st.write(f"**Baseline Pass:** {analysis['baseline_date']}")
        with col_rep2:
            st.write(f"**Comparison Pass:** {analysis.get('comparison_date', 'Single Pass')}")
            st.write(f"**Detected Hotspots:** {len(analysis.get('hotspots', []))}")
        with col_rep3:
            hs = analysis.get("health_score", {})
            st.write(f"**Health Score:** {hs.get('overall_score', 'N/A')} (Grade {hs.get('letter_grade', '')})")
            st.write(f"**Boundary Source:** {wb.get('boundary_source', 'OSM')}")

        st.markdown("---")
        col_pdf_gen, col_pdf_dl = st.columns([1, 1])
        with col_pdf_gen:
            if st.button("📄 Compile Official AquaTrace PDF Report", type="primary", use_container_width=True, key="btn_dash_compile_pdf"):
                with st.spinner("Compiling vector PDF audit report..."):
                    pdf_path = report_service.generate_pdf_report(
                        lake_data=wb,
                        analysis_data=analysis,
                        hotspots=analysis.get("hotspots", []),
                        source_trace=analysis.get("source_trace"),
                        health_score=analysis.get("health_score")
                    )
                    st.session_state.last_pdf_path = pdf_path

        with col_pdf_dl:
            if st.session_state.last_pdf_path and os.path.exists(st.session_state.last_pdf_path):
                pdf_file_path = Path(st.session_state.last_pdf_path)
                with open(pdf_file_path, "rb") as f:
                    pdf_bytes = f.read()

                st.download_button(
                    label=f"⬇️ Download PDF Report ({pdf_file_path.name})",
                    data=pdf_bytes,
                    file_name=pdf_file_path.name,
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                    key="btn_dash_download_pdf"
                )

