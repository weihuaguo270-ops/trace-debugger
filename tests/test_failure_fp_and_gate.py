"""False-positive regression + tool contract + failure-gate export."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from trace_debugger.analyzer import Analyzer, FailureType
from trace_debugger.evidence import evidence_chain_from_analysis
from trace_debugger.golden import (
    DEFAULT_FP_DIR,
    load_manifest,
    run_false_positive_suite,
    validate_case,
    analyze_case,
)
from trace_debugger.harness_health import evaluate_regression_gate
from trace_debugger.profiles import resolve_analyzer
from trace_debugger.reader import load
from trace_debugger.record import build_failures_export, build_scan_snapshot, distribution_rates
from trace_debugger.tool_contracts import check_tool_contract, merge_contracts


def test_false_positive_suite_passes():
    report = run_false_positive_suite()
    assert report["n_cases"] == 5
    assert report["n_failed"] == 0, report


@pytest.mark.parametrize("case_id", [c.id for c in load_manifest(str(DEFAULT_FP_DIR / "manifest.json")).cases])
def test_fp_case(case_id: str):
    manifest = load_manifest(str(DEFAULT_FP_DIR / "manifest.json"))
    case = next(c for c in manifest.cases if c.id == case_id)
    analysis = analyze_case(case, golden_dir=DEFAULT_FP_DIR)
    errors = validate_case(analysis, case)
    assert not errors, f"{case_id}: {errors}"


def test_search_weak_no_url_vs_with_url():
    """3 条无 url → search_weak；带 url → 不触发。"""
    weak = DEFAULT_FP_DIR.parent / "failure_golden" / "search_weak.json"
    ok = DEFAULT_FP_DIR / "fp_search_with_urls.json"
    az = Analyzer(search_min_results=1, search_require_url=True)
    weak_fails = {ft for pa in az.analyze(load(str(weak))).paths for ft in pa.failure_types}
    ok_fails = {ft for pa in az.analyze(load(str(ok))).paths for ft in pa.failure_types}
    assert FailureType.SEARCH_WEAK in weak_fails
    assert FailureType.SEARCH_EMPTY not in weak_fails
    assert FailureType.SEARCH_WEAK not in ok_fails
    assert FailureType.SEARCH_EMPTY not in ok_fails


def test_code_profile_skips_offtrack():
    path = DEFAULT_FP_DIR / "fp_code_snippet.json"
    default = Analyzer().analyze(load(str(path)))
    code = resolve_analyzer("code").analyze(load(str(path)))
    # default may flag offtrack; code must not
    code_fails = {ft for pa in code.paths for ft in pa.failure_types}
    assert FailureType.LLM_OFFTRACK not in code_fails
    # evidence of the point: profiles differ or both clean
    _ = default  # exercised


def test_tool_contract_missing_args():
    v = check_tool_contract(
        "web_search",
        '{"q": "weather"}',
        merge_contracts(),
    )
    assert v is not None
    assert v["rule_id"] == "tool_contract.missing_args"

    traj = load(str(DEFAULT_FP_DIR / "contract_missing_query.json"))
    analysis = Analyzer(enable_tool_contracts=True).analyze(traj)
    fails = {ft for pa in analysis.paths for ft in pa.failure_types}
    assert FailureType.TOOL_ERROR in fails
    chain = evidence_chain_from_analysis(analysis)
    assert any(e.get("rule_id", "").startswith("tool_contract.") for e in chain)


def test_evidence_on_tool_error():
    path = Path(__file__).resolve().parents[1] / "fixtures" / "failure_golden" / "tool_error.json"
    analysis = Analyzer().analyze(load(str(path)))
    chain = evidence_chain_from_analysis(analysis)
    assert chain
    assert any(e.get("failure_type") == "tool_error" for e in chain)


def test_failures_export_schema():
    path = Path(__file__).resolve().parents[1] / "fixtures" / "failure_golden"
    files = sorted(path.glob("tool_error.json"))
    trajs = [load(str(f)) for f in files]
    analyses = [Analyzer().analyze(t) for t in trajs]
    snap = build_scan_snapshot(str(path), 1, trajs, analyses, source_files=[str(f) for f in files])
    export = build_failures_export(snap)
    assert export["schema_version"] == "failure-gate/v1"
    assert export["producer"] == "trace-debugger"
    assert "distribution_rates" in export
    assert export["trajectories"][0]["evidence_chain"]


def test_gate_rule_r_rate_when_n_differs():
    """n 不对齐时规则 B 跳过，规则 R 仍可按率差触发。"""
    base = {
        "n_trajectories": 100,
        "distribution": {"tool_error": 1},
        "distribution_rates": distribution_rates({"tool_error": 1}, 100),
        "trajectories": [{"failure_types": ["tool_error"]}] + [{"failure_types": []}] * 99,
    }
    cur = {
        "n_trajectories": 10,
        "distribution": {"tool_error": 2},
        "distribution_rates": distribution_rates({"tool_error": 2}, 10),
        "trajectories": [{"failure_types": ["tool_error"]}] * 2 + [{"failure_types": []}] * 8,
    }
    gate = evaluate_regression_gate(cur, base)
    assert gate["fail_rate"]["n_aligned"] is False
    assert gate["fail_rate"]["delta_pp"] is None
    assert "R" in gate["triggered_rules"]
    assert gate["decision"] in ("review", "hold")
    assert "stability" in gate
