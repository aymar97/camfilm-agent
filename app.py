"""
CamFilm Agent - Hackathon Ready API
===================================

API agentique pour la production cinématographique au Cameroun.

Fonctionnalités :
- chargement des 4 datasets JSON
- analyse de scène
- alertes IA
- recommandation linguistique
- camérounisation de dialogues
- estimation de budget
- exposition des outils pour agent IA
- couche agentique Gemini via agent_layer.py

Placement des datasets :
- soit dans le même dossier que app.py
- soit dans ./dataset/
- soit dans ./data/
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


# ---------------------------------------------------------------------
# Import optionnel de la couche agentique
# ---------------------------------------------------------------------

try:
    from agent_layer import run_agent, agent_status
    AGENT_LAYER_AVAILABLE = True
    AGENT_LAYER_ERROR = None
except Exception as agent_import_exception:
    AGENT_LAYER_AVAILABLE = False
    AGENT_LAYER_ERROR = str(agent_import_exception)


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

DATASET_FILES: Dict[str, str] = {
    "logistique": "dataset_logistique_village.json",
    "couts": "dataset_couts_reels.json",
    "frictions": "dataset_frictions_admin.json",
    "culture": "dataset_culture_langues.json",
}

BASE_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------------------
# Utils
# ---------------------------------------------------------------------

def find_dataset_path(filename: str) -> Path:
    """
    Cherche le dataset dans plusieurs dossiers possibles :
    - ./dataset/
    - ./data/
    - dossier courant
    - dossier de app.py
    """
    candidates = [
        BASE_DIR / "dataset" / filename,
        BASE_DIR / "data" / filename,
        BASE_DIR / filename,
        Path("dataset") / filename,
        Path("data") / filename,
        Path(filename),
        Path.cwd() / filename,
        Path.cwd() / "dataset" / filename,
        Path.cwd() / "data" / filename,
    ]

    seen = set()

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except Exception:
            resolved = candidate

        if resolved in seen:
            continue

        seen.add(resolved)

        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        f"Dataset introuvable : {filename}. "
        "Place-le dans ./dataset/ ou ./data/ à côté de app.py."
    )


def _normalize(obj: Any) -> Any:
    """
    Nettoie récursivement les clés et chaînes.
    Très important car les JSON peuvent contenir des espaces dans les clés.
    Exemple : "metadata " -> "metadata"
    """
    if isinstance(obj, dict):
        return {str(k).strip(): _normalize(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [_normalize(item) for item in obj]

    if isinstance(obj, str):
        return obj.strip()

    return obj


def load_datasets() -> Dict[str, Any]:
    """Charge et normalise les 4 datasets."""
    loaded: Dict[str, Any] = {}

    for key, filename in DATASET_FILES.items():
        path = find_dataset_path(filename)
        raw = path.read_text(encoding="utf-8")
        loaded[key] = _normalize(json.loads(raw))

    return loaded


def _strip_accents(text: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def _norm_text(text: Any) -> str:
    return _strip_accents(str(text).lower())


def parse_range(value: Any, default: Tuple[float, float] = (0.0, 0.0)) -> Tuple[float, float]:
    """
    Transforme une valeur de coût en fourchette basse/haute.
    Exemples :
    - "50000 - 200000"
    - "300000 - 1000000+"
    - 15000
    - {"petit_village": "50000 - 100000"}
    """
    if value is None:
        return default

    if isinstance(value, (int, float)):
        return float(value), float(value)

    if isinstance(value, dict):
        lows: List[float] = []
        highs: List[float] = []

        for v in value.values():
            low, high = parse_range(v, default)
            lows.append(low)
            highs.append(high)

        if lows and highs:
            return min(lows), max(highs)

        return default

    text = str(value)
    text = re.sub(r"(?i)(xaf|fcfa|eur|€|\$)", "", text)
    text = text.replace("+", "")
    text = text.replace(">", "")
    text = text.replace("≥", "")
    text = text.replace("environ", "")

    numbers = re.findall(r"[\d]+(?:[.,]\d+)?", text.replace(" ", ""))

    if not numbers:
        return default

    parsed = [float(n.replace(",", ".")) for n in numbers]

    if len(parsed) == 1:
        return parsed[0], parsed[0]

    return min(parsed), max(parsed)


def get_by_path(obj: Any, path: str) -> Any:
    """
    Récupère une valeur imbriquée.
    Exemple :
    get_by_path(data, "realite_energetique.groupes_electrogenes.types_disponibles")
    """
    current = obj

    for part in path.split("."):
        if current is None:
            return None

        if isinstance(current, list):
            try:
                index = int(part)
            except ValueError:
                return None

            if 0 <= index < len(current):
                current = current[index]
            else:
                return None

        elif isinstance(current, dict):
            current = current.get(part)

        else:
            return None

    return current


def find_item(items: Any, key: str, needle: str) -> Optional[Dict[str, Any]]:
    """
    Recherche un élément dans une liste de dicts.
    D'abord par substring, puis par score de tokens.
    """
    if not isinstance(items, list) or not needle:
        return None

    needle_norm = _norm_text(needle)

    for item in items:
        value = _norm_text(item.get(key, ""))
        if needle_norm in value:
            return item

    needle_tokens = set(re.findall(r"[a-z0-9]+", needle_norm))
    best_item = None
    best_score = 0

    for item in items:
        value = item.get(key, "")
        value_tokens = set(re.findall(r"[a-z0-9]+", _norm_text(value)))
        score = len(needle_tokens.intersection(value_tokens))

        if score > best_score:
            best_score = score
            best_item = item

    return best_item if best_score > 0 else None


# ---------------------------------------------------------------------
# Alertes IA
# ---------------------------------------------------------------------

ALERT_RULES: List[Dict[str, Any]] = [
    # Drones
    {
        "dataset": "frictions",
        "path": "reglementation_drones.alertes_IA.scenario_plan_drone",
        "keywords": ["drone", "drones", "vue aerienne", "plan aerien", "aerien"],
    },
    {
        "dataset": "frictions",
        "path": "reglementation_drones.alertes_IA.scenario_drone_etranger",
        "keywords": [
            "drone personnel",
            "importer un drone",
            "importer drone",
            "equipe etrangere avec drone",
        ],
    },

    # Village / chefferie
    {
        "dataset": "logistique",
        "path": "protocole_chefferie.alertes_IA.scenario_village_sans_accord",
        "keywords": [
            "village",
            "chefferie",
            "rural",
            "brousse",
            "chef de village",
            "chef traditionnel",
        ],
    },

    # Énergie
    {
        "dataset": "logistique",
        "path": "realite_energetique.alertes_IA.scenario_sans_groupe",
        "keywords": [
            "sans groupe electrogene",
            "pas de groupe electrogene",
            "zone rurale sans electricite",
            "coupure electrique",
            "eneo instable",
        ],
    },

    # Route / planning
    {
        "dataset": "logistique",
        "path": "logistique_routiere.alertes_IA.scenario_planning_serre",
        "keywords": [
            "google maps",
            "planning serre",
            "temps de trajet",
            "trajet optimiste",
        ],
    },
    {
        "dataset": "logistique",
        "path": "logistique_routiere.alertes_IA.scenario_saison_pluies",
        "keywords": [
            "saison des pluies",
            "pluies",
            "boue",
            "bourbier",
            "piste boueuse",
        ],
    },
    {
        "dataset": "logistique",
        "path": "logistique_routiere.alertes_IA.scenario_nuit",
        "keywords": [
            "nuit",
            "deplacement nocturne",
            "transport nocturne",
            "route de nuit",
        ],
    },

    # Checkpoints / forces de l'ordre
    {
        "dataset": "frictions",
        "path": "checkpoints_police_gendarmerie.alertes_IA.scenario_sans_documents",
        "keywords": [
            "transport materiel",
            "sans documents",
            "sans ordre de mission",
            "ordres de mission manquants",
        ],
    },
    {
        "dataset": "frictions",
        "path": "checkpoints_police_gendarmerie.alertes_IA.scenario_filming_checkpoint",
        "keywords": [
            "checkpoint",
            "poste de controle",
            "police",
            "gendarmerie",
            "filmer la police",
            "filmer les forces de l'ordre",
        ],
    },
    {
        "dataset": "frictions",
        "path": "checkpoints_police_gendarmerie.alertes_IA.scenario_nuit",
        "keywords": [
            "nuit",
            "deplacement nocturne",
            "transport nocturne",
        ],
    },

    # MINAC / autorisations
    {
        "dataset": "frictions",
        "path": "autorisations_MINAC.alertes_IA.scenario_delai_court",
        "keywords": [
            "minac",
            "autorisation de tournage",
            "autorisation minac",
            "visa",
            "censure",
        ],
    },
    {
        "dataset": "frictions",
        "path": "autorisations_MINAC.alertes_IA.scenario_sans_fixer",
        "keywords": [
            "production etrangere",
            "equipe etrangere",
            "sans fixer",
            "sans partenaire local",
            "sans regulateur local",
        ],
    },
    {
        "dataset": "frictions",
        "path": "autorisations_MINAC.alertes_IA.scenario_film_sensible",
        "keywords": [
            "politique",
            "corruption",
            "manifestation",
            "crise anglophone",
            "sujet sensible",
        ],
    },

    # Tabous culturels
    {
        "dataset": "culture",
        "path": "tabous_visuels.alertes_IA.scenario_rituel_sacre",
        "keywords": [
            "rituel",
            "initiation",
            "masque",
            "foret sacree",
            "societe secrete",
            "rite",
            "rite traditionnel",
        ],
    },
    {
        "dataset": "culture",
        "path": "tabous_visuels.alertes_IA.scenario_marche",
        "keywords": [
            "marche",
            "vendeurs",
            "vendor",
            "marche traditionnel",
        ],
    },
    {
        "dataset": "culture",
        "path": "tabous_visuels.alertes_IA.scenario_crise_anglophone",
        "keywords": [
            "nord-ouest",
            "nord ouest",
            "sud-ouest",
            "sud ouest",
            "bamenda",
            "buea",
            "crise anglophone",
            "north west",
            "south west",
        ],
    },
    {
        "dataset": "culture",
        "path": "tabous_visuels.alertes_IA.scenario_enfants",
        "keywords": [
            "enfants",
            "enfant",
            "ecole",
            "mineur",
            "mineurs",
            "scolaire",
        ],
    },
    {
        "dataset": "culture",
        "path": "tabous_visuels.alertes_IA.scenario_batiment_gouvernemental",
        "keywords": [
            "batiment gouvernemental",
            "ministere",
            "tribunal",
            "prison",
            "palais presidentiel",
            "presidence",
            "batiment officiel",
        ],
    },
]


def _extract_level(message: str) -> str:
    normalized = _norm_text(message)

    if "alerte rouge" in normalized:
        return "ROUGE"

    if "alerte orange" in normalized:
        return "ORANGE"

    if "alerte jaune" in normalized:
        return "JAUNE"

    return "INFO"


def detect_alerts(
    text: str,
    datasets: Dict[str, Any],
    tags: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Détecte les alertes IA à partir d'un texte libre et de tags."""
    if isinstance(tags, str):
        tags = [tags]

    tags = tags or []
    full_text = _norm_text(" ".join([str(text), *map(str, tags)]))

    alerts: List[Dict[str, Any]] = []
    seen = set()

    for rule in ALERT_RULES:
        matched_keywords = [
            keyword
            for keyword in rule.get("keywords", [])
            if _norm_text(keyword) in full_text
        ]

        if not matched_keywords:
            continue

        message = get_by_path(datasets.get(rule["dataset"], {}), rule["path"])

        if not message:
            continue

        alert_id = f"{rule['dataset']}:{rule['path']}"

        if alert_id in seen:
            continue

        seen.add(alert_id)

        alerts.append(
            {
                "id": alert_id,
                "level": _extract_level(str(message)),
                "message": message,
                "source_dataset": rule["dataset"],
                "trigger_keywords": matched_keywords,
            }
        )

    level_order = {
        "ROUGE": 0,
        "ORANGE": 1,
        "JAUNE": 2,
        "INFO": 3,
    }

    alerts.sort(key=lambda alert: level_order.get(alert.get("level", "INFO"), 9))

    return alerts


