import time
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Request
from sqlalchemy import text

from ..dependencies import DatabaseDep, OpenSearchDep, SettingsDep
from ..schemas.api.health import HealthResponse, ServiceStatus
from ..services.ollama import OllamaClient

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check(settings: SettingsDep, database: DatabaseDep, opensearch_client: OpenSearchDep) -> HealthResponse:
    """Comprehensive health check endpoint for monitoring and load balancer probes.

    :returns: Service health status with version and connectivity checks
    :rtype: HealthResponse
    """
    services = {}
    overall_status = "ok"

    def _check_service(name: str, check_func, *args, **kwargs):
        """Helper to standardize service health checks."""
        try:
            if kwargs.get("is_async"):
                # Handle async functions separately in the calling code
                return check_func(*args)
            result = check_func(*args)
            services[name] = result
            if result.status != "healthy":
                nonlocal overall_status
                overall_status = "degraded"
        except Exception as e:
            services[name] = ServiceStatus(status="unhealthy", message=str(e))
            overall_status = "degraded"

    # Database check
    def _check_database():
        with database.get_session() as session:
            session.execute(text("SELECT 1"))
        return ServiceStatus(status="healthy", message="Connected successfully")

    # OpenSearch check
    def _check_opensearch():
        if not opensearch_client.health_check():
            return ServiceStatus(status="unhealthy", message="Not responding")
        stats = opensearch_client.get_index_stats()
        return ServiceStatus(
            status="healthy",
            message=f"Index '{stats.get('index_name', 'unknown')}' with {stats.get('document_count', 0)} documents",
        )

    # Run synchronous checks
    _check_service("database", _check_database)
    _check_service("opensearch", _check_opensearch)

    # Handle Ollama async check separately
    try:
        ollama_client = OllamaClient(settings)
        ollama_health = await ollama_client.health_check()
        services["ollama"] = ServiceStatus(status=ollama_health["status"], message=ollama_health["message"])
        if ollama_health["status"] != "healthy":
            overall_status = "degraded"
    except Exception as e:
        services["ollama"] = ServiceStatus(status="unhealthy", message=str(e))
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        version=settings.app_version,
        environment=settings.environment,
        service_name=settings.service_name,
        services=services,
    )


@router.get("/health/detailed", tags=["Health"])
async def detailed_health_check(
    request: Request,
    settings: SettingsDep,
    database: DatabaseDep,
    opensearch_client: OpenSearchDep
) -> Dict[str, Any]:
    """
    Detailed health check showing per-component status and latency metrics.
    
    Returns comprehensive health information including:
    - Individual component status (healthy/unhealthy)
    - Response latency for each component
    - Document counts and system metadata
    - Cache statistics
    - Timestamp for monitoring
    
    This endpoint is useful for:
    - Debugging which component is slow/failing
    - Monitoring dashboards
    - Alerting systems
    - Performance tracking
    """
    checks = {}
    overall_healthy = True
    
    # Database Check with latency
    try:
        start = time.time()
        with database.get_session() as session:
            result = session.execute(text("SELECT 1")).scalar()
        latency_ms = round((time.time() - start) * 1000, 2)
        
        checks["database"] = {
            "status": "healthy" if result == 1 else "unhealthy",
            "latency_ms": latency_ms,
            "message": "Connected successfully"
        }
    except Exception as e:
        checks["database"] = {
            "status": "unhealthy",
            "error": str(e)[:200]
        }
        overall_healthy = False
    
    # OpenSearch Check with latency
    try:
        start = time.time()
        healthy = opensearch_client.health_check()
        latency_ms = round((time.time() - start) * 1000, 2)
        
        stats = opensearch_client.get_index_stats()
        
        checks["opensearch"] = {
            "status": "healthy" if healthy else "unhealthy",
            "latency_ms": latency_ms,
            "documents": stats.get("document_count", 0),
            "index_name": stats.get("index_name", "N/A"),
            "size_bytes": stats.get("size_in_bytes", 0)
        }
        
        if not healthy:
            overall_healthy = False
            
    except Exception as e:
        checks["opensearch"] = {
            "status": "unhealthy",
            "error": str(e)[:200]
        }
        overall_healthy = False
    
    # Ollama Check with latency
    try:
        start = time.time()
        ollama_client = OllamaClient(settings)
        health_result = await ollama_client.health_check()
        latency_ms = round((time.time() - start) * 1000, 2)
        
        checks["ollama"] = {
            "status": health_result.get("status", "unknown"),
            "latency_ms": latency_ms,
            "message": health_result.get("message", ""),
            "default_model": settings.ollama_model
        }
        
        if health_result.get("status") != "healthy":
            overall_healthy = False
            
    except Exception as e:
        checks["ollama"] = {
            "status": "unhealthy",
            "error": str(e)[:200]
        }
        overall_healthy = False
    
    # Cache Statistics
    try:
        cache_stats = {}
        
        # Search cache stats
        search_cache_client = getattr(request.app.state, "search_cache_client", None)
        if search_cache_client:
            search_stats = search_cache_client.get_cache_stats()
            cache_stats["search_cache"] = {
                "cached_searches": search_stats.get("search_cache_keys", 0),
                "ttl_hours": search_stats.get("ttl_hours", 0),
            }
        
        # RAG cache stats (if available)
        cache_client = getattr(request.app.state, "cache_client", None)
        if cache_client:
            # Basic info about RAG cache
            cache_stats["rag_cache"] = {
                "status": "enabled",
                "ttl_hours": settings.redis.ttl_hours,
            }
        
        if cache_stats:
            checks["cache"] = {
                "status": "healthy",
                **cache_stats
            }
        
    except Exception as e:
        checks["cache"] = {
            "status": "degraded",
            "error": str(e)[:200]
        }
    
    return {
        "status": "healthy" if overall_healthy else "degraded",
        "timestamp": datetime.now().isoformat(),
        "version": settings.app_version,
        "environment": settings.environment,
        "components": checks
    }
