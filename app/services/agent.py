from google import genai
from google.genai import types
import json
import logging
from elasticsearch import Elasticsearch

from app.config import settings
from app.services.hybrid_search import hybrid_search
from app.services.aggregations import is_issue_recurring
from app.models import TriageResponse, SimilarCase

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=settings.google_api_key)


TRIAGE_PROMPT = """You are SupportSense AI, an expert customer support triage agent.

You will be given:
1. A new support ticket (title + description + customer tier)
2. A list of similar historical resolved tickets retrieved from our knowledge base

Your job is to analyze the ticket and produce a structured triage decision.

## New Ticket
**Title:** {title}
**Description:** {description}
**Customer Tier:** {customer_tier}

## Similar Historical Cases (from knowledge base)
{similar_cases_text}

## Trend Alert
{trend_alert}

## Instructions
Analyze the ticket step by step, then return a JSON object.

**Escalation Level Rules:**
- `auto-resolve`: Clear solution exists in similar cases, severity P3/P4, tier=free/pro
- `L1`: Known issue, needs agent assistance, severity P2-P3
- `L2`: Complex issue, needs senior engineer, severity P1-P2 or tier=enterprise
- `L3`: Critical outage, data loss risk, severity P1, tier=enterprise

**Severity Rules (if not explicitly stated):**
- P1: Production down, data loss, payment failure, security breach
- P2: Major feature broken, affecting multiple users, no workaround
- P3: Feature degraded, workaround exists
- P4: Minor issue, cosmetic, single user

Return ONLY a valid JSON object with this exact structure:
{{
  "issue_type": "<one of: authentication|payment|performance|api|ui_bug|billing|data_export|data_import|file_upload|email_delivery|notifications|sync|mobile_crash|infrastructure|search|reporting|permissions|scheduled_jobs|other>",
  "severity": "<P1|P2|P3|P4>",
  "escalation_level": "<auto-resolve|L1|L2|L3>",
  "recommended_response": "<A professional, specific response to send to the customer. 2-4 sentences.>",
  "reasoning_steps": [
    "<Step 1: What type of issue is this and why>",
    "<Step 2: What severity and why>",
    "<Step 3: What do similar cases tell us>",
    "<Step 4: Trend context and impact>",
    "<Step 5: Escalation decision and recommended action>"
  ]
}}"""


def format_similar_cases(cases: list[dict]) -> str:
    if not cases:
        return "No similar historical cases found."
    lines = []
    for i, c in enumerate(cases, 1):
        lines.append(
            f"{i}. [{c.get('severity', 'N/A')}] {c['title']}\n"
            f"   Type: {c.get('issue_type', 'unknown')} | "
            f"Status: {c.get('status', 'unknown')} | "
            f"Tier: {c.get('customer_tier', 'unknown')}\n"
            f"   Resolution: {c.get('resolution_notes') or 'Not resolved yet'}"
        )
    return "\n\n".join(lines)


def run_triage_agent(
    es: Elasticsearch,
    title: str,
    description: str,
    customer_tier: str,
) -> TriageResponse:
    """
    Multi-step triage agent:
      Step 1 — Hybrid search: retrieve top-5 similar historical tickets
      Step 2 — Trend check: is this issue spiking in the last 24h?
      Step 3 — LLM reasoning: classify, assess severity, decide escalation
      Step 4 — Return structured response
    """
    reasoning_steps = []

    # ── Step 1: Hybrid retrieval ──────────────────────────────────────────────
    logger.info("Agent Step 1: Running hybrid search...")
    similar_cases = hybrid_search(
        es=es,
        title=title,
        description=description,
        customer_tier=customer_tier,
        top_k=5,
    )
    reasoning_steps.append(
        f"Retrieved {len(similar_cases)} similar historical tickets via hybrid search (BM25 + kNN RRF)"
    )

    # ── Step 2: Trend detection (pre-LLM) ────────────────────────────────────
    logger.info("Agent Step 2: Checking trend data...")
    guessed_type = similar_cases[0].get("issue_type") if similar_cases else None
    recurring = is_issue_recurring(es, guessed_type) if guessed_type else False

    trend_alert = (
        f"⚠️  TREND ALERT: '{guessed_type}' has seen a spike in the last 24 hours. "
        f"This may be a recurring or systemic issue."
        if recurring
        else "No active trend spike detected for this issue type."
    )
    reasoning_steps.append(
        f"Trend check: issue_type='{guessed_type}' | recurring_spike={recurring}"
    )

    # ── Step 3: LLM reasoning ─────────────────────────────────────────────────
    logger.info(f"Agent Step 3: Running LLM reasoning with {settings.llm_model}...")
    prompt = TRIAGE_PROMPT.format(
        title=title,
        description=description,
        customer_tier=customer_tier,
        similar_cases_text=format_similar_cases(similar_cases),
        trend_alert=trend_alert,
    )

    response = _client.models.generate_content(
        model=f"models/{settings.llm_model}",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )

    raw_json = response.text.strip()

    # ── Step 4: Parse + assemble response ────────────────────────────────────
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as e:
        logger.error(f"LLM returned invalid JSON: {e}\nRaw: {raw_json}")
        raise ValueError(f"LLM JSON parse error: {e}")

    llm_steps = parsed.get("reasoning_steps", [])
    all_steps = reasoning_steps + llm_steps

    # Re-check recurring flag with LLM's more accurate issue_type classification
    final_issue_type = parsed.get("issue_type", guessed_type)
    if final_issue_type != guessed_type:
        recurring = is_issue_recurring(es, final_issue_type)
        all_steps.append(
            f"Re-checked trend with LLM-classified type '{final_issue_type}': recurring={recurring}"
        )

    logger.info(
        f"Agent complete: type={final_issue_type} | "
        f"severity={parsed.get('severity')} | "
        f"escalation={parsed.get('escalation_level')}"
    )

    return TriageResponse(
        issue_type=final_issue_type or "other",
        severity=parsed.get("severity", "P3"),
        escalation_level=parsed.get("escalation_level", "L1"),
        recommended_response=parsed.get("recommended_response", ""),
        similar_cases=[
            SimilarCase(
                ticket_id=c["ticket_id"],
                title=c["title"],
                issue_type=c.get("issue_type"),
                severity=c.get("severity"),
                resolution_notes=c.get("resolution_notes"),
                score=c.get("score", 0.0),
            )
            for c in similar_cases
        ],
        recurring_issue_flag=recurring,
        reasoning_steps=all_steps,
    )
