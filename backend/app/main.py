from fastapi import FastAPI, Response
from fastapi.exceptions import (
    RequestValidationError,
)
from fastapi.middleware.cors import (
    CORSMiddleware,
)

from app.api.appointments import (
    router as appointments_router,
)
from app.api.copilot import (
    router as copilot_router,
)
from app.api.dashboard import (
    router as dashboard_router,
)
from app.api.ml import router as ml_router
from app.api.optimization import router as optimization_router
from app.api.recommendations import (
    router as recommendations_router,
)
from app.config import get_settings
from app.database import engine
from app.services.readiness_service import ReadinessService
from app.errors import (
    AppError,
    app_error_handler,
    validation_error_handler,
)
from app.logging_config import configure_logging
from app.middleware import (
    RequestLoggingMiddleware,
)


configure_logging()
settings = get_settings()

# Build the FastAPI application first, then wrap the entire ASGI app in
# CORSMiddleware at the end of this module. Wrapping the whole application
# ensures CORS headers are also present on unhandled 500 responses, which
# prevents browser-side CORS messages from hiding the real backend error.
fastapi_app = FastAPI(
    title=settings.app_name,
    version=settings.api_version,
)

fastapi_app.add_middleware(
    RequestLoggingMiddleware,
)

fastapi_app.add_exception_handler(
    AppError,
    app_error_handler,
)

fastapi_app.add_exception_handler(
    RequestValidationError,
    validation_error_handler,
)

fastapi_app.include_router(
    dashboard_router,
)

fastapi_app.include_router(
    appointments_router,
)

fastapi_app.include_router(
    recommendations_router,
)

fastapi_app.include_router(
    copilot_router,
)

fastapi_app.include_router(
    ml_router,
)

fastapi_app.include_router(
    optimization_router,
)


@fastapi_app.get("/")
def root() -> dict[str, str]:
    return {
        "message":
            f"{settings.app_name} is running",
    }


@fastapi_app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "environment":
            settings.environment,
        "version":
            settings.api_version,
    }


@fastapi_app.get("/health/readiness")
def readiness(
    response: Response,
) -> dict[str, object]:
    result = ReadinessService(engine).check()
    if not result["ready"]:
        response.status_code = 503
    return result


# Keep the explicit configured origins for non-local environments and allow
# localhost/127.0.0.1 on any development port so Vite can safely move from
# 5173 to 5174 (or another port) without requiring another backend change.
app = CORSMiddleware(
    app=fastapi_app,
    allow_origins=settings.cors_origins,
    allow_origin_regex=(
        r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
        if settings.environment.lower() == "development"
        else None
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
