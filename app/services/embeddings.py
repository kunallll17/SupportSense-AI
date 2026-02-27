from google import genai
from app.config import settings
import logging
import time

logger = logging.getLogger(__name__)

# Single client instance — new google.genai SDK style
_client = genai.Client(api_key=settings.google_api_key)


def get_embedding(text: str) -> list[float]:
    """
    Generate a 3072-dim embedding using gemini-embedding-001.
    Uses the new google.genai SDK (google-generativeai is deprecated).
    """
    try:
        result = _client.models.embed_content(
            model=f"models/{settings.embedding_model}",
            contents=text,
        )
        return result.embeddings[0].values
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        raise


def get_query_embedding(text: str) -> list[float]:
    """Generate embedding for a search query — same model as document embedding."""
    return get_embedding(text)


def get_embeddings_batch(texts: list[str], delay: float = 0.1) -> list[list[float]]:
    """
    Generate embeddings for a batch of texts with rate-limit handling.
    Gemini free tier: ~15 req/min sustained.
    """
    embeddings = []
    for i, text in enumerate(texts):
        embeddings.append(get_embedding(text))
        if i < len(texts) - 1:
            time.sleep(delay)
    return embeddings
