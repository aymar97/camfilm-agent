"""
agent_layer.py
==============
Couche agentique du projet CamFilm Agent.
"""

from __future__ import annotations
import json, os, time
from pathlib import Path
from typing import Any, Dict, Optional, Callable
import httpx
from dotenv import load_dotenv
from parallel import Parallel
from google import genai
from google.genai import types

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
PARALLEL_API_KEY = os.getenv("PARALLEL_API_KEY", "").strip()
PARALLEL_SEARCH_URL = os.getenv("PARALLEL_SEARCH_URL", "").strip()
PARALLEL_TIMEOUT = float(os.getenv("PARALLEL_TIMEOUT", "10"))
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
GOOGLE_CLOUD_REGION = os.getenv("GOOGLE_CLOUD_REGION", "us-central1").strip()
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
GCP_AGENT_BUILDER_URL = os.getenv("GCP_AGENT_BUILDER_URL", "").strip()
GCP_AGENT_BUILDER_TOKEN = os.getenv("GCP_AGENT_BUILDER_TOKEN", "").strip()

def agent_status() -> Dict[str, Any]:
    return {
        "gemini_configured": bool(GEMINI_API_KEY), "gemini_model": GEMINI_MODEL if GEMINI_API_KEY else None,
        "parallel_configured": bool(PARALLEL_API_KEY and PARALLEL_SEARCH_URL),
        "parallel_url_set": bool(PARALLEL_SEARCH_URL), "parallel_key_set": bool(PARALLEL_API_KEY),
        "google_cloud_project": GOOGLE_CLOUD_PROJECT or None, "google_cloud_region": GOOGLE_CLOUD_REGION or None,
        "gcp_agent_builder_configured": bool(GCP_AGENT_BUILDER_URL),
        "gcp_service_account_file_set": bool(GOOGLE_APPLICATION_CREDENTIALS),
        "gcp_agent_builder_token_set": bool(GCP_AGENT_BUILDER_TOKEN),
    }

def _json_dumps(obj: Any) -> str:
    try: return json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    except Exception: return str(obj)

def _truncate(text: str, max_chars: int = 20000) -> str:
    if not text: return ""
    return text if len(text) <= max_chars else text[:max_chars] + "\n...[contenu tronqué]..."

def _extract_json(text: str) -> Dict[str, Any]:
    if not text: return {}
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"): text = text[4:]
    try: return json.loads(text)
    except Exception: pass
    start, end = text.find("{"), text.rfind("}") + 1
    if start != -1 and end > start:
        try: return json.loads(text[start:end])
        except Exception: return {}
    return {}

def _generate_with_retry(client, prompt: str, config=None, max_retries: int = 2):
    last_error = None
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(model=GEMINI_MODEL, contents=prompt, config=config) if config else client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        except Exception as exc:
            last_error = exc
            message = str(exc)
            if any(code in message for code in ["503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED"]):
                time.sleep(3 * (attempt + 1)); continue
            raise
    raise last_error

