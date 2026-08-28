"""
agent_layer.py
==============

Couche agentique du projet CamFilm Agent.

Cette couche ajoute :
- l'analyse d'intention avec Gemini
- l'appel aux outils locaux de app.py
- l'appel réel à Parallel Search API à l'exécution (via SDK officiel parallel-web)
- l'appel optionnel à Google Cloud Agent Builder
- la génération d'une réponse finale structurée pour le producteur
- un système de retry automatique en cas de surcharge Gemini (503/429)
- un support bilingue FR/EN via le paramètre `language` dans le contexte

Elle est conçue pour fonctionner même si Parallel Search API
ou Google Cloud Agent Builder ne sont pas encore configurés.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Callable

import httpx
from dotenv import load_dotenv

# SDK officiel Parallel (requis par le règlement Agentic Cinema - Parallel track)
from parallel import Parallel

# Nouveau SDK Gemini
from google import genai
from google.genai import types


# ---------------------------------------------------------------------
# Chargement des variables d'environnement
# ---------------------------------------------------------------------

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

# Parallel Search API
PARALLEL_API_KEY = os.getenv("PARALLEL_API_KEY", "").strip()
PARALLEL_SEARCH_URL = os.getenv("PARALLEL_SEARCH_URL", "").strip()
PARALLEL_TIMEOUT = float(os.getenv("PARALLEL_TIMEOUT", "15"))

# Google Cloud / Agent Builder
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
GOOGLE_CLOUD_REGION = os.getenv("GOOGLE_CLOUD_REGION", "us-central1").strip()
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
GCP_AGENT_BUILDER_URL = os.getenv("GCP_AGENT_BUILDER_URL", "").strip()
GCP_AGENT_BUILDER_TOKEN = os.getenv("GCP_AGENT_BUILDER_TOKEN", "").strip()


# ---------------------------------------------------------------------
# Statut de configuration
# ---------------------------------------------------------------------

def agent_status() -> Dict[str, Any]:
    """
    Retourne l'état de configuration de la couche agentique.
    Utile pour la route /hackathon/agent/status.
    """
    return {
        "gemini_configured": bool(GEMINI_API_KEY),
        "gemini_model": GEMINI_MODEL if GEMINI_API_KEY else None,
        "parallel_configured": bool(PARALLEL_API_KEY and PARALLEL_SEARCH_URL),
        "parallel_url_set": bool(PARALLEL_SEARCH_URL),
        "parallel_key_set": bool(PARALLEL_API_KEY),
        "google_cloud_project": GOOGLE_CLOUD_PROJECT or None,
        "google_cloud_region": GOOGLE_CLOUD_REGION or None,
        "gcp_agent_builder_configured": bool(GCP_AGENT_BUILDER_URL),
        "gcp_service_account_file_set": bool(GOOGLE_APPLICATION_CREDENTIALS),
        "gcp_agent_builder_token_set": bool(GCP_AGENT_BUILDER_TOKEN),
    }


# ---------------------------------------------------------------------
# Utils JSON
# ---------------------------------------------------------------------

def _json_dumps(obj: Any) -> str:
    """Transforme un objet en JSON lisible, sans erreur."""
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    except Exception:
        return str(obj)


def _truncate(text: str, max_chars: int = 20000) -> str:
    """Évite d'envoyer un texte trop long à Gemini."""
    if not text:
        return ""

    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "\n...[contenu tronqué]..."


def _extract_json(text: str) -> Dict[str, Any]:
    """
    Extrait un JSON depuis une réponse Gemini.
    Gère le cas où Gemini entoure le JSON de markdown.
    """
    if not text:
        return {}

    text = text.strip()

    # Enlever les blocs markdown ```json ... ```
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]

    # Essayer de parser directement
    try:
        return json.loads(text)
    except Exception:
        pass

    # Essayer de trouver un bloc JSON dans le texte
    start = text.find("{")
    end = text.rfind("}") + 1

    if start != -1 and end > start:
        try:
            return json.loads(text[start:end])
        except Exception:
            return {}

    return {}


