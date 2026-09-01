"""Unit tests for portfolio accounting — PRD Section 8."""

from datetime import datetime
from decimal import Decimal

import pytest

from packages.portfolio.accounting.engine import (
    PortfolioAccounting, TradeRecord, LotMethod, PositionDetail,
)
from packages.portfolio.optimization.optimizer import PortfolioOptimizer
from packages.portfolio.attribution.attribution import PerformanceAttribution


class TestPortfolioAccounting:
    """Test portfolio accounting engine."""

    def test_buy_trade(self):
        acct = PortfolioAccounting()
        trade = TradeRecord(
            trade_id="t1",
            instrument_id="inst1",
            symbol="AAPL",
            side="BUY",
            quantity=Decimal("100"),
            price=Decimal("150.00"),
            fees=Decimal("1.50"),
            timestamp=datetime.utcnow(),
        )
        result = acct.execute_trade(trade)
        assert result["action"] == "BUY"
        assert result["new_position_qty"] == 100.0

    def test_sell_trade(self):
        acct = PortfolioAccounting()
        # Buy first
        acct.execute_trade(TradeRecord(
            trade_id="t1", instrument_id="inst1", symbol="AAPL",
            side="BUY", quantity=Decimal("100"), price=Decimal("150"),
            fees=Decimal("1"), timestamp=datetime.utcnow(),
        ))
        # Then sell
        result = acct.execute_trade(TradeRecord(
            trade_id="t2", instrument_id="inst1", symbol="AAPL",
            side="SELL", quantity=Decimal("50"), price=Decimal("160"),
            fees=Decimal("1"), timestamp=datetime.utcnow(),
        ))
        assert result["action"] == "SELL"
        assert result["realized_pnl"] > 0

    def test_cannot_sell_more_than_held(self):
        acct = PortfolioAccounting()
        acct.execute_trade(TradeRecord(
            trade_id="t1", instrument_id="inst1", symbol="AAPL",
            side="BUY", quantity=Decimal("10"), price=Decimal("150"),
            fees=Decimal("0"), timestamp=datetime.utcnow(),
        ))
        result = acct.execute_trade(TradeRecord(
            trade_id="t2", instrument_id="inst1", symbol="AAPL",
            side="SELL", quantity=Decimal("20"), price=Decimal("160"),
            fees=Decimal("0"), timestamp=datetime.utcnow(),
        ))
        assert "error" in result

    def test_unrealized_pnl(self):
        acct = PortfolioAccounting()
        acct.execute_trade(TradeRecord(
            trade_id="t1", instrument_id="inst1", symbol="AAPL",
            side="BUY", quantity=Decimal("100"), price=Decimal("150"),
            fees=Decimal("0"), timestamp=datetime.utcnow(),
        ))
        acct.update_prices({"inst1": Decimal("160")})
        pos = acct.get_position("inst1")
        assert pos.unrealized_pnl == Decimal("1000")

    def test_snapshot(self):
        acct = PortfolioAccounting()
        acct.execute_trade(TradeRecord(
            trade_id="t1", instrument_id="inst1", symbol="AAPL",
            side="BUY", quantity=Decimal("100"), price=Decimal("150"),
            fees=Decimal("1"), timestamp=datetime.utcnow(),
        ))
        acct.update_prices({"inst1": Decimal("160")})
        snapshot = acct.get_snapshot("p1", Decimal("50000"))
        assert snapshot.total_market_value == Decimal("16000")
        assert snapshot.cash == Decimal("50000")


class TestPortfolioOptimizer:
    """Test portfolio optimization."""

    def test_mean_variance(self):
        import pandas as pd
        import numpy as np
        np.random.seed(42)
        returns = pd.DataFrame({
            "A": np.random.randn(100) * 0.01,
            "B": np.random.randn(100) * 0.01,
            "C": np.random.randn(100) * 0.01,
        })
        opt = PortfolioOptimizer()
        result = opt.optimize_mean_variance(returns)
        assert abs(sum(result.weights.values()) - 1.0) < 0.01
        assert result.method == "mean_variance"

    def test_minimum_variance(self):
        import pandas as pd
        import numpy as np
        np.random.seed(42)
        returns = pd.DataFrame({
            "A": np.random.randn(100) * 0.01,
            "B": np.random.randn(100) * 0.02,
        })
        opt = PortfolioOptimizer()
        result = opt.optimize_minimum_variance(returns)
        # Lower volatility asset should get higher weight
        assert result.weights["A"] > result.weights["B"]

    def test_rebalance_suggestions(self):
        opt = PortfolioOptimizer()
        actions = opt.rebalance_suggestions(
            current_weights={"A": 0.6, "B": 0.4},
            target_weights={"A": 0.4, "B": 0.6},
            portfolio_value=100000,
            threshold_pct=5.0,
        )
        assert len(actions) == 2
        assert actions[0]["action"] == "SELL"  # A is overweight


class TestPerformanceAttribution:
    """Test performance attribution."""

    def test_brinson_attribution(self):
        attr = PerformanceAttribution()
        result = attr.brinson_attribution(
            portfolio_weights={"Tech": 0.6, "Health": 0.4},
            benchmark_weights={"Tech": 0.5, "Health": 0.5},
            portfolio_returns={"Tech": 0.1, "Health": 0.05},
            benchmark_returns={"Tech": 0.08, "Health": 0.06},
        )
        assert result.method == "brinson_fachler"
        assert len(result.entries) == 2

    def test_sector_attribution(self):
        attr = PerformanceAttribution()
        result = attr.sector_attribution(
            positions=[
                {"instrument_id": "a", "weight": 0.6, "return": 0.1},
                {"instrument_id": "b", "weight": 0.4, "return": 0.05},
            ],
            sector_map={"a": "Tech", "b": "Health"},
        )
        assert result.method == "sector"
        assert len(result.entries) == 2
