from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import List
from elasticsearch import Elasticsearch

from app.services.elasticsearch import get_es_client
from app.services.analytics import get_24h_analytics


# ── Response Models ──────────────────────────────────────────────────────────

class EscalationBucket(BaseModel):
    level: str = Field(..., description="Escalation level: auto-resolve | L1 | L2 | L3 | unassigned")
    count: int = Field(..., description="Number of tickets at this escalation level")


class AnalyticsResponse(BaseModel):
    window_hours: int = Field(24, description="Time window in hours")
    total_tickets_24h: int = Field(..., description="Total tickets created in the last 24 hours")
    p1_ticket_count: int = Field(..., description="Number of critical (P1) tickets in the last 24 hours")
    escalation_distribution: List[EscalationBucket] = Field(
        ..., description="Ticket count by escalation level"
    )
    recurring_issue_count: int = Field(..., description="Tickets flagged as recurring issues")
    recurring_issue_percentage: float = Field(
        ..., description="Percentage of tickets flagged as recurring (0-100)"
    )
    generated_at: str = Field(..., description="ISO timestamp when this report was generated")

    model_config = {
        "json_schema_extra": {
            "example": {
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
                "generated_at": "2026-02-27T13:35:08+00:00"
            }
        }
    }


# ── Router ───────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get(
    "/",
    response_model=AnalyticsResponse,
    summary="Get 24h support analytics dashboard",
)
def get_analytics(es: Elasticsearch = Depends(get_es_client)):
    """
    Real-time analytics dashboard for the last 24 hours.

    Returns:
    - **total_tickets_24h** — total ticket volume
    - **p1_ticket_count** — critical severity count
    - **escalation_distribution** — breakdown by escalation level (auto-resolve, L1, L2, L3, unassigned)
    - **recurring_issue_percentage** — % of tickets flagged as recurring

    Uses Elasticsearch aggregations (filter, terms, missing) in a single query.
    """
    data = get_24h_analytics(es)
    return AnalyticsResponse(
        window_hours=data["window_hours"],
        total_tickets_24h=data["total_tickets_24h"],
        p1_ticket_count=data["p1_ticket_count"],
        escalation_distribution=[
            EscalationBucket(level=b["level"], count=b["count"])
            for b in data["escalation_distribution"]
        ],
        recurring_issue_count=data["recurring_issue_count"],
        recurring_issue_percentage=data["recurring_issue_percentage"],
        generated_at=data["generated_at"],
    )
