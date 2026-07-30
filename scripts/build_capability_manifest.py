#!/usr/bin/env python3
"""Build stratified capability dev / held-out manifests from react-agent trajectories.

Excludes mock. Caps single-day (20260713) oversampling. Deterministic seed.
"""
from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

from trace_debugger.analyzer import Analyzer
from trace_debugger.reader import load

ROOT = Path(__file__).resolve().parents[1]
TRAJ_DIR = ROOT.parent / "react-agent" / "src" / "react_agent" / "trajectories"
if not TRAJ_DIR.exists():
    TRAJ_DIR = ROOT / "../react-agent/src/react_agent/trajectories"

OUT_DIR = ROOT / "docs" / "pilot"
SEED = 20260730
HELD_OUT_N = 80
DEV_N = 50
MAX_DAY_SHARE = 0.28  # max fraction from any single YYYYMMDD in a manifest


def step_bucket(n: int) -> str:
    if n <= 2:
        return "short_1-2"
    if n <= 4:
        return "mid_3-4"
    if n <= 6:
        return "long_5-6"
    return "long_7+"


def outcome(has_fails: bool) -> str:
    return "fail" if has_fails else "pass"


def load_pool() -> list[dict]:
    analyzer = Analyzer()
    pool = []
    for p in sorted(TRAJ_DIR.glob("traj_*.json"), key=lambda x: x.name):
        t = load(str(p))
        if (t.model or "").lower() == "mock":
            continue
        a = analyzer.analyze(t)
        fails = sorted({ft for pa in a.paths for ft in pa.failure_types})
        pool.append(
            {
                "file": p.name,
                "date": p.name[5:13],
                "steps": t.num_steps,
                "step_bucket": step_bucket(t.num_steps),
                "outcome": outcome(bool(fails)),
                "failure_types": fails,
                "has_memory_prefix": "相关记忆" in (t.query or ""),
                "query_preview": (t.query or "").replace("\n", " ")[:100],
            }
        )
    return pool


def stratified_sample(
    pool: list[dict],
    n: int,
    exclude: set[str],
    rng: random.Random,
) -> list[dict]:
    available = [r for r in pool if r["file"] not in exclude]
    by_stratum: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in available:
        by_stratum[(r["step_bucket"], r["outcome"])].append(r)

    strata = list(by_stratum.keys())
    # target: proportional to stratum size, at least 1 per non-empty stratum if n allows
    total = len(available)
    picks: list[dict] = []
    quotas: dict[tuple[str, str], int] = {}
    remaining = n
    for s in sorted(strata):
        size = len(by_stratum[s])
        q = max(1, round(n * size / total)) if remaining > 0 else 0
        quotas[s] = min(q, size, remaining)
        remaining -= quotas[s]
    # distribute rounding slack to largest strata
    while remaining > 0:
        for s in sorted(strata, key=lambda x: len(by_stratum[x]), reverse=True):
            if len(by_stratum[s]) > quotas[s]:
                quotas[s] += 1
                remaining -= 1
                if remaining == 0:
                    break

    for s, q in quotas.items():
        candidates = by_stratum[s][:]
        rng.shuffle(candidates)
        picks.extend(candidates[:q])

    # enforce day cap
    picks = _enforce_day_cap(picks, n, by_stratum, rng, max_share=MAX_DAY_SHARE)
    return sorted(picks, key=lambda r: r["file"])


def _enforce_day_cap(
    picks: list[dict],
    target_n: int,
    by_stratum: dict,
    rng: random.Random,
    max_share: float,
) -> list[dict]:
    max_per_day = max(1, int(target_n * max_share))

    def ok(rows: list[dict]) -> bool:
        from collections import Counter

        c = Counter(r["date"] for r in rows)
        return all(v <= max_per_day for v in c.values())

    if ok(picks):
        return picks[:target_n]

    picks = picks[:]
    rng.shuffle(picks)
    result: list[dict] = []
    day_count: dict[str, int] = defaultdict(int)
    for r in picks:
        if len(result) >= target_n:
            break
        if day_count[r["date"]] >= max_per_day:
            continue
        result.append(r)
        day_count[r["date"]] += 1

    # fill if under target from remaining pool
    if len(result) < target_n:
        used = {r["file"] for r in result}
        rest = [r for rows in by_stratum.values() for r in rows if r["file"] not in used]
        rng.shuffle(rest)
        for r in rest:
            if len(result) >= target_n:
                break
            if day_count[r["date"]] >= max_per_day:
                continue
            result.append(r)
            day_count[r["date"]] += 1
    return result[:target_n]


def summarize(rows: list[dict]) -> dict:
    from collections import Counter

    return {
        "n": len(rows),
        "step_bucket": dict(Counter(r["step_bucket"] for r in rows)),
        "outcome": dict(Counter(r["outcome"] for r in rows)),
        "date": dict(Counter(r["date"] for r in rows)),
        "failure_types": dict(Counter(ft for r in rows for ft in r["failure_types"])),
    }


def main() -> None:
    pool = load_pool()
    rng = random.Random(SEED)

    held = stratified_sample(pool, HELD_OUT_N, exclude=set(), rng=rng)
    held_files = {r["file"] for r in held}
    dev = stratified_sample(pool, DEV_N, exclude=held_files, rng=random.Random(SEED + 1))

    payload = {
        "meta": {
            "created": "2026-07-30",
            "source_dir": str(TRAJ_DIR.as_posix()),
            "seed": SEED,
            "excluded": ["model:mock"],
            "max_day_share": MAX_DAY_SHARE,
            "pool_non_mock": len(pool),
            "purpose": {
                "held_out": "能力评估 — 冻结，不参与 prompt 调参",
                "dev": "开发调优 — 可复盘，不得泄漏到 held-out 标签",
            },
        },
        "held_out": {"summary": summarize(held), "trajectories": held},
        "dev": {"summary": summarize(dev), "trajectories": dev},
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "capability_manifest.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # flat file lists for scripts
    (OUT_DIR / "capability_held_out_files.txt").write_text(
        "\n".join(r["file"] for r in held) + "\n", encoding="utf-8"
    )
    (OUT_DIR / "capability_dev_files.txt").write_text(
        "\n".join(r["file"] for r in dev) + "\n", encoding="utf-8"
    )

    print(f"pool={len(pool)} held_out={len(held)} dev={len(dev)}")
    print("held_out", json.dumps(payload["held_out"]["summary"], ensure_ascii=False))
    print("dev", json.dumps(payload["dev"]["summary"], ensure_ascii=False))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
