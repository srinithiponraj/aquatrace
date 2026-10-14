import os
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from config import REPORTS_DIR, APP_NAME, APP_TAGLINE, APP_VERSION
from utils.logger import logger

class ReportService:
    """
    Generates publication-quality environmental intelligence PDF reports
    for Lake Health, Water Change, and Pollution Source Trace analyses.
    """

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

        # 3. Water Surface Area & Change Dynamics
        story.append(Paragraph("2. Water Surface Area & Dynamics", section_style))
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

        # 4. Lake Health Score
        if health_score:
            story.append(Paragraph("3. Transparent Lake Health Score", section_style))
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

        # 5. Detected Pollution Hotspots
        story.append(Paragraph("4. AI-Assisted Potential Hotspots", section_style))
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

        # 6. Pollution Source Trace (Signature Feature)
        if source_trace:
            story.append(Paragraph("5. Signature Feature: Pollution Source Trace", section_style))
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

        # 7. Scientific Limitations & Legal Disclaimer
        story.append(Paragraph("6. Scientific Limitations & Regulatory Disclaimer", section_style))
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
