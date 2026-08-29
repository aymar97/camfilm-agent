"""
CamFilm Agent - Hackathon Ready API
===================================
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from agent_layer import run_agent, agent_status
    AGENT_LAYER_AVAILABLE = True
    AGENT_LAYER_ERROR = None
except Exception as agent_import_exception:
    AGENT_LAYER_AVAILABLE = False
    AGENT_LAYER_ERROR = str(agent_import_exception)

DATASET_FILES: Dict[str, str] = {
    "logistique": "dataset_logistique_village.json",
    "couts": "dataset_couts_reels.json",
    "frictions": "dataset_frictions_admin.json",
    "culture": "dataset_culture_langues.json",
}
BASE_DIR = Path(__file__).resolve().parent

def find_dataset_path(filename: str) -> Path:
    candidates = [
        BASE_DIR / "dataset" / filename, BASE_DIR / "data" / filename, BASE_DIR / filename,
        Path("dataset") / filename, Path("data") / filename, Path(filename),
        Path.cwd() / filename, Path.cwd() / "dataset" / filename, Path.cwd() / "data" / filename,
    ]
    seen = set()
    for candidate in candidates:
        try: resolved = candidate.resolve()
        except Exception: resolved = candidate
        if resolved in seen: continue
        seen.add(resolved)
        if candidate.exists(): return candidate
    raise FileNotFoundError(f"Dataset introuvable : {filename}. Place-le dans ./dataset/ ou ./data/.")

def _normalize(obj: Any) -> Any:
    if isinstance(obj, dict): return {str(k).strip(): _normalize(v) for k, v in obj.items()}
    if isinstance(obj, list): return [_normalize(item) for item in obj]
    if isinstance(obj, str): return obj.strip()
    return obj

def load_datasets() -> Dict[str, Any]:
    loaded: Dict[str, Any] = {}
    for key, filename in DATASET_FILES.items():
        path = find_dataset_path(filename)
        raw = path.read_text(encoding="utf-8")
        loaded[key] = _normalize(json.loads(raw))
    return loaded

def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")

def _norm_text(text: Any) -> str:
    return _strip_accents(str(text).lower())

def parse_range(value: Any, default: Tuple[float, float] = (0.0, 0.0)) -> Tuple[float, float]:
    if value is None: return default
    if isinstance(value, (int, float)): return float(value), float(value)
    if isinstance(value, dict):
        lows, highs = [], []
        for v in value.values():
            low, high = parse_range(v, default)
            lows.append(low); highs.append(high)
        if lows and highs: return min(lows), max(highs)
        return default
    text = re.sub(r"(?i)(xaf|fcfa|eur|€|\$)", "", str(value)).replace("+", "").replace(">", "").replace("≥", "").replace("environ", "")
    numbers = re.findall(r"[\d]+(?:[.,]\d+)?", text.replace(" ", ""))
    if not numbers: return default
    parsed = [float(n.replace(",", ".")) for n in numbers]
    return (parsed[0], parsed[0]) if len(parsed) == 1 else (min(parsed), max(parsed))

def get_by_path(obj: Any, path: str) -> Any:
    current = obj
    for part in path.split("."):
        if current is None: return None
        if isinstance(current, list):
            try: index = int(part)
            except ValueError: return None
            if 0 <= index < len(current): current = current[index]
            else: return None
        elif isinstance(current, dict): current = current.get(part)
        else: return None
    return current

def find_item(items: Any, key: str, needle: str) -> Optional[Dict[str, Any]]:
    if not isinstance(items, list) or not needle: return None
    needle_norm = _norm_text(needle)
    for item in items:
        if needle_norm in _norm_text(item.get(key, "")): return item
    needle_tokens = set(re.findall(r"[a-z0-9]+", needle_norm))
    best_item, best_score = None, 0
    for item in items:
        value_tokens = set(re.findall(r"[a-z0-9]+", _norm_text(item.get(key, ""))))
        score = len(needle_tokens.intersection(value_tokens))
        if score > best_score: best_score, best_item = score, item
    return best_item if best_score > 0 else None

ALERT_RULES: List[Dict[str, Any]] = [
    {"dataset": "frictions", "path": "reglementation_drones.alertes_IA.scenario_plan_drone", "keywords": ["drone", "drones", "vue aerienne", "plan aerien", "aerien"]},
    {"dataset": "frictions", "path": "reglementation_drones.alertes_IA.scenario_drone_etranger", "keywords": ["drone personnel", "importer un drone", "importer drone", "equipe etrangere avec drone"]},
    {"dataset": "logistique", "path": "protocole_chefferie.alertes_IA.scenario_village_sans_accord", "keywords": ["village", "chefferie", "rural", "brousse", "chef de village", "chef traditionnel"]},
    {"dataset": "logistique", "path": "realite_energetique.alertes_IA.scenario_sans_groupe", "keywords": ["sans groupe electrogene", "pas de groupe electrogene", "zone rurale sans electricite", "coupure electrique", "eneo instable"]},
    {"dataset": "logistique", "path": "logistique_routiere.alertes_IA.scenario_planning_serre", "keywords": ["google maps", "planning serre", "temps de trajet", "trajet optimiste"]},
    {"dataset": "logistique", "path": "logistique_routiere.alertes_IA.scenario_saison_pluies", "keywords": ["saison des pluies", "pluies", "boue", "bourbier", "piste boueuse"]},
    {"dataset": "logistique", "path": "logistique_routiere.alertes_IA.scenario_nuit", "keywords": ["nuit", "deplacement nocturne", "transport nocturne", "route de nuit"]},
    {"dataset": "frictions", "path": "checkpoints_police_gendarmerie.alertes_IA.scenario_sans_documents", "keywords": ["transport materiel", "sans documents", "sans ordre de mission", "ordres de mission manquants"]},
    {"dataset": "frictions", "path": "checkpoints_police_gendarmerie.alertes_IA.scenario_filming_checkpoint", "keywords": ["checkpoint", "poste de controle", "police", "gendarmerie", "filmer la police", "filmer les forces de l'ordre"]},
    {"dataset": "frictions", "path": "autorisations_MINAC.alertes_IA.scenario_delai_court", "keywords": ["minac", "autorisation de tournage", "autorisation minac", "visa", "censure"]},
    {"dataset": "frictions", "path": "autorisations_MINAC.alertes_IA.scenario_sans_fixer", "keywords": ["production etrangere", "equipe etrangere", "sans fixer", "sans partenaire local", "sans regulateur local"]},
    {"dataset": "frictions", "path": "autorisations_MINAC.alertes_IA.scenario_film_sensible", "keywords": ["politique", "corruption", "manifestation", "crise anglophone", "sujet sensible"]},
    {"dataset": "culture", "path": "tabous_visuels.alertes_IA.scenario_rituel_sacre", "keywords": ["rituel", "initiation", "masque", "foret sacree", "societe secrete", "rite", "rite traditionnel"]},
    {"dataset": "culture", "path": "tabous_visuels.alertes_IA.scenario_marche", "keywords": ["marche", "vendeurs", "vendor", "marche traditionnel"]},
    {"dataset": "culture", "path": "tabous_visuels.alertes_IA.scenario_crise_anglophone", "keywords": ["nord-ouest", "nord ouest", "sud-ouest", "sud ouest", "bamenda", "buea", "crise anglophone", "north west", "south west"]},
    {"dataset": "culture", "path": "tabous_visuels.alertes_IA.scenario_enfants", "keywords": ["enfants", "enfant", "ecole", "mineur", "mineurs", "scolaire"]},
    {"dataset": "culture", "path": "tabous_visuels.alertes_IA.scenario_batiment_gouvernemental", "keywords": ["batiment gouvernemental", "ministere", "tribunal", "prison", "palais presidentiel", "presidence", "batiment officiel"]},
]

def _extract_level(message: str) -> str:
    normalized = _norm_text(message)
    if "alerte rouge" in normalized: return "ROUGE"
    if "alerte orange" in normalized: return "ORANGE"
    if "alerte jaune" in normalized: return "JAUNE"
    return "INFO"

def detect_alerts(text: str, datasets: Dict[str, Any], tags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    if isinstance(tags, str): tags = [tags]
    tags = tags or []
    full_text = _norm_text(" ".join([str(text), *map(str, tags)]))
    alerts, seen = [], set()
    for rule in ALERT_RULES:
        matched_keywords = [kw for kw in rule.get("keywords", []) if _norm_text(kw) in full_text]
        if not matched_keywords: continue
        message = get_by_path(datasets.get(rule["dataset"], {}), rule["path"])
        if not message: continue
        alert_id = f"{rule['dataset']}:{rule['path']}"
        if alert_id in seen: continue
        seen.add(alert_id)
        alerts.append({"id": alert_id, "level": _extract_level(str(message)), "message": message, "source_dataset": rule["dataset"], "trigger_keywords": matched_keywords})
    alerts.sort(key=lambda alert: {"ROUGE": 0, "ORANGE": 1, "JAUNE": 2, "INFO": 3}.get(alert.get("level", "INFO"), 9))
    return alerts

def recommend_language(scene: Dict[str, Any], datasets: Dict[str, Any]) -> Dict[str, Any]:
    culture = datasets.get("culture", {})
    lieu = scene.get("lieu", {}) if isinstance(scene.get("lieu"), dict) else {}
    scene_type = _norm_text(lieu.get("type", scene.get("contexte", "")))
    region = _norm_text(lieu.get("region", ""))
    tags = scene.get("tags", []) or []
    if isinstance(tags, str): tags = [tags]
    full_text = _norm_text(" ".join([str(scene.get("description", "")), " ".join(map(str, tags)), scene_type, region]))
    output = {"recommended": [], "examples": [], "regles_dataset": get_by_path(culture, "realite_linguistique.feature_IA_dialogue.regles") or []}
    if any(kw in full_text for kw in ["marche", "quartier populaire", "quartier_populaire", "rue", "transport", "gare"]):
        output["recommended"].extend(["Pidgin English", "Camfranglais"])
        output["examples"].extend(get_by_path(culture, "realite_linguistique.pidgin_english.exemples_dialogue", [])[:6])
    elif any(kw in full_text for kw in ["village", "ouest", "bafoussam", "bamileke", "chefferie"]):
        output["recommended"].append("Français local + expressions Bamiléké / Ouest")
        items = get_by_path(culture, "realite_linguistique.expressions_locales_par_region") or []
        for item in items:
            if region in _norm_text(item.get("region", "")) or _norm_text(item.get("region", "")) in region:
                output["examples"].extend(item.get("expressions", [])[:8])
    else:
        output["recommended"].append("Français camerounais courant")
    return output

def camerounize_dialogue(text: str, contexte: str, datasets: Dict[str, Any]) -> Dict[str, Any]:
    culture = datasets.get("culture", {})
    contexte_norm = _norm_text(contexte)
    examples, target_field = [], "pidgin"
    if any(kw in contexte_norm for kw in ["marche", "douala", "quartier populaire", "rue", "transport"]):
        examples = get_by_path(culture, "realite_linguistique.pidgin_english.exemples_dialogue") or []
        target_field = "pidgin"
    elif any(kw in contexte_norm for kw in ["jeune", "yaounde", "universite", "campus", "lycee", "reseau social"]):
        examples = get_by_path(culture, "realite_linguistique.camfranglais.exemples_dialogue") or []
        target_field = "camfranglais"
    else:
        examples = get_by_path(culture, "realite_linguistique.pidgin_english.exemples_dialogue") or []
        target_field = "pidgin"
    text_tokens = set(re.findall(r"[a-z0-9]+", _norm_text(text)))
    scored_suggestions = []
    for example in examples:
        francais = example.get("francais", "")
        target_text = example.get(target_field) or example.get("pidgin") or example.get("camfranglais") or ""
        example_tokens = set(re.findall(r"[a-z0-9]+", _norm_text(francais)))
        common = text_tokens.intersection(example_tokens)
        if common: scored_suggestions.append((len(common), {"francais": francais, target_field: target_text, "contexte": example.get("contexte", "")}))
    scored_suggestions.sort(key=lambda item: item[0], reverse=True)
    suggestions = [item for _, item in scored_suggestions[:10]]
    standard_version = None
    original_norm = _norm_text(text)
    if any(kw in original_norm for kw in ["bonjour", "comment allez", "acheter", "combien", "produit", "cout"]):
        transformation = get_by_path(culture, "realite_linguistique.feature_IA_dialogue.exemple_transformation") or {}
        if any(kw in contexte_norm for kw in ["marche", "douala"]): standard_version = transformation.get("version_marche_douala")
        elif any(kw in contexte_norm for kw in ["jeune", "yaounde"]): standard_version = transformation.get("version_jeune_yaounde")
        elif any(kw in contexte_norm for kw in ["village", "ouest"]): standard_version = transformation.get("version_village_ouest")
    return {"original": text, "contexte": contexte, "version_camerounisee": standard_version, "suggestions": suggestions}

def estimate_budget(params: Dict[str, Any], datasets: Dict[str, Any]) -> Dict[str, Any]:
    couts, logistique, frictions = datasets.get("couts", {}), datasets.get("logistique", {}), datasets.get("frictions", {})
    days, crew = float(params.get("jours_tournage", 1)), int(params.get("equipe_personnes", 20))
    lines, notes, total_low, total_high = [], [], 0.0, 0.0
    def add_line(name: str, low: float, high: float, quantity: float = 1.0, unit: str = "forfait", line_note: Optional[str] = None):
        nonlocal total_low, total_high
        low, high, quantity = float(low), float(high), float(quantity)
        if low <= 0 and high <= 0: return
        line_low, line_high = low * quantity, high * quantity
        total_low += line_low; total_high += line_high
        line = {"poste": name, "low_XAF": round(line_low), "high_XAF": round(line_high), "quantite": quantity, "unit": unit}
        if line_note: line["note"] = line_note
        lines.append(line)

    camera_query = params.get("camera")
    if camera_query:
        camera_item = find_item(get_by_path(couts, "materiel.cameras") or [], "modele", str(camera_query))
        if camera_item:
            low, high = parse_range(camera_item.get("prix_jour_XAF"))
            add_line(f"Caméra : {camera_item.get('modele')}", low, high, days, "jour", camera_item.get("note"))
        else: notes.append(f"Caméra introuvable : {camera_query}")

    sound_query = params.get("son")
    if sound_query:
        sound_item = find_item(get_by_path(couts, "materiel.son") or [], "type", str(sound_query))
        if sound_item:
            low, high = parse_range(sound_item.get("prix_jour_XAF"))
            add_line(f"Son : {sound_item.get('type')}", low, high, days, "jour", sound_item.get("note"))

    light_query = params.get("eclairage")
    if light_query:
        light_item = find_item(get_by_path(couts, "materiel.eclairage") or [], "type", str(light_query))
        if light_item:
            low, high = parse_range(light_item.get("prix_jour_XAF"))
            add_line(f"Éclairage : {light_item.get('type')}", low, high, days, "jour", light_item.get("note"))

    generator_query = params.get("generateur")
    if generator_query:
        generator_item = find_item(get_by_path(logistique, "realite_energetique.groupes_electrogenes.types_disponibles") or [], "type", str(generator_query))
        if generator_item:
            low, high = parse_range(generator_item.get("prix_location_jour_XAF"))
            add_line(f"Groupe électrogène : {generator_item.get('type')}", low, high, days, "jour", generator_item.get("usage"))
            fuel_key = "diesel_100kVA" if "100" in str(generator_item.get("type", "")).lower() else "diesel_50kVA" if "50" in str(generator_item.get("type", "")).lower() else "essence_5kVA"
            fuel_data = get_by_path(logistique, f"realite_energetique.cout_carburant_12h_tournage.{fuel_key}")
            if fuel_data:
                f_low, f_high = parse_range(fuel_data.get("cout_XAF"))
                add_line(f"Carburant groupe ({fuel_key})", f_low, f_high, days, "jour", "Base 12h de tournage.")

    if params.get("include_catering", True):
        catering_query = params.get("catering", "mama")
        catering_item = find_item(get_by_path(couts, "catering_restauration.options") or [], "type", str(catering_query))
        if catering_item:
            low, high = parse_range(catering_item.get("cout_par_personne_XAF"))
            add_line(f"Catering : {catering_item.get('type')}", low, high, crew * days, "personne/jour", catering_item.get("description"))
        else: add_line("Catering : minimum recommandé", 3000, 5000, crew * days, "personne/jour", "Minimum appliqué.")

    lieu_type = _norm_text(params.get("lieu_type", ""))
    if lieu_type in ["village", "rural", "chefferie"]:
        cadeaux = get_by_path(logistique, "protocole_chefferie.cadeaux_protocolaires") or []
        taille_chefferie = params.get("taille_chefferie", "village_moyen")
        for cadeau in cadeaux:
            cadeau_type = str(cadeau.get("type", ""))
            if any(kw in cadeau_type for kw in ["Noix de kola", "Boissons traditionnelles"]):
                low, high = parse_range(cadeau.get("cout_estime_XAF"))
                add_line(f"Protocole chefferie : {cadeau_type}", low, high, 1, "forfait", cadeau.get("note"))
            if "Enveloppe financière" in cadeau_type:
                env_val = cadeau.get("cout_estime_XAF")
                selected_val = env_val.get(taille_chefferie, env_val.get("village_moyen")) if isinstance(env_val, dict) else env_val
                low, high = parse_range(selected_val)
                add_line("Protocole chefferie : enveloppe / contribution", low, high, 1, "forfait", cadeau.get("note"))

    tags = params.get("tags", [])
    if isinstance(tags, str): tags = [tags]
    if params.get("marche", False) or any("marche" in _norm_text(tag) for tag in tags):
        add_line("Contribution marché / accord vendeurs", 20000, 50000, 1, "forfait", "Accord du président du marché.")

    if params.get("fixer_local") or params.get("fixer"):
        fixer_item = find_item(get_by_path(couts, "humain.roles_cles") or [], "role", "Régisseur Général")
        if fixer_item:
            low, high = parse_range(fixer_item.get("cachet_jour_XAF"))
            add_line("Régisseur / fixer local", low, high, days, "jour", fixer_item.get("note"))

    eur_rate = float(get_by_path(logistique, "metadata.taux_change_approximatif.EUR") or 655.957)
    return {"devise": "XAF", "low_XAF": round(total_low), "high_XAF": round(total_high), "low_EUR": round(total_low / eur_rate, 2), "high_EUR": round(total_high / eur_rate, 2), "jours_tournage": days, "equipe_personnes": crew, "lines": lines, "notes": notes}

def analyze_scene(scene: Dict[str, Any], datasets: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(scene, dict): scene = {"description": str(scene)}
    lieu = scene.get("lieu", {}) if isinstance(scene.get("lieu"), dict) else {}
    tags = scene.get("tags", []) or []
    if isinstance(tags, str): tags = [tags]
    full_text = " ".join([str(scene.get("description", "")), str(lieu.get("type", "")), str(lieu.get("region", "")), str(scene.get("contexte", "")), " ".join(map(str, tags))])
    alerts = detect_alerts(full_text, datasets, tags)
    budget_params = scene.get("budget_params", {})
    if isinstance(budget_params, dict):
        if budget_params.get("include_catering") is False:
            alerts.append({"id": "budget:catering_manquant", "level": "JAUNE", "message": "ALERTE JAUNE : Budget sans ligne catering = risque de grève. Prévoir min. 3000 XAF/pers/repas.", "source_dataset": "couts", "trigger_keywords": ["catering"]})
    return {"alerts": alerts, "language": recommend_language(scene, datasets)}

def build_llm_context(scene: Dict[str, Any], datasets: Dict[str, Any]) -> Dict[str, Any]:
    response = {"analysis": analyze_scene(scene, datasets)}
    if isinstance(scene.get("budget_params"), dict): response["budget"] = estimate_budget(scene["budget_params"], datasets)
    if scene.get("dialogue"): response["dialogue"] = camerounize_dialogue(str(scene.get("dialogue")), str(scene.get("contexte_dialogue", "quartier_populaire")), datasets)
    return response

def generate_storyboard(arguments: Dict[str, Any], datasets: Dict[str, Any]) -> Dict[str, Any]:
    scene = (arguments or {}).get("scene", {}) or {}
    description = str(scene.get("description", "") or "")
    lieu = scene.get("lieu", {}) or {}
    lieu_type = str(lieu.get("type", "ville")).lower()
    region = str(lieu.get("region", ""))
    tags = scene.get("tags", []) or []
    budget_params = (arguments or {}).get("budget_params", {}) or {}
    jours = int(budget_params.get("jours_tournage", 1) or 1)

    templates = {
        "marche": [("Plan large (establishing)", "Vue d'ensemble du marché, foule et étals", 20, "Ambiance + son direct"), ("Plan moyen", "Vendeurs et clients, échanges aux étals", 15, "Son direct (dialogues)"), ("Gros plan", "Produits, mains, argent, expressions", 10, "Son direct ou voix off"), ("Travelling", "Suivi du personnage dans les allées", 15, "Ambiance + pas"), ("Plan en plongée", "Vue depuis un bâtiment (alternative drone)", 15, "Ambiance")],
        "village": [("Plan large (establishing)", "Vue du village / chefferie, paysage", 20, "Ambiance (nature, village)"), ("Plan moyen", "Cérémonie, rassemblement, danses", 15, "Son direct + musique traditionnelle"), ("Gros plan", "Visages des notables, symboles, détails", 10, "Voix off ou ambiance"), ("Champ / contre-champ", "Dialogues entre personnages", 15, "Son direct (dialogues)"), ("Plan de coupe (sunset)", "Plan de clôture, lumière chaude", 10, "Musique + ambiance")],
        "ville": [("Plan large (establishing)", "Rue, bâtiments, circulation", 20, "Ambiance urbaine"), ("Plan moyen", "Personnages en action dans la rue", 15, "Son direct (dialogues)"), ("Gros plan", "Émotions, objets importants", 10, "Son direct ou voix off"), ("Travelling", "Suivi du personnage en mouvement", 15, "Ambiance + pas"), ("Plan de nuit", "Scène nocturne avec éclairage", 20, "Ambiance + musique")],
        "rural": [("Plan large (establishing)", "Paysage, champs, piste", 20, "Ambiance (nature)"), ("Plan moyen", "Personnages en activité", 15, "Son direct"), ("Gros plan", "Détails, gestes, expressions", 10, "Voix off ou ambiance"), ("Plan drone (si autorisé)", "Vue aérienne — vérifier autorisation CCAA", 15, "Ambiance")],
    }
    shots_template = templates.get(lieu_type, templates["ville"])
    shots, total_minutes = [], 0
    for i, (type_plan, desc, duree, son) in enumerate(shots_template, start=1):
        shots.append({"numero": i, "type_plan": type_plan, "description": desc, "duree_minutes": duree, "son_recommande": son})
        total_minutes += duree

    has_drone = ("drone" in description.lower()) or any("drone" in str(t).lower() for t in tags)
    notes = []
    if has_drone: notes.append("Drone : autorisation CCAA obligatoire (1-3 mois). Alternatives : grue, perche, bâtiment.")
    if lieu_type == "marche": notes.append("Marché : accord du président du marché + vendeurs (contribution 20 000-50 000 XAF).")
    if lieu_type == "village": notes.append("Village : respecter le protocole de la chefferie, prévoir cérémonie d'accueil.")

    return {"status": "success", "tool": "generate_storyboard", "result": {"description_scene": description or "Scène non précisée", "lieu_type": lieu_type, "region": region, "jours_tournage": jours, "storyboard": shots, "duree_totale_minutes": total_minutes, "duree_estimee_heures": round(total_minutes / 60, 1), "son_global": "Son direct + ambiance ; pidgin/camfranglais pour les dialogues de marché", "notes": notes}}

# ---------------------------------------------------------------------
# NOUVEAU : Outil Post-Production
# ---------------------------------------------------------------------
def post_production_advice(arguments: Dict[str, Any], datasets: Dict[str, Any]) -> Dict[str, Any]:
    scene_type = str((arguments or {}).get("scene_type", "général")).lower()
    camera = str((arguments or {}).get("camera", "Standard")).lower()
    audio_issues = (arguments or {}).get("audio_issues", [])
    if isinstance(audio_issues, str): audio_issues = [audio_issues]

    color_grading = {
        "lut_recommandee": "LUT 'African Skin Tones' (chaude, préservant les sous-tons) ou Kodak 2383 adapté.",
        "reglages_resolve": "Augmenter légèrement la saturation des rouges/oranges pour les peaux. Réduire les hautes lumières vertes si tournage en forêt/village.",
        "probleme_lumiere": "Si sous-exposition (fréquent en intérieur sans groupe) : utiliser le bruit de réduction temporel de Resolve avant d'éclaircir."
    }
    if "nuit" in scene_type or "interieur" in scene_type:
        color_grading["probleme_lumiere"] = "Attention au bruit numérique (noise) en haute ISO. Utiliser un denoiser spatial avant l'étalonnage."

    sound_design = {
        "nettoyage": "Utiliser iZotope RX (Dialogue Isolate) pour retirer le vent du marché ou le bourdonnement du groupe électrogène.",
        "ambiances": "Ajouter des 'room tones' locaux (criquets, bruits de rue de Douala/Yaoundé) pour combler les trous de montage.",
        "mixage": "Normaliser les dialogues à -12 LUFS pour la diffusion web, -23 LUFS pour la TV (CRTV)."
    }
    if any("vent" in str(a).lower() or "marche" in str(a).lower() or "bruit" in str(a).lower() for a in audio_issues):
        sound_design["nettoyage"] = "Priorité absolue : iZotope RX Voice De-noise et Wind De-noise. Enregistrer 1 min de 'room tone' sur place pour le patching."

    vfx_et_finition = {
        "stabilisation": "Appliquer une stabilisation Warp Stabilizer (After Effects) ou Resolve pour les plans au téléphone ou caméra épaule.",
        "export": "Exporter en H.264 (YouTube) et ProRes 422 (mastering local)."
    }

    prestataires_locaux = [
        "Yaoundé : Studios d'étalonnage et mixage à Bastos ou Mvog-Ada (ex: Askia Production, studios indépendants).",
        "Douala : Prestataires techniques à Bonanjo ou Akwa pour le DCP et le mastering final."
    ]

    return {
        "status": "success", "tool": "post_production_advice",
        "result": {
            "post_production": {
                "color_grading": color_grading, "sound_design": sound_design,
                "vfx_et_finition": vfx_et_finition, "prestataires_locaux": prestataires_locaux
            }
        }
    }

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {"type": "function", "function": {"name": "analyze_scene", "description": "Analyse une scène de tournage au Cameroun et retourne les alertes IA, risques culturels, administratifs, logistiques, recommandations linguistiques.", "parameters": {"type": "object", "properties": {"scene": {"type": "object"}}, "required": ["scene"]}}},
    {"type": "function", "function": {"name": "estimate_budget", "description": "Estime un budget de tournage au Cameroun en XAF à partir des datasets locaux.", "parameters": {"type": "object", "properties": {"jours_tournage": {"type": "number"}, "equipe_personnes": {"type": "integer"}, "camera": {"type": "string"}, "son": {"type": "string"}, "eclairage": {"type": "string"}, "generateur": {"type": "string"}, "catering": {"type": "string"}, "lieu_type": {"type": "string"}, "taille_chefferie": {"type": "string"}, "marche": {"type": "boolean"}, "transport_generateur": {"type": "boolean"}, "zone_transport": {"type": "string"}, "autorisation_minac": {"type": "boolean"}, "fixer_local": {"type": "boolean"}}}}},
    {"type": "function", "function": {"name": "camerounize_dialogue", "description": "Camérounise un dialogue en proposant du pidgin english, du camfranglais ou des expressions locales selon le contexte.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "contexte": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "build_llm_context", "description": "Construit un contexte complet pour un LLM : analyse de scène, budget, dialogue, alertes et recommandations culturelles.", "parameters": {"type": "object", "properties": {"description": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}}, "lieu": {"type": "object"}, "budget_params": {"type": "object"}, "dialogue": {"type": "string"}, "contexte_dialogue": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "generate_storyboard", "description": "Génère un storyboard textuel de tournage : liste de plans à tourner, durée par plan, type de son recommandé, recommandations de réalisation.", "parameters": {"type": "object", "properties": {"scene": {"type": "object"}, "budget_params": {"type": "object"}}}}},
    {"type": "function", "function": {"name": "post_production_advice", "description": "Fournit des recommandations techniques de post-production : étalonnage (LUTs), nettoyage sonore (vent, marché), sound design, et recommandations de prestataires locaux.", "parameters": {"type": "object", "properties": {"scene_type": {"type": "string"}, "camera": {"type": "string"}, "audio_issues": {"type": "array", "items": {"type": "string"}}}}}},
]

def get_trace(datasets: Dict[str, Any]) -> Dict[str, Any]:
    trace = {}
    for dataset_key, dataset in datasets.items():
        metadata = dataset.get("metadata", {}) if isinstance(dataset, dict) else {}
        trace[dataset_key] = {"nom": metadata.get("nom"), "version": metadata.get("version"), "date_generation": metadata.get("date_generation"), "niveau_confiance_global": metadata.get("niveau_confiance_global"), "source_recherche": metadata.get("source_recherche")}
    return trace

def execute_tool(name: str, arguments: Dict[str, Any], datasets: Dict[str, Any]) -> Dict[str, Any]:
    arguments = arguments or {}
    try:
        if name == "analyze_scene": result = analyze_scene(arguments.get("scene", arguments), datasets)
        elif name == "estimate_budget": result = estimate_budget(arguments, datasets)
        elif name == "camerounize_dialogue": result = camerounize_dialogue(arguments.get("text", ""), arguments.get("contexte", "quartier_populaire"), datasets)
        elif name == "build_llm_context": result = build_llm_context(arguments, datasets)
        elif name == "generate_storyboard": result = generate_storyboard(arguments if "scene" in arguments or "budget_params" in arguments else {"scene": arguments}, datasets)
        elif name == "post_production_advice": result = post_production_advice(arguments, datasets)
        else: return {"status": "error", "tool": name, "error": f"Outil inconnu : {name}"}
        return {"status": "success", "tool": name, "result": result, "trace": get_trace(datasets)}
    except Exception as exc:
        return {"status": "error", "tool": name, "error": str(exc)}

app = FastAPI(title="CamFilm Agent — Hackathon API", description="Agent IA spécialisé dans la production cinématographique au Cameroun.", version="0.6.0-hackathon")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

_DB: Optional[Dict[str, Any]] = None
def get_db() -> Dict[str, Any]:
    global _DB
    if _DB is None:
        try: _DB = load_datasets()
        except Exception as exc: raise HTTPException(status_code=500, detail=f"Impossible de charger les datasets : {exc}")
    return _DB

class ToolRunRequest(BaseModel):
    tool: str = Field(..., description="Nom de l'outil à exécuter.")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments de l'outil.")

class AgentChatRequest(BaseModel):
    message: str = Field(..., description="Message utilisateur.")
    context: Dict[str, Any] = Field(default_factory=dict, description="Contexte optionnel : scène, budget, dialogue, langue.")

@app.get("/")
def root() -> Dict[str, Any]:
    return {"service": "CamFilm Agent API", "status": "ok", "endpoints": ["/health", "/hackathon/manifest", "/hackathon/tools", "/hackathon/run", "/hackathon/agent/status", "/hackathon/agent/chat", "/hackathon/agent/chat/gemini"]}

@app.get("/health")
def health() -> Dict[str, str]: return {"status": "ok", "service": "CamFilm Agent Hackathon API"}

@app.get("/hackathon/manifest")
def hackathon_manifest() -> Dict[str, Any]:
    db = get_db()
    return {"name": "CamFilm Production Agent", "tagline": "Agent IA terrain pour production cinématographique au Cameroun", "version": "0.6.0-hackathon", "category": "Agentic Cinema / Production Assistant", "capabilities": ["scene_risk_analysis", "cultural_authenticity", "budget_estimation", "dialogue_localization", "administrative_alerts", "logistics_planning", "storyboard_generation", "post_production_advice", "gemini_agent", "parallel_search_ready", "gcp_agent_builder_ready", "bilingual_FR_EN"], "languages": ["fr", "en"], "currency": "XAF", "guardrails": ["Ne jamais recommander la corruption.", "Signaler les alertes ROUGE comme bloquantes.", "Proposer des alternatives légales aux drones.", "Recommander un fixer local pour les productions étrangères.", "Toujours vérifier localement les tabous et protocoles."], "api": {"openapi": "/openapi.json", "tools": "/hackathon/tools", "run": "/hackathon/run", "agent_status": "/hackathon/agent/status", "agent_chat": "/hackathon/agent/chat", "agent_chat_gemini": "/hackathon/agent/chat/gemini"}, "datasets": get_trace(db), "agent_layer_available": AGENT_LAYER_AVAILABLE}

@app.get("/hackathon/tools")
def hackathon_tools() -> Dict[str, Any]: return {"tools": TOOL_SCHEMAS}

@app.post("/hackathon/run")
def hackathon_run(payload: ToolRunRequest) -> Dict[str, Any]:
    return execute_tool(name=payload.tool, arguments=payload.arguments, datasets=get_db())

@app.get("/hackathon/agent/status")
def hackathon_agent_status() -> Dict[str, Any]:
    if not AGENT_LAYER_AVAILABLE: return {"configured": False, "error": AGENT_LAYER_ERROR}
    return agent_status()

@app.post("/hackathon/agent/chat")
def hackathon_agent_chat(payload: AgentChatRequest) -> Dict[str, Any]:
    db, context, message = get_db(), payload.context or {}, payload.message.lower()
    selected_tool, arguments, example = "build_llm_context", {}, {}
    if any(kw in message for kw in ["budget", "cout", "coût", "prix", "estimation", "combien", "argent"]):
        selected_tool, arguments = "estimate_budget", context.get("budget_params", context)
        if not arguments: return {"status": "need_arguments", "selected_tool": selected_tool, "message": "Pour estimer un budget, fournis des paramètres de tournage.", "example": {"tool": "estimate_budget", "arguments": {"jours_tournage": 2, "equipe_personnes": 20, "camera": "Sony FX3", "son": "Kit son complet", "eclairage": "Kit LED 3 panneaux", "generateur": "Groupe diesel moyen", "catering": "Mama du quartier", "lieu_type": "village"}}}
    elif any(kw in message for kw in ["dialogue", "langue", "pidgin", "camfranglais", "réplique", "replique", "parle", "camerounise"]):
        selected_tool, arguments = "camerounize_dialogue", {"text": context.get("dialogue", payload.message), "contexte": context.get("contexte_dialogue", "quartier_populaire")}
    elif any(kw in message for kw in ["storyboard", "plans", "shot list", "planning", "timing", "preparer", "préparer"]):
        selected_tool = "generate_storyboard"
        arguments = {"scene": context} if context else {"scene": {"description": payload.message}}
    elif any(kw in message for kw in ["post-prod", "post production", "etalonnage", "étalonnage", "mixage", "sound design", "lut", "montage"]):
        selected_tool = "post_production_advice"
        arguments = {"scene_type": context.get("lieu", {}).get("type", "général") if isinstance(context.get("lieu"), dict) else "général", "camera": context.get("budget_params", {}).get("camera", "Standard") if isinstance(context.get("budget_params"), dict) else "Standard"}
    elif any(kw in message for kw in ["scene", "scène", "risque", "alerte", "tournage", "tabou", "drone", "village", "marche", "chef", "chefferie"]):
        selected_tool = "analyze_scene"
        arguments = {"scene": context} if context else {"scene": {"description": payload.message}}
    else:
        arguments = context if context else {"description": payload.message}

    result = execute_tool(name=selected_tool, arguments=arguments, datasets=db)
    return {"status": result.get("status"), "selected_tool": selected_tool, "agent_message": "J'ai analysé ta demande avec CamFilm Agent. Voici le résultat structuré.", "response": result, "example_if_missing": example}

@app.post("/hackathon/agent/chat/gemini")
def hackathon_agent_chat_gemini(payload: AgentChatRequest) -> Dict[str, Any]:
    if not AGENT_LAYER_AVAILABLE: raise HTTPException(status_code=500, detail=f"agent_layer indisponible : {AGENT_LAYER_ERROR}")
    return run_agent(message=payload.message, context=payload.context or {}, datasets=get_db(), execute_tool_fn=execute_tool, use_parallel=True, use_gcp=bool(os.getenv("GCP_AGENT_BUILDER_URL")))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)