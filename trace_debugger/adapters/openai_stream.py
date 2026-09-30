"""Coalesce OpenAI Chat Completions streaming chunks → complete messages.

Default: half-finished streams are **rejected** (``on_incomplete="reject"``).
For CI/debug dump-and-tag, pass ``on_incomplete="mark"`` then export Format B
with ``meta.incomplete=true`` and an ``incomplete_stream`` failure step.

``--fail-on`` (scan gate) is unrelated — it only applies after ``--compare``.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from ..harness import StepEvent

INCOMPLETE_RULE_ID = "responses.incomplete"
INCOMPLETE_OBS = f"[错误] incomplete stream [{INCOMPLETE_RULE_ID}]"
_INCOMPLETE_FLAG = "_tdebug_incomplete"


class IncompleteStreamError(ValueError):
    """Raised when stream chunks are not a finished assistant turn."""


def normalize_on_incomplete(
    on_incomplete: Optional[str] = None,
    *,
    reject_incomplete: Optional[bool] = None,
    require_finished: Optional[bool] = None,
) -> str:
    """Resolve ``reject`` | ``mark`` from new or legacy kwargs.

    - Default / True → ``reject``
    - ``on_incomplete="mark"`` or legacy False → ``mark``
    """
    if on_incomplete is not None:
        mode = str(on_incomplete).strip().lower()
        if mode not in {"reject", "mark"}:
            raise ValueError(
                f"on_incomplete must be 'reject' or 'mark', got {on_incomplete!r}"
            )
        return mode
    if reject_incomplete is False or require_finished is False:
        return "mark"
    return "reject"


def incomplete_mark_step(*, step_index: int, detail: str = "") -> StepEvent:
    """Format B failure step for marked incomplete stream / Responses item."""
    obs = INCOMPLETE_OBS
    if detail and detail not in obs:
        obs = f"[错误] incomplete stream: {detail} [{INCOMPLETE_RULE_ID}]"
    return StepEvent(
        step_index=step_index,
        thought="[incomplete_stream]",
        tool_name="incomplete_stream",
        tool_input={"status": "incomplete"},
        observation=obs,
        has_error=True,
        error_message=obs[:200],
    )


def apply_incomplete_meta(traj: dict[str, Any], *, reason: str = "") -> dict[str, Any]:
    """Set ``meta.incomplete=true`` and append a marked failure step if missing."""
    meta = dict(traj.get("meta") or {})
    meta["incomplete"] = True
    if reason:
        meta["incomplete_reason"] = reason
    traj["meta"] = meta
    steps = traj.setdefault("steps", [])
    already = any(
        (s.get("action") or {}).get("name") == "incomplete_stream"
        or INCOMPLETE_RULE_ID in str(s.get("observation") or "")
        for s in steps
        if isinstance(s, dict)
    )
    if not already:
        next_i = int(steps[-1]["step"]) + 1 if steps else 1
        ev = incomplete_mark_step(step_index=next_i, detail=reason)
        steps.append({
            "step": ev.step_index,
            "thought": ev.thought,
            "action": {"name": ev.tool_name, "arguments": ev.tool_args_str()},
            "observation": ev.observation,
            "duration_seconds": 0.0,
            "tokens_estimated": 0,
        })
    return traj


def _merge_tool_call_delta(
    acc: dict[int, dict[str, Any]],
    deltas: list[dict[str, Any]],
) -> None:
    for d in deltas:
        if not isinstance(d, dict):
            continue
        idx = int(d.get("index", 0))
        if idx not in acc:
            acc[idx] = {
                "id": "",
                "type": "function",
                "function": {"name": "", "arguments": ""},
            }
        slot: dict[str, Any] = acc[idx]
        if d.get("id"):
            slot["id"] = str(d["id"])
        if d.get("type"):
            slot["type"] = str(d["type"])
        raw_fn = d.get("function")
        fn: dict[str, Any] = raw_fn if isinstance(raw_fn, dict) else {}
        raw_slot_fn = slot.get("function")
        slot_fn: dict[str, Any] = raw_slot_fn if isinstance(raw_slot_fn, dict) else {}
        slot["function"] = slot_fn
        if fn.get("name"):
            slot_fn["name"] = str(fn["name"])
        if fn.get("arguments"):
            slot_fn["arguments"] = (
                str(slot_fn.get("arguments") or "") + str(fn["arguments"])
            )


def coalesce_chat_completion_chunks(
    chunks: list[dict[str, Any]],
    *,
    on_incomplete: str = "reject",
    require_finished: Optional[bool] = None,
) -> dict[str, Any]:
    """Merge ``chat.completion.chunk`` dicts into one assistant message.

    Returns a Chat Completions-style message::

        {"role": "assistant", "content": "...", "tool_calls": [...]?}

    ``on_incomplete``:

    - ``reject`` (default): raise ``IncompleteStreamError`` on half-finished streams
    - ``mark``: return best-effort message and set ``_tdebug_incomplete=True``
      (use ``chat_stream_to_trajectory`` / ``apply_incomplete_meta`` for Format B)

    Legacy ``require_finished=False`` maps to ``mark``.
    """
    mode = normalize_on_incomplete(
        on_incomplete, require_finished=require_finished,
    )
    content_parts: list[str] = []
    tool_acc: dict[int, dict[str, Any]] = {}
    finish_reason: Optional[str] = None
    role = "assistant"
    incomplete = False

    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        # Allow either raw chunk or {"choices":[...]} / single choice
        choices = chunk.get("choices")
        if isinstance(choices, list) and choices:
            choice = choices[0] if isinstance(choices[0], dict) else {}
        else:
            choice = chunk
        if choice.get("finish_reason"):
            finish_reason = str(choice["finish_reason"])
        raw_delta = choice.get("delta")
        delta: dict[str, Any] = raw_delta if isinstance(raw_delta, dict) else {}
        if not delta and "content" in choice and "role" in choice:
            # Already a full message slipped into the stream list
            return {
                "role": choice.get("role") or "assistant",
                "content": choice.get("content"),
                **(
                    {"tool_calls": choice["tool_calls"]}
                    if choice.get("tool_calls")
                    else {}
                ),
            }
        if delta.get("role"):
            role = str(delta["role"])
        if delta.get("content"):
            content_parts.append(str(delta["content"]))
        tcs = delta.get("tool_calls")
        if isinstance(tcs, list) and tcs:
            _merge_tool_call_delta(tool_acc, tcs)

    if not finish_reason:
        if mode == "reject":
            raise IncompleteStreamError(
                "stream has no finish_reason; refuse half-finished assistant turn"
            )
        incomplete = True

    msg: dict[str, Any] = {
        "role": role or "assistant",
        "content": "".join(content_parts) if content_parts else None,
    }
    if tool_acc:
        msg["tool_calls"] = [tool_acc[i] for i in sorted(tool_acc)]
        for tc in msg["tool_calls"]:
            fn = tc.get("function") or {}
            if not fn.get("name"):
                if mode == "reject":
                    raise IncompleteStreamError(
                        "stream finished but tool_call name is empty (incomplete deltas)"
                    )
                incomplete = True
                fn["name"] = fn.get("name") or "(incomplete)"
                tc["function"] = fn

    if not (msg.get("content") or msg.get("tool_calls")):
        if mode == "reject":
            raise IncompleteStreamError("coalesced assistant message is empty")
        incomplete = True
        msg["content"] = msg.get("content") or ""

    if incomplete:
        msg[_INCOMPLETE_FLAG] = True
    return msg


def messages_from_chat_stream_ex(
    prior_messages: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    *,
    tool_results: Optional[list[dict[str, Any]]] = None,
    on_incomplete: str = "reject",
    require_finished: Optional[bool] = None,
) -> tuple[list[dict[str, Any]], bool]:
    """Like ``messages_from_chat_stream`` but also returns ``incomplete`` flag."""
    assistant = coalesce_chat_completion_chunks(
        chunks,
        on_incomplete=on_incomplete,
        require_finished=require_finished,
    )
    incomplete = bool(assistant.pop(_INCOMPLETE_FLAG, False))
    out = list(prior_messages) + [assistant]
    if tool_results:
        out.extend(tool_results)
    return out, incomplete


def messages_from_chat_stream(
    prior_messages: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    *,
    tool_results: Optional[list[dict[str, Any]]] = None,
    on_incomplete: str = "reject",
    require_finished: Optional[bool] = None,
) -> list[dict[str, Any]]:
    """Build a complete messages list: prior + coalesced assistant (+ optional tool rows)."""
    messages, _incomplete = messages_from_chat_stream_ex(
        prior_messages,
        chunks,
        tool_results=tool_results,
        on_incomplete=on_incomplete,
        require_finished=require_finished,
    )
    return messages


def chat_stream_to_trajectory(
    prior_messages: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    *,
    tool_results: Optional[list[dict[str, Any]]] = None,
    on_incomplete: str = "reject",
    session_id: Optional[str] = None,
    query: Optional[str] = None,
    model: str = "openai-stream",
) -> dict[str, Any]:
    """Coalesce stream → Format B. With ``on_incomplete='mark'``, tags incomplete."""
    from .openai_messages import openai_messages_to_trajectory

    messages, incomplete = messages_from_chat_stream_ex(
        prior_messages,
        chunks,
        tool_results=tool_results,
        on_incomplete=on_incomplete,
    )
    traj = openai_messages_to_trajectory(
        messages,
        session_id=session_id or f"stream_{uuid.uuid4().hex[:12]}",
        query=query,
        model=model,
    )
    meta = dict(traj.get("meta") or {})
    meta["stream_adapter"] = "openai_stream"
    traj["meta"] = meta
    if incomplete:
        apply_incomplete_meta(
            traj, reason="no finish_reason or incomplete tool deltas",
        )
    return traj
