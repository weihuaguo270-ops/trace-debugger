"""golden — 黄金失败集加载与断言（证据链）"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .analyzer import Analyzer, TrajectoryAnalysis
from .profiles import resolve_analyzer
from .reader import load, parse

DEFAULT_GOLDEN_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "failure_golden"
DEFAULT_FP_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "failure_fp"


@dataclass
class GoldenCase:
    """一个轨迹夹具及其必须命中、不得命中的失败断言。"""

    id: str
    file: str
    split: str
    category: str
    expected_failures: list[str]
    must_not_detect: list[str] = field(default_factory=list)
    expected_step_failures: list[dict[str, Any]] = field(default_factory=list)
    notes: str = ""
    task_type: str = "default"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GoldenCase":
        """从 manifest 条目构建用例，缺省值保持旧清单兼容。"""
        return cls(
            id=data["id"],
            file=data["file"],
            split=data.get("split", "golden"),
            category=data.get("category", "negative"),
            expected_failures=list(data.get("expected_failures") or []),
            must_not_detect=list(data.get("must_not_detect") or []),
            expected_step_failures=list(data.get("expected_step_failures") or []),
            notes=data.get("notes", ""),
            task_type=data.get("task_type") or "default",
        )


@dataclass
class GoldenManifest:
    """带 schema 版本的失败回归集清单。"""

    schema_version: str
    description: str
    cases: list[GoldenCase]

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "GoldenManifest":
        """从指定路径或内置夹具目录加载清单。"""
        root = path or (DEFAULT_GOLDEN_DIR / "manifest.json")
        with open(root, encoding="utf-8") as f:
            data = json.load(f)
        return cls(
            schema_version=str(data.get("schema_version", "1")),
            description=data.get("description", ""),
            cases=[GoldenCase.from_dict(c) for c in data.get("cases") or []],
        )


def load_manifest(manifest_path: Optional[str] = None) -> GoldenManifest:
    """加载默认或显式指定的 Golden 清单。"""
    path = Path(manifest_path) if manifest_path else DEFAULT_GOLDEN_DIR / "manifest.json"
    return GoldenManifest.load(path)


def analyze_case(case: GoldenCase, *, golden_dir: Optional[Path] = None) -> TrajectoryAnalysis:
    """加载一个 Golden 轨迹并运行对应 task_type 分析器。"""
    base = golden_dir or DEFAULT_GOLDEN_DIR
    analyzer = resolve_analyzer(case.task_type)
    return analyzer.analyze(load(str(base / case.file)))


def validate_case(analysis: TrajectoryAnalysis, case: GoldenCase) -> list[str]:
    """返回断言失败信息（空列表 = 通过）。"""
    detected: set[str] = set()
    for pa in analysis.paths:
        detected.update(pa.failure_types)

    expected = set(case.expected_failures)
    must_not = set(case.must_not_detect)
    errors: list[str] = []

    # false_positive cases: only enforce must_not (+ optional exact expected if set)
    if case.category == "false_positive":
        forbidden = detected & must_not
        if forbidden:
            errors.append(f"forbidden failures detected: {sorted(forbidden)}")
        if expected and detected != expected:
            missing = expected - detected
            extra = detected - expected
            if missing:
                errors.append(f"missing failures: {sorted(missing)}")
            if extra:
                errors.append(f"unexpected failures: {sorted(extra)}")
        return errors

    if detected != expected:
        missing = expected - detected
        extra = detected - expected
        if missing:
            errors.append(f"missing failures: {sorted(missing)}")
        if extra:
            errors.append(f"unexpected failures: {sorted(extra)}")

    forbidden = detected & must_not
    if forbidden:
        errors.append(f"forbidden failures detected: {sorted(forbidden)}")

    for spec in case.expected_step_failures:
        step_idx = int(spec["step"])
        ftype = spec["type"]
        path_idx = int(spec.get("path", 0))
        found = False
        for pa in analysis.paths:
            if pa.path_index != path_idx:
                continue
            for sa in pa.step_analyses:
                if sa.step_index == step_idx and sa.failure_type == ftype:
                    found = True
                    break
        if not found:
            errors.append(
                f"missing step failure {ftype!r} at path={path_idx} step={step_idx}"
            )

    return errors


def run_golden_suite(
    *,
    manifest_path: Optional[str] = None,
    split: Optional[str] = None,
    analyzer: Optional[Analyzer] = None,
) -> dict[str, Any]:
    """运行黄金集并返回证据报告结构。"""
    manifest = load_manifest(manifest_path)
    golden_dir = Path(manifest_path).parent if manifest_path else DEFAULT_GOLDEN_DIR

    rows = []
    passed = 0
    failed = 0
    for case in manifest.cases:
        if split and case.split != split:
            continue
        traj = load(str(golden_dir / case.file))
        _analyzer = analyzer or resolve_analyzer(case.task_type)
        analysis = _analyzer.analyze(traj)
        errors = validate_case(analysis, case)
        ok = not errors
        if ok:
            passed += 1
        else:
            failed += 1
        detected = sorted({ft for pa in analysis.paths for ft in pa.failure_types})
        rows.append({
            "id": case.id,
            "file": case.file,
            "split": case.split,
            "category": case.category,
            "task_type": case.task_type,
            "expected_failures": case.expected_failures,
            "detected_failures": detected,
            "pass": ok,
            "errors": errors,
            "assessment": analysis.overall_assessment,
            "notes": case.notes,
        })

    total = passed + failed
    return {
        "schema_version": manifest.schema_version,
        "description": manifest.description,
        "n_cases": total,
        "n_passed": passed,
        "n_failed": failed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "cases": rows,
    }


def run_false_positive_suite(
    *,
    manifest_path: Optional[str] = None,
) -> dict[str, Any]:
    """Run fixtures/failure_fp — assert historical FPs stay clean."""
    path = Path(manifest_path) if manifest_path else DEFAULT_FP_DIR / "manifest.json"
    return run_golden_suite(manifest_path=str(path))
