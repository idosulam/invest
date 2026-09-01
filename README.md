# Market Platform — Self-Hosted Stock & ETF Research Platform

A modular, self-hosted web platform for stock and ETF research, backtesting, and paper trading.

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Make (optional, for convenience commands)

### 1. Clone and configure
```bash
cp .env.example .env
# Edit .env with your settings
```

### 2. Start services
```bash
make up
# or: docker compose up -d
```

### 3. Run database migrations
```bash
make db-upgrade
# or: alembic upgrade head
```

### 4. Access the platform
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs (dev mode)
- **MinIO Console**: http://localhost:9001
- **Health Check**: http://localhost:8000/health/live

## Architecture

```
market-platform/
├── apps/
│   ├── api/          # FastAPI backend
│   ├── web/          # Next.js frontend (Phase 3)
│   └── worker/       # Prefect workers
├── packages/
│   ├── domain/       # Business entities and rules
│   ├── data/         # Data providers and pipeline
│   ├── features/     # Indicators and feature computation
│   ├── strategies/   # Trading strategies
│   ├── risk/         # Risk management
│   ├── backtest/     # Backtesting engines
│   ├── portfolio/    # Portfolio management
│   ├── ml/           # Machine learning
│   ├── reasoning/    # LLM explanation layer
│   ├── alerts/       # Alert rules and channels
│   ├── reporting/    # Report generation
│   └── observability/# Logging, tracing, metrics
├── db/
│   ├── migrations/   # Alembic migrations
│   └── seeds/        # Seed data
├── tests/
├── infra/            # Docker, monitoring configs
└── docs/             # ADRs, runbooks, contracts
```

## Development

```bash
# Run API locally with hot-reload
make dev

# Run tests
make test

# Lint and format
make lint
make format

# Database operations
make db-migrate msg="add instruments table"
make db-upgrade
make db-shell
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.11, FastAPI, SQLAlchemy |
| Database | PostgreSQL + TimescaleDB |
| Cache | Redis |
| Object Storage | MinIO (S3-compatible) |
| Task Queue | Prefect |
| Analytics | pandas, NumPy, SciPy, TA-Lib |
| Backtesting | VectorBT, NautilusTrader |
| Auth | Argon2 + JWT + RBAC |
| Observability | OpenTelemetry, Prometheus, Grafana |
| LLM | Ollama (dev) / vLLM (prod) |

## License

MIT
