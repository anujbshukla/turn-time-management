import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


logger = logging.getLogger("turn_time.api")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:
        request_id = request.headers.get(
            "X-Request-ID",
            str(uuid.uuid4()),
        )

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (
                time.perf_counter() - start_time
            ) * 1000

            logger.exception(
                "Unhandled request failure | "
                "request_id=%s method=%s path=%s "
                "duration_ms=%.2f",
                request_id,
                request.method,
                request.url.path,
                elapsed_ms,
            )
            raise

        elapsed_ms = (
            time.perf_counter() - start_time
        ) * 1000

        response.headers["X-Request-ID"] = request_id

        logger.info(
            "Request completed | "
            "request_id=%s method=%s path=%s "
            "status=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )

        return response