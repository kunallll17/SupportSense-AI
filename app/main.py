from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.routers import ingest, triage, trends, analytics, triage_confidence, explain
from app.services.elasticsearch import get_es_client, create_index
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:\t%(name)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure the index exists on startup."""
    es = get_es_client()
    create_index(es)
    logger.info(f"SupportSense AI started | index={settings.index_name} | llm={settings.llm_model}")
    yield
    logger.info("SupportSense AI shutting down.")


app = FastAPI(
    title="SupportSense AI",
    description="""
## AI-Powered Customer Support Triage Agent

Uses **Elasticsearch hybrid search** (BM25 + kNN) combined with **Gemini AI** 
to automatically classify, prioritize, and route support tickets.

### Key Features
- 🔍 **Hybrid Search** — BM25 text relevance + semantic kNN via RRF
- 🧠 **Multi-step reasoning** — classify → severity → trend check → escalate
- 📊 **Trend detection** — ES aggregations flag recurring issues in real-time
- 🎯 **Customer tier filtering** — enterprise tickets matched to enterprise cases
    """,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router)
app.include_router(triage.router)
app.include_router(trends.router)
app.include_router(analytics.router)
app.include_router(triage_confidence.router)
app.include_router(explain.router)


@app.get("/", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "service": "SupportSense AI",
        "version": "1.0.0",
        "index": settings.index_name,
        "llm": settings.llm_model,
        "embedding_model": settings.embedding_model,
    }
