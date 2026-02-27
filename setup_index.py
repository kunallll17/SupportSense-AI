"""
setup_index.py — Run once to create the support_tickets index in Elasticsearch.
Usage: python setup_index.py [--reset]
"""
import sys
import logging
from app.services.elasticsearch import get_es_client, create_index, delete_index, get_index_stats

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    reset = "--reset" in sys.argv
    es = get_es_client()

    # Verify connection
    info = es.info()
    logger.info(f"Connected to Elasticsearch {info['version']['number']} — cluster: {info['cluster_name']}")

    if reset:
        logger.warning("--reset flag detected. Deleting existing index...")
        result = delete_index(es)
        logger.info(f"Delete result: {result}")

    # Create index
    result = create_index(es)
    logger.info(f"Index result: {result}")

    # Print stats
    stats = get_index_stats(es)
    logger.info(f"Index stats: {stats}")


if __name__ == "__main__":
    main()
