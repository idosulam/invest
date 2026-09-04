"""Outcome resolver — Phase B of the memory system.

Fetches actual price returns after a holding period and generates
reflections on what held/failed in the original decision.

Can be triggered:
1. Automatically at the start of a new analysis for the same ticker
2. Manually via API endpoint
3. On a schedule (e.g., daily cron job)
"""

import logging
from datetime import datetime, timedelta

from apps.api.llm.ollama_client import OllamaClient
from packages.agents.memory import DecisionMemoryLog
from packages.agents.structured import structured_chat
from packages.agents.schemas import RiskLevel

logger = logging.getLogger(__name__)

# Default holding period (trading days) before we evaluate outcomes
DEFAULT_HOLDING_DAYS = 5

REFLECTION_SYSTEM = (
    "You are a trading analyst reviewing your own past decision now that "
    "the outcome is known. Write exactly 2-4 sentences of plain prose "
    "(no bullets, no headers, no markdown).\n\n"
    "Cover in order:\n"
    "1. Was the directional call correct? (cite the alpha figure)\n"
    "2. Which part of the investment thesis held or failed?\n"
    "3. One concrete lesson to apply to the next similar analysis.\n\n"
    "Be specific and terse. Your output will be stored verbatim in a "
    "decision log and re-read by future analysts, so every word must "
    "earn its place."
)


def _fetch_returns(
    symbol: str,
    trade_date: str,
    holding_days: int = DEFAULT_HOLDING_DAYS,
    benchmark: str = "SPY",
) -> tuple[float | None, float | None, int | None, str | None]:
    """Fetch raw and alpha returns for symbol over holding_days from trade_date.

    Returns (raw_return, alpha_return, holding_days, resolution_date) or
    (None, None, None, None) if data is unavailable.
    """
    try:
        import yfinance as yf

        start = datetime.strptime(trade_date, "%Y-%m-%d")
        end = start + timedelta(days=holding_days + 10)  # buffer for weekends

        stock = yf.Ticker(symbol).history(start=trade_date, end=end.strftime("%Y-%m-%d"))
        bench = yf.Ticker(benchmark).history(start=trade_date, end=end.strftime("%Y-%m-%d"))

        if len(stock) <= holding_days or len(bench) <= holding_days:
            return None, None, None, None

        raw = float(
            (stock["Close"].iloc[holding_days] - stock["Close"].iloc[0])
            / stock["Close"].iloc[0]
        )
        bench_ret = float(
            (bench["Close"].iloc[holding_days] - bench["Close"].iloc[0])
            / bench["Close"].iloc[0]
        )
        alpha = raw - bench_ret
        resolution_date = stock.index[holding_days].strftime("%Y-%m-%d")

        return raw, alpha, holding_days, resolution_date

    except Exception as e:
        logger.warning(f"Could not fetch returns for {symbol} from {trade_date}: {e}")
        return None, None, None, None


def _generate_reflection(
    decision_text: str,
    raw_return: float,
    alpha_return: float,
    benchmark: str = "SPY",
) -> str:
    """Generate a reflection on the decision with known outcomes."""
    client = OllamaClient()

    user_prompt = (
        f"Raw return: {raw_return:+.1%}\n"
        f"Alpha vs {benchmark}: {alpha_return:+.1%}\n\n"
        f"Final Decision:\n{decision_text}"
    )

    try:
        reflection = client.chat(REFLECTION_SYSTEM, user_prompt, temperature=0.3)
        return reflection
    except RuntimeError as e:
        logger.warning(f"LLM unavailable for reflection: {e}")
        # Fallback: simple template
        correct = "correct" if raw_return > 0 else "incorrect"
        beat = "beat" if alpha_return > 0 else "underperformed"
        return (
            f"The directional call was {correct} with a {raw_return:+.1%} raw return. "
            f"The position {beat} the {benchmark} benchmark by {alpha_return:+.1%} alpha. "
            f"Lesson: {'the thesis held — similar setups deserve conviction' if raw_return > 0 else 'risk management was key — review stop-loss placement'}."
        )


def resolve_pending_outcomes(
    memory: DecisionMemoryLog,
    symbol: str | None = None,
    holding_days: int = DEFAULT_HOLDING_DAYS,
    benchmark: str = "SPY",
) -> list[dict]:
    """Resolve all pending entries (optionally filtered by symbol).

    Fetches actual returns, generates reflections, and updates the log.

    Returns list of resolved entries.
    """
    pending = memory.get_pending_entries(symbol=symbol)
    if not pending:
        return []

    updates = []
    for entry in pending:
        trade_date = entry.get("date")
        sym = entry.get("symbol")
        if not trade_date or not sym:
            continue

        # Skip entries that are too recent (within holding period)
        try:
            entry_date = datetime.strptime(trade_date, "%Y-%m-%d")
            if entry_date + timedelta(days=holding_days + 5) > datetime.now():
                logger.debug(f"Skipping {sym} on {trade_date} — too recent for outcome resolution")
                continue
        except ValueError:
            continue

        raw, alpha, days, resolution_date = _fetch_returns(
            sym, trade_date, holding_days=holding_days, benchmark=benchmark,
        )
        if raw is None:
            continue

        reflection = _generate_reflection(
            entry.get("decision", ""), raw, alpha, benchmark=benchmark,
        )

        updates.append({
            "symbol": sym,
            "trade_date": trade_date,
            "raw_return": raw,
            "alpha_return": alpha,
            "holding_days": days,
            "reflection": reflection,
            "resolution_date": resolution_date,
        })

    if updates:
        memory.batch_update_with_outcomes(updates)
        logger.info(f"Resolved {len(updates)} pending entries")

    return updates
