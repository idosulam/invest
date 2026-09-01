"""FastAPI application entry point."""

import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from apps.api.config import get_settings
from apps.api.database import close_db, init_db
from apps.api.routers import auth, backtests, charts, health, instruments, scanner, signals, watchlists

settings = get_settings()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Starting Market Platform API", env=settings.api_env)

    # Initialize database tables in development
    if settings.api_env == "development":
        await init_db()
        logger.info("Database tables initialized (development mode)")

    yield

    # Shutdown
    await close_db()
    logger.info("Market Platform API stopped")


app = FastAPI(
    title="Market Platform API",
    description="Self-Hosted Stock & ETF Research Platform",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.api_env == "development" else None,
    redoc_url="/redoc" if settings.api_env == "development" else None,
)

# ── Middleware ───────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"] if settings.api_env == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenTelemetry instrumentation
FastAPIInstrumentor.instrument_app(app)


# ── Request logging middleware ───────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every request with structured logging."""
    response = await call_next(request)
    logger.info(
        "request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
    )
    return response


# ── Routers ─────────────────────────────────────────────────

app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(instruments.router, prefix="/api/v1")
app.include_router(watchlists.router, prefix="/api/v1")
app.include_router(charts.router, prefix="/api/v1")
app.include_router(scanner.router, prefix="/api/v1")
app.include_router(signals.router, prefix="/api/v1")
app.include_router(backtests.router, prefix="/api/v1")


# ── Root ────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "name": "Market Platform API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health/live",
    }
