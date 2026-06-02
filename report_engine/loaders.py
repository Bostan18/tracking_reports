"""Lecture des fichiers de rapport et détection du type."""
import re
import pandas as pd

# Mots-clés (préfixes) -> type de rapport normalisé
REPORT_TYPE_MAP = {
    "trip": "trajet",
    "trajet": "trajet",
    "ecodrive": "ecodrive",
    "eco": "ecodrive",
    "behavior": "ecodrive",
    "behaviour": "ecodrive",
    "comportement": "ecodrive",
    "fuel": "conso",
    "consumption": "conso",
    "carburant": "conso",
    "conso": "conso",
}


def _normalize_type(raw_type: str) -> str:
    """Normalise le type brut (gère pluriels/variantes) via correspondance par préfixe."""
    rt = raw_type.strip().lower()
    if rt in REPORT_TYPE_MAP:
        return REPORT_TYPE_MAP[rt]
    for key, val in REPORT_TYPE_MAP.items():
        if rt.startswith(key):
            return val
    return rt


def _read_raw(path_or_buffer, sheet_name=0):
    """Lit la feuille brute (sans en-tête) pour inspecter les métadonnées."""
    return pd.read_excel(path_or_buffer, sheet_name=sheet_name, header=None)


def parse_metadata(raw: pd.DataFrame) -> dict:
    """Extrait type / période / nb records depuis les lignes d'en-tête du fichier.

    Format attendu (ligne 2) :
    'Report Type: Trips | Period: 01/05/2026 - 31/05/2026 | Records: 9,516'
    """
    meta = {"report_type": None, "period_start": None, "period_end": None,
            "records": None, "raw_type": None}
    # On scanne les 6 premières lignes, colonne 0
    text_blob = " ".join(
        str(v) for v in raw.iloc[:6, 0].dropna().tolist()
    )
    m_type = re.search(r"Report Type:\s*([A-Za-zéèà-]+)", text_blob, re.I)
    if m_type:
        raw_type = m_type.group(1).strip()
        meta["raw_type"] = raw_type
        meta["report_type"] = _normalize_type(raw_type)
    m_period = re.search(r"Period:\s*([\d/]+)\s*-\s*([\d/]+)", text_blob)
    if m_period:
        meta["period_start"] = m_period.group(1)
        meta["period_end"] = m_period.group(2)
    m_rec = re.search(r"Records:\s*([\d,\.]+)", text_blob)
    if m_rec:
        meta["records"] = int(m_rec.group(1).replace(",", "").replace(".", ""))
    return meta


def _find_header_row(raw: pd.DataFrame, expected_cols) -> int:
    """Trouve l'index de la ligne d'en-tête en cherchant les colonnes attendues."""
    expected = {c.lower() for c in expected_cols}
    for i in range(min(15, len(raw))):
        row_vals = {str(v).strip().lower() for v in raw.iloc[i].dropna().tolist()}
        if len(expected & row_vals) >= max(2, len(expected) // 2):
            return i
    return 4  # défaut connu pour le format actuel


def load_report(path_or_buffer, sheet_name=0):
    """Charge un rapport : renvoie (df_donnees, metadata, client_name).

    Le nom du client est déduit de la colonne 'Company'.
    """
    raw = _read_raw(path_or_buffer, sheet_name=sheet_name)
    meta = parse_metadata(raw)

    expected = ["Company", "Units", "Start", "End", "Distance"]
    header_row = _find_header_row(raw, expected)
    df = pd.read_excel(path_or_buffer, sheet_name=sheet_name, header=header_row)
    df = df.dropna(how="all").reset_index(drop=True)
    # Nettoyage noms de colonnes
    df.columns = [str(c).strip() for c in df.columns]

    client = None
    if "Company" in df.columns and df["Company"].notna().any():
        vals = df["Company"].dropna().unique()
        client = ", ".join(map(str, vals[:3]))
    meta["client"] = client or "Client"
    return df, meta
