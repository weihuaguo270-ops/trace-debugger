"""adjudication — blind human labeling sheet + analyzer agreement scoring.

The analyzer cannot measure whether the analyzer is right. This module turns a scan
into a sheet where a human judges each case **from the trajectory evidence alone**,
while the analyzer's verdict lives in a separate key file. Scoring the two yields
per-type precision/recall and a root-cause correctness rate.

Blinding matters: showing the analyzer's label anchors the annotator, which converts
a measurement into a confirmation.

Output contains raw query / observation text — keep sheets out of git (``.tdebug/``
is already ignored) and follow ``SECURITY.md`` for anything shared.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Optional

SHEET_SCHEMA = "adjudication-sheet/v1"
KEY_SCHEMA = "adjudication-key/v1"

MAX_QUERY_CHARS = 300
MAX_ANSWER_CHARS = 500
MAX_OBS_CHARS = 400
MAX_STEPS = 40


def _excerpt(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + "…"


def _raw_steps(trajectory: Any) -> list[dict[str, Any]]:
    """Excerpt every step of a raw trajectory for human reading."""
    rows: list[dict[str, Any]] = []
    for step in (getattr(trajectory, "steps", None) or [])[:MAX_STEPS]:
        rows.append({
            "step": step.index,
            "action": step.action_name or "",
            "observation": _excerpt(step.observation, MAX_OBS_CHARS),
            "error": _excerpt(step.error_message, MAX_OBS_CHARS),
        })
    return rows


def _opaque_case_id(index: int) -> str:
    """不透明用例 id：盲表不得从 id / 文件名读出失败类型。"""
    return f"case_{index + 1:04d}"


def build_sheet(
    analyses: Iterable[Any],
    trajectories: Iterable[Any],
    source_files: Iterable[str],
) -> list[dict[str, Any]]:
    """Blind labeling sheet — carries neither analyzer labels nor provenance.

    ``source_file`` / ``session_id`` 也被刻意去掉：夹具文件名本身就编码失败类型
    （如 ``search_empty.json``），带进盲表等于把答案递给标注者。来源映射只存在 key 里，
    评分时按 ``case_id`` 合并。
    """
    sheet: list[dict[str, Any]] = []
    for index, (analysis, trajectory, _source) in enumerate(
        zip(analyses, trajectories, source_files)
    ):
        sheet.append({
            "case_id": _opaque_case_id(index),
            "query": _excerpt(getattr(analysis, "query", ""), MAX_QUERY_CHARS),
            "final_answer": _excerpt(getattr(trajectory, "final_answer", "") or "", MAX_ANSWER_CHARS),
            "steps": _raw_steps(trajectory),
            "human_label": [],
            "human_note": "",
        })
    return sheet


def build_key(
    analyses: Iterable[Any],
    source_files: Iterable[str],
) -> list[dict[str, Any]]:
    """Analyzer verdicts + provenance, kept apart from the sheet until scoring."""
    key: list[dict[str, Any]] = []
    for index, (analysis, source) in enumerate(zip(analyses, source_files)):
        labels = sorted({
            failure
            for path in (getattr(analysis, "paths", None) or [])
            for failure in path.failure_types
        })
        key.append({
            "case_id": _opaque_case_id(index),
            "source_file": source,
            "analyzer_label": labels,
            "needs_fix": bool(getattr(analysis, "needs_fix", False)),
        })
    return key


def write_jsonl(path: str, rows: list[dict[str, Any]], *, schema: str) -> None:
    lines = [json.dumps({"schema": schema}, ensure_ascii=False)]
    lines.extend(json.dumps(row, ensure_ascii=False) for row in rows)
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_jsonl(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if "schema" in row:
            continue
        rows.append(row)
    return rows


def _labels(row: dict[str, Any], field: str) -> set[str]:
    value = row.get(field)
    if isinstance(value, str):
        value = [part.strip() for part in value.split(",") if part.strip()]
    return {str(item).strip() for item in (value or []) if str(item).strip()}


def score_sheet(sheet: list[dict[str, Any]], key: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare human labels with analyzer labels; return metrics + disagreements."""
    human = {row.get("case_id"): row for row in sheet}
    analyzer = {row.get("case_id"): row for row in key}
    case_ids = sorted(set(human) & set(analyzer))

    types: set[str] = set()
    exact = 0
    verdict_agree = 0
    unlabeled: list[str] = []
    disagreements: list[dict[str, Any]] = []
    counts: dict[str, dict[str, Any]] = {}

    for case_id in case_ids:
        h = _labels(human[case_id], "human_label")
        a = _labels(analyzer[case_id], "analyzer_label")
        if not h and not (human[case_id].get("human_note") or "").strip():
            unlabeled.append(case_id)
        types |= h | a
        if h == a:
            exact += 1
        if bool(h) == bool(a):
            verdict_agree += 1
        else:
            disagreements.append({
                "case_id": case_id,
                "kind": "analyzer_false_positive" if a and not h else "analyzer_miss",
                "analyzer_label": sorted(a),
                "human_label": sorted(h),
                "source_file": human[case_id].get("source_file", ""),
            })
        if h != a and bool(h) == bool(a):
            disagreements.append({
                "case_id": case_id,
                "kind": "type_mismatch",
                "analyzer_label": sorted(a),
                "human_label": sorted(h),
                "source_file": human[case_id].get("source_file", ""),
            })

    for ftype in sorted(types):
        tp = fp = fn = 0
        for case_id in case_ids:
            h = ftype in _labels(human[case_id], "human_label")
            a = ftype in _labels(analyzer[case_id], "analyzer_label")
            if a and h:
                tp += 1
            elif a and not h:
                fp += 1
            elif h and not a:
                fn += 1
        counts[ftype] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(tp / (tp + fp), 4) if (tp + fp) else None,
            "recall": round(tp / (tp + fn), 4) if (tp + fn) else None,
        }

    n = len(case_ids)
    return {
        "n_cases": n,
        "n_labeled": n - len(unlabeled),
        "n_unlabeled": len(unlabeled),
        "unlabeled_cases": unlabeled[:20],
        "exact_match_rate": round(exact / n, 4) if n else None,
        "case_verdict_agreement": round(verdict_agree / n, 4) if n else None,
        "per_type": counts,
        "disagreements": disagreements,
    }