LOCAL_TOOL_SUMMARY = [
    {"name": "analyze_scene", "description": "Analyse une scène de tournage au Cameroun : alertes IA, risques culturels, administratifs, logistiques, recommandations linguistiques.", "arguments_example": {"scene": {"description": "Tournage d'une scène de marché à Douala avec drone.", "tags": ["marche", "drone"], "lieu": {"type": "marche", "region": "Littoral"}}}},
    {"name": "estimate_budget", "description": "Estime un budget de tournage au Cameroun en XAF à partir des datasets locaux.", "arguments_example": {"jours_tournage": 2, "equipe_personnes": 20, "camera": "Sony FX3", "son": "Kit son complet", "eclairage": "Kit LED 3 panneaux", "generateur": "Groupe diesel moyen", "catering": "Mama du quartier", "lieu_type": "village", "taille_chefferie": "village_moyen", "marche": False, "transport_generateur": True, "zone_transport": "yaounde_peripherie_50km", "autorisation_minac": False, "fixer_local": True}},
    {"name": "camerounize_dialogue", "description": "Camérounise un dialogue en proposant du pidgin english, du camfranglais ou des expressions locales selon le contexte.", "arguments_example": {"text": "Bonjour monsieur, comment allez-vous ? Je voudrais acheter ce produit.", "contexte": "marche_douala"}},
    {"name": "build_llm_context", "description": "Construit un contexte complet pour un LLM : analyse de scène, budget, dialogue, alertes et recommandations culturelles.", "arguments_example": {"description": "Scène de village dans l'Ouest avec cérémonie traditionnelle.", "tags": ["village", "ouest", "rituel"], "lieu": {"type": "village", "region": "Ouest"}, "budget_params": {"jours_tournage": 3, "equipe_personnes": 15, "camera": "Sony FX3", "lieu_type": "village"}}},
    {"name": "generate_storyboard", "description": "Génère un storyboard textuel de tournage : liste de plans à tourner, durée par plan, type de son recommandé, et recommandations pour la phase de réalisation.", "arguments_example": {"scene": {"description": "Scène de marché à Douala.", "tags": ["marche"], "lieu": {"type": "marche", "region": "Littoral"}}}},
    {"name": "post_production_advice", "description": "Fournit des recommandations techniques de post-production : étalonnage (LUTs pour peaux africaines), nettoyage sonore (vent, marché), sound design, et recommandations de prestataires à Yaoundé/Douala.", "arguments_example": {"scene_type": "marche_exterieur", "camera": "Sony FX3", "audio_issues": ["vent", "bruit de fond"]}}
]

KNOWN_TOOLS = {"analyze_scene", "estimate_budget", "camerounize_dialogue", "build_llm_context", "generate_storyboard", "post_production_advice"}

def parallel_search(query: str) -> Dict[str, Any]:
    query = str(query or "").strip()
    if not query: return {"configured": False, "ok": False, "error": "Aucune requête de recherche fournie."}
    if not PARALLEL_API_KEY: return {"configured": False, "ok": False, "query": query, "note": "Parallel Search API n'est pas encore configuré. Ajoute PARALLEL_API_KEY dans .env."}
    try:
        client = Parallel(api_key=PARALLEL_API_KEY)
        search = client.search(objective=query, search_queries=[query])
        results_serializable = [{"title": getattr(r, "title", None), "url": getattr(r, "url", None), "publish_date": getattr(r, "publish_date", None), "excerpts": list(getattr(r, "excerpts", []) or [])} for r in search.results] if search and getattr(search, "results", None) else []
        return {"configured": True, "ok": True, "query": query, "sdk": "parallel-web (official)", "results_count": len(results_serializable), "data": {"results": results_serializable, "search_id": getattr(search, "search_id", None)}}
    except Exception as exc:
        return {"configured": True, "ok": False, "query": query, "sdk": "parallel-web (official)", "error": str(exc)}

def gcp_agent_builder_query(query: str) -> Dict[str, Any]:
    query = str(query or "").strip()
    if not query: return {"configured": False, "ok": False, "error": "Aucune requête fournie."}
    if not GCP_AGENT_BUILDER_URL: return {"configured": False, "ok": False, "query": query, "note": "Google Cloud Agent Builder n'est pas encore configuré."}
    headers = {"Content-Type": "application/json"}
    if GCP_AGENT_BUILDER_TOKEN: headers["Authorization"] = f"Bearer {GCP_AGENT_BUILDER_TOKEN}"
    try:
        with httpx.Client(timeout=30) as client:
            response = client.post(GCP_AGENT_BUILDER_URL, json={"input": query, "query": query, "message": query}, headers=headers)
        return {"configured": True, "ok": response.status_code < 400, "status_code": response.status_code, "query": query, "data": response.json() if response.status_code < 400 else {"raw": response.text}}
    except Exception as exc:
        return {"configured": True, "ok": False, "query": query, "error": str(exc)}

