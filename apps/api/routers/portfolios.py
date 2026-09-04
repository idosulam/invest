"""Portfolio endpoints — PRD Section 1.3 (paper portfolios).

CRUD for paper portfolios, positions, transactions, and analytics.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import get_current_user
from apps.api.database import get_db
from packages.domain.entities.models import (
    Portfolio, Position, Transaction, Instrument, User,
)
from packages.domain.enums.common import PortfolioType, InstrumentType, InstrumentStatus

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


# ── Schemas ─────────────────────────────────────────────────

class PortfolioCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    base_currency: str = "USD"
    type: PortfolioType = PortfolioType.PAPER


class PortfolioResponse(BaseModel):
    id: uuid.UUID
    name: str
    owner_id: uuid.UUID
    base_currency: str
    type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PositionResponse(BaseModel):
    id: uuid.UUID
    instrument_id: uuid.UUID
    symbol: Optional[str] = None
    instrument_name: Optional[str] = None
    quantity: float
    avg_cost: float
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    unrealized_pnl: float
    unrealized_pnl_pct: Optional[float] = None
    realized_pnl: float


class TransactionResponse(BaseModel):
    id: uuid.UUID
    instrument_id: uuid.UUID
    symbol: Optional[str] = None
    side: str
    quantity: float
    price: float
    fees: float
    currency: str
    ts: datetime
    created_at: datetime


class PortfolioAnalytics(BaseModel):
    total_value: float
    total_cost: float
    total_pnl: float
    total_pnl_pct: float
    position_count: int
    sector_allocation: dict[str, float]
    top_positions: list[dict]


class PaperTradeRequest(BaseModel):
    instrument_id: uuid.UUID
    side: str = Field(..., pattern="^(BUY|SELL)$")
    quantity: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    fees: float = 0


class PositionAddRequest(BaseModel):
    """Add a position by symbol — no need to look up instrument_id."""
    symbol: str = Field(..., min_length=1, max_length=20, description="Stock/ETF ticker, e.g. AAPL, SPY")
    quantity: float = Field(..., gt=0, description="Number of shares")
    avg_cost: float = Field(..., gt=0, description="Average cost per share")
    current_price: Optional[float] = Field(None, gt=0, description="Current price (auto-fetched from yfinance if omitted)")


class BulkImportRequest(BaseModel):
    """Bulk import positions — list of symbols with quantities and costs."""
    positions: list[PositionAddRequest]


class IBKRImportRequest(BaseModel):
    """Import positions from IBKR CSV export format."""
    csv_data: str = Field(..., description="Raw CSV content from IBKR activity statement")


# ── Endpoints ───────────────────────────────────────────────

@router.get("", response_model=list[PortfolioResponse])
async def list_portfolios(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List portfolios owned by the current user."""
    result = await db.execute(
        select(Portfolio).where(Portfolio.owner_id == current_user.id)
    )
    return [PortfolioResponse.model_validate(p) for p in result.scalars().all()]


