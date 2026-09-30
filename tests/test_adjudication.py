"""Adjudication — blinding, scoring math, and the CLI round-trip."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from trace_debugger.adjudication import (
    SHEET_SCHEMA,
    build_key,
    build_sheet,
    format_score,
    load_jsonl,
    score_sheet,
    write_jsonl,
)
from trace_debugger.analyzer import Analyzer
from trace_debugger.reader import load

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "fixtures" / "failure_golden"

LEAK_TOKENS = ("failure_type", "analyzer_label", "needs_fix", "llm_offtrack", "tool_error", "search_empty")


def _analyze(files: list[Path]):
    analyzer = Analyzer()
    trajs = [load(str(f)) for f in files]
    return trajs, [analyzer.analyze(t) for t in trajs]


# ── blinding ──


def test_sheet_carries_no_analyzer_verdict():
    files = sorted(GOLDEN.glob("*.json"))[:6]
    trajs, analyses = _analyze(files)
    src = [str(f) for f in files]
    sheet = build_sheet(analyses, trajs, src)
    assert sheet
    for row in sheet:
        assert row["human_label"] == []
        blob = json.dumps(row, ensure_ascii=False)
        for leaked in LEAK_TOKENS:
            assert leaked not in blob, f"{leaked} leaked into the blind sheet"

    key = build_key(analyses, src)
    assert len(key) == len(sheet)
    assert any(row["analyzer_label"] for row in key), "key must hold the analyzer verdicts"


def test_sheet_carries_the_evidence_a_human_needs():
    files = [GOLDEN / "tool_error.json"]
    trajs, analyses = _analyze(files)
    row = build_sheet(analyses, trajs, [str(files[0])])[0]
    assert row["query"]
    assert row["steps"]
    assert row["steps"][0]["action"]
    assert any(step["observation"] or step["error"] for step in row["steps"])


# ── scoring ──


def test_score_perfect_agreement():
    files = [GOLDEN / "tool_error.json", GOLDEN / "pass_clean.json"]
    trajs, analyses = _analyze(files)
    src = [str(f) for f in files]
    key = build_key(analyses, src)
    sheet = build_sheet(analyses, trajs, src)
    for row, expected in zip(sheet, key):
        row["human_label"] = list(expected["analyzer_label"])
        row["human_note"] = "reviewed"
    report = score_sheet(sheet, key)
    assert report["n_labeled"] == 2
    assert report["exact_match_rate"] == 1.0
    assert report["case_verdict_agreement"] == 1.0
    assert report["disagreements"] == []


def test_score_flags_analyzer_false_positive():
    sheet = [
        {"case_id": "a", "human_label": [], "human_note": "答对了"},
        {"case_id": "b", "human_label": ["tool_error"], "human_note": "工具确实报错"},
    ]
    key = [
        {"case_id": "a", "analyzer_label": ["llm_offtrack"]},
        {"case_id": "b", "analyzer_label": ["tool_error"]},
    ]
    report = score_sheet(sheet, key)
    assert report["exact_match_rate"] == 0.5
    assert report["case_verdict_agreement"] == 0.5
    assert report["per_type"]["llm_offtrack"] == {
        "tp": 0, "fp": 1, "fn": 0, "precision": 0.0, "recall": None,
    }
    assert report["per_type"]["tool_error"]["precision"] == 1.0
    assert {d["kind"] for d in report["disagreements"]} == {"analyzer_false_positive"}


def test_score_flags_analyzer_miss():
    sheet = [{"case_id": "a", "human_label": ["search_empty"], "human_note": "检索确实为空"}]
    key = [{"case_id": "a", "analyzer_label": []}]
    report = score_sheet(sheet, key)
    assert report["per_type"]["search_empty"]["fn"] == 1
    assert report["per_type"]["search_empty"]["recall"] == 0.0
    assert report["disagreements"][0]["kind"] == "analyzer_miss"


def test_label_accepts_comma_string():
    sheet = [{"case_id": "a", "human_label": "tool_error, search_empty"}]
    key = [{"case_id": "a", "analyzer_label": ["tool_error", "search_empty"]}]
    report = score_sheet(sheet, key)
    assert report["exact_match_rate"] == 1.0


def test_unlabeled_cases_are_counted_and_warned():
    sheet = [{"case_id": "a", "human_label": []}, {"case_id": "b", "human_label": ["tool_error"]}]
    key = [
        {"case_id": "a", "analyzer_label": []},
        {"case_id": "b", "analyzer_label": ["tool_error"]},
    ]
    report = score_sheet(sheet, key)
    assert report["n_unlabeled"] == 1
    assert "a" in report["unlabeled_cases"]
    assert report["n_labeled"] == 1

    empty = score_sheet([{"case_id": "z", "human_label": []}], [{"case_id": "z", "analyzer_label": ["tool_error"]}])
    assert "尚无人工标注" in format_score(empty)


# ── CLI round-trip ──


def _run_tdebug(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "trace_debugger", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def test_cli_adjudicate_roundtrip(tmp_path):
    sheet_path = tmp_path / "sheet.jsonl"
    key_path = tmp_path / "key.jsonl"
    report_path = tmp_path / "report.json"

    proc = _run_tdebug([
        "adjudicate", str(GOLDEN), "5",
        "--sheet-out", str(sheet_path), "--key-out", str(key_path),
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert sheet_path.exists() and key_path.exists()

    # Blind: the sheet must not contain any analyzer verdict.
    raw = sheet_path.read_text(encoding="utf-8")
    for leaked in LEAK_TOKENS:
        assert leaked not in raw

    # Unlabeled → scoring refuses to invent a number.
    proc2 = _run_tdebug([
        "adjudicate", "--score", "--sheet", str(sheet_path), "--key", str(key_path),
    ])
    assert proc2.returncode == 0, proc2.stdout + proc2.stderr
    assert "尚无人工标注" in proc2.stdout

    # Simulate a human filling the sheet, then score.
    key_rows = load_jsonl(str(key_path))
    sheet_rows = load_jsonl(str(sheet_path))
    for row in sheet_rows:
        match = next(k for k in key_rows if k["case_id"] == row["case_id"])
        row["human_label"] = list(match["analyzer_label"])
        row["human_note"] = "simulated"
    write_jsonl(str(sheet_path), sheet_rows, schema=SHEET_SCHEMA)

    proc3 = _run_tdebug([
        "adjudicate", "--score", "--sheet", str(sheet_path), "--key", str(key_path),
        "--json-out", str(report_path),
    ])
    assert proc3.returncode == 0, proc3.stdout + proc3.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["exact_match_rate"] == 1.0
    assert report["n_labeled"] == report["n_cases"]


def test_cli_score_requires_sheet_and_key():
    proc = _run_tdebug(["adjudicate", "--score"])
    assert proc.returncode == 1
    assert "--sheet" in (proc.stdout + proc.stderr)
