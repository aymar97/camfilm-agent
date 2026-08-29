"""
interface.py
============
Interface Streamlit BILINGUE (FR/EN) pour CamFilm Agent.
"""
import streamlit as st
import httpx
import pandas as pd
from typing import Dict, Any

st.set_page_config(page_title="CamFilm Agent — Production Cinéma Cameroun", page_icon="🎬", layout="wide", initial_sidebar_state="expanded")
API_URL = "http://127.0.0.1:8000"

ALERT_COLORS = {"ROUGE": "#ff4444", "ORANGE": "#ff8800", "JAUNE": "#ffcc00", "INFO": "#4488ff"}
ALERT_EMOJIS = {"ROUGE": "🔴", "ORANGE": "🟠", "JAUNE": "🟡", "INFO": "ℹ️"}

TEXTS = {
    "Français": {"title": "Agent CamFilm", "subtitle": "Agent IA pour la Production Cinématographique au Cameroun", "examples": "Exemples de requêtes", "scenario1": "Scénario 1 : Marché à Douala", "scenario2": "Scénario 2 : Village Bamiléké", "use1": "Utiliser Exemple 1", "use2": "Utiliser Exemple 2", "tip": "Astuce :", "tip_text": "Plus vous donnez de détails (lieu, durée, équipe, matériel), plus l'agent sera précis !", "describe": "Décrivez votre projet de tournage", "message_label": "Votre message :", "placeholder": "Exemple : Je veux tourner un court-métrage à Yaoundé, scène de rue avec 8 personnes, 3 jours...", "advanced": "Paramètres Avancés (Optionnel)", "basic_info": "Informations de base :", "days": "Jours de tournage", "people": "Nombre de personnes", "lieu_type": "Type de lieu", "region": "Région", "materiel": "Matériel et services :", "camera": "Caméra", "sound": "Son", "lighting": "Éclairage", "generator": "Groupe électrogène", "catering": "Catering", "fixer": "Fixer local", "tags": "Tags (séparés par des virgules)", "analyze": "Analyser avec CamFilm Agent", "analyzing": "L'agent analyse votre projet...", "error_empty": "Veuillez décrire votre projet de tournage.", "error_connect": "Impossible de se connecter à l'API FastAPI. Assurez-vous que le serveur tourne sur http://127.0.0.1:8000", "done": "Analyse terminée !", "report": "Rapport Complet de l'Agent", "alerts": "Alertes Détectées", "no_alerts": "Aucune alerte détectée", "alert_word": "ALERTE", "languages": "Recommandations Linguistiques", "recommended": "Langues recommandées :", "dialogue_examples": "Exemples de dialogues :", "budget": "Budget Estimé", "min_budget": "Budget Minimum", "max_budget": "Budget Maximum", "duration_team": "Durée & Équipe", "days_unit": "jours", "people_unit": "personnes", "detail": "Détail des Postes de Dépenses", "chart": "Répartition du Budget", "notes": "Notes :", "tech": "Informations Techniques", "agent_asked_details": "L'agent a besoin de plus de détails. Donnez-lui des informations sur le lieu, la durée, l'équipe, etc."},
    "English": {"title": "CamFilm Agent", "subtitle": "AI Agent for Film Production in Cameroon", "examples": "Request examples", "scenario1": "Scenario 1: Market in Douala", "scenario2": "Scenario 2: Bamileke Village", "use1": "Use Example 1", "use2": "Use Example 2", "tip": "Tip:", "tip_text": "The more details you provide (location, duration, crew, equipment), the more accurate the agent!", "describe": "Describe your film project", "message_label": "Your message:", "placeholder": "Example: I want to shoot a short film in Yaounde, street scene with 8 people, 3 days...", "advanced": "Advanced Settings (Optional)", "basic_info": "Basic information:", "days": "Shooting days", "people": "Number of people", "lieu_type": "Location type", "region": "Region", "materiel": "Equipment & services:", "camera": "Camera", "sound": "Sound", "lighting": "Lighting", "generator": "Generator", "catering": "Catering", "fixer": "Local fixer", "tags": "Tags (comma separated)", "analyze": "Analyze with CamFilm Agent", "analyzing": "The agent is analyzing your project...", "error_empty": "Please describe your film project.", "error_connect": "Cannot connect to the FastAPI API. Make sure the server runs on http://127.0.0.1:8000", "done": "Analysis complete!", "report": "Full Agent Report", "alerts": "Detected Alerts", "no_alerts": "No alerts detected", "alert_word": "ALERT", "languages": "Language Recommendations", "recommended": "Recommended languages:", "dialogue_examples": "Dialogue examples:", "budget": "Estimated Budget", "min_budget": "Minimum Budget", "max_budget": "Maximum Budget", "duration_team": "Duration & Crew", "days_unit": "days", "people_unit": "people", "detail": "Expense Breakdown", "chart": "Budget Distribution", "notes": "Notes:", "tech": "Technical Information", "agent_asked_details": "The agent needs more details. Tell it about the location, duration, crew, etc."},
}
LEVEL_TRANSLATION = {"Français": {"ROUGE": "ROUGE", "ORANGE": "ORANGE", "JAUNE": "JAUNE", "INFO": "INFO"}, "English": {"ROUGE": "RED", "ORANGE": "ORANGE", "JAUNE": "YELLOW", "INFO": "INFO"}}

