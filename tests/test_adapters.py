"""Adapter 可移植性测试 — graph / react 两种框架映射"""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from examples.adapters.graph_style import (  # noqa: E402
    graph_node_to_step_event,
    sample_graph_run,
)
from examples.adapters.react_loop import ReActStepRaw, react_step_to_event  # noqa: E402
from trace_debugger.analyzer import Analyzer
from trace_debugger.harness import (
    FailureHarness,
    RunContext,
    analyze_trajectory_dict,
    build_trajectory_dict,
    enrich_trajectory_dict,
)
from trace_debugger.validate import validate_trajectory_file


def test_react_loop_adapter_offline():
    events = [
        react_step_to_event(ReActStepRaw(1, "calc", tool="calculator", input={"x": "2++"}, output='{"error": "bad"}', latency_s=0.1)),
        react_step_to_event(ReActStepRaw(2, "FINAL ANSWER: no", output="")),
    ]
    ctx = RunContext(session_id="react_adapt", query="calc", model="m")
    traj = enrich_trajectory_dict(build_trajectory_dict(ctx, events, final_answer="no"))
    analysis = analyze_trajectory_dict(traj)
    types = {ft for pa in analysis.paths for ft in pa.failure_types}
    assert "tool_error" in types


def test_graph_style_adapter_with_custom_search_tools():
    """tavily_query 不在默认 search 子串中，需配置 search_tool_names。"""
    analyzer = Analyzer(search_tool_names=("tavily_query",))
    events = [graph_node_to_step_event(n) for n in sample_graph_run()]
    ctx = RunContext(session_id="graph_adapt", query="AI agents 2026", model="graph-mock")
    traj = build_trajectory_dict(
        ctx,
        events,
        final_answer="2026 年企业 AI Agent 采用加速。",
        total_duration=1.5,
    )

    with tempfile.TemporaryDirectory() as td:
        path = f"{td}/graph_traj.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(traj, f, ensure_ascii=False)
        assert validate_trajectory_file(path) == []

    enriched = enrich_trajectory_dict(traj, analyzer=analyzer)
    assert enriched["steps"][0].get("failure_tags") == ["search_empty"]

    harness = FailureHarness(ctx, analyzer=analyzer)
    for ev in events:
        harness.after_observation(ev)
    harness.finish(final_answer="2026 年企业 AI Agent 采用加速。", total_duration=1.5)
    assert harness.trajectory_dict()["steps"][0]["failure_tags"] == ["search_empty"]


def test_custom_final_answer_marker():
    analyzer = Analyzer(final_answer_markers=("ANSWER:",))
    events = [
        react_step_to_event(ReActStepRaw(1, "done", output="")),
    ]
    ctx = RunContext(session_id="m", query="q", model="m")
    traj = build_trajectory_dict(
        ctx,
        events,
        final_answer="",
    )
    traj["steps"][0]["thought"] = "ANSWER: hello world about AI trends in 2026"
    analysis = analyze_trajectory_dict(traj, analyzer=analyzer)
    types = {ft for pa in analysis.paths for ft in pa.failure_types}
    assert "no_answer" not in types
