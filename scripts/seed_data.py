"""
seed_data.py — Ingest sample tickets into Elasticsearch with Gemini embeddings.

Usage:
    python scripts/seed_data.py
    python scripts/seed_data.py --reset   # Deletes + recreates index first
"""
import sys
import json
import uuid
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
import random

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.elasticsearch import get_es_client, create_index, delete_index
from app.services.embeddings import get_embedding
from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def load_tickets() -> list[dict]:
    data_path = Path(__file__).parent.parent / "data" / "sample_tickets.json"
    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)


def spread_timestamps(count: int) -> list[datetime]:
    """
    Distribute tickets across the last 7 days.
    Cluster 6 authentication tickets in the last 24h to trigger spike detection.
    """
    now = datetime.now(timezone.utc)
    timestamps = []
    for i in range(count):
        hours_ago = random.uniform(24, 168)  # 1–7 days ago by default
        timestamps.append(now - timedelta(hours=hours_ago))
    return timestamps


def embed_text(title: str, description: str) -> list[float]:
    """Combine title + description for a richer embedding signal."""
    combined = f"{title}\n\n{description}"
    return get_embedding(combined)


def ingest_tickets(es, tickets: list[dict], timestamps: list[datetime]):
    success = 0
    failed = 0

    for i, ticket in enumerate(tickets):
        ticket_id = str(uuid.uuid4())
        logger.info(f"[{i+1}/{len(tickets)}] Embedding: {ticket['title'][:60]}...")

        try:
            vector = embed_text(ticket["title"], ticket["description"])
        except Exception as e:
            logger.error(f"  ✗ Embedding failed, skipping: {e}")
            failed += 1
            continue

        doc = {
            "ticket_id": ticket_id,
            "title": ticket["title"],
            "description": ticket["description"],
            "description_vector": vector,
            "customer_tier": ticket.get("customer_tier", "free"),
            "issue_type": ticket.get("issue_type"),
            "severity": ticket.get("severity"),
            "status": ticket.get("status", "open"),
            "resolution_notes": ticket.get("resolution_notes"),
            "escalation_level": None,
            "recurring_issue_flag": False,
            "created_at": timestamps[i].isoformat(),
        }

        es.index(index=settings.index_name, id=ticket_id, document=doc)
        logger.info(f"  ✓ Indexed ticket_id={ticket_id[:8]}...")
        success += 1

    return success, failed


def inject_recent_spike(es, base_tickets: list[dict]):
    """
    Inject 6 authentication tickets within the last 2 hours
    to simulate a trending spike for the demo.
    """
    logger.info("\n🔥 Injecting authentication spike (last 2h)...")
    now = datetime.now(timezone.utc)
    spike_tickets = [t for t in base_tickets if t.get("issue_type") == "authentication"][:3]

    for spike in spike_tickets:
        for _ in range(2):  # Duplicate for volume
            ticket_id = str(uuid.uuid4())
            ts = now - timedelta(minutes=random.randint(10, 110))

            try:
                vector = embed_text(spike["title"], spike["description"])
            except Exception as e:
                logger.warning(f"Spike embed failed: {e}")
                continue

            doc = {
                "ticket_id": ticket_id,
                "title": spike["title"],
                "description": spike["description"],
                "description_vector": vector,
                "customer_tier": spike.get("customer_tier", "pro"),
                "issue_type": spike.get("issue_type"),
                "severity": spike.get("severity"),
                "status": "open",
                "resolution_notes": None,
                "escalation_level": None,
                "recurring_issue_flag": False,
                "created_at": ts.isoformat(),
            }
            es.index(index=settings.index_name, id=ticket_id, document=doc)
            logger.info(f"  ✓ Spike ticket: {spike['title'][:50]}...")


def main():
    reset = "--reset" in sys.argv
    es = get_es_client()

    if reset:
        logger.warning("--reset: Deleting index...")
        delete_index(es)
        create_index(es)

    tickets = load_tickets()
    logger.info(f"Loaded {len(tickets)} sample tickets from data/sample_tickets.json")

    timestamps = spread_timestamps(len(tickets))
    success, failed = ingest_tickets(es, tickets, timestamps)

    # Inject authentication spike for demo purposes
    inject_recent_spike(es, tickets)

    # Force refresh so docs are immediately searchable
    es.indices.refresh(index=settings.index_name)

    final_count = es.count(index=settings.index_name)["count"]
    logger.info(f"\n✅ Seeding complete!")
    logger.info(f"   Ingested: {success} | Failed: {failed}")
    logger.info(f"   Total docs in index: {final_count}")


if __name__ == "__main__":
    main()