def call_agent(message: str, context: Dict[str, Any], language: str) -> Dict[str, Any]:
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(f"{API_URL}/hackathon/agent/chat/gemini", json={"message": message, "context": {**(context or {}), "language": language}}, headers={"Content-Type": "application/json"})
            response.raise_for_status()
            return response.json()
    except httpx.ConnectError: return {"status": "error", "error": "CONNECT"}
    except Exception as e: return {"status": "error", "error": str(e)}

def display_alerts(alerts, lang):
    tr, lv = TEXTS[lang], LEVEL_TRANSLATION[lang]
    if not alerts: st.info("✅ " + tr["no_alerts"]); return
    st.subheader("🚨 " + tr["alerts"])
    for alert in sorted(alerts, key=lambda x: {"ROUGE": 0, "ORANGE": 1, "JAUNE": 2, "INFO": 3}.get(x.get("level", "INFO"), 99)):
        level, color, emoji = alert.get("level", "INFO"), ALERT_COLORS.get(alert.get("level", "INFO"), "#888888"), ALERT_EMOJIS.get(alert.get("level", "INFO"), "⚪")
        st.markdown(f"""<div style="background-color:{color}20;border-left:5px solid {color};padding:15px;margin:10px 0;border-radius:5px;"><h4 style="color:{color};margin:0;">{emoji} {tr['alert_word']} {lv.get(level, level)}</h4><p style="margin:10px 0 0 0;">{alert.get('message','')}</p></div>""", unsafe_allow_html=True)

def display_budget(budget, lang):
    tr = TEXTS[lang]
    if not budget: return
    st.subheader("💰 " + tr["budget"])
    c1, c2, c3 = st.columns(3)
    c1.metric(tr["min_budget"], f"{budget.get('low_XAF',0):,} XAF", f"{budget.get('low_EUR',0):,.2f} EUR")
    c2.metric(tr["max_budget"], f"{budget.get('high_XAF',0):,} XAF", f"{budget.get('high_EUR',0):,.2f} EUR")
    c3.metric(tr["duration_team"], f"{budget.get('jours_tournage',0)} {tr['days_unit']}", f"{budget.get('equipe_personnes',0)} {tr['people_unit']}")
    lines = budget.get("lines", [])
    if lines:
        st.markdown("### " + tr["detail"])
        st.dataframe(pd.DataFrame([{"Poste": l.get("poste", ""), "Quantité": f"{l.get('quantite',0)} {l.get('unit','')}", "Min (XAF)": f"{l.get('low_XAF',0):,}", "Max (XAF)": f"{l.get('high_XAF',0):,}", "Note": l.get("note", "")} for l in lines]), use_container_width=True, hide_index=True)
        st.markdown("### " + tr["chart"])
        st.bar_chart(pd.DataFrame({"Poste": [l.get("poste", "").split(":")[0] for l in lines[:7]], "Min (XAF)": [l.get("low_XAF", 0) for l in lines[:7]], "Max (XAF)": [l.get("high_XAF", 0) for l in lines[:7]]}).set_index("Poste"))
    if budget.get("notes"):
        st.warning("**" + tr["notes"] + "**")
        for n in budget["notes"]: st.markdown(f"- {n}")

