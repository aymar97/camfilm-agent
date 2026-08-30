Ah oui, tu as raison ! Voici le **README complet** avec la section **Deployment Streamlit Cloud** et le lien de l'app live bien mis en avant. Copie-colle tout :

```markdown
# CamFilm Agent

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_red.svg)](https://camfilm-agent.streamlit.app/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Gemini](https://img.shields.io/badge/Gemini-2.5_Flash-blueviolet)](https://ai.google.dev/)

An AI agent for film production planning in Cameroon.

CamFilm Agent helps producers analyze shooting scenes, detect cultural, administrative and logistical risks, estimate realistic budgets in XAF, generate detailed storyboards, and localize dialogues into Pidgin English, Camfranglais and regional languages.

Built for the Agentic Cinema hackathon (Parallel track).

👉 **[Try the live demo: https://camfilm-agent.streamlit.app/](https://camfilm-agent.streamlit.app/)**

---

## The Problem

International and local film productions in Cameroon frequently fail or face costly delays because of unknown local realities:

- **Drone shooting is illegal** without a specific CCAA authorization (1 to 3 months, often denied for sensitive areas).
- **Village and chefferie protocols** require formal procedures and contributions that foreign crews ignore.
- **Checkpoints, MINAC authorizations** and administrative frictions are unpredictable without local knowledge.
- **No public, structured pricing data** exists for equipment, crew, catering or logistics in XAF.
- **Inauthentic dialogues** break immersion when written in standard French instead of Pidgin or Camfranglais.

The result? Confiscated equipment, blocked shootings, blown budgets, and culturally inappropriate content.

## The Solution

CamFilm Agent is an agentic system that combines:

1. A **Gemini-powered reasoning layer** that plans which tool to call.
2. **Four unique local datasets** built from field research on Cameroonian film production realities.
3. **Real-time web verification** through the Parallel Search API.
4. A **Google Agent Development Kit (ADK)** agent exposing the same tools through Google Cloud Agent Builder.
5. A **bilingual (French / English) Streamlit interface** for producers.

---

## Key Features

- 🚨 **Scene risk analysis** with color-coded alerts (RED, ORANGE, YELLOW) triggered by keywords such as *drone, market, village, ritual, checkpoint, children, sensitive topics*.
- 💰 **Budget estimation in XAF and EUR** computed from real local cost datasets: cameras, sound, lighting, generators, fuel, catering, water, chefferie protocol, market contributions, fixer fees.
- 🎬 **Technical storyboard generation** with shot types, durations, sound recommendations and legal alternatives (crane, telescopic pole, elevated building) when drones are not allowed.
- 🎛️ **Post-production guidance**: color grading LUTs for African skin tones (Kodak 2383, African Skin Tones), sound design with iZotope RX, LUFS normalization for web and CRTV broadcast, local post-prod providers in Yaoundé and Douala.
- 🗣️ **Dialogue localization**: Pidgin English, Camfranglais, Bamiléké and Fulfulde / Hausa regional expressions, with usage rules per context.
- 🔍 **Real-time web search** via Parallel Search API for up-to-date regulations (CCAA, MINAC).
- 🌍 **Bilingual FR/EN interface**: the agent answers in the selected language while local cultural data remains authentic.
- 🔄 **Automatic retry handling** for Gemini quota and overload errors (429 / 503).
- 🛟 **Deterministic fallback router** that works even without an LLM.

---

## Sample Output

Here is a real excerpt of an analysis generated for a *"5-day documentary shoot in a Bamiléké village with drone"*:

> **🔴 RED ALERT N°1: Drone usage (CCAA)**
> Drone flying is illegal without authorization. The procedure takes 1-3 months and is often denied for sensitive areas. Strong recommendation: use alternatives (crane, telescopic pole, elevated building).
>
> **🔴 RED ALERT N°2: Chefferie Protocol**
> Shooting without protocol with the village chief (Fô) = risk of blocked shoot, equipment confiscation, or crew aggression. Contact the chief BEFORE arriving on site.
>
> **💰 Estimated budget: 595,000 - 1,270,000 XAF** (907 - 1,936 EUR)
> Including: Sony FX3 rental, "Mama du quartier" catering, chefferie protocol (kola nuts, traditional drinks, contribution envelope).
>
> **🎬 Storyboard**: 5 shot types covering 70 minutes of footage, with sound recommendations.
> **🎛️ Post-prod**: LUT "African Skin Tones", iZotope RX for wind/generator noise, -12 LUFS for web / -23 LUFS for CRTV.

---

## Architecture

```
+------------------------+        +-------------------------+
|  Streamlit UI (FR/EN)  |        |  Google ADK Web UI      |
|  localhost:8501        |        |  localhost:8001         |
+-----------+------------+        +------------+------------+
            | HTTP                             | tools
            v                                  v
