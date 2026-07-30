#!/usr/bin/env python3
"""Build pilot scan snapshots with optional mock exclusion.

Used when tdebug scan does not yet support --exclude-model.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from trace_debugger.analyzer import Analyzer
from trace_debugger.reader import load, load_recent_paths
from trace_debugger.record import build_scan_snapshot


def _select_from_snapshot(directory: str, snapshot_path: str) -> tuple[list, list[str]]:
    data = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    trajs, paths = [], []
    for row in data.get("trajectories") or []:
        fname = row.get("file")
        if not fname:
            continue
        full = os.path.join(directory, fname)
        trajs.append(load(full))
        paths.append(full)
    return trajs, paths


def _select(directory: str, n: int, *, exclude_mock: bool) -> tuple[list, list[str]]:
    if not exclude_mock:
        return load_recent_paths(directory, n)

    files = sorted(
        [f for f in os.listdir(directory) if f.endswith(".json")],
        key=lambda f: os.path.getmtime(os.path.join(directory, f)),
        reverse=True,
    )
    trajs, paths = [], []
    for f in files:
        full = os.path.join(directory, f)
        try:
            traj = load(full)
        except Exception:
            continue
        if (traj.model or "").lower() == "mock":
            continue
        trajs.append(traj)
        paths.append(full)
        if len(trajs) >= n:
            break
    return trajs, paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Build pilot scan / baseline JSON")
    parser.add_argument("directory", nargs="?", default="../react-agent/src/react_agent/trajectories")
    parser.add_argument("-n", type=int, default=100)
    parser.add_argument("--exclude-mock", action="store_true")
    parser.add_argument(
        "--offtrack-overlap",
        type=float,
        default=None,
        help="Override Analyzer offtrack_overlap (Run B simulation)",
    )
    parser.add_argument(
        "--from-snapshot",
        default="",
        help="Use exact file list from an existing snapshot JSON",
    )
    parser.add_argument("--json-out", required=True, help="Output snapshot path")
    parser.add_argument("--report-id", default="", help="Override report_id")
    parser.add_argument("--baseline", action="store_true", help="Mark meta.baseline=true")
    args = parser.parse_args()

    if args.from_snapshot:
        trajs, paths = _select_from_snapshot(args.directory, args.from_snapshot)
    else:
        trajs, paths = _select(args.directory, args.n, exclude_mock=args.exclude_mock)
    if not trajs:
        print(f"No trajectories in {args.directory}", file=sys.stderr)
        return 1

    if args.offtrack_overlap is not None:
        analyzer = Analyzer(offtrack_overlap=args.offtrack_overlap)
    else:
        analyzer = Analyzer()
    analyses = [analyzer.analyze(t) for t in trajs]
    snap = build_scan_snapshot(args.directory, args.n, trajs, analyses, source_files=paths)

    if args.report_id:
        snap["report_id"] = args.report_id
    if args.baseline:
        variant = "latest_non_mock_by_mtime" if args.exclude_mock else "latest_by_mtime"
        snap["meta"] = {
            **snap.get("meta", {}),
            "baseline": True,
            "variant": variant,
            "frozen_at": datetime.now(timezone.utc).isoformat(),
        }

    out = Path(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")

    fail_n = sum(1 for r in snap["trajectories"] if r.get("failure_types"))
    print(f"Wrote {out} n={snap['n_trajectories']} dist={snap['distribution']} fail_sessions={fail_n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
