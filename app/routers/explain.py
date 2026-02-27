from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict
from elasticsearch import Elasticsearch

from app.models import TriageRequest
from app.services.elasticsearch import get_es_client
from app.services.explain import generate_explain_preview


# ── Response Models ──────────────────────────────────────────────────────────

class ExplainSimilarCase(BaseModel):
    ticket_id: str = Field(..., description="Unique ID of the matched historical ticket")
    title: str = Field(..., description="Title of the matched ticket")
    issue_type: str = Field(..., description="Issue category of the matched ticket")
    severity: str = Field(..., description="Severity level (P1–P4)")
    score: float = Field(..., description="RRF hybrid search relevance score")


class ExplainPreviewResponse(BaseModel):
    guessed_issue_type: str = Field(
        ..., description="Most likely issue type based on similar historical cases"
    )
    similar_cases: List[ExplainSimilarCase] = Field(
        ..., description="Top 3 most similar historical tickets"
    )
    average_similarity_score: float = Field(
        ..., description="Mean RRF score across top-5 results"
    )
    issue_type_distribution: Dict[str, int] = Field(
        ..., description="Frequency of each issue_type among top-5 similar cases"
    )
    recurring_spike_detected: bool = Field(
        ..., description="True if guessed issue type has ≥3 tickets in last 24h"
    )
    explanation_summary: str = Field(
        ..., description="Human-readable explanation of the classification reasoning"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "guessed_issue_type": "authentication",
                "similar_cases": [
                    {
                        "ticket_id": "abc-123",
                        "title": "Cannot log in after password reset",
                        "issue_type": "authentication",
                        "severity": "P2",
                        "score": 0.032258
                    },
                    {
                        "ticket_id": "def-456",
                        "title": "SSO login loop — redirect keeps cycling",
                        "issue_type": "authentication",
                        "severity": "P1",
                        "score": 0.031250
                    },
                    {
                        "ticket_id": "ghi-789",
                        "title": "2FA OTP codes not working",
                        "issue_type": "authentication",
                        "severity": "P2",
                        "score": 0.030303
                    }
                ],
                "average_similarity_score": 0.031270,
                "issue_type_distribution": {
                    "authentication": 4,
                    "permissions": 1
                },
                "recurring_spike_detected": True,
                "explanation_summary": (
                    "Based on hybrid search (BM25 + kNN RRF), the top-5 similar historical tickets "
                    "suggest this is a 'authentication' issue. "
                    "Primary guess is 'authentication' with 4/5 matches. "
                    "⚠️ SPIKE DETECTED: 'authentication' has ≥3 tickets in the last 24h. "
                    "Average similarity score: 0.0313."
                )
            }
        }
    }


# ── Router ───────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/explain_preview", tags=["Explainability"])


@router.post(
    "/",
    response_model=ExplainPreviewResponse,
    summary="Preview triage classification with explainability",
)
def explain_preview(
    payload: TriageRequest,
    es: Elasticsearch = Depends(get_es_client),
):
    """
    Lightweight explainability endpoint — **no LLM involved**.

    Runs the same hybrid search (BM25 + kNN RRF) as the full triage agent,
    then returns a transparent breakdown of *why* the system would classify
    the ticket the way it does:

    - **guessed_issue_type** — most common issue type among top-5 similar cases
    - **similar_cases** — top 3 matches with scores
    - **average_similarity_score** — mean RRF score (higher = better match)
    - **issue_type_distribution** — frequency count across top-5
    - **recurring_spike_detected** — trend check via ES count aggregation
    - **explanation_summary** — human-readable reasoning summary

    Use this to preview and understand triage decisions before calling
    the full `/triage/` or `/triage_with_confidence/` endpoints.
    """
    try:
        data = generate_explain_preview(
            es=es,
            title=payload.title,
            description=payload.description,
            customer_tier=payload.customer_tier,
        )
        return ExplainPreviewResponse(
            guessed_issue_type=data["guessed_issue_type"],
            similar_cases=[
                ExplainSimilarCase(**c)
                for c in data["similar_cases"]
            ],
            average_similarity_score=data["average_similarity_score"],
            issue_type_distribution=data["issue_type_distribution"],
            recurring_spike_detected=data["recurring_spike_detected"],
            explanation_summary=data["explanation_summary"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Explain preview error: {e}")
