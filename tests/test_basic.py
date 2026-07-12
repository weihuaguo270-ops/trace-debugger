"""Basic tests for trace-debugger"""

import json
import os
import sys
import tempfile

# Simple trajectory for testing
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
    from trace_debugger import TraceDebugger
    assert TraceDebugger is not None
    print("✅ Imports OK")


def test_analyze_trajectory():
    """Test analyzing a simple trajectory"""
    from trace_debugger import TraceDebugger
    debugger = TraceDebugger()
    
    # Create a temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(SAMPLE_TRAJECTORY, f)
        tmp_path = f.name
    
    try:
        result = debugger.analyze(tmp_path)
        assert result is not None
        print(f"✅ Trajectory analyzed: {result}")
    finally:
        os.unlink(tmp_path)


def test_classify_failures():
    """Test failure classification"""
    from trace_debugger.failure_classifier import classify_step
    
    # A successful step
    cls = classify_step({
        "step_index": 1, "type": "action",
        "action": {"name": "web_search"},
        "content": "OK"
    })
    print(f"✅ Step classified: {cls}")


if __name__ == "__main__":
    test_imports()
    test_analyze_trajectory()
    print("\n🎉 All tests passed!")