# ---------------------------------------------------------------------
# Langue / dialogues
# ---------------------------------------------------------------------

def _get_examples(culture: Dict[str, Any], kind: str, limit: int = 6) -> List[Dict[str, Any]]:
    if kind == "pidgin":
        path = "realite_linguistique.pidgin_english.exemples_dialogue"
    elif kind == "camfranglais":
        path = "realite_linguistique.camfranglais.exemples_dialogue"
    else:
        return []

    examples = get_by_path(culture, path) or []
    return examples[:limit]


def _expressions_region(culture: Dict[str, Any], region: str) -> List[Dict[str, Any]]:
    items = get_by_path(culture, "realite_linguistique.expressions_locales_par_region") or []
    region_norm = _norm_text(region)

    if not region_norm:
        return []

    for item in items:
        item_region = _norm_text(item.get("region", ""))

        if region_norm in item_region or item_region in region_norm:
            return item.get("expressions", [])

    return []


def recommend_language(scene: Dict[str, Any], datasets: Dict[str, Any]) -> Dict[str, Any]:
    """Recommande un registre linguistique selon le contexte."""
    culture = datasets.get("culture", {})

    lieu = scene.get("lieu", {}) if isinstance(scene.get("lieu"), dict) else {}
    scene_type = _norm_text(lieu.get("type", scene.get("contexte", "")))
    region = _norm_text(lieu.get("region", ""))

    tags = scene.get("tags", []) or []
    if isinstance(tags, str):
        tags = [tags]

    full_text = _norm_text(
        " ".join(
            [
                str(scene.get("description", "")),
                " ".join(map(str, tags)),
                scene_type,
                region,
            ]
        )
    )

    output: Dict[str, Any] = {
        "recommended": [],
        "examples": [],
        "regles_dataset": get_by_path(
            culture,
            "realite_linguistique.feature_IA_dialogue.regles",
        )
        or [],
    }

    if any(
        keyword in full_text
        for keyword in [
            "marche",
            "quartier populaire",
            "quartier_populaire",
            "rue",
            "transport",
            "gare",
        ]
    ):
        output["recommended"].append("Pidgin English")
        output["recommended"].append("Camfranglais")
        output["examples"].extend(_get_examples(culture, "pidgin", 6))
        output["examples"].extend(_get_examples(culture, "camfranglais", 6))

    elif any(
        keyword in full_text
        for keyword in [
            "universite",
            "jeune",
            "jeunes",
            "campus",
            "lycee",
            "college",
            "reseau social",
        ]
    ):
        output["recommended"].append("Camfranglais")
        output["examples"].extend(_get_examples(culture, "camfranglais", 10))

    elif any(
        keyword in full_text
        for keyword in [
            "village",
            "ouest",
            "bafoussam",
            "bamileke",
            "chefferie",
        ]
    ):
        output["recommended"].append("Français local + expressions Bamiléké / Ouest")
        output["examples"].extend(_expressions_region(culture, "Ouest")[:8])

    elif any(
        keyword in full_text
        for keyword in [
            "nord",
            "garoua",
            "fulfulde",
            "peulh",
            "extreme nord",
            "adamaoua",
        ]
    ):
        output["recommended"].append("Fulfulde / Hausa")
        output["examples"].extend(_expressions_region(culture, "Nord")[:8])

    else:
        output["recommended"].append("Français camerounais courant")

    return output


