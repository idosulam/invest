"""Quick local dev server — SQLite, no Docker needed."""

import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select, func, String, Text, Integer, Numeric, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.sqlite import CHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from decimal import Decimal

from apps.api.database_dev import Base, get_db, init_db, close_db, async_session_factory
from apps.api.auth import hash_password, verify_password, create_access_token
import apps.api.auth as auth_module
import apps.api.database as db_module
from packages.domain.enums.common import (
    InstrumentType, InstrumentStatus, SignalState, Horizon,
    QualityGate, UserRole, PortfolioType,
)
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

# ── Inline models (SQLite-compatible) ──────────────────────

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="VIEWER")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Instrument(Base):
    __tablename__ = "instruments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(20))
    venue_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    exchange: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sector: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Watchlist(Base):
    __tablename__ = "watchlists"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100))
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    instrument_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── Schemas ────────────────────────────────────────────────

class RegisterReq(BaseModel):
    email: str
    username: str
    password: str

class LoginReq(BaseModel):
    username: str
    password: str

class TokenResp(BaseModel):
    access_token: str
    token_type: str = "bearer"

class InstrumentCreate(BaseModel):
    symbol: str
    name: str
    type: str
    exchange: Optional[str] = None
    sector: Optional[str] = None
    country: Optional[str] = None

class InstrumentResp(BaseModel):
    id: str
    symbol: str
    name: str
    type: str
    currency: str
    status: str
    exchange: Optional[str]
    sector: Optional[str]
    country: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}

class WatchlistCreate(BaseModel):
    name: str
    instrument_ids: list[str] = []

class WatchlistResp(BaseModel):
    id: str
    name: str
    owner_id: str
    instrument_ids: list[str]
    created_at: datetime


# ── App ────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Seed sample data
    async with async_session_factory() as db:
        existing = await db.execute(select(Instrument).limit(1))
        if not existing.scalar_one_or_none():
            samples = [
                Instrument(symbol="AAPL", name="Apple Inc.", type="STOCK", exchange="NASDAQ", sector="Technology", country="US"),
                Instrument(symbol="MSFT", name="Microsoft Corporation", type="STOCK", exchange="NASDAQ", sector="Technology", country="US"),
                Instrument(symbol="GOOGL", name="Alphabet Inc.", type="STOCK", exchange="NASDAQ", sector="Technology", country="US"),
                Instrument(symbol="AMZN", name="Amazon.com Inc.", type="STOCK", exchange="NASDAQ", sector="Consumer Cyclical", country="US"),
                Instrument(symbol="TSLA", name="Tesla Inc.", type="STOCK", exchange="NASDAQ", sector="Consumer Cyclical", country="US"),
                Instrument(symbol="SPY", name="SPDR S&P 500 ETF Trust", type="ETF", exchange="NYSE", country="US"),
                Instrument(symbol="QQQ", name="Invesco QQQ Trust", type="ETF", exchange="NASDAQ", country="US"),
                Instrument(symbol="VTI", name="Vanguard Total Stock Market ETF", type="ETF", exchange="NYSE", country="US"),
                Instrument(symbol="^GSPC", name="S&P 500 Index", type="BENCHMARK", exchange="NYSE", country="US"),
                Instrument(symbol="^DJI", name="Dow Jones Industrial Average", type="BENCHMARK", exchange="NYSE", country="US"),
            ]
            db.add_all(samples)
            await db.commit()
    yield
    await close_db()

# Monkey-patch auth to use dev models/db
auth_module.get_db = get_db
db_module.get_db = get_db

def _get_current_user_override():
    from fastapi import Depends, HTTPException, status
    from jose import JWTError, jwt
    from apps.api.config import get_settings
    from fastapi.security import HTTPBearer
    security = HTTPBearer()
    settings = get_settings()

    async def _dep(
        credentials=Depends(security),
        db=Depends(get_db),
    ):
        try:
            payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=[settings.jwt_algorithm])
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        uid = payload["sub"]
        result = await db.execute(select(User).where(User.id == uid))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        return user
    return _dep