@router.post("", response_model=PortfolioResponse, status_code=201)
async def create_portfolio(
    req: PortfolioCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new paper portfolio."""
    portfolio = Portfolio(
        name=req.name,
        owner_id=current_user.id,
        base_currency=req.base_currency,
        type=req.type,
    )
    db.add(portfolio)
    await db.flush()
    await db.refresh(portfolio)
    return portfolio


@router.get("/{portfolio_id}", response_model=PortfolioResponse)
async def get_portfolio(
    portfolio_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Portfolio).where(
            Portfolio.id == portfolio_id,
            Portfolio.owner_id == current_user.id,
        )
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolio


@router.get("/{portfolio_id}/positions", response_model=list[PositionResponse])
async def get_positions(
    portfolio_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all positions in a portfolio."""
    # Verify ownership
    port = await db.execute(
        select(Portfolio).where(
            Portfolio.id == portfolio_id,
            Portfolio.owner_id == current_user.id,
        )
    )
    if not port.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Portfolio not found")

    result = await db.execute(
        select(Position).where(Position.portfolio_id == portfolio_id)
    )
    positions = result.scalars().all()

    items = []
    for pos in positions:
        inst_result = await db.execute(select(Instrument).where(Instrument.id == pos.instrument_id))
        inst = inst_result.scalar_one_or_none()

        # Fetch live price for real-time P&L
        current_price = None
        if inst:
            current_price = await _fetch_current_price(inst.symbol)

        cost_basis = float(pos.quantity) * float(pos.avg_cost)
        if current_price:
            market_value = float(pos.quantity) * current_price
            unrealized_pnl = (current_price - float(pos.avg_cost)) * float(pos.quantity)
        else:
            market_value = cost_basis + float(pos.unrealized_pnl)
            unrealized_pnl = float(pos.unrealized_pnl)
        pnl_pct = (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0

        items.append(PositionResponse(
            id=pos.id,
            instrument_id=pos.instrument_id,
            symbol=inst.symbol if inst else None,
            instrument_name=inst.name if inst else None,
            quantity=float(pos.quantity),
            avg_cost=float(pos.avg_cost),
            current_price=current_price,
            market_value=round(market_value, 2),
            unrealized_pnl=round(unrealized_pnl, 2),
            unrealized_pnl_pct=round(pnl_pct, 2),
            realized_pnl=float(pos.realized_pnl),
        ))

    return items


@router.get("/{portfolio_id}/transactions", response_model=list[TransactionResponse])
async def get_transactions(
    portfolio_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get transaction history for a portfolio."""
    port = await db.execute(
        select(Portfolio).where(
            Portfolio.id == portfolio_id,
            Portfolio.owner_id == current_user.id,
        )
    )
    if not port.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Portfolio not found")

    result = await db.execute(
        select(Transaction)
        .where(Transaction.portfolio_id == portfolio_id)
        .order_by(Transaction.ts.desc())
        .limit(limit)
    )
    txns = result.scalars().all()

    items = []
    for tx in txns:
        inst_result = await db.execute(select(Instrument).where(Instrument.id == tx.instrument_id))
        inst = inst_result.scalar_one_or_none()

        items.append(TransactionResponse(
            id=tx.id,
            instrument_id=tx.instrument_id,
            symbol=inst.symbol if inst else None,
            side=tx.side,
            quantity=float(tx.quantity),
            price=float(tx.price),
            fees=float(tx.fees),
            currency=tx.currency,
            ts=tx.ts,
            created_at=tx.created_at,
        ))

    return items


@router.post("/{portfolio_id}/trade", response_model=TransactionResponse, status_code=201)
async def execute_paper_trade(
    portfolio_id: uuid.UUID,
    req: PaperTradeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Execute a paper trade (BUY or SELL) in a portfolio."""
    # Verify ownership
    port_result = await db.execute(
        select(Portfolio).where(
            Portfolio.id == portfolio_id,
            Portfolio.owner_id == current_user.id,
        )
    )
    portfolio = port_result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    if portfolio.type != PortfolioType.PAPER:
        raise HTTPException(status_code=400, detail="Can only trade in paper portfolios")

    # Verify instrument
    inst_result = await db.execute(select(Instrument).where(Instrument.id == req.instrument_id))
    instrument = inst_result.scalar_one_or_none()
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument not found")

    # Create transaction
    tx = Transaction(
        portfolio_id=portfolio_id,
        instrument_id=req.instrument_id,
        side=req.side,
        quantity=Decimal(str(req.quantity)),
        price=Decimal(str(req.price)),
        fees=Decimal(str(req.fees)),
        currency=portfolio.base_currency,
        ts=datetime.utcnow(),
    )
    db.add(tx)

    # Update or create position
    pos_result = await db.execute(
        select(Position).where(
            Position.portfolio_id == portfolio_id,
            Position.instrument_id == req.instrument_id,
        )
    )
    position = pos_result.scalar_one_or_none()

    if req.side == "BUY":
        if position:
            # Average up/down
            old_cost = float(position.quantity) * float(position.avg_cost)
            new_cost = req.quantity * req.price
            total_qty = float(position.quantity) + req.quantity
            new_avg = (old_cost + new_cost) / total_qty if total_qty > 0 else req.price
            position.quantity = Decimal(str(total_qty))
            position.avg_cost = Decimal(str(round(new_avg, 6)))
        else:
            position = Position(
                portfolio_id=portfolio_id,
                instrument_id=req.instrument_id,
                quantity=Decimal(str(req.quantity)),
                avg_cost=Decimal(str(req.price)),
            )
            db.add(position)

    elif req.side == "SELL":
        if not position or float(position.quantity) < req.quantity:
            raise HTTPException(status_code=400, detail="Insufficient position to sell")

        # Realized P&L
        pnl = (req.price - float(position.avg_cost)) * req.quantity - req.fees
        position.realized_pnl = Decimal(str(float(position.realized_pnl) + pnl))
        new_qty = float(position.quantity) - req.quantity
        position.quantity = Decimal(str(new_qty))

        # Remove position if fully sold
        if new_qty <= 0:
            await db.delete(position)

    await db.flush()
    await db.refresh(tx)

    return TransactionResponse(
        id=tx.id,
        instrument_id=tx.instrument_id,
        symbol=instrument.symbol,
        side=tx.side,
        quantity=float(tx.quantity),
        price=float(tx.price),
        fees=float(tx.fees),
        currency=tx.currency,
        ts=tx.ts,
        created_at=tx.created_at,
    )


@router.get("/{portfolio_id}/analytics", response_model=PortfolioAnalytics)
async def get_analytics(
    portfolio_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get portfolio analytics: total value, P&L, sector allocation."""
    port_result = await db.execute(
        select(Portfolio).where(
            Portfolio.id == portfolio_id,
            Portfolio.owner_id == current_user.id,
        )
    )
    if not port_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Portfolio not found")

    pos_result = await db.execute(
        select(Position).where(Position.portfolio_id == portfolio_id)
    )
    positions = pos_result.scalars().all()

    total_value = 0
    total_cost = 0
    sector_alloc: dict[str, float] = {}
    top_positions = []

    for pos in positions:
        inst_result = await db.execute(select(Instrument).where(Instrument.id == pos.instrument_id))
        inst = inst_result.scalar_one_or_none()

        cost = float(pos.quantity) * float(pos.avg_cost)
        # Use live price for market value
        current_price = None
        if inst:
            current_price = await _fetch_current_price(inst.symbol)
        if current_price:
            value = float(pos.quantity) * current_price
        else:
            value = cost + float(pos.unrealized_pnl)
        total_cost += cost
        total_value += value

        if inst and inst.sector:
            sector_alloc[inst.sector] = sector_alloc.get(inst.sector, 0) + value

        top_positions.append({
            "symbol": inst.symbol if inst else "?",
            "value": round(value, 2),
            "pnl": float(pos.unrealized_pnl),
        })

    # Sort top positions by value
    top_positions.sort(key=lambda p: p["value"], reverse=True)

    # Normalize sector allocation to percentages
    if total_value > 0:
        sector_alloc = {k: round(v / total_value * 100, 1) for k, v in sector_alloc.items()}

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

    return PortfolioAnalytics(
        total_value=round(total_value, 2),
        total_cost=round(total_cost, 2),
        total_pnl=round(total_pnl, 2),
        total_pnl_pct=round(total_pnl_pct, 2),
        position_count=len(positions),
        sector_allocation=sector_alloc,
        top_positions=top_positions[:10],
    )


# ── Bulk Import ─────────────────────────────────────────────

async def _get_or_create_instrument(db: AsyncSession, symbol: str) -> Instrument:
    """Find an existing instrument by symbol, or create one using yfinance data."""
    symbol = symbol.upper().strip()
    result = await db.execute(select(Instrument).where(Instrument.symbol == symbol))
    instrument = result.scalar_one_or_none()
    if instrument:
        return instrument

    # Create from yfinance
    import yfinance as yf
    try:
        info = yf.Ticker(symbol).info
        name = info.get("shortName") or info.get("longName") or symbol
        sector = info.get("sector", "")
        industry = info.get("industry", "")
        exchange = info.get("exchange", "")
        currency = info.get("currency", "USD")
    except Exception:
        name = symbol
        sector = ""
        industry = ""
        exchange = ""
        currency = "USD"

    instrument = Instrument(
        symbol=symbol,
        name=name,
        type=InstrumentType.STOCK,
        sector=sector or None,
        industry=industry or None,
        exchange=exchange or None,
        currency=currency,
        status=InstrumentStatus.ACTIVE,
    )
    db.add(instrument)
    await db.flush()
    await db.refresh(instrument)
    return instrument


async def _fetch_current_price(symbol: str) -> float | None:
    """Fetch current price from yfinance. Returns None if unavailable."""
    import yfinance as yf
    try:
        fast_info = yf.Ticker(symbol).fast_info
        price = fast_info.get("lastPrice") if hasattr(fast_info, "get") else getattr(fast_info, "last_price", None)
        return float(price) if price else None
    except Exception:
        return None


async def _upsert_position(
    db: AsyncSession,
    portfolio_id: uuid.UUID,
    instrument_id: uuid.UUID,
    quantity: float,
    avg_cost: float,
    side: str = "BUY",
    price: float | None = None,
) -> Position:
    """Create or update a position. For imports, always merges (adds to existing)."""
    pos_result = await db.execute(
        select(Position).where(
            Position.portfolio_id == portfolio_id,
            Position.instrument_id == instrument_id,
        )
    )
    position = pos_result.scalar_one_or_none()

    if position:
        # Merge: average up/down
        old_cost = float(position.quantity) * float(position.avg_cost)
        new_cost = quantity * avg_cost
        total_qty = float(position.quantity) + quantity
        new_avg = (old_cost + new_cost) / total_qty if total_qty > 0 else avg_cost
        position.quantity = Decimal(str(total_qty))
        position.avg_cost = Decimal(str(round(new_avg, 6)))
    else:
        position = Position(
            portfolio_id=portfolio_id,
            instrument_id=instrument_id,
            quantity=Decimal(str(quantity)),
            avg_cost=Decimal(str(avg_cost)),
        )
        db.add(position)

    await db.flush()
    return position


@router.post("/{portfolio_id}/add-position", response_model=list[PositionResponse], status_code=201)
async def add_position(
    portfolio_id: uuid.UUID,
    req: PositionAddRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a position by symbol. Auto-fetches instrument info and current price from yfinance."""
    # Verify ownership
    port_result = await db.execute(
        select(Portfolio).where(
            Portfolio.id == portfolio_id,
            Portfolio.owner_id == current_user.id,
        )
    )
    portfolio = port_result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    instrument = await _get_or_create_instrument(db, req.symbol)

    # Use provided price or fetch from yfinance
    current_price = req.current_price
    if current_price is None:
        current_price = await _fetch_current_price(req.symbol)

    # Upsert the position
    position = await _upsert_position(
        db, portfolio_id, instrument.id,
        quantity=req.quantity, avg_cost=req.avg_cost,
    )

    # Build response
    cost_basis = float(position.quantity) * float(position.avg_cost)
    market_value = cost_basis + float(position.unrealized_pnl)
    pnl_pct = (float(position.unrealized_pnl) / cost_basis * 100) if cost_basis > 0 else 0

    return [PositionResponse(
        id=position.id,
        instrument_id=position.instrument_id,
        symbol=instrument.symbol,
        instrument_name=instrument.name,
        quantity=float(position.quantity),
        avg_cost=float(position.avg_cost),
        current_price=current_price,
        market_value=market_value,
        unrealized_pnl=float(position.unrealized_pnl),
        unrealized_pnl_pct=round(pnl_pct, 2),
        realized_pnl=float(position.realized_pnl),
    )]


@router.post("/{portfolio_id}/bulk-import", response_model=dict, status_code=201)
async def bulk_import(
    portfolio_id: uuid.UUID,
    req: BulkImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bulk import multiple positions by symbol.

    Each position is looked up (or created) via yfinance, and the position
    is created or merged with any existing position for that symbol.
    Current prices are auto-fetched for P&L calculation.
    """
    port_result = await db.execute(
        select(Portfolio).where(
            Portfolio.id == portfolio_id,
            Portfolio.owner_id == current_user.id,
        )
    )
    portfolio = port_result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    imported = []
    errors = []

    for pos_req in req.positions:
        try:
            instrument = await _get_or_create_instrument(db, pos_req.symbol)
            current_price = pos_req.current_price or await _fetch_current_price(pos_req.symbol)

            position = await _upsert_position(
                db, portfolio_id, instrument.id,
                quantity=pos_req.quantity, avg_cost=pos_req.avg_cost,
            )

            imported.append({
                "symbol": instrument.symbol,
                "name": instrument.name,
                "quantity": pos_req.quantity,
                "avg_cost": pos_req.avg_cost,
                "current_price": current_price,
            })
        except Exception as e:
            errors.append({"symbol": pos_req.symbol, "error": str(e)})

    await db.flush()

    return {
        "imported": len(imported),
        "errors": len(errors),
        "positions": imported,
        "error_details": errors,
    }


@router.post("/{portfolio_id}/import-ibkr", response_model=dict, status_code=201)
async def import_ibkr(
    portfolio_id: uuid.UUID,
    req: IBKRImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import positions from an IBKR activity statement CSV.

    Expects the CSV to have columns like: Symbol, Quantity, Cost Basis, ...
    IBKR CSV formats vary by statement type — this handles the most common
    "Positions" section of the activity statement.
    """
    import csv
    import io

    port_result = await db.execute(
        select(Portfolio).where(
            Portfolio.id == portfolio_id,
            Portfolio.owner_id == current_user.id,
        )
    )
    portfolio = port_result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    # Parse CSV
    reader = csv.DictReader(io.StringIO(req.csv_data))
    imported = []
    errors = []

    for row in reader:
        try:
            # IBKR CSV column names (common variants)
            symbol = (
                row.get("Symbol") or row.get("symbol") or
                row.get("Ticker") or row.get("ticker") or ""
            ).strip()
            if not symbol:
                continue

            qty_str = (
                row.get("Quantity") or row.get("quantity") or
                row.get("Position") or row.get("position") or "0"
            ).strip()
            cost_str = (
                row.get("Cost Basis") or row.get("Cost Price") or
                row.get("Avg Cost") or row.get("avg_cost") or
                row.get("cost_basis") or "0"
            ).strip()
            price_str = (
                row.get("Close Price") or row.get("Market Price") or
                row.get("Current Price") or row.get("price") or "0"
            ).strip()

            qty = float(qty_str.replace(",", "").replace("+", ""))
            cost = float(cost_str.replace(",", ""))
            price = float(price_str.replace(",", "")) if price_str and price_str != "0" else None

            if qty <= 0:
                continue

            instrument = await _get_or_create_instrument(db, symbol)
            current_price = price or await _fetch_current_price(symbol)

            position = await _upsert_position(
                db, portfolio_id, instrument.id,
                quantity=qty, avg_cost=cost if cost > 0 else (current_price or 0),
            )

            imported.append({
                "symbol": symbol,
                "quantity": qty,
                "avg_cost": cost,
                "current_price": current_price,
            })
        except Exception as e:
            symbol = row.get("Symbol", row.get("symbol", "?"))
            errors.append({"symbol": symbol, "error": str(e)})

    await db.flush()

    return {
        "imported": len(imported),
        "errors": len(errors),
        "positions": imported,
        "error_details": errors,
    }
