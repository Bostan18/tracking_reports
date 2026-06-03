"""PDF d'analyse combinée ADVANS : comportement (Ecodrive) + consommation."""
import io
import os

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, Image as RLImage

from . import charts
from .pdf_report import _Doc, _styles, _df_table, _kpi_grid, ASSETS, NAVY, LIGHT, RED

GREEN = colors.HexColor("#2E8B57")


def _kpi_grid_sc(kpis, ss):
    """Grille KPI adaptée au scorecard combiné (réutilise le style des cartes)."""
    cells = [
        (str(kpis["n_vehicles"]), "Véhicules"),
        (str(kpis["n_drivers"]), "Conducteurs"),
        (f"{kpis['total_distance']:,.0f}".replace(",", " ") + " km", "Distance totale"),
        (f"{kpis['avg_score']}%", "Score moyen flotte"),
        (f"{kpis['total_fuel']:,.0f}".replace(",", " ") + " L", "Carburant total"),
        (f"{kpis['avg_conso']} L" if kpis["avg_conso"] else "n/a", "Conso moy. /100km"),
        (str(kpis["total_harsh"]), "Évén. brusques"),
        (str(kpis["n_risk_poor"]), "Véhic. à risque"),
    ]
    from reportlab.platypus import Table as T
    data, row = [], []
    for val, lbl in cells:
        row.append([Paragraph(val, ss["KpiVal"]), Spacer(1, 3), Paragraph(lbl, ss["KpiLbl"])])
        if len(row) == 4:
            data.append(row); row = []
    if row:
        while len(row) < 4:
            row.append("")
        data.append(row)
    t = T(data, colWidths=[44 * mm] * 4, rowHeights=[19 * mm] * len(data))
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


def _alert_box_sc(kpis, ss):
    parts = []
    if kpis["n_risk_poor"]:
        parts.append(f"<b>{kpis['n_risk_poor']}</b> véhicule(s) en note « Poor / Risk » à suivre")
    if kpis["n_conso_suspecte"]:
        parts.append(f"<b>{kpis['n_conso_suspecte']}</b> valeur(s) de consommation suspecte(s) "
                     f"(capteur à vérifier/calibrer)")
    n_no_fuel = kpis["n_vehicles"] - kpis["n_with_fuel"]
    if n_no_fuel:
        parts.append(f"<b>{n_no_fuel}</b> véhicule(s) sans donnée carburant exploitable")
    txt = "<b>Points d'attention.</b> " + " ; ".join(parts) + "."
    t = Table([[Paragraph(txt, ss["Body"])]], colWidths=[176 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FDECEA")),
        ("BOX", (0, 0), (-1, -1), 0.5, RED),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def build_scorecard_pdf(result, meta, logo_left=None, logo_right=None) -> bytes:
    if logo_left is None:
        logo_left = os.path.join(ASSETS, "logo_comafrique.png")
    if logo_right is None:
        logo_right = os.path.join(ASSETS, "logo_client_placeholder.png")

    buf = io.BytesIO()
    ss = _styles()
    doc = _Doc(buf, meta, logo_left, logo_right,
               title="SCORECARD FLOTTE")
    k = result["kpis"]
    story = []

    story.append(Paragraph(f"Synthèse combinée — {k['client']}", ss["H1b"]))
    story.append(Paragraph(
        f"Période : <b>{meta.get('period_start','?')} → {meta.get('period_end','?')}</b>  •  "
        f"<b>{k['n_vehicles']} véhicules</b> ({k['n_with_behavior']} notés Ecodrive, "
        f"{k['n_with_fuel']} avec données carburant)  •  <b>{k['n_drivers']} conducteurs</b>. "
        f"Ce rapport croise le comportement de conduite et la consommation carburant "
        f"au niveau de chaque véhicule.", ss["Body"]))
    story.append(Spacer(1, 8))
    story.append(_kpi_grid_sc(k, ss))
    story.append(Spacer(1, 10))
    story.append(_alert_box_sc(k, ss))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Lecture analytique", ss["H2b"]))
    conso_txt = (f"La consommation moyenne des véhicules équipés est de "
                 f"{k['avg_conso']} L/100 km" if k["avg_conso"] else
                 "Aucune consommation exploitable n'a pu être calculée")
    story.append(Paragraph(
        f"Le score Ecodrive moyen de la flotte s'établit à <b>{k['avg_score']}%</b>, avec "
        f"<b>{k['n_risk_poor']}</b> véhicule(s) en zone de vigilance. {conso_txt}. "
        f"La couverture carburant reste partielle ({k['n_with_fuel']}/{k['n_vehicles']} "
        f"véhicules), ce qui limite l'analyse conso à un sous-ensemble de la flotte et "
        f"appelle une vérification des capteurs sur les véhicules non couverts ou aux "
        f"valeurs aberrantes.", ss["Body"]))

    # Nombre d'éléments dans les graphiques 'top' selon la taille de flotte
    top_n = charts.top_n_for_fleet(k["n_vehicles"])

    # Comportement
    story.append(Paragraph("Comportement de conduite (Ecodrive)", ss["H2b"]))
    story.append(RLImage(io.BytesIO(charts.chart_label_distribution(result["label_counts"])),
                         width=170 * mm, height=80 * mm))
    story.append(Spacer(1, 6))
    story.append(RLImage(io.BytesIO(charts.chart_score_distribution(result["merged"])),
                         width=170 * mm, height=80 * mm))
    risk = charts.chart_top_risk(result["merged"], n=top_n)
    if risk:
        story.append(Spacer(1, 6))
        story.append(RLImage(io.BytesIO(risk), width=170 * mm, height=90 * mm))

    # Consommation
    story.append(Paragraph("Consommation carburant", ss["H2b"]))
    cons = charts.chart_top_consumers(result["merged"], n=top_n)
    if cons:
        story.append(RLImage(io.BytesIO(cons), width=170 * mm, height=99 * mm))
    dvf = charts.chart_distance_vs_fuel(result["merged"])
    if dvf:
        story.append(Spacer(1, 6))
        story.append(RLImage(io.BytesIO(dvf), width=170 * mm, height=90 * mm))

    # Scorecard table
    story.append(Paragraph("Scorecard véhicule (top 20 par distance)", ss["H2b"]))
    sc = result["scorecard"][["Véhicule", "Score (%)", "Label", "Distance (km)",
                              "Conso (L/100km)", "Brusques/100km", "Conducteurs"]]
    cw = [42 * mm, 18 * mm, 20 * mm, 22 * mm, 24 * mm, 24 * mm, 20 * mm]
    story.append(_df_table(sc, ss, max_rows=20, col_widths=cw))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()
