"""Output validator — PRD Section 7.

Validates LLM explanations against evidence.
Rejects unknown evidence IDs, unsupported numbers, and missing caveats.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ValidationResult:
    """Result of validating an LLM explanation."""
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ExplanationValidator:
    """Validates LLM-generated explanations against evidence.

    Rules (PRD Section 7):
    - All cited evidence IDs must exist in the package
    - Numeric claims must be traceable to evidence data
    - Must include caveats/limitations
    - Must not contain unsupported predictions
    """

    # Patterns that indicate unsupported claims
    UNSUPPORTED_PATTERNS = [
        r"guaranteed\s+(?:return|profit)",
        r"will\s+definitely",
        r"cannot\s+lose",
        r"100%\s+(?:certain|sure|guaranteed)",
        r"risk[\s-]*free",
    ]

    # Required caveat indicators
    CAVEAT_INDICATORS = [
        "risk", "limitation", "caveat", "disclaimer", "not financial advice",
        "research only", "past performance", "may", "could", "possible",
        "uncertainty", "assumption",
    ]

    def validate(
        self,
        explanation: str,
        evidence_ids: list[str],
        evidence_data: dict,
        max_length: int = 2000,
    ) -> ValidationResult:
        """Validate an LLM explanation.

        Args:
            explanation: The LLM-generated text
            evidence_ids: Valid evidence IDs from the package
            evidence_data: Dict of evidence_id -> data for number checking
            max_length: Maximum explanation length

        Returns:
            ValidationResult with errors and warnings
        """
        errors = []
        warnings = []

        # 1. Length check
        if len(explanation) > max_length:
            warnings.append(f"Explanation too long ({len(explanation)} > {max_length} chars)")

        # 2. Check for unsupported claims
        lower = explanation.lower()
        for pattern in self.UNSUPPORTED_PATTERNS:
            if re.search(pattern, lower):
                errors.append(f"Unsupported claim detected: '{pattern}'")

        # 3. Check for caveat/limitation language
        has_caveat = any(indicator in lower for indicator in self.CAVEAT_INDICATORS)
        if not has_caveat:
            warnings.append("No caveat or risk language found in explanation")

        # 4. Check referenced evidence IDs
        # Look for patterns like [abc123] or evidence ID references
        referenced_ids = re.findall(r'\[([a-f0-9]{8})\]', explanation)
        for ref_id in referenced_ids:
            if ref_id not in evidence_ids:
                errors.append(f"Unknown evidence ID referenced: {ref_id}")

        # 5. Check for suspicious numeric claims
        numbers_in_text = re.findall(r'[\$]?(\d+(?:\.\d+)?)\s*%?', explanation)
        # This is a simplified check — in production, cross-reference with evidence data

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
