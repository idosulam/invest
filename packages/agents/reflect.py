"""Decision-log reflection — TradingAgents' memory/reflect loop.

Turns logged decisions + resolved outcomes into short "lessons" text that is
injected into future analyst prompts. The engine already logs decisions
(`memory.py`) and resolves outcomes (`resolver.py`); this closes the loop so the
trading firm learns from what worked and what didn't.

Deterministic scoring/formatting is PURE and unit-tested. An LLM may later wrap
this in more natural prose, but the numbers here are fixed.
"""

from __future__ import annotations

from typing import Iterable


def _num(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def score_decisions(entries: Iterable[dict]) -> dict:
    """Aggregate performance of resolved decisions (pure)."""
    resolved = [e for e in entries if e.get("alpha_return") is not None or e.get("resolved")]
    if not resolved:
        return {"resolved": 0, "hit_rate": None, "avg_alpha_pct": None, "avg_raw_pct": None}
    alphas = [a for a in (_num(e.get("alpha_return")) for e in resolved) if a is not None]
    raws = [r for r in (_num(e.get("raw_return")) for e in resolved) if r is not None]
    hits = [a for a in alphas if a > 0]
    return {
        "resolved": len(resolved),
        "hit_rate": (len(hits) / len(alphas)) if alphas else None,
        "avg_alpha_pct": (sum(alphas) / len(alphas)) if alphas else None,
        "avg_raw_pct": (sum(raws) / len(raws)) if raws else None,
    }


def _entry_line(e: dict) -> str:
    parts = [f"{e.get('symbol', '?')} {str(e.get('date', ''))[:10]} {e.get('state', '')}".strip()]
    raw = _num(e.get("raw_return"))
    alpha = _num(e.get("alpha_return"))
    if raw is not None:
        parts.append(f"raw {raw:+.1%}")
    if alpha is not None:
        parts.append(f"vs benchmark {alpha:+.1%}")
    if e.get("holding_days"):
        parts.append(f"over {e['holding_days']}d")
    return " ".join(parts)


def format_lessons(entries: Iterable[dict], max_items: int = 8) -> str:
    """Render past decisions + outcomes as a compact history block (pure)."""
    entries = list(entries)
    if not entries:
        return ""
    resolved = [e for e in entries if e.get("alpha_return") is not None]
    pending = [e for e in entries if e.get("alpha_return") is None]
    lines: list[str] = []
    for e in resolved[-max_items:]:
        alpha = _num(e.get("alpha_return"), 0.0)
        outcome = "worked" if alpha > 0 else ("underperformed" if alpha < 0 else "was flattish")
        line = f"- {_entry_line(e)} -> {outcome}"
        note = (e.get("reflection") or "").strip()
        if note:
            line += f"; lesson: {note}"
        lines.append(line)
    for e in pending[-max_items:]:
        lines.append(f"- {_entry_line(e)} -> still pending")
    return "\n".join(lines)


def derive_lessons(entries: Iterable[dict]) -> list[str]:
    """A few data-driven, deterministic lessons to steer future calls (pure)."""
    entries = list(entries)
    out: list[str] = []
    stats = score_decisions(entries)
    if stats["resolved"]:
        if stats["hit_rate"] is not None:
            out.append(
                f"Your calls have beaten the benchmark {stats['hit_rate']:.0%} of the time "
                f"across {stats['resolved']} resolved decisions."
            )
        if stats["avg_alpha_pct"] is not None:
            tag = "outperformed" if stats["avg_alpha_pct"] > 0 else "underperformed"
            out.append(f"On average you {tag} the benchmark by {stats['avg_alpha_pct']:+.1%} per decision.")

    by_state: dict[str, list[float]] = {}
    for e in entries:
        a = _num(e.get("alpha_return"))
        if a is not None:
            by_state.setdefault(str(e.get("state", "")), []).append(a)
    for state, arr in sorted(by_state.items()):
        if len(arr) >= 2 and (sum(arr) / len(arr)) < 0:
            out.append(
                f"Your {state} calls have struggled (avg {sum(arr)/len(arr):+.1%}) — "
                f"raise the bar before acting on {state} again."
            )
    return out


def lessons_block(entries: Iterable[dict]) -> str:
    """Combined deterministic lessons + history for prompt injection (pure)."""
    derived = derive_lessons(entries)
    hist = format_lessons(entries)
    parts: list[str] = []
    if derived:
        parts.append("KEY LESSONS:\n" + "\n".join(f"- {d}" for d in derived))
    if hist:
        parts.append("RECENT DECISION HISTORY:\n" + hist)
    return "\n\n".join(parts)


def reflect(entries: Iterable[dict]) -> str:
    """Reflection over the decision log. Deterministic today (LLM can wrap later)."""
    return lessons_block(entries)
