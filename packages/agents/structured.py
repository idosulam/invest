"""Structured output helpers for Ollama + Pydantic.

Provides a clean interface to get typed Pydantic models from LLM responses.
Supports two strategies:
1. JSON mode (Ollama supports format="json") — preferred
2. Text parsing fallback with regex extraction of JSON blocks
"""

from __future__ import annotations

import json
import logging
import re
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def _extract_json(text: str) -> dict | None:
    """Try to extract a JSON object from LLM text output.

    Handles: raw JSON, JSON wrapped in markdown code blocks, text with
    embedded JSON objects, trailing commas, single quotes, etc.
    """
    # Strip markdown code fences
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()

    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try to find a JSON object in the text (greedy)
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        candidate = match.group()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        # Try fixing common LLM JSON issues
        # Remove trailing commas before } or ]
        fixed = re.sub(r",\s*([}\]])", r"\1", candidate)
        # Replace single quotes with double quotes (crude but often works)
        fixed = fixed.replace("'", '"')
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

    return None


def _build_schema_prompt(schema: Type[BaseModel]) -> str:
    """Build a prompt fragment describing the expected JSON schema."""
    schema_dict = schema.model_json_schema()
    properties = schema_dict.get("properties", {})
    required = set(schema_dict.get("required", []))

    lines = ["Respond with a JSON object with these fields:"]
    for name, prop in properties.items():
        desc = prop.get("description", "")
        field_type = prop.get("type", "string")
        req_mark = " (required)" if name in required else " (optional)"
        enum_vals = prop.get("enum")
        if enum_vals:
            lines.append(f'  "{name}": one of {enum_vals}{req_mark} — {desc}')
        else:
            lines.append(f'  "{name}": {field_type}{req_mark} — {desc}')

    lines.append("")
    lines.append("Return ONLY the JSON object, no other text.")
    return "\n".join(lines)


def structured_chat(
    client,
    system: str,
    user: str,
    schema: Type[T],
    temperature: float = 0.2,
    max_retries: int = 3,
) -> T | None:
    """Call the LLM and parse the response into a Pydantic model.

    Args:
        client: OllamaClient instance
        system: System prompt
        user: User prompt
        schema: Pydantic model class to parse into
        temperature: LLM temperature
        max_retries: Number of retries on parse failure

    Returns:
        Parsed Pydantic model or None if all retries fail.
    """
    schema_instruction = _build_schema_prompt(schema)
    full_system = f"{system}\n\n{schema_instruction}"

    for attempt in range(max_retries + 1):
        try:
            raw = client.chat(full_system, user, temperature=temperature)

            # Try JSON mode parse
            data = _extract_json(raw)
            if data is None:
                logger.warning(
                    "Attempt %d: could not extract JSON from LLM output (len=%d): %s",
                    attempt + 1, len(raw), raw[:500],
                )
                continue

            return schema.model_validate(data)

        except ValidationError as e:
            logger.warning(
                "Attempt %d: schema validation failed: %s",
                attempt + 1, e,
            )
            continue
        except RuntimeError as e:
            logger.error("LLM call failed: %s", e)
            return None

    logger.error("All %d attempts failed for structured output", max_retries + 1)
    return None


def structured_chat_json(
    client,
    system: str,
    user: str,
    schema: Type[T],
    temperature: float = 0.2,
    max_retries: int = 2,
) -> T | None:
    """Call Ollama with JSON format mode enabled.

    Uses Ollama's native format="json" parameter for more reliable
    structured output. Falls back to text parsing if the model doesn't
    support it.
    """
    schema_instruction = _build_schema_prompt(schema)
    full_system = f"{system}\n\n{schema_instruction}"

    for attempt in range(max_retries + 1):
        try:
            # Try with JSON format mode
            raw = client.chat(
                full_system, user,
                temperature=temperature,
                format="json",
            )

            data = _extract_json(raw)
            if data is None:
                logger.warning("Attempt %d: JSON parse failed, retrying...", attempt + 1)
                continue

            return schema.model_validate(data)

        except ValidationError as e:
            logger.warning("Attempt %d: validation failed: %s", attempt + 1, e)
            # On validation failure, try without format hint
            try:
                raw = client.chat(full_system, user, temperature=temperature)
                data = _extract_json(raw)
                if data:
                    return schema.model_validate(data)
            except Exception:
                pass
            continue
        except (RuntimeError, TypeError) as e:
            # format="json" might not be supported, fall back to plain
            logger.info("JSON format mode not supported, falling back to text parsing: %s", e)
            return structured_chat(client, system, user, schema, temperature, max_retries)

    logger.error("All %d attempts failed", max_retries + 1)
    return None
