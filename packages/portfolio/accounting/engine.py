"""Portfolio accounting engine — PRD Section 8.

Tracks positions, lots, fees, realized/unrealized P&L.
Uses Decimal types for monetary values — never binary float for accounting.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from enum import Enum


class LotMethod(str, Enum):
    FIFO = "FIFO"
    LIFO = "LIFO"
    AVERAGE = "AVERAGE"


@dataclass
class Lot:
    """Individual tax lot."""
    quantity: Decimal
    cost_basis: Decimal  # per unit
    acquired_at: datetime
    lot_id: str = ""


@dataclass
class PositionDetail:
    """Detailed position with lots."""
    instrument_id: str
    symbol: str
    lots: list[Lot] = field(default_factory=list)
    current_price: Decimal = Decimal("0")

    @property
    def total_quantity(self) -> Decimal:
        return sum(lot.quantity for lot in self.lots)

    @property
    def avg_cost(self) -> Decimal:
        total_cost = sum(lot.quantity * lot.cost_basis for lot in self.lots)
        qty = self.total_quantity
        return (total_cost / qty).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP) if qty > 0 else Decimal("0")

    @property
    def market_value(self) -> Decimal:
        return self.total_quantity * self.current_price

    @property
    def unrealized_pnl(self) -> Decimal:
        return (self.current_price - self.avg_cost) * self.total_quantity

    @property
    def unrealized_pnl_pct(self) -> Decimal:
        if self.avg_cost == 0:
            return Decimal("0")
        return ((self.current_price / self.avg_cost - 1) * 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )


@dataclass
class TradeRecord:
    """Record of a trade execution."""
    trade_id: str
    instrument_id: str
    symbol: str
    side: str  # BUY, SELL
    quantity: Decimal
    price: Decimal
    fees: Decimal
    timestamp: datetime
    signal_id: Optional[str] = None


@dataclass
class PortfolioSnapshot:
    """Point-in-time portfolio snapshot."""
    portfolio_id: str
    timestamp: datetime
    positions: list[PositionDetail]
    cash: Decimal
    total_market_value: Decimal
    total_unrealized_pnl: Decimal
    total_realized_pnl: Decimal
    total_fees: Decimal


class PortfolioAccounting:
    """Portfolio accounting engine.

    Manages positions, lots, trade execution, and P&L tracking.
    All monetary calculations use Decimal for precision.
    """

    def __init__(self, lot_method: LotMethod = LotMethod.AVERAGE):
        self.lot_method = lot_method
        self._positions: dict[str, PositionDetail] = {}
        self._realized_pnl: Decimal = Decimal("0")
        self._total_fees: Decimal = Decimal("0")
        self._trade_history: list[TradeRecord] = []

    def execute_trade(self, trade: TradeRecord) -> dict:
        """Execute a trade and update positions.

        Args:
            trade: Trade record with instrument, side, quantity, price, fees.

        Returns:
            Dict with execution details.
        """
        pos = self._positions.get(trade.instrument_id)
        if pos is None:
            pos = PositionDetail(
                instrument_id=trade.instrument_id,
                symbol=trade.symbol,
            )
            self._positions[trade.instrument_id] = pos

        self._total_fees += trade.fees

        if trade.side == "BUY":
            # Add lot
            pos.lots.append(Lot(
                quantity=trade.quantity,
                cost_basis=trade.price,
                acquired_at=trade.timestamp,
                lot_id=f"lot_{len(self._trade_history)}",
            ))
            self._trade_history.append(trade)

            return {
                "action": "BUY",
                "quantity": float(trade.quantity),
                "price": float(trade.price),
                "fees": float(trade.fees),
                "new_position_qty": float(pos.total_quantity),
                "new_avg_cost": float(pos.avg_cost),
            }

        elif trade.side == "SELL":
            if pos.total_quantity < trade.quantity:
                return {"error": "Insufficient position", "available": float(pos.total_quantity)}

            # Calculate realized P&L
            avg_cost = pos.avg_cost
            realized = (trade.price - avg_cost) * trade.quantity - trade.fees
            self._realized_pnl += realized

            # Remove lots based on method
            remaining = trade.quantity
            if self.lot_method == LotMethod.FIFO:
                while remaining > 0 and pos.lots:
                    lot = pos.lots[0]
                    if lot.quantity <= remaining:
                        remaining -= lot.quantity
                        pos.lots.pop(0)
                    else:
                        lot.quantity -= remaining
                        remaining = Decimal("0")
            elif self.lot_method == LotMethod.LIFO:
                while remaining > 0 and pos.lots:
                    lot = pos.lots[-1]
                    if lot.quantity <= remaining:
                        remaining -= lot.quantity
                        pos.lots.pop()
                    else:
                        lot.quantity -= remaining
                        remaining = Decimal("0")
            else:  # AVERAGE
                # Just reduce total quantity
                for lot in pos.lots:
                    if remaining <= 0:
                        break
                    reduction = min(lot.quantity, remaining)
                    lot.quantity -= reduction
                    remaining -= reduction
                pos.lots = [l for l in pos.lots if l.quantity > 0]

            self._trade_history.append(trade)

            return {
                "action": "SELL",
                "quantity": float(trade.quantity),
                "price": float(trade.price),
                "fees": float(trade.fees),
                "realized_pnl": float(realized),
                "remaining_qty": float(pos.total_quantity),
            }

        return {"error": f"Unknown side: {trade.side}"}

    def update_prices(self, prices: dict[str, Decimal]):
        """Update current prices for all positions."""
        for inst_id, price in prices.items():
            if inst_id in self._positions:
                self._positions[inst_id].current_price = price

    def get_snapshot(self, portfolio_id: str, cash: Decimal) -> PortfolioSnapshot:
        """Get current portfolio snapshot."""
        positions = list(self._positions.values())
        total_market_value = sum(p.market_value for p in positions)
        total_unrealized = sum(p.unrealized_pnl for p in positions)

        return PortfolioSnapshot(
            portfolio_id=portfolio_id,
            timestamp=datetime.utcnow(),
            positions=positions,
            cash=cash,
            total_market_value=total_market_value,
            total_unrealized_pnl=total_unrealized,
            total_realized_pnl=self._realized_pnl,
            total_fees=self._total_fees,
        )

    def get_position(self, instrument_id: str) -> Optional[PositionDetail]:
        """Get position detail for an instrument."""
        return self._positions.get(instrument_id)

    def get_all_positions(self) -> list[PositionDetail]:
        """Get all positions."""
        return list(self._positions.values())

    def get_trade_history(self) -> list[TradeRecord]:
        """Get full trade history."""
        return self._trade_history.copy()
