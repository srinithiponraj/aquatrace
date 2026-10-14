import streamlit as st
from typing import Optional
from config import APP_NAME, APP_VERSION

def render_top_brand_bar(
    waterbody_name: str,
    region: str,
    water_type: str = "Lake",
    observation_date: str = "2024-04-15",
    is_demo: bool = False,
    boundary_source: str = "OpenStreetMap Verified Polygon"
):
    """
    Render prominent hero top bar with water body name, classification badge,
    boundary source indicator, observation date, and explicit live/demo status.
    """
    type_badge_map = {
        "Lake": "badge-lake",
        "Pond": "badge-pond",
        "Reservoir": "badge-reservoir",
        "Tank": "badge-tank",
        "Lagoon": "badge-lagoon",
        "Wetland": "badge-pond",
        "Water body — type unverified": "badge-unverified"
    }
    badge_cls = type_badge_map.get(water_type, "badge-unverified")

    type_icon_map = {
        "Lake": "🏞️",
        "Pond": "💧",
        "Reservoir": "🌊",
        "Tank": "🏺",
        "Lagoon": "🏝️",
        "Wetland": "🌿",
        "Water body — type unverified": "❔"
    }
    t_icon = type_icon_map.get(water_type, "💧")

    st.html(
        f"""
        <div class="topbar-hero">
            <div>
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 6px;">
                    <span style="font-size: 24px;">{t_icon}</span>
                    <h2 style="margin: 0; color: #0f172a; font-size: 24px; font-weight: 800; letter-spacing: -0.5px;">{waterbody_name}</h2>
                    <span class="{badge_cls}">{t_icon} {water_type}</span>
                    {"<span class='badge-demo-data'>⚠️ DEMO DATA</span>" if is_demo else "<span class='badge-live-stac'>🛰️ LIVE SENTINEL-2 DATA</span>"}
                </div>
                <div style="font-size: 12px; color: #475569; display: flex; flex-wrap: wrap; gap: 16px;">
                    <span>📍 <b style="color: #1e293b;">Location:</b> {region}</span>
                    <span>📐 <b style="color: #1e293b;">Boundary:</b> {boundary_source}</span>
                    <span>🛰️ <b style="color: #1e293b;">Observation:</b> {observation_date}</span>
                    <span>📡 <b style="color: #1e293b;">Constellation:</b> Sentinel-2 MSI Level-2A</span>
                </div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 11px; font-weight: 700; color: #0891b2; letter-spacing: 0.8px;">AI SATELLITE LAKE INTELLIGENCE</div>
                <div style="font-size: 20px; font-weight: 800; color: #0369a1;">AquaTrace</div>
            </div>
        </div>
        """
    )

def render_metric_cards_row(
    water_area_km2: float,
    area_change_pct: Optional[float],
    anomalies_count: int,
    health_score: float,
    health_grade: str,
    hotspot_count: int,
    is_demo: bool = False
):
    """
    Render the 4 primary KPI cards using native Streamlit containers and metrics
    with colourful top accents and clear delta values.
    """
    cols = st.columns(4)

    # 1. Water Surface Area
    with cols[0]:
        with st.container(border=True):
            st.caption("🌊 WATER SURFACE EXTENT")
            delta_str = f"{area_change_pct:+.1f}% vs baseline" if area_change_pct is not None else "Baseline pass"
            delta_color = "normal" if (area_change_pct is not None and area_change_pct >= 0) else ("inverse" if area_change_pct is not None else "off")
            st.metric(
                label="Surface Extent",
                value=f"{water_area_km2:.2f} km²",
                delta=delta_str,
                delta_color=delta_color,
                label_visibility="collapsed"
            )
            if is_demo:
                st.caption("🏷️ :orange[DEMO DATA] • Synthetic MNDWI")
            else:
                st.caption("🛰️ :green[LIVE STAC] • Real Sentinel-2 MNDWI")

    # 2. Lake Health Score
    with cols[1]:
        with st.container(border=True):
            st.caption("🌱 WATER BODY HEALTH SCORE")
            st.metric(
                label="Health Score",
                value=f"{health_score:.1f} / 100",
                delta=f"Grade {health_grade} (Evaluated)",
                delta_color="off",
                label_visibility="collapsed"
            )
            st.caption("⚖️ Multi-criteria decision model")

    # 3. Potential Hotspots
    with cols[2]:
        with st.container(border=True):
            st.caption("🎯 POTENTIAL HOTSPOTS")
            hs_delta = f"{hotspot_count} active cluster(s)" if hotspot_count > 0 else "Nominal / Clear"
            hs_color = "inverse" if hotspot_count > 0 else "off"
            st.metric(
                label="Detected Hotspots",
                value=f"{hotspot_count} sites",
                delta=hs_delta,
                delta_color=hs_color,
                label_visibility="collapsed"
            )
            st.caption("🧪 Spectral DBSCAN clusters")

    # 4. Statistical Anomalies
    with cols[3]:
        with st.container(border=True):
            st.caption("⚡ STATISTICAL DEVIATIONS")
            anom_delta = f"{anomalies_count} deviation(s)" if anomalies_count > 0 else "Nominal series"
            anom_color = "inverse" if anomalies_count > 0 else "off"
            st.metric(
                label="Historical Anomalies",
                value=f"{anomalies_count} flags",
                delta=anom_delta,
                delta_color=anom_color,
                label_visibility="collapsed"
            )
            st.caption("📈 Seasonal Z-score evaluation")

