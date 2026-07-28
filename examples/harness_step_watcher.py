"""Harness 集成示例 — 执行中逐步检测并记录失败

演示 react-agent Harness 应如何在两个 hook 点调用 StepWatcher：
  1. after_tool_observation → on_step()
  2. on_trajectory_save     → on_finish() + to_trajectory_dict()

在 react-agent 仓中，将 MOCK_RUN 替换为真实 Agent 循环即可。
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trace_debugger.runtime import StepWatcher, failure_tags_from_step  # noqa: E402


def mock_agent_run(query: str) -> list[dict]:
    """模拟 Agent 三步执行：搜索失败 → 重试成功 → 输出答案。"""
    return [
        {
            "step_index": 1,
            "thought": "先搜索资料",
            "action_name": "web_search",
            "action_args": '{"query": "AI trends 2026"}',
            "observation": "err",
            "duration": 0.3,
            "tokens": 50,
        },
        {
            "step_index": 2,
            "thought": "换词再搜",
            "action_name": "web_search",
            "action_args": '{"query": "artificial intelligence market 2026"}',
            "observation": "AI market is growing rapidly in 2026 with strong adoption.",
            "duration": 1.2,
            "tokens": 120,
        },
        {
            "step_index": 3,
            "thought": "FINAL ANSWER: AI 市场在 2026 年持续增长。",
            "action_name": "",
            "action_args": "",
            "observation": "",
            "duration": 0.1,
            "tokens": 30,
        },
    ]


def run_with_watcher(query: str, record_path: str) -> tuple[dict, list[str]]:
    """模拟 Harness 主循环 + StepWatcher 集成。"""
    watcher = StepWatcher(
        session_id="demo_runtime_001",
        query=query,
        model="mock-gpt",
        record_path=record_path,
        source_file="trajectories/demo_runtime_001.json",
    )

    log_lines: list[str] = []
    for raw in mock_agent_run(query):
        sa = watcher.on_step(**raw)
        tags = failure_tags_from_step(sa)
        if not sa.success:
            log_lines.append(
                f"  [LIVE] Step {sa.step_index} → {sa.failure_type}: {sa.failure_detail}"
            )
        if tags:
            raw.update(tags)

    analysis = watcher.on_finish(
        final_answer="AI 市场在 2026 年持续增长。",
        total_duration=1.6,
    )
    traj_dict = watcher.to_trajectory_dict()

    log_lines.append(f"  [FINISH] {analysis.overall_assessment}")
    return traj_dict, log_lines


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        record_path = str(Path(td) / "failures.jsonl")
        traj, logs = run_with_watcher("写一份 AI 趋势简报", record_path)

        print("=" * 55)
        print("  Harness StepWatcher 集成演示")
        print("=" * 55)
        for line in logs:
            print(line)

        print("\n  轨迹 JSON（含 failure_tags）:")
        print(json.dumps(traj["steps"][0], ensure_ascii=False, indent=2))

        print("\n  failures.jsonl:")
        with open(record_path, encoding="utf-8") as f:
            for line in f:
                ev = json.loads(line)
                print(f"    {ev['event_type']} step={ev.get('step_index')} type={ev.get('failure_type')}")

        print("\n  react-agent 集成要点:")
        print("    1. Harness.after_observation(step) → watcher.on_step(...)")
        print("    2. Harness.save_trajectory()       → watcher.on_finish(...)")
        print("    3. 落盘时用 watcher.to_trajectory_dict() 保留 failure_tags")
        print("=" * 55)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
