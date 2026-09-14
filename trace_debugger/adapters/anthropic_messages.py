"""Anthropic Messages API-style turns → Format B.

Accepts plain dict messages (no ``anthropic`` package). Typical shape::

    {"role": "user"|"assistant",
     "content": "..." | [
       {"type": "text", "text": "..."},
       {"type": "tool_use", "id": "...", "name": "...", "input": {...}},
       {"type": "tool_result", "tool_use_id": "...", "content": "...", "is_error": false}
     ]}
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from ..harness import RunContext, StepEvent, build_trajectory_dict


def _as_blocks(content: Any) -> list[dict[str, Any]]:
    if content is None:
        return []
    if isinstance(content, str):
        return [{"type": "text", "text": content}] if content else []
    if isinstance(content, list):
        out: list[dict[str, Any]] = []
        for block in content:
            if isinstance(block, str):
                out.append({"type": "text", "text": block})
            elif isinstance(block, dict):
                out.append(block)
        return out
    return [{"type": "text", "text": str(content)}]


def _text_from_blocks(blocks: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for b in blocks:
        if (b.get("type") or "") == "text":
            parts.append(str(b.get("text") or ""))
        elif "text" in b and b.get("type") is None:
            parts.append(str(b.get("text") or ""))
    return "".join(parts)


def _tool_result_text(block: dict[str, Any]) -> str:
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return _text_from_blocks(_as_blocks(content))
    if content is None:
        return ""
    return str(content)


def _first_user_query(messages: list[dict[str, Any]]) -> str:
    for msg in messages:
        if (msg.get("role") or "") != "user":
            continue
        blocks = _as_blocks(msg.get("content"))
        # Prefer pure text user turns (skip tool_result-only)
        if any((b.get("type") or "") == "tool_result" for b in blocks):
            text = _text_from_blocks(blocks)
            if text.strip():
                return text
            continue
        text = _text_from_blocks(blocks)
        if text.strip():
            return text
    return ""


def anthropic_messages_to_step_events(
    messages: list[dict[str, Any]],
) -> tuple[list[StepEvent], str]:
    """Map Anthropic-style messages to StepEvents + inferred final_answer."""
    events: list[StepEvent] = []
    final_answer = ""
    step_index = 1
    i = 0
    n = len(messages)

    while i < n:
        msg = messages[i] or {}
        role = (msg.get("role") or "").strip().lower()

        if role != "assistant":
            i += 1
            continue

        blocks = _as_blocks(msg.get("content"))
        thought = _text_from_blocks(blocks)
        tool_uses = [b for b in blocks if (b.get("type") or "") == "tool_use"]

        if tool_uses:
            results: dict[str, tuple[str, bool]] = {}
            j = i + 1
            while j < n:
                nxt = messages[j] or {}
                if (nxt.get("role") or "").strip().lower() != "user":
                    break
                nxt_blocks = _as_blocks(nxt.get("content"))
                has_tool_result = any(
                    (b.get("type") or "") == "tool_result" for b in nxt_blocks
                )
                if not has_tool_result:
                    break
                for b in nxt_blocks:
                    if (b.get("type") or "") != "tool_result":
                        continue
                    tid = str(b.get("tool_use_id") or "")
                    is_err = bool(b.get("is_error"))
                    results[tid] = (_tool_result_text(b), is_err)
                j += 1

            for k, tu in enumerate(tool_uses):
                tid = str(tu.get("id") or "")
                name = str(tu.get("name") or "")
                tool_input = tu.get("input")
                obs, is_err = results.get(tid, ("", False))
                if is_err:
                    if not obs:
                        obs = "tool_result is_error"
                    elif "error" not in obs.lower() and "异常" not in obs:
                        obs = f"[错误] {obs}"
                ev = StepEvent(
                    step_index=step_index,
                    thought=thought if k == 0 else "",
                    tool_name=name,
                    tool_input=tool_input if tool_input is not None else {},
                    observation=obs,
                    has_error=True if is_err else None,
                    error_message=obs[:200] if is_err else "",
                )
                events.append(ev)
                step_index += 1
            i = j
            continue

        if thought.strip():
            final_answer = thought
            events.append(
                StepEvent(
                    step_index=step_index,
                    thought=thought,
                )
            )
            step_index += 1
        i += 1

    return events, final_answer


def anthropic_messages_to_trajectory(
    messages: list[dict[str, Any]],
    *,
    session_id: Optional[str] = None,
    query: Optional[str] = None,
    model: str = "",
    final_answer: Optional[str] = None,
) -> dict[str, Any]:
    """Build a Format B trajectory dict from Anthropic-style messages."""
    events, inferred_final = anthropic_messages_to_step_events(messages)
    ctx = RunContext(
        session_id=session_id or f"anthropic_{uuid.uuid4().hex[:12]}",
        query=query if query is not None else _first_user_query(messages),
        model=model or "anthropic",
    )
    answer = final_answer if final_answer is not None else inferred_final
    return build_trajectory_dict(ctx, events, final_answer=answer)
