"""Search result caching for faster repeated queries."""

import hashlib
import json
import logging
from datetime import timedelta
from typing import Optional

import redis
from src.config import RedisSettings
from src.schemas.api.search import HybridSearchRequest, SearchResponse
from src.utils.retry import REDIS_RETRY, with_retry

logger = logging.getLogger(__name__)


class SearchCacheClient:
    """Redis-based cache for search results."""

    def __init__(self, redis_client: redis.Redis, settings: RedisSettings):
        self.redis = redis_client
        self.settings = settings
        # Search results cache for shorter time than RAG answers
        self.ttl = timedelta(hours=max(1, settings.ttl_hours // 2))  # Half of RAG cache TTL
        self.cache_prefix = "search_cache"

    def _generate_cache_key(self, request: HybridSearchRequest) -> str:
        """
        Generate cache key based on search parameters.

        Args:
            request: Search request with all parameters

        Returns:
            Cache key string
        """
        key_data = {
            "query": request.query.lower().strip(),  # Normalize query
            "size": request.size,
            "from": request.from_,
            "categories": sorted(request.categories) if request.categories else [],
            "latest_papers": request.latest_papers,
            "use_hybrid": request.use_hybrid,
            "min_score": request.min_score,
        }

        key_string = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()[:16]
        return f"{self.cache_prefix}:{key_hash}"

    @with_retry(REDIS_RETRY)
    async def get_cached_search(self, request: HybridSearchRequest) -> Optional[SearchResponse]:
        """
        Retrieve cached search results.

        Args:
            request: Search request

        Returns:
            Cached SearchResponse or None if not found
        """
        try:
            cache_key = self._generate_cache_key(request)
            cached_data = self.redis.get(cache_key)

            if cached_data:
                try:
                    response_data = json.loads(cached_data)
                    logger.info(f"Search cache HIT for query: '{request.query[:50]}...'")
                    return SearchResponse(**response_data)
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(f"Failed to deserialize cached search result: {e}")
                    # Delete corrupted cache entry
                    self.redis.delete(cache_key)
                    return None

            logger.debug(f"Search cache MISS for query: '{request.query[:50]}...'")
            return None

        except Exception as e:
            logger.error(f"Error checking search cache: {e}")
            return None

    @with_retry(REDIS_RETRY)
    async def store_search_result(self, request: HybridSearchRequest, response: SearchResponse) -> bool:
        """
        Store search results in cache.

        Args:
            request: Search request
            response: Search response to cache

        Returns:
            True if stored successfully
        """
        try:
            cache_key = self._generate_cache_key(request)

            # Only cache successful searches with results
            if response.total == 0:
                logger.debug("Skipping cache for empty search results")
                return False

            # Store with TTL
            success = self.redis.set(
                cache_key,
                response.model_dump_json(),
                ex=self.ttl
            )

            if success:
                logger.info(
                    f"Cached search result for '{request.query[:50]}...' "
                    f"({response.total} results, TTL: {self.ttl.total_seconds()}s)"
                )
                return True
            else:
                logger.warning("Failed to store search result in cache")
                return False

        except Exception as e:
            logger.error(f"Error storing search result in cache: {e}")
            return False

    def get_cache_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        try:
            # Count search cache keys
            cursor = 0
            search_cache_keys = 0

            while True:
                cursor, keys = self.redis.scan(
                    cursor,
                    match=f"{self.cache_prefix}:*",
                    count=100
                )
                search_cache_keys += len(keys)

                if cursor == 0:
                    break

            return {
                "search_cache_keys": search_cache_keys,
                "ttl_hours": self.ttl.total_seconds() / 3600,
            }

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {
                "search_cache_keys": 0,
                "ttl_hours": 0,
                "error": str(e)
            }

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate cache entries matching a pattern.

        Args:
            pattern: Redis key pattern to match

        Returns:
            Number of keys deleted
        """
        try:
            cursor = 0
            deleted_count = 0

            while True:
                cursor, keys = self.redis.scan(
                    cursor,
                    match=f"{self.cache_prefix}:{pattern}*",
                    count=100
                )

                if keys:
                    deleted_count += self.redis.delete(*keys)

                if cursor == 0:
                    break

            logger.info(f"Invalidated {deleted_count} search cache entries matching '{pattern}'")
            return deleted_count

        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
            return 0

