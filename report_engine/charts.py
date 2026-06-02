"""Génération des graphiques (PNG) pour le rapport PDF."""
import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Charte Comafrique
NAVY = "#003366"
BLUE = "#2E6DA4"
ORANGE = "#E58A00"
RED = "#C0392B"
GREY = "#7F8C8D"
LIGHT = "#EAF0F6"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.edgecolor": "#cccccc",
    "axes.grid": True,
    "grid.color": "#ececec",
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def _save(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def chart_top_vehicles(by_vehicle, n=12) -> bytes:
    d = by_vehicle.head(n).iloc[::-1]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.barh(d["Véhicule"].astype(str), d["Distance (km)"], color=BLUE)
    ax.set_xlabel("Distance (km)")
    ax.set_title(f"Top {n} véhicules par distance parcourue", color=NAVY, fontweight="bold")
    for i, v in enumerate(d["Distance (km)"]):
        ax.text(v, i, f" {v:,.0f}", va="center", fontsize=8)
    return _save(fig)


def chart_speed_distribution(speed_values, threshold) -> bytes:
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.hist(speed_values, bins=range(0, 150, 10), color=BLUE, edgecolor="white")
    ax.axvline(threshold, color=RED, linestyle="--", linewidth=2,
               label=f"Seuil {threshold} km/h")
    ax.set_xlabel("Vitesse max par trajet (km/h)")
    ax.set_ylabel("Nb de trajets")
    ax.set_title("Distribution des vitesses maximales", color=NAVY, fontweight="bold")
    ax.legend()
    return _save(fig)


def chart_daily_activity(by_day) -> bytes:
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.bar(by_day["date"], by_day["trajets"], color=BLUE, width=0.7)
    ax.set_ylabel("Nb de trajets")
    ax.set_title("Activité journalière (nombre de trajets)", color=NAVY, fontweight="bold")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    fig.autofmt_xdate(rotation=45)
    return _save(fig)


def chart_hourly(by_hour, night_start=22, night_end=5) -> bytes:
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    colors = [ORANGE if (h >= night_start or h < night_end) else BLUE
              for h in by_hour["heure"]]
    ax.bar(by_hour["heure"], by_hour["trajets"], color=colors)
    ax.set_xlabel("Heure de la journée")
    ax.set_ylabel("Nb de trajets")
    ax.set_xticks(range(0, 24, 2))
    ax.set_title("Répartition horaire des départs (orange = nuit)",
                 color=NAVY, fontweight="bold")
    return _save(fig)


def chart_speeding_by_vehicle(by_vehicle, n=10) -> bytes:
    d = by_vehicle[by_vehicle["Excès vitesse"] > 0].sort_values(
        "Excès vitesse", ascending=True).tail(n)
    if d.empty:
        return None
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    ax.barh(d["Véhicule"].astype(str), d["Excès vitesse"], color=RED)
    ax.set_xlabel("Nb d'excès de vitesse")
    ax.set_title(f"Top {len(d)} véhicules en excès de vitesse",
                 color=NAVY, fontweight="bold")
    for i, v in enumerate(d["Excès vitesse"]):
        ax.text(v, i, f" {int(v)}", va="center", fontsize=8)
    return _save(fig)


# ============ Graphiques scorecard combiné (Behavior + Conso) ============
GREEN = "#2E8B57"
LABEL_COLORS = {"Excellent": "#2E8B57", "Good": "#5CB85C", "Average": "#E58A00",
                "Poor": "#E67E22", "Risk": "#C0392B"}


def chart_label_distribution(label_counts) -> bytes:
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    labels = list(label_counts.index)
    vals = list(label_counts.values)
    colors_ = [LABEL_COLORS.get(l, BLUE) for l in labels]
    bars = ax.bar(labels, vals, color=colors_)
    ax.set_ylabel("Nb de véhicules")
    ax.set_title("Répartition des véhicules par note de conduite",
                 color=NAVY, fontweight="bold")
    for b, v in zip(bars, vals):
        if v > 0:
            ax.text(b.get_x() + b.get_width() / 2, v, str(int(v)),
                    ha="center", va="bottom", fontsize=9)
    return _save(fig)


def chart_score_distribution(merged) -> bytes:
    s = merged["score"].dropna()
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    ax.hist(s, bins=range(0, 110, 10), color=BLUE, edgecolor="white")
    ax.axvline(s.mean(), color=RED, linestyle="--", linewidth=2,
               label=f"Moyenne {s.mean():.0f}%")
    ax.set_xlabel("Score Ecodrive (%)")
    ax.set_ylabel("Nb de véhicules")
    ax.set_title("Distribution des scores de conduite", color=NAVY, fontweight="bold")
    ax.legend()
    return _save(fig)


def chart_top_consumers(merged, n=12) -> bytes:
    d = merged[merged["conso_100"].notna()].sort_values("conso_100").tail(n)
    if d.empty:
        return None
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    colors_ = [RED if x else ORANGE for x in d["conso_suspecte"]]
    ax.barh(d["Units"].astype(str).str.slice(0, 26), d["conso_100"], color=colors_)
    ax.set_xlabel("Consommation (L/100km)")
    ax.set_title(f"Top {len(d)} consommateurs — rouge = valeur suspecte (capteur)",
                 color=NAVY, fontweight="bold")
    for i, v in enumerate(d["conso_100"]):
        ax.text(v, i, f" {v}", va="center", fontsize=8)
    return _save(fig)


def chart_top_risk(merged, n=10) -> bytes:
    d = merged[merged["harsh_100km"].notna()].sort_values("harsh_100km").tail(n)
    if d.empty:
        return None
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    ax.barh(d["Units"].astype(str).str.slice(0, 26), d["harsh_100km"], color=RED)
    ax.set_xlabel("Événements brusques / 100 km")
    ax.set_title(f"Top {len(d)} véhicules à risque (conduite brusque)",
                 color=NAVY, fontweight="bold")
    for i, v in enumerate(d["harsh_100km"]):
        ax.text(v, i, f" {v}", va="center", fontsize=8)
    return _save(fig)


def chart_distance_vs_fuel(merged) -> bytes:
    d = merged[(merged["fuel"] > 0) & (merged["distance"] > 0)]
    if d.empty:
        return None
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    colors_ = [RED if x else BLUE for x in d["conso_suspecte"]]
    ax.scatter(d["distance"], d["fuel"], c=colors_, s=40, alpha=0.8, edgecolor="white")
    ax.set_xlabel("Distance (km)")
    ax.set_ylabel("Carburant consommé (L)")
    ax.set_title("Distance vs carburant (rouge = conso suspecte)",
                 color=NAVY, fontweight="bold")
    return _save(fig)
