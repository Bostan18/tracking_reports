# Plateforme Rapports — Support Tracking (Comafrique)

Traitement automatique des rapports de géolocalisation / gestion de flotte.
L'agent dépose un (ou deux) fichier(s) `.xlsx` ; la plateforme produit
**l'analyse en PDF** (brandée Comafrique à gauche, client à droite) et le **récap Excel**.

## Modes disponibles
- ✅ **Rapport simple — Trajet (Trips)** : KPIs, top véhicules, vitesses, activité, excès.
- ✅ **Scorecard combiné — Ecodrive (Behavior) + Conso (Consumption)** :
  fusion par véhicule (clé = plaque) du comportement de conduite et de la
  consommation carburant, avec détection des consos suspectes (capteur).
- 🔜 Autres types (rapports journaliers, etc.).

## Installation (WSL2 Ubuntu)
```bash
cd tracking_reports
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Logos
- `assets/logo_comafrique.png` : logo Comafrique (gauche) — remplace le placeholder.
- Logo client : chargé depuis la barre latérale de l'app.

## Architecture (évolutive)
```
report_engine/
  loaders.py                  # lecture xlsx + détection auto du type (Trips/Behavior/Consumption…)
  analyzer_trips.py           # KPIs du rapport Trajet
  analyzer_fleet_scorecard.py # fusion Behavior + Consumption -> scorecard véhicule
  charts.py                   # graphiques matplotlib (charte Comafrique)
  pdf_report.py               # PDF Trajet (en-tête brandé réutilisable)
  pdf_scorecard.py            # PDF scorecard combiné
  excel_recap.py              # récaps Excel (Trajet + scorecard) avec formules
  __init__.py                 # process() / process_combined() + registre ANALYZERS
app.py                        # interface Streamlit (2 modes)
```

### Logique de fusion du scorecard combiné
- Clé véhicule = 1er token de `Units` (la plaque), normalisé en majuscules.
- Behavior agrégé par véhicule : score pondéré par distance, pire label,
  événements brusques cumulés, nb conducteurs.
- Consumption joint par véhicule : carburant, conso L/100km.
- Jointure **complète** (aucun véhicule perdu) + flags `has_behavior` / `has_fuel`.
- Conso hors bornes [3 ; 25] L/100km signalée comme « suspecte » (capteur).

### Ajouter un nouveau type de rapport simple
1. Créer `report_engine/analyzer_<type>.py` (`analyze_<type>(df, ...)`).
2. L'enregistrer dans `ANALYZERS` (`__init__.py`).

## Déploiement
Comme `bi-analytics` : push GitHub + Streamlit Community Cloud, ou Docker sur VPS (Contabo/Hetzner).