def render_flag_banner(flag_status: str, flag_label: str, message: str = ""):
    """Render automated health status flag banner with colorful gradients and distinct icons."""
    cls_map = {
        "GREEN": "flag-banner-green",
        "YELLOW": "flag-banner-yellow",
        "RED": "flag-banner-red",
        "INSUFFICIENT_DATA": "flag-banner-insufficient"
    }
    banner_cls = cls_map.get(flag_status, "flag-banner-insufficient")
    
    st.html(
        f"""
        <div class="{banner_cls}">
            <div style="font-size: 16px; margin-bottom: 2px;">{flag_label}</div>
            <div style="font-size: 13px; font-weight: 500; opacity: 0.9;">{message}</div>
        </div>
        """
    )

def render_scientific_disclaimer():
    """Render scientific methodology and limitations banner."""
    st.info(
        "ℹ️ **Scientific Methodology & Limitations Notice:** Spectral indicators (NDCI, NDTI, FAI) and unsupervised DBSCAN clusters "
        "reflect optical surface water signatures consistent with photosynthetic pigments or inorganic particulates. They establish "
        "**candidate screening signals** for prioritized environmental monitoring, not confirmed toxic contamination, illegal discharge "
        "culpability, or laboratory-grade chemical certification without in-situ field validation. Catchment terrain routing utilizes "
        "30m Copernicus DEM and does not resolve municipal storm pipes, culverts, or underground drainage. "
        "Simulated scenarios are explicitly labeled as **DEMO DATA**."
    )

def render_executive_summary_card(analysis: dict, waterbody: dict):
    """
    Render executive summary card detailing key ecological changes,
    data limitations, and recommended field next steps for the single dashboard.
    """
    chg = analysis.get("change_metrics") or {}
    pct_chg = chg.get("pct_change", 0.0)
    net_km2 = chg.get("net_change_km2", 0.0)
    hotspots = analysis.get("hotspots") or []
    hs_score = analysis.get("health_score", {}).get("overall_score", 0.0)
    b_meta = analysis.get("base_scene") or {}
    c_meta = analysis.get("comp_scene") or {}
    
    # Dynamics description
    if net_km2 < -1.0:
        extent_text = f"Surface water contracted by **{abs(net_km2):.2f} km²** ({pct_chg:+.1f}%) between the baseline and comparison observation passes."
    elif net_km2 > 1.0:
        extent_text = f"Surface water expanded by **{net_km2:.2f} km²** ({pct_chg:+.1f}%) indicating shoreline inundation or increased reservoir inflow."
    else:
        extent_text = f"Surface water extent remained relatively stable ({pct_chg:+.1f}% change, net {net_km2:+.2f} km²)."

    # Spectral anomaly description
    if hotspots:
        severe_count = sum(1 for h in hotspots if h.get("severity") == "Severe")
        hs_text = f"**{len(hotspots)} spatial anomaly cluster(s)** detected ({severe_count} severe). Primary optical indicator: **{hotspots[0]['indicator_type'].replace('_', ' ')}**."
    else:
        hs_text = "No critical spectral anomalies or algal bloom signatures detected exceeding alert thresholds."

    # Recommended action
    if hotspots:
        top_h = hotspots[0]
        rec_text = f"Dispatch environmental inspection team to coordinates `({top_h['center_lat']:.4f}, {top_h['center_lon']:.4f})` for in-situ Secchi disk depth and chlorophyll-a sampling."
    elif hs_score < 70:
        rec_text = "Continue periodic 5-day Sentinel-2 satellite monitoring to track hydrological retention and seasonal baseline recovery."
    else:
        rec_text = "Water body conditions remain within acceptable historical limits. Standard Sentinel-2 surveillance recommended."

    with st.container(border=True):
        st.markdown("#### 📋 Executive Ecological Assessment & Recommended Actions")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"• **Hydrological Extent:** {extent_text}")
            st.markdown(f"• **Spectral Screening:** {hs_text}")
        with c2:
            st.markdown(f"• **Data Provenance:** Sentinel-2 Level-2A Multi-Spectral Instrument (10m ground resolution, cloud cover ≤ {b_meta.get('cloud_cover', 0.0):.1f}%).")
            st.markdown(f"• **Priority Field Action:** {rec_text}")

def render_workflow_stepper(current_step: int = 1):
    """
    Renders visual step progress bar for the 6-step guided workflow:
    1. Select Water Body
    2. Select Observation Dates
    3. Retrieve Satellite Data
    4. Run Analysis
    5. View Results
    6. Generate Report
    """
    steps = [
        ("1", "Water Body", "🔍"),
        ("2", "Observation Dates", "📅"),
        ("3", "Satellite Data", "🛰️"),
        ("4", "Run Analysis", "⚡"),
        ("5", "View Results", "📊"),
        ("6", "Generate Report", "📄")
    ]

    pills_html = []
    for num_str, title, icon in steps:
        step_num = int(num_str)
        if step_num < current_step:
            cls = "step-pill completed"
            badge = "✓"
        elif step_num == current_step:
            cls = "step-pill active"
            badge = str(step_num)
        else:
            cls = "step-pill pending"
            badge = str(step_num)

        pills_html.append(
            f'<div class="{cls}"><span class="step-num">{badge}</span><span>{icon} {title}</span></div>'
        )

    all_pills = "".join(pills_html)
    st.html(
        f"""
        <div class="workflow-stepper">
            {all_pills}
        </div>
        """
    )