def display_storyboard(storyboard, lang):
    if not storyboard or not storyboard.get("storyboard"): return
    st.subheader("🎬 Storyboard de tournage" if lang == "Français" else "🎬 Shooting storyboard")
    shots = storyboard.get("storyboard", [])
    st.dataframe(pd.DataFrame([{"#": s.get("numero"), "Plan": s.get("type_plan"), "Description": s.get("description"), "Durée (min)": s.get("duree_minutes"), "Son": s.get("son_recommande")} for s in shots]), use_container_width=True, hide_index=True)
    st.markdown(f"**⏱️ Durée totale estimée :** {storyboard.get('duree_estimee_heures')} h ({storyboard.get('duree_totale_minutes')} min)")
    if storyboard.get("son_global"): st.markdown(f"**🔊 Son global :** {storyboard.get('son_global')}")
    for n in storyboard.get("notes", []): st.warning("⚠️ " + n)

def display_post_production(post_prod, lang):
    if not post_prod or not post_prod.get("color_grading"): return
    st.subheader("🎛️ Post-Production & Finition" if lang == "Français" else "🎛️ Post-Production & Finishing")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("🎨 **Étalonnage (Color Grading)**")
        cg = post_prod.get("color_grading", {})
        st.info(f"**LUT recommandée :** {cg.get('lut_recommandee')}")
        st.markdown(f"**Réglages :** {cg.get('reglages_resolve')}")
        st.markdown(f"**Astuce lumière :** {cg.get('probleme_lumiere')}")
        st.markdown("🎬 **VFX & Finition**")
        vfx = post_prod.get("vfx_et_finition", {})
        st.markdown(f"- **Stabilisation :** {vfx.get('stabilisation')}")
        st.markdown(f"- **Export :** {vfx.get('export')}")
    with c2:
        st.markdown("🔊 **Sound Design & Mixage**")
        sd = post_prod.get("sound_design", {})
        st.warning(f"**Nettoyage :** {sd.get('nettoyage')}")
        st.markdown(f"**Ambiances :** {sd.get('ambiances')}")
        st.markdown(f"**Mixage :** {sd.get('mixage')}")
        st.markdown("📍 **Prestataires Locaux**")
        for p in post_prod.get("prestataires_locaux", []): st.markdown(f"- {p}")

def display_language(language, lang):
    tr = TEXTS[lang]
    if not language: return
    st.subheader("🗣️ " + tr["languages"])
    if language.get("recommended"): st.markdown(f"**{tr['recommended']}** {', '.join(language['recommended'])}")
    if language.get("examples"):
        st.markdown("**" + tr["dialogue_examples"] + "**")
        for ex in language["examples"][:6]:
            with st.expander(f"💬 {ex.get('francais','')}"):
                if ex.get("pidgin"): st.markdown(f"**Pidgin English :** {ex['pidgin']}")
                if ex.get("camfranglais"): st.markdown(f"**Camfranglais :** {ex['camfranglais']}")
                if ex.get("contexte"): st.markdown(f"*{ex['contexte']}*")

lang = st.sidebar.radio("🌍 Langue / Language", ["Français", "English"], index=0)
tr = TEXTS[lang]
st.title("🎬 " + tr["title"])
st.markdown("**" + tr["subtitle"] + "**")
st.markdown("---")

with st.sidebar:
    st.header("📚 " + tr["examples"])
    st.markdown("**" + tr["scenario1"] + "**")
    if st.button(tr["use1"]):
        st.session_state.message = "Je veux tourner une scène de marché à Douala avec un drone. On est 12 personnes pendant 2 jours, petit budget."
        st.session_state.context = {"description": "Scène de marché à Douala avec drone", "tags": ["marche", "drone", "petit_budget"], "lieu": {"type": "marche", "region": "Littoral"}, "budget_params": {"jours_tournage": 2, "equipe_personnes": 12, "camera": "Sony FX3", "son": "Kit son complet", "eclairage": "Kit LED 3 panneaux", "generateur": "Groupe essence portable", "catering": "Mama du quartier", "lieu_type": "ville", "marche": True, "fixer_local": True}}
        st.rerun()
    st.markdown("**" + tr["scenario2"] + "**")
    if st.button(tr["use2"]):
        st.session_state.message = "Je prépare un tournage dans un village Bamiléké avec une cérémonie traditionnelle. 15 personnes, 3 jours."
        st.session_state.context = {"description": "Tournage village Bamiléké avec cérémonie", "tags": ["village", "ouest", "rituel"], "lieu": {"type": "village", "region": "Ouest"}, "budget_params": {"jours_tournage": 3, "equipe_personnes": 15, "camera": "Blackmagic Pocket 6K", "son": "Kit son complet", "eclairage": "Kit LED 3 panneaux", "generateur": "Groupe diesel moyen", "catering": "Traiteur local", "lieu_type": "village", "taille_chefferie": "village_moyen", "marche": False, "fixer_local": True}}
        st.rerun()
    st.markdown("---")
    st.markdown("**💡 " + tr["tip"] + "**")
    st.info(tr["tip_text"])

st.header("💬 " + tr["describe"])
message = st.text_area(tr["message_label"], value=st.session_state.get("message", ""), height=100, placeholder=tr["placeholder"])

with st.expander("⚙️ " + tr["advanced"], expanded=False):
    st.markdown("**" + tr["basic_info"] + "**")
    c1, c2 = st.columns(2)
    jours = c1.number_input(tr["days"], min_value=1, max_value=30, value=2)
    equipe = c2.number_input(tr["people"], min_value=1, max_value=100, value=12)
    c3, c4 = st.columns(2)
    lieu_type = c3.selectbox(tr["lieu_type"], ["ville", "village", "marche", "rural"])
    region = c4.selectbox(tr["region"], ["Littoral", "Centre", "Ouest", "Nord", "Sud", "Est", "Adamaoua", "Extrême-Nord"])
    st.markdown("**" + tr["materiel"] + "**")
    c5, c6 = st.columns(2)
    camera = c5.selectbox(tr["camera"], ["Sony FX3", "Blackmagic Pocket 6K", "Canon C70", "RED Komodo"])
    son = c6.selectbox(tr["sound"], ["Kit son complet", "Kit son basique"])
    eclairage = st.selectbox(tr["lighting"], ["Kit LED 3 panneaux", "Kit HMI traditionnel"])
    generateur = st.selectbox(tr["generator"], ["Groupe essence portable", "Groupe diesel moyen", "Groupe diesel industriel"])
    catering = st.selectbox(tr["catering"], ["Mama du quartier", "Traiteur local", "Traiteur professionnel"])
    fixer = st.checkbox(tr["fixer"], value=True)
    tags_input = st.text_input(tr["tags"], value="")
    tags = [t.strip() for t in tags_input.split(",") if t.strip()]
    context = {"description": message[:200] if message else "", "tags": tags, "lieu": {"type": lieu_type, "region": region}, "budget_params": {"jours_tournage": jours, "equipe_personnes": equipe, "camera": camera, "son": son, "eclairage": eclairage, "generateur": generateur, "catering": catering, "lieu_type": lieu_type, "fixer_local": fixer}}
    if lieu_type == "marche": context["budget_params"]["marche"] = True

st.markdown("---")

if st.button("🚀 " + tr["analyze"], type="primary", use_container_width=True):
    if not message: st.error(tr["error_empty"])
    else:
        with st.spinner(tr["analyzing"]):
            progress_placeholder = st.empty()
            progress_placeholder.info("🔄 Étape 1/3 : Gemini analyse votre demande...")
            ctx = st.session_state.context if "context" in st.session_state else context
            result = call_agent(message, ctx, lang)
            progress_placeholder.success("✅ Analyse terminée !")

            if result.get("status") == "error":
                err = result.get("error")
                st.error("❌ " + (tr["error_connect"] if err == "CONNECT" else str(err)))
            else:
                st.success("✅ " + tr["done"])
                if result.get("agent_message"):
                    st.subheader("📋 " + tr["report"])
                    st.markdown(result["agent_message"])
                st.markdown("---")
                tool_result = result.get("tool_result") or {}
                if tool_result.get("status") == "success":
                    data = tool_result.get("result", {})
                    analysis = data.get("analysis", {})
                    if analysis:
                        display_alerts(analysis.get("alerts", []), lang)
                        display_language(analysis.get("language", {}), lang)
                    display_budget(data.get("budget", {}), lang)
                    display_storyboard(data.get("storyboard", {}), lang)
                    display_post_production(data.get("post_production", {}), lang)
                else:
                    st.info("💬 " + tr["agent_asked_details"])
                with st.expander("🔧 " + tr["tech"]): st.json(result)

st.markdown("---")
st.markdown("<div style='text-align:center;color:#888;font-size:0.9em;'><p>CamFilm Agent v0.6.0 — Cycle Complet : Pré-prod, Réalisation, Post-prod</p><p>API : <a href='http://127.0.0.1:8000/docs' target='_blank'>http://127.0.0.1:8000/docs</a></p></div>", unsafe_allow_html=True)