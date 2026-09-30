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


def test_gate_stability_block_present():
    base = _snap({"tool_error": 2}, 2)
    cur = _snap({"tool_error": 2}, 2)
    gate = evaluate_regression_gate(cur, base)
    assert gate["stability"]["n_aligned"] is True
    assert "distribution_rate_delta_pp" in gate["stability"]


def test_build_findings_includes_evidence():
    base = _snap({"llm_offtrack": 1}, 1)
    cur = _snap({"llm_offtrack": 4}, 4)
    report = build_findings_report(cur, base)
    assert report["gate_decision"] == "hold"
    assert any(f.get("evidence") for f in report["findings"])
    assert "stability" in (report.get("compare") or {})
def test_probe_project_mechanisms():
    import os

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    mechs = probe_project_mechanisms(root)
    ids = {m['id'] for m in mechs}
    assert 'golden-fixtures' in ids
    assert 'false-positive-fixtures' in ids
    assert 'thresholds-doc' in ids
    golden = next(m for m in mechs if m['id'] == 'golden-fixtures')
    assert golden['evidence_state'] in ('present', 'wired', 'missing')


def test_probe_fixture_counts_come_from_manifests():
    """探针计数必须来自 manifest，不得硬编码（回归：曾写死 27 条）。"""
    import os

    from trace_debugger.golden import DEFAULT_FP_DIR, load_manifest

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    mechs = {m['id']: m for m in probe_project_mechanisms(root)}

    golden_n = len(load_manifest().cases)
    fp_n = len(load_manifest(str(DEFAULT_FP_DIR / 'manifest.json')).cases)

    assert mechs['golden-fixtures']['case_count'] == golden_n
    assert f'{golden_n} 条' in mechs['golden-fixtures']['label']
    assert mechs['false-positive-fixtures']['case_count'] == fp_n
    assert f'{fp_n} 条' in mechs['false-positive-fixtures']['label']


def test_probe_without_manifests_degrades_gracefully(tmp_path):
    """夹具缺失时探针标 missing，不带计数、不抛异常。"""
    mechs = {m['id']: m for m in probe_project_mechanisms(str(tmp_path))}
    golden = mechs['golden-fixtures']
    assert golden['evidence_state'] == 'missing'
    assert 'case_count' not in golden
    assert golden['label'] == '失败 golden 回归集'
