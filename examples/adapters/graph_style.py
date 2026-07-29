"""Graph-style Agent 适配器 — 模拟节点/状态机类运行时（非 ReAct 原生字段）

内部格式与 Format B 不同，通过 adapter 映射为 StepEvent。
可作为 LangGraph / 状态机 Agent 的集成样板。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from trace_debugger.harness import StepEvent


@dataclass
class GraphNodeRecord:
    """Graph 运行时单节点记录（框架内部形态）。"""

    run_id: str
    node_name: str
    turn: int
    planner_text: str
    tool: Optional[str] = None
    tool_payload: Optional[dict[str, Any]] = None
    tool_result: str = ""
    elapsed_ms: int = 0


def graph_node_to_step_event(record: GraphNodeRecord) -> StepEvent:
    """GraphNodeRecord → trace-debugger StepEvent。"""
    thought = f"[{record.node_name}] {record.planner_text}"
    if record.tool:
        return StepEvent(
            step_index=record.turn,
            thought=thought,
            tool_name=record.tool,
            tool_input=record.tool_payload or {},
            observation=record.tool_result,
            duration=record.elapsed_ms / 1000.0,
        )
    return StepEvent(
        step_index=record.turn,
        thought=thought,
        observation=record.tool_result,
        duration=record.elapsed_ms / 1000.0,
    )


def sample_graph_run() -> list[GraphNodeRecord]:
    """演示用 graph 轨迹（含 tavily_query 工具名，非 *search* 命名）。"""
    return [
        GraphNodeRecord(
            run_id="g1",
            node_name="researcher",
            turn=1,
            planner_text="query knowledge base",
            tool="tavily_query",
            tool_payload={"q": "AI agents 2026"},
            tool_result="err",
            elapsed_ms=400,
        ),
        GraphNodeRecord(
            run_id="g1",
            node_name="researcher",
            turn=2,
            planner_text="retry with broader query",
            tool="tavily_query",
            tool_payload={"q": "artificial intelligence agents adoption 2026"},
            tool_result="Enterprise AI agent adoption accelerated in 2026 across sectors.",
            elapsed_ms=1100,
        ),
        GraphNodeRecord(
            run_id="g1",
            node_name="writer",
            turn=3,
            planner_text="FINAL ANSWER: 2026 年企业 AI Agent 采用加速。",
            elapsed_ms=80,
        ),
    ]
