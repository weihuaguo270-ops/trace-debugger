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
                "step": 0,
                "thought": "I should search for this",
                "action": {"name": "web_search", "args": {"query": "Python"}},
                "observation": "Python is a programming language",
            },
            {
                "step": 1,
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
                "step": 0,
                "thought": "Let me search for machine learning",
                "action": {"name": "web_search", "args": {"query": "machine learning"}},
                "observation": "Machine learning is a subset of AI",
            },
            {
                "step": 1,
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
                "step": 0,
                "thought": "Let me execute Python code",
                "action": {"name": "execute_python", "args": {"code": "print(1/0)"}},
                "observation": "Error: division by zero",
            },
            {
                "step": 1,
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
                "step": 0,
                "thought": "search",
                "action": {"name": "web_search", "args": {"query": "AI"}},
                "observation": "result about AI industry trends and markets " * 3,
            },
            {
                "step": 1,
                "thought": "search again",
                "action": {"name": "web_search", "args": {"query": "AI"}},
                "observation": "result about AI industry trends and markets " * 3,
            },
            {
                "step": 2,
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
                "step": 0,
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
                "step": 0,
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
                "step": 0,
                "thought": "read",
                "action": {"name": "fetch_page", "args": {"url": "x"}},
                "observation": "Error: maximum context length exceeded for this model",
                "tokens_estimated": 100,
            },
            {
                "step": 1,
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


if __name__ == "__main__":
    test_imports()
    test_parse_minimal()
    test_analyze()
    test_analyze_with_error()
    test_detect_duplicate_and_no_answer()
    test_detect_offtrack_and_overflow()
    test_sample_trajectory_not_false_offtrack()
    print("\n🎉 All tests passed!")
