"""harness — 框架无关的可移植集成层

任意 Agent 运行时只需：
  1. 构造 RunContext + StepEvent
  2. FailureHarness.after_observation() / finish()
或离线：build_trajectory_dict() → analyze_trajectory_dict()

不依赖 LangChain、LangGraph、react-agent 等具体框架。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

from .analyzer import Analyzer, StepAnalysis, TrajectoryAnalysis
from .reader import parse
from .record import resolve_record_path
from .runtime import StepWatcher, failure_tags_from_step
from .validate import SCHEMA_PATH, validate_trajectory_dict


@dataclass
class RunContext:
    """一次 Agent 运行的元数据（与框架无关）。"""

    session_id: str
    query: str
    model: str = ""
    source_file: str = ""
    record_path: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


@dataclass
class StepEvent:
    """单步 observation 返回后的中性事件（由各 Agent 适配器填充）。"""

    step_index: int
    thought: str = ""
    tool_name: str = ""
    tool_input: Union[str, dict, None] = None
    observation: str = ""
    duration: float = 0.0
    tokens: int = 0
    has_error: Optional[bool] = None
    error_message: str = ""

    def tool_args_str(self) -> str:
        return normalize_tool_input(self.tool_input)


def normalize_tool_input(tool_input: Union[str, dict, None]) -> str:
    """将任意框架的工具参数统一为 Format B 字符串。"""
    if tool_input is None:
        return ""
    if isinstance(tool_input, dict):
        return json.dumps(tool_input, ensure_ascii=False)
    return str(tool_input)


def step_event_to_format_b(
    event: StepEvent,
    *,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """StepEvent → Format B step dict（不含 failure 字段）。"""
    entry: dict[str, Any] = {
        "step": event.step_index,
        "thought": event.thought,
        "observation": event.observation,
        "duration_seconds": event.duration,
        "tokens_estimated": event.tokens,
    }
    if event.tool_name:
        entry["action"] = {
            "name": event.tool_name,
            "arguments": event.tool_args_str(),
        }
    if extra:
        entry.update(extra)
    return entry


def build_trajectory_dict(
    context: RunContext,
    steps: list[StepEvent],
    *,
    final_answer: str = "",
    total_duration: float = 0.0,
    total_tokens: Optional[int] = None,
) -> dict[str, Any]:
    """离线构建 Format B 轨迹（无需 StepWatcher，适合 exporter-only 集成）。"""
    data: dict[str, Any] = {
        "session_id": context.session_id,
        "query": context.query,
        "model": context.model,
        "timestamp": context.timestamp,
        "steps": [step_event_to_format_b(s) for s in steps],
        "final_answer": final_answer,
        "total_duration_seconds": total_duration,
    }
    if total_tokens is not None:
        data["total_tokens_estimated"] = total_tokens
    return data


def analyze_trajectory_dict(
    data: dict,
    *,
    analyzer: Optional[Analyzer] = None,
) -> TrajectoryAnalysis:
    """对已构建的 Format B dict 做离线分析。"""
    errors = validate_trajectory_dict(data)
    if errors:
        raise ValueError("; ".join(errors))
    return (analyzer or Analyzer()).analyze(parse(data))


def enrich_trajectory_dict(
    data: dict,
    *,
    analyzer: Optional[Analyzer] = None,
) -> dict[str, Any]:
    """离线补全 step 上的 failure 字段（无需运行时 StepWatcher）。"""
    analysis = analyze_trajectory_dict(data, analyzer=analyzer)
    step_map: dict[int, Any] = {}
    for pa in analysis.paths:
        for sa in pa.step_analyses:
            if sa.failure_type:
                step_map[sa.step_index] = sa

    enriched = dict(data)
    steps_out: list[dict[str, Any]] = []
    for raw in data.get("steps", []):
        step = dict(raw)
        step_index = int(step.get("step", 0))
        sa = step_map.get(step_index)
        if sa:
            action = step.get("action") or {}
            args = action.get("arguments", action.get("args", "")) if isinstance(action, dict) else ""
            if isinstance(args, dict):
                args = json.dumps(args, ensure_ascii=False)
            step.update(failure_tags_from_step(
                sa,
                thought=str(step.get("thought", "")),
                action_args=str(args),
                observation=str(step.get("observation", "")),
            ))
        steps_out.append(step)
    enriched["steps"] = steps_out
    return enriched


@dataclass
class FailureHarness:
    """可移植运行时适配器 — 包装 StepWatcher，接受 StepEvent。"""

    context: RunContext
    auto_record: bool = True
    analyzer: Analyzer = field(default_factory=Analyzer)
    _watcher: StepWatcher = field(init=False, repr=False)
    _last_tags: dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        record_path = resolve_record_path(self.context.record_path)
        self._watcher = StepWatcher(
            session_id=self.context.session_id,
            query=self.context.query,
            model=self.context.model,
            record_path=record_path,
            source_file=self.context.source_file,
            auto_record=self.auto_record,
            analyzer=self.analyzer,
        )

    def after_observation(self, event: StepEvent):
        """每步 tool/LLM 返回后调用。返回 StepAnalysis；可用 last_failure_tags() 写回 step。"""
        sa = self._watcher.on_step(
            step_index=event.step_index,
            thought=event.thought,
            action_name=event.tool_name,
            action_args=event.tool_args_str(),
            observation=event.observation,
            duration=event.duration,
            tokens=event.tokens,
            has_error=event.has_error,
            error_message=event.error_message,
        )
        self._last_tags = failure_tags_from_step(
            sa,
            thought=event.thought,
            action_args=event.tool_args_str(),
            observation=event.observation,
        )
        return sa

    def last_failure_tags(self) -> dict[str, Any]:
        """上一步 after_observation 产生的 failure 字段（空 dict 表示无失败）。"""
        return dict(self._last_tags)

    def finish(
        self,
        *,
        final_answer: str = "",
        total_duration: float = 0.0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> TrajectoryAnalysis:
        return self._watcher.on_finish(
            final_answer=final_answer,
            total_duration=total_duration,
            metadata=metadata,
        )

    def trajectory_dict(self) -> dict[str, Any]:
        data = self._watcher.to_trajectory_dict()
        data.setdefault("timestamp", self.context.timestamp)
        return data

    @property
    def record_path(self) -> str:
        return self._watcher.record_path
