"""Findings verification — every actionable finding must carry a resolvable regression lock."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from trace_debugger.harness_health import build_findings_report
from trace_debugger.verification import (
    build_verification_ref,
    fixture_coverage,
    known_case_ids,
    validate_findings_report,
)

ROOT = Path(__file__).resolve().parents[1]

COVERED_TYPES = [
    "tool_error",
    "approval_denied",
    "search_empty",
    "search_weak",
    "search_timeout",
    "duplicate",
    "no_answer",
    "llm_offtrack",
    "context_overflow",
    "acceptance_failed",
    "incomplete_stream",
]


def _snap(dist: dict, fail_count: int, n: int = 10) -> dict:
    rows = [{"failure_types": ["x"]}] * fail_count + [{"failure_types": []}] * (n - fail_count)
    return {
        "report_id": "test",
        "timestamp": "2026-07-30T00:00:00+00:00",
        "n_trajectories": n,
        "distribution": dist,
        "trajectories": rows,
    }


# ── coverage source of truth ──


def test_coverage_comes_from_manifests():
    """回归锁来自 manifest，不是硬编码。"""
    cov = fixture_coverage("tool_error")
    assert "golden_tool_error" in cov["must_detect"]
    assert cov["must_stay_clean"]
    assert set(cov["must_detect"]) <= known_case_ids()


@pytest.mark.parametrize("failure_type", COVERED_TYPES)
def test_covered_type_finding_is_verified(failure_type):
    report = build_findings_report(_snap({failure_type: 3}, 3), _snap({}, 0))
    assert report["gate_decision"] == "hold"
    assert validate_findings_report(report, project_root=str(ROOT)) == []
    for finding in report["findings"]:
        assert finding["verification_ref"]["verified"] is True
        assert finding["verification_ref"]["tests"]


def test_uncovered_type_is_reported_unverified():
    """无夹具覆盖的类型（如 unknown）：finding 照样产出，但明确标记不可验证。"""
    report = build_findings_report(_snap({"unknown": 3}, 3), _snap({}, 0))
    by_id = {f["id"]: f for f in report["findings"]}
    ref = by_id["regression-distribution-unknown"]["verification_ref"]
    assert ref["verified"] is False
    assert ref["failure_type"] == "unknown"
    problems = validate_findings_report(report, project_root=str(ROOT))
    assert any("unknown" in p for p in problems)


def test_suite_scope_ref_needs_no_fixture():
    ref = build_verification_ref(None)
    assert ref["scope"] == "suite" and ref["verified"] is True
    report = {"findings": [{"id": "regression-fail-rate", "verification_ref": ref}]}
    assert validate_findings_report(report, project_root=str(ROOT)) == []


# ── the validator must actually refuse ──


def test_missing_ref_is_rejected():
    problems = validate_findings_report({"findings": [{"id": "x", "gate": "hold", "title": "t"}]})
    assert problems and "missing verification_ref" in problems[0]


def test_unknown_fixture_id_is_rejected():
    ref = build_verification_ref("tool_error")
    ref["fixtures"]["must_detect"] = ["does_not_exist"]
    problems = validate_findings_report({"findings": [{"id": "x", "verification_ref": ref}]})
    assert any("does_not_exist" in p for p in problems)


def test_missing_test_file_is_rejected(tmp_path):
    ref = build_verification_ref("tool_error")
    problems = validate_findings_report(
        {"findings": [{"id": "x", "verification_ref": ref}]},
        project_root=str(tmp_path),
    )
    assert any("missing test file" in p for p in problems)


# ── CLI wiring (end to end) ──


def _run_tdebug(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "trace_debugger", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _write_acceptance_trajs(directory: Path, n: int = 3) -> None:
    """acceptance_failed 目前没有 gold fixture —— 正好用来验证拒绝路径。"""
    for i in range(n):
        traj = {
            "session_id": f"acc_{i}",
            "query": "run acceptance tests",
            "model": "mock",
            "steps": [
                {
                    "step": 1,
                    "thought": "run acceptance tests",
                    "action": {"name": "run_acceptance_tests", "args": {}},
                    "observation": "failed",
                },
                {"step": 2, "thought": "FINAL ANSWER: failed", "observation": ""},
            ],
            "final_answer": "failed",
        }
        (directory / f"acc_{i}.json").write_text(json.dumps(traj, ensure_ascii=False), encoding="utf-8")


def _clean_baseline(tmp_path: Path, n: int = 3) -> Path:
    baseline = {
        "report_id": "base",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "n_trajectories": n,
        "distribution": {"acceptance_failed": 0},
        "distribution_rates": {"acceptance_failed": 0.0},
        "trajectories": [{"failure_types": []} for _ in range(n)],
    }
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(baseline), encoding="utf-8")
    return path


def test_cli_acceptance_regression_is_now_verifiable(tmp_path):
    """T1 暴露的缺口已闭合：acceptance_failed 回归现在带回归锁。"""
    trajs = tmp_path / "trajs"
    trajs.mkdir()
    _write_acceptance_trajs(trajs)

    findings_path = tmp_path / "findings.json"
    proc = _run_tdebug([
        "scan", str(trajs), "10",
        "--compare", str(_clean_baseline(tmp_path)),
        "--findings-out", str(findings_path),
        "--require-verification",
        "--project-root", str(ROOT),
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr

    findings = json.loads(findings_path.read_text(encoding="utf-8"))
    assert findings["gate_decision"] == "hold"
    assert findings["findings"]
    for finding in findings["findings"]:
        assert finding["verification_ref"]["verified"] is True
    acceptance = next(f for f in findings["findings"] if f.get("failure_type") == "acceptance_failed")
    assert "golden_acceptance_failed" in acceptance["verification_ref"]["fixtures"]["must_detect"]


def test_cli_require_verification_rejects_when_lock_tests_missing(tmp_path):
    """端到端：回归锁无法执行（lock 测试不在 project-root 下）必须让门禁红。"""
    trajs = tmp_path / "trajs"
    trajs.mkdir()
    _write_acceptance_trajs(trajs)

    proc = _run_tdebug([
        "scan", str(trajs), "10",
        "--compare", str(_clean_baseline(tmp_path)),
        "--findings-out", str(tmp_path / "findings.json"),
        "--require-verification",
        "--project-root", str(tmp_path / "no-lock-here"),
    ])
    assert proc.returncode == 1, proc.stdout + proc.stderr
    out = proc.stdout + proc.stderr
    assert "missing test file" in out
    assert "require-verification" in out


def test_cli_require_verification_requires_findings_out():
    proc = _run_tdebug([
        "scan", str(ROOT / "fixtures" / "failure_golden"), "3",
        "--require-verification",
    ])
    assert proc.returncode == 1
    assert "--findings-out" in (proc.stdout + proc.stderr)


def test_cli_require_verification_passes_without_regression(tmp_path):
    """同数据 compare → 无 finding → 验证通过。"""
    baseline = tmp_path / "baseline.json"
    proc1 = _run_tdebug([
        "scan", str(ROOT / "fixtures" / "failure_golden"), "5",
        "--json-out", str(baseline),
    ])
    assert proc1.returncode == 0, proc1.stdout + proc1.stderr

    proc2 = _run_tdebug([
        "scan", str(ROOT / "fixtures" / "failure_golden"), "5",
        "--compare", str(baseline),
        "--findings-out", str(tmp_path / "findings.json"),
        "--require-verification",
        "--project-root", str(ROOT),
    ])
    assert proc2.returncode == 0, proc2.stdout + proc2.stderr
    assert "均有可解析的回归锁" in proc2.stdout
