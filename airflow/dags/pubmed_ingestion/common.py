"""Common utilities and setup for PubMed ingestion DAG."""
import sys
from functools import lru_cache
from pathlib import Path

# Add src directory to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


@lru_cache
def get_cached_services():
    """Get cached service instances for the DAG."""
    from src.config import get_settings
    from src.database import get_database
    from src.services.metadata_fetcher import make_metadata_fetcher
    from src.services.pubmed.factory import get_pubmed_client

    settings = get_settings()
    pubmed_client = get_pubmed_client()
    database = get_database()
    metadata_fetcher = make_metadata_fetcher(pubmed_client=pubmed_client, settings=settings)

    return pubmed_client, None, database, metadata_fetcher, None


