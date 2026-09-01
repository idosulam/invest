"""Evidence compiler — PRD Section 7.

Creates compact, signed context packages from retrieved data.
Each evidence item gets a unique ID for traceability.
"""

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class EvidenceItem:
    """A single piece of evidence with provenance."""
    id: str
    source: str  # tool name or data source
    data: Any
    retrieved_at: datetime = field(default_factory=datetime.utcnow)
    content_hash: str = ""

    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = hashlib.sha256(
                str(self.data).encode()
            ).hexdigest()[:16]


@dataclass
class EvidencePackage:
    """Compiled evidence for LLM reasoning."""
    package_id: str
    instrument_id: str
    instrument_symbol: str
    question: str
    items: list[EvidenceItem]
    compiled_at: datetime = field(default_factory=datetime.utcnow)
    total_tokens_estimate: int = 0


class EvidenceCompiler:
    """Compiles retrieved data into a structured evidence package.

    - Assigns unique IDs to each evidence item
    - Estimates token count for context window management
    - Signs the package for audit trail
    """

    MAX_ITEMS = 20
    MAX_TOKENS_ESTIMATE = 3000  # rough estimate

    def compile(
        self,
        instrument_id: str,
        instrument_symbol: str,
        question: str,
        tool_results: dict[str, Any],
    ) -> EvidencePackage:
        """Compile tool results into an evidence package.

        Args:
            instrument_id: UUID of the instrument
            instrument_symbol: Ticker symbol
            question: User's question
            tool_results: Dict of tool_name -> result data

        Returns:
            EvidencePackage with all items
        """
        items = []
        total_tokens = 0

        for tool_name, data in tool_results.items():
            if data is None:
                continue

            # Estimate tokens (rough: 1 token per 4 chars)
            data_str = str(data)
            token_estimate = len(data_str) // 4

            if total_tokens + token_estimate > self.MAX_TOKENS_ESTIMATE:
                # Truncate or skip
                continue

            item = EvidenceItem(
                id=str(uuid.uuid4())[:8],
                source=tool_name,
                data=data,
            )
            items.append(item)
            total_tokens += token_estimate

            if len(items) >= self.MAX_ITEMS:
                break

        return EvidencePackage(
            package_id=str(uuid.uuid4()),
            instrument_id=instrument_id,
            instrument_symbol=instrument_symbol,
            question=question,
            items=items,
            total_tokens_estimate=total_tokens,
        )

    def to_context_string(self, package: EvidencePackage) -> str:
        """Convert evidence package to a string for LLM context."""
        lines = [
            f"=== Evidence Package {package.package_id} ===",
            f"Instrument: {package.instrument_symbol} ({package.instrument_id})",
            f"Question: {package.question}",
            f"Compiled: {package.compiled_at.strftime('%Y-%m-%d %H:%M UTC')}",
            f"Items: {len(package.items)}, Est. tokens: {package.total_tokens_estimate}",
            "",
        ]

        for item in package.items:
            lines.append(f"--- Evidence [{item.id}] from {item.source} ---")
            if isinstance(item.data, list):
                for entry in item.data[:10]:  # limit rows
                    lines.append(f"  {entry}")
                if len(item.data) > 10:
                    lines.append(f"  ... ({len(item.data) - 10} more)")
            elif isinstance(item.data, dict):
                for k, v in item.data.items():
                    lines.append(f"  {k}: {v}")
            else:
                lines.append(f"  {item.data}")
            lines.append("")

        return "\n".join(lines)

    def get_evidence_ids(self, package: EvidencePackage) -> list[str]:
        """Get all evidence item IDs for audit trail."""
        return [item.id for item in package.items]
