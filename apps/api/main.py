"""FastAPI application entry point."""

import os
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from apps.api.config import get_settings
from apps.api.database import close_db, init_db
from apps.api.routers import admin, alerts, assistant, auth, backtests, charts, health, instruments, portfolios, reports, scanner, signals, watchlists

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
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"] if settings.api_env == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
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
app.include_router(portfolios.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(assistant.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")


# ── Root ────────────────────────────────────────────────────

# ── Frontend static files ───────────────────────────────────

# Serve Next.js static files if they exist
NEXTJS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "apps", "web", "out")
NEXTJS_EXISTS = os.path.isdir(NEXTJS_DIR)

if NEXTJS_EXISTS:
    app.mount("/_next", StaticFiles(directory=os.path.join(NEXTJS_DIR, "_next")), name="nextjs_static")

@app.get("/")
async def root():
    if NEXTJS_EXISTS:
        return FileResponse(os.path.join(NEXTJS_DIR, "index.html"))
    return {
        "name": "Market Platform API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health/live",
    }

# Catch-all for frontend routes (SPA)
@app.get("/{path:path}")
async def serve_frontend(path: str):
    if NEXTJS_EXISTS:
        # Try exact file first
        file_path = os.path.join(NEXTJS_DIR, path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        # Fall back to index.html for SPA routing
        return FileResponse(os.path.join(NEXTJS_DIR, "index.html"))
    return {"error": "Frontend not built. Run: cd apps/web && npm run build"}
