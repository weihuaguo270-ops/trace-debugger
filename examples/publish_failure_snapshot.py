"""发布失败类型分布周报（Markdown + 归档 JSON）。

用法：
  python examples/publish_failure_snapshot.py
  python examples/publish_failure_snapshot.py --dir examples/failure_bundle --stem tdebug_failure_20260715
  tdebug scan examples/failure_bundle 20   # 终端版
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trace_debugger import Analyzer, failure_distribution  # noqa: E402
from trace_debugger.analyzer import FailureType  # noqa: E402
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


def scan_directory(directory: Path, n: int = 50) -> dict:
    files = sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    files = files[:n]
    analyses = []
    rows = []
    analyzer = Analyzer()
    for path in files:
        traj = load(str(path))
        analysis = analyzer.analyze(traj)
        analyses.append(analysis)
        fails = sorted({ft for pa in analysis.paths for ft in pa.failure_types})
        rows.append({
            "file": path.name,
            "session_id": traj.session_id,
            "query": (traj.query or "")[:120],
            "assessment": analysis.overall_assessment,
            "failure_types": fails,
            "num_steps": traj.num_steps,
        })
    dist = failure_distribution(analyses)
    return {
        "report_id": f"tdebug_failure_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_dir": str(directory.as_posix()),
        "n_trajectories": len(rows),
        "distribution": dist,
        "distribution_labels": {
            k: FailureType.LABELS.get(k, k) for k in dist
        },
        "trajectories": rows,
        "meta": {
            "git": _git_sha(),
            "note": "启发式失败分类；非 LLM Judge",
        },
    }


def to_markdown(report: dict, *, title: str) -> str:
    dist = report.get("distribution") or {}
    lines = [
        f"# {title}",
        "",
        f"- **report_id:** `{report.get('report_id', '')}`",
        f"- **timestamp:** `{report.get('timestamp', '')}`",
        f"- **source:** `{report.get('source_dir', '')}`",
        f"- **轨迹数:** {report.get('n_trajectories', 0)}",
        f"- **git:** `{((report.get('meta') or {}).get('git', 'unknown'))}`",
        "",
        "## 失败类型分布（路径级计数）",
        "",
        "| type | count | label |",
        "|------|------:|-------|",
    ]
    if not dist:
        lines.append("| _(none)_ | 0 | 无检测到失败类型 |")
    else:
        for ft, cnt in sorted(dist.items(), key=lambda x: (-x[1], x[0])):
            label = FailureType.LABELS.get(ft, ft)
            lines.append(f"| `{ft}` | {cnt} | {label} |")
    lines.extend(["", "## 轨迹明细", ""])
    for row in report.get("trajectories") or []:
        fails = ",".join(row.get("failure_types") or []) or "-"
        lines.append(
            f"- `{row.get('file')}` — {row.get('assessment', '')} — "
            f"fails=[{fails}] — {(row.get('query') or '')[:80]}"
        )
    lines.extend([
        "",
        "## 复现",
        "",
        "```bash",
        "python examples/publish_failure_snapshot.py --dir examples/failure_bundle",
        "tdebug scan examples/failure_bundle 20",
        "```",
        "",
        "## 诚实边界",
        "",
        "- 分类为规则/启发式，不是 Judge 打分",
        "- `failure_bundle` 为演示样例；真实周报应指向本周 `trajectories/`",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dir",
        default=str(ROOT / "examples" / "failure_bundle"),
        help="轨迹 JSON 目录",
    )
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument(
        "--stem",
        default=None,
        help="输出文件 stem（默认 tdebug_failure_YYYYMMDD）",
    )
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "docs"),
        help="Markdown/快照输出目录",
    )
    args = parser.parse_args()

    source = Path(args.dir)
    if not source.is_dir():
        print(f"目录不存在: {source}", file=sys.stderr)
        return 1

    report = scan_directory(source, args.n)
    stem = args.stem or f"tdebug_failure_{datetime.now().strftime('%Y%m%d')}"
    out_dir = Path(args.out_dir)
    snap_dir = out_dir / "snapshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    snap_dir.mkdir(parents=True, exist_ok=True)

    json_path = snap_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(
        to_markdown(report, title=f"tdebug 失败分布周报（{stem}）"),
        encoding="utf-8",
    )

    print("=" * 55)
    print(f"  Failure snapshot: {stem}")
    print(f"  trajectories={report['n_trajectories']}  dist={report['distribution']}")
    print(f"  -> {md_path}")
    print(f"  -> {json_path}")
    print("=" * 55)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
