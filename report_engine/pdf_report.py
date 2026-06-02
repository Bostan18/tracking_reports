"""Génération du PDF d'analyse, brandé Comafrique (gauche) + client (droite)."""
import io
import os
from datetime import datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table,
    TableStyle, Image as RLImage,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from . import charts

NAVY = colors.HexColor("#003366")
BLUE = colors.HexColor("#2E6DA4")
LIGHT = colors.HexColor("#EAF0F6")
GREY = colors.HexColor("#7F8C8D")
RED = colors.HexColor("#C0392B")

ASSETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("H1b", parent=ss["Heading1"], textColor=NAVY,
                          fontName="Helvetica-Bold", fontSize=16, spaceAfter=4))
    ss.add(ParagraphStyle("H2b", parent=ss["Heading2"], textColor=BLUE,
                          fontName="Helvetica-Bold", fontSize=12, spaceBefore=10, spaceAfter=6))
    ss.add(ParagraphStyle("Body", parent=ss["Normal"], fontSize=9.5, leading=13))
    ss.add(ParagraphStyle("Small", parent=ss["Normal"], fontSize=8, textColor=GREY))
    ss.add(ParagraphStyle("KpiVal", parent=ss["Normal"], fontName="Helvetica-Bold",
                          fontSize=17, leading=20, textColor=NAVY, alignment=TA_CENTER))
    ss.add(ParagraphStyle("KpiLbl", parent=ss["Normal"], fontSize=7.5, leading=9,
                          textColor=GREY, alignment=TA_CENTER))
    return ss


class _Doc(BaseDocTemplate):
    def __init__(self, buf, meta, logo_left, logo_right, title="RAPPORT D'ANALYSE — TRAJETS", **kw):
        super().__init__(buf, pagesize=A4, topMargin=32 * mm,
                         bottomMargin=18 * mm, leftMargin=15 * mm, rightMargin=15 * mm, **kw)
        self.meta = meta
        self.logo_left = logo_left
        self.logo_right = logo_right
        self.header_title = title
        frame = Frame(self.leftMargin, self.bottomMargin,
                      self.width, self.height, id="main")
        self.addPageTemplates([PageTemplate(id="all", frames=[frame],
                                            onPage=self._header_footer)])

    def _header_footer(self, canvas, doc):
        canvas.saveState()
        w, h = A4
        # bandeau haut
        canvas.setFillColor(NAVY)
        canvas.rect(0, h - 26 * mm, w, 26 * mm, fill=1, stroke=0)
        # logos
        def draw_logo(path, x_left):
            if path and os.path.exists(path):
                from reportlab.lib.utils import ImageReader
                img = ImageReader(path)
                iw, ih = img.getSize()
                target_h = 14 * mm
                target_w = target_h * iw / ih
                y = h - 26 * mm + (26 * mm - target_h) / 2
                x = x_left if x_left is not None else (w - 15 * mm - target_w)
                canvas.drawImage(path, x, y, width=target_w, height=target_h,
                                 mask="auto", preserveAspectRatio=True)
        draw_logo(self.logo_left, 15 * mm)
        draw_logo(self.logo_right, None)
        # titre centre
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawCentredString(w / 2, h - 13 * mm, self.header_title)
        canvas.setFont("Helvetica", 8)
        canvas.drawCentredString(w / 2, h - 18 * mm,
                                 f"{self.meta.get('client','')}  •  Comafrique Technologies")
        # footer
        canvas.setFillColor(GREY)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(15 * mm, 10 * mm,
                          f"Généré le {datetime.now():%d/%m/%Y %H:%M} — Comafrique Technologies / Support Tracking")
        canvas.drawRightString(w - 15 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()


def _kpi_grid(kpis, ss):
    cells = [
        (f"{kpis['n_trips']:,}".replace(",", " "), "Trajets"),
        (f"{kpis['total_distance']:,.0f}".replace(",", " ") + " km", "Distance totale"),
        (f"{kpis['total_duration_h']:,.0f}".replace(",", " ") + " h", "Durée de conduite"),
        (str(kpis["n_vehicles"]), "Véhicules actifs"),
        (f"{kpis['avg_distance']} km", "Distance moy./trajet"),
        (f"{kpis['avg_km_per_vehicle']:,.0f}".replace(",", " ") + " km", "Km moy./véhicule"),
        (f"{kpis['max_speed_fleet']} km/h", "Vitesse max flotte"),
        (f"{kpis['avg_max_speed']} km/h", "Vitesse max moy."),
    ]
    data = []
    row = []
    for i, (val, lbl) in enumerate(cells):
        cell = [Paragraph(val, ss["KpiVal"]), Spacer(1, 3), Paragraph(lbl, ss["KpiLbl"])]
        row.append(cell)
        if len(row) == 4:
            data.append(row)
            row = []
    if row:
        while len(row) < 4:
            row.append("")
        data.append(row)
    t = Table(data, colWidths=[44 * mm] * 4, rowHeights=[19 * mm] * len(data))
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 3, colors.white),
        ("INNERGRID", (0, 0), (-1, -1), 6, colors.white),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


