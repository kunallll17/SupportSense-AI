from fastapi import APIRouter, HTTPException, Depends
from elasticsearch import Elasticsearch

from app.models import TriageRequest, TriageResponse
from app.services.elasticsearch import get_es_client
from app.services.agent import run_triage_agent

router = APIRouter(prefix="/triage", tags=["Triage"])


@router.post("/", response_model=TriageResponse, summary="Triage a support ticket")
def triage_ticket(
    payload: TriageRequest,
    es: Elasticsearch = Depends(get_es_client),
):
    """
    Triage a support ticket using multi-step AI reasoning.

    **Pipeline:**
    1. Hybrid search (BM25 + kNN) to find similar historical cases
    2. Aggregation check for trend spikes in last 24h
    3. Gemini LLM classifies issue, determines severity + escalation
    4. Returns structured JSON decision

    **Filters:** Customer tier is used to bias retrieval toward same-tier cases.
    """
    try:
        result = run_triage_agent(
            es=es,
            title=payload.title,
            description=payload.description,
            customer_tier=payload.customer_tier,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")
