from elasticsearch import Elasticsearch
from app.config import settings
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger(__name__)


def get_24h_analytics(es: Elasticsearch) -> dict:
    """
    Compute comprehensive analytics for the last 24 hours using
    a single Elasticsearch query with multiple aggregations:

      - Total ticket count (from hits.total)
      - P1 (critical) ticket count (filter agg)
      - Escalation level distribution (terms agg + missing agg)
      - Recurring issue percentage (filter agg on recurring_issue_flag)

    Returns a flat dict consumed by the router layer.
    """
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    body = {
        "size": 0,
        "query": {
            "range": {
                "created_at": {
                    "gte": since
                }
            }
        },
        "aggs": {
            # Count of P1 (critical) tickets
            "p1_tickets": {
                "filter": {
                    "term": {"severity": "P1"}
                }
            },
            # Distribution by escalation level (auto-resolve | L1 | L2 | L3)
            "by_escalation_level": {
                "terms": {
                    "field": "escalation_level",
                    "size": 10,
                    "order": {"_count": "desc"}
                }
            },
            # Count tickets with no escalation level assigned yet
            "unassigned_escalation": {
                "missing": {
                    "field": "escalation_level"
                }
            },
            # Count tickets flagged as recurring
            "recurring_tickets": {
                "filter": {
                    "term": {"recurring_issue_flag": True}
                }
            }
        }
    }

    logger.info(f"Running 24h analytics aggregation since {since}")
    response = es.search(index=settings.index_name, body=body)

    total = response["hits"]["total"]["value"]
    p1_count = response["aggregations"]["p1_tickets"]["doc_count"]
    recurring_count = response["aggregations"]["recurring_tickets"]["doc_count"]
    escalation_buckets = response["aggregations"]["by_escalation_level"]["buckets"]
    unassigned_count = response["aggregations"]["unassigned_escalation"]["doc_count"]

    # Build escalation distribution including unassigned tickets
    escalation_distribution = []
    for bucket in escalation_buckets:
        escalation_distribution.append({
            "level": bucket["key"],
            "count": bucket["doc_count"],
        })
    if unassigned_count > 0:
        escalation_distribution.append({
            "level": "unassigned",
            "count": unassigned_count,
        })

    # Calculate recurring percentage safely
    recurring_pct = round((recurring_count / total) * 100, 2) if total > 0 else 0.0

    logger.info(
        f"Analytics complete: total={total} | P1={p1_count} | "
        f"recurring={recurring_count} ({recurring_pct}%)"
    )

    return {
        "window_hours": 24,
        "total_tickets_24h": total,
        "p1_ticket_count": p1_count,
        "escalation_distribution": escalation_distribution,
        "recurring_issue_count": recurring_count,
        "recurring_issue_percentage": recurring_pct,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
