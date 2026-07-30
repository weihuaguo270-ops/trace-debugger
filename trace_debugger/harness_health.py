"""Harness health — Agent Work Loop evidence states, regression findings, mechanism probes.

Inspired by Better Harness (QoderAI/better-harness) evidence model; grounded in
trace-debugger's deterministic scan/compare gates (THRESHOLDS v1).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

EvidenceState = Literal[
    "present",
    "wired",
    "exercised",
    "outcome_supported",
    "missing",
    "unobserved",
    "not_applicable",
]

GateDecision = Literal["pass", "review", "hold"]

DIMENSIONS: dict[str, str] = {
    "task-understanding": "Task Understanding",
    "controlled-execution": "Controlled Execution",
    "change-validation": "Change Validation",
    "reliable-delivery": "Reliable Delivery",
    "learning-capture": "Learning Capture",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fail_session_stats(snapshot: dict[str, Any]) -> tuple[int, int, float]:
    rows = snapshot.get("trajectories") or []
    n = snapshot.get("n_trajectories") or len(rows) or 0
    fail = sum(1 for r in rows if r.get("failure_types"))
    rate = (fail / n * 100.0) if n else 0.0
    return fail, n, rate


def evaluate_regression_gate(
    current: dict[str, Any],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    """Apply THRESHOLDS v1 rules A/B; return decision + triggered rules + findings."""
    cur_dist = current.get("distribution") or {}
    base_dist = baseline.get("distribution") or {}
    all_types = sorted(set(cur_dist) | set(base_dist))

    triggered: list[str] = []
    findings: list[dict[str, Any]] = []
    decision: GateDecision = "pass"

    for ft in all_types:
        b = base_dist.get(ft, 0)
        c = cur_dist.get(ft, 0)
        delta = c - b
        if delta >= 2:
            triggered.append("A")
            findings.append(_finding_distribution(
                ft, b, c, delta, severity="high", gate="hold",
            ))
            decision = "hold"
        elif delta == 1:
            triggered.append("A-notice")
            findings.append(_finding_distribution(
                ft, b, c, delta, severity="medium", gate="review",
            ))
            if decision == "pass":
                decision = "review"

    _, cur_n, cur_rate = _fail_session_stats(current)
    _, base_n, base_rate = _fail_session_stats(baseline)
    delta_pp = cur_rate - base_rate if cur_n == base_n else None

    if delta_pp is not None:
        if delta_pp >= 10:
            triggered.append("B")
            findings.append(_finding_fail_rate(
                base_rate, cur_rate, delta_pp, severity="high", gate="hold",
            ))
            decision = "hold"
        elif delta_pp >= 5:
            triggered.append("B")
            findings.append(_finding_fail_rate(
                base_rate, cur_rate, delta_pp, severity="medium", gate="review",
            ))
            if decision == "pass":
                decision = "review"

    return {
        "decision": decision,
        "triggered_rules": sorted(set(triggered)),
        "fail_rate": {
            "baseline_pct": round(base_rate, 2),
            "current_pct": round(cur_rate, 2),
            "delta_pp": round(delta_pp, 2) if delta_pp is not None else None,
            "n_aligned": cur_n == base_n,
        },
        "distribution_delta": {
            ft: cur_dist.get(ft, 0) - base_dist.get(ft, 0) for ft in all_types
        },
        "findings": findings,
    }


def _finding_distribution(
    ft: str,
    base: int,
    cur: int,
    delta: int,
    *,
    severity: str,
    gate: GateDecision,
) -> dict[str, Any]:
    return {
        "id": f"regression-distribution-{ft}",
        "dimension": "change-validation",
        "severity": severity,
        "gate": gate,
        "title": f"失败类型 {ft} 计数上升 {delta:+d}",
        "evidence_state": "exercised",
        "detail": f"distribution[{ft}]: {base} → {cur} ({delta:+d})",
        "impact": "回归门禁规则 A：单类型计数异常上升",
        "repair_boundary": "trace-debugger/analyzer 或 react-agent prompt/工具",
        "validation_route": "tdebug scan --compare + golden 27/27 + METRICS_LOG",
    }


def _finding_fail_rate(
    base_rate: float,
    cur_rate: float,
    delta_pp: float,
    *,
    severity: str,
    gate: GateDecision,
) -> dict[str, Any]:
    return {
        "id": "regression-fail-rate",
        "dimension": "reliable-delivery",
        "severity": severity,
        "gate": gate,
        "title": f"含失败 session 占比上升 {delta_pp:+.1f}pp",
        "evidence_state": "exercised",
        "detail": f"fail_rate: {base_rate:.1f}% → {cur_rate:.1f}% ({delta_pp:+.1f}pp)",
        "impact": "回归门禁规则 B：含失败轨迹占比显著上升",
        "repair_boundary": "发版前 prompt/工具/analyzer 变更",
        "validation_route": "重扫 pilot N=100 对齐 baseline 后 compare",
    }


def probe_project_mechanisms(project_root: str) -> list[dict[str, Any]]:
    """Static probe: Present / Wired for known harness mechanisms (no session inference)."""
    root = Path(project_root)
    checks: list[dict[str, Any]] = []

    def _add(
        mechanism_id: str,
        dimension: str,
        label: str,
        path: str,
        *,
        wired_hint: Optional[str] = None,
    ) -> None:
        full = root / path
        exists = full.exists()
        state: EvidenceState = "present" if exists else "missing"
        wired = False
        if exists and wired_hint:
            wired = (root / wired_hint).exists()
            if wired:
                state = "wired"
        checks.append({
            "id": mechanism_id,
            "dimension": dimension,
            "label": label,
            "path": path,
            "evidence_state": state,
            "wired": wired,
        })

    _add(
        "golden-fixtures",
        "change-validation",
        "失败 golden 27 条",
        "fixtures/failure_golden/manifest.json",
        wired_hint=".github/workflows/test.yml",
    )
    _add(
        "pilot-baseline",
        "reliable-delivery",
        "试点 baseline 快照",
        "docs/snapshots/pilot_baseline.json",
    )
    _add(
        "thresholds-doc",
        "reliable-delivery",
        "回归门禁阈值 THRESHOLDS v1",
        "docs/pilot/THRESHOLDS.md",
    )
    _add(
        "intervention-ledger",
        "learning-capture",
        "干预 ledger（纵向验证）",
        "docs/intervention_ledger.json",
    )
    _add(
        "capability-manifest",
        "task-understanding",
        "能力/回归分离 manifest",
        "docs/pilot/capability_manifest.json",
    )
    return checks


def summarize_dimensions(
    mechanisms: list[dict[str, Any]],
    gate: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """Aggregate mechanism evidence states per Agent Work Loop dimension."""
    summary: dict[str, dict[str, Any]] = {}
    for dim_id, dim_label in DIMENSIONS.items():
        summary[dim_id] = {
            "id": dim_id,
            "label": dim_label,
            "evidence_state": "unobserved",
            "mechanism_count": 0,
            "findings_count": 0,
        }

    state_rank = {
        "missing": 0,
        "unobserved": 1,
        "present": 2,
        "wired": 3,
        "exercised": 4,
        "outcome_supported": 5,
        "not_applicable": -1,
    }

    for m in mechanisms:
        dim = m.get("dimension", "")
        if dim not in summary:
            continue
        summary[dim]["mechanism_count"] += 1
        st = m.get("evidence_state", "unobserved")
        cur = summary[dim]["evidence_state"]
        if state_rank.get(st, 0) > state_rank.get(cur, 0):
            summary[dim]["evidence_state"] = st

    if gate:
        for f in gate.get("findings") or []:
            dim = f.get("dimension", "")
            if dim in summary:
                summary[dim]["findings_count"] += 1
                summary[dim]["evidence_state"] = "exercised"

    return list(summary.values())


def build_findings_report(
    current: dict[str, Any],
    baseline: Optional[dict[str, Any]] = None,
    *,
    project_root: Optional[str] = None,
) -> dict[str, Any]:
    """Build structured findings.json from scan snapshot + optional baseline compare."""
    gate = evaluate_regression_gate(current, baseline) if baseline else None
    mechanisms: list[dict[str, Any]] = []
    if project_root and os.path.isdir(project_root):
        mechanisms = probe_project_mechanisms(project_root)

    findings = list(gate["findings"]) if gate else []
    report: dict[str, Any] = {
        "report_id": f"harness_health_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "timestamp": _utc_now(),
        "model": "agent-work-loop-v1",
        "gate_decision": gate["decision"] if gate else "pass",
        "dimensions": summarize_dimensions(mechanisms, gate),
        "findings": findings,
        "mechanisms": mechanisms,
        "scan": {
            "report_id": current.get("report_id"),
            "timestamp": current.get("timestamp"),
            "n_trajectories": current.get("n_trajectories"),
            "distribution": current.get("distribution"),
        },
    }
    if baseline:
        report["compare"] = {
            "baseline_report_id": baseline.get("report_id"),
            "baseline_timestamp": baseline.get("timestamp"),
            "triggered_rules": gate["triggered_rules"] if gate else [],
            "fail_rate": gate["fail_rate"] if gate else {},
            "distribution_delta": gate["distribution_delta"] if gate else {},
        }
    return report
