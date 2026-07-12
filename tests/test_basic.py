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
    from trace_debugger.reader import Trajectory

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
    from trace_debugger.reader import Trajectory

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
    print(f"✅ Analysis complete: {result.status}")


def test_analyze_with_error():
    """Test analyzing a trajectory with errors"""
    from trace_debugger import Analyzer
    from trace_debugger.reader import Trajectory

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
    print(f"✅ Error analysis complete: {result.status}")


if __name__ == "__main__":
    test_imports()
    test_parse_minimal()
    test_analyze()
    test_analyze_with_error()
    print("\n🎉 All tests passed!")
