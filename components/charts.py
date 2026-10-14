import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from typing import Dict, Any, List, Optional

def render_surface_water_transition_chart(
    change_metrics: Dict[str, Any],
    title: str = "Surface Water Transition",
    height: int = 320
) -> None:
    """
    Renders a clear categorical surface-water transition donut chart showing:
    - Water Gained (non-water before -> water after)
    - Water Lost (water before -> non-water after)
    - Stable Water (water on both dates)
    - Unobserved / Invalid (clouds or invalid data reported separately)
    """
    if not change_metrics:
        st.info("No change detection metrics available.")
        return

    stable_km2 = change_metrics.get("stable_water_km2", 0.0)
    loss_km2 = change_metrics.get("water_loss_km2", 0.0)
    gain_km2 = change_metrics.get("water_gain_km2", 0.0)
    invalid_km2 = change_metrics.get("invalid_area_km2", 0.0)
    valid_pct = change_metrics.get("valid_observation_pct", 100.0)

    # Calculate total evaluated area for transition dynamics
    water_dynamics_total = stable_km2 + loss_km2 + gain_km2
    total_area_evaluated = water_dynamics_total + (invalid_km2 if invalid_km2 > 0 else 0.0)

    if total_area_evaluated <= 0:
        st.warning("No water-covered or valid pixels identified in either observation.")
        return

    categories = [
        {
            "Category": "Stable Water",
            "Area (km²)": stable_km2,
            "Percentage": round((stable_km2 / total_area_evaluated) * 100.0, 1) if total_area_evaluated > 0 else 0.0,
            "Description": "Persistent surface water present on both satellite dates"
        },
        {
            "Category": "Water Lost",
            "Area (km²)": loss_km2,
            "Percentage": round((loss_km2 / total_area_evaluated) * 100.0, 1) if total_area_evaluated > 0 else 0.0,
            "Description": "Receded water / contracted shoreline since baseline"
        },
        {
            "Category": "Water Gained",
            "Area (km²)": gain_km2,
            "Percentage": round((gain_km2 / total_area_evaluated) * 100.0, 1) if total_area_evaluated > 0 else 0.0,
            "Description": "Inundated land / expanded water since baseline"
        }
    ]

    if invalid_km2 > 0.01:
        categories.append({
            "Category": "Unobserved / Invalid",
            "Area (km²)": invalid_km2,
            "Percentage": round((invalid_km2 / total_area_evaluated) * 100.0, 1) if total_area_evaluated > 0 else 0.0,
            "Description": "Cloud-covered or no-data pixels excluded from valid water mask"
        })

    chart_data = pd.DataFrame(categories)

    color_map = {
        "Stable Water": "#38bdf8",         # Electric Sky Blue
        "Water Lost": "#f43f5e",           # Vivid Rose/Crimson
        "Water Gained": "#10b981",         # Emerald Green
        "Unobserved / Invalid": "#64748b"  # Slate Gray
    }

    fig = go.Figure(data=[go.Pie(
        labels=chart_data["Category"],
        values=chart_data["Area (km²)"],
        hole=0.55,
        marker=dict(
            colors=[color_map[c] for c in chart_data["Category"]],
            line=dict(color="#ffffff", width=2)
        ),
        textinfo="label+percent",
        texttemplate="<b>%{label}</b><br>%{value:.2f} km²<br>(%{percent})",
        hovertemplate="<b>%{label}</b><br>Area: %{value:.2f} km²<br>Proportion: %{percent}<br><extra></extra>",
        insidetextorientation="horizontal"
    )])

    net_chg = change_metrics.get("net_change_km2", 0.0)
    net_pct = change_metrics.get("pct_change", 0.0)
    net_sign = "+" if net_chg >= 0 else ""

    fig.update_layout(
        title=dict(
            text=f"<b>{title}</b>",
            font=dict(size=15, color="#0f172a"),
            x=0.0
        ),
        template="plotly_white",
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(255,255,255,0)",
        font=dict(color="#0f172a", family="Plus Jakarta Sans, sans-serif"),
        height=height,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.25,
            xanchor="center",
            x=0.5,
            font=dict(size=11, color="#334155")
        ),
        annotations=[
            dict(
                text=f"<b>Net Delta</b><br><span style='font-size:14px;color:{'#10b981' if net_chg>=0 else '#e11d48'}'>{net_sign}{net_chg:.2f} km²</span><br><span style='font-size:11px;color:#64748b;'>({net_sign}{net_pct:.1f}%)</span>",
                x=0.5, y=0.5,
                font=dict(size=12, color="#0f172a"),
                showarrow=False
            )
        ]
    )

    st.plotly_chart(fig, use_container_width=True)

    # Report unobserved / cloud area separately as required
    unobserved_pct = round(100.0 - valid_pct, 1)
    if unobserved_pct > 0.5:
        st.caption(f"☁️ **Unobserved Surface:** {unobserved_pct}% of scene pixels obscured by cloud cover or nodata. Transition percentages reflect valid comparable surface only.")

