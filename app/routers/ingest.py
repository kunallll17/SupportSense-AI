import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from elasticsearch import Elasticsearch

from app.models import TicketIngestRequest, TicketIngestResponse
from app.services.elasticsearch import get_es_client
from app.services.embeddings import get_embedding
from app.config import settings

router = APIRouter(prefix="/ingest", tags=["Ingestion"])


@router.post("/", response_model=TicketIngestResponse, summary="Ingest a support ticket")
def ingest_ticket(
    payload: TicketIngestRequest,
    es: Elasticsearch = Depends(get_es_client),
):
    """
    Ingest a new support ticket into Elasticsearch.

    - Generates a Gemini embedding for the combined title + description
    - Stores the full document with metadata for future hybrid search
    """
    ticket_id = str(uuid.uuid4())
    combined_text = f"{payload.title}\n\n{payload.description}"

    try:
        vector = get_embedding(combined_text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Embedding service error: {e}")

    doc = {
        "ticket_id": ticket_id,
        "title": payload.title,
        "description": payload.description,
        "description_vector": vector,
        "customer_tier": payload.customer_tier,
        "issue_type": payload.issue_type,
        "severity": payload.severity,
        "status": payload.status,
        "resolution_notes": payload.resolution_notes,
        "escalation_level": None,
        "recurring_issue_flag": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        es.index(index=settings.index_name, id=ticket_id, document=doc)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Elasticsearch error: {e}")

    return TicketIngestResponse(
        ticket_id=ticket_id,
        message="Ticket ingested and indexed successfully."
    )
