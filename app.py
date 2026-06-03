"""Plateforme de traitement automatique des rapports Support Tracking — Comafrique.

Lancement : streamlit run app.py
L'agent dépose un rapport (.xlsx) -> téléchargement du PDF d'analyse + récap Excel.
"""
import os
import tempfile
import streamlit as st

import report_engine as engine

st.set_page_config(page_title="Comafrique - Rapports Tracking", page_icon="📊", layout="centered")

ASSETS = os.path.join(os.path.dirname(__file__), "assets")

st.markdown(
    "<h2 style='color:#003366;margin-bottom:0'>📊 Plateforme Rapports - Support Tracking</h2>"
    "<p style='color:#7F8C8D;margin-top:4px'> PC / CT - Géolocalisation & Gestion de flotte</p>",
    unsafe_allow_html=True,
)
st.divider()

with st.sidebar:
    st.subheader("Paramètres")
    speed_threshold = st.slider("Seuil excès de vitesse (km/h)", 50, 130, 90, step=5)
    st.caption("Limite à partir de laquelle un trajet est compté en excès de vitesse.")
    st.divider()
    st.subheader("Branding")
    st.caption("Le logo de Comafrique sera par défaut à gauche de l'entête. "
               "Chargez le logo du client pour qu'il s'affiche à droite.")
    client_logo = st.file_uploader("Logo du client (PNG/JPG)", type=["png", "jpg", "jpeg"],
                                   key="logo")

st.subheader("1. Choisir le mode")
mode = st.radio(
    "Type de traitement",
    ["Rapport simple (Trajet)", "KPI combiné (Ecodrive + Conso)"],
    horizontal=True, label_visibility="collapsed")


def _save_logo(upload):
    if upload is None:
        return None
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    tmp.write(upload.getbuffer())
    tmp.close()
    return tmp.name


if mode == "Rapport simple (Trajet)":
    st.subheader("2. Déposer le rapport")
    uploaded = st.file_uploader("Fichier de rapport Trajet (.xlsx)", type=["xlsx"])
    if uploaded is not None:
        try:
            with st.spinner("Analyse en cours…"):
                pdf_bytes, excel_bytes, meta, result = engine.process(
                    uploaded, speed_threshold=speed_threshold,
                    logo_right=_save_logo(client_logo))
            k = result["kpis"]
            st.success(f"Rapport **{meta.get('raw_type','')}** traité — client **{k['client']}**")
            c1, c2, c3 = st.columns(3)
            c1.metric("Trajets", f"{k['n_trips']:,}".replace(",", " "))
            c2.metric("Distance totale", f"{k['total_distance']:,.0f} km".replace(",", " "))
            c3.metric("Véhicules", k["n_vehicles"])
            c4, c5, c6 = st.columns(3)
            c4.metric("Durée conduite", f"{k['total_duration_h']:,.0f} h".replace(",", " "))
            c5.metric(f"Excès > {k['speed_threshold']}", k["n_speeding"], f"{k['pct_speeding']}%")
            c6.metric("Trajets nuit", k["n_night"], f"{k['pct_night']}%")
            base = f"{k['client']}_trajet_{meta.get('period_start','').replace('/','-')}"
            d1, d2 = st.columns(2)
            d1.download_button("📄 Analyse PDF", pdf_bytes, file_name=f"{base}_analyse.pdf",
                               mime="application/pdf", use_container_width=True)
            d2.download_button("📊 Récap Excel", excel_bytes, file_name=f"{base}_recap.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)
            with st.expander("Détail par véhicule"):
                st.dataframe(result["by_vehicle"], use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Erreur : {e}")
    else:
        st.info("Dépose un fichier .xlsx (rapport Trajet).")

else:  # Scorecard combiné
    st.subheader("2. Déposer les deux rapports")
    st.caption("L'ordre n'a pas d'importance : le type est détecté automatiquement.")
    cc1, cc2 = st.columns(2)
    f_rating = cc1.file_uploader("Rapport Ecodrive / Behavior (.xlsx)", type=["xlsx"], key="rating")
    f_conso = cc2.file_uploader("Rapport Consommation (.xlsx)", type=["xlsx"], key="conso")
    if f_rating is not None and f_conso is not None:
        try:
            with st.spinner("Fusion & analyse en cours…"):
                pdf_bytes, excel_bytes, meta, result = engine.process_combined(
                    f_rating, f_conso, logo_right=_save_logo(client_logo))
            k = result["kpis"]
            st.success(f"Scorecard combiné généré — client **{k['client']}**")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Véhicules", k["n_vehicles"])
            c2.metric("Score moyen", f"{k['avg_score']}%")
            c3.metric("Conso moy.", f"{k['avg_conso']} L/100" if k["avg_conso"] else "n/a")
            c4.metric("À risque", k["n_risk_poor"])
            base = f"{k['client']}_scorecard_{meta.get('period_start','').replace('/','-')}"
            d1, d2 = st.columns(2)
            d1.download_button("📄 Analyse PDF", pdf_bytes, file_name=f"{base}_analyse.pdf",
                               mime="application/pdf", use_container_width=True)
            d2.download_button("📊 Récap Excel", excel_bytes, file_name=f"{base}_recap.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)
            with st.expander("Scorecard véhicule"):
                st.dataframe(result["scorecard"], use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Erreur : {e}")
    else:
        st.info("Déposez les deux fichiers (Ecodrive + Consommation) pour combiner.")