def _alert_box(kpis, ss):
    txt = (f"<b>Alertes sécurité.</b> {kpis['n_speeding']} trajet(s) avec dépassement "
           f"du seuil de {kpis['speed_threshold']} km/h ({kpis['pct_speeding']}% des trajets) — "
           f"vitesse max relevée : {kpis['max_speed_fleet']} km/h. "
           f"{kpis['n_night']} trajet(s) de nuit ({kpis['night_window']}, {kpis['pct_night']}%).")
    t = Table([[Paragraph(txt, ss["Body"])]], colWidths=[176 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FDECEA")),
        ("BOX", (0, 0), (-1, -1), 0.5, RED),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def _df_table(df, ss, max_rows=20, col_widths=None):
    df = df.head(max_rows)
    header = list(df.columns)
    data = [[Paragraph(f"<b>{h}</b>", ss["Small"]) for h in header]]
    for _, r in df.iterrows():
        line = []
        for v in r:
            if v is None or (isinstance(v, float) and pd.isna(v)):
                v = "—"
            elif isinstance(v, float):
                v = f"{v:,.1f}".replace(",", " ")
            line.append(Paragraph(str(v), ss["Small"]))
        data.append(line)
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def build_pdf(result, meta, logo_left=None, logo_right=None) -> bytes:
    """Construit le PDF et renvoie les bytes."""
    if logo_left is None:
        logo_left = os.path.join(ASSETS, "logo_comafrique.png")
    if logo_right is None:
        logo_right = os.path.join(ASSETS, "logo_client_placeholder.png")

    buf = io.BytesIO()
    ss = _styles()
    doc = _Doc(buf, meta, logo_left, logo_right)
    k = result["kpis"]
    story = []

    # --- Synthèse ---
    story.append(Paragraph(f"Synthèse — {k['client']}", ss["H1b"]))
    story.append(Paragraph(
        f"Période : <b>{meta.get('period_start','?')} → {meta.get('period_end','?')}</b> "
        f"({k['n_days']} jours d'activité)  •  Flotte suivie : <b>{k['n_vehicles']} véhicules</b>  •  "
        f"Moyenne de <b>{k['avg_trips_per_vehicle']} trajets/véhicule</b>.", ss["Body"]))
    story.append(Spacer(1, 8))
    story.append(_kpi_grid(k, ss))
    story.append(Spacer(1, 10))
    story.append(_alert_box(k, ss))
    story.append(Spacer(1, 12))

    # Lecture analytique
    story.append(Paragraph("Lecture analytique", ss["H2b"]))
    story.append(Paragraph(
        f"Sur la période, la flotte a réalisé <b>{k['n_trips']:,}".replace(",", " ") +
        f"</b> trajets pour <b>{k['total_distance']:,.0f}".replace(",", " ") +
        f" km</b> et <b>{k['total_duration_h']:,.0f}".replace(",", " ") +
        f" heures</b> de conduite cumulées. La distance moyenne par trajet est de "
        f"{k['avg_distance']} km (durée moyenne {k['avg_duration_min']} min), profil typique "
        f"d'une activité urbaine et péri-urbaine. "
        f"Le taux d'excès de vitesse s'établit à {k['pct_speeding']}% et la part de conduite "
        f"nocturne à {k['pct_night']}%, deux indicateurs à surveiller dans le cadre du suivi sécurité.",
        ss["Body"]))

    # Top véhicules
    story.append(Paragraph("Activité par véhicule", ss["H2b"]))
    story.append(RLImage(io.BytesIO(charts.chart_top_vehicles(result["by_vehicle"])),
                         width=170 * mm, height=99 * mm))

    # Tableau récap par véhicule
    story.append(Spacer(1, 6))
    story.append(Paragraph("Détail par véhicule (top 18 par distance)", ss["H2b"]))
    cw = [40 * mm, 16 * mm, 22 * mm, 18 * mm, 22 * mm, 22 * mm, 18 * mm, 18 * mm]
    story.append(_df_table(result["by_vehicle"], ss, max_rows=18, col_widths=cw))

    # Sécurité & comportement
    story.append(Paragraph("Comportement & sécurité", ss["H2b"]))
    story.append(RLImage(io.BytesIO(charts.chart_speed_distribution(
        result["speed_values"], k["speed_threshold"])), width=170 * mm, height=85 * mm))
    story.append(Spacer(1, 6))
    sp_chart = charts.chart_speeding_by_vehicle(result["by_vehicle"])
    if sp_chart:
        story.append(RLImage(io.BytesIO(sp_chart), width=170 * mm, height=90 * mm))

    # Activité temporelle
    story.append(Paragraph("Activité dans le temps", ss["H2b"]))
    story.append(RLImage(io.BytesIO(charts.chart_daily_activity(result["by_day"])),
                         width=170 * mm, height=85 * mm))
    story.append(Spacer(1, 6))
    story.append(RLImage(io.BytesIO(charts.chart_hourly(result["by_hour"])),
                         width=170 * mm, height=76 * mm))

    # Top excès de vitesse
    if not result["speeding_detail"].empty:
        story.append(Paragraph("Principaux excès de vitesse", ss["H2b"]))
        det = result["speeding_detail"][["Véhicule", "Début", "Distance (km)", "V. max (km/h)"]]
        cw2 = [45 * mm, 45 * mm, 30 * mm, 30 * mm]
        story.append(_df_table(det, ss, max_rows=15, col_widths=cw2))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()
