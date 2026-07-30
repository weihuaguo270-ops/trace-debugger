"""Tests for harness_health — regression gate findings and mechanism probes."""
from trace_debugger.harness_health import (
    build_findings_report,
    evaluate_regression_gate,
    probe_project_mechanisms,
)


def _snap(dist: dict, fail_count: int, n: int = 10) -> dict:
    rows = [{"failure_types": ["x"]}] * fail_count + [{"failure_types": []}] * (n - fail_count)
    return {
        "report_id": "test",
        "timestamp": "2026-07-30T00:00:00+00:00",
        "n_trajectories": n,
        "distribution": dist,
        "trajectories": rows,
    }


def test_gate_pass():
    base = _snap({"tool_error": 2}, 2)
    cur = _snap({"tool_error": 2}, 2)
    gate = evaluate_regression_gate(cur, base)
    assert gate["decision"] == "pass"
    assert gate["findings"] == []


def test_gate_hold_rule_a():
    base = _snap({"llm_offtrack": 1}, 1)
    cur = _snap({"llm_offtrack": 4}, 4)
    gate = evaluate_regression_gate(cur, base)
    assert gate["decision"] == "hold"
    assert "A" in gate["triggered_rules"]
    assert any(f["id"].startswith("regression-distribution") for f in gate["findings"])


def test_gate_review_rule_b():
    base = _snap({}, 1)
    cur = _snap({"tool_error": 2}, 3)
    gate = evaluate_regression_gate(cur, base)
    assert gate["decision"] in ("review", "hold")
    assert gate["fail_rate"]["delta_pp"] == 20.0


def test_build_findings_report():
    base = _snap({"llm_offtrack": 6}, 6)
    cur = _snap({"llm_offtrack": 1}, 1)
    report = build_findings_report(cur, base)
    assert report["gate_decision"] == "pass"
    assert report["model"] == "agent-work-loop-v1"
    assert len(report["dimensions"]) == 5


def test_probe_project_mechanisms():
    import os

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    mechs = probe_project_mechanisms(root)
    ids = {m["id"] for m in mechs}
    assert "golden-fixtures" in ids
    assert "thresholds-doc" in ids
    golden = next(m for m in mechs if m["id"] == "golden-fixtures")
    assert golden["evidence_state"] in ("present", "wired", "missing")
