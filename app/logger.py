"""
logger.py — Structured JSON request logging middleware.

Logs every request with: trace_id, store_id, endpoint, latency_ms,
event_count (for ingest), status_code.
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class StructuredLogger:
    """Simple JSON logger that writes to stdout."""

    @staticmethod
    def info(message: str, **kwargs) -> None:
        print(json.dumps({"level": "INFO", "message": message, **kwargs}), file=sys.stdout)

    @staticmethod
    def warning(message: str, **kwargs) -> None:
        print(json.dumps({"level": "WARN", "message": message, **kwargs}), file=sys.stderr)

    @staticmethod
    def error(message: str, **kwargs) -> None:
        print(json.dumps({"level": "ERROR", "message": message, **kwargs}), file=sys.stderr)


logger = StructuredLogger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request with trace_id, latency_ms, and status_code."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        trace_id = str(uuid.uuid4())
        start = time.monotonic()

        # Extract store_id from path if present
        store_id = None
        path_parts = request.url.path.split("/")
        if "stores" in path_parts:
            idx = path_parts.index("stores")
            if idx + 1 < len(path_parts):
                store_id = path_parts[idx + 1]

        request.state.trace_id = trace_id

        response = await call_next(request)

        latency_ms = int((time.monotonic() - start) * 1000)

        log_data = {
            "trace_id": trace_id,
            "method": request.method,
            "endpoint": request.url.path,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
        }
        if store_id:
            log_data["store_id"] = store_id

        logger.info("request", **log_data)
        return response
