"""Position context lookup — bridges a user's holdings to the action advisor."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.entities.models import Portfolio, Position


async def get_position_context(
    db: AsyncSession, user_id, instrument_id
) -> tuple[float, float, float]:
    """Return (quantity, avg_cost, portfolio_value) for a user's holding.

    portfolio_value is the cost-basis notional across all the user's positions —
    a rough but sufficient weight base for position sizing (avoids N price calls).
    """
    q = await db.execute(
        select(Position)
        .join(Portfolio, Position.portfolio_id == Portfolio.id)
        .where(Portfolio.owner_id == user_id, Position.instrument_id == instrument_id)
    )
    pos = q.scalar_one_or_none()
    qty = float(pos.quantity) if pos else 0.0
    avg_cost = float(pos.avg_cost) if pos else 0.0

    tq = await db.execute(
        select(Position).join(Portfolio, Position.portfolio_id == Portfolio.id)
        .where(Portfolio.owner_id == user_id)
    )
    all_pos = tq.scalars().all()
    portfolio_value = sum(float(p.quantity) * float(p.avg_cost) for p in all_pos)
    return qty, avg_cost, float(portfolio_value)


async def list_portfolio_instrument_ids(db: AsyncSession, user_id) -> list:
    q = await db.execute(
        select(Position.instrument_id)
        .join(Portfolio, Position.portfolio_id == Portfolio.id)
        .where(Portfolio.owner_id == user_id)
    )
    return [row[0] for row in q.all()]
