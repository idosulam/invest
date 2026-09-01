"""Reasoning engine — PRD Section 7.

Orchestrates the LLM explanation workflow:
1. User asks a question
2. Intent router selects allowlisted read-only tools
3. Tools retrieve stored data
4. Evidence compiler creates context package
5. LLM returns JSON matching ExplanationSchema
6. Validator rejects bad output
7. Renderer produces readable explanation
8. Store prompt, tool calls, evidence IDs, answer, validation

For MVP, uses a deterministic template-based approach when no LLM
is configured, with hooks for local LLM (Ollama/vLLM).
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from packages.reasoning.tools.market_tools import ALLOWLISTED_TOOLS
from packages.reasoning.evidence.compiler import EvidenceCompiler, EvidencePackage
from packages.reasoning.validation.validator import ExplanationValidator, ValidationResult


@dataclass
class ExplanationRequest:
    """A request for explanation."""
    question: str
    instrument_id: uuid.UUID
    context_type: str = "signal"  # signal, backtest, general


@dataclass
class ExplanationResult:
    """Final explanation output."""
    id: str
    question: str
    answer: str
    evidence_ids: list[str]
    evidence_summary: dict
    validation: ValidationResult
    template_version: str = "1.0.0"
    tool_calls: list[dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


class ReasoningEngine:
    """Orchestrates the evidence-based explanation workflow.

    MVP: Template-based explanations when no LLM is available.
    Production: Routes to local LLM (Ollama/vLLM) with evidence context.
    """

    def __init__(self, llm_base_url: Optional[str] = None, llm_model: str = "qwen3:8b"):
        self.compiler = EvidenceCompiler()
        self.validator = ExplanationValidator()
        self.llm_base_url = llm_base_url  # e.g., "http://localhost:11434" for Ollama
        self.llm_model = llm_model

    async def explain(
        self,
        db: AsyncSession,
        request: ExplanationRequest,
    ) -> ExplanationResult:
        """Generate an explanation for a question about an instrument.

        1. Select tools based on intent
        2. Retrieve evidence
        3. Compile evidence package
        4. Generate explanation (template or LLM)
        5. Validate output
        6. Return result
        """
        # Step 1: Select tools based on question intent
        tools_to_call = self._select_tools(request.question, request.context_type)

        # Step 2: Retrieve evidence
        tool_results = {}
        tool_calls = []
        for tool_name in tools_to_call:
            tool_fn = ALLOWLISTED_TOOLS.get(tool_name)
            if not tool_fn:
                continue

            try:
                if tool_name in ("get_instrument_info", "get_recent_bars", "get_instrument_signals", "get_fundamentals"):
                    result = await tool_fn(db, request.instrument_id)
                elif tool_name == "get_strategy_card":
                    # Would need strategy_version_id from signal
                    result = None
                elif tool_name == "get_backtest_summary":
                    result = await tool_fn(db)
                else:
                    result = None

                tool_results[tool_name] = result
                tool_calls.append({
                    "tool": tool_name,
                    "success": result is not None,
                    "items": len(result) if isinstance(result, list) else (1 if result else 0),
                })
            except Exception as e:
                tool_calls.append({
                    "tool": tool_name,
                    "success": False,
                    "error": str(e),
                })

        # Step 3: Compile evidence package
        # Get instrument symbol
        inst_info = tool_results.get("get_instrument_info", {})
        symbol = inst_info.get("symbol", "?") if inst_info else "?"

        package = self.compiler.compile(
            instrument_id=str(request.instrument_id),
            instrument_symbol=symbol,
            question=request.question,
            tool_results=tool_results,
        )

        # Step 4: Generate explanation
        explanation = self._generate_explanation(request, package, tool_results)

        # Step 5: Validate
        evidence_data = {item.id: item.data for item in package.items}
        validation = self.validator.validate(
            explanation=explanation,
            evidence_ids=self.compiler.get_evidence_ids(package),
            evidence_data=evidence_data,
        )

        # Step 6: Build result
        return ExplanationResult(
            id=str(uuid.uuid4()),
            question=request.question,
            answer=explanation,
            evidence_ids=self.compiler.get_evidence_ids(package),
            evidence_summary={
                item.id: {"source": item.source, "hash": item.content_hash}
                for item in package.items
            },
            validation=validation,
            tool_calls=tool_calls,
        )

    def _select_tools(self, question: str, context_type: str) -> list[str]:
        """Select which tools to call based on question intent."""
        lower = question.lower()
        tools = ["get_instrument_info"]  # always get basic info

        if any(w in lower for w in ["price", "chart", "trend", "recent", "move", "volume"]):
            tools.append("get_recent_bars")

        if any(w in lower for w in ["signal", "buy", "sell", "entry", "exit", "strategy", "why"]):
            tools.append("get_instrument_signals")

        if any(w in lower for w in ["fundamental", "earnings", "pe", "revenue", "valuation", "margin"]):
            tools.append("get_fundamentals")

        if any(w in lower for w in ["backtest", "performance", "historical", "sharpe"]):
            tools.append("get_backtest_summary")

        if context_type == "signal":
            if "get_instrument_signals" not in tools:
                tools.append("get_instrument_signals")

        return tools

    def _generate_explanation(
        self,
        request: ExplanationRequest,
        package: EvidencePackage,
        tool_results: dict,
    ) -> str:
        """Generate explanation text.

        MVP: Template-based. Production: LLM with evidence context.
        """
        # Try LLM first if configured
        if self.llm_base_url:
            try:
                return self._llm_explanation(request, package, tool_results)
            except Exception:
                pass  # Fall back to template

        return self._template_explanation(request, package, tool_results)

    def _llm_explanation(
        self,
        request: ExplanationRequest,
        package: EvidencePackage,
        tool_results: dict,
    ) -> str:
        """Generate explanation using local LLM (Ollama/vLLM)."""
        import httpx

        # Build evidence context for LLM
        context_parts = []
        for item in package.items:
            context_parts.append(f"[{item.source}] {item.data}")

        evidence_context = "\n".join(context_parts)

        prompt = f"""You are a financial research assistant. Answer the user's question using ONLY the provided evidence.