+----------------------------------------------------------+
|                    FastAPI application                   |
|              localhost:8000  (/docs for Swagger)         |
+---------------------------+------------------------------+
                            |
                            v
+----------------------------------------------------------+
|               agent_layer.py (orchestration)             |
|  1. Gemini planning (tool selection)                     |
|  2. Parallel Search API (real-time web, when needed)     |
|  3. Local tool execution (6 tools, 4 datasets)           |
|  4. Gemini final structured answer (FR or EN)            |
+------------+-----------------------------+---------------+
             |                             |
             v                             v
+-------------------------+     +--------------------------+
| 4 local JSON datasets   |     | Parallel Search API      |
| (Cameroon field data)   |     | api.parallel.ai          |
+-------------------------+     +--------------------------+
```

---

## Tech Stack

- **Gemini 2.5 Flash** via the Google GenAI SDK
- **Google Agent Development Kit (ADK)** for Google Cloud Agent Builder
- **Parallel Search API** for runtime web search
- **FastAPI** for the tool and agent API
- **Streamlit** for the bilingual producer interface
- Python, httpx, pandas, python-dotenv

---

## Local Datasets

The core value of CamFilm Agent is its **proprietary knowledge base**, stored as four JSON files:

| File | Content |
|---|---|
| `dataset_logistique_village.json` | Village logistics, chefferie protocol, energy reality (Eneo), road conditions, transport costs |
| `dataset_couts_reels.json` | Real equipment prices, crew day rates, catering options, water and beverages in XAF |
| `dataset_frictions_admin.json` | MINAC authorizations, drone regulation (CCAA), police and gendarmerie checkpoints |
| `dataset_culture_langues.json` | Visual taboos, Pidgin English and Camfranglais examples, regional expressions, linguistic rules |

Each dataset includes metadata with version, generation date, confidence level and research sources, exposed through the API trace for transparency.

---

## Installation

### Prerequisites

- Python 3.10 or newer
- A Google AI Studio API key (Gemini)
- A Parallel Search API key

### Setup

```bash
git clone https://github.com/YOUR_USERNAME/camfilm-agent.git
cd camfilm-agent

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### Environment variables

Create a `.env` file at the project root (never commit it):

```env
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-2.5-flash

PARALLEL_API_KEY=your_parallel_key
PARALLEL_SEARCH_URL=https://api.parallel.ai/v1beta/search
PARALLEL_TIMEOUT=15
```

---

## Running the Application

The project exposes three interfaces. Open three terminals.

**Terminal 1 - FastAPI backend:**

```bash
python app.py
```

API documentation: `http://127.0.0.1:8000/docs`

**Terminal 2 - Streamlit producer interface:**

```bash
streamlit run interface.py
```

User interface: `http://localhost:8501`

**Terminal 3 - Google ADK agent (Agent Builder):**

```bash
cd camfilm_adk
set GOOGLE_API_KEY=your_gemini_key   # Windows
adk web --port 8001
```

Agent Builder UI: `http://localhost:8001`

---

## ☁️ Deployment on Streamlit Community Cloud

The app is **live** at: 👉 **https://camfilm-agent.streamlit.app/**

The file `cloud_app.py` is a **self-contained version** that calls the Gemini agent directly (no FastAPI server needed), which allows free hosting on Streamlit Community Cloud.

To deploy your own instance:

1. Push this repository to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) and click **New app**.
3. Configure:
   - **Main file path**: `cloud_app.py`
   - **Branch**: `main`
4. In **Advanced settings → Secrets**, add your keys:

```toml
GEMINI_API_KEY = "your_gemini_key"
GEMINI_MODEL = "gemini-2.5-flash"
PARALLEL_API_KEY = "your_parallel_key"
```

