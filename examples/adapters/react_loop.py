"""ReAct-loop 风格适配器 — 对照 graph_style，展示第二种框架映射。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from trace_debugger.harness import StepEvent


@dataclass
class ReActStepRaw:
    """典型 ReAct 循环内部 step（与 Format B 较接近）。"""

    index: int
    reasoning: str
    tool: Optional[str] = None
    input: Any = None
    output: str = ""
    latency_s: float = 0.0


def react_step_to_event(raw: ReActStepRaw) -> StepEvent:
    return StepEvent(
        step_index=raw.index,
        thought=raw.reasoning,
        tool_name=raw.tool or "",
        tool_input=raw.input,
        observation=raw.output,
        duration=raw.latency_s,
    )
