"""--fail-on gate exit behavior."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from trace_debugger.harness_health import should_fail_on_gate


ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "fixtures" / "failure_golden"


@pytest.mark.parametrize(
    "decision,fail_on,expect",
    [
        ("pass", "hold", False),
        ("review", "hold", False),
        ("hold", "hold", True),
        ("pass", "review", False),
        ("review", "review", True),
        ("hold", "review", True),
        ("pass", "pass", True),
        ("review", "pass", True),
    ],
)
def test_should_fail_on_gate(decision, fail_on, expect):
    assert should_fail_on_gate(decision, fail_on) is expect


def test_should_fail_on_gate_invalid():
    with pytest.raises(ValueError, match="fail_on"):
        should_fail_on_gate("pass", "warn")


def _run_tdebug(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "trace_debugger", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def test_cli_fail_on_requires_compare():
    proc = _run_tdebug(["scan", str(GOLDEN), "3", "--fail-on", "hold"])
    assert proc.returncode == 1
    assert "--compare" in (proc.stdout + proc.stderr)


def test_cli_fail_on_hold_pass_when_unchanged(tmp_path: Path):
    baseline = tmp_path / "baseline.json"
    # Build baseline snapshot
    proc1 = _run_tdebug([
        "scan", str(GOLDEN), "5",
        "--json-out", str(baseline),
    ])
    assert proc1.returncode == 0, proc1.stdout + proc1.stderr
    assert baseline.exists()

    proc2 = _run_tdebug([
        "scan", str(GOLDEN), "5",
        "--compare", str(baseline),
        "--fail-on", "hold",
    ])
    assert proc2.returncode == 0, proc2.stdout + proc2.stderr
    assert "未达阈值" in proc2.stdout or "PASS" in proc2.stdout


def test_cli_fail_on_hold_exits_when_regressed(tmp_path: Path):
    baseline = {
        "report_id": "base",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "n_trajectories": 5,
        "distribution": {"tool_error": 0},
        "distribution_rates": {"tool_error": 0.0},
        "trajectories": [{"failure_types": []} for _ in range(5)],
    }
    base_path = tmp_path / "clean_baseline.json"
    base_path.write_text(json.dumps(baseline), encoding="utf-8")

    # Golden set includes tool_error etc. → distribution rises vs empty baseline
    proc = _run_tdebug([
        "scan", str(GOLDEN), "10",
        "--compare", str(base_path),
        "--fail-on", "hold",
    ])
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "fail-on" in proc.stdout.lower() or "HOLD" in proc.stdout
