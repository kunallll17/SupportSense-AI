from elasticsearch import Elasticsearch
from app.config import settings
from app.services.embeddings import get_query_embedding
import logging

logger = logging.getLogger(__name__)


def hybrid_search(
    es: Elasticsearch,
    title: str,
    description: str,
    customer_tier: str | None = None,
    top_k: int = 5,
) -> list[dict]:
    """
    Hybrid search combining BM25 (text relevance) + kNN (semantic similarity)
    via Elasticsearch's native Reciprocal Rank Fusion (RRF).

    RRF merges two ranked lists without needing manual score tuning:
      - BM25 on title + description (keyword overlap)
      - kNN on description_vector (semantic meaning)

    Optionally filters by customer_tier before retrieval.
    """
    query_text = f"{title}\n\n{description}"
    query_vector = get_query_embedding(query_text)

    # Optional pre-filter by customer tier (enterprise gets enterprise-matched cases)
    filter_clause = []
    if customer_tier:
        filter_clause.append({"term": {"customer_tier": customer_tier}})

    body = {
        "retriever": {
            "rrf": {
                "retrievers": [
                    # ── BM25 retriever ────────────────────────────────────
                    {
                        "standard": {
                            "query": {
                                "multi_match": {
                                    "query": query_text,
                                    "fields": [
                                        "title^2",        # boost title matches
                                        "description",
                                        "resolution_notes"
                                    ],
                                    "type": "best_fields",
                                    "fuzziness": "AUTO"
                                }
                            },
                            **({"filter": filter_clause} if filter_clause else {})
                        }
                    },
                    # ── kNN (semantic) retriever ──────────────────────────
                    {
                        "knn": {
                            "field": "description_vector",
                            "query_vector": query_vector,
                            "num_candidates": 50,
                            "k": top_k,
                            **({"filter": filter_clause} if filter_clause else {})
                        }
                    }
                ],
                "rank_window_size": 20,
                "rank_constant": 60       # RRF standard constant
            }
        },
        "size": top_k,
        "_source": {
            "excludes": ["description_vector"]   # don't return the raw vector
        }
    }

    logger.info(f"Running hybrid search | tier_filter={customer_tier} | top_k={top_k}")
    response = es.search(index=settings.index_name, body=body)

    hits = response["hits"]["hits"]
    results = []
    for hit in hits:
        src = hit["_source"]
        results.append({
            "ticket_id": src.get("ticket_id", hit["_id"]),
            "title": src.get("title"),
            "issue_type": src.get("issue_type"),
            "severity": src.get("severity"),
            "customer_tier": src.get("customer_tier"),
            "status": src.get("status"),
            "resolution_notes": src.get("resolution_notes"),
            "score": hit.get("_score", 0.0),
        })

    logger.info(f"Hybrid search returned {len(results)} results")
    return results
