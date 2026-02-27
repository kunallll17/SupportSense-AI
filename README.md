# SupportSense AI 🧠

> **AI-Powered Customer Support Triage Agent** — Elasticsearch Hackathon 2026

An intelligent support triage system that combines **Elasticsearch hybrid search** (BM25 + kNN) with **Gemini AI** to automatically classify, prioritize, and route support tickets in real-time.

---

## 🏗️ Architecture

```
New Ticket (POST /triage)
       │
       ▼
┌─────────────────────┐
│  Embedding Service  │  ← Gemini gemini-embedding-001 (3072 dims)
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│   Hybrid Search     │  ← BM25 + kNN via RRF (Elasticsearch 9.x)
│   (ES RRF)          │  ← Filter by customer_tier
└─────────┬───────────┘
          │ Top-5 similar cases
          ▼
┌─────────────────────┐
│  Aggregation Check  │  ← 24h spike detection (terms + date_histogram)
└─────────┬───────────┘
          │ recurring_flag
          ▼
┌─────────────────────┐
│  Gemini 2.5-flash   │  ← Multi-step reasoning with full context
│  Agent Reasoning    │  ← response_mime_type=application/json
└─────────┬───────────┘
          │
          ▼
  Structured JSON Decision
  { issue_type, severity, escalation_level,
    recommended_response, similar_cases,
    recurring_issue_flag, reasoning_steps }
```

---

## ⚡ Tech Stack

| Component | Technology |
|---|---|
| **API** | FastAPI + Uvicorn |
| **Search** | Elasticsearch 9.3.1 (Cloud) |
| **Embeddings** | Gemini `gemini-embedding-001` (3072 dims) |
| **LLM** | Gemini `gemini-2.5-flash` |
| **SDK** | `google-genai` |
| **Config** | `pydantic-settings` |

---

## 📁 Project Structure

