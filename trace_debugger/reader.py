"""reader — 读取并解析 Agent Trajectory JSON (Format B)

Canonical schema: schemas/agent_trajectory.schema.json
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Step:
    """轨迹中的单步"""
    index: int
    thought: str = ""
    action_name: str = ""
    action_args: str = ""
    observation: str = ""
    duration: float = 0.0
    tokens: int = 0
    has_error: bool = False          # 工具调用是否报错
    error_message: str = ""          # 错误信息

    @property
    def is_action(self) -> bool:
        """返回该步是否包含工具动作。"""
        return bool(self.action_name)

    @property
    def is_final(self) -> bool:
        """按兼容格式中的 FINAL ANSWER 标记识别终答步骤。"""
        return "FINAL ANSWER" in self.thought.upper()

    @property
    def is_thought(self) -> bool:
        """返回该步是否为非终答的有效思考。"""
        return bool(self.thought.strip()) and not self.is_final

    @property
    def summary(self) -> str:
        """生成用于终端和报告的截断单行摘要。"""
        if self.is_final:
            return f"输出答案: {self.thought[:80]}"
        if self.is_action:
            return f"调工具: {self.action_name}({self.action_args[:60]})"
        if self.thought:
            return f"思考: {self.thought[:80]}"
        return f"步骤 {self.index}"


@dataclass
class Path:
    """Agent 执行的一条路径

    一条路径 = 从开始到 FINAL ANSWER（或终止）的连续步骤。
    简单任务只有 1 条路径，复杂任务（如 ToT 多次推理）可能有多条。
    """
    steps: list[Step] = field(default_factory=list)
    success: bool = False
    final_answer: str = ""
    is_main_path: bool = False       # 是否最终输出答案的路径

    @property
    def num_steps(self) -> int:
        """返回路径中的步骤数。"""
        return len(self.steps)

    @property
    def tools_used(self) -> list[str]:
        """按调用顺序返回工具名，保留重复调用。"""
        return [s.action_name for s in self.steps if s.action_name]

    @property
    def has_errors(self) -> bool:
        """返回路径是否含解析器识别出的工具错误。"""
        return any(s.has_error for s in self.steps)

    @property
    def error_summary(self) -> list[str]:
        """返回路径内各错误步骤的截断消息。"""
        return [s.error_message for s in self.steps if s.has_error]


@dataclass
class Trajectory:
    """完整的执行轨迹"""
    session_id: str
    query: str
    model: str
    timestamp: str
    steps: list[Step]
    paths: list[Path]
    final_answer: str
    total_duration: float
    metadata: dict = field(default_factory=dict)

    @property
    def num_steps(self) -> int:
        """返回顶层轨迹步骤数。"""
        return len(self.steps)

    @property
    def num_paths(self) -> int:
        """返回解析后的执行路径数。"""
        return len(self.paths)

    @property
    def main_path(self) -> Optional[Path]:
        """返回显式主路径；旧数据未标记时回退到最后一条。"""
        for p in self.paths:
            if p.is_main_path:
                return p
        return self.paths[-1] if self.paths else None

    @property
    def failed_paths(self) -> list[Path]:
        """返回失败的非主路径，避免把最终输出路径重复计为失败分支。"""
        return [p for p in self.paths if not p.success and not p.is_main_path]


def load(filepath: str) -> Trajectory:
    """从 JSON 文件加载轨迹

    参数:
        filepath: JSON 文件路径

    返回:
        Trajectory
    """
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)
    return parse(data)


def _parse_step(raw: dict) -> Step:
    """Parse a single raw step dict into Step."""
    step_num = raw.get("step", 0)
    thought = raw.get("thought", "")
    action = raw.get("action", {}) or {}
    actions = raw.get("actions")
    if (not action) and isinstance(actions, list) and actions:
        action = actions[0] or {}
    observation = raw.get("observation", "")

    action_name = action.get("name", "") if isinstance(action, dict) else ""
    raw_args = ""
    if isinstance(action, dict):
        raw_args = action.get("arguments", action.get("args", ""))
    if isinstance(raw_args, dict):
        action_args = json.dumps(raw_args, ensure_ascii=False)
    else:
        action_args = str(raw_args) if raw_args is not None else ""

    has_error = False
    error_msg = ""
    if observation:
        if "error" in observation.lower() or "异常" in observation:
            has_error = True
            error_msg = observation[:200]

    return Step(
        index=step_num,
        thought=thought,
        action_name=action_name,
        action_args=action_args[:200],
        observation=observation[:300],
        duration=raw.get("duration_seconds", 0.0),
        tokens=raw.get("tokens_estimated", 0),
        has_error=has_error,
        error_message=error_msg,
    )


def _build_paths_from_steps(
    steps: list[Step],
    *,
    final_answer: str,
) -> list[Path]:
    """从步骤列表构建路径（单路径 fallback）。"""
    has_final = bool(final_answer.strip()) or any(s.is_final for s in steps)
    return [Path(
        steps=steps,
        success=has_final,
        is_main_path=True,
        final_answer=final_answer,
    )]


def _split_steps_by_path_id(raw_steps: list[dict]) -> list[tuple[int, list[Step]]]:
    """按 step.path_id / step.branch_id 分组。"""
    if not raw_steps:
        return []
    groups: list[tuple[int, list[Step]]] = []
    current_id = 0
    current_steps: list[Step] = []

    for raw in raw_steps:
        pid = raw.get("path_id", raw.get("branch_id"))
        if pid is None:
            pid = current_id
        else:
            pid = int(pid)
        if current_steps and pid != current_id:
            groups.append((current_id, current_steps))
            current_steps = []
        current_id = pid
        current_steps.append(_parse_step(raw))

    if current_steps:
        groups.append((current_id, current_steps))
    return groups


def _parse_paths_array(paths_data: list[dict]) -> list[Path]:
    """解析顶层 paths[]（Harness 多路径格式）。"""
    paths: list[Path] = []
    for i, pdata in enumerate(paths_data):
        raw_steps = pdata.get("steps", [])
        steps = [_parse_step(s) for s in raw_steps]
        final_answer = pdata.get("final_answer", "") or ""
        has_final = bool(final_answer.strip()) or any(s.is_final for s in steps)
        paths.append(Path(
            steps=steps,
            success=pdata.get("success", has_final),
            is_main_path=bool(pdata.get("is_main", pdata.get("is_main_path", False))),
            final_answer=final_answer,
        ))
    if paths and not any(p.is_main_path for p in paths):
        paths[-1].is_main_path = True
    return paths


def _resolve_paths(data: dict, steps: list[Step]) -> list[Path]:
    """解析轨迹中的路径（支持 paths[]、path_id 分组、单路径）。"""
    paths_data = data.get("paths")
    if isinstance(paths_data, list) and paths_data:
        return _parse_paths_array(paths_data)

    raw_steps = data.get("steps", [])
    if raw_steps and any(
        raw.get("path_id") is not None or raw.get("branch_id") is not None
        for raw in raw_steps
    ):
        groups = _split_steps_by_path_id(raw_steps)
        if groups:
            main_idx = data.get("main_path_index")
            if main_idx is None:
                main_idx = groups[-1][0]
            final_answer = data.get("final_answer", "") or ""
            paths = []
            for path_id, path_steps in groups:
                ans = ""
                for s in reversed(path_steps):
                    if s.is_final:
                        ans = s.thought
                        break
                has_final = bool(ans.strip()) or any(s.is_final for s in path_steps)
                is_main = path_id == main_idx or (
                    main_idx is None and path_id == groups[-1][0]
                )
                paths.append(Path(
                    steps=path_steps,
                    success=has_final,
                    is_main_path=is_main,
                    final_answer=ans or (final_answer if is_main else ""),
                ))
            if paths and not any(p.is_main_path for p in paths):
                paths[-1].is_main_path = True
            return paths

    final_answer = data.get("final_answer", "") or ""
    return _build_paths_from_steps(steps, final_answer=final_answer)


def parse(data: dict) -> Trajectory:
    """解析轨迹字典为 Trajectory 对象"""
    raw_steps = data.get("steps", [])
    steps = [_parse_step(s) for s in raw_steps]
    paths = _resolve_paths(data, steps)

    return Trajectory(
        session_id=data.get("session_id", ""),
        query=data.get("query", ""),
        model=data.get("model", ""),
        timestamp=data.get("timestamp", ""),
        steps=steps,
        paths=paths,
        final_answer=data.get("final_answer", ""),
        total_duration=data.get("total_duration_seconds", 0.0),
        metadata={
            "system_prompt_preview": data.get("system_prompt_preview", ""),
            "total_tokens_estimated": data.get("total_tokens_estimated", 0),
            "task_episode_id": data.get("task_episode_id", ""),
            "acceptance_criteria": data.get("acceptance_criteria") or [],
            **dict(data.get("metadata") or {}),
        },
    )


def load_recent_paths(directory: str, n: int = 5) -> tuple[list[Trajectory], list[str]]:
    """加载最近 N 条轨迹，并返回对应文件路径。"""
    if not os.path.exists(directory):
        return [], []
    files = sorted(
        [f for f in os.listdir(directory) if f.endswith(".json")],
        key=lambda f: os.path.getmtime(os.path.join(directory, f)),
        reverse=True,
    )[:n]
    trajs: list[Trajectory] = []
    paths: list[str] = []
    for f in files:
        full = os.path.join(directory, f)
        try:
            trajs.append(load(full))
            paths.append(full)
        except Exception:
            continue
    return trajs, paths


def load_recent(directory: str, n: int = 5) -> list[Trajectory]:
    """加载最近的 N 条轨迹

    参数:
        directory: 轨迹目录
        n: 加载条数

    返回:
        list[Trajectory]
    """
    if not os.path.exists(directory):
        return []
    files = sorted(
        [f for f in os.listdir(directory) if f.endswith(".json")],
        reverse=True,
    )[:n]
    result = []
    for f in files:
        try:
            result.append(load(os.path.join(directory, f)))
        except Exception:
            continue
    return result
