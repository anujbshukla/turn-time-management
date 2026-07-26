from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from app.api.dashboard import router as dashboard_router
from app.api.appointments import router as appointments_router
from app.api.recommendations import (
    router as recommendations_router,
)
from app.config import get_settings
from app.errors import (
    AppError,
    app_error_handler,
    validation_error_handler,
)
from app.logging_config import configure_logging
from app.middleware import RequestLoggingMiddleware
from app.api.copilot import (
    router as copilot_router,
)

configure_logging()
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.api_version,
)
app.include_router(copilot_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestLoggingMiddleware)

app.add_exception_handler(
    AppError,
    app_error_handler,
)

app.add_exception_handler(
    RequestValidationError,
    validation_error_handler,
)
app.include_router(dashboard_router)
app.include_router(appointments_router)
app.include_router(recommendations_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": f"{settings.app_name} is running",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "environment": settings.environment,
        "version": settings.api_version,
    }