```
├── app/
│   ├── main.py                      # FastAPI entry point (6 routers)
│   ├── config.py                    # Settings (pydantic-settings)
│   ├── models.py                    # Request/Response schemas
│   ├── services/
│   │   ├── elasticsearch.py         # ES client + index schema
│   │   ├── embeddings.py            # Gemini embedding service
│   │   ├── hybrid_search.py         # BM25 + kNN RRF retrieval
│   │   ├── aggregations.py          # Trend detection (24h aggs)
│   │   ├── agent.py                 # Multi-step triage agent
│   │   ├── analytics.py             # 24h analytics aggregations
│   │   ├── confidence.py            # Confidence scoring engine
│   │   └── explain.py               # Explainability (no-LLM preview)
│   └── routers/
│       ├── ingest.py                # POST /ingest/
│       ├── triage.py                # POST /triage/
│       ├── trends.py                # GET /trends/
│       ├── analytics.py             # GET /analytics/
│       ├── triage_confidence.py     # POST /triage_with_confidence/
│       └── explain.py               # POST /explain_preview/
├── scripts/
│   └── seed_data.py                 # Bulk ingest + spike injection
├── data/
│   └── sample_tickets.json          # 25 realistic support tickets
├── setup_index.py                   # One-time ES index creation
├── .env.example
└── requirements.txt
```

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.11+
- Elasticsearch Cloud cluster (free tier works)
- Google AI Studio API key (free — [aistudio.google.com](https://aistudio.google.com))

### 2. Setup

```bash
# Clone and create virtual environment
git clone <repo>
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your keys
```

### 3. Configure `.env`

```env
ELASTICSEARCH_URL=https://your-cluster.es.io:443
ELASTIC_API_KEY=your_elastic_api_key
GOOGLE_API_KEY=your_gemini_api_key
```

### 4. Create Index & Seed Data

```bash
# Create Elasticsearch index
python setup_index.py

# Ingest 25 sample tickets + inject authentication spike
python scripts/seed_data.py
```

### 5. Run the API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000/docs** for the interactive Swagger UI.

---

## 🔌 API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/ingest/` | POST | Ingest a new ticket with Gemini embedding |
| `/triage/` | POST | Core triage: hybrid search + trend + LLM reasoning |
| `/trends/` | GET | 24h ticket volume, severity breakdown, spike detection |
| `/analytics/` | GET | Ops dashboard: P1 count, escalation distribution, recurring % |
| `/triage_with_confidence/` | POST | Triage + confidence score (0–100) with breakdown |
| `/explain_preview/` | POST | Explainability preview — no LLM, pure retrieval transparency |

### `POST /triage/` — Core triage endpoint

```bash
curl -X POST http://localhost:8000/triage/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Users locked out after password reset",
    "description": "Multiple users cannot log in after password reset via email link. Error: invalid credentials. Tried multiple browsers.",
    "customer_tier": "enterprise"
  }'
```

**Response:**
```json
{
  "issue_type": "authentication",
  "severity": "P2",
  "escalation_level": "L2",
  "recommended_response": "We've identified this as a known authentication issue...",
  "similar_cases": [...],
  "recurring_issue_flag": true,
  "reasoning_steps": [
    "Retrieved 5 similar historical tickets via hybrid search (BM25 + kNN RRF)",
    "Trend check: issue_type='authentication' | recurring_spike=true",
    "..."
  ]
}
```

### `POST /triage_with_confidence/` — Triage + confidence scoring

Same input as `/triage/`, returns the full `TriageResponse` **plus**:

```json
{
  "confidence_score": 78.5,
  "confidence_label": "high",
  "confidence_breakdown": {
    "similar_cases_score": 35.0,
    "similarity_quality_score": 22.4,
    "recurring_trend_score": 15.0,
    "reasoning_depth_score": 6.1
  }
}
```

### `POST /explain_preview/` — Explainability (no LLM)

Runs only hybrid search — fast, transparent, zero LLM cost:

```json
{
  "guessed_issue_type": "authentication",
  "similar_cases": [...],
  "average_similarity_score": 0.031270,
  "issue_type_distribution": {"authentication": 4, "permissions": 1},
  "recurring_spike_detected": true,
  "explanation_summary": "Based on hybrid search (BM25 + kNN RRF), the top-5 similar historical tickets suggest this is a 'authentication' issue..."
}
```

### `GET /analytics/` — Ops dashboard

```json
{
  "window_hours": 24,
  "total_tickets_24h": 12,
  "p1_ticket_count": 2,
  "escalation_distribution": [
    {"level": "L2", "count": 3},
    {"level": "L1", "count": 2},
    {"level": "unassigned", "count": 7}
  ],
  "recurring_issue_count": 4,
  "recurring_issue_percentage": 33.33,
  "generated_at": "2026-02-27T16:41:09Z"
}
```

### `GET /trends/` — Real-time trend detection

```json
{
  "window_hours": 24,
  "total_tickets": 8,
  "spike_threshold": 3,
  "trends": [
    {"issue_type": "authentication", "count": 6, "is_spike": true},
    {"issue_type": "payment", "count": 1, "is_spike": false}
  ]
}
```

---

## 🔍 Elasticsearch Schema

```json
{
  "mappings": {
    "properties": {
      "ticket_id":          { "type": "keyword" },
      "title":              { "type": "text", "analyzer": "support_analyzer" },
      "description":        { "type": "text", "analyzer": "support_analyzer" },
      "description_vector": { "type": "dense_vector", "dims": 3072, "similarity": "cosine" },
      "issue_type":         { "type": "keyword" },
      "severity":           { "type": "keyword" },
      "customer_tier":      { "type": "keyword" },
      "status":             { "type": "keyword" },
      "created_at":         { "type": "date" }
    }
  }
}
```

**Custom analyzer:** `support_analyzer` — standard tokenizer + lowercase + stopwords + snowball stemming for superior BM25 recall.

---

## 🧠 Agent Reasoning Pipeline

The 4-step agent processes every triage request:

| Step | Action | ES Feature Used |
|---|---|---|
| **1** | Embed new ticket → hybrid search top-5 | `dense_vector` + `multi_match` + `rrf` retriever |
| **2** | Check if issue type is trending in 24h | `terms` aggregation + `range` filter |
| **3** | LLM classifies + reasons with full context | Gemini 2.5-flash (JSON mode) |
| **4** | Re-verify spike with LLM's refined classification | `count` API |

---

## 📊 Trend Detection

Uses three parallel aggregations in a single ES query:
- **`terms` on `issue_type`** — ranks by volume
- **`terms` on `severity`** — breakdown by priority  
- **`date_histogram` by hour** — volume over time

Any `issue_type` with ≥3 tickets in 24h is flagged as a **spike** → sets `recurring_issue_flag: true` in triage response.

---

## 🏆 Hackathon Highlights

- ✅ **Hybrid search** — ES 9.x native RRF (BM25 + kNN in one query)
- ✅ **Multi-step agent reasoning** — 4 steps, full audit trail in `reasoning_steps`
- ✅ **Enterprise realism** — customer tier filtering, severity matrix, escalation rules
- ✅ **Trend detection** — real-time aggregations with spike alerting
- ✅ **Confidence scoring** — 4-factor scoring engine (0–100) with per-component breakdown
- ✅ **Explainability** — no-LLM `/explain_preview/` endpoint for transparent retrieval reasoning
- ✅ **Analytics dashboard** — ops-ready 24h metrics: P1 count, escalation distribution, recurring %
- ✅ **Structured output** — guaranteed JSON via Gemini `response_mime_type`
- ✅ **Production patterns** — pydantic settings, lifespan handlers, proper error codes
- ✅ **Clean architecture** — services / routers / models separation
