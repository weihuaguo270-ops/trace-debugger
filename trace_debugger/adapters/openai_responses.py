"""OpenAI Responses API items → Format B (no SDK).

Maps Chat-style ``function_call`` **and** broader Item types (computer / MCP /
web_search / file_search / shell / code_interpreter / image / custom / program)
into Format B steps. Binary / base64 payloads are **not** embedded — only
refs and short status text go into observations.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from ..harness import RunContext, StepEvent, build_trajectory_dict
from .openai_stream import (
    IncompleteStreamError,
    incomplete_mark_step,
    normalize_on_incomplete,
)
from .openai_messages import _content_text

# call item type → possible paired output type(s)
_CALL_OUTPUT_TYPES: dict[str, tuple[str, ...]] = {
    "function_call": ("function_call_output",),
    "computer_call": ("computer_call_output", "computer_tool_call_output"),
    "computer_tool_call": ("computer_tool_call_output", "computer_call_output"),
    "local_shell_call": ("local_shell_call_output",),
    "function_shell_call": ("function_shell_call_output",),
    "shell_call": ("shell_call_output",),
    "custom_tool_call": ("custom_tool_call_output",),
    "apply_patch_call": ("apply_patch_call_output",),
    "apply_patch_tool_call": ("apply_patch_tool_call_output",),
    "program": ("program_output",),
    "tool_search_call": ("tool_search_output", "tool_search_call_output"),
}

# Self-contained tool-like items (output/error often inline)
# Note: mcp_list_tools is soft-protocol — see protocol_mode, not hard tool_error by default
_INLINE_TOOL_TYPES = frozenset({
    "mcp_call",
    "file_search_call",
    "web_search_call",
    "web_search",
    "code_interpreter_call",
    "image_generation_call",
})

# Soft protocol: mappable, not an Agent task failure by default
_SOFT_PROTOCOL_TYPES = frozenset({
    "mcp_list_tools",
    "additional_tools",
    "compaction",
})

# Approval / control handshake (approve=false remains a real failure — Task 2)
_PROTOCOL_TYPES = frozenset({
    "mcp_approval_request",
    "mcp_approval_response",
})

# Pure output rows consumed via call_id index (not emitted alone)
_OUTPUT_ONLY_TYPES = frozenset({
    "function_call_output",
    "computer_call_output",
    "computer_tool_call_output",
    "local_shell_call_output",
    "function_shell_call_output",
    "shell_call_output",
    "custom_tool_call_output",
    "apply_patch_call_output",
    "apply_patch_tool_call_output",
    "program_output",
    "tool_search_output",
    "tool_search_call_output",
})


def _message_text(item: dict[str, Any]) -> str:
    content = item.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                btype = (block.get("type") or "").strip().lower()
                if btype in ("output_text", "input_text", "text"):
                    parts.append(str(block.get("text") or ""))
                elif btype in ("refusal",):
                    parts.append(str(block.get("refusal") or block.get("text") or ""))
                elif "text" in block and btype not in {
                    "input_image", "output_image", "image_url", "input_file", "file",
                }:
                    parts.append(str(block.get("text") or ""))
        return "".join(parts)
    return _content_text(content)


def _multimodal_refs(item: dict[str, Any]) -> list[str]:
    """Collect non-text media refs from message content (no binary)."""
    content = item.get("content")
    if not isinstance(content, list):
        return []
    refs: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = (block.get("type") or "").strip().lower()
        if btype in {"input_image", "output_image", "image_url"}:
            url = block.get("image_url") or block.get("url") or ""
            if isinstance(url, dict):
                url = url.get("url") or ""
            detail = block.get("detail") or ""
            refs.append(f"{btype}:{str(url)[:120]}{(' detail='+str(detail)) if detail else ''}")
        elif btype in {"input_file", "file"}:
            fid = block.get("file_id") or block.get("id") or block.get("filename") or ""
            refs.append(f"{btype}:{fid}")
    return refs


def _item_incomplete(item: dict[str, Any]) -> bool:
    status = (item.get("status") or "").strip().lower()
    return status in {"in_progress", "incomplete", "generating", "calling"}


def normalize_protocol_mode(protocol_mode: Optional[str] = None) -> str:
    """``ignore_fail`` (default) | ``audit`` | ``fail_on_error``."""
    mode = str(protocol_mode or "ignore_fail").strip().lower()
    if mode not in {"ignore_fail", "audit", "fail_on_error"}:
        raise ValueError(
            f"protocol_mode must be ignore_fail|audit|fail_on_error, got {protocol_mode!r}"
        )
    return mode


def _protocol_error_payload(item: dict[str, Any]) -> Any:
    if item.get("error") is not None:
        return item.get("error")
    if str(item.get("status") or "").lower() == "failed":
        return {"status": "failed"}
    return None


def _json_preview(value: Any, *, limit: int = 400) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        # Omit huge base64-looking blobs
        if len(value) > 200 and all(
            c.isalnum() or c in "+/=\n\r" for c in value[:80]
        ):
            return f"[omitted binary/base64-like payload len={len(value)}]"
        return value[:limit]
    try:
        text = json.dumps(value, ensure_ascii=False)
    except TypeError:
        text = str(value)
    if len(text) > limit:
        return text[:limit] + "…"
    return text


def _call_id(item: dict[str, Any]) -> str:
    return str(item.get("call_id") or item.get("id") or "")


def _tool_name(item: dict[str, Any], itype: str) -> str:
    name = item.get("name") or item.get("server_label") or ""
    if name:
        return str(name)
    # computer actions often nest under action.type
    action = item.get("action")
    if isinstance(action, dict) and action.get("type"):
        return f"{itype}.{action.get('type')}"
    return itype


def _tool_args(item: dict[str, Any], itype: str) -> Any:
    if item.get("arguments") is not None:
        return item.get("arguments")
    if itype in {"local_shell_call", "function_shell_call", "shell_call"}:
        action = item.get("action")
        if isinstance(action, dict):
            return {
                "command": action.get("command"),
                "working_directory": action.get("working_directory"),
                "timeout_ms": action.get("timeout_ms"),
            }
    if itype in {"computer_call", "computer_tool_call"}:
        return item.get("action") or {
            k: item.get(k)
            for k in ("pending_safety_checks", "status")
            if item.get(k) is not None
        }
    if itype == "program":
        return {"code_preview": _json_preview(item.get("code"), limit=200)}
    if itype == "image_generation_call":
        return {
            "action": item.get("action"),
            "size": item.get("size"),
            "output_format": item.get("output_format"),
            "revised_prompt": item.get("revised_prompt"),
        }
    if itype == "mcp_list_tools":
        tools = item.get("tools") or []
        names = [
            t.get("name") for t in tools if isinstance(t, dict) and t.get("name")
        ]
        return {"server_label": item.get("server_label"), "tools": names[:40]}
    if itype == "mcp_approval_request":
        return {
            "name": item.get("name"),
            "server_label": item.get("server_label"),
            "arguments": item.get("arguments"),
        }
    if itype == "mcp_approval_response":
        return {
            "approval_request_id": item.get("approval_request_id"),
            "approve": item.get("approve"),
            "reason": item.get("reason"),
        }
    if itype == "additional_tools":
        return {"role": item.get("role"), "tool_count": len(item.get("tools") or [])}
    queries = item.get("queries")
    if queries is not None:
        return {"queries": queries}
    return {k: item[k] for k in ("id", "status") if k in item}


def _inline_observation(item: dict[str, Any], itype: str) -> str:
    if itype == "image_generation_call":
        status = item.get("status") or ""
        fmt = item.get("output_format") or ""
        result = item.get("result")
        if result:
            return (
                f"[image_generation_call result omitted; status={status}; "
                f"format={fmt}; len={len(str(result))}]"
            )
        return f"[image_generation_call status={status}]"
    if item.get("error") is not None:
        err = item.get("error")
        return f"[错误] {_json_preview(err)}"
    if item.get("output") is not None:
        return _json_preview(item.get("output"))
    if itype == "mcp_list_tools" and item.get("error"):
        return f"[错误] {item.get('error')}"
    if itype in {"file_search_call", "web_search_call", "web_search", "code_interpreter_call"}:
        # results / outputs often nested
        for key in ("results", "output", "outputs", "actions"):
            if item.get(key) is not None:
                return _json_preview(item.get(key))
        return f"[{itype} status={item.get('status') or 'unknown'}]"
    return ""


def _index_outputs_by_call_id(
    items: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        itype = (item.get("type") or "").strip().lower()
        if itype not in _OUTPUT_ONLY_TYPES and not itype.endswith("_output"):
            continue
        cid = _call_id(item)
        if cid:
            indexed[cid] = item
    return indexed


def _observation_from_output(out_item: dict[str, Any]) -> str:
    if out_item.get("output") is not None:
        return _json_preview(out_item.get("output"))
    if out_item.get("result") is not None:
        return _json_preview(out_item.get("result"))
    if out_item.get("error") is not None:
        return _format_structured_error_payload(out_item.get("error"))
    return _json_preview(
        {k: out_item[k] for k in ("status", "id", "type") if k in out_item}
    )


def _format_structured_error_payload(payload: Any) -> str:
    """Render structured error without requiring the English word 'error' in text."""
    if isinstance(payload, dict):
        code = payload.get("code") or payload.get("type") or payload.get("name") or ""
        detail = (
            payload.get("message")
            or payload.get("detail")
            or payload.get("reason")
            or ""
        )
        parts = []
        if code:
            parts.append(f"code={code}")
        if detail:
            parts.append(f"detail={detail}")
        if parts:
            return "[错误] " + " ".join(str(p) for p in parts)
        return "[错误] " + _json_preview(payload)
    if payload is None:
        return "[错误] structured_failure"
    return f"[错误] {payload}"


def _parse_maybe_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or text[0] not in "{[":
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def _extract_exit_code(payload: Any) -> Optional[int]:
    data = _parse_maybe_json(payload)
    if not isinstance(data, dict):
        return None
    for key in ("exit_code", "exitCode", "returncode", "return_code", "status_code"):
        if key not in data or data[key] is None:
            continue
        try:
            return int(data[key])
        except (TypeError, ValueError):
            continue
    return None


def _safety_check_failed(item: Optional[dict[str, Any]]) -> Optional[str]:
    if not item:
        return None
    for key in (
        "pending_safety_checks",
        "acknowledged_safety_checks",
        "safety_checks",
    ):
        checks = item.get(key)
        if not isinstance(checks, list):
            continue
        for check in checks:
            if not isinstance(check, dict):
                continue
            status = str(check.get("status") or check.get("state") or "").lower()
            if status in {"failed", "rejected", "unacknowledged", "denied"}:
                code = check.get("code") or check.get("id") or status
                return f"safety_check:{code}"
            # acknowledged=false explicitly
            if check.get("acknowledged") is False:
                code = check.get("code") or check.get("id") or "unacked"
                return f"safety_check_unacknowledged:{code}"
    return None


def _nested_output_error(out_item: Optional[dict[str, Any]]) -> Any:
    """Return structured error object from output.error / top-level error."""
    if not out_item:
        return None
    if out_item.get("error") is not None:
        return out_item.get("error")
    raw = out_item.get("output")
    data = _parse_maybe_json(raw)
    if isinstance(data, dict) and data.get("error") is not None:
        return data.get("error")
    return None


def detect_computer_shell_failure(
    call_item: dict[str, Any],
    out_item: Optional[dict[str, Any]],
    itype: str,
) -> Optional[tuple[str, str]]:
    """Structured computer/shell failure → (rule_id, observation_with_[错误]).

    Does not rely on the English substring ``error`` appearing in free text.
    """
    name = itype.lower()
    is_computer = "computer" in name
    is_shell = "shell" in name

    # status on call / output
    for src, label in (
        (call_item, "call"),
        (out_item or {}, "output"),
    ):
        status = str(src.get("status") or "").lower()
        if status == "failed" and src:
            rule = (
                "responses.computer.failed"
                if is_computer
                else "responses.shell.failed"
                if is_shell
                else "responses.tool.failed"
            )
            return rule, f"[错误] {label}_status={status}"

    # safety checks (computer)
    for src in (call_item, out_item):
        safety = _safety_check_failed(src)
        if safety:
            return "responses.computer.failed", f"[错误] {safety}"

    # structured output.error (key present — message may be Chinese only)
    nested_err = _nested_output_error(out_item)
    if nested_err is not None:
        rule = (
            "responses.computer.failed"
            if is_computer
            else "responses.shell.failed"
            if is_shell
            else "responses.tool.failed"
        )
        return rule, _format_structured_error_payload(nested_err)

    # shell nonzero exit
    if out_item is not None:
        exit_code = _extract_exit_code(out_item.get("output"))
        if exit_code is None:
            exit_code = _extract_exit_code(out_item)
        if exit_code is not None and exit_code != 0:
            return (
                "responses.shell.nonzero_exit",
                f"[错误] exit_code={exit_code}",
            )

    return None


def _apply_failure_to_observation(
    obs: str,
    failure: Optional[tuple[str, str]],
) -> tuple[str, bool, str, str]:
    """Return observation, has_error, error_message, rule_id."""
    if not failure:
        return obs, False, "", ""
    rule_id, fail_obs = failure
    # Prefer structured fail_obs only — raw output may contain an "error" JSON
    # key; acceptance requires tool_error without English "error" in free text.
    combined = fail_obs or obs
    if not combined.startswith("[错误]"):
        combined = f"[错误] {combined}"
    if rule_id and rule_id not in combined:
        combined = f"{combined} [{rule_id}]"
    return combined, True, combined[:200], rule_id


def openai_responses_items_to_step_events(
    items: list[dict[str, Any]],
    *,
    on_incomplete: str = "reject",
    reject_incomplete: Optional[bool] = None,
    include_reasoning: bool = True,
    include_protocol: bool = True,
    protocol_mode: str = "ignore_fail",
) -> tuple[list[StepEvent], str, str, list[str], bool, list[dict[str, Any]]]:
    """Map a flat Responses Item transcript to steps.

    Returns
    ``(events, final_answer, query, skipped_types, incomplete, protocol_events)``.

    ``protocol_mode`` (soft protocol: list_tools / compaction / additional_tools):

    - ``ignore_fail`` (default): map; errors do **not** become Agent ``tool_error``
    - ``audit``: map + ``meta.protocol_events``; still no distribution failure
    - ``fail_on_error``: ``mcp_list_tools`` with error → ``tool_error``;
      compaction / additional_tools stay audit-only

    Protocol failure ≠ Agent task failure — see INTEGRATIONS.md.
    """
    mode = normalize_on_incomplete(
        on_incomplete, reject_incomplete=reject_incomplete,
    )
    pmode = normalize_protocol_mode(protocol_mode)
    events: list[StepEvent] = []
    final_answer = ""
    query = ""
    skipped: list[str] = []
    protocol_events: list[dict[str, Any]] = []
    incomplete = False
    step_index = 1
    outputs = _index_outputs_by_call_id(items)
    pending_reason = ""

    for i, raw in enumerate(items):
        item = raw or {}
        if not isinstance(item, dict):
            continue

        item_incomplete = _item_incomplete(item)
        if item_incomplete:
            if mode == "reject":
                raise IncompleteStreamError(
                    f"Responses item incomplete/in_progress at index {i}: "
                    f"type={item.get('type')!r} status={item.get('status')!r}"
                )
            incomplete = True
            status = str(item.get("status") or "incomplete")
            itype_early = (item.get("type") or "item").strip().lower()
            events.append(
                incomplete_mark_step(
                    step_index=step_index,
                    detail=f"{itype_early} status={status}",
                )
            )
            step_index += 1
            # Still fall through to map residual content when useful; skip
            # pure in-progress calls with no usable payload beyond the mark.
            if itype_early in _OUTPUT_ONLY_TYPES or itype_early.endswith("_output"):
                continue
            # For incomplete calls/messages, the mark step is enough
            continue

        itype = (item.get("type") or "").strip().lower()
        if not itype and item.get("role"):
            itype = "message"

        if itype in _OUTPUT_ONLY_TYPES or itype.endswith("_output"):
            # Consumed via call_id index
            continue

        if itype == "reasoning":
            if include_reasoning:
                summary = item.get("summary") or item.get("content") or item.get("text")
                text = _json_preview(summary, limit=300)
                if text:
                    pending_reason = text
                    events.append(
                        StepEvent(
                            step_index=step_index,
                            thought=f"[reasoning] {text}",
                        )
                    )
                    step_index += 1
            else:
                skipped.append(itype)
            continue

        if itype == "message":
            role = (item.get("role") or "").strip().lower()
            text = _message_text(item)
            refs = _multimodal_refs(item)
            if role == "user" and text.strip() and not query:
                query = text
            if role == "user" and refs and not text.strip():
                # user uploaded media only
                query = query or f"[multimodal user: {', '.join(refs[:3])}]"
            if role == "assistant":
                thought = text
                if refs:
                    thought = (thought + "\n" if thought else "") + "; ".join(refs)
                if pending_reason and not thought.startswith("[reasoning]"):
                    thought = f"{pending_reason}\n{thought}".strip()
                    pending_reason = ""
                if thought.strip():
                    final_answer = text or final_answer
                    events.append(
                        StepEvent(step_index=step_index, thought=thought)
                    )
                    step_index += 1
            continue

        # Paired call → output (explicit registry only — unknown *_call goes to unmapped)
        if itype in _CALL_OUTPUT_TYPES:
            cid = _call_id(item)
            out_item = outputs.get(cid) if cid else None
            obs = _observation_from_output(out_item) if out_item else ""
            thought = pending_reason
            pending_reason = ""
            failure = None
            if "computer" in itype or "shell" in itype:
                failure = detect_computer_shell_failure(item, out_item, itype)
            obs, has_err, err_msg, _rule = _apply_failure_to_observation(obs, failure)
            events.append(
                StepEvent(
                    step_index=step_index,
                    thought=thought,
                    tool_name=_tool_name(item, itype),
                    tool_input=_tool_args(item, itype),
                    observation=obs,
                    has_error=True if has_err else None,
                    error_message=err_msg,
                )
            )
            step_index += 1
            continue

        if itype in _INLINE_TOOL_TYPES:
            obs = _inline_observation(item, itype)
            has_err = item.get("error") is not None or (
                str(item.get("status") or "").lower() == "failed"
            )
            if has_err and obs and "错误" not in obs and "error" not in obs.lower():
                obs = f"[错误] {obs}"
            events.append(
                StepEvent(
                    step_index=step_index,
                    thought=pending_reason,
                    tool_name=_tool_name(item, itype),
                    tool_input=_tool_args(item, itype),
                    observation=obs,
                    has_error=True if has_err else None,
                    error_message=obs[:200] if has_err else "",
                )
            )
            pending_reason = ""
            step_index += 1
            continue

        if itype in _SOFT_PROTOCOL_TYPES:
            if not include_protocol:
                skipped.append(itype)
                continue
            err_payload = _protocol_error_payload(item)
            # Never auto-prefix [错误] here — protocol_mode decides escalation
            if itype == "mcp_list_tools":
                tools = item.get("tools") or []
                names = [
                    t.get("name") for t in tools
                    if isinstance(t, dict) and t.get("name")
                ]
                obs = _json_preview({
                    "server_label": item.get("server_label"),
                    "tools": names[:40],
                    **({"status": item["status"]} if "status" in item else {}),
                })
            else:
                base = _tool_args(item, itype)
                if isinstance(base, dict):
                    payload = dict(base)
                else:
                    payload = {"value": base} if base else {}
                for k in ("status", "id"):
                    if k in item:
                        payload[k] = item[k]
                obs = _json_preview(payload) or f"[{itype}]"
            has_err = None
            err_msg = ""
            if err_payload is not None:
                pe: dict[str, Any] = {
                    "type": itype,
                    "step": step_index,
                    "rule_id": f"responses.protocol.{itype}",
                    "signal": _json_preview(err_payload, limit=200),
                    "mode": pmode,
                }
                if pmode == "fail_on_error" and itype == "mcp_list_tools":
                    obs = (
                        "[错误] mcp_list_tools failed "
                        "[responses.protocol.mcp_list_tools]"
                    )
                    has_err = True
                    err_msg = obs[:200]
                    pe["escalated"] = True
                elif pmode in {"audit", "fail_on_error"}:
                    # compaction / additional_tools (and audit mode): meta only
                    obs = (
                        f"[protocol_audit] {itype}: "
                        f"{_json_preview(err_payload, limit=160)}"
                    )
                    pe["audit"] = True
                else:
                    # ignore_fail: keep mapped obs; avoid English "error" so
                    # reader heuristics do not escalate to tool_error
                    detail = _json_preview(err_payload, limit=160)
                    obs = (obs + f" | protocol_issue={detail}") if obs else detail
                    pe["ignored"] = True
                protocol_events.append(pe)
            elif pmode == "audit":
                protocol_events.append({
                    "type": itype,
                    "step": step_index,
                    "rule_id": f"responses.protocol.{itype}",
                    "signal": "ok",
                    "mode": pmode,
                    "audit": True,
                })
            events.append(
                StepEvent(
                    step_index=step_index,
                    thought=pending_reason or f"[{itype}]",
                    tool_name=(
                        _tool_name(item, itype)
                        if itype == "mcp_list_tools"
                        else itype
                    ),
                    tool_input=_tool_args(item, itype),
                    observation=obs or f"[{itype}]",
                    has_error=True if has_err else None,
                    error_message=err_msg,
                )
            )
            pending_reason = ""
            step_index += 1
            continue

        if itype in _PROTOCOL_TYPES:
            if not include_protocol:
                skipped.append(itype)
                continue
            obs = _json_preview(
                {k: item.get(k) for k in ("status", "error", "approve") if k in item}
            )
            has_err = None
            err_msg = ""
            if itype == "mcp_approval_response" and item.get("approve") is False:
                obs = (
                    "[错误] mcp approval denied "
                    "[responses.mcp.approval_denied]"
                )
                has_err = True
                err_msg = obs[:200]
            events.append(
                StepEvent(
                    step_index=step_index,
                    thought=f"[{itype}]",
                    tool_name=itype,
                    tool_input=_tool_args(item, itype),
                    observation=obs,
                    has_error=True if has_err else None,
                    error_message=err_msg,
                )
            )
            step_index += 1
            continue

        # Unknown Item: still map as opaque tool step so scan does not silently drop it
        skipped.append(itype or "unknown")
        events.append(
            StepEvent(
                step_index=step_index,
                thought=f"[unmapped_responses_item:{itype or 'unknown'}]",
                tool_name=itype or "unknown_responses_item",
                tool_input=_json_preview(item, limit=300),
                observation="",
            )
        )
        step_index += 1

    return events, final_answer, query, skipped, incomplete, protocol_events


def openai_responses_to_trajectory(
    response: dict[str, Any] | list[dict[str, Any]],
    *,
    input_items: Optional[list[dict[str, Any]]] = None,
    session_id: Optional[str] = None,
    query: Optional[str] = None,
    model: str = "",
    final_answer: Optional[str] = None,
    on_incomplete: str = "reject",
    reject_incomplete: Optional[bool] = None,
    include_reasoning: bool = True,
    include_protocol: bool = True,
    protocol_mode: str = "ignore_fail",
) -> dict[str, Any]:
    """Build Format B from a Responses ``output`` list or full response object.

    ``on_incomplete``: ``reject`` (default) or ``mark`` (dump + tag; sets
    ``meta.incomplete=true``). Unrelated to CLI ``--fail-on``.

    ``protocol_mode``: soft protocol policy (list_tools / compaction / …);
    protocol failure ≠ Agent task failure by default.
    """
    if isinstance(response, list):
        output_items = response
        resp_meta: dict[str, Any] = {}
    else:
        resp_meta = response or {}
        output_items = list(resp_meta.get("output") or [])

    items: list[dict[str, Any]] = []
    if input_items:
        items.extend(input_items)
    items.extend(output_items)

    events, inferred_final, inferred_query, skipped, incomplete, protocol_events = (
        openai_responses_items_to_step_events(
            items,
            on_incomplete=on_incomplete,
            reject_incomplete=reject_incomplete,
            include_reasoning=include_reasoning,
            include_protocol=include_protocol,
            protocol_mode=protocol_mode,
        )
    )
    sid = session_id or str(resp_meta.get("id") or "") or f"responses_{uuid.uuid4().hex[:12]}"
    ctx = RunContext(
        session_id=sid,
        query=query if query is not None else inferred_query,
        model=model or str(resp_meta.get("model") or "openai-responses"),
    )
    answer = final_answer if final_answer is not None else inferred_final
    traj = build_trajectory_dict(ctx, events, final_answer=answer)
    meta = dict(traj.get("meta") or {})
    meta.update({
        "responses_adapter": "openai_responses",
        "skipped_or_unmapped_types": sorted(set(skipped)),
        "protocol_mode": normalize_protocol_mode(protocol_mode),
    })
    if protocol_events:
        meta["protocol_events"] = protocol_events
    if incomplete:
        meta["incomplete"] = True
    traj["meta"] = meta
    return traj
