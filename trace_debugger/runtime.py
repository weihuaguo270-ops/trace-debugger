"""runtime — Agent 执行过程中的实时失败检测与记录

供 react-agent Harness 在每步 observation 返回后调用 StepWatcher.on_step()，
任务结束时调用 on_finish() 补记路径级失败（duplicate / no_answer / offtrack 等）。

集成示例见 examples/harness_step_watcher.py
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .analyzer import Analyzer, StepAnalysis, TrajectoryAnalysis
from .reader import Step, Trajectory, parse
from .record import (
    DEFAULT_RECORD_PATH,
    append_events,
    append_failure_events,
    step_failure_event,
)


def _detect_step_error(observation: str) -> tuple[bool, str]:
    if not observation:
        return False, ""
    if "error" in observation.lower() or "异常" in observation:
        return True, observation[:200]
    return False, ""


def failure_tags_from_step(
    sa: StepAnalysis,
    *,
    thought: str = "",
    action_args: str = "",
    observation: str = "",
) -> dict[str, Any]:
    """供 Harness 写入 step JSON 的失败标记（无失败时返回空 dict）。"""
    if sa.success or not sa.failure_type:
        return {}
    from .record import (
        build_failure_context,
        build_failure_summary,
        failure_label,
        failure_severity,
    )

    label = failure_label(sa.failure_type)
    summary = build_failure_summary(
        failure_type=sa.failure_type,
        step_index=sa.step_index,
        action=sa.action,
    )
    ctx = build_failure_context(
        thought=thought,
        action=sa.action,
        action_args=action_args,
        observation=observation,
        duration=sa.duration,
    )
    block: dict[str, Any] = {
        "types": [sa.failure_type],
        "label": label,
        "summary": summary,
        "detail": sa.failure_detail,
        "severity": failure_severity(sa.failure_type),
        "context": ctx,
    }
    if sa.suggestion:
        block["suggestion"] = sa.suggestion

    return {
        "failure_tags": [sa.failure_type],
        "failure_label": label,
        "failure_summary": summary,
        "failure_detail": sa.failure_detail,
        "failure_severity": block["severity"],
        "failure_context": ctx,
        "failure": block,
        "suggestion": sa.suggestion,
    }


@dataclass
class StepWatcher:
    """运行时逐步检测并记录 Agent 失败动作。

    用法（在 Harness 中）::

        watcher = StepWatcher(session_id, query, model, record_path=".tdebug/failures.jsonl")
        for step in run_agent():
            sa = watcher.on_step(
                step_index=step.n,
                thought=step.thought,
                action_name=step.tool,
                action_args=step.args,
                observation=step.observation,
                duration=step.duration,
                tokens=step.tokens,
            )
            step.extra.update(failure_tags_from_step(sa))  # 可选：写回轨迹
        analysis = watcher.on_finish(final_answer=answer, total_duration=elapsed)
    """

    session_id: str
    query: str
    model: str
    record_path: str = DEFAULT_RECORD_PATH
    source_file: str = ""
    path_index: int = 0
    auto_record: bool = True
    analyzer: Analyzer = field(default_factory=Analyzer)

    _steps: list[Step] = field(default_factory=list, init=False, repr=False)
    _recorded_steps: set[tuple[int, int]] = field(default_factory=set, init=False, repr=False)
    _step_results: list[StepAnalysis] = field(default_factory=list, init=False, repr=False)
    _final_answer: str = field(default="", init=False, repr=False)
    _total_duration: float = field(default=0.0, init=False, repr=False)
    _metadata: dict[str, Any] = field(default_factory=dict, init=False, repr=False)
    _final_analysis: Optional[TrajectoryAnalysis] = field(default=None, init=False, repr=False)

    def on_step(
        self,
        *,
        step_index: int,
        thought: str = "",
        action_name: str = "",
        action_args: str = "",
        observation: str = "",
        duration: float = 0.0,
        tokens: int = 0,
        has_error: Optional[bool] = None,
        error_message: str = "",
    ) -> StepAnalysis:
        """每步 observation 返回后调用 — 检测并可选即时记录失败。"""
        self._upsert_step(
            step_index=step_index,
            thought=thought,
            action_name=action_name,
            action_args=action_args,
            observation=observation,
            duration=duration,
            tokens=tokens,
            has_error=has_error,
            error_message=error_message,
        )
        step = self._steps[-1]
        cum = self._cum_tokens_for(step_index)
        sa = self.analyzer.analyze_step(step, cum_tokens=cum)
        self._step_results[-1] = sa

        if self.auto_record and not sa.success and sa.failure_type:
            key = (self.path_index, step_index)
            if key not in self._recorded_steps:
                ev = step_failure_event(
                    sa,
                    session_id=self.session_id,
                    query=self.query,
                    model=self.model,
                    path_index=self.path_index,
                    source_file=self.source_file,
                    thought=thought,
                    action_args=action_args,
                    observation=observation,
                )
                append_events(self.record_path, [ev])
                self._recorded_steps.add(key)

        return sa

    def _upsert_step(
        self,
        *,
        step_index: int,
        thought: str,
        action_name: str,
        action_args: str,
        observation: str,
        duration: float,
        tokens: int,
        has_error: Optional[bool],
        error_message: str,
    ) -> None:
        """同 step_index 再次调用时更新（适配 add_thought → add_tool_call）。"""
        for i, existing in enumerate(self._steps):
            if existing.index == step_index:
                self._steps.pop(i)
                self._step_results.pop(i)
                self._recorded_steps.discard((self.path_index, step_index))
                break

        if has_error is None:
            has_error, auto_err = _detect_step_error(observation)
            if not error_message and auto_err:
                error_message = auto_err
        elif has_error and not error_message:
            error_message = observation[:200]

        step = Step(
            index=step_index,
            thought=thought,
            action_name=action_name,
            action_args=str(action_args)[:200],
            observation=observation[:300],
            duration=duration,
            tokens=tokens,
            has_error=bool(has_error),
            error_message=error_message,
        )
        self._steps.append(step)
        self._step_results.append(
            StepAnalysis(
                step_index=step_index,
                action=action_name,
                success=True,
                duration=duration,
            )
        )

    def _cum_tokens_for(self, through_step: int) -> int:
        total = 0
        for s in sorted(self._steps, key=lambda x: x.index):
            total += int(s.tokens or 0)
            if s.index == through_step:
                break
        return total

    def on_finish(
        self,
        *,
        final_answer: str = "",
        total_duration: float = 0.0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> TrajectoryAnalysis:
        """任务结束时调用 — 路径级检测并补记未记录的失败事件。"""
        self._final_answer = final_answer
        self._total_duration = total_duration
        if metadata:
            self._metadata.update(metadata)

        traj = self.build_trajectory()
        analysis = self.analyzer.analyze(traj)
        self._final_analysis = analysis

        if self.auto_record:
            append_failure_events(
                analysis,
                self.record_path,
                source_file=self.source_file,
                skip_steps=self._recorded_steps,
            )

        return analysis

    def build_trajectory(self) -> Trajectory:
        """从已收集步骤构建 Trajectory（供 Harness 落盘前合并 failure_tags）。"""
        data = self.to_trajectory_dict()
        return parse(data)

    def to_trajectory_dict(self) -> dict[str, Any]:
        """转为 Harness Format B 轨迹 dict（含 failure_tags）。"""
        step_analysis_map: dict[int, StepAnalysis] = {
            sa.step_index: sa for sa in self._step_results
        }
        if self._final_analysis:
            for pa in self._final_analysis.paths:
                if pa.path_index != self.path_index:
                    continue
                for sa in pa.step_analyses:
                    if sa.failure_type:
                        step_analysis_map[sa.step_index] = sa

        raw_steps: list[dict[str, Any]] = []
        for step in self._steps:
            sa = step_analysis_map.get(step.index, StepAnalysis(
                step_index=step.index, action=step.action_name, success=True, duration=step.duration,
            ))
            entry: dict[str, Any] = {
                "step": step.index,
                "thought": step.thought,
                "observation": step.observation,
                "duration_seconds": step.duration,
                "tokens_estimated": step.tokens,
            }
            if step.action_name:
                entry["action"] = {
                    "name": step.action_name,
                    "arguments": step.action_args,
                }
            entry.update(failure_tags_from_step(
                sa,
                thought=step.thought,
                action_args=step.action_args,
                observation=step.observation,
            ))
            raw_steps.append(entry)

        return {
            "session_id": self.session_id,
            "query": self.query,
            "model": self.model,
            "steps": raw_steps,
            "final_answer": self._final_answer,
            "total_duration_seconds": self._total_duration,
            **({"total_tokens_estimated": self._metadata["total_tokens_estimated"]}
               if "total_tokens_estimated" in self._metadata else {}),
        }
