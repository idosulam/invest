"""Structured logging — PRD Section 11.

JSON-structured logs with trace_id, snapshot, strategy and model versions.
Uses structlog for consistent formatting.
"""

import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import Optional

import structlog

# ── Context vars for request tracing ────────────────────────

trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar("user_id", default=None)


def get_trace_id() -> str:
    """Get or create a trace ID for the current request."""
    tid = trace_id_var.get()
    if not tid:
        tid = uuid.uuid4().hex[:16]
        trace_id_var.set(tid)
    return tid


# ── Processors ──────────────────────────────────────────────

def add_trace_info(logger, method_name, event_dict):
    """Add trace_id and user_id to every log entry."""
    event_dict["trace_id"] = get_trace_id()
    uid = user_id_var.get()
    if uid:
        event_dict["user_id"] = uid
    return event_dict


def add_timestamp(logger, method_name, event_dict):
    """Add ISO timestamp."""
    event_dict["timestamp"] = datetime.utcnow().isoformat() + "Z"
    return event_dict


# ── Setup ───────────────────────────────────────────────────

def setup_logging(level: str = "INFO", json_output: bool = True):
    """Configure structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_output: If True, output JSON; otherwise, human-readable
    """
    processors = [
        structlog.contextvars.merge_contextvars,
        add_trace_info,
        add_timestamp,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = ""):
    """Get a structured logger instance."""
    return structlog.get_logger(name)
