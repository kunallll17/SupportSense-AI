from fastapi import APIRouter, Depends
from elasticsearch import Elasticsearch

from app.models import TrendsResponse, IssueTrend
from app.services.elasticsearch import get_es_client
from app.services.aggregations import get_24h_trends

router = APIRouter(prefix="/trends", tags=["Trends"])


@router.get("/", response_model=TrendsResponse, summary="Get 24h issue trends")
def get_trends(es: Elasticsearch = Depends(get_es_client)):
    """
    Real-time trend detection using Elasticsearch aggregations.

    - **terms aggregation** on `issue_type` to count occurrences
    - **date_histogram** for hourly volume breakdown
    - Flags any `issue_type` with ≥3 tickets in last 24h as a spike

    Use this to identify systemic issues before they escalate.
    """
    data = get_24h_trends(es)
    return TrendsResponse(
        window_hours=data["window_hours"],
        total_tickets=data["total_tickets"],
        spike_threshold=data["spike_threshold"],
        trends=[
            IssueTrend(
                issue_type=t["issue_type"],
                count=t["count"],
                is_spike=t["is_spike"],
            )
            for t in data["trends"]
        ],
    )