def camerounize_dialogue(
    text: str,
    contexte: str,
    datasets: Dict[str, Any],
) -> Dict[str, Any]:
    """Propose une version camerounaise d'un dialogue selon le contexte."""
    culture = datasets.get("culture", {})
    contexte_norm = _norm_text(contexte)

    examples: List[Dict[str, Any]] = []
    target_field = "pidgin"

    if any(
        keyword in contexte_norm
        for keyword in [
            "marche",
            "douala",
            "quartier populaire",
            "rue",
            "transport",
        ]
    ):
        examples = get_by_path(culture, "realite_linguistique.pidgin_english.exemples_dialogue") or []
        target_field = "pidgin"

    elif any(
        keyword in contexte_norm
        for keyword in [
            "jeune",
            "yaounde",
            "universite",
            "campus",
            "lycee",
            "reseau social",
        ]
    ):
        examples = get_by_path(culture, "realite_linguistique.camfranglais.exemples_dialogue") or []
        target_field = "camfranglais"

    else:
        examples = get_by_path(culture, "realite_linguistique.pidgin_english.exemples_dialogue") or []
        target_field = "pidgin"

    text_tokens = set(re.findall(r"[a-z0-9]+", _norm_text(text)))
    scored_suggestions: List[Tuple[int, Dict[str, Any]]] = []

    for example in examples:
        francais = example.get("francais", "")
        target_text = example.get(target_field) or example.get("pidgin") or example.get("camfranglais") or ""

        example_tokens = set(re.findall(r"[a-z0-9]+", _norm_text(francais)))
        common = text_tokens.intersection(example_tokens)

        if common:
            scored_suggestions.append(
                (
                    len(common),
                    {
                        "francais": francais,
                        target_field: target_text,
                        "contexte": example.get("contexte", ""),
                    },
                )
            )

    scored_suggestions.sort(key=lambda item: item[0], reverse=True)
    suggestions = [item for _, item in scored_suggestions[:10]]

    standard_version = None
    original_norm = _norm_text(text)

    if any(
        keyword in original_norm
        for keyword in [
            "bonjour",
            "comment allez",
            "acheter",
            "combien",
            "produit",
            "cout",
        ]
    ):
        transformation = get_by_path(
            culture,
            "realite_linguistique.feature_IA_dialogue.exemple_transformation",
        ) or {}

        if any(keyword in contexte_norm for keyword in ["marche", "douala"]):
            standard_version = transformation.get("version_marche_douala")

        elif any(keyword in contexte_norm for keyword in ["jeune", "yaounde"]):
            standard_version = transformation.get("version_jeune_yaounde")

        elif any(keyword in contexte_norm for keyword in ["village", "ouest"]):
            standard_version = transformation.get("version_village_ouest")

    return {
        "original": text,
        "contexte": contexte,
        "version_camerounisee": standard_version,
        "suggestions": suggestions,
    }


