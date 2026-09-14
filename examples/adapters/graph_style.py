"""有限示例：当节点记录已经近似「一步」时，映射为 StepEvent。

警告：这不是「把整张 LangGraph / 状态机编译成 Format B steps」的方案。
图拓扑应留在原运行时；仅在已有 thought/tool/obs 边界时使用本映射。
政策说明见 docs/INTEGRATIONS.md「LangGraph / 状态机图」。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from trace_debugger.harness import StepEvent


@dataclass
class GraphNodeRecord:
    """已近似线性步进的节点记录（非通用图 IR）。"""

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
