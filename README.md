# CamFilm Agent

An AI agent for film production planning in Cameroon.

CamFilm Agent helps producers analyze shooting scenes, detect cultural, administrative and logistical risks, estimate realistic budgets in XAF, and localize dialogues into Pidgin English, Camfranglais and regional languages.

Built for the Agentic Cinema hackathon (Parallel track).

---

## The Problem

International and local film productions in Cameroon frequently fail or face costly delays because of unknown local realities:

- Drone shooting is illegal without a specific CCAA authorization (1 to 3 months, often denied for sensitive areas).
- Village and chefferie protocols require formal procedures and contributions that foreign crews ignore.
- Checkpoints, MINAC authorizations and administrative frictions are unpredictable without local knowledge.
- There is no public, structured pricing data for equipment, crew, catering or logistics in XAF.

## The Solution

CamFilm Agent is an agentic system that combines:

1. A Gemini-powered reasoning layer that plans which tool to call.
2. Four unique local datasets built from field research on Cameroonian film production realities.
3. Real-time web verification through the Parallel Search API.
4. A Google Agent Development Kit (ADK) agent exposing the same tools through Google Cloud Agent Builder.
5. A bilingual (French / English) Streamlit interface for producers.

---

## Key Features

- Scene risk analysis with color-coded alerts (RED, ORANGE, YELLOW) triggered by keywords such as drone, market, village, ritual, checkpoint, children, sensitive topics.
- Budget estimation in XAF and EUR computed from real local cost datasets: cameras, sound, lighting, generators, fuel, catering, water, chefferie protocol, market contributions, fixer fees.
- Dialogue localization: Pidgin English, Camfranglais, Bamilike and Fulfulde / Hausa regional expressions, with usage rules per context.
- Real-time web search via Parallel Search API for up-to-date regulations.
- Bilingual FR/EN interface; the agent answers in the selected language while local cultural data remains authentic.
- Automatic retry handling for Gemini quota and overload errors (429 / 503).
- Deterministic fallback router that works even without an LLM.

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
|  3. Local tool execution (4 tools, 4 datasets)           |
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

- Gemini 2.5 Flash via the Google GenAI SDK
- Google Agent Development Kit (ADK) for Google Cloud Agent Builder
- Parallel Search API for runtime web search
- FastAPI for the tool and agent API
- Streamlit for the bilingual producer interface
- Python, httpx, pandas, python-dotenv

---

## Local Datasets

The core value of CamFilm Agent is its proprietary knowledge base, stored as four JSON files:

| File | Content |
|---|---|
| `dataset_logistique_village.json` | Village logistics, chefferie protocol, energy reality, road conditions, transport costs |
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

Terminal 1 - FastAPI backend:

```bash
python app.py
```

API documentation: `http://127.0.0.1:8000/docs`

Terminal 2 - Streamlit producer interface:

```bash
streamlit run interface.py
```

User interface: `http://localhost:8501`

Terminal 3 - Google ADK agent (Agent Builder):

```bash
cd camfilm_adk
set GOOGLE_API_KEY=your_gemini_key   # Windows
adk web --port 8001
```

Agent Builder UI: `http://localhost:8001`

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

The response contains the agent message, the selected plan, the tool result (alerts, languages, budget), the Parallel Search result and the dataset trace.

---

## Guardrails and Ethics

- The agent never recommends corruption; it always proposes legal alternatives.
- RED alerts are treated as blocking (for example: drone without CCAA authorization).
- Sensitive subjects (politics, anglophone crisis, sacred rituals) trigger caution and local verification advice.
- Foreign productions are always advised to hire a local fixer or regulator.
- Estimated figures are explicitly flagged as estimates that must be verified locally.

---

## Project Status and Roadmap

Completed:

- FastAPI tool API with four datasets
- Gemini agent layer with planning, retry and bilingual output
- Parallel Search API integration at runtime
- Google ADK agent with the same four tools
- Bilingual Streamlit interface

Planned:

- Deployment on Google Cloud Run
- Additional field data collected from real productions
- Producer testimonials and pilot tests
- English-native dataset expansion

---

## Hackathon

This project was built for Agentic Cinema on Devpost, Parallel track.

Requirements coverage:

- Gemini: reasoning and final answer generation
- Google Cloud Agent Builder: agent implemented with the Google Agent Development Kit
- Parallel: Search API called at runtime for regulation verification
- Hosted application: local development stack, Cloud Run deployment planned

---

## License

MIT License. See the LICENSE file.

## Author

Aymar Mbassi - CamFilm Agent, Cameroon