5. Click **Deploy**. The app **rebuilds automatically on every `git push`**.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/hackathon/manifest` | Project manifest, capabilities, guardrails, dataset trace |
| GET | `/hackathon/tools` | Tool schemas for external agents |
| POST | `/hackathon/run` | Execute a single tool directly |
| GET | `/hackathon/agent/status` | Configuration status of Gemini, Parallel, GCP |
| POST | `/hackathon/agent/chat` | Deterministic agent router (no LLM required) |
| POST | `/hackathon/agent/chat/gemini` | Full Gemini agent with Parallel Search and local tools |

### Example request

```json
POST /hackathon/agent/chat/gemini
{
  "message": "I want to shoot a market scene in Douala with a drone. 12 people, 2 days, small budget.",
  "context": {
    "description": "Market scene in Douala with drone",
    "tags": ["market", "drone", "small_budget"],
    "lieu": {"type": "marche", "region": "Littoral"},
    "budget_params": {
      "jours_tournage": 2,
      "equipe_personnes": 12,
      "camera": "Sony FX3",
      "lieu_type": "ville",
      "marche": true,
      "fixer_local": true
    },
    "language": "English"
  }
}
```

The response contains the agent message, the selected plan, the tool result (alerts, languages, budget, storyboard, post-production), the Parallel Search result and the dataset trace.

---

## Available Tools

| Tool | Description |
|---|---|
| `analyze_scene` | Detects risks (CCAA, MINAC, chefferie, taboos) and returns linguistic recommendations |
| `estimate_budget` | Computes realistic XAF budget from local cost datasets |
| `camerounize_dialogue` | Converts standard French into Pidgin, Camfranglais or regional expressions |
| `generate_storyboard` | Builds shot list with types, durations and sound recommendations |
| `post_production_advice` | Color grading LUTs, sound design (iZotope RX), local providers |
| `build_llm_context` | Proactive combo: analysis + budget + storyboard + post-prod in one call |

---

## Guardrails and Ethics

- The agent **never recommends corruption**; it always proposes legal alternatives.
- **RED alerts are treated as blocking** (for example: drone without CCAA authorization).
- **Sensitive subjects** (politics, anglophone crisis, sacred rituals) trigger caution and local verification advice.
- Foreign productions are **always advised to hire a local fixer** or regulator.
- Estimated figures are **explicitly flagged as estimates** that must be verified locally.

---

## Example Use Cases

### 🎥 Foreign producer arriving tomorrow
> *"I'm a French producer, landing in Cameroon tomorrow for a music video in Douala. 2 days, 6 people, drone, market and Kribi beach scenes. Give me everything."*

→ CamFilm Agent instantly flags CCAA drone risks and MINAC needs, generates a budget in XAF, builds a storyboard, provides Pidgin dialogues and lists post-prod providers in Douala.

### 🎬 Local director on a sensitive topic
> *"I'm shooting a documentary on Kwifon secret societies in the North-West."*

→ RED alerts on cultural taboos and anglophone crisis safety, recommendation to hire a local fixer and contact the chefferie beforehand.

### 🎓 Film student budgeting a short film
> *"How much for a 3-day short film with 10 people?"*

→ Detailed XAF budget with every line item, including "Mama du quartier" catering.

---

## Project Status

**Completed:**
- ✅ FastAPI tool API with four Cameroon-specific datasets
- ✅ Gemini agent layer with planning, retry and bilingual output
- ✅ Parallel Search API integration at runtime
- ✅ Google ADK agent with the same six tools
- ✅ Bilingual Streamlit interface (FR/EN)
- ✅ Live deployment on Streamlit Community Cloud

**Planned:**
- Migration to Google Cloud Run for production scale
- Additional field data collected from real productions
- Producer testimonials and pilot tests
- Support for more Cameroonian languages (Ewondo, Duala, Bassa)

---

## Hackathon

This project was built for **Agentic Cinema on Devpost** (Parallel track).

**Requirements coverage:**

- ✅ **Gemini**: reasoning and final answer generation
- ✅ **Google Cloud Agent Builder**: agent implemented with the Google Agent Development Kit
- ✅ **Parallel**: Search API called at runtime for regulation verification
- ✅ **Hosted application**: live on Streamlit Community Cloud, Cloud Run migration planned

---

## License

MIT License. See the [LICENSE](LICENSE) file.

---

## Author

**Aymar Mbassi** — CamFilm Agent, Cameroon 🇨

*Made with ❤️ for Cameroonian cinema. Saving productions, one alert at a time.*

---

<p align="center">
  <strong>🎬 CamFilm Agent — Your AI line producer for Cameroon</strong><br>
  <em>Pre-production • Shooting • Post-production</em><br>
  <a href="https://camfilm-agent.streamlit.app/">camfilm-agent.streamlit.app</a>
</p>
```

---