# ---------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------

def _choose_fuel_key(generator_type: str) -> str:
    normalized = _norm_text(generator_type)

    if "100" in normalized:
        return "diesel_100kVA"

    if "30" in normalized or "50" in normalized:
        return "diesel_50kVA"

    if "10" in normalized or "20" in normalized:
        return "diesel_20kVA"

    return "essence_5kVA"


def estimate_budget(params: Dict[str, Any], datasets: Dict[str, Any]) -> Dict[str, Any]:
    """Estime un budget de tournage à partir des datasets."""
    couts = datasets.get("couts", {})
    logistique = datasets.get("logistique", {})
    frictions = datasets.get("frictions", {})

    days = float(params.get("jours_tournage", 1))
    crew = int(params.get("equipe_personnes", 20))

    lines: List[Dict[str, Any]] = []
    notes: List[str] = []
    total_low = 0.0
    total_high = 0.0

    def add_line(
        name: str,
        low: float,
        high: float,
        quantity: float = 1.0,
        unit: str = "forfait",
        line_note: Optional[str] = None,
    ) -> None:
        nonlocal total_low, total_high

        low = float(low)
        high = float(high)
        quantity = float(quantity)

        if low <= 0 and high <= 0:
            return

        line_low = low * quantity
        line_high = high * quantity

        total_low += line_low
        total_high += line_high

        line = {
            "poste": name,
            "low_XAF": round(line_low),
            "high_XAF": round(line_high),
            "quantite": quantity,
            "unit": unit,
        }

        if line_note:
            line["note"] = line_note

        lines.append(line)

    # Caméra
    camera_query = params.get("camera")
    if camera_query:
        cameras = get_by_path(couts, "materiel.cameras") or []
        camera_item = find_item(cameras, "modele", str(camera_query))

        if camera_item:
            low, high = parse_range(camera_item.get("prix_jour_XAF"))
            add_line(
                f"Caméra : {camera_item.get('modele')}",
                low,
                high,
                days,
                "jour",
                camera_item.get("note"),
            )
        else:
            notes.append(f"Caméra introuvable dans le dataset : {camera_query}")

    # Son
    sound_query = params.get("son")
    if sound_query:
        sound_items = get_by_path(couts, "materiel.son") or []
        sound_item = find_item(sound_items, "type", str(sound_query))

        if sound_item:
            low, high = parse_range(sound_item.get("prix_jour_XAF"))
            add_line(
                f"Son : {sound_item.get('type')}",
                low,
                high,
                days,
                "jour",
                sound_item.get("note"),
            )
        else:
            notes.append(f"Kit son introuvable dans le dataset : {sound_query}")

    # Éclairage
    light_query = params.get("eclairage")
    if light_query:
        light_items = get_by_path(couts, "materiel.eclairage") or []
        light_item = find_item(light_items, "type", str(light_query))

        if light_item:
            low, high = parse_range(light_item.get("prix_jour_XAF"))
            add_line(
                f"Éclairage : {light_item.get('type')}",
                low,
                high,
                days,
                "jour",
                light_item.get("note"),
            )
        else:
            notes.append(f"Éclairage introuvable dans le dataset : {light_query}")

    # Accessoires
    accessories = params.get("accessoires", [])
    if isinstance(accessories, str):
        accessories = [accessories]

    accessory_items = get_by_path(couts, "materiel.accessoires") or []

    for accessory_query in accessories:
        accessory_item = find_item(accessory_items, "type", str(accessory_query))

        if accessory_item:
            low, high = parse_range(accessory_item.get("prix_jour_XAF"))
            add_line(
                f"Accessoire : {accessory_item.get('type')}",
                low,
                high,
                days,
                "jour",
                accessory_item.get("note"),
            )
        else:
            notes.append(f"Accessoire introuvable : {accessory_query}")

    # Groupe électrogène
    generator_query = params.get("generateur")
    if generator_query:
        generator_items = get_by_path(
            logistique,
            "realite_energetique.groupes_electrogenes.types_disponibles",
        ) or []

        generator_item = find_item(generator_items, "type", str(generator_query))

        if generator_item:
            low, high = parse_range(generator_item.get("prix_location_jour_XAF"))
            add_line(
                f"Groupe électrogène : {generator_item.get('type')}",
                low,
                high,
                days,
                "jour",
                generator_item.get("usage"),
            )

            fuel_key = _choose_fuel_key(str(generator_item.get("type", "")))
            fuel_data = get_by_path(
                logistique,
                f"realite_energetique.cout_carburant_12h_tournage.{fuel_key}",
            )

            if fuel_data:
                fuel_low, fuel_high = parse_range(fuel_data.get("cout_XAF"))
                add_line(
                    f"Carburant groupe électrogène ({fuel_key})",
                    fuel_low,
                    fuel_high,
                    days,
                    "jour",
                    "Base 12h de tournage par jour.",
                )
        else:
            notes.append(f"Groupe électrogène introuvable : {generator_query}")

    # Transport groupe électrogène
    if generator_query and params.get("transport_generateur", True):
        zone_transport = params.get("zone_transport", "yaounde_peripherie_50km")
        transport_data = get_by_path(
            logistique,
            f"realite_energetique.transport_groupe_electrogene.{zone_transport}",
        )

        if isinstance(transport_data, dict):
            transport_value = transport_data.get("camionnette_pickup") or transport_data.get(
                "camion_5t",
                "0",
            )
            low, high = parse_range(transport_value)
            add_line(
                f"Transport groupe électrogène ({zone_transport})",
                low,
                high,
                1,
                "forfait",
                "Aller simple ; prévoir retour ou doublement si besoin.",
            )

    # Catering
    if params.get("include_catering", True):
        catering_query = params.get("catering", "mama")
        catering_options = get_by_path(couts, "catering_restauration.options") or []
        catering_item = find_item(catering_options, "type", str(catering_query))

        if catering_item:
            low, high = parse_range(catering_item.get("cout_par_personne_XAF"))
            add_line(
                f"Catering : {catering_item.get('type')}",
                low,
                high,
                crew * days,
                "personne/jour",
                catering_item.get("description"),
            )
        else:
            add_line(
                "Catering : minimum recommandé",
                3000,
                5000,
                crew * days,
                "personne/jour",
                "Option catering non trouvée : minimum recommandé appliqué.",
            )
    else:
        notes.append(
            "Catering non inclus. Attention : risque de démotivation ou de blocage équipe."
        )

    # Eau potable
    if params.get("include_water", True):
        water_price = get_by_path(
            couts,
            "catering_restauration.boissons_et_snacks.eau_minerale_1.5L",
        )
        low, high = parse_range(water_price)
        add_line(
            "Eau minérale 1.5L",
            low,
            high,
            crew * days * 2,
            "bouteille",
            "Base : 2 bouteilles de 1.5L par personne et par jour.",
        )

    # Protocole chefferie / village
    lieu_type = _norm_text(params.get("lieu_type", ""))

    if lieu_type in ["village", "rural", "chefferie"]:
        cadeaux = get_by_path(logistique, "protocole_chefferie.cadeaux_protocolaires") or []
        taille_chefferie = params.get("taille_chefferie", "village_moyen")

        for cadeau in cadeaux:
            cadeau_type = str(cadeau.get("type", ""))

            if any(
                keyword in cadeau_type
                for keyword in [
                    "Noix de kola",
                    "Boissons traditionnelles",
                ]
            ):
                low, high = parse_range(cadeau.get("cout_estime_XAF"))
                add_line(
                    f"Protocole chefferie : {cadeau_type}",
                    low,
                    high,
                    1,
                    "forfait",
                    cadeau.get("note"),
                )

            if "Enveloppe financière" in cadeau_type:
                envelope_value = cadeau.get("cout_estime_XAF")

                if isinstance(envelope_value, dict):
                    selected_value = envelope_value.get(
                        taille_chefferie,
                        envelope_value.get("village_moyen"),
                    )
                    low, high = parse_range(selected_value)
                else:
                    low, high = parse_range(envelope_value)

                add_line(
                    "Protocole chefferie : enveloppe / contribution",
                    low,
                    high,
                    1,
                    "forfait",
                    cadeau.get("note"),
                )

    # Marché / contribution vendeurs
    tags = params.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]

    market_flag = params.get("marche", False)
    market_in_tags = any("marche" in _norm_text(tag) for tag in tags)

    if market_flag or market_in_tags:
        add_line(
            "Contribution marché / accord vendeurs",
            20000,
            50000,
            1,
            "forfait",
            "À prévoir pour accord du président du marché ou chefs de section.",
        )

    # Autorisation MINAC optionnelle
    if params.get("autorisation_minac"):
        minac_fee = get_by_path(
            frictions,
            "autorisations_MINAC.types_autorisations.0.frais_estimes_XAF",
        )
        low, high = parse_range(minac_fee)
        add_line(
            "Autorisation MINAC (estimation)",
            low,
            high,
            1,
            "forfait",
            "Hors délais imprévus et frais de suivi.",
        )

    # Fixer / régisseur local optionnel
    if params.get("fixer_local") or params.get("fixer"):
        roles = get_by_path(couts, "humain.roles_cles") or []
        fixer_item = find_item(roles, "role", "Régisseur Général")

        if fixer_item:
            low, high = parse_range(fixer_item.get("cachet_jour_XAF"))
            add_line(
                "Régisseur / fixer local",
                low,
                high,
                days,
                "jour",
                fixer_item.get("note"),
            )

    eur_rate = get_by_path(logistique, "metadata.taux_change_approximatif.EUR") or 655.957
    eur_rate = float(eur_rate)

    return {
        "devise": "XAF",
        "low_XAF": round(total_low),
        "high_XAF": round(total_high),
        "low_EUR": round(total_low / eur_rate, 2),
        "high_EUR": round(total_high / eur_rate, 2),
        "jours_tournage": days,
        "equipe_personnes": crew,
        "lines": lines,
        "notes": notes,
    }


