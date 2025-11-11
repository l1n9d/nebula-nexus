import logging

import redis
from src.config import Settings
from src.services.cache.client import CacheClient
from src.services.cache.search_cache import SearchCacheClient

logger = logging.getLogger(__name__)


def make_redis_client(settings: Settings) -> redis.Redis:
    """Create Redis client with connection pooling."""
    redis_settings = settings.redis

    try:
        client = redis.Redis(
            host=redis_settings.host,
            port=redis_settings.port,
            password=redis_settings.password if redis_settings.password else None,
            db=redis_settings.db,
            decode_responses=redis_settings.decode_responses,
            socket_timeout=redis_settings.socket_timeout,
            socket_connect_timeout=redis_settings.socket_connect_timeout,
            retry_on_timeout=True,
            retry_on_error=[redis.ConnectionError, redis.TimeoutError],
        )

        # Test connection
        client.ping()
        logger.info(f"Connected to Redis at {redis_settings.host}:{redis_settings.port}")
        return client

    except redis.ConnectionError as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating Redis client: {e}")
        raise


def make_cache_client(settings: Settings) -> CacheClient:
    """Create exact match cache client."""
    try:
        redis_client = make_redis_client(settings)
        cache_client = CacheClient(redis_client, settings.redis)
        logger.info("Exact match cache client created successfully")
        return cache_client
    except Exception as e:
        logger.error(f"Failed to create cache client: {e}")
        raise


def make_search_cache_client(settings: Settings) -> SearchCacheClient:
    """Create search results cache client."""
    try:
        redis_client = make_redis_client(settings)
        search_cache_client = SearchCacheClient(redis_client, settings.redis)
        logger.info("Search cache client created successfully")
        return search_cache_client
    except Exception as e:
        logger.error(f"Failed to create search cache client: {e}")
        raise
