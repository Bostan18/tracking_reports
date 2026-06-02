"""Analyseur du rapport Trajet (Trips).

Produit un dictionnaire de KPIs + des tables agrégées prêtes à exporter.
"""
import numpy as np
import pandas as pd


def _to_seconds(duration_series: pd.Series) -> pd.Series:
    """Convertit 'HH:MM:SS' -> secondes."""
    return pd.to_timedelta(duration_series.astype(str), errors="coerce").dt.total_seconds()


def analyze_trips(df: pd.DataFrame, speed_threshold: int = 90,
                  night_start: int = 22, night_end: int = 5) -> dict:
    """Calcule l'ensemble des indicateurs du rapport Trajet.

    Paramètres
    ----------
    speed_threshold : seuil d'alerte excès de vitesse (km/h)
    night_start / night_end : bornes de la plage nocturne (heures)
    """
    d = df.copy()
    d["Start_dt"] = pd.to_datetime(d["Start"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
    d["End_dt"] = pd.to_datetime(d["End"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
    d["dur_s"] = _to_seconds(d["Duration"])
    d["Distance"] = pd.to_numeric(d["Distance"], errors="coerce")
    d["Max Speed"] = pd.to_numeric(d["Max Speed"], errors="coerce")
    d["date"] = d["Start_dt"].dt.date
    d["hour"] = d["Start_dt"].dt.hour

    is_night = (d["hour"] >= night_start) | (d["hour"] < night_end)
    d["is_night"] = is_night
    d["is_speeding"] = d["Max Speed"] > speed_threshold

    # --- KPIs globaux ---
    total_dur_s = float(d["dur_s"].sum())
    kpis = {
        "client": str(d["Company"].dropna().iloc[0]) if "Company" in d and d["Company"].notna().any() else "Client",
        "n_trips": int(len(d)),
        "n_vehicles": int(d["Units"].nunique()),
        "total_distance": round(float(d["Distance"].sum()), 1),
        "total_duration_s": total_dur_s,
        "total_duration_h": round(total_dur_s / 3600, 1),
        "avg_distance": round(float(d["Distance"].mean()), 2),
        "avg_duration_min": round(float(d["dur_s"].mean()) / 60, 1),
        "max_speed_fleet": int(d["Max Speed"].max()),
        "avg_max_speed": round(float(d["Max Speed"].mean()), 1),
        "n_speeding": int(d["is_speeding"].sum()),
        "pct_speeding": round(100 * d["is_speeding"].mean(), 1),
        "n_night": int(is_night.sum()),
        "pct_night": round(100 * is_night.mean(), 1),
        "n_days": int(d["date"].nunique()),
        "speed_threshold": speed_threshold,
        "night_window": f"{night_start:02d}h-{night_end:02d}h",
    }
    kpis["avg_trips_per_vehicle"] = round(kpis["n_trips"] / max(kpis["n_vehicles"], 1), 1)
    kpis["avg_km_per_vehicle"] = round(kpis["total_distance"] / max(kpis["n_vehicles"], 1), 1)

    # --- Agrégat par véhicule ---
    by_vehicle = (
        d.groupby("Units")
        .agg(
            trajets=("Distance", "size"),
            distance_km=("Distance", "sum"),
            duree_h=("dur_s", lambda s: s.sum() / 3600),
            vitesse_max=("Max Speed", "max"),
            vitesse_moy=("Max Speed", "mean"),
            exces=("is_speeding", "sum"),
            trajets_nuit=("is_night", "sum"),
        )
        .reset_index()
        .sort_values("distance_km", ascending=False)
    )
    by_vehicle["distance_km"] = by_vehicle["distance_km"].round(1)
    by_vehicle["duree_h"] = by_vehicle["duree_h"].round(1)
    by_vehicle["vitesse_moy"] = by_vehicle["vitesse_moy"].round(1)
    by_vehicle = by_vehicle.rename(columns={
        "Units": "Véhicule", "trajets": "Trajets", "distance_km": "Distance (km)",
        "duree_h": "Durée (h)", "vitesse_max": "V. max (km/h)",
        "vitesse_moy": "V. moy (km/h)", "exces": "Excès vitesse",
        "trajets_nuit": "Trajets nuit",
    })

    # --- Activité journalière ---
    by_day = (
        d.groupby("date")
        .agg(trajets=("Distance", "size"), distance_km=("Distance", "sum"))
        .reset_index()
        .sort_values("date")
    )
    by_day["distance_km"] = by_day["distance_km"].round(1)
    by_day["date"] = pd.to_datetime(by_day["date"])

    # --- Répartition horaire ---
    by_hour = d.groupby("hour").size().reindex(range(24), fill_value=0).reset_index()
    by_hour.columns = ["heure", "trajets"]

    # --- Détail des excès de vitesse (top) ---
    speeding = d[d["is_speeding"]].copy()
    speeding_detail = speeding[[
        "Units", "Start", "Distance", "Max Speed", "Start Location", "End Location"
    ]].sort_values("Max Speed", ascending=False).rename(columns={
        "Units": "Véhicule", "Start": "Début", "Distance": "Distance (km)",
        "Max Speed": "V. max (km/h)", "Start Location": "Lieu départ",
        "End Location": "Lieu arrivée",
    })

    # --- Distribution des vitesses (pour histogramme) ---
    speed_values = d["Max Speed"].dropna().values

    return {
        "kpis": kpis,
        "by_vehicle": by_vehicle,
        "by_day": by_day,
        "by_hour": by_hour,
        "speeding_detail": speeding_detail,
        "speed_values": speed_values,
    }
