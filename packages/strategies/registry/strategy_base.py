"""Strategy base class and registry — PRD Section 5.2.

Every strategy implements: metadata, required_features, generate, risk_plan.
Strategies are versioned and immutable after promotion.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

import pandas as pd

from packages.domain.enums.common import Horizon, SignalState, QualityGate


# ── Strategy Card (metadata) ────────────────────────────────

@dataclass
class StrategyCard:
    """Human-readable strategy description."""
    name: str
    version: str
    horizon: Horizon
    description: str
    author: str = "system"
    tags: list[str] = field(default_factory=list)
    required_lookback: int = 200  # bars needed


# ── Feature spec ────────────────────────────────────────────

@dataclass
class FeatureSpec:
    """Declares a feature a strategy needs."""
    name: str
    params: dict = field(default_factory=dict)


# ── Market context (input to strategy) ──────────────────────

@dataclass
class MarketContext:
    """Point-in-time market data for signal generation."""
    instrument_id: uuid.UUID
    symbol: str
    bars: pd.DataFrame  # OHLCV, chronological
    indicators: dict[str, pd.Series]  # pre-computed indicators
    fundamentals: dict[str, float] = field(default_factory=dict)
    benchmark_bars: Optional[pd.DataFrame] = None  # e.g. SPY bars for relative strength
    as_of: datetime = field(default_factory=datetime.utcnow)


# ── Raw signal (strategy output) ────────────────────────────

@dataclass
class RawSignal:
    """Raw output from a strategy before risk gate."""
    state: SignalState
    confidence: float  # 0.0 - 1.0
    entry_zone_low: Optional[Decimal] = None
    entry_zone_high: Optional[Decimal] = None
    invalidation_rule: str = ""
    invalidation_level: Optional[Decimal] = None
    target_method: str = ""
    target_price: "Decimal | None" = None
    reason_codes: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


# ── Risk plan ───────────────────────────────────────────────

@dataclass
class RiskPlan:
    """Position sizing and risk limits."""
    max_loss_pct: Decimal = Decimal("2.0")
    suggested_size_pct: Decimal = Decimal("5.0")
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None


# ── Base strategy ───────────────────────────────────────────

class Strategy(ABC):
    """Base class all strategies must implement."""

    @property
    @abstractmethod
    def metadata(self) -> StrategyCard:
        """Return strategy metadata/card."""
        ...

    @abstractmethod
    def required_features(self) -> list[FeatureSpec]:
        """Declare which features this strategy needs."""
        ...

    @abstractmethod
    def generate(self, context: MarketContext) -> RawSignal:
        """Generate a raw signal from market context."""
        ...

    def risk_plan(self, signal: RawSignal, portfolio_value: Decimal = Decimal("100000")) -> RiskPlan:
        """Default risk plan — override for custom sizing."""
        return RiskPlan()


# ── Strategy Registry ───────────────────────────────────────

class StrategyRegistry:
    """Central registry for all strategies."""

    _strategies: dict[str, type[Strategy]] = {}

    @classmethod
    def register(cls, strategy_cls: type[Strategy]) -> type[Strategy]:
        """Decorator to register a strategy class."""
        name = strategy_cls.__name__
        cls._strategies[name] = strategy_cls
        return strategy_cls

    @classmethod
    def get(cls, name: str) -> Optional[type[Strategy]]:
        return cls._strategies.get(name)

    @classmethod
    def list_all(cls) -> list[StrategyCard]:
        """List all registered strategy cards."""
        cards = []
        for name, cls_ in cls._strategies.items():
            try:
                instance = cls_()
                cards.append(instance.metadata)
            except Exception:
                pass
        return cards

    @classmethod
    def list_by_horizon(cls, horizon: Horizon) -> list[StrategyCard]:
        return [c for c in cls.list_all() if c.horizon == horizon]

    @classmethod
    def create(cls, name: str) -> Optional[Strategy]:
        """Instantiate a strategy by class name or display name."""
        strategy_cls = cls._strategies.get(name)
        if strategy_cls:
            return strategy_cls()

        # Fallback: match by the strategy's display name (metadata.name)
        for cls_ in cls._strategies.values():
            try:
                instance = cls_()
                if instance.metadata.name == name:
                    return instance
            except Exception:
                continue
        return None
