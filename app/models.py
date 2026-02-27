from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid


# ── Ingest ──────────────────────────────────────────────────────────────────

class TicketIngestRequest(BaseModel):
    title: str = Field(..., description="Short summary of the support issue")
    description: str = Field(..., description="Full description of the problem")
    customer_tier: str = Field(..., description="Customer tier: free | pro | enterprise")
    issue_type: Optional[str] = Field(None, description="Issue category if known")
    severity: Optional[str] = Field(None, description="P1 | P2 | P3 | P4")
    status: str = Field("open", description="open | resolved | escalated")
    resolution_notes: Optional[str] = Field(None, description="How this was resolved")

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Cannot log into dashboard after password reset",
                "description": "User reset their password via email link but login fails with 'invalid credentials'. Tried incognito, cleared cookies. Issue persists.",
                "customer_tier": "enterprise",
                "issue_type": "authentication",
                "severity": "P2",
                "status": "resolved",
                "resolution_notes": "Session token cache not cleared after password reset. Fixed by force-expiring sessions."
            }
        }
    }


class TicketIngestResponse(BaseModel):
    ticket_id: str
    message: str


# ── Triage ───────────────────────────────────────────────────────────────────

class TriageRequest(BaseModel):
    title: str
    description: str
    customer_tier: str = Field("free", description="free | pro | enterprise")

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Payment gateway timeout on checkout",
                "description": "Getting 504 timeout on /api/checkout/pay. Happens consistently for orders over $500. Started 2 hours ago.",
                "customer_tier": "pro"
            }
        }
    }


class SimilarCase(BaseModel):
    ticket_id: str
    title: str
    issue_type: Optional[str]
    severity: Optional[str]
    resolution_notes: Optional[str]
    score: float


class TriageResponse(BaseModel):
    issue_type: str
    severity: str
    escalation_level: str
    recommended_response: str
    similar_cases: List[SimilarCase]
    recurring_issue_flag: bool
    reasoning_steps: List[str]


# ── Trends ────────────────────────────────────────────────────────────────────

class IssueTrend(BaseModel):
    issue_type: str
    count: int
    is_spike: bool


class TrendsResponse(BaseModel):
    window_hours: int = 24
    total_tickets: int
    trends: List[IssueTrend]
    spike_threshold: int = 3
