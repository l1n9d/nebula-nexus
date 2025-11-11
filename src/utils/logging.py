"""Structured logging configuration with JSON formatting."""

import json
import logging
import sys
import time
from datetime import datetime
from typing import Any, Dict, Optional

try:
    from pythonjsonlogger import jsonlogger
    HAS_JSON_LOGGER = True
except ImportError:
    HAS_JSON_LOGGER = False
    jsonlogger = None


if HAS_JSON_LOGGER:
    class StructuredFormatter(jsonlogger.JsonFormatter):
        """
        Custom JSON formatter that adds structured fields to log records.
        
        Adds:
        - timestamp (ISO format)
        - level (INFO, ERROR, etc.)
        - logger name
        - message
        - exception info (if present)
        - custom fields from extra
        """

        def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
            """Add custom fields to the log record."""
            super().add_fields(log_record, record, message_dict)
            
            # Add timestamp in ISO format
            log_record['timestamp'] = datetime.fromtimestamp(record.created).isoformat()
            
            # Add standard fields
            log_record['level'] = record.levelname
            log_record['logger'] = record.name
            log_record['message'] = record.getMessage()
            
            # Add file location
            log_record['file'] = f"{record.filename}:{record.lineno}"
            
            # Add function name
            if record.funcName:
                log_record['function'] = record.funcName
            
            # Add exception info if present
            if record.exc_info:
                log_record['exception'] = self.formatException(record.exc_info)
            
            # Add any extra fields passed via extra={}
            for key, value in message_dict.items():
                if key not in log_record:
                    log_record[key] = value
else:
    StructuredFormatter = None


class RequestContextFilter(logging.Filter):
    """
    Filter that adds request context to log records.
    
    Request context is stored in contextvars and includes:
    - request_id: Unique identifier for the request
    - endpoint: API endpoint being accessed
    - method: HTTP method (GET, POST, etc.)
    - user_agent: Client user agent
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Add request context to the log record."""
        # Try to get request context from contextvars
        from contextvars import ContextVar
        
        request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
        endpoint_var: ContextVar[Optional[str]] = ContextVar('endpoint', default=None)
        method_var: ContextVar[Optional[str]] = ContextVar('method', default=None)
        
        # Add to record if available
        request_id = request_id_var.get()
        if request_id:
            record.request_id = request_id
        
        endpoint = endpoint_var.get()
        if endpoint:
            record.endpoint = endpoint
        
        method = method_var.get()
        if method:
            record.method = method
        
        return True


def setup_structured_logging(
    level: str = "INFO",
    json_format: bool = True,
    include_request_context: bool = True
) -> None:
    """
    Configure structured logging for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Use JSON formatting (True) or plain text (False)
        include_request_context: Add request context filter
    
    Example:
        >>> setup_structured_logging(level="INFO", json_format=True)
        >>> logger = logging.getLogger(__name__)
        >>> logger.info("User logged in", extra={"user_id": "123", "action": "login"})
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper()))
    
    # Fallback to plain text if python-json-logger not available
    if json_format and not HAS_JSON_LOGGER:
        logging.warning("python-json-logger not installed, falling back to plain text logging")
        json_format = False
    
    if json_format:
        # Use JSON formatter for machine-readable logs
        formatter = StructuredFormatter(
            fmt='%(timestamp)s %(level)s %(logger)s %(message)s',
            rename_fields={
                'levelname': 'level',
                'name': 'logger',
                'pathname': 'file'
            }
        )
    else:
        # Use plain text formatter
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    handler.setFormatter(formatter)
    
    # Add request context filter if requested
    if include_request_context and json_format:
        handler.addFilter(RequestContextFilter())
    
    root_logger.addHandler(handler)
    
    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("opensearchpy").setLevel(logging.WARNING)


class StructuredLogger:
    """
    Helper class for structured logging with consistent field names.
    
    Usage:
        logger = StructuredLogger(__name__)
        logger.info("Operation completed", operation="search", duration_ms=123.45, status="success")
    """

    def __init__(self, name: str):
        """Initialize structured logger."""
        self.logger = logging.getLogger(name)

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message with structured fields."""
        self.logger.debug(message, extra=kwargs)

    def info(self, message: str, **kwargs) -> None:
        """Log info message with structured fields."""
        self.logger.info(message, extra=kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """Log warning message with structured fields."""
        self.logger.warning(message, extra=kwargs)

    def error(self, message: str, **kwargs) -> None:
        """Log error message with structured fields."""
        self.logger.error(message, extra=kwargs)

    def critical(self, message: str, **kwargs) -> None:
        """Log critical message with structured fields."""
        self.logger.critical(message, extra=kwargs)

    def log_operation(
        self,
        operation: str,
        status: str,
        duration_ms: Optional[float] = None,
        **kwargs
    ) -> None:
        """
        Log an operation with standard fields.
        
        Args:
            operation: Name of the operation (e.g., "search", "rag_query")
            status: Operation status ("success", "failure", "timeout")
            duration_ms: Operation duration in milliseconds
            **kwargs: Additional structured fields
        """
        extra = {
            "operation": operation,
            "status": status,
            **kwargs
        }
        
        if duration_ms is not None:
            extra["duration_ms"] = round(duration_ms, 2)
        
        if status == "success":
            self.info(f"{operation} completed successfully", **extra)
        elif status == "failure":
            self.error(f"{operation} failed", **extra)
        else:
            self.warning(f"{operation} status: {status}", **extra)


class OperationTimer:
    """
    Context manager for timing operations with structured logging.
    
    Usage:
        with OperationTimer("search_query", logger):
            # perform search
            results = search(query)
    """

    def __init__(
        self,
        operation: str,
        logger: StructuredLogger,
        log_start: bool = True,
        **extra_fields
    ):
        """
        Initialize operation timer.
        
        Args:
            operation: Operation name
            logger: StructuredLogger instance
            log_start: Log when operation starts
            **extra_fields: Additional fields to include in logs
        """
        self.operation = operation
        self.logger = logger
        self.log_start = log_start
        self.extra_fields = extra_fields
        self.start_time = None

    def __enter__(self):
        """Start timing."""
        self.start_time = time.time()
        if self.log_start:
            self.logger.info(
                f"{self.operation} started",
                operation=self.operation,
                **self.extra_fields
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop timing and log result."""
        duration_ms = (time.time() - self.start_time) * 1000
        
        if exc_type is None:
            # Success
            self.logger.log_operation(
                self.operation,
                "success",
                duration_ms=duration_ms,
                **self.extra_fields
            )
        else:
            # Failure
            self.logger.log_operation(
                self.operation,
                "failure",
                duration_ms=duration_ms,
                error=str(exc_val),
                error_type=exc_type.__name__,
                **self.extra_fields
            )
        
        return False  # Don't suppress exceptions

