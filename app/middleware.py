from __future__ import annotations

import re
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars


CORRELATION_ID_PATTERN = re.compile(r"^req-[0-9a-f]{8}$")


def generate_correlation_id() -> str:
    """Sinh correlation ID hợp lệ theo format ``req-<8 ký tự hex>``."""
    return f"req-{uuid.uuid4().hex[:8]}"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Xóa context cũ để tránh leak context giữa các request.
        clear_contextvars()

        # Ưu tiên dùng x-request-id hợp lệ; sinh mới khi thiếu/sai format.
        header_id = request.headers.get("x-request-id", "")
        correlation_id = (
            header_id
            if CORRELATION_ID_PATTERN.match(header_id)
            else generate_correlation_id()
        )

        bind_contextvars(correlation_id=correlation_id)
        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        response.headers["x-request-id"] = correlation_id
        response.headers["x-response-time-ms"] = f"{elapsed_ms:.2f}"

        return response
