"""Basic tests for trace-debugger"""

import json
import os
import sys
import tempfile

SAMPLE_TRAJECTORY = {
    "session_id": "test_001",
    "query": "What is Python?",
    "steps": [
        {"step_index": 0, "type": "thought", "content": "I should search for this"},
        {"step_index": 1, "type": "action",
         "action": {"name": "web_search", "args": {"query": "Python"}},
         "content": "Searching..."},
        {"step_index": 2, "type": "observation",
         "content": "Python is a programming language",
         "observation": "Python is a programming language"},
        {"step_index": 3, "type": "thought", "content": "I have enough info"},
        {"step_index": 4, "type": "final",
         "content": "Python is a programming language created by Guido van Rossum"},
    ]
}


def test_imports():
    """Verify package imports work"""
    from trace_debugger import Analyzer, Trajectory
    from trace_debugger.reader import Step, Path
    assert Analyzer is not None
    assert Trajectory is not None
    print("✅ Package imports OK")


def test_analyze_trajectory():
    """Test analyzing a simple trajectory"""
    from trace_debugger import Analyzer
    
    analyzer = Analyzer()
    result = analyzer.analyze(SAMPLE_TRAJECTORY)
    assert result is not None
    assert result.summary is not None
    print(f"✅ Trajectory analyzed: {result.status}")


def test_reporter():
    """Test reporter output"""
    from trace_debugger import Analyzer, format_report
    
    analyzer = Analyzer()
    result = analyzer.analyze(SAMPLE_TRAJECTORY)
    report = format_report(result)
    assert len(report) > 0
    print(f"✅ Report generated ({len(report)} chars)")


if __name__ == "__main__":
    test_imports()
    test_analyze_trajectory()
    test_reporter()
    print("\n🎉 All tests passed!")