def _build_planning_prompt(message: str, context: Dict[str, Any]) -> str:
    tools_json = _json_dumps(LOCAL_TOOL_SUMMARY)
    context_json = _json_dumps(context or {})
    example = {"need_web_search": True, "web_search_query": "réglementation drone Cameroun 2026 CCAA", "tool": "analyze_scene", "arguments": {"scene": {"description": "Tournage avec drone à Yaoundé", "tags": ["drone"], "lieu": {"type": "ville", "region": "Centre"}}}, "reason": "L'utilisateur demande une scène avec drone, il faut vérifier les règles."}
    return (
        "Tu es CamFilm Agent, un agent IA expert de production cinématographique au Cameroun.\n"
        "Ton rôle est d'aider un producteur à analyser une scène, estimer un budget, camérouniser des dialogues, et détecter des risques locaux.\n\n"
        "Tu dois décider quel outil local appeler.\n\n"
        f"Outils disponibles :\n{tools_json}\n\n"
        f"Message du producteur :\n{message}\n\n"
        f"Contexte optionnel fourni par l'application :\n{context_json}\n\n"
        "Règles importantes :\n"
        "- Si la demande concerne une scène, un lieu, un risque, un tabou, un drone, un village, un marché, une chefferie : utilise analyze_scene ou build_llm_context.\n"
        "- Si la demande concerne un coût, prix, budget, estimation : utilise estimate_budget.\n"
        "- Si la demande concerne une réplique, dialogue, pidgin, camfranglais : utilise camerounize_dialogue.\n"
        "- Si la demande concerne la préparation, un storyboard, des plans à tourner, une shot list, un planning, un timing, ou le son de tournage : utilise generate_storyboard.\n"
        "- Si la demande concerne la post-production, l'étalonnage, le mixage, le sound design, les LUTs ou le montage : utilise post_production_advice.\n"
        "- Si l'utilisateur demande des informations actuelles, externes, météo, actualité, réglementation mise à jour, tendances : active need_web_search=true.\n"
        "- Si tu n'as pas assez d'informations pour appeler un outil, utilise tool='final_answer' et pose des questions précises.\n"
        "- Ne recommande jamais la corruption. Respecte les alertes ROUGE comme bloquantes.\n\n"
        "Réponds UNIQUEMENT avec un JSON valide contenant ces champs : need_web_search, web_search_query, tool, arguments, reason.\n\n"
        f"Exemple de réponse :\n{_json_dumps(example)}\n"
    )

def _build_final_prompt(message: str, plan: Dict[str, Any], tool_result: Optional[Dict[str, Any]], web_result: Optional[Dict[str, Any]], gcp_result: Optional[Dict[str, Any]], language: str = "Français") -> str:
    lang_instruction = "You must answer in ENGLISH, in a clear and structured way, useful for an international film producer. Keep local names, pidgin examples, and cultural terms in their original form." if str(language).lower().startswith("en") else "Tu dois répondre en français, de manière claire, structurée et utile pour un producteur camerounais."
    return (
        "Tu es CamFilm Agent, un agent IA professionnel expert de production cinématographique au Cameroun.\n"
        f"{lang_instruction}\n\n"
        f"Message du producteur :\n{message}\n\n"
        f"Plan décidé par l'agent :\n{_truncate(_json_dumps(plan))}\n\n"
        f"Résultat de l'outil local CamFilm :\n{_truncate(_json_dumps(tool_result)) if tool_result else 'Aucun outil local appelé.'}\n\n"
        f"Résultat Parallel Search :\n{_truncate(_json_dumps(web_result)) if web_result else 'Aucune recherche Parallel effectuée.'}\n\n"
        f"Résultat Google Cloud Agent Builder :\n{_truncate(_json_dumps(gcp_result)) if gcp_result else 'Google Cloud Agent Builder non utilisé.'}\n\n"
        "Règles de réponse :\n"
        "- Utilise les données ci-dessus. Si une alerte ROUGE existe, commence par ça.\n"
        "- Si des résultats Parallel Search sont présents, cite-les comme sources web à jour.\n"
        "- Ne recommande jamais la corruption. Propose des alternatives légales et pratiques.\n"
        "- Si les données sont estimées, dis qu'elles doivent être vérifiées localement.\n\n"
        "Structure recommandée :\n1. Résumé rapide\n2. Alertes principales 🔴🟠\n3. Budget estimé si demandé\n4. Recommandations terrain / Post-production\n5. Prochaines actions concrètes\n\n"
        "Réponds maintenant directement au producteur.\n"
    )