Question: {request.question}
Instrument: {package.instrument_symbol}

Evidence:
{evidence_context}

Provide a clear, concise analysis. Reference specific data points from the evidence.
Always include a disclaimer that this is research analysis, not financial advice.
"""

        response = httpx.post(
            f"{self.llm_base_url}/api/generate",
            json={
                "model": self.llm_model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 500},
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "")

    def _template_explanation(
        self,
        request: ExplanationRequest,
        package: EvidencePackage,
        tool_results: dict,
    ) -> str:
        """Template-based explanation (MVP fallback)."""
        inst_info = tool_results.get("get_instrument_info", {})
        symbol = inst_info.get("symbol", "?") if inst_info else "?"
        name = inst_info.get("name", "?") if inst_info else "?"
        sector = inst_info.get("sector", "—") if inst_info else "—"

        signals = tool_results.get("get_instrument_signals", [])
        bars = tool_results.get("recent_bars", tool_results.get("get_recent_bars", []))
        fundamentals = tool_results.get("get_fundamentals", [])

        parts = []

        # Header
        parts.append(f"## Analysis: {symbol} ({name})")
        parts.append(f"*Sector: {sector}*\n")

        # Price context
        if bars and len(bars) > 0:
            latest = bars[-1]
            prev = bars[-2] if len(bars) > 1 else None
            change = ((latest["close"] - prev["close"]) / prev["close"] * 100) if prev else 0
            parts.append(f"**Recent Price:** ${latest['close']:.2f} ({'+' if change >= 0 else ''}{change:.1f}%)")
            parts.append(f"30-day range: ${min(b['low'] for b in bars):.2f} — ${max(b['high'] for b in bars):.2f}\n")

        # Signal context
        if signals:
            latest_sig = signals[0]
            parts.append(f"**Latest Signal:** {latest_sig['state']} ({latest_sig['strategy']})")
            parts.append(f"Confidence: {latest_sig['confidence']*100:.0f}% · Quality: {latest_sig['quality_gate']}")
            if latest_sig.get("reason_codes"):
                parts.append(f"Evidence: {', '.join(latest_sig['reason_codes'])}")
            if latest_sig.get("limitations"):
                parts.append(f"Limitations: {', '.join(latest_sig['limitations'])}")
            parts.append("")

        # Fundamentals
        if fundamentals:
            parts.append("**Key Fundamentals:**")
            for f in fundamentals[:5]:
                parts.append(f"- {f['taxonomy']}: {f['value']:.2f} {f['unit']}")
            parts.append("")

        # Caveats
        parts.append("---")
        parts.append("*⚠️ This is research analysis, not financial advice. Past performance does not guarantee future results. All signals are for paper trading and research purposes only.*")

        return "\n".join(parts)
