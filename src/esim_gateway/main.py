import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from esim_gateway.api.router import api_router
from esim_gateway.config import settings
from esim_gateway.core.exceptions import GatewayException, ProviderException
from esim_gateway.core.logging import configure_logging, get_logger, set_request_id
from esim_gateway.core.resilience import reset_circuit_breakers
from esim_gateway.core.security import limiter, verify_api_key
from esim_gateway.models.catalog import ErrorDetail, ErrorResponse
from esim_gateway.providers.registry import clear_provider_cache

# Configure logging (set json_logs=True for production)
configure_logging(json_logs=settings.env != "development", log_level="INFO")
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan - startup and shutdown."""
    # Startup
    logger.info(
        "application_starting",
        env=settings.env,
        require_api_key=settings.require_api_key,
        rate_limit=f"{settings.rate_limit_requests}/{settings.rate_limit_window}",
    )

    if settings.require_api_key and not settings.get_api_keys():
        logger.warning(
            "no_api_keys_configured",
            message="API key authentication is enabled but no keys configured. "
            "Set API_KEYS environment variable or disable with REQUIRE_API_KEY=false",
        )

    yield

    # Shutdown - cleanup resources
    logger.info("application_shutting_down")
    clear_provider_cache()
    reset_circuit_breakers()


app = FastAPI(
    title="eSIM Gateway",
    description="Unified API gateway for eSIM providers",
    version="0.1.0",
    lifespan=lifespan,
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def log_requests(request: Request, call_next: Any) -> Any:
    """Log all incoming requests and responses."""
    # Set correlation ID from header or generate new one
    request_id = request.headers.get("X-Request-ID")
    request_id = set_request_id(request_id)

    # Skip logging for health checks
    if request.url.path == "/health":
        return await call_next(request)

    # Log incoming request
    logger.info(
        "request_started",
        method=request.method,
        path=request.url.path,
        query=str(request.query_params) if request.query_params else None,
        client=request.client.host if request.client else None,
    )

    start_time = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    # Log response
    logger.info(
        "request_completed",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        elapsed_ms=round(elapsed_ms, 2),
    )

    # Add request ID to response headers
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(ProviderException)
async def provider_exception_handler(
    request: Request,  # noqa: ARG001
    exc: ProviderException,
) -> JSONResponse:
    """Handle provider exceptions."""
    error_response = ErrorResponse(
        error=ErrorDetail(
            code=exc.error_code,
            message=exc.message,
            provider_code=exc.provider_code,
            provider_message=exc.provider_message,
        ),
        provider=exc.provider,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(),
    )


@app.exception_handler(GatewayException)
async def gateway_exception_handler(
    request: Request,  # noqa: ARG001
    exc: GatewayException,
) -> JSONResponse:
    """Handle gateway exceptions."""
    error_response = ErrorResponse(
        error=ErrorDetail(
            code=exc.error_code,
            message=exc.message,
        ),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(),
    )


# Include routes with API key dependency
app.include_router(
    api_router,
    dependencies=[Depends(verify_api_key)],
)


# Health endpoint (no auth required)
@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "esim-gateway"}