def format_score(report: dict[str, Any]) -> str:
    lines = ["=" * 55, "  Adjudication — 人工标注 vs Analyzer", "=" * 55]
    lines.append(f"  用例数: {report['n_cases']}  已标注: {report['n_labeled']}  未标注: {report['n_unlabeled']}")
    if report["n_labeled"] == 0:
        lines.append("")
        lines.append("  ⚠ 尚无人工标注：请填写 sheet 的 human_label 后再评分。")
        lines.append("    human_label 为空 = 该用例无失败；多个类型用逗号分隔。")
        lines.append("=" * 55)
        return "\n".join(lines)

    rate = report["exact_match_rate"]
    agree = report["case_verdict_agreement"]
    lines.append(f"  根因判对率（标签集合完全一致）: {rate:.1%}" if rate is not None else "  根因判对率: n/a")
    lines.append(f"  有无失败的判定一致率:           {agree:.1%}" if agree is not None else "  有无失败一致率: n/a")
    lines.append("")
    lines.append("  按类型（precision = 报出来的有多少是对的）:")
    lines.append(f"    {'type':22s} {'TP':>3s} {'FP':>3s} {'FN':>3s} {'precision':>10s} {'recall':>8s}")
    for ftype, c in sorted(report["per_type"].items()):
        prec = f"{c['precision']:.0%}" if c["precision"] is not None else "—"
        rec = f"{c['recall']:.0%}" if c["recall"] is not None else "—"
        lines.append(
            f"    {ftype:22s} {c['tp']:>3d} {c['fp']:>3d} {c['fn']:>3d} {prec:>10s} {rec:>8s}"
        )

    if report["disagreements"]:
        lines.append("")
        lines.append(f"  分歧 {len(report['disagreements'])} 处（前 10）:")
        for item in report["disagreements"][:10]:
            lines.append(
                f"    [{item['kind']}] {item['case_id']} "
                f"analyzer={item['analyzer_label']} human={item['human_label']}"
            )
    lines.append("=" * 55)
    return "\n".join(lines)


def default_sheet_paths(directory: str) -> tuple[str, str]:
    """Default output paths — under .tdebug/ so raw excerpts never land in git."""
    stem = Path(directory).name or "trajectories"
    base = Path(".tdebug") / "adjudication"
    return str(base / f"{stem}_sheet.jsonl"), str(base / f"{stem}_key.jsonl")
