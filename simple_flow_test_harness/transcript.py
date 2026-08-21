from __future__ import annotations

import json
import re
from typing import Any


MAX_PROMPT_FIELD_CHARS = 500
MAX_RESPONSE_CHARS = 900
MAX_GENERIC_TEXT_CHARS = 700


def compact_fixture_prompt(prompt: str) -> dict[str, str]:
    summary: dict[str, str] = {}
    for line in prompt.splitlines():
        stripped = line.strip()
        if stripped.startswith("USER_ACTION TO EXECUTE NOW:"):
            summary["user_action"] = _truncate(stripped.split(":", 1)[1].strip(), MAX_PROMPT_FIELD_CHARS)
        elif stripped.startswith("Scenario ID:"):
            summary["scenario_id"] = _truncate(stripped.split(":", 1)[1].strip(), MAX_PROMPT_FIELD_CHARS)
        elif stripped.startswith("Scenario Purpose:"):
            summary["purpose"] = _truncate(stripped.split(":", 1)[1].strip(), MAX_PROMPT_FIELD_CHARS)
        elif stripped.startswith("Action Reference:"):
            summary["action_ref"] = _truncate(stripped.split(":", 1)[1].strip(), MAX_PROMPT_FIELD_CHARS)
        elif stripped.startswith("GitHub test repository:"):
            summary["test_repo"] = _truncate(stripped.split(":", 1)[1].strip(), MAX_PROMPT_FIELD_CHARS)
        elif stripped.startswith("Use this GitHub CLI executable"):
            summary["github_cli"] = "configured"

    if "user_action" not in summary:
        summary["user_action"] = _truncate(_single_line(prompt), MAX_PROMPT_FIELD_CHARS)
    return summary


def compact_codex_response(stdout: str, stderr: str, exit_code: int | None) -> dict[str, Any]:
    json_texts: list[str] = []
    plain_texts: list[str] = []
    for stream_text in (stdout, stderr):
        for line in stream_text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("{"):
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError:
                    plain_texts.append(stripped)
                    continue
                json_texts.extend(_text_values(payload))
            else:
                plain_texts.append(stripped)

    selected = _dedupe(json_texts or plain_texts)
    meaningful_response = _truncate(
        _single_line(" ".join(selected)) or "No meaningful response captured.",
        MAX_RESPONSE_CHARS,
    )
    return {
        "exit_code": exit_code,
        "meaningful_response": meaningful_response,
        "stdout_chars": len(stdout),
        "stderr_chars": len(stderr),
    }


def compact_text(text: str, limit: int = MAX_GENERIC_TEXT_CHARS) -> str:
    return _truncate(_single_line(text), limit)


def _text_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if _looks_like_response_text(value) else []
    if isinstance(value, list):
        texts: list[str] = []
        for item in value:
            texts.extend(_text_values(item))
        return texts
    if not isinstance(value, dict):
        return []

    texts: list[str] = []
    for key, child in value.items():
        if key in {"id", "thread_id", "type", "role", "status"}:
            continue
        if key in {"text", "message", "content", "delta", "output", "response", "summary", "item"}:
            texts.extend(_text_values(child))
        elif isinstance(child, (dict, list)):
            texts.extend(_text_values(child))
    return texts


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = _single_line(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _looks_like_response_text(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    if re.fullmatch(r"[A-Za-z0-9_-]{6,}", stripped):
        return False
    if stripped in {"thread.started", "turn.started", "turn.completed", "output_text"}:
        return False
    return True


def _single_line(text: str) -> str:
    return " ".join(text.split())


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."
