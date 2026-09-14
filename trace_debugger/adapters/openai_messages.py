"""OpenAI Chat Completions / Responses-style messages → Format B.

Accepts plain dict messages (no ``openai`` package). Typical shape::

    {"role": "user"|"assistant"|"tool"|"system", "content": "...",
     "tool_calls": [{"id": "...", "type": "function",
                     "function": {"name": "...", "arguments": "{...}"}}],
     "tool_call_id": "..."}  # on role=tool
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from ..harness import RunContext, StepEvent, build_trajectory_dict


def _content_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text") or ""))
                elif "text" in block:
                    parts.append(str(block.get("text") or ""))
        return "".join(parts)
    return str(content)


def _first_user_query(messages: list[dict[str, Any]]) -> str:
    for msg in messages:
        if (msg.get("role") or "") == "user":
            text = _content_text(msg.get("content"))
            if text.strip():
                return text
    return ""


def openai_messages_to_step_events(
    messages: list[dict[str, Any]],
) -> tuple[list[StepEvent], str]:
    """Map OpenAI-style messages to StepEvents + inferred final_answer.

    - Each ``tool_calls`` entry becomes its own step (aligned via ``tool_call_id``).
    - Assistant text without tool_calls updates the final-answer candidate
      (also emitted as a thought-only step when non-empty).
    """
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

        thought = _content_text(msg.get("content"))
        tool_calls = msg.get("tool_calls") or []
        if not isinstance(tool_calls, list):
            tool_calls = []

        if tool_calls:
            results: dict[str, str] = {}
            j = i + 1
            while j < n:
                nxt = messages[j] or {}
                if (nxt.get("role") or "").strip().lower() != "tool":
                    break
                tcid = str(nxt.get("tool_call_id") or "")
                results[tcid] = _content_text(nxt.get("content"))
                j += 1

            for k, tc in enumerate(tool_calls):
                if not isinstance(tc, dict):
                    continue
                fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
                name = str((fn or {}).get("name") or tc.get("name") or "")
                args = (fn or {}).get("arguments", tc.get("arguments", ""))
                tcid = str(tc.get("id") or "")
                obs = results.get(tcid, "")
                events.append(
                    StepEvent(
                        step_index=step_index,
                        thought=thought if k == 0 else "",
                        tool_name=name,
                        tool_input=args if args is not None else "",
                        observation=obs,
                    )
                )
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


def openai_messages_to_trajectory(
    messages: list[dict[str, Any]],
    *,
    session_id: Optional[str] = None,
    query: Optional[str] = None,
    model: str = "",
    final_answer: Optional[str] = None,
) -> dict[str, Any]:
    """Build a Format B trajectory dict from OpenAI-style messages."""
    events, inferred_final = openai_messages_to_step_events(messages)
    ctx = RunContext(
        session_id=session_id or f"openai_{uuid.uuid4().hex[:12]}",
        query=query if query is not None else _first_user_query(messages),
        model=model or "openai",
    )
    answer = final_answer if final_answer is not None else inferred_final
    return build_trajectory_dict(ctx, events, final_answer=answer)
