"""
CamFilm Agent — Google Cloud Agent Builder (ADK)
=================================================
Agent officiel Google ADK qui utilise :
- Gemini (gemini-2.5-flash)
- les 4 datasets locaux Cameroun
- les outils locaux de app.py
- Parallel Search API via agent_layer.parallel_search
"""

import sys
from pathlib import Path

# Permet d'importer app.py et agent_layer.py depuis la racine du projet
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from google.adk.agents import Agent
from google.adk.tools import FunctionTool

from app import load_datasets, analyze_scene, estimate_budget, camerounize_dialogue
from agent_layer import parallel_search

# Charge les 4 datasets locaux au démarrage
DB = load_datasets()


def analyse_scene(scene_description: str, region: str = "Littoral",
                  lieu_type: str = "marche", tags: str = "") -> dict:
    """Analyse une scene de tournage au Cameroun : alertes ROUGE/ORANGE/JAUNE,
    risques culturels, administratifs, logistiques, langues recommandees.
    tags : mots-cles separes par des virgules (ex : marche, drone, nuit)."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    scene = {
        "description": scene_description,
        "tags": tag_list,
        "lieu": {"type": lieu_type, "region": region},
    }
    return analyze_scene(scene, DB)


def estime_budget(jours_tournage: int = 2, equipe_personnes: int = 12,
                  camera: str = "Sony FX3", son: str = "Kit son complet",
                  eclairage: str = "Kit LED 3 panneaux",
                  generateur: str = "Groupe essence portable",
                  catering: str = "Mama du quartier",
                  lieu_type: str = "ville", marche: bool = False,
                  fixer_local: bool = True) -> dict:
    """Estime un budget de tournage en XAF a partir des datasets locaux
    (materiel, humains, catering, groupe electrogene, protocole chefferie)."""
    params = {
        "jours_tournage": jours_tournage,
        "equipe_personnes": equipe_personnes,
        "camera": camera,
        "son": son,
        "eclairage": eclairage,
        "generateur": generateur,
        "catering": catering,
        "lieu_type": lieu_type,
        "marche": marche,
        "fixer_local": fixer_local,
    }
    return estimate_budget(params, DB)


def camerounise_dialogue(text: str, contexte: str = "marche_douala") -> dict:
    """Camerounise un dialogue en proposant du pidgin english, du camfranglais
    ou des expressions locales selon le contexte."""
    return camerounize_dialogue(text, contexte, DB)


def recherche_web(query: str) -> dict:
    """Recherche web en temps reel via Parallel Search API
    (reglementations, actualites, verification de faits)."""
    return parallel_search(query)


root_agent = Agent(
    name="camfilm_agent",
    model="gemini-2.5-flash",
    description="Agent IA expert de la production cinematographique au Cameroun.",
    instruction=(
        "Tu es CamFilm Agent, expert de la production cinematographique au Cameroun. "
        "Utilise tes outils pour analyser les scenes (analyse_scene), estimer les budgets "
        "(estime_budget), camerouniser les dialogues (camerounise_dialogue) et verifier "
        "les informations a jour sur le web (recherche_web). "
        "Signale toujours les alertes ROUGE en premier. Ne recommande jamais la corruption. "
        "Reponds en francais, de facon claire et structuree."
    ),
    tools=[
        FunctionTool(analyse_scene),
        FunctionTool(estime_budget),
        FunctionTool(camerounise_dialogue),
        FunctionTool(recherche_web),
    ],
)