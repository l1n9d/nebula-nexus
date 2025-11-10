from typing import Optional

from src.config import Settings, get_settings

from .jina_client import JinaEmbeddingsClient


def make_embeddings_service(settings: Optional[Settings] = None, redis_client=None) -> JinaEmbeddingsClient:
    """Factory function to create embeddings service with optional Redis caching.

    Creates a new client instance each time to avoid closed client issues.

    :param settings: Optional settings instance
    :param redis_client: Optional Redis client for caching embeddings
    :returns: JinaEmbeddingsClient instance
    """
    if settings is None:
        settings = get_settings()

    # Get API key from settings
    api_key = settings.jina_api_key

    return JinaEmbeddingsClient(api_key=api_key, redis_client=redis_client)


def make_embeddings_client(settings: Optional[Settings] = None, redis_client=None) -> JinaEmbeddingsClient:
    """Factory function to create embeddings client with optional Redis caching.

    Creates a new client instance each time to avoid closed client issues.

    :param settings: Optional settings instance
    :param redis_client: Optional Redis client for caching embeddings
    :returns: JinaEmbeddingsClient instance
    """
    if settings is None:
        settings = get_settings()

    # Get API key from settings
    api_key = settings.jina_api_key

    return JinaEmbeddingsClient(api_key=api_key, redis_client=redis_client)
