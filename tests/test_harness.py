"""可移植集成层测试 — 框架无关 StepEvent / FailureHarness"""

import json
import tempfile

from trace_debugger.harness import (
    FailureHarness,
    RunContext,
    StepEvent,
    analyze_trajectory_dict,
    build_trajectory_dict,
    enrich_trajectory_dict,
    normalize_tool_input,
    validate_trajectory_dict,
)


def test_normalize_tool_input():
    assert normalize_tool_input({"q": "AI"}) == '{"q": "AI"}'
    assert normalize_tool_input('{"q": "x"}') == '{"q": "x"}'
    assert normalize_tool_input(None) == ""


def test_build_and_validate_trajectory():
    ctx = RunContext(session_id="s1", query="hello", model="m")
    traj = build_trajectory_dict(
        ctx,
        [
            StepEvent(
                step_index=1,
                thought="search",
                tool_name="web_search",
                tool_input={"query": "AI"},
                observation="results here " * 5,
                duration=0.5,
            ),
            StepEvent(step_index=2, thought="FINAL ANSWER: done", observation=""),
        ],
        final_answer="done",
        total_duration=1.0,
    )
    assert validate_trajectory_dict(traj) == []
    assert traj["steps"][0]["action"]["name"] == "web_search"


def test_offline_enrich_adds_failure_tags():
    ctx = RunContext(session_id="s2", query="calc", model="m")
    traj = build_trajectory_dict(
        ctx,
        [
            StepEvent(
                step_index=1,
                thought="calc",
                tool_name="calculator",
                tool_input={"expression": "2++"},
                observation='{"error": "syntax"}',
            ),
            StepEvent(step_index=2, thought="FINAL ANSWER: no", observation=""),
        ],
        final_answer="no",
    )
    enriched = enrich_trajectory_dict(traj)
    assert enriched["steps"][0].get("failure_tags") == ["tool_error"]


def test_failure_harness_runtime():
    with tempfile.TemporaryDirectory() as td:
        record_path = f"{td}/failures.jsonl"
        harness = FailureHarness(
            RunContext(
                session_id="live",
                query="search AI",
                model="mock",
                record_path=record_path,
            )
        )
        sa = harness.after_observation(
            StepEvent(
                step_index=1,
                thought="search",
                tool_name="web_search",
                tool_input={"query": "x"},
                observation="err",
                duration=0.2,
            )
        )
        assert not sa.success
        assert harness.last_failure_tags().get("failure_tags") == ["search_empty"]

        harness.after_observation(
            StepEvent(step_index=2, thought="FINAL ANSWER: ok", observation="")
        )
        harness.finish(final_answer="ok", total_duration=0.5)
        traj = harness.trajectory_dict()
        assert traj["steps"][0]["failure_tags"] == ["search_empty"]

        with open(record_path, encoding="utf-8") as f:
            assert f.readline().strip()


def test_analyze_trajectory_dict_raises_on_invalid():
    try:
        analyze_trajectory_dict({"session_id": "x"})
        assert False, "expected ValueError"
    except ValueError as e:
        assert "missing" in str(e)
