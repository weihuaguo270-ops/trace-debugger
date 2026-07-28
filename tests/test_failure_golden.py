"""Golden failure set — evidence chain regression tests."""
from __future__ import annotations

import json

import pytest

from trace_debugger.golden import (
    DEFAULT_GOLDEN_DIR,
    load_manifest,
    run_golden_suite,
    validate_case,
    analyze_case,
)
from trace_debugger.runtime import StepWatcher


def test_manifest_has_27_cases():
    manifest = load_manifest()
    assert len(manifest.cases) == 27
    assert {c.split for c in manifest.cases} == {"golden", "held_out"}
    assert sum(1 for c in manifest.cases if c.split == "golden") == 21
    assert sum(1 for c in manifest.cases if c.split == "held_out") == 6


@pytest.mark.parametrize("case_id", [c.id for c in load_manifest().cases])
def test_golden_case_detection(case_id: str):
    case = next(c for c in load_manifest().cases if c.id == case_id)
    analysis = analyze_case(case)
    errors = validate_case(analysis, case)
    assert not errors, f"{case_id}: {errors}"


def test_golden_suite_all_pass():
    report = run_golden_suite()
    assert report["n_failed"] == 0, report
    assert report["pass_rate"] == 1.0


def test_taxonomy_coverage():
    covered: set[str] = set()
    for case in load_manifest().cases:
        if case.category == "negative":
            covered.update(case.expected_failures)
    required = {
        "tool_error", "search_empty", "search_timeout", "duplicate",
        "no_answer", "llm_offtrack", "context_overflow",
    }
    assert required <= covered


_SKIP_WATCHER_REPLAY = {"golden_multi_paths", "golden_path_id_branch"}


@pytest.mark.parametrize(
    "case_id",
    [
        c.id for c in load_manifest().cases
        if c.expected_step_failures and c.id not in _SKIP_WATCHER_REPLAY
    ],
)
def test_step_watcher_replay(case_id: str, tmp_path):
    case = next(c for c in load_manifest().cases if c.id == case_id)
    data = json.loads((DEFAULT_GOLDEN_DIR / case.file).read_text(encoding="utf-8"))
    record_path = str(tmp_path / f"{case_id}.jsonl")

    watcher = StepWatcher(
        session_id=data.get("session_id", case_id),
        query=data.get("query", ""),
        model=data.get("model", "mock"),
        record_path=record_path,
    )

    for raw in data.get("steps") or []:
        action = raw.get("action") or {}
        watcher.on_step(
            step_index=raw["step"],
            thought=raw.get("thought", ""),
            action_name=action.get("name", ""),
            action_args=action.get("arguments", ""),
            observation=raw.get("observation", ""),
            duration=float(raw.get("duration_seconds") or 0),
            tokens=int(raw.get("tokens_estimated") or 0),
        )

    analysis = watcher.on_finish(
        final_answer=data.get("final_answer", ""),
        total_duration=float(data.get("total_duration_seconds") or 0),
        metadata={"total_tokens_estimated": data.get("total_tokens_estimated", 0)},
    )
    errors = validate_case(analysis, case)
    assert not errors, f"StepWatcher replay {case_id}: {errors}"
