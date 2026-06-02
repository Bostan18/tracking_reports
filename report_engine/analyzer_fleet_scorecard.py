"""Analyseur combiné ADVANS : fusionne Behavior (Ecodrive) + Consumption.

Granularité de sortie : 1 ligne par véhicule (clé = plaque).
- Le comportement (multi-conducteurs) est agrégé au véhicule.
- La consommation (déjà par véhicule) est jointe sur la plaque.
- Jointure complète : aucun véhicule perdu.
"""
import numpy as np
import pandas as pd

LABEL_ORDER = {"Risk": 0, "Poor": 1, "Average": 2, "Good": 3, "Excellent": 4}
# Bornes de plausibilité conso (L/100km) pour flag qualité capteur
CONSO_MIN_PLAUSIBLE = 3.0
CONSO_MAX_PLAUSIBLE = 25.0


def _plate(units):
    s = str(units).strip()
    return s.split()[0].upper() if s and s.lower() != "nan" else None


def _to_seconds(series):
    return pd.to_timedelta(series.astype(str), errors="coerce").dt.total_seconds()


def analyze_fleet_scorecard(rating: pd.DataFrame, conso: pd.DataFrame,
                            client: str = "ADVANS") -> dict:
    rating = rating.copy()
    conso = conso.copy()
    rating["plate"] = rating["Units"].map(_plate)
    conso["plate"] = conso["Units"].map(_plate)
    rating = rating[rating["plate"].notna()]
    conso = conso[conso["plate"].notna()]

    rating["score_num"] = rating["Score"].astype(str).str.replace("%", "", regex=False)
    rating["score_num"] = pd.to_numeric(rating["score_num"], errors="coerce")
    for c in ["Distance", "Harsh Braking", "Harsh Acceleration", "Harsh Cornering",
              "Overspeed Duration", "Idle Duration"]:
        rating[c] = pd.to_numeric(rating[c], errors="coerce").fillna(0)
    for c in ["Distance", "Fuel Used", "Fuel Tank Size"]:
        conso[c] = pd.to_numeric(conso[c], errors="coerce").fillna(0)

    # ---- Agrégation comportement par véhicule ----
    def _agg_behavior(g):
        d = g["Distance"]
        score = np.average(g["score_num"], weights=d) if d.sum() > 0 else g["score_num"].mean()
        return pd.Series({
            "Units": g.sort_values("Distance", ascending=False)["Units"].iloc[0],
            "conducteurs": int(g["Driver"].nunique()),
            "dist_beh": round(float(d.sum()), 1),
            "score": round(float(score), 1),
            "pire_label": min(g["Label"], key=lambda x: LABEL_ORDER.get(x, 9)),
            "harsh_brake": int(g["Harsh Braking"].sum()),
            "harsh_accel": int(g["Harsh Acceleration"].sum()),
            "harsh_corner": int(g["Harsh Cornering"].sum()),
            "overspeed_min": round(float(g["Overspeed Duration"].sum()), 1),
            "idle_min": round(float(g["Idle Duration"].sum()), 1),
        })
    beh = rating.groupby("plate").apply(_agg_behavior, include_groups=False).reset_index()

    cons = conso.groupby("plate").agg(
        Units_c=("Units", "first"),
        dist_conso=("Distance", "sum"),
        fuel=("Fuel Used", "sum"),
        tank=("Fuel Tank Size", "first"),
    ).reset_index()

    # ---- Fusion ----
    m = pd.merge(beh, cons, on="plate", how="outer")
    m["Units"] = m["Units"].fillna(m["Units_c"])
    m["distance"] = m["dist_conso"].where(m["dist_conso"].notna() & (m["dist_conso"] > 0),
                                          m["dist_beh"])
    m["distance"] = m["distance"].fillna(0).round(1)
    m["fuel"] = m["fuel"].fillna(0).round(1)
    m["harsh_total"] = m[["harsh_brake", "harsh_accel", "harsh_corner"]].fillna(0).sum(axis=1).astype(int)
    m["conso_100"] = np.where((m["fuel"] > 0) & (m["distance"] > 0),
                              (m["fuel"] / m["distance"] * 100).round(1), np.nan)
    m["harsh_100km"] = np.where(m["distance"] > 0,
                                (m["harsh_total"] / m["distance"] * 100).round(1), np.nan)
    m["has_behavior"] = m["score"].notna()
    m["has_fuel"] = m["fuel"] > 0
    m["conso_suspecte"] = m["conso_100"].notna() & (
        (m["conso_100"] < CONSO_MIN_PLAUSIBLE) | (m["conso_100"] > CONSO_MAX_PLAUSIBLE))

    m = m.sort_values("distance", ascending=False).reset_index(drop=True)

    # ---- KPIs globaux ----
    kpis = {
        "client": client,
        "n_vehicles": int(len(m)),
        "n_with_behavior": int(m["has_behavior"].sum()),
        "n_with_fuel": int(m["has_fuel"].sum()),
        "n_drivers": int(rating["Driver"].nunique()),
        "total_distance": round(float(m["distance"].sum()), 0),
        "total_fuel": round(float(m["fuel"].sum()), 0),
        "avg_score": round(float(m["score"].mean()), 1),
        "avg_conso": round(float(m["conso_100"].mean()), 1) if m["conso_100"].notna().any() else None,
        "total_harsh": int(m["harsh_total"].sum()),
        "n_risk_poor": int(m["pire_label"].isin(["Risk", "Poor"]).sum()),
        "n_conso_suspecte": int(m["conso_suspecte"].sum()),
    }
    kpis["avg_harsh_100km"] = round(float(m["harsh_100km"].mean()), 1) if m["harsh_100km"].notna().any() else None

    # ---- Répartition des labels ----
    label_counts = (m["pire_label"].value_counts()
                    .reindex(["Excellent", "Good", "Average", "Poor", "Risk"], fill_value=0))

    # ---- Scorecard formaté pour export ----
    scorecard = m[[
        "Units", "conducteurs", "distance", "score", "pire_label",
        "conso_100", "fuel", "harsh_total", "harsh_100km", "overspeed_min",
    ]].rename(columns={
        "Units": "Véhicule", "conducteurs": "Conducteurs", "distance": "Distance (km)",
        "score": "Score (%)", "pire_label": "Label", "conso_100": "Conso (L/100km)",
        "fuel": "Carburant (L)", "harsh_total": "Évén. brusques",
        "harsh_100km": "Brusques/100km", "overspeed_min": "Excès (min)",
    })

    # ---- Détails (jeux nettoyés conservés) ----
    behavior_detail = rating[[
        "Units", "Driver", "Distance", "Harsh Cornering", "Harsh Braking",
        "Harsh Acceleration", "Idle Duration", "Overspeed Duration", "Score", "Label",
    ]].rename(columns={
        "Units": "Véhicule", "Driver": "Conducteur", "Distance": "Distance (km)",
        "Harsh Cornering": "Virages brusques", "Harsh Braking": "Freinages brusques",
        "Harsh Acceleration": "Accél. brusques", "Idle Duration": "Ralenti (min)",
        "Overspeed Duration": "Excès (min)",
    }).sort_values("Distance (km)", ascending=False)

    conso_detail = conso[[
        "Units", "Distance", "Fuel Used", "Fuel Tank Size",
    ]].rename(columns={
        "Units": "Véhicule", "Distance": "Distance (km)",
        "Fuel Used": "Carburant (L)", "Fuel Tank Size": "Réservoir (L)",
    }).sort_values("Distance (km)", ascending=False)

    return {
        "kpis": kpis,
        "scorecard": scorecard,
        "merged": m,
        "label_counts": label_counts,
        "behavior_detail": behavior_detail,
        "conso_detail": conso_detail,
    }
