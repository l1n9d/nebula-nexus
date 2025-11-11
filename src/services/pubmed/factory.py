from functools import lru_cache

from src.config import get_settings
from src.services.pubmed.client import PubMedClient


@lru_cache
def get_pubmed_client() -> PubMedClient:
    """Get cached PubMed client instance."""
    settings = get_settings()
    return PubMedClient(settings.pubmed)


