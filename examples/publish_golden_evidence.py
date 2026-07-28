"""发布黄金失败集证据报告（Markdown + JSON 快照）。"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trace_debugger.analyzer import FailureType, failure_distribution  # noqa: E402
from trace_debugger.golden import DEFAULT_GOLDEN_DIR, run_golden_suite  # noqa: E402
from trace_debugger.reader import load  # noqa: E402


def _git_sha() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=ROOT,
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:
        return "unknown"


def build_distribution_report() -> dict:
    from trace_debugger import Analyzer

    suite = run_golden_suite()
    analyzed = []
    for row in suite["cases"]:
        analyzed.append(Analyzer().analyze(load(str(DEFAULT_GOLDEN_DIR / row["file"]))))
    dist = failure_distribution(analyzed)
    return {
        **suite,
        "report_id": f"golden_evidence_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_dir": str(DEFAULT_GOLDEN_DIR.as_posix()),
        "distribution": dist,
        "distribution_labels": {k: FailureType.LABELS.get(k, k) for k in dist},
        "meta": {
            "git": _git_sha(),
            "note": "黄金集标签经 Analyzer 验证；held-out 与 golden 分栏",
        },
    }


def to_markdown(report: dict, *, title: str) -> str:
    lines = [
        f"# {title}",
        "",
        f"- **report_id:** `{report.get('report_id', '')}`",
        f"- **timestamp:** `{report.get('timestamp', '')}`",
        f"- **cases:** {report.get('n_cases', 0)} (pass {report.get('n_passed', 0)} / fail {report.get('n_failed', 0)})",
        f"- **pass_rate:** {report.get('pass_rate', 0):.0%}",
        f"- **git:** `{((report.get('meta') or {}).get('git', 'unknown'))}`",
        "",
        "## 分栏通过率",
        "",
        "| split | n | passed | pass_rate |",
        "|-------|--:|-------:|----------:|",
    ]
    for split in ("golden", "held_out"):
        sub = run_golden_suite(split=split)
        lines.append(
            f"| `{split}` | {sub['n_cases']} | {sub['n_passed']} | {sub['pass_rate']:.0%} |"
        )

    lines.extend(["", "## 失败类型覆盖（负例轨迹）", ""])
    dist = report.get("distribution") or {}
    if not dist:
        lines.append("_（无）_")
    else:
        lines.append("| type | count | label |")
        lines.append("|------|------:|-------|")
        for ft, cnt in sorted(dist.items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"| `{ft}` | {cnt} | {FailureType.LABELS.get(ft, ft)} |")

    lines.extend(["", "## 用例明细", ""])
    for row in report.get("cases") or []:
        exp = ",".join(row.get("expected_failures") or []) or "-"
        det = ",".join(row.get("detected_failures") or []) or "-"
        icon = "PASS" if row.get("pass") else "FAIL"
        lines.append(
            f"- `{row.get('id')}` [{icon}] split={row.get('split')} "
            f"expected=[{exp}] detected=[{det}] — {row.get('file')}"
        )

    lines.extend([
        "",
        "## 复现",
        "",
        "```bash",
        "python scripts/generate_failure_golden.py",
        "python -m pytest tests/test_failure_golden.py -v",
        "python examples/publish_golden_evidence.py",
        "```",
        "",
        "## 诚实边界",
        "",
        "- 标签为规则/启发式 ground truth，非 LLM Judge",
        "- golden=开发集，held_out=对照集；不可合并为一个准确率数字",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stem", default=None)
    parser.add_argument("--out-dir", default=str(ROOT / "docs"))
    args = parser.parse_args()

    report = build_distribution_report()
    if report["n_failed"] > 0:
        print(f"Golden suite has failures: {report['n_failed']}", file=sys.stderr)
        return 1

    stem = args.stem or f"golden_evidence_{datetime.now().strftime('%Y%m%d')}"
    out_dir = Path(args.out_dir)
    snap_dir = out_dir / "snapshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    snap_dir.mkdir(parents=True, exist_ok=True)

    json_path = snap_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(
        to_markdown(report, title=f"黄金失败集证据（{stem}）"),
        encoding="utf-8",
    )

    print("=" * 55)
    print(f"  Golden evidence: {stem}")
    print(f"  cases={report['n_cases']} pass_rate={report['pass_rate']:.0%}")
    print(f"  -> {md_path}")
    print(f"  -> {json_path}")
    print("=" * 55)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
