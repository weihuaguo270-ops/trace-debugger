"""可移植集成演示 — 任意 Agent 只需映射 StepEvent

不依赖 react-agent / LangChain / LangGraph。
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trace_debugger.harness import (  # noqa: E402
    FailureHarness,
    RunContext,
    StepEvent,
    build_trajectory_dict,
    enrich_trajectory_dict,
    validate_trajectory_dict,
)


class MockAgent:
    """模拟任意框架的 Agent：内部有自己的 step 结构。"""

    def __init__(self, query: str) -> None:
        self.query = query
        self._i = 0

    def run(self) -> list[dict]:
        return [
            {"kind": "tool", "name": "web_search", "input": {"query": "AI"}, "output": "err", "ms": 300},
            {"kind": "tool", "name": "web_search", "input": {"query": "AI market"}, "output": "growth " * 20, "ms": 900},
            {"kind": "answer", "text": "FINAL ANSWER: AI 市场增长", "output": ""},
        ]


def framework_step_to_event(raw: dict, step_index: int) -> StepEvent:
    """适配器：把 MockAgent 的 step 映射为 trace-debugger StepEvent。"""
    if raw.get("kind") == "tool":
        return StepEvent(
            step_index=step_index,
            thought=f"call {raw['name']}",
            tool_name=raw["name"],
            tool_input=raw["input"],
            observation=raw.get("output", ""),
            duration=raw.get("ms", 0) / 1000.0,
        )
    return StepEvent(
        step_index=step_index,
        thought=raw.get("text", ""),
        observation=raw.get("output", ""),
    )


def demo_runtime() -> None:
    print("── 运行时集成（FailureHarness）──")
    harness = FailureHarness(
        RunContext(session_id="portable_demo", query="AI 趋势", model="mock-gpt")
    )
    for i, raw in enumerate(MockAgent("AI 趋势").run(), start=1):
        sa = harness.after_observation(framework_step_to_event(raw, i))
        tags = harness.last_failure_tags()
        if tags:
            print(f"  step {i}: {tags.get('failure_summary', sa.failure_type)}")
    harness.finish(final_answer="AI 市场增长", total_duration=1.2)
    print(f"  轨迹步数: {len(harness.trajectory_dict()['steps'])}")


def demo_offline_exporter() -> None:
    print("\n── 离线 exporter（build + enrich）──")
    ctx = RunContext(session_id="export_demo", query="calc", model="mock")
    events = [
        framework_step_to_event(
            {"kind": "tool", "name": "calculator", "input": {"expression": "2++"}, "output": '{"error": "bad"}', "ms": 100},
            1,
        ),
        framework_step_to_event({"kind": "answer", "text": "FINAL ANSWER: fail", "output": ""}, 2),
    ]
    traj = build_trajectory_dict(ctx, events, final_answer="fail")
    assert validate_trajectory_dict(traj) == []
    enriched = enrich_trajectory_dict(traj)
    print(f"  failure_tags step1: {enriched['steps'][0].get('failure_tags')}")


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "exported.json"
        demo_runtime()
        demo_offline_exporter()
        print(f"\n  适配要点: 实现 framework_step_to_event() 即可接入任意 Agent")
        print(f"  Schema: schemas/agent_trajectory.schema.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