# ---------------------------------------------------------------------
# Analyse scène
# ---------------------------------------------------------------------

def analyze_scene(scene: Dict[str, Any], datasets: Dict[str, Any]) -> Dict[str, Any]:
    """Analyse une scène : alertes, risques, langue recommandée."""
    if not isinstance(scene, dict):
        scene = {"description": str(scene)}

    lieu = scene.get("lieu", {}) if isinstance(scene.get("lieu"), dict) else {}
    tags = scene.get("tags", []) or []

    if isinstance(tags, str):
        tags = [tags]

    text_parts = [
        str(scene.get("description", "")),
        str(lieu.get("type", "")),
        str(lieu.get("region", "")),
        str(scene.get("contexte", "")),
        " ".join(map(str, tags)),
    ]

    full_text = " ".join(text_parts)
    alerts = detect_alerts(full_text, datasets, tags)

    budget_params = scene.get("budget_params", {})
    if isinstance(budget_params, dict):
        if budget_params.get("include_catering") is False:
            alerts.append(
                {
                    "id": "budget:catering_manquant",
                    "level": "JAUNE",
                    "message": (
                        "ALERTE JAUNE : Budget sans ligne catering = risque de grève "
                        "de l'équipe ou de démotivation. Action requise : prévoir "
                        "minimum 3000 XAF/personne/repas."
                    ),
                    "source_dataset": "couts",
                    "trigger_keywords": ["catering"],
                }
            )

        lieu_type = _norm_text(lieu.get("type", ""))
        if lieu_type in ["village", "rural"] and budget_params.get("include_water") is False:
            alerts.append(
                {
                    "id": "budget:eau_manquante",
                    "level": "ROUGE",
                    "message": (
                        "ALERTE ROUGE : Zone rurale sans eau potable = risque sanitaire "
                        "majeur. Action requise : stocker 3L d'eau minérale/personne/jour."
                    ),
                    "source_dataset": "couts",
                    "trigger_keywords": ["eau"],
                }
            )

    return {
        "alerts": alerts,
        "language": recommend_language(scene, datasets),
    }