get_current_user_dep = _get_current_user_override()

app = FastAPI(title="Market Platform API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Include data router with overridden auth
from apps.api.routers.data import router as data_router
app.include_router(data_router, prefix="/api/v1")

# Override data router dependencies to use dev auth
import apps.api.auth as _auth_mod
app.dependency_overrides[_auth_mod.get_current_user] = lambda: get_current_user_dep
# Create a simple require_analyst that just returns the user for dev
async def _dev_require_analyst(user = Depends(get_current_user_dep)):
    return user
app.dependency_overrides[_auth_mod.require_analyst] = _dev_require_analyst

# ── Health ─────────────────────────────────────────────────

@app.get("/")
def root():
    return {"name": "Market Platform API", "version": "0.1.0", "status": "running", "docs": "/docs"}

@app.get("/health/live")
def liveness():
    return {"status": "alive"}

@app.get("/health/ready")
async def readiness(db: AsyncSession = Depends(get_db)):
    await db.execute(select(1))
    return {"status": "ready", "database": "ok"}

# ── Auth ───────────────────────────────────────────────────

@app.post("/api/v1/auth/register")
async def register(req: RegisterReq, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where((User.email == req.email) | (User.username == req.username)))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Email or username already exists")
    user = User(email=req.email, username=req.username, password_hash=hash_password(req.password))
    db.add(user)
    await db.flush()
    return {"id": user.id, "email": user.email, "username": user.username, "role": user.role}

@app.post("/api/v1/auth/login")
async def login(req: LoginReq, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    token = create_access_token(uuid.UUID(user.id), UserRole(user.role))
    return {"access_token": token, "token_type": "bearer"}

@app.get("/api/v1/auth/me")
async def me(user = Depends(get_current_user_dep)):
    return {"id": user.id, "email": user.email, "username": user.username, "role": user.role}

# ── Instruments ────────────────────────────────────────────

@app.get("/api/v1/instruments")
async def list_instruments(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    type: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Instrument)
    count_query = select(func.count()).select_from(Instrument)
    if type:
        query = query.where(Instrument.type == type)
        count_query = count_query.where(Instrument.type == type)
    if search:
        f = Instrument.symbol.ilike(f"%{search}%") | Instrument.name.ilike(f"%{search}%")
        query = query.where(f)
        count_query = count_query.where(f)
    total = (await db.execute(count_query)).scalar()
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size).order_by(Instrument.symbol))
    items = result.scalars().all()
    return {"items": [InstrumentResp.model_validate(i) for i in items], "total": total, "page": page, "page_size": page_size}

@app.get("/api/v1/instruments/{instrument_id}")
async def get_instrument(instrument_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Instrument).where(Instrument.id == instrument_id))
    inst = result.scalar_one_or_none()
    if not inst:
        raise HTTPException(404, "Instrument not found")
    return InstrumentResp.model_validate(inst)

@app.post("/api/v1/instruments", status_code=201)
async def create_instrument(req: InstrumentCreate, db: AsyncSession = Depends(get_db)):
    inst = Instrument(**req.model_dump())
    db.add(inst)
    await db.flush()
    return InstrumentResp.model_validate(inst)

# ── Watchlists ─────────────────────────────────────────────

@app.get("/api/v1/watchlists")
async def list_watchlists(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Watchlist))
    items = result.scalars().all()
    return [{"id": w.id, "name": w.name, "owner_id": w.owner_id, "instrument_ids": w.instrument_ids or "[]"} for w in items]

@app.post("/api/v1/watchlists", status_code=201)
async def create_watchlist(req: WatchlistCreate, db: AsyncSession = Depends(get_db)):
    import json
    w = Watchlist(name=req.name, owner_id="00000000-0000-0000-0000-000000000001", instrument_ids=json.dumps(req.instrument_ids))
    db.add(w)
    await db.flush()
    return {"id": w.id, "name": w.name, "instrument_ids": req.instrument_ids}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
