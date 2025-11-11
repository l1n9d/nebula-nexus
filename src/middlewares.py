"""
Middleware configurations for the FastAPI application.
"""

import logging
import time
import uuid
from contextvars import ContextVar

from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Context variables for request tracking
request_id_var: ContextVar[str] = ContextVar('request_id', default=None)
endpoint_var: ContextVar[str] = ContextVar('endpoint', default=None)
method_var: ContextVar[str] = ContextVar('method', default=None)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log request duration and status codes with structured context."""
    
    async def dispatch(self, request: Request, call_next):
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        # Set context variables for structured logging throughout the request
        request_id_var.set(request_id)
        endpoint_var.set(str(request.url.path))
        method_var.set(request.method)
        
        start_time = time.time()
        
        # Log request start
        logger.info(
            "Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": str(request.url.path),
                "client_host": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent", "unknown"),
            }
        )
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log request completion
        logger.info(
            "Request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": str(request.url.path),
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            }
        )
        
        # Add request ID to response headers for tracing
        response.headers["X-Request-ID"] = request_id
        
        return response


def setup_middlewares(app):
    """Setup all middlewares for the application"""
    
    # CORS middleware - must be first
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify actual origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=3600,  # Cache CORS preflight requests for 1 hour
    )
    
    # Gzip compression - 30-50% bandwidth reduction
    app.add_middleware(
        GZipMiddleware,
        minimum_size=1000,  # Only compress responses > 1KB
        compresslevel=6,    # Balance between speed and compression (1-9)
    )
    
    # Request logging
    app.add_middleware(RequestLoggingMiddleware)
    
    logger.info("Middlewares configured: CORS, Gzip, RequestLogging")
