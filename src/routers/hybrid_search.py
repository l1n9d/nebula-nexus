import logging
import time

from fastapi import APIRouter, HTTPException
from src.dependencies import EmbeddingsDep, OpenSearchDep, SearchCacheDep
from src.schemas.api.search import HybridSearchRequest, SearchHit, SearchResponse
from src.utils.logging import StructuredLogger

logger = StructuredLogger(__name__)

router = APIRouter(prefix="/hybrid-search", tags=["hybrid-search"])


@router.post("/", response_model=SearchResponse)
async def hybrid_search(
    request: HybridSearchRequest,
    opensearch_client: OpenSearchDep,
    embeddings_service: EmbeddingsDep,
    search_cache: SearchCacheDep,
) -> SearchResponse:
    """
    Hybrid search endpoint supporting multiple search modes with caching.
    """
    try:
        start_time = time.time()

        # Check cache first
        if search_cache:
            try:
                cached_result = await search_cache.get_cached_search(request)
                if cached_result:
                    # Add cache hit indicator and return time
                    cached_result.search_time_ms = round((time.time() - start_time) * 1000, 2)
                    logger.info(
                        "Returning cached search result",
                        query=request.query[:50],
                        cache_hit=True,
                        duration_ms=cached_result.search_time_ms,
                        total_results=cached_result.total
                    )
                    return cached_result
            except Exception as e:
                logger.warning("Cache check failed, proceeding with search", error=str(e))

        if not opensearch_client.health_check():
            raise HTTPException(status_code=503, detail="Search service is currently unavailable")

        query_embedding = None
        if request.use_hybrid:
            try:
                embed_start = time.time()
                query_embedding = await embeddings_service.embed_query(request.query)
                embed_time_ms = (time.time() - embed_start) * 1000
                logger.info(
                    "Generated query embedding for hybrid search",
                    embedding_time_ms=round(embed_time_ms, 2)
                )
            except Exception as e:
                logger.warning("Failed to generate embeddings, falling back to BM25", error=str(e))
                query_embedding = None

        logger.info(
            "Executing search",
            query=request.query[:50],
            search_mode="hybrid" if (request.use_hybrid and query_embedding) else "bm25",
            top_k=request.size
        )

        results = opensearch_client.search_unified(
            query=request.query,
            query_embedding=query_embedding,
            size=request.size,
            from_=request.from_,
            categories=request.categories,
            latest=request.latest_papers,
            use_hybrid=request.use_hybrid,
            min_score=request.min_score,
        )

        hits = []
        for hit in results.get("hits", []):
            hits.append(
                SearchHit(
                    arxiv_id=hit.get("arxiv_id", ""),
                    title=hit.get("title", ""),
                    authors=hit.get("authors"),
                    abstract=hit.get("abstract"),
                    published_date=hit.get("published_date"),
                    pdf_url=hit.get("pdf_url"),
                    score=hit.get("score", 0.0),
                    highlights=hit.get("highlights"),
                    chunk_text=hit.get("chunk_text"),
                    chunk_id=hit.get("chunk_id"),
                    section_name=hit.get("section_name"),
                )
            )

        search_time = round((time.time() - start_time) * 1000, 2)

        search_response = SearchResponse(
            query=request.query,
            total=results.get("total", 0),
            hits=hits,
            size=request.size,
            **{"from": request.from_},
            search_mode="hybrid" if (request.use_hybrid and query_embedding) else "bm25",
            search_time_ms=search_time,
        )

        logger.log_operation(
            "search",
            "success",
            duration_ms=search_time,
            query=request.query[:50],
            total_results=search_response.total,
            returned_results=len(search_response.hits),
            search_mode=search_response.search_mode,
            cache_hit=False
        )

        # Store in cache for future requests
        if search_cache and search_response.total > 0:
            try:
                await search_cache.store_search_result(request, search_response)
            except Exception as e:
                logger.warning("Failed to cache search result", error=str(e))

        return search_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Search failed",
            error=str(e),
            error_type=type(e).__name__,
            query=request.query[:50]
        )
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