def render_historical_extent_chart(
    hist_records: List[Dict[str, Any]],
    lake_name: str = "Water Body",
    height: int = 240
) -> None:
    """
    Renders the historical water extent time-series strictly from valid observed measurements.
    Distinguishes single observations, avoids interpolating missing dates, and handles
    zero-area baselines without mathematical errors.
    """
    if not hist_records:
        st.info("ℹ️ Insufficient historical observations to display trend. Search additional dates in Step 3.")
        return

    # Filter out empty or missing dates
    valid_obs = [r for r in hist_records if r.get("date") and r.get("water_area_km2") is not None]
    if not valid_obs:
        st.info("ℹ️ Insufficient historical observations to display trend.")
        return

    # Sort strictly chronologically
    valid_obs.sort(key=lambda x: str(x["date"]))

    df = pd.DataFrame(valid_obs)
    df["date"] = pd.to_datetime(df["date"])

    if len(df) == 1:
        # Single observation - show point with value callout
        single_date = df.iloc[0]["date"].strftime("%Y-%m-%d")
        single_area = df.iloc[0]["water_area_km2"]
        st.info(f"📅 **Single Valid Observation Recorded:** `{single_date}` with water surface area **{single_area:.2f} km²**.")
        st.caption("Select a second distinct observation pass in Step 3 to view comparative change trend.")
        return

    fig = px.line(
        df,
        x="date",
        y="water_area_km2",
        markers=True,
        labels={"water_area_km2": "Water Area (km²)", "date": "Observation Date"},
        title="<b>Historical Water Extent Trend</b>"
    )

    fig.update_traces(
        line=dict(color="#0284c7", width=3),
        marker=dict(size=9, color="#0891b2", line=dict(color="#ffffff", width=1.5)),
        hovertemplate="<b>Date:</b> %{x|%Y-%m-%d}<br><b>Extent:</b> %{y:.2f} km²<extra></extra>"
    )

    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(255,255,255,0)",
        font=dict(color="#0f172a", family="Plus Jakarta Sans, sans-serif"),
        margin=dict(l=10, r=10, t=35, b=10),
        height=height,
        xaxis=dict(
            showgrid=True,
            gridcolor="#e2e8f0",
            title=dict(text="Actual Satellite Acquisition Date", font=dict(size=11, color="#64748b"))
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#e2e8f0",
            title=dict(text="Area (km²)", font=dict(size=11, color="#64748b"))
        )
    )

    st.plotly_chart(fig, use_container_width=True)

    # Show net change between first and last chronological observation
    first_area = df.iloc[0]["water_area_km2"]
    last_area = df.iloc[-1]["water_area_km2"]
    net_diff = round(last_area - first_area, 2)
    pct_diff = round((net_diff / first_area * 100.0), 1) if first_area > 0 else 0.0
    sign = "+" if net_diff >= 0 else ""

    st.caption(
        f"📊 **Observed Period Shift:** {df.iloc[0]['date'].strftime('%b %d, %Y')} to {df.iloc[-1]['date'].strftime('%b %d, %Y')} "
        f"— Net change: **{sign}{net_diff} km²** ({sign}{pct_diff}%)"
    )
