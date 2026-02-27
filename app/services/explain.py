from collections import Counter
from elasticsearch import Elasticsearch
import logging

from app.services.hybrid_search import hybrid_search
from app.services.aggregations import is_issue_recurring

logger = logging.getLogger(__name__)


def generate_explain_preview(
    es: Elasticsearch,
    title: str,
    description: str,
    customer_tier: str,
) -> dict:
    """
    Lightweight explainability preview — no LLM involved.

    Uses hybrid search (BM25 + kNN RRF) to find the top-5 similar cases,
    then computes statistical insights:
      1. Top 3 similar cases with key metadata
      2. Average similarity score across all 5 results
      3. Issue-type frequency distribution among the top-5
      4. Guessed issue type (most frequent among top-5)
      5. Recurring spike check via ES count aggregation

    Returns a flat dict consumed by the router layer.
    """
    # ── Step 1: Hybrid search ────────────────────────────────────────────────
    logger.info("Explain: Running hybrid search (top_k=5)...")
    results = hybrid_search(
        es=es,
        title=title,
        description=description,
        customer_tier=customer_tier,
        top_k=5,
    )
    logger.info(f"Explain: Hybrid search returned {len(results)} results")

    # ── Step 2: Extract top 3 similar cases ──────────────────────────────────
    top_3 = [
        {
            "ticket_id": r["ticket_id"],
            "title": r.get("title", ""),
            "issue_type": r.get("issue_type", "unknown"),
            "severity": r.get("severity", "N/A"),
            "score": round(r.get("score", 0.0), 6),
        }
        for r in results[:3]
    ]

    # ── Step 3: Average similarity score ─────────────────────────────────────
    scores = [r.get("score", 0.0) for r in results if r.get("score", 0.0) > 0]
    avg_score = round(sum(scores) / len(scores), 6) if scores else 0.0

    # ── Step 4: Issue-type frequency distribution ────────────────────────────
    issue_types = [
        r.get("issue_type", "unknown")
        for r in results
        if r.get("issue_type")
    ]
    type_counter = Counter(issue_types)
    issue_type_distribution = dict(type_counter.most_common())

    # Most common issue type = our best guess
    guessed_issue_type = type_counter.most_common(1)[0][0] if type_counter else "unknown"

    # ── Step 5: Recurring spike check ────────────────────────────────────────
    logger.info(f"Explain: Checking spike for guessed type '{guessed_issue_type}'...")
    recurring = is_issue_recurring(es, guessed_issue_type) if guessed_issue_type != "unknown" else False

    # ── Step 6: Build human-readable explanation summary ─────────────────────
    summary_parts = [
        f"Based on hybrid search (BM25 + kNN RRF), the top-5 similar historical tickets "
        f"suggest this is a '{guessed_issue_type}' issue.",
    ]

    if len(results) == 0:
        summary_parts = ["No similar historical tickets found. Manual review recommended."]
    else:
        if len(type_counter) == 1:
            summary_parts.append(
                f"All {len(results)} similar cases are '{guessed_issue_type}' — high classification confidence."
            )
        elif len(type_counter) > 1:
            runner_up = type_counter.most_common(2)
            summary_parts.append(
                f"Issue type distribution: {dict(runner_up)}. "
                f"Primary guess is '{guessed_issue_type}' with {type_counter[guessed_issue_type]}/{len(results)} matches."
            )

        if recurring:
            summary_parts.append(
                f"⚠️ SPIKE DETECTED: '{guessed_issue_type}' has ≥3 tickets in the last 24h — "
                f"this may be a systemic or recurring issue."
            )
        else:
            summary_parts.append(
                f"No active spike detected for '{guessed_issue_type}' in the last 24 hours."
            )

        summary_parts.append(f"Average similarity score: {avg_score:.4f}.")

    explanation_summary = " ".join(summary_parts)

    logger.info(
        f"Explain complete: guessed_type={guessed_issue_type} | "
        f"avg_score={avg_score} | recurring={recurring} | "
        f"distribution={issue_type_distribution}"
    )

    return {
        "guessed_issue_type": guessed_issue_type,
        "similar_cases": top_3,
        "average_similarity_score": avg_score,
        "issue_type_distribution": issue_type_distribution,
        "recurring_spike_detected": recurring,
        "explanation_summary": explanation_summary,
    }