def _generate_with_retry(client, prompt: str, config=None, max_retries: int = 3):
    """
    Appelle Gemini avec tentatives automatiques.
    En cas de 503 (surcharge) ou 429 (quota), attend puis réessaie.
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            if config is not None:
                return client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config=config,
                )
            return client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
        except Exception as exc:
            last_error = exc
            message = str(exc)

            # Erreurs temporaires : on attend puis on réessaie
            if any(code in message for code in ["503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED"]):
                wait = 3 * (attempt + 1)
                time.sleep(wait)
                continue

            # Autre erreur : on arrête
            raise

    raise last_error


# ---------------------------------------------------------------------
# Description des outils locaux pour Gemini
# ---------------------------------------------------------------------

LOCAL_TOOL_SUMMARY = [
    {
        "name": "analyze_scene",
        "description": (
            "Analyse une scène de tournage au Cameroun : alertes IA, risques culturels, "
            "administratifs, logistiques, recommandations linguistiques."
        ),
        "arguments_example": {
            "scene": {
                "description": "Tournage d'une scène de marché à Douala avec drone.",
                "tags": ["marche", "drone"],
                "lieu": {
                    "type": "marche",
                    "region": "Littoral"
                }
            }
        }
    },
    {
        "name": "estimate_budget",
        "description": (
            "Estime un budget de tournage au Cameroun en XAF à partir des datasets locaux."
        ),
        "arguments_example": {
            "jours_tournage": 2,
            "equipe_personnes": 20,
            "camera": "Sony FX3",
            "son": "Kit son complet",
            "eclairage": "Kit LED 3 panneaux",
            "generateur": "Groupe diesel moyen",
            "catering": "Mama du quartier",
            "lieu_type": "village",
            "taille_chefferie": "village_moyen",
            "marche": False,
            "transport_generateur": True,
            "zone_transport": "yaounde_peripherie_50km",
            "autorisation_minac": False,
            "fixer_local": True
        }
    },
    {
        "name": "camerounize_dialogue",
        "description": (
            "Camérounise un dialogue en proposant du pidgin english, du camfranglais "
            "ou des expressions locales selon le contexte."
        ),
        "arguments_example": {
            "text": "Bonjour monsieur, comment allez-vous ? Je voudrais acheter ce produit.",
            "contexte": "marche_douala"
        }
    },
    {
        "name": "build_llm_context",
        "description": (
            "Construit un contexte complet pour un LLM : analyse de scène, budget, "
            "dialogue, alertes et recommandations culturelles."
        ),
        "arguments_example": {
            "description": "Scène de village dans l'Ouest avec cérémonie traditionnelle.",
            "tags": ["village", "ouest", "rituel"],
            "lieu": {
                "type": "village",
                "region": "Ouest"
            },
            "budget_params": {
                "jours_tournage": 3,
                "equipe_personnes": 15,
                "camera": "Sony FX3",
                "lieu_type": "village"
            }
        }
    }
]

KNOWN_TOOLS = {
    "analyze_scene",
    "estimate_budget",
    "camerounize_dialogue",
    "build_llm_context",
}


# ---------------------------------------------------------------------
# Parallel Search API (via SDK officiel parallel-web)
# ---------------------------------------------------------------------

def parallel_search(query: str) -> Dict[str, Any]:
    """
    Appelle Parallel Search API à l'exécution via le SDK officiel parallel-web.

    Conformité règlement Agentic Cinema (Parallel track) :
    "your project must actively use Parallel's Search API at runtime —
    for example, via the official parallel-web SDK (Python or TypeScript)".
    """
    query = str(query or "").strip()

    if not query:
        return {
            "configured": False,
            "ok": False,
            "error": "Aucune requête de recherche fournie.",
        }

    if not PARALLEL_API_KEY:
        return {
            "configured": False,
            "ok": False,
            "query": query,
            "note": (
                "Parallel Search API n'est pas encore configuré. "
                "Ajoute PARALLEL_API_KEY dans .env."
            ),
        }

    try:
        # Client officiel parallel-web (SDK Python)
        client = Parallel(api_key=PARALLEL_API_KEY)

        # Appel via le SDK officiel
        search = client.search(
            objective=query,
            search_queries=[query],
        )

        # Convertir les résultats Pydantic en dicts sérialisables en JSON
        results_serializable = []
        if search and getattr(search, "results", None):
            for r in search.results:
                results_serializable.append({
                    "title": getattr(r, "title", None),
                    "url": getattr(r, "url", None),
                    "publish_date": getattr(r, "publish_date", None),
                    "excerpts": list(getattr(r, "excerpts", []) or []),
                })

        return {
            "configured": True,
            "ok": True,
            "query": query,
            "sdk": "parallel-web (official)",
            "results_count": len(results_serializable),
            "data": {
                "results": results_serializable,
                "search_id": getattr(search, "search_id", None),
            },
        }

    except Exception as exc:
        return {
            "configured": True,
            "ok": False,
            "query": query,
            "sdk": "parallel-web (official)",
            "error": str(exc),
        }


# ---------------------------------------------------------------------
# Google Cloud Agent Builder
# ---------------------------------------------------------------------

def gcp_agent_builder_query(query: str) -> Dict[str, Any]:
    """
    Appelle Google Cloud Agent Builder si configuré.

    Comme l'endpoint exact dépend de ton agent créé dans Google Cloud,
    on utilise GCP_AGENT_BUILDER_URL. Tu devras y coller l'endpoint officiel.
    """
    query = str(query or "").strip()

    if not query:
        return {
            "configured": False,
            "ok": False,
            "error": "Aucune requête fournie.",
        }

    if not GCP_AGENT_BUILDER_URL:
        return {
            "configured": False,
            "ok": False,
            "query": query,
            "note": (
                "Google Cloud Agent Builder n'est pas encore configuré. "
                "Ajoute GCP_AGENT_BUILDER_URL dans .env."
            ),
        }

    headers = {
        "Content-Type": "application/json",
    }

    token = GCP_AGENT_BUILDER_TOKEN

    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload = {
        "input": query,
        "query": query,
        "message": query,
    }

    try:
        with httpx.Client(timeout=30) as client:
            response = client.post(
                GCP_AGENT_BUILDER_URL,
                json=payload,
                headers=headers,
            )

        try:
            data = response.json()
        except Exception:
            data = {
                "raw": response.text,
            }

        return {
            "configured": True,
            "ok": response.status_code < 400,
            "status_code": response.status_code,
            "query": query,
            "data": data,
        }

    except Exception as exc:
        return {
            "configured": True,
            "ok": False,
            "query": query,
            "error": str(exc),
        }


# ---------------------------------------------------------------------
# Prompt de planification Gemini
# ---------------------------------------------------------------------

def _build_planning_prompt(message: str, context: Dict[str, Any]) -> str:
    """Construit le prompt pour que Gemini choisisse le bon outil."""
    tools_json = _json_dumps(LOCAL_TOOL_SUMMARY)
    context_json = _json_dumps(context or {})

    example = {
        "need_web_search": True,
        "web_search_query": "réglementation drone Cameroun 2026 CCAA",
        "tool": "analyze_scene",
        "arguments": {
            "scene": {
                "description": "Tournage avec drone à Yaoundé",
                "tags": ["drone"],
                "lieu": {
                    "type": "ville",
                    "region": "Centre"
                }
            }
        },
        "reason": "L'utilisateur demande une scène avec drone, il faut vérifier les règles."
    }

    example_json = _json_dumps(example)

    return (
        "Tu es CamFilm Agent, un agent IA expert de production cinématographique au Cameroun.\n"
        "Ton rôle est d'aider un producteur à analyser une scène, estimer un budget, "
        "camérouniser des dialogues, et détecter des risques locaux.\n\n"
        "Tu dois décider quel outil local appeler.\n\n"
        "Outils disponibles :\n"
        f"{tools_json}\n\n"
        "Message du producteur :\n"
        f"{message}\n\n"
        "Contexte optionnel fourni par l'application :\n"
        f"{context_json}\n\n"
        "Règles importantes :\n"
        "- Si la demande concerne une scène, un lieu, un risque, un tabou, un drone, un village, un marché, une chefferie : utilise analyze_scene ou build_llm_context.\n"
        "- Si la demande concerne un coût, prix, budget, estimation : utilise estimate_budget.\n"
        "- Si la demande concerne une réplique, dialogue, pidgin, camfranglais : utilise camerounize_dialogue.\n"
        "- Si la demande demande une analyse complète : utilise build_llm_context.\n"
        "- Si l'utilisateur demande des informations actuelles, externes, météo, actualité, réglementation mise à jour, tendances : active need_web_search=true.\n"
        "- Si tu n'as pas assez d'informations pour appeler un outil, utilise tool='final_answer' et pose des questions précises.\n"
        "- Ne recommande jamais la corruption.\n"
        "- Respecte les alertes ROUGE comme bloquantes.\n\n"
        "Réponds UNIQUEMENT avec un JSON valide contenant ces champs :\n"
        "need_web_search, web_search_query, tool, arguments, reason.\n\n"
        "Exemple de réponse :\n"
        f"{example_json}\n"
    )


# ---------------------------------------------------------------------
# Prompt final Gemini (bilingue FR/EN)
# ---------------------------------------------------------------------

def _build_final_prompt(
    message: str,
    plan: Dict[str, Any],
    tool_result: Optional[Dict[str, Any]],
    web_result: Optional[Dict[str, Any]],
    gcp_result: Optional[Dict[str, Any]],
    language: str = "Français",
) -> str:
    """Construit le prompt final pour produire la réponse utilisateur."""
    # Choix de la langue de réponse
    if str(language).lower().startswith("en"):
        lang_instruction = (
            "You must answer in ENGLISH, in a clear and structured way, "
            "useful for an international film producer. "
            "Keep local names, pidgin examples, and cultural terms in their original form."
        )
    else:
        lang_instruction = (
            "Tu dois répondre en français, de manière claire, structurée "
            "et utile pour un producteur camerounais."
        )

    plan_text = _truncate(_json_dumps(plan))
    tool_text = _truncate(_json_dumps(tool_result)) if tool_result else "Aucun outil local appelé."
    web_text = _truncate(_json_dumps(web_result)) if web_result else "Aucune recherche Parallel effectuée."
    gcp_text = _truncate(_json_dumps(gcp_result)) if gcp_result else "Google Cloud Agent Builder non utilisé."

    return (
        "Tu es CamFilm Agent, un agent IA professionnel expert de production cinématographique au Cameroun.\n"
        f"{lang_instruction}\n\n"
        "Message du producteur :\n"
        f"{message}\n\n"
        "Plan décidé par l'agent :\n"
        f"{plan_text}\n\n"
        "Résultat de l'outil local CamFilm :\n"
        f"{tool_text}\n\n"
        "Résultat Parallel Search :\n"
        f"{web_text}\n\n"
        "Résultat Google Cloud Agent Builder :\n"
        f"{gcp_text}\n\n"
        "Règles de réponse :\n"
        "- Utilise les données ci-dessus.\n"
        "- Si une alerte ROUGE existe, commence par ça.\n"
        "- Si des résultats Parallel Search sont présents, cite-les comme sources web à jour.\n"
        "- Si Parallel Search n'est pas configuré, ne bloque pas la réponse. Utilise les datasets locaux.\n"
        "- Si Google Cloud Agent Builder n'est pas configuré, ne bloque pas la réponse.\n"
        "- Ne recommande jamais la corruption.\n"
        "- Propose des alternatives légales et pratiques.\n"
        "- Si les données sont estimées, dis qu'elles doivent être vérifiées localement.\n\n"
        "Structure recommandée :\n"
        "1. Résumé rapide\n"
        "2. Alertes principales 🔴🟠\n"
        "3. Budget estimé si demandé\n"
        "4. Recommandations terrain\n"
        "5. Prochaines actions concrètes\n\n"
        "Réponds maintenant directement au producteur.\n"
    )


# ---------------------------------------------------------------------
# Fonction principale de l'agent
# ---------------------------------------------------------------------

def run_agent(
    message: str,
    context: Dict[str, Any],
    datasets: Dict[str, Any],
    execute_tool_fn: Callable[..., Dict[str, Any]],
    use_parallel: bool = True,
    use_gcp: bool = False,
) -> Dict[str, Any]:
    """
    Exécute l'agent Gemini :
    1. Gemini analyse la demande
    2. Gemini choisit un outil local
    3. Parallel Search est appelé si nécessaire (via SDK officiel parallel-web)
    4. Google Cloud Agent Builder peut être appelé
    5. Gemini produit la réponse finale (en FR ou EN selon le contexte)
    """
    if not GEMINI_API_KEY:
        return {
            "status": "error",
            "error": "GEMINI_API_KEY manquant dans .env",
            "agent_status": agent_status(),
        }

    message = str(message or "").strip()

    if not message:
        return {
            "status": "error",
            "error": "Le message utilisateur est vide.",
        }

    # Extraction de la langue choisie dans l'interface (FR par défaut)
    language = str((context or {}).get("language", "Français")).strip() or "Français"

    # Créer le client Gemini
    client = genai.Client(api_key=GEMINI_API_KEY)

    # -----------------------------------------------------------------
    # 1. Planification : Gemini choisit l'outil (avec retry anti-503)
    # -----------------------------------------------------------------
    planning_prompt = _build_planning_prompt(message, context)

    try:
        planning_response = _generate_with_retry(
            client,
            planning_prompt,
            types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )
        plan = _extract_json(planning_response.text)
    except Exception as exc:
        return {
            "status": "error",
            "error": f"Erreur Gemini lors de la planification : {exc}",
            "agent_status": agent_status(),
        }

    if not isinstance(plan, dict):
        plan = {}

    tool = plan.get("tool", "final_answer")
    arguments = plan.get("arguments") or {}
    need_web_search = bool(plan.get("need_web_search", False))
    web_search_query = plan.get("web_search_query") or message

    if tool not in KNOWN_TOOLS:
        tool = "final_answer"

    # -----------------------------------------------------------------
    # 2. Parallel Search API (recherche web en temps réel via SDK officiel)
    # -----------------------------------------------------------------
    web_result = None

    if use_parallel and need_web_search:
        web_result = parallel_search(web_search_query)

    # -----------------------------------------------------------------
    # 3. Google Cloud Agent Builder
    # -----------------------------------------------------------------
    gcp_result = None

    if use_gcp or bool(GCP_AGENT_BUILDER_URL):
        gcp_result = gcp_agent_builder_query(message)

    # -----------------------------------------------------------------
    # 4. Exécution de l'outil local CamFilm
    # -----------------------------------------------------------------
    tool_result = None

    if tool != "final_answer":
        # Enrichissement automatique avec le contexte si besoin
        if tool == "analyze_scene" and context and not arguments.get("scene"):
            arguments = {"scene": context}

        if tool == "build_llm_context" and context and not arguments:
            arguments = context

        if tool == "estimate_budget" and context.get("budget_params") and not arguments:
            arguments = context.get("budget_params")

        try:
            tool_result = execute_tool_fn(
                name=tool,
                arguments=arguments,
                datasets=datasets,
            )
        except Exception as exc:
            tool_result = {
                "status": "error",
                "tool": tool,
                "error": str(exc),
            }

    # -----------------------------------------------------------------
    # 5. Réponse finale par Gemini (avec retry anti-503 + bilingue)
    # -----------------------------------------------------------------
    final_prompt = _build_final_prompt(
        message=message,
        plan=plan,
        tool_result=tool_result,
        web_result=web_result,
        gcp_result=gcp_result,
        language=language,
    )

    try:
        final_response = _generate_with_retry(
            client,
            final_prompt,
            types.GenerateContentConfig(
                temperature=0.3,
            ),
        )
        final_text = final_response.text
    except Exception as exc:
        final_text = f"Erreur Gemini lors de la réponse finale : {exc}"

    return {
        "status": "success",
        "agent_message": final_text,
        "plan": plan,
        "tool_called": tool,
        "tool_result": tool_result,
        "parallel_search": web_result,
        "gcp_agent_builder": gcp_result,
        "language": language,
        "agent_status": agent_status(),
    }