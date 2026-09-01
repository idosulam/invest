"""Core domain enumerations."""

from enum import Enum


class InstrumentType(str, Enum):
    STOCK = "STOCK"
    ETF = "ETF"
    BENCHMARK = "BENCHMARK"
    INDEX = "INDEX"


class InstrumentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DELISTED = "DELISTED"
    PENDING = "PENDING"


class Timeframe(str, Enum):
    DAILY = "1D"
    HOURLY = "1H"
    MINUTE_15 = "15m"
    MINUTE_5 = "5m"
    MINUTE_1 = "1m"


class SignalState(str, Enum):
    ENTER_LONG = "ENTER_LONG"
    EXIT = "EXIT"
    REDUCE = "REDUCE"
    HOLD = "HOLD"
    WATCH = "WATCH"
    NO_SIGNAL = "NO_SIGNAL"


class Horizon(str, Enum):
    LONG_TERM = "LONG_TERM"
    SWING = "SWING"
    INTRADAY = "INTRADAY"


class QualityGate(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class CorporateActionType(str, Enum):
    SPLIT = "SPLIT"
    DIVIDEND = "DIVIDEND"
    DISTRIBUTION = "DISTRIBUTION"
    LISTING = "LISTING"
    SUSPENSION = "SUSPENSION"
    DELISTING = "DELISTING"


class DataQualityStatus(str, Enum):
    RAW = "RAW"
    VALIDATED = "VALIDATED"
    NORMALIZED = "NORMALIZED"
    ADJUSTED = "ADJUSTED"
    REJECTED = "REJECTED"


class BacktestStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PortfolioType(str, Enum):
    PAPER = "PAPER"
    LIVE = "LIVE"


class AlertChannel(str, Enum):
    EMAIL = "EMAIL"
    WEBHOOK = "WEBHOOK"
    IN_APP = "IN_APP"


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"