def build_llm_context(scene: Dict[str, Any], datasets: Dict[str, Any]) -> Dict[str, Any]:
    """Construit un contexte structuré pour LLM."""
    response: Dict[str, Any] = {
        "analysis": analyze_scene(scene, datasets),
    }

    if isinstance(scene.get("budget_params"), dict):
        response["budget"] = estimate_budget(scene["budget_params"], datasets)

    if scene.get("dialogue"):
        response["dialogue"] = camerounize_dialogue(
            str(scene.get("dialogue")),
            str(scene.get("contexte_dialogue", "quartier_populaire")),
            datasets,
        )

    return response


# ---------------------------------------------------------------------
# Hackathon tools
# ---------------------------------------------------------------------

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "analyze_scene",
            "description": (
                "Analyse une scène de tournage au Cameroun et retourne les alertes IA, "
                "les risques culturels, administratifs, logistiques, ainsi que les "
                "recommandations linguistiques."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "scene": {
                        "type": "object",
                        "description": "Scène de tournage à analyser.",
                    }
                },
                "required": ["scene"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "estimate_budget",
            "description": (
                "Estime un budget de tournage au Cameroun en XAF à partir des datasets locaux."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "jours_tournage": {"type": "number"},
                    "equipe_personnes": {"type": "integer"},
                    "camera": {"type": "string"},
                    "son": {"type": "string"},
                    "eclairage": {"type": "string"},
                    "generateur": {"type": "string"},
                    "catering": {"type": "string"},
                    "lieu_type": {"type": "string"},
                    "taille_chefferie": {"type": "string"},
                    "marche": {"type": "boolean"},
                    "transport_generateur": {"type": "boolean"},
                    "zone_transport": {"type": "string"},
                    "autorisation_minac": {"type": "boolean"},
                    "fixer_local": {"type": "boolean"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "camerounize_dialogue",
            "description": (
                "Camérounise un dialogue en proposant du pidgin english, du camfranglais "
                "ou des expressions locales selon le contexte."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "contexte": {"type": "string"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "build_llm_context",
            "description": (
                "Construit un contexte complet pour un LLM : analyse de scène, budget, "
                "dialogue, alertes et recommandations culturelles."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "lieu": {"type": "object"},
                    "budget_params": {"type": "object"},
                    "dialogue": {"type": "string"},
                    "contexte_dialogue": {"type": "string"},
                },
            },
        },
    },
]


def get_trace(datasets: Dict[str, Any]) -> Dict[str, Any]:
    """Traçabilité des datasets utilisés."""
    trace: Dict[str, Any] = {}

    for dataset_key, dataset in datasets.items():
        metadata = dataset.get("metadata", {}) if isinstance(dataset, dict) else {}

        trace[dataset_key] = {
            "nom": metadata.get("nom"),
            "version": metadata.get("version"),
            "date_generation": metadata.get("date_generation"),
            "niveau_confiance_global": metadata.get("niveau_confiance_global"),
            "source_recherche": metadata.get("source_recherche"),
        }

    return trace


def execute_tool(
    name: str,
    arguments: Dict[str, Any],
    datasets: Dict[str, Any],
) -> Dict[str, Any]:
    """Exécute un outil agentique."""
    arguments = arguments or {}

    try:
        if name == "analyze_scene":
            scene = arguments.get("scene", arguments)
            result = analyze_scene(scene, datasets)

        elif name == "estimate_budget":
            result = estimate_budget(arguments, datasets)

        elif name == "camerounize_dialogue":
            result = camerounize_dialogue(
                arguments.get("text", ""),
                arguments.get("contexte", "quartier_populaire"),
                datasets,
            )

        elif name == "build_llm_context":
            result = build_llm_context(arguments, datasets)

        else:
            return {
                "status": "error",
                "tool": name,
                "error": f"Outil inconnu : {name}",
            }

        return {
            "status": "success",
            "tool": name,
            "result": result,
            "trace": get_trace(datasets),
        }

    except Exception as exc:
        return {
            "status": "error",
            "tool": name,
            "error": str(exc),
        }


# ---------------------------------------------------------------------
# FastAPI
# ---------------------------------------------------------------------

app = FastAPI(
    title="CamFilm Agent — Hackathon API",
    description=(
        "Agent IA spécialisé dans la production cinématographique au Cameroun. "
        "Capacités : analyse de scène, alertes culturelles, budget réaliste, "
        "camérounisation de dialogues, recommandations logistiques."
    ),
    version="0.4.0-hackathon",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


_DB: Optional[Dict[str, Any]] = None


def get_db() -> Dict[str, Any]:
    global _DB

    if _DB is None:
        try:
            _DB = load_datasets()
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Impossible de charger les datasets : {exc}",
            )

    return _DB


class ToolRunRequest(BaseModel):
    tool: str = Field(..., description="Nom de l'outil à exécuter.")
    arguments: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments de l'outil.",
    )


