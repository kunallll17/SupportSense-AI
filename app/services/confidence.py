import logging
from app.models import TriageResponse

logger = logging.getLogger(__name__)

# ── Scoring Weights ──────────────────────────────────────────────────────────
# Total possible: 100 points

WEIGHT_SIMILAR_CASES = 35        # max points from number of similar cases found
WEIGHT_SIMILARITY_SCORES = 35    # max points from average similarity score quality
WEIGHT_RECURRING_FLAG = 15       # bonus if spike/trend data confirms the classification
WEIGHT_REASONING_DEPTH = 15      # points from reasoning completeness

# ── Confidence Labels ────────────────────────────────────────────────────────

CONFIDENCE_LABELS = [
    (85, "very_high"),
    (70, "high"),
    (50, "medium"),
    (30, "low"),
    (0,  "very_low"),
]


def _score_similar_cases_count(count: int, max_expected: int = 5) -> float:
    """
    More similar historical cases found → higher confidence.
    0 cases = 0 points, 5 cases = full points.
    """
    return min(count / max_expected, 1.0) * WEIGHT_SIMILAR_CASES


def _score_similarity_quality(scores: list[float]) -> float:
    """
    Higher average similarity score → higher confidence.
    RRF scores are typically in the 0.01–0.05 range, so we normalize
    against a practical max of 0.05.
    """
    if not scores:
        return 0.0
    avg_score = sum(scores) / len(scores)
    # RRF rank scores are small; normalize to 0–1 range
    # Typical good RRF score is ~0.03–0.05
    normalized = min(avg_score / 0.05, 1.0)
    return normalized * WEIGHT_SIMILARITY_SCORES


def _score_recurring_flag(recurring: bool) -> float:
    """
    If the issue is detected as recurring/trending, the system has
    more data points to validate the classification → higher confidence.
    """
    return WEIGHT_RECURRING_FLAG if recurring else 0.0


def _score_reasoning_depth(steps: list[str]) -> float:
    """
    More reasoning steps = more thorough analysis by the agent.
    Baseline is 2 steps (hybrid search + trend check from the pipeline).
    Full depth is 7+ steps (pipeline steps + LLM's 5-step reasoning).
    """
    # Pipeline contributes ~2 steps, LLM contributes ~5 steps
    expected_steps = 7
    depth = min(len(steps) / expected_steps, 1.0)
    return depth * WEIGHT_REASONING_DEPTH


def compute_confidence(triage_result: TriageResponse) -> dict:
    """
    Compute a confidence score (0–100) for a triage decision based on:
      1. Number of similar historical cases retrieved
      2. Quality of similarity scores (RRF rank fusion scores)
      3. Whether spike/trend detection confirmed the classification
      4. Depth of agent reasoning steps

    Returns a dict with confidence_score (float) and confidence_label (str).
    """
    similar_cases = triage_result.similar_cases
    scores = [c.score for c in similar_cases if c.score > 0]

    # Compute each component
    cases_score = _score_similar_cases_count(len(similar_cases))
    quality_score = _score_similarity_quality(scores)
    recurring_score = _score_recurring_flag(triage_result.recurring_issue_flag)
    reasoning_score = _score_reasoning_depth(triage_result.reasoning_steps)

    # Total confidence
    total = cases_score + quality_score + recurring_score + reasoning_score
    confidence_score = round(min(total, 100.0), 2)

    # Map to label
    confidence_label = "very_low"
    for threshold, label in CONFIDENCE_LABELS:
        if confidence_score >= threshold:
            confidence_label = label
            break

    logger.info(
        f"Confidence computed: {confidence_score}/100 ({confidence_label}) | "
        f"cases={cases_score:.1f} quality={quality_score:.1f} "
        f"recurring={recurring_score:.1f} reasoning={reasoning_score:.1f}"
    )

    return {
        "confidence_score": confidence_score,
        "confidence_label": confidence_label,
        "confidence_breakdown": {
            "similar_cases_score": round(cases_score, 2),
            "similarity_quality_score": round(quality_score, 2),
            "recurring_trend_score": round(recurring_score, 2),
            "reasoning_depth_score": round(reasoning_score, 2),
        },
    }
