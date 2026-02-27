from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from elasticsearch import Elasticsearch

from app.models import TriageRequest, TriageResponse, SimilarCase
from app.services.elasticsearch import get_es_client
from app.services.agent import run_triage_agent
from app.services.confidence import compute_confidence


# ── Response Models ──────────────────────────────────────────────────────────

class ConfidenceBreakdown(BaseModel):
    similar_cases_score: float = Field(..., description="Points from number of similar cases (max 35)")
    similarity_quality_score: float = Field(..., description="Points from match quality (max 35)")
    recurring_trend_score: float = Field(..., description="Points from trend confirmation (max 15)")
    reasoning_depth_score: float = Field(..., description="Points from reasoning depth (max 15)")


class TriageWithConfidenceResponse(TriageResponse):
    """Extends the standard TriageResponse with confidence scoring."""
    confidence_score: float = Field(
        ..., ge=0, le=100,
        description="Confidence score from 0 to 100"
    )
    confidence_label: str = Field(
        ...,
        description="Confidence level: very_high | high | medium | low | very_low"
    )
    confidence_breakdown: ConfidenceBreakdown = Field(
        ...,
        description="Detailed score breakdown by factor"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "issue_type": "authentication",
                "severity": "P2",
                "escalation_level": "L2",
                "recommended_response": "We've identified this as a known authentication issue...",
                "similar_cases": [
                    {
                        "ticket_id": "abc-123",
                        "title": "Cannot log in after password reset",
                        "issue_type": "authentication",
                        "severity": "P2",
                        "resolution_notes": "Session token cache not cleared.",
                        "score": 0.032
                    }
                ],
                "recurring_issue_flag": True,
                "reasoning_steps": [
                    "Retrieved 5 similar tickets via hybrid search",
                    "Trend check: recurring_spike=true"
                ],
                "confidence_score": 78.5,
                "confidence_label": "high",
                "confidence_breakdown": {
                    "similar_cases_score": 35.0,
                    "similarity_quality_score": 22.4,
                    "recurring_trend_score": 15.0,
                    "reasoning_depth_score": 6.1
                }
            }
        }
    }


# ── Router ───────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/triage_with_confidence", tags=["Triage + Confidence"])


@router.post(
    "/",
    response_model=TriageWithConfidenceResponse,
    summary="Triage a ticket with confidence scoring",
)
def triage_with_confidence(
    payload: TriageRequest,
    es: Elasticsearch = Depends(get_es_client),
):
    """
    Enhanced triage endpoint that wraps the standard triage agent
    and adds a **confidence score** (0–100) to the response.

    **Confidence is computed from 4 factors:**
    1. **Similar cases count** (35%) — more historical matches = higher confidence
    2. **Similarity quality** (35%) — stronger RRF match scores = better signal
    3. **Recurring trend** (15%) — spike detection confirms the classification
    4. **Reasoning depth** (15%) — more reasoning steps = more thorough analysis

    **Labels:**
    - `very_high` (85–100) | `high` (70–84) | `medium` (50–69) | `low` (30–49) | `very_low` (0–29)

    Uses the same input as `POST /triage/` — drop-in replacement with extra insight.
    """
    try:
        # Step 1: Run the existing triage agent (unchanged)
        triage_result = run_triage_agent(
            es=es,
            title=payload.title,
            description=payload.description,
            customer_tier=payload.customer_tier,
        )

        # Step 2: Compute confidence score on top of the result
        confidence = compute_confidence(triage_result)

        # Step 3: Return enriched response
        return TriageWithConfidenceResponse(
            # All original triage fields
            issue_type=triage_result.issue_type,
            severity=triage_result.severity,
            escalation_level=triage_result.escalation_level,
            recommended_response=triage_result.recommended_response,
            similar_cases=triage_result.similar_cases,
            recurring_issue_flag=triage_result.recurring_issue_flag,
            reasoning_steps=triage_result.reasoning_steps,
            # New confidence fields
            confidence_score=confidence["confidence_score"],
            confidence_label=confidence["confidence_label"],
            confidence_breakdown=ConfidenceBreakdown(
                **confidence["confidence_breakdown"]
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")