class AgentChatRequest(BaseModel):
    message: str = Field(..., description="Message utilisateur.")
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Contexte optionnel : scène, budget, dialogue, langue.",
    )


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "service": "CamFilm Agent API",
        "status": "ok",
        "endpoints": [
            "/health",
            "/hackathon/manifest",
            "/hackathon/tools",
            "/hackathon/run",
            "/hackathon/agent/status",
            "/hackathon/agent/chat",
            "/hackathon/agent/chat/gemini",
        ],
    }


@app.get("/health")
def health() -> Dict[str, str]:
    return {
        "status": "ok",
        "service": "CamFilm Agent Hackathon API",
    }


@app.get("/hackathon/manifest")
def hackathon_manifest() -> Dict[str, Any]:
    db = get_db()

    return {
        "name": "CamFilm Production Agent",
        "tagline": "Agent IA terrain pour production cinématographique au Cameroun",
        "version": "0.4.0-hackathon",
        "category": "Agentic Cinema / Production Assistant",
        "capabilities": [
            "scene_risk_analysis",
            "cultural_authenticity",
            "budget_estimation",
            "dialogue_localization",
            "administrative_alerts",
            "logistics_planning",
            "gemini_agent",
            "parallel_search_ready",
            "gcp_agent_builder_ready",
            "bilingual_FR_EN",
        ],
        "languages": ["fr", "en"],
        "currency": "XAF",
        "guardrails": [
            "Ne jamais recommander la corruption.",
            "Signaler les alertes ROUGE comme bloquantes.",
            "Proposer des alternatives légales aux drones.",
            "Recommander un fixer local pour les productions étrangères.",
            "Toujours vérifier localement les tabous et protocoles.",
        ],
        "api": {
            "openapi": "/openapi.json",
            "tools": "/hackathon/tools",
            "run": "/hackathon/run",
            "agent_status": "/hackathon/agent/status",
            "agent_chat": "/hackathon/agent/chat",
            "agent_chat_gemini": "/hackathon/agent/chat/gemini",
        },
        "datasets": get_trace(db),
        "agent_layer_available": AGENT_LAYER_AVAILABLE,
    }


