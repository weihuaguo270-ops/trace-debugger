"""Deterministic tool-contract checks (arg presence / JSON shape).

Not a substitute for TraceGate-style runtime policy — only offline heuristics
that map to tool_error with evidence.rule_id = tool_contract.*.
"""
from __future__ import annotations

import json
from typing import Any, Optional

# Minimal built-in contracts: required argument keys when args parse as JSON object.
DEFAULT_TOOL_CONTRACTS: dict[str, dict[str, Any]] = {
    "web_search": {"required_args": ["query"]},
    "search": {"required_args": ["query"]},
    "bing_search": {"required_args": ["query"]},
    "google_search": {"required_args": ["query"]},
    "http_get": {"required_args": ["url"]},
    "fetch_url": {"required_args": ["url"]},
    "read_file": {"required_args": ["path"]},
    "write_file": {"required_args": ["path"]},
}


def merge_contracts(
    extra: Optional[dict[str, Any]] = None,
    *,
    use_defaults: bool = True,
) -> dict[str, dict[str, Any]]:
    """Merge caller contracts over defaults."""
    out: dict[str, dict[str, Any]] = dict(DEFAULT_TOOL_CONTRACTS) if use_defaults else {}
    if extra:
        for name, spec in extra.items():
            base = dict(out.get(name) or {})
            base.update(spec or {})
            out[name] = base
    return out


def parse_action_args(raw: str) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """Parse action_args string as JSON object; return (obj, error)."""
    text = (raw or "").strip()
    if not text:
        return {}, None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"action_args 不是合法 JSON: {exc}"
    if data is None:
        return {}, None
    if not isinstance(data, dict):
        return None, "action_args JSON 必须是 object"
    return data, None


def check_tool_contract(
    action_name: str,
    action_args: str,
    contracts: dict[str, dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Return violation dict or None if OK / no contract for tool."""
    name = (action_name or "").strip()
    if not name or name not in contracts:
        return None
    spec = contracts[name] or {}
    required = list(spec.get("required_args") or [])
    if not required:
        return None

    parsed, err = parse_action_args(action_args)
    if err:
        return {
            "rule_id": "tool_contract.invalid_json",
            "signal": err,
            "excerpt": (action_args or "")[:120],
            "missing": required,
        }

    missing = [k for k in required if k not in parsed or parsed.get(k) in (None, "")]
    if missing:
        return {
            "rule_id": "tool_contract.missing_args",
            "signal": f"{name} 缺少必填参数: {', '.join(missing)}",
            "excerpt": (action_args or "")[:120],
            "missing": missing,
        }
    return None
