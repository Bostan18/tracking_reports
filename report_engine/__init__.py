"""Moteur de génération de rapports Support Tracking — Comafrique.

Pipeline : load_report -> analyze -> (PDF + Excel).
Conçu pour évoluer : ajouter un analyseur par type (ecodrive, conso...).
"""
from .loaders import load_report
from .analyzer_trips import analyze_trips
from .analyzer_fleet_scorecard import analyze_fleet_scorecard
from .pdf_report import build_pdf
from .pdf_scorecard import build_scorecard_pdf
from .excel_recap import build_excel, build_scorecard_excel

# Registre des analyseurs par type de rapport
ANALYZERS = {
    "trajet": analyze_trips,
}


def process(path_or_buffer, speed_threshold=90, logo_left=None, logo_right=None):
    """Traite un fichier de rapport et renvoie (pdf_bytes, excel_bytes, meta, result)."""
    df, meta = load_report(path_or_buffer)
    rtype = meta.get("report_type", "trajet")
    analyzer = ANALYZERS.get(rtype)
    if analyzer is None:
        raise ValueError(
            f"Type de rapport '{rtype}' non encore pris en charge. "
            f"Types disponibles : {list(ANALYZERS)}")
    result = analyzer(df, speed_threshold=speed_threshold)
    pdf_bytes = build_pdf(result, meta, logo_left=logo_left, logo_right=logo_right)
    excel_bytes = build_excel(result, meta)
    return pdf_bytes, excel_bytes, meta, result


__all__ = ["load_report", "analyze_trips", "build_pdf", "build_excel", "process",
           "process_combined", "analyze_fleet_scorecard"]


def process_combined(rating_file, conso_file, logo_left=None, logo_right=None):
    """Combine un rapport Behavior (rating) + Consumption (conso) en un scorecard véhicule.

    Renvoie (pdf_bytes, excel_bytes, meta, result). La détection garantit que chaque
    fichier est bien du type attendu, quel que soit l'ordre de chargement.
    """
    df_a, meta_a = load_report(rating_file)
    df_b, meta_b = load_report(conso_file)

    # On identifie qui est qui via le type détecté (ordre indifférent)
    pair = {meta_a["report_type"]: (df_a, meta_a), meta_b["report_type"]: (df_b, meta_b)}
    if "ecodrive" not in pair or "conso" not in pair:
        types = [meta_a.get("raw_type"), meta_b.get("raw_type")]
        raise ValueError(
            f"Attendu un rapport Behavior/Ecodrive + un rapport Consumption. Reçu : {types}")

    rating_df, rating_meta = pair["ecodrive"]
    conso_df, conso_meta = pair["conso"]
    client = rating_meta.get("client") or conso_meta.get("client") or "Client"

    result = analyze_fleet_scorecard(rating_df, conso_df, client=client)
    # période : on prend celle du rapport conso (format cohérent jj/mm)
    meta = {
        "period_start": conso_meta.get("period_start") or rating_meta.get("period_start"),
        "period_end": conso_meta.get("period_end") or rating_meta.get("period_end"),
        "client": client,
        "report_type": "scorecard",
    }
    pdf_bytes = build_scorecard_pdf(result, meta, logo_left=logo_left, logo_right=logo_right)
    excel_bytes = build_scorecard_excel(result, meta)
    return pdf_bytes, excel_bytes, meta, result
