import os
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image as RLImage
from config import REPORTS_DIR, CACHE_DIR, APP_NAME, APP_TAGLINE, APP_VERSION
from utils.logger import logger
from utils.geo_utils import get_geometry_bbox, parse_geojson
from shapely.geometry import shape, Polygon, MultiPolygon
import numpy as np
from PIL import Image as PILImage, ImageDraw

class ReportService:
    """
    Generates publication-quality environmental intelligence PDF reports
    for Lake Health, Water Change, and Pollution Source Trace analyses,
    including Before and After satellite boundary imagery.
    """

    def _create_satellite_boundary_image(
        self,
        rgb_array: Optional[np.ndarray],
        lake_geom: Optional[Dict[str, Any]],
        bbox: Optional[Tuple[float, float, float, float]],
        label_date: str,
        label_satellite: str = "Sentinel-2 MSI",
        output_size: Tuple[int, int] = (520, 340)
    ) -> Optional[str]:
        """
        Renders genuine satellite imagery overlaid with the verified lake boundary polygon,
        cartographic halo lines, and satellite platform/acquisition metadata badges.
        Returns the saved absolute file path of the PDF-compatible PNG image.
        """
        if rgb_array is None or not isinstance(rgb_array, np.ndarray):
            return None

        w, h = output_size

        # 1. Prepare base satellite RGB image
        try:
            if rgb_array.dtype != np.uint8:
                rgb_uint8 = (np.clip(rgb_array, 0.0, 1.0) * 255).astype(np.uint8)
            else:
                rgb_uint8 = rgb_array

            if rgb_uint8.ndim == 2:
                base_img = PILImage.fromarray(rgb_uint8).convert("RGBA")
            elif rgb_uint8.ndim == 3 and rgb_uint8.shape[2] >= 3:
                base_img = PILImage.fromarray(rgb_uint8[:, :, :3]).convert("RGBA")
            else:
                return None

            base_img = base_img.resize((w, h), PILImage.Resampling.BICUBIC)
        except Exception as e:
            logger.warning(f"Failed to convert satellite array to image: {e}")
            return None

        # 2. Parse lake boundary geometry and determine bounding coordinates
        overlay = PILImage.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        polygons = []
        if lake_geom:
            try:
                geom_parsed = parse_geojson(lake_geom) if isinstance(lake_geom, (str, dict)) else None
                s = shape(geom_parsed or lake_geom)
                if s.geom_type == "Polygon":
                    polygons = [s]
                elif s.geom_type == "MultiPolygon":
                    polygons = list(s.geoms)
                elif s.geom_type == "GeometryCollection":
                    polygons = [g for g in s.geoms if g.geom_type in ("Polygon", "MultiPolygon")]
            except Exception as e_geom:
                logger.debug(f"Could not parse lake boundary shape: {e_geom}")

        # Compute or fallback bbox
        if bbox is None or len(bbox) != 4:
            if polygons:
                from shapely.ops import unary_union
                all_bounds = unary_union(polygons).bounds
                min_lon, min_lat, max_lon, max_lat = all_bounds
            else:
                min_lon, min_lat, max_lon, max_lat = (-1.0, -1.0, 1.0, 1.0)
        else:
            min_lon, min_lat, max_lon, max_lat = bbox

        # Ensure non-zero bbox width/height
        if abs(max_lon - min_lon) < 1e-6:
            max_lon += 0.01
            min_lon -= 0.01
        if abs(max_lat - min_lat) < 1e-6:
            max_lat += 0.01
            min_lat -= 0.01

        def to_xy(lon: float, lat: float) -> Tuple[int, int]:
            x = int(((lon - min_lon) / (max_lon - min_lon)) * (w - 1))
            y = int(((max_lat - lat) / (max_lat - min_lat)) * (h - 1))
            return (max(0, min(w - 1, x)), max(0, min(h - 1, y)))

        # 3. Draw lake boundary polygon with glowing dual-stroke outline
        if polygons:
            for p in polygons:
                ext_pts = [to_xy(x_c, y_c) for x_c, y_c in p.exterior.coords]
                if len(ext_pts) >= 3:
                    # Subtle translucent fill
                    draw.polygon(ext_pts, fill=(0, 229, 255, 35))
                    # Outer dark halo for contrast against bright terrain/clouds
                    draw.line(ext_pts, fill=(15, 23, 42, 230), width=4)
                    # Core vibrant cyan boundary
                    draw.line(ext_pts, fill=(0, 229, 255, 255), width=2)

                # Interior rings (islands)
                for interior in p.interiors:
                    int_pts = [to_xy(x_c, y_c) for x_c, y_c in interior.coords]
                    if len(int_pts) >= 3:
                        draw.line(int_pts, fill=(15, 23, 42, 230), width=4)
                        draw.line(int_pts, fill=(0, 229, 255, 255), width=2)

        # 4. Corner badges and cartographic annotations
        badge_text = f"OBS: {label_date} | {label_satellite}"
        draw.rectangle([6, 6, 260, 24], fill=(15, 23, 42, 200), outline=(56, 189, 248, 180), width=1)
        draw.text((12, 9), badge_text, fill=(241, 245, 249, 255))

        # Legend pill at bottom-right
        draw.rectangle([w - 170, h - 24, w - 6, h - 6], fill=(15, 23, 42, 200), outline=(56, 189, 248, 180), width=1)
        draw.line([(w - 162, h - 15), (w - 140, h - 15)], fill=(0, 229, 255, 255), width=2)
        draw.text((w - 134, h - 20), "Monitored Boundary", fill=(241, 245, 249, 255))

        # 5. Composite and save
        try:
            composite = PILImage.alpha_composite(base_img, overlay).convert("RGB")
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            out_path = CACHE_DIR / f"sat_boundary_{timestamp}.png"
            composite.save(out_path, format="PNG")
            return str(out_path)
        except Exception as e_save:
            logger.warning(f"Failed to save composite satellite boundary image: {e_save}")
            return None

    def _create_unavailable_cell(
        self,
        title: str,
        date_str: str,
        reason: str,
        width: int = 255,
        height: int = 165
    ) -> Table:
        """
        Creates a clean, styled callout cell when genuine satellite imagery is unavailable,
        guaranteeing that fake or simulated imagery is never displayed.
        """
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "UnavailHdr",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#b45309"),
            fontName="Helvetica-Bold"
        )
        msg_style = ParagraphStyle(
            "UnavailMsg",
            parent=styles["Normal"],
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#475569")
        )
        note_style = ParagraphStyle(
            "UnavailNote",
            parent=styles["Normal"],
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#64748b"),
            fontName="Helvetica-Oblique"
        )

        flowables = [
            Paragraph(f"<b>⚠️ {title}</b>", title_style),
            Spacer(1, 4),
            Paragraph(f"<b>Observation Date:</b> {date_str}", msg_style),
            Spacer(1, 3),
            Paragraph(f"<b>Status:</b> {reason}", msg_style),
            Spacer(1, 6),
            Paragraph("AquaTrace adheres strictly to Earth observation integrity and excludes synthetic or unverified rasters from official imagery audits.", note_style)
        ]

        t_box = Table([[flowables]], colWidths=[width], rowHeights=[height])
        t_box.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        return t_box

    def generate_pdf_report(
        self,
        lake_data: Dict[str, Any],
        analysis_data: Dict[str, Any],
        hotspots: List[Dict[str, Any]],
        source_trace: Optional[Dict[str, Any]] = None,
        health_score: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a complete PDF report and return the saved absolute file path.
        Includes Before and After genuine satellite boundary imagery.
        """
        lake_name = lake_data.get("name", "Unknown Lake").replace(" ", "_")
        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"AquaTrace_Report_{lake_name}_{timestamp_str}.pdf"
        output_path = REPORTS_DIR / filename

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40
        )

        styles = getSampleStyleSheet()
        # Custom styles
        primary_color = colors.HexColor("#0f172a")  # Dark slate
        accent_color = colors.HexColor("#0284c7")   # Deep cyan
        text_color = colors.HexColor("#1e293b")

        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=22,
            leading=26,
            textColor=primary_color,
            spaceAfter=4
        )
        subtitle_style = ParagraphStyle(
            "DocSubtitle",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=accent_color,
            spaceAfter=15
        )
        section_style = ParagraphStyle(
            "SectionHeader",
            parent=styles["Heading2"],
            fontSize=13,
            leading=16,
            textColor=primary_color,
            spaceBefore=12,
            spaceAfter=6
        )
        body_style = ParagraphStyle(
            "BodyDark",
            parent=styles["Normal"],
            fontSize=9,
            leading=13,
            textColor=text_color
        )
        caption_style = ParagraphStyle(
            "ImgCaption",
            parent=styles["Normal"],
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#334155")
        )
        table_hdr_style = ParagraphStyle(
            "TableHdr",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.whitesmoke,
            fontName="Helvetica-Bold"
        )

        story = []

        # 1. Header Banner
        story.append(Paragraph(f"<b>{APP_NAME}</b> — Environmental Intelligence Report", title_style))
        story.append(Paragraph(f"<i>“{APP_TAGLINE}”</i> | Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M UTC')}", subtitle_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=accent_color, spaceBefore=0, spaceAfter=12))

        # 2. Executive Summary / Lake Profile
        story.append(Paragraph("1. Lake & Observation Profile", section_style))
        lake_meta = [
            [
                Paragraph("<b>Water Body Name:</b>", body_style), Paragraph(lake_data.get("name", "N/A"), body_style),
                Paragraph("<b>Classification Type:</b>", body_style), Paragraph(lake_data.get("type", "Lake"), body_style)
            ],
            [
                Paragraph("<b>Region / Location:</b>", body_style), Paragraph(f"{lake_data.get('region', '')}, {lake_data.get('country', '')}", body_style),
                Paragraph("<b>Boundary Source:</b>", body_style), Paragraph(lake_data.get("boundary_source", "OpenStreetMap Verified"), body_style)
            ],
            [
                Paragraph("<b>Center Lat/Lon:</b>", body_style), Paragraph(f"{lake_data.get('centroid_lat', 0):.4f}, {lake_data.get('centroid_lon', 0):.4f}", body_style),
                Paragraph("<b>Typical Surface Area:</b>", body_style), Paragraph(f"{lake_data.get('typical_area_km2', 'N/A')} km²", body_style)
            ],
            [
                Paragraph("<b>Baseline Observation:</b>", body_style), Paragraph(str(analysis_data.get("baseline_date", "N/A")), body_style),
                Paragraph("<b>Comparison Observation:</b>", body_style), Paragraph(str(analysis_data.get("comparison_date", "Single Observation")), body_style)
            ],
            [
                Paragraph("<b>Satellite Platform:</b>", body_style), Paragraph("Sentinel-2 MSI Level-2A", body_style),
                Paragraph("<b>Data Status:</b>", body_style), Paragraph("DEMO DATA (Simulated)" if analysis_data.get("is_demo") else "LIVE STAC (AWS Earth Search)", body_style)
            ]
        ]
        t_meta = Table(lake_meta, colWidths=[110, 150, 110, 160])
        t_meta.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t_meta)
        story.append(Spacer(1, 10))

        # -----------------------------------------------------------------
        # 3. Before and After Satellite Boundary Images (Feature)
        # -----------------------------------------------------------------
        lake_geom = lake_data.get("boundary")
        if not lake_geom and "boundary_geojson" in lake_data:
            lake_geom = parse_geojson(lake_data["boundary_geojson"])
        if not lake_geom and "boundary" in analysis_data:
            lake_geom = analysis_data["boundary"]

        bbox = None
        if lake_geom:
            try:
                bbox = get_geometry_bbox(lake_geom)
            except Exception:
                bbox = None
        if not bbox:
            c_lat = lake_data.get("centroid_lat", 0.0)
            c_lon = lake_data.get("centroid_lon", 0.0)
            if c_lat != 0.0 or c_lon != 0.0:
                bbox = (c_lon - 0.03, c_lat - 0.03, c_lon + 0.03, c_lat + 0.03)

        # Baseline (Before) Observation Details
        base_bands = analysis_data.get("base_bands") or {}
        base_scene = analysis_data.get("base_scene") or {}
        base_rgb = base_bands.get("REAL_RGB")
        base_date = analysis_data.get("baseline_date") or base_scene.get("date_str") or "Baseline"
        base_satellite = base_scene.get("satellite", "Sentinel-2 MSI Level-2A")
        base_cloud = base_scene.get("cloud_cover")
        base_acq_str = base_scene.get("date_str", str(base_date))

        # Lazy retrieval if scene is live but bands were not pre-cached
        if base_rgb is None and not analysis_data.get("is_demo") and not base_scene.get("is_demo") and base_scene and bbox:
            try:
                from services.satellite_service import satellite_service
                b_fetch = satellite_service.fetch_scene_bands(base_scene, bbox, grid_size=(160, 160), lake_polygon=lake_geom)
                base_rgb = b_fetch.get("REAL_RGB")
            except Exception as e_b_fetch:
                logger.debug(f"Could not lazily fetch baseline satellite image: {e_b_fetch}")

        # Comparison (After) Observation Details
        comp_bands = analysis_data.get("comp_bands") or {}
        comp_scene = analysis_data.get("comp_scene") or {}
        comp_rgb = comp_bands.get("REAL_RGB") if comp_bands else None
        comp_date = analysis_data.get("comparison_date") or (comp_scene.get("date_str") if comp_scene else None)
        comp_satellite = comp_scene.get("satellite", "Sentinel-2 MSI Level-2A") if comp_scene else "Sentinel-2 MSI Level-2A"
        comp_cloud = comp_scene.get("cloud_cover") if comp_scene else None
        comp_acq_str = comp_scene.get("date_str", str(comp_date)) if comp_scene else (str(comp_date) if comp_date else "N/A")

        if comp_rgb is None and not analysis_data.get("is_demo") and comp_scene and not comp_scene.get("is_demo") and bbox:
            try:
                from services.satellite_service import satellite_service
                c_fetch = satellite_service.fetch_scene_bands(comp_scene, bbox, grid_size=(160, 160), lake_polygon=lake_geom)
                comp_rgb = c_fetch.get("REAL_RGB")
            except Exception as e_c_fetch:
                logger.debug(f"Could not lazily fetch comparison satellite image: {e_c_fetch}")

        story.append(Paragraph("2. Multi-Temporal Satellite Boundary Imagery (Before & After)", section_style))
        story.append(Paragraph(
            "Synchronized observation panels featuring genuine Sentinel-2 Level-2A satellite reflectance imagery for the evaluated acquisition passes. "
            "The verified water body boundary is delineated with high-contrast dual-stroke cyan cartography to enable visual cross-examination of shoreline shifts.",
            body_style
        ))
        story.append(Spacer(1, 4))

        # Generate Before & After Satellite Boundary Images
        before_img_path = self._create_satellite_boundary_image(
            rgb_array=base_rgb,
            lake_geom=lake_geom,
            bbox=bbox,
            label_date=str(base_date),
            label_satellite=base_satellite,
            output_size=(520, 340)
        )
        after_img_path = self._create_satellite_boundary_image(
            rgb_array=comp_rgb,
            lake_geom=lake_geom,
            bbox=bbox,
            label_date=str(comp_date) if comp_date else "N/A",
            label_satellite=comp_satellite,
            output_size=(520, 340)
        )

        # Before Cell Construction
        if before_img_path and os.path.exists(before_img_path):
            before_cell = [RLImage(before_img_path, width=255, height=165)]
            cloud_txt = f"{base_cloud:.1f}%" if base_cloud is not None else "Clear"
            caption_b = Paragraph(
                f"<b>Before Image (Baseline Pass)</b><br/>"
                f"📅 Acquisition: <b>{base_acq_str}</b> | ☁️ Cloud: <b>{cloud_txt}</b><br/>"
                f"🛰️ Platform: <b>{base_satellite}</b> | 🔍 Outline: <b>Lake Boundary (Cyan)</b>",
                caption_style
            )
        else:
            reason_b = "Demonstration / Simulation Mode Active. Synthetic spectral approximations are excluded from the official imagery record." if analysis_data.get("is_demo") else "Live STAC satellite imagery asset could not be retrieved from provider endpoints for this observation pass."
            before_cell = [self._create_unavailable_cell(
                title="Satellite Imagery Unavailable",
                date_str=str(base_date),
                reason=reason_b,
                width=255,
                height=165
            )]
            caption_b = Paragraph(f"<b>Before Pass:</b> {base_date} | Platform: {base_satellite}", caption_style)

        # After Cell Construction
        if after_img_path and os.path.exists(after_img_path):
            after_cell = [RLImage(after_img_path, width=255, height=165)]
            cloud_txt = f"{comp_cloud:.1f}%" if comp_cloud is not None else "Clear"
            caption_a = Paragraph(
                f"<b>After Image (Comparison Pass)</b><br/>"
                f"📅 Acquisition: <b>{comp_acq_str}</b> | ☁️ Cloud: <b>{cloud_txt}</b><br/>"
                f"🛰️ Platform: <b>{comp_satellite}</b> | 🔍 Outline: <b>Lake Boundary (Cyan)</b>",
                caption_style
            )
        else:
            if not comp_date or comp_date == "Single Observation":
                reason_a = "Single observation evaluation mode active. To view comparative Before/After satellite boundary imagery, select two distinct observation dates in the AquaTrace analysis panel."
            elif analysis_data.get("is_demo"):
                reason_a = "Demonstration / Simulation Mode Active. Synthetic spectral approximations are excluded from the official imagery record."
            else:
                reason_a = f"Live STAC satellite imagery asset could not be retrieved from provider endpoints for comparison pass ({comp_date})."
            after_cell = [self._create_unavailable_cell(
                title="Satellite Imagery Unavailable",
                date_str=str(comp_date) if comp_date else "Single Observation",
                reason=reason_a,
                width=255,
                height=165
            )]
            caption_a = Paragraph(f"<b>After Pass:</b> {comp_date or 'Single Observation'} | Platform: {comp_satellite}", caption_style)

        image_table = Table(
            [
                [before_cell, after_cell],
                [caption_b, caption_a]
            ],
            colWidths=[260, 260]
        )
        image_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        story.append(image_table)
        story.append(Spacer(1, 4))

        # Map Legend Bar
        legend_data = [
            [
                Paragraph("<b>Map Legend:</b>", body_style),
                Paragraph("<font color='#00e5ff'><b>━━━</b></font> Verified Boundary Outline", body_style),
                Paragraph("<font color='#0284c7'><b>■</b></font> Sentinel-2 MSI True-Color", body_style),
                Paragraph(f"<b>Map Extent:</b> Synchronized BBox", body_style)
            ]
        ]
        t_legend = Table(legend_data, colWidths=[90, 150, 150, 130])
        t_legend.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t_legend)
        story.append(Spacer(1, 10))

        # 4. Water Surface Area & Change Dynamics
        story.append(Paragraph("3. Water Surface Area & Dynamics", section_style))
        b_area = analysis_data.get("baseline_water_area_km2", 0.0)
        c_area = analysis_data.get("comparison_water_area_km2")
        chg_km2 = analysis_data.get("water_area_change_km2")
        chg_pct = analysis_data.get("water_area_change_pct")

        water_table_data = [
            [Paragraph("Metric", table_hdr_style), Paragraph("Value", table_hdr_style), Paragraph("Interpretation", table_hdr_style)],
            [Paragraph("Baseline Water Area", body_style), Paragraph(f"{b_area:.2f} km²", body_style), Paragraph("Reference surface extent observed by Sentinel-2 MNDWI", body_style)],
            [Paragraph("Comparison Water Area", body_style), Paragraph(f"{c_area:.2f} km²" if c_area is not None else "N/A", body_style), Paragraph("Target observation surface extent", body_style)],
            [Paragraph("Net Area Change", body_style), Paragraph(f"{chg_km2:+.2f} km² ({chg_pct:+.1f}%)" if chg_km2 is not None else "N/A", body_style), Paragraph("Absolute and percentage water body boundary shift", body_style)],
        ]
        t_water = Table(water_table_data, colWidths=[140, 110, 280])
        t_water.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), primary_color),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t_water)
        story.append(Spacer(1, 10))

        # 5. Lake Health Score
        if health_score:
            story.append(Paragraph("4. Transparent Lake Health Score", section_style))
            hs_val = health_score.get("overall_score", 0.0)
            hs_grade = health_score.get("letter_grade", "N/A")
            hs_interp = health_score.get("interpretation", "")
            
            story.append(Paragraph(f"<b>Overall Score: {hs_val} / 100</b> (Grade: <b>{hs_grade}</b>) | Data Completeness: {health_score.get('data_completeness_pct', 100)}%", body_style))
            story.append(Paragraph(f"<i>{hs_interp}</i>", body_style))
            story.append(Spacer(1, 6))

            hs_rows = [[Paragraph("Component", table_hdr_style), Paragraph("Weight", table_hdr_style), Paragraph("Score", table_hdr_style), Paragraph("Status", table_hdr_style)]]
            for comp in health_score.get("components", {}).values():
                hs_rows.append([
                    Paragraph(comp.get("name", ""), body_style),
                    Paragraph(f"{int(comp.get('weight', 0)*100)}%", body_style),
                    Paragraph(f"{comp.get('score', 0):.1f}", body_style),
                    Paragraph(comp.get("status", ""), body_style),
                ])
            t_hs = Table(hs_rows, colWidths=[170, 70, 70, 220])
            t_hs.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), accent_color),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))
            story.append(t_hs)
            story.append(Spacer(1, 10))

        # 6. Detected Pollution Hotspots
        story.append(Paragraph("5. AI-Assisted Potential Hotspots", section_style))
        if hotspots:
            hs_table = [[Paragraph("ID", table_hdr_style), Paragraph("Signal Type", table_hdr_style), Paragraph("Location", table_hdr_style), Paragraph("Area (ha)", table_hdr_style), Paragraph("Max Value", table_hdr_style), Paragraph("Severity", table_hdr_style), Paragraph("Priority", table_hdr_style)]]
            for h in hotspots[:6]:
                hs_table.append([
                    Paragraph(h.get("hotspot_id", ""), body_style),
                    Paragraph(h.get("indicator_type", "").replace("_", " "), body_style),
                    Paragraph(f"{h.get('center_lat', 0):.4f}, {h.get('center_lon', 0):.4f}", body_style),
                    Paragraph(f"{h.get('area_ha', 0):.1f}", body_style),
                    Paragraph(f"{h.get('max_val', 0):.3f}", body_style),
                    Paragraph(h.get("severity", ""), body_style),
                    Paragraph(f"<b>{h.get('inspection_priority', '')}</b>", body_style),
                ])
            t_hs_list = Table(hs_table, colWidths=[70, 110, 100, 60, 60, 60, 70])
            t_hs_list.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), primary_color),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))
            story.append(t_hs_list)
        else:
            story.append(Paragraph("No anomalous spectral clusters detected exceeding current severity thresholds.", body_style))
        story.append(Spacer(1, 10))

        # 7. Pollution Source Trace (Signature Feature)
        if source_trace:
            story.append(Paragraph("6. Signature Feature: Pollution Source Trace", section_style))
            story.append(Paragraph(f"<b>Target Hotspot:</b> {source_trace.get('hotspot_id')} | <b>Method:</b> {source_trace.get('terrain_method')}", body_style))
            story.append(Paragraph(f"<b>Shoreline Entry Point:</b> Lat {source_trace.get('candidate_entry_lat', 0):.5f}, Lon {source_trace.get('candidate_entry_lon', 0):.5f} | <b>Catchment Area:</b> {source_trace.get('contributing_area_km2', 0)} km²", body_style))
            story.append(Spacer(1, 4))

            st_summary = [
                [
                    Paragraph("<b>Primary Pressure:</b>", body_style), Paragraph(str(source_trace.get("primary_source_pressure")), body_style),
                    Paragraph("<b>Land Cover:</b>", body_style), Paragraph(f"Built: {source_trace.get('built_up_pct')}% | Agri: {source_trace.get('agriculture_pct')}% | Soil: {source_trace.get('bare_soil_pct')}%", body_style)
                ]
            ]
            t_st = Table(st_summary, colWidths=[110, 160, 90, 170])
            t_st.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(t_st)
            story.append(Spacer(1, 6))

            story.append(Paragraph("<b>Recommended Field Inspection Actions:</b>", body_style))
            for rec in source_trace.get("inspection_recommendations", []):
                story.append(Paragraph(f"• <b>{rec.get('title')}</b> ({rec.get('location')}): {rec.get('action')}", body_style))
            story.append(Spacer(1, 8))

        # 8. Scientific Limitations & Legal Disclaimer
        story.append(Paragraph("7. Scientific Limitations & Regulatory Disclaimer", section_style))
        disclaimer_text = (
            "AquaTrace is an automated Earth observation decision-support tool. Spectral indicators (NDCI, NDTI, FAI) "
            "represent optical absorption and reflectance characteristics consistent with photosynthetic pigments or inorganic particles; "
            "they do not establish certified chemical identification, industrial discharge culpability, or regulatory compliance without "
            "accredited in-situ grab sampling and laboratory verification. D8 terrain catchments are derived from 30m Copernicus DEM "
            "and do not map subsurface stormwater pipes, culverts, or municipal infrastructure."
        )
        story.append(Paragraph(disclaimer_text, ParagraphStyle("Disc", parent=body_style, fontSize=7.5, leading=10, textColor=colors.HexColor("#64748b"))))

        # Build Document
        doc.build(story)
        logger.info(f"PDF Report generated successfully: {output_path}")
        return str(output_path)

report_service = ReportService()

