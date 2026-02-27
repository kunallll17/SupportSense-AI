from elasticsearch import Elasticsearch, NotFoundError
from app.config import settings
import logging

logger = logging.getLogger(__name__)


def get_es_client() -> Elasticsearch:
    return Elasticsearch(
        settings.elasticsearch_url,
        api_key=settings.elastic_api_key,
    )


# ── Index Mapping ────────────────────────────────────────────────────────────

INDEX_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "support_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "stop", "snowball"]
                }
            }
        }
    },
    "mappings": {
        "properties": {
            # ── Identity ─────────────────────────────────────────────────
            "ticket_id": {
                "type": "keyword"
            },

            # ── Full-text (BM25) ─────────────────────────────────────────
            "title": {
                "type": "text",
                "analyzer": "support_analyzer",
                "fields": {
                    "keyword": {"type": "keyword"}  # for exact filters
                }
            },
            "description": {
                "type": "text",
                "analyzer": "support_analyzer"
            },
            "resolution_notes": {
                "type": "text",
                "analyzer": "support_analyzer"
            },

            # ── Semantic (kNN / vector) ──────────────────────────────────
            "description_vector": {
                "type": "dense_vector",
                "dims": settings.embedding_dims,   # 768 for text-embedding-004
                "index": True,
                "similarity": "cosine"
            },

            # ── Categorical / filter fields ──────────────────────────────
            "issue_type": {
                "type": "keyword"
            },
            "severity": {
                "type": "keyword"   # P1 | P2 | P3 | P4
            },
            "customer_tier": {
                "type": "keyword"   # free | pro | enterprise
            },
            "status": {
                "type": "keyword"   # open | resolved | escalated
            },

            # ── Temporal (aggregations) ──────────────────────────────────
            "created_at": {
                "type": "date",
                "format": "strict_date_optional_time||epoch_millis"
            },

            # ── Agent output (for resolved tickets stored back) ──────────
            "escalation_level": {
                "type": "keyword"   # auto-resolve | L1 | L2 | L3
            },
            "recurring_issue_flag": {
                "type": "boolean"
            }
        }
    }
}


def create_index(es: Elasticsearch, index_name: str = settings.index_name) -> dict:
    """Create the support_tickets index if it doesn't exist."""
    if es.indices.exists(index=index_name):
        logger.info(f"Index '{index_name}' already exists. Skipping creation.")
        return {"status": "already_exists", "index": index_name}

    response = es.indices.create(index=index_name, body=INDEX_MAPPING)
    logger.info(f"Created index '{index_name}': {response}")
    return {"status": "created", "index": index_name, "response": response}


def delete_index(es: Elasticsearch, index_name: str = settings.index_name) -> dict:
    """Drop the index — useful for re-seeding during development."""
    try:
        es.indices.delete(index=index_name)
        return {"status": "deleted", "index": index_name}
    except NotFoundError:
        return {"status": "not_found", "index": index_name}


def get_index_stats(es: Elasticsearch, index_name: str = settings.index_name) -> dict:
    """Return doc count and index health."""
    try:
        stats = es.indices.stats(index=index_name)
        count = es.count(index=index_name)
        return {
            "index": index_name,
            "doc_count": count["count"],
            "store_size": stats["_all"]["primaries"]["store"]["size_in_bytes"]
        }
    except NotFoundError:
        return {"index": index_name, "error": "Index not found"}
