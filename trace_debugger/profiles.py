"""Task-type analyzer profiles — QA / code / creative knobs (no LLM Judge)."""
from __future__ import annotations

from typing import Any, Optional

from .analyzer import Analyzer

# Profile → Analyzer kwargs. Creative/code turn off token-overlap offtrack
# (high false-positive rate on paraphrase / generated code).
PROFILES: dict[str, dict[str, Any]] = {
    "default": {},
    "qa": {
        "enable_offtrack": True,
        "offtrack_overlap": 0.15,
        # Structural search weak signals (not semantic quality)
        "search_min_results": 1,
        "search_require_url": True,
    },
    "code": {
        "enable_offtrack": False,
        "final_answer_markers": ("FINAL ANSWER", "```"),
    },
    "creative": {
        "enable_offtrack": False,
    },
}

PROFILE_NAMES = tuple(PROFILES.keys())


def resolve_analyzer(
    task_type: Optional[str] = None,
    *,
    enable_tool_contracts: bool = False,
    tool_contracts: Optional[dict[str, Any]] = None,
    overrides: Optional[dict[str, Any]] = None,
) -> Analyzer:
    """Build Analyzer from named profile + optional knobs."""
    name = (task_type or "default").strip().lower() or "default"
    if name not in PROFILES:
        known = ", ".join(PROFILE_NAMES)
        raise ValueError(f"unknown task_type {task_type!r}; expected one of: {known}")
    kwargs = dict(PROFILES[name])
    if overrides:
        kwargs.update(overrides)
    kwargs["enable_tool_contracts"] = enable_tool_contracts
    if tool_contracts is not None:
        kwargs["tool_contracts"] = tool_contracts
    kwargs["task_type"] = name
    return Analyzer(**kwargs)
