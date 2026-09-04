"""Decision memory log — learn from past trades.

Inspired by TradingAgents' TradingMemoryLog. Two-phase approach:

Phase A (Write): After every consolidated analysis, store the decision
as a "pending" entry with the full signal, reasoning, and metadata.

Phase B (Resolve): On subsequent runs for the same ticker, fetch actual
price returns after the holding period. Generate a reflection on what
held/failed. Inject past lessons into future agent prompts.

Storage: append-only markdown file (portable, no DB migration needed).
Each entry has a structured header line for fast scanning, plus
DECISION and REFLECTION sections.
"""

import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# Default holding period to evaluate outcomes (trading days)
DEFAULT_HOLDING_DAYS = 5

# Default paths
_MEMORY_DIR = os.path.join(os.path.expanduser("~"), ".invest", "memory")
_MEMORY_FILE = "decision_log.md"


class DecisionMemoryLog:
    """Append-only markdown log of trading decisions and reflections."""

    # HTML comment as hard delimiter — can't appear in LLM prose
    _SEPARATOR = "\n\n<!-- ENTRY_END -->\n\n"
    _DECISION_RE = re.compile(r"DECISION:\n(.*?)(?=\nREFLECTION:|\Z)", re.DOTALL)
    _REFLECTION_RE = re.compile(r"REFLECTION:\n(.*?)$", re.DOTALL)

    def __init__(self, memory_dir: str | None = None, max_entries: int | None = None):
        self._dir = Path(memory_dir or _MEMORY_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / _MEMORY_FILE
        self._max_entries = max_entries

    # ── Phase A: Write ──────────────────────────────────────

    def store_decision(
        self,
        symbol: str,
        trade_date: str,
        final_state: str,
        confidence: float,
        summary: str,
        entry_zone: str,
        stop_loss: str,
        take_profit: str,
        risk_level: str,
        strategy_breakdown: list[dict] | None = None,
        sentiment_band: str | None = None,
        sentiment_score: float | None = None,
    ) -> None:
        """Append a pending decision entry."""
        # Idempotency: skip if already stored for this symbol+date
        if self._path.exists():
            raw = self._path.read_text(encoding="utf-8")
            for line in raw.splitlines():
                if line.startswith(f"[{trade_date} | {symbol} |") and line.endswith("| pending]"):
                    return

        # Build a structured tag for fast scanning
        conf_pct = f"{confidence:.0f}%"
        tag = f"[{trade_date} | {symbol} | {final_state} | conf:{conf_pct} | pending]"

        # Build the decision block
        parts = [
            f"FINAL STATE: {final_state}",
            f"CONFIDENCE: {conf_pct}",
            f"SUMMARY: {summary}",
            f"ENTRY ZONE: {entry_zone}",
            f"STOP LOSS: {stop_loss}",
            f"TAKE PROFIT: {take_profit}",
            f"RISK LEVEL: {risk_level}",
        ]
        if sentiment_band:
            parts.append(f"SENTIMENT: {sentiment_band} ({sentiment_score:.1f}/10)" if sentiment_score else f"SENTIMENT: {sentiment_band}")
        if strategy_breakdown:
            strat_lines = [
                f"  - {s['strategy']}: {s['state']} ({s['confidence']:.0%})"
                + (f" win:{s['win_rate']:.0f}%" if s.get('win_rate') else "")
                for s in strategy_breakdown if not s.get('error')
            ]
            if strat_lines:
                parts.append("STRATEGIES:\n" + "\n".join(strat_lines))

        decision_text = "\n".join(parts)
        entry = f"{tag}\n\nDECISION:\n{decision_text}{self._SEPARATOR}"

        with open(self._path, "a", encoding="utf-8") as f:
            f.write(entry)

        logger.info(f"Stored decision for {symbol} on {trade_date}: {final_state}")

    # ── Phase A: Read ───────────────────────────────────────

    def load_entries(self) -> list[dict]:
        """Parse all entries from the log."""
        if not self._path.exists():
            return []
        text = self._path.read_text(encoding="utf-8")
        raw_entries = [e.strip() for e in text.split(self._SEPARATOR) if e.strip()]
        entries = []
        for raw in raw_entries:
            parsed = self._parse_entry(raw)
            if parsed:
                entries.append(parsed)
        return entries

    def get_pending_entries(self, symbol: str | None = None) -> list[dict]:
        """Return entries with pending status, optionally filtered by symbol."""
        entries = [e for e in self.load_entries() if e.get("pending")]
        if symbol:
            entries = [e for e in entries if e.get("symbol") == symbol]
        return entries

    def get_past_context(
        self,
        symbol: str,
        n_same: int = 5,
        n_cross: int = 3,
    ) -> str:
        """Build a context string from past decisions for prompt injection.

        Returns resolved (non-pending) entries: most recent N for the same
        ticker, plus M cross-ticker lessons.
        """
        entries = [e for e in self.load_entries() if not e.get("pending")]
        if not entries:
            return ""

        same, cross = [], []
        for e in reversed(entries):  # most recent first
            if len(same) >= n_same and len(cross) >= n_cross:
                break
            if e.get("symbol") == symbol and len(same) < n_same:
                same.append(e)
            elif e.get("symbol") != symbol and len(cross) < n_cross:
                cross.append(e)

        if not same and not cross:
            return ""

        parts = []
        if same:
            parts.append(f"Past analyses of {symbol} (most recent first):")
            parts.extend(self._format_full(e) for e in same)
        if cross:
            parts.append("Recent cross-ticker lessons:")
            parts.extend(self._format_reflection_only(e) for e in cross)

        return "\n\n".join(parts)

    # ── Phase B: Resolve Outcomes ───────────────────────────

    def update_with_outcome(
        self,
        symbol: str,
        trade_date: str,
        raw_return: float,
        alpha_return: float,
        holding_days: int,
        reflection: str,
        resolution_date: str | None = None,
    ) -> None:
        """Replace pending tag with resolved outcome + reflection."""
        if not self._path.exists():
            return

        text = self._path.read_text(encoding="utf-8")
        blocks = text.split(self._SEPARATOR)

        pending_prefix = f"[{trade_date} | {symbol} |"
        raw_pct = f"{raw_return:+.1%}"
        alpha_pct = f"{alpha_return:+.1%}"

        updated = False
        new_blocks = []
        for block in blocks:
            stripped = block.strip()
            if not stripped:
                new_blocks.append(block)
                continue

            lines = stripped.splitlines()
            tag_line = lines[0].strip()

            if (
                not updated
                and tag_line.startswith(pending_prefix)
                and tag_line.endswith("| pending]")
            ):
                # Parse fields from existing tag
                fields = [f.strip() for f in tag_line[1:-1].split("|")]
                # Extract state and confidence from existing tag
                state = fields[2] if len(fields) > 2 else "unknown"
                conf = fields[3] if len(fields) > 3 else ""

                new_tag = (
                    f"[{trade_date} | {symbol} | {state} | {conf} "
                    f"| {raw_pct} | {alpha_pct} | {holding_days}d"
                    + (f" | resolved:{resolution_date}" if resolution_date else "")
                    + "]"
                )
                rest = "\n".join(lines[1:])
                new_blocks.append(
                    f"{new_tag}\n\n{rest.lstrip()}\n\nREFLECTION:\n{reflection}"
                )
                updated = True
            else:
                new_blocks.append(block)

        if not updated:
            return

        new_blocks = self._apply_rotation(new_blocks)
        new_text = self._SEPARATOR.join(new_blocks)
        tmp_path = self._path.with_suffix(".tmp")
        tmp_path.write_text(new_text, encoding="utf-8")
        tmp_path.replace(self._path)

        logger.info(
            f"Resolved {symbol} on {trade_date}: raw={raw_pct}, alpha={alpha_pct}"
        )

    def batch_update_with_outcomes(self, updates: list[dict]) -> None:
        """Apply multiple outcome updates in a single atomic write."""
        if not self._path.exists() or not updates:
            return

        text = self._path.read_text(encoding="utf-8")
        blocks = text.split(self._SEPARATOR)
        update_map = {(u["trade_date"], u["symbol"]): u for u in updates}

        new_blocks = []
        for block in blocks:
            stripped = block.strip()
            if not stripped:
                new_blocks.append(block)
                continue

            lines = stripped.splitlines()
            tag_line = lines[0].strip()

            matched = False
            for (trade_date, symbol), upd in list(update_map.items()):
                pending_prefix = f"[{trade_date} | {symbol} |"
                if tag_line.startswith(pending_prefix) and tag_line.endswith("| pending]"):
                    fields = [f.strip() for f in tag_line[1:-1].split("|")]
                    state = fields[2] if len(fields) > 2 else "unknown"
                    conf = fields[3] if len(fields) > 3 else ""

                    raw_pct = f"{upd['raw_return']:+.1%}"
                    alpha_pct = f"{upd['alpha_return']:+.1%}"
                    new_tag = (
                        f"[{trade_date} | {symbol} | {state} | {conf} "
                        f"| {raw_pct} | {alpha_pct} | {upd['holding_days']}d"
                        + (f" | resolved:{upd.get('resolution_date')}" if upd.get('resolution_date') else "")
                        + "]"
                    )
                    rest = "\n".join(lines[1:])
                    new_blocks.append(
                        f"{new_tag}\n\n{rest.lstrip()}\n\nREFLECTION:\n{upd['reflection']}"
                    )
                    del update_map[(trade_date, symbol)]
                    matched = True
                    break

            if not matched:
                new_blocks.append(block)

        new_blocks = self._apply_rotation(new_blocks)
        new_text = self._SEPARATOR.join(new_blocks)
        tmp_path = self._path.with_suffix(".tmp")
        tmp_path.write_text(new_text, encoding="utf-8")
        tmp_path.replace(self._path)

    # ── Helpers ─────────────────────────────────────────────

    def _apply_rotation(self, blocks: list[str]) -> list[str]:
        """Drop oldest resolved blocks when count exceeds max_entries."""
        if not self._max_entries or self._max_entries <= 0:
            return blocks

        decisions = []
        for block in blocks:
            stripped = block.strip()
            if not stripped:
                decisions.append((block, False))
                continue
            tag_line = stripped.splitlines()[0].strip()
            is_resolved = (
                tag_line.startswith("[")
                and tag_line.endswith("]")
                and not tag_line.endswith("| pending]")
            )
            decisions.append((block, is_resolved))

        resolved_count = sum(1 for _, r in decisions if r)
        if resolved_count <= self._max_entries:
            return blocks

        to_drop = resolved_count - self._max_entries
        kept = []
        for block, is_resolved in decisions:
            if is_resolved and to_drop > 0:
                to_drop -= 1
                continue
            kept.append(block)
        return kept

    def _parse_entry(self, raw: str) -> dict | None:
        lines = raw.strip().splitlines()
        if not lines:
            return None
        tag_line = lines[0].strip()
        if not (tag_line.startswith("[") and tag_line.endswith("]")):
            return None

        fields = [f.strip() for f in tag_line[1:-1].split("|")]
        if len(fields) < 4:
            return None

        # Parse the tag fields
        # Format: [date | symbol | state | conf:X% | pending]
        # or:     [date | symbol | state | conf:X% | +5.2% | -2.1% | 5d | resolved:2024-01-15]
        entry = {
            "date": fields[0],
            "symbol": fields[1],
            "state": fields[2],
            "confidence": fields[3].replace("conf:", "").strip() if fields[3].startswith("conf:") else fields[3],
            "pending": any(f.strip() == "pending" for f in fields),
            "raw_return": None,
            "alpha_return": None,
            "holding_days": None,
            "resolved": None,
        }

        # Parse resolved fields
        for f in fields[4:]:
            f = f.strip()
            if f == "pending":
                continue
            elif f.startswith("resolved:"):
                entry["resolved"] = f[len("resolved:"):].strip()
            elif "%" in f and not f.startswith("conf:"):
                if entry["raw_return"] is None:
                    entry["raw_return"] = f
                elif entry["alpha_return"] is None:
                    entry["alpha_return"] = f
            elif f.endswith("d") and f[:-1].isdigit():
                entry["holding_days"] = int(f[:-1])

        # Parse body sections
        body = "\n".join(lines[1:]).strip()
        decision_match = self._DECISION_RE.search(body)
        reflection_match = self._REFLECTION_RE.search(body)
        entry["decision"] = decision_match.group(1).strip() if decision_match else ""
        entry["reflection"] = reflection_match.group(1).strip() if reflection_match else ""

        return entry

    def _format_full(self, e: dict) -> str:
        raw = e.get("raw_return") or "n/a"
        alpha = e.get("alpha_return") or "n/a"
        holding = e.get("holding_days") or "n/a"
        tag = f"[{e['date']} | {e['symbol']} | {e['state']} | {raw} | {alpha} | {holding}]"
        parts = [tag, f"DECISION:\n{e['decision']}"]
        if e.get("reflection"):
            parts.append(f"REFLECTION:\n{e['reflection']}")
        return "\n\n".join(parts)

    def _format_reflection_only(self, e: dict) -> str:
        tag = f"[{e['date']} | {e['symbol']} | {e['state']} | {e.get('raw_return') or 'n/a'}]"
        if e.get("reflection"):
            return f"{tag}\n{e['reflection']}"
        text = e.get("decision", "")[:300]
        suffix = "..." if len(e.get("decision", "")) > 300 else ""
        return f"{tag}\n{text}{suffix}"