def run_agent(message: str, context: Dict[str, Any], datasets: Dict[str, Any], execute_tool_fn: Callable[..., Dict[str, Any]], use_parallel: bool = True, use_gcp: bool = False) -> Dict[str, Any]:
    if not GEMINI_API_KEY: return {"status": "error", "error": "GEMINI_API_KEY manquant dans .env", "agent_status": agent_status()}
    message = str(message or "").strip()
    if not message: return {"status": "error", "error": "Le message utilisateur est vide."}
    language = str((context or {}).get("language", "Français")).strip() or "Français"
    client = genai.Client(api_key=GEMINI_API_KEY)

    try:
        planning_response = _generate_with_retry(client, _build_planning_prompt(message, context), types.GenerateContentConfig(temperature=0.1, response_mime_type="application/json"))
        plan = _extract_json(planning_response.text)
    except Exception as exc:
        return {"status": "error", "error": f"Erreur Gemini lors de la planification : {exc}", "agent_status": agent_status()}

    if not isinstance(plan, dict): plan = {}
    tool = plan.get("tool", "final_answer")
    arguments = plan.get("arguments") or {}
    need_web_search = bool(plan.get("need_web_search", False))
    web_search_query = plan.get("web_search_query") or message
    if tool not in KNOWN_TOOLS: tool = "final_answer"

    web_result = parallel_search(web_search_query) if use_parallel and need_web_search else None
    gcp_result = gcp_agent_builder_query(message) if use_gcp or bool(GCP_AGENT_BUILDER_URL) else None
    tool_result = None

    if tool != "final_answer":
        if tool == "analyze_scene" and context and not arguments.get("scene"): arguments = {"scene": context}
        if tool == "build_llm_context" and context and not arguments: arguments = context
        if tool == "estimate_budget" and context.get("budget_params") and not arguments: arguments = context.get("budget_params")
        if tool == "generate_storyboard" and context and not arguments.get("scene"): arguments = {"scene": context}
        if tool == "post_production_advice" and context:
            if not arguments.get("scene_type") and isinstance(context.get("lieu"), dict): arguments["scene_type"] = context.get("lieu", {}).get("type", "général")
            if not arguments.get("camera") and isinstance(context.get("budget_params"), dict): arguments["camera"] = context.get("budget_params", {}).get("camera", "Standard")
        try: tool_result = execute_tool_fn(name=tool, arguments=arguments, datasets=datasets)
        except Exception as exc: tool_result = {"status": "error", "tool": tool, "error": str(exc)}

    try:
        final_response = _generate_with_retry(client, _build_final_prompt(message, plan, tool_result, web_result, gcp_result, language), types.GenerateContentConfig(temperature=0.3))
        final_text = final_response.text
    except Exception as exc:
        final_text = f"Erreur Gemini lors de la réponse finale : {exc}"

    return {"status": "success", "agent_message": final_text, "plan": plan, "tool_called": tool, "tool_result": tool_result, "parallel_search": web_result, "gcp_agent_builder": gcp_result, "language": language, "agent_status": agent_status()}