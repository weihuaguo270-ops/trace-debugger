"""Basic tests for trace-debugger"""

import json
import os
import sys
import tempfile


def test_imports():
    """Verify package imports work"""
    from trace_debugger import Analyzer
    from trace_debugger.reader import Trajectory, Step, Path, parse
    assert Analyzer is not None
    assert Trajectory is not None
    print("✅ Package imports OK")


def test_parse_minimal():
    """Test Trajectory.parse with minimal data"""
    from trace_debugger.reader import Trajectory, parse

    data = {
        "session_id": "test_001",
        "query": "What is Python?",
        "model": "gpt-4",
        "steps": [
            {
                "step": 1,
                "thought": "I should search for this",
                "action": {"name": "web_search", "args": {"query": "Python"}},
                "observation": "Python is a programming language",
            },
            {
                "step": 2,
                "thought": "I have enough info",
                "observation": "",
            },
        ],
        "final_answer": "Python is a programming language",
    }

    traj = parse(data)
    assert traj.session_id == "test_001"
    assert traj.query == "What is Python?"
    assert traj.num_steps == 2
    assert traj.num_paths >= 1
    print(f"✅ Trajectory parsed: {traj.num_steps} steps, {traj.num_paths} path(s)")


def test_analyze():
    """Test full analysis pipeline"""
    from trace_debugger import Analyzer
    from trace_debugger.reader import Trajectory, parse

    data = {
        "session_id": "test_002",
        "query": "Explain ML",
        "model": "gpt-4",
        "steps": [
            {
                "step": 1,
                "thought": "Let me search for machine learning",
                "action": {"name": "web_search", "args": {"query": "machine learning"}},
                "observation": "Machine learning is a subset of AI",
            },
            {
                "step": 2,
                "thought": "I have enough to answer",
                "observation": "",
            },
        ],
        "final_answer": "Machine learning is a subset of AI.",
    }

    traj = parse(data)
    analyzer = Analyzer()
    result = analyzer.analyze(traj)

    assert result is not None
    assert result.session_id == "test_002"
    assert result.query == "Explain ML"
    assert len(result.paths) > 0
    print(f"✅ Analysis complete: {str(result.needs_fix)}")


def test_analyze_with_error():
    """Test analyzing a trajectory with errors"""
    from trace_debugger import Analyzer
    from trace_debugger.reader import Trajectory, parse

    data = {
        "session_id": "test_003",
        "query": "Run code",
        "model": "gpt-4",
        "steps": [
            {
                "step": 1,
                "thought": "Let me execute Python code",
                "action": {"name": "execute_python", "args": {"code": "print(1/0)"}},
                "observation": "Error: division by zero",
            },
            {
                "step": 2,
                "thought": "That failed, let me try again",
                "observation": "",
            },
        ],
        "final_answer": "I encountered an error.",
    }

    traj = parse(data)
    analyzer = Analyzer()
    result = analyzer.analyze(traj)

    assert result is not None
    print(f"✅ Error analysis complete: {str(result.needs_fix)}")


def test_detect_duplicate_and_no_answer():
    """duplicate / no_answer 路径级检测"""
    from trace_debugger import Analyzer
    from trace_debugger.reader import parse

    dup_data = {
        "session_id": "dup",
        "query": "search twice",
        "model": "gpt-4",
        "steps": [
            {
                "step": 1,
                "thought": "search",
                "action": {"name": "web_search", "args": {"query": "AI"}},
                "observation": "result about AI industry trends and markets " * 3,
            },
            {
                "step": 2,
                "thought": "search again",
                "action": {"name": "web_search", "args": {"query": "AI"}},
                "observation": "result about AI industry trends and markets " * 3,
            },
            {
                "step": 3,
                "thought": "FINAL ANSWER: done",
                "observation": "",
            },
        ],
        "final_answer": "done",
    }
    result = Analyzer().analyze(parse(dup_data))
    types = set()
    for pa in result.paths:
        types.update(pa.failure_types)
    assert "duplicate" in types, types
    print("✅ duplicate detection OK")

    no_ans = {
        "session_id": "noans",
        "query": "hello",
        "model": "gpt-4",
        "steps": [
            {
                "step": 1,
                "thought": "thinking only",
                "observation": "",
            },
        ],
        "final_answer": "",
    }
    result2 = Analyzer().analyze(parse(no_ans))
    types2 = set()
    for pa in result2.paths:
        types2.update(pa.failure_types)
    assert "no_answer" in types2, types2
    print("✅ no_answer detection OK")


def test_detect_offtrack_and_overflow():
    """llm_offtrack / context_overflow 启发式"""
    from trace_debugger import Analyzer, failure_distribution
    from trace_debugger.reader import parse

    off = {
        "session_id": "off",
        "query": "写一份关于人工智能行业趋势的详细分析报告",
        "model": "gpt-4",
        "steps": [
            {
                "step": 1,
                "thought": "FINAL ANSWER: 今天天气很好，适合出门散步，记得带伞以免突然下雨。",
                "observation": "",
            }
        ],
        "final_answer": (
            "今天天气很好，适合出门散步，记得带伞以免突然下雨。"
            "周末还可以去公园野餐，欣赏美丽的风景。"
        ),
    }
    r = Analyzer().analyze(parse(off))
    types = {ft for pa in r.paths for ft in pa.failure_types}
    assert "llm_offtrack" in types, types
    print("✅ llm_offtrack detection OK")

    ov = {
        "session_id": "ov",
        "query": "summarize this",
        "model": "gpt-4",
        "steps": [
            {
                "step": 1,
                "thought": "read",
                "action": {"name": "fetch_page", "args": {"url": "x"}},
                "observation": "Error: maximum context length exceeded for this model",
                "tokens_estimated": 100,
            },
            {
                "step": 2,
                "thought": "FINAL ANSWER: failed",
                "observation": "",
            },
        ],
        "final_answer": "failed due to context",
        "total_tokens_estimated": 9000,
    }
    r2 = Analyzer(token_budget=8192).analyze(parse(ov))
    types2 = {ft for pa in r2.paths for ft in pa.failure_types}
    assert "context_overflow" in types2, types2
    print("✅ context_overflow detection OK")

    dist = failure_distribution([r, r2])
    assert dist.get("llm_offtrack", 0) >= 1
    assert dist.get("context_overflow", 0) >= 1
    print(f"✅ failure_distribution OK: {dist}")


def test_sample_trajectory_not_false_offtrack():
    """示例正常轨迹不应被误判为 offtrack"""
    from trace_debugger import Analyzer
    from trace_debugger.reader import load

    path = os.path.join(os.path.dirname(__file__), "..", "examples", "sample_trajectory.json")
    path = os.path.abspath(path)
    if not os.path.exists(path):
        print("⚠️ sample missing, skip")
        return
    result = Analyzer().analyze(load(path))
    types = {ft for pa in result.paths for ft in pa.failure_types}
    assert "llm_offtrack" not in types, types
    print("✅ sample trajectory not false-offtrack")


def test_tool_grounded_short_qa_not_offtrack():
    """短问答 + 工具观测数字 → 不应误报 llm_offtrack"""
    from trace_debugger import Analyzer
    from trace_debugger.reader import parse

    data = {
        "session_id": "time_ok",
        "query": "现在几点了？",
        "model": "gpt-4",
        "steps": [
            {
                "step": 1,
                "thought": "查时间",
                "action": {"name": "get_time", "arguments": "{}"},
                "observation": "2026-07-13 14:12:25",
            },
            {
                "step": 2,
                "thought": "FINAL ANSWER: 当前时间是 2026年7月13日 14时12分25秒",
                "observation": "",
            },
        ],
        "final_answer": "当前时间是 **2026年7月13日 14时12分25秒**（本地时间）。",
    }
    types = {ft for pa in Analyzer().analyze(parse(data)).paths for ft in pa.failure_types}
    assert "llm_offtrack" not in types, types
    print("✅ tool-grounded short QA not offtrack")


def test_readable_failure_record():
    """JSONL + .log + 可读字段"""
    import tempfile
    from trace_debugger.record import (
        append_events,
        format_failures_digest,
        load_failure_events,
        readable_log_path,
    )

    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "failures.jsonl")
        ev = {
            "recorded_at": "2026-07-28T12:00:00+00:00",
            "event_type": "step_failure",
            "session_id": "demo",
            "query": "calc 2+2",
            "step_index": 1,
            "action": "calculator",
            "action_args": '{"expression": "2++"}',
            "observation": '{"error": "syntax"}',
            "failure_type": "tool_error",
            "failure_detail": "calculator 调用失败",
            "suggestion": "检查参数",
        }
        append_events(path, [ev])
        loaded = load_failure_events(path)[0]
        assert loaded["failure_label"] == "工具调用报错"
        assert "Step 1" in loaded["summary"]
        assert loaded["context"]["action"] == "calculator"
        assert readable_log_path(path).is_file()
        digest = format_failures_digest(path)
        assert "工具调用报错" in digest
        assert "calculator" in digest
    print("✅ readable failure record OK")


def test_failure_stats_aggregate():
    """按失败类型聚合统计"""
    import tempfile
    from trace_debugger.record import (
        append_events,
        aggregate_failure_stats,
        format_failure_stats,
    )

    events = [
        {
            "recorded_at": "2026-07-28T12:00:00+00:00",
            "event_type": "step_failure",
            "session_id": "s1",
            "failure_type": "tool_error",
            "action": "calculator",
            "step_index": 1,
        },
        {
            "recorded_at": "2026-07-28T12:01:00+00:00",
            "event_type": "step_failure",
            "session_id": "s1",
            "failure_type": "search_empty",
            "action": "web_search",
            "step_index": 2,
        },
        {
            "recorded_at": "2026-07-28T12:02:00+00:00",
            "event_type": "step_failure",
            "session_id": "s2",
            "failure_type": "tool_error",
            "action": "calculator",
            "step_index": 1,
        },
    ]
    stats = aggregate_failure_stats(events)
    assert stats["n_events"] == 3
    assert stats["n_sessions"] == 2
    assert stats["by_type"][0]["failure_type"] == "tool_error"
    assert stats["by_type"][0]["count"] == 2
    assert stats["by_type"][0]["unique_sessions"] == 2

    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "failures.jsonl")
        append_events(path, events)
        report = format_failure_stats(path)
        assert "工具调用报错" in report
        assert "tool_error" in report
    print("✅ failure stats aggregate OK")


if __name__ == "__main__":
    test_imports()
    test_parse_minimal()
    test_analyze()
    test_analyze_with_error()
    test_detect_duplicate_and_no_answer()
    test_detect_offtrack_and_overflow()
    test_sample_trajectory_not_false_offtrack()
    test_tool_grounded_short_qa_not_offtrack()
    test_multi_path_paths_array()
    test_multi_path_path_id()
    test_failure_recording()
    test_compare_snapshots()
    test_step_watcher_runtime()
    print("\n🎉 All tests passed!")


def test_step_watcher_runtime():
    """StepWatcher 运行时逐步检测 + 结束补记"""
    import tempfile
    from trace_debugger.runtime import StepWatcher, failure_tags_from_step

    with tempfile.TemporaryDirectory() as td:
        record_path = os.path.join(td, "live.jsonl")
        watcher = StepWatcher(
            session_id="live",
            query="search AI",
            model="gpt-4",
            record_path=record_path,
        )
        sa1 = watcher.on_step(
            step_index=1,
            thought="search",
            action_name="web_search",
            action_args='{"query": "AI"}',
            observation="short",
            duration=0.5,
        )
        assert not sa1.success
        assert sa1.failure_type == "search_empty"
        tags = failure_tags_from_step(sa1)
        assert tags["failure_tags"] == ["search_empty"]

        watcher.on_step(
            step_index=2,
            thought="FINAL ANSWER: done",
            observation="",
        )
        analysis = watcher.on_finish(final_answer="done", total_duration=1.0)
        assert analysis.session_id == "live"

        traj = watcher.to_trajectory_dict()
        assert traj["steps"][0].get("failure_tags") == ["search_empty"]

        with open(record_path, encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) >= 1
        first = json.loads(lines[0])
        assert first["event_type"] == "step_failure"
        assert first["step_index"] == 1
    print("✅ StepWatcher runtime OK")


def test_multi_path_paths_array():
    """顶层 paths[] 多路径解析"""
    from trace_debugger.reader import parse

    data = {
        "session_id": "multi_paths",
        "query": "explore options",
        "model": "gpt-4",
        "steps": [],
        "paths": [
            {
                "path_id": 0,
                "is_main": False,
                "success": False,
                "steps": [
                    {
                        "step": 1,
                        "thought": "try A",
                        "action": {"name": "web_search", "args": {"query": "bad"}},
                        "observation": "err",
                    },
                ],
            },
            {
                "path_id": 1,
                "is_main": True,
                "success": True,
                "final_answer": "good answer about AI trends",
                "steps": [
                    {
                        "step": 1,
                        "thought": "try B",
                        "action": {"name": "web_search", "args": {"query": "AI trends"}},
                        "observation": "AI trends are growing rapidly in 2026 " * 2,
                    },
                    {
                        "step": 2,
                        "thought": "FINAL ANSWER: AI trends are growing",
                        "observation": "",
                    },
                ],
            },
        ],
    }
    traj = parse(data)
    assert traj.num_paths == 2
    assert traj.main_path is not None
    assert traj.main_path.is_main_path
    assert len(traj.failed_paths) >= 1
    print("✅ multi-path paths[] OK")


def test_multi_path_path_id():
    """step.path_id 分组多路径"""
    from trace_debugger.reader import parse

    data = {
        "session_id": "multi_pid",
        "query": "branch test",
        "model": "gpt-4",
        "main_path_index": 1,
        "steps": [
            {
                "step": 1,
                "path_id": 0,
                "thought": "branch fail",
                "action": {"name": "calc", "args": {}},
                "observation": '{"error": "fail"}',
            },
            {
                "step": 1,
                "path_id": 1,
                "thought": "FINAL ANSWER: ok",
                "observation": "",
            },
        ],
        "final_answer": "ok",
    }
    traj = parse(data)
    assert traj.num_paths == 2
    main = traj.main_path
    assert main is not None and main.is_main_path
    print("✅ multi-path path_id OK")


def test_failure_recording():
    """JSONL 失败事件记录"""
    import tempfile
    from trace_debugger import Analyzer
    from trace_debugger.reader import parse
    from trace_debugger.record import append_failure_events, failure_events_from_analysis

    data = {
        "session_id": "rec",
        "query": "calc",
        "model": "gpt-4",
        "steps": [
            {
                "step": 1,
                "thought": "calc",
                "action": {"name": "calc", "args": {}},
                "observation": '{"error": "bad"}',
            },
            {"step": 2, "thought": "FINAL ANSWER: no", "observation": ""},
        ],
        "final_answer": "no",
    }
    analysis = Analyzer().analyze(parse(data))
    events = failure_events_from_analysis(analysis, source_file="x.json")
    assert any(e["failure_type"] == "tool_error" for e in events)

    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "failures.jsonl")
        n = append_failure_events(analysis, path, source_file="x.json")
        assert n >= 1
        with open(path, encoding="utf-8") as f:
            line = json.loads(f.readline())
        assert line["session_id"] == "rec"
        assert line["event_type"] == "step_failure"
    print("✅ failure recording OK")


def test_compare_snapshots():
    """扫描快照对比"""
    from trace_debugger.record import compare_snapshots

    base = {
        "report_id": "old",
        "timestamp": "2026-07-01T00:00:00+00:00",
        "n_trajectories": 10,
        "distribution": {"tool_error": 2, "llm_offtrack": 6},
        "trajectories": [{"failure_types": ["tool_error"]}] * 2
        + [{"failure_types": ["llm_offtrack"]}] * 6
        + [{"failure_types": []}] * 2,
    }
    cur = {
        "report_id": "new",
        "timestamp": "2026-07-16T00:00:00+00:00",
        "n_trajectories": 10,
        "distribution": {"tool_error": 2, "llm_offtrack": 1},
        "trajectories": [{"failure_types": ["tool_error"]}] * 2
        + [{"failure_types": ["llm_offtrack"]}]
        + [{"failure_types": []}] * 7,
    }
    report = compare_snapshots(cur, base)
    assert "llm_offtrack" in report
    assert "-5" in report or "    -5" in report
    print("✅ compare snapshots OK")