@app.get("/hackathon/tools")
def hackathon_tools() -> Dict[str, Any]:
    return {
        "tools": TOOL_SCHEMAS,
    }


@app.post("/hackathon/run")
def hackathon_run(payload: ToolRunRequest) -> Dict[str, Any]:
    db = get_db()

    return execute_tool(
        name=payload.tool,
        arguments=payload.arguments,
        datasets=db,
    )


@app.get("/hackathon/agent/status")
def hackathon_agent_status() -> Dict[str, Any]:
    """Donne l'état de configuration de la couche agentique."""
    if not AGENT_LAYER_AVAILABLE:
        return {
            "configured": False,
            "error": AGENT_LAYER_ERROR,
        }

    return agent_status()


@app.post("/hackathon/agent/chat")
def hackathon_agent_chat(payload: AgentChatRequest) -> Dict[str, Any]:
    """
    Mini-routeur agentique déterministe.
    Utile pour démo sans dépendre d'un LLM payant.
    """
    db = get_db()
    context = payload.context or {}
    message = payload.message.lower()

    selected_tool = "build_llm_context"
    arguments: Dict[str, Any] = {}
    example: Dict[str, Any] = {}

    # Budget intent
    if any(
        keyword in message
        for keyword in [
            "budget",
            "cout",
            "coût",
            "prix",
            "estimation",
            "combien",
            "argent",
        ]
    ):
        selected_tool = "estimate_budget"
        arguments = context.get("budget_params", context)

        example = {
            "tool": "estimate_budget",
            "arguments": {
                "jours_tournage": 2,
                "equipe_personnes": 20,
                "camera": "Sony FX3",
                "son": "Kit son complet",
                "eclairage": "Kit LED 3 panneaux",
                "generateur": "Groupe diesel moyen",
                "catering": "Mama du quartier",
                "lieu_type": "village",
            },
        }

        if not arguments:
            return {
                "status": "need_arguments",
                "selected_tool": selected_tool,
                "message": "Pour estimer un budget, fournis des paramètres de tournage.",
                "example": example,
            }

    # Dialogue intent
    elif any(
        keyword in message
        for keyword in [
            "dialogue",
            "langue",
            "pidgin",
            "camfranglais",
            "réplique",
            "replique",
            "parle",
            "camerounise",
        ]
    ):
        selected_tool = "camerounize_dialogue"

        arguments = {
            "text": context.get("dialogue", payload.message),
            "contexte": context.get("contexte_dialogue", "quartier_populaire"),
        }

        example = {
            "tool": "camerounize_dialogue",
            "arguments": {
                "text": "Bonjour monsieur, comment allez-vous ? Je voudrais acheter ce produit. Combien coûte-t-il ?",
                "contexte": "marche_douala",
            },
        }

    # Scene / risk intent
    elif any(
        keyword in message
        for keyword in [
            "scene",
            "scène",
            "risque",
            "alerte",
            "tournage",
            "tabou",
            "drone",
            "village",
            "marche",
            "chef",
            "chefferie",
        ]
    ):
        selected_tool = "analyze_scene"

        if context:
            arguments = {"scene": context}
        else:
            arguments = {
                "scene": {
                    "description": payload.message,
                }
            }

        example = {
            "tool": "analyze_scene",
            "arguments": {
                "scene": {
                    "description": "Tournage d'une scène de marché à Douala avec drone et enfants.",
                    "tags": ["marche", "drone", "enfants"],
                    "lieu": {
                        "type": "marche",
                        "region": "Littoral",
                    },
                }
            },
        }

    # Default context builder
    else:
        selected_tool = "build_llm_context"

        if context:
            arguments = context
        else:
            arguments = {
                "description": payload.message,
            }

        example = {
            "tool": "build_llm_context",
            "arguments": {
                "description": "Scène de village dans l'Ouest avec cérémonie traditionnelle.",
                "tags": ["village", "ouest", "rituel"],
                "lieu": {
                    "type": "village",
                    "region": "Ouest",
                },
            },
        }

    result = execute_tool(
        name=selected_tool,
        arguments=arguments,
        datasets=db,
    )

    return {
        "status": result.get("status"),
        "selected_tool": selected_tool,
        "agent_message": (
            "J'ai analysé ta demande avec CamFilm Agent. "
            "Voici le résultat structuré."
        ),
        "response": result,
        "example_if_missing": example,
    }


@app.post("/hackathon/agent/chat/gemini")
def hackathon_agent_chat_gemini(payload: AgentChatRequest) -> Dict[str, Any]:
    """
    Version agentique avec Gemini.

    Elle utilise :
    - les datasets locaux CamFilm
    - Gemini
    - Parallel Search API si configuré
    - Google Cloud Agent Builder si configuré
    - Support bilingue FR/EN via le paramètre `language` dans le contexte
    """
    if not AGENT_LAYER_AVAILABLE:
        raise HTTPException(
            status_code=500,
            detail=f"agent_layer indisponible : {AGENT_LAYER_ERROR}",
        )

    db = get_db()

    return run_agent(
        message=payload.message,
        context=payload.context or {},
        datasets=db,
        execute_tool_fn=execute_tool,
        use_parallel=True,
        use_gcp=bool(os.getenv("GCP_AGENT_BUILDER_URL")),
    )


# ---------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)