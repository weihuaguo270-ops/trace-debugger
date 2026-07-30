#!/usr/bin/env python3
"""Phase 5 timing study — raw JSON investigation vs tdebug.

Three layers (see docs/pilot/PHASE5.md):
  A1  in-process naive JSON scan (machine floor — not human)
  A2  human proxy model from steps + chars (estimated wall time)
  B1  in-process load + Analyzer (tool core)
  B2  CLI `python -m trace_debugger.cli` (what devs actually run)
"""
from __future__ import annotations

import json
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRAJ_DIR = ROOT.parent / "react-agent" / "src" / "react_agent" / "trajectories"
if not TRAJ_DIR.exists():
    TRAJ_DIR = ROOT / "../react-agent/src/react_agent/trajectories"

OUT = ROOT / "docs" / "pilot" / "phase5_timing_results.json"

CASES = [
    ("traj_20260727_220616_o20u.json", "tool_error", "deepseek"),
    ("traj_20260727_220517_h8zm.json", "tool_error", "deepseek"),
    ("traj_20260727_220426_46q8.json", "tool_error", "deepseek"),
    ("traj_20260727_220233_k6v8.json", "tool_error", "deepseek"),
    ("traj_20260727_215701_pr0y.json", "tool_error", "deepseek"),
    ("traj_20260717_095838_566v.json", "tool_error", "deepseek"),
    ("traj_20260716_181136_ztgc.json", "no_answer", "deepseek"),
    ("traj_20260713_141323_jayb.json", "duplicate+tool_error", "deepseek"),
    ("traj_20260729_134107_zhf4.json", "search_empty", "mock"),
    ("traj_20260729_134107_ifcm.json", "search_empty", "mock"),
]

ERROR_KW = re.compile(
    r"error|exception|failed|traceback|超时|失败|报错|empty|no results|无结果",
    re.I,
)

# Human proxy (seconds): orient + per-step read + classify without taxonomy cheat sheet
HUMAN_BASE_S = 35.0
HUMAN_PER_STEP_S = 22.0
HUMAN_CLASSIFY_S = 40.0
HUMAN_READ_CHARS_PER_S = 45.0  # skim JSON in editor

# Human tdebug path (seconds): type command + read one-screen summary
HUMAN_TDEBUG_S = 12.0


def _file_stats(path: Path) -> tuple[int, int, int]:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    steps = data.get("steps") or []
    return len(text), len(steps), len(steps)


def investigate_raw_inprocess(path: Path) -> float:
    """Machine floor: parse + scan steps once."""
    t0 = time.perf_counter()
    data = json.loads(path.read_text(encoding="utf-8"))
    for step in data.get("steps") or []:
        obs = step.get("observation") or ""
        err = step.get("error_message") or step.get("error") or ""
        _ = step.get("has_error") or err or ERROR_KW.search(obs)
    _ = (data.get("final_answer") or "").strip()
    return (time.perf_counter() - t0) * 1000


def investigate_raw_thorough(path: Path) -> float:
    """Simulate jq/grep-style multi-pass manual triage in terminal."""
    t0 = time.perf_counter()
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    # pass 1: skim raw text for error-ish lines
    for line in text.splitlines():
        if ERROR_KW.search(line):
            _ = line
    # pass 2: walk structured steps
    for step in data.get("steps") or []:
        blob = json.dumps(step, ensure_ascii=False)
        for _m in ERROR_KW.finditer(blob):
            pass
    # pass 3: check answer present
    steps = data.get("steps") or []
    final = (data.get("final_answer") or "").strip()
    if not final:
        for s in steps:
            if "FINAL ANSWER" in (s.get("thought") or "").upper():
                final = s.get("thought") or ""
                break
    return (time.perf_counter() - t0) * 1000


def investigate_tdebug_inprocess(path: Path) -> float:
    from trace_debugger.analyzer import Analyzer
    from trace_debugger.reader import load

    t0 = time.perf_counter()
    traj = load(str(path))
    analysis = Analyzer().analyze(traj)
    _ = analysis.overall_assessment
    _ = {ft for pa in analysis.paths for ft in pa.failure_types}
    return (time.perf_counter() - t0) * 1000


def investigate_tdebug_cli(path: Path) -> float:
    t0 = time.perf_counter()
    subprocess.run(
        [sys.executable, "-m", "trace_debugger.cli", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return (time.perf_counter() - t0) * 1000


def human_proxy_raw_s(n_steps: int, n_chars: int) -> float:
    read_s = n_chars / HUMAN_READ_CHARS_PER_S
    return HUMAN_BASE_S + n_steps * HUMAN_PER_STEP_S + HUMAN_CLASSIFY_S + read_s


def median(values: list[float]) -> float:
    return statistics.median(values)


def main() -> int:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    rows = []
    for fname, fail_type, model in CASES:
        path = TRAJ_DIR / fname
        if not path.exists():
            print(f"MISSING {path}", file=sys.stderr)
            continue
        n_chars, n_steps, _ = _file_stats(path)
        human_raw_s = human_proxy_raw_s(n_steps, n_chars)

        raw_fast, raw_thorough, td_in, td_cli = [], [], [], []
        for _ in range(runs):
            raw_fast.append(investigate_raw_inprocess(path))
            raw_thorough.append(investigate_raw_thorough(path))
            td_in.append(investigate_tdebug_inprocess(path))
            td_cli.append(investigate_tdebug_cli(path))

        row = {
            "file": fname,
            "failure_type": fail_type,
            "model": model,
            "num_steps": n_steps,
            "file_chars": n_chars,
            "human_proxy_raw_s": round(human_raw_s, 1),
            "human_proxy_tdebug_s": HUMAN_TDEBUG_S,
            "human_proxy_ratio": round(HUMAN_TDEBUG_S / human_raw_s, 3),
            "human_tdebug_faster": HUMAN_TDEBUG_S < human_raw_s,
            "raw_inprocess_ms_median": round(median(raw_fast), 2),
            "raw_thorough_ms_median": round(median(raw_thorough), 2),
            "tdebug_inprocess_ms_median": round(median(td_in), 2),
            "tdebug_cli_ms_median": round(median(td_cli), 2),
            "runs": runs,
        }
        rows.append(row)
        print(
            f"{fname}: human {human_raw_s:.0f}s vs tdebug~{HUMAN_TDEBUG_S}s | "
            f"inproc raw={row['raw_inprocess_ms_median']:.1f}ms td={row['tdebug_inprocess_ms_median']:.1f}ms"
        )

    n = len(rows)
    human_faster = sum(1 for r in rows if r["human_tdebug_faster"])
    total_human_raw = sum(r["human_proxy_raw_s"] for r in rows)
    total_human_td = n * HUMAN_TDEBUG_S
    summary = {
        "n_cases": n,
        "runs_per_case": runs,
        "human_proxy": {
            "tdebug_faster_count": human_faster,
            "tdebug_faster_pct": round(100 * human_faster / n, 1),
            "total_raw_s": round(total_human_raw, 1),
            "total_tdebug_s": total_human_td,
            "aggregate_ratio": round(total_human_td / total_human_raw, 3),
            "pass_70pct_cases": human_faster >= 0.7 * n,
            "pass_60pct_aggregate_time": (total_human_td / total_human_raw) <= 0.6,
        },
        "machine_inprocess": {
            "note": "json.loads vs Analyzer — not valid human proxy",
            "tdebug_faster_count": sum(
                1 for r in rows if r["tdebug_inprocess_ms_median"] < r["raw_thorough_ms_median"]
            ),
        },
    }
    payload = {"summary": summary, "cases": rows, "methodology": "docs/pilot/PHASE5.md"}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SUMMARY human_proxy", json.dumps(summary["human_proxy"], ensure_ascii=False))
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
