#!/usr/bin/env python3
"""Run capability manifest eval (held-out + dev) and write snapshot JSON."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from trace_debugger.analyzer import Analyzer
from trace_debugger.reader import load
from trace_debugger.record import failure_distribution

ROOT = Path(__file__).resolve().parents[1]
TRAJ_DIR = ROOT.parent / "react-agent" / "src" / "react_agent" / "trajectories"
if not TRAJ_DIR.exists():
    TRAJ_DIR = ROOT / "../react-agent/src/react_agent/trajectories"

MANIFEST = ROOT / "docs" / "pilot" / "capability_manifest.json"
OUT = ROOT / "docs" / "pilot" / "capability_held_out_run_20260730.json"


def step_bucket(n: int) -> str:
    if n <= 2:
        return "short_1-2"
    if n <= 4:
        return "mid_3-4"
    if n <= 6:
        return "long_5-6"
    return "long_7+"


def eval_split(name: str, rows: list[dict], analyzer: Analyzer) -> dict:
    analyses = []
    records = []
    missing = []
    for row in rows:
        path = TRAJ_DIR / row["file"]
        if not path.exists():
            missing.append(row["file"])
            continue
        traj = load(str(path))
        analysis = analyzer.analyze(traj)
        analyses.append(analysis)
        fails = sorted({ft for pa in analysis.paths for ft in pa.failure_types})
        records.append(
            {
                "file": row["file"],
                "session_id": traj.session_id,
                "steps": traj.num_steps,
                "step_bucket": step_bucket(traj.num_steps),
                "failure_types": fails,
                "assessment": analysis.overall_assessment,
                "query_preview": (traj.query or "").replace("\n", " ")[:100],
            }
        )
    n = len(records)
    fail_n = sum(1 for r in records if r["failure_types"])
    dist = failure_distribution(analyses)
    return {
        "split": name,
        "n": n,
        "missing": missing,
        "fail_sessions": fail_n,
        "fail_rate_pct": round(100 * fail_n / n, 1) if n else 0.0,
        "distribution": dist,
        "step_bucket": dict(Counter(r["step_bucket"] for r in records)),
        "outcome": {"pass": n - fail_n, "fail": fail_n},
        "trajectories": records,
    }


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    analyzer = Analyzer()
    held = eval_split("held_out", manifest["held_out"]["trajectories"], analyzer)
    dev = eval_split("dev", manifest["dev"]["trajectories"], analyzer)

    payload = {
        "report_id": "capability_held_out_run_20260730",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "react_agent_trajectories": str(TRAJ_DIR.as_posix()),
        "manifest": str(MANIFEST.relative_to(ROOT)).replace("\\", "/"),
        "held_out": {k: held[k] for k in held if k != "trajectories"},
        "dev": {k: dev[k] for k in dev if k != "trajectories"},
        "held_out_trajectories": held["trajectories"],
        "dev_trajectories": dev["trajectories"],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"held-out: n={held['n']} fail={held['fail_sessions']} ({held['fail_rate_pct']}%) "
        f"dist={held['distribution']}"
    )
    print(
        f"dev:      n={dev['n']} fail={dev['fail_sessions']} ({dev['fail_rate_pct']}%) "
        f"dist={dev['distribution']}"
    )
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
