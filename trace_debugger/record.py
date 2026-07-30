"""record — 失败事件持久化与扫描快照对比

注意：事件可能含 query、thought、action_args、observation（见 step_failure_event）。
无内置脱敏/TTL/访问控制 — 企业集成前请阅 docs/RISKS.md R2 与 SECURITY.md。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .analyzer import FailureType, StepAnalysis, TrajectoryAnalysis, failure_distribution
from .reader import Trajectory

DEFAULT_RECORD_PATH = ".tdebug/failures.jsonl"
RECORD_SCHEMA_VERSION = "2"


def resolve_record_path(explicit: Optional[str] = None) -> str:
    """Resolve failure JSONL path: explicit arg > TDEBUG_RECORD_PATH > default."""
    if explicit:
        return explicit
    return os.environ.get("TDEBUG_RECORD_PATH", DEFAULT_RECORD_PATH)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _preview(text: str, limit: int = 160) -> str:
    text = (text or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def failure_label(failure_type: str) -> str:
    return FailureType.LABELS.get(failure_type, failure_type)


def failure_severity(failure_type: str, *, event_type: str = "step_failure") -> str:
    if failure_type in (FailureType.NO_FINAL_ANSWER, FailureType.LLM_OFFTRACK):
        return "fail"
    if failure_type in (FailureType.CONTEXT_OVERFLOW, FailureType.SEARCH_TIMEOUT):
        return "warn"
    if event_type == "path_failure":
        return "fail"
    return "warn"


def build_failure_summary(
    *,
    failure_type: str,
    step_index: Optional[int] = None,
    action: str = "",
    event_type: str = "step_failure",
) -> str:
    label = failure_label(failure_type)
    if event_type == "path_failure":
        return f"路径级 · {label}"
    if action:
        return f"Step {step_index} · {action} · {label}"
    if step_index is not None:
        return f"Step {step_index} · {label}"
    return label


def build_failure_context(
    *,
    thought: str = "",
    action: str = "",
    action_args: str = "",
    observation: str = "",
    duration: float = 0.0,
) -> dict[str, Any]:
    ctx: dict[str, Any] = {}
    if action:
        ctx["action"] = action
    if action_args:
        ctx["arguments_preview"] = _preview(action_args, 120)
    if observation:
        ctx["observation_preview"] = _preview(observation, 200)
    if thought:
        ctx["thought_preview"] = _preview(thought, 120)
    if duration:
        ctx["duration_seconds"] = round(duration, 2)
    return ctx


def enrich_failure_event(ev: dict[str, Any]) -> dict[str, Any]:
    """为事件补充可读字段（label / summary / severity / context）。"""
    ft = ev.get("failure_type") or ""
    event_type = ev.get("event_type") or "step_failure"
    step_index = ev.get("step_index")
    action = ev.get("action") or ""
    ctx = ev.get("context")
    if ctx is None:
        ctx = build_failure_context(
            thought=ev.get("thought", ""),
            action=action,
            action_args=ev.get("action_args", ""),
            observation=ev.get("observation", ""),
            duration=float(ev.get("duration_seconds") or 0),
        )
    enriched = {
        **ev,
        "schema_version": RECORD_SCHEMA_VERSION,
        "failure_label": failure_label(ft),
        "summary": build_failure_summary(
            failure_type=ft,
            step_index=step_index,
            action=action,
            event_type=event_type,
        ),
        "severity": failure_severity(ft, event_type=event_type),
        "context": ctx,
    }
    return enriched


def format_event_readable(ev: dict[str, Any]) -> str:
    """单条失败事件的人类可读文本块。"""
    ev = enrich_failure_event(ev) if ev.get("schema_version") != RECORD_SCHEMA_VERSION else ev
    ts = (ev.get("recorded_at") or "")[:19].replace("T", " ")
    session = ev.get("session_id") or "?"
    query = _preview(ev.get("query") or "", 80)
    lines = [
        f"[{ts}] {session} · {ev.get('summary', ev.get('failure_type', '?'))}",
        f"  类型: {ev.get('failure_type')} ({ev.get('failure_label')}) · 级别: {ev.get('severity', '?')}",
    ]
    if query:
        lines.append(f"  查询: {query}")
    ctx = ev.get("context") or {}
    if ctx.get("action"):
        arg = ctx.get("arguments_preview") or ""
        lines.append(f"  工具: {ctx['action']}({arg})" if arg else f"  工具: {ctx['action']}")
    if ctx.get("thought_preview"):
        lines.append(f"  思考: {ctx['thought_preview']}")
    if ctx.get("observation_preview"):
        lines.append(f"  观测: {ctx['observation_preview']}")
    if ev.get("failure_detail"):
        lines.append(f"  原因: {ev['failure_detail']}")
    if ev.get("suggestion"):
        lines.append(f"  建议: {ev['suggestion']}")
    if ev.get("source_file"):
        lines.append(f"  轨迹: {ev['source_file']}")
    return "\n".join(lines)


def readable_log_path(record_path: str) -> Path:
    p = Path(record_path)
    return p.with_name(p.stem + ".log")


def session_summary_path(record_path: str, session_id: str) -> Path:
    base = Path(record_path).parent / "sessions"
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
    return base / f"{safe}.md"


def append_events(record_path: str, events: list[dict[str, Any]]) -> int:
    """追加事件到 JSONL，并同步写入可读 .log。"""
    if not events:
        return 0
    enriched = [enrich_failure_event(ev) for ev in events]
    path = Path(record_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for ev in enriched:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    log_path = readable_log_path(record_path)
    with log_path.open("a", encoding="utf-8") as f:
        for ev in enriched:
            f.write(format_event_readable(ev))
            f.write("\n---\n")
    return len(enriched)


def write_session_summary(
    record_path: str,
    *,
    session_id: str,
    query: str,
    model: str,
    events: list[dict[str, Any]],
    overall_assessment: str = "",
) -> Optional[str]:
    """为单次会话生成 Markdown 摘要（便于人工复盘）。"""
    if not events:
        return None
    enriched = [
        enrich_failure_event(ev) if ev.get("schema_version") != RECORD_SCHEMA_VERSION else ev
        for ev in events
    ]
    out = session_summary_path(record_path, session_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    types = sorted({ev.get("failure_type") for ev in enriched if ev.get("failure_type")})
    lines = [
        f"# 失败复盘 · {session_id}",
        "",
        f"- **时间:** `{_utc_now()[:19]}`",
        f"- **模型:** {model or '-'}",
        f"- **失败数:** {len(enriched)}",
        f"- **类型:** {', '.join(failure_label(t) for t in types)}",
        "",
        f"## 用户需求",
        "",
        query[:500] or "_(空)_",
        "",
    ]
    if overall_assessment:
        lines.extend([f"## 总体评估", "", overall_assessment, ""])
    lines.append("## 失败明细")
    lines.append("")
    for i, ev in enumerate(enriched, 1):
        lines.append(f"### {i}. {ev.get('summary', ev.get('failure_type'))}")
        lines.append("")
        lines.append(f"- **类型:** `{ev.get('failure_type')}` · {ev.get('failure_label')}")
        lines.append(f"- **级别:** {ev.get('severity')}")
        ctx = ev.get("context") or {}
        if ctx.get("action"):
            lines.append(f"- **工具:** `{ctx['action']}`")
        if ctx.get("arguments_preview"):
            lines.append(f"- **参数:** `{ctx['arguments_preview']}`")
        if ctx.get("observation_preview"):
            lines.append(f"- **观测:** {ctx['observation_preview']}")
        if ev.get("failure_detail"):
            lines.append(f"- **原因:** {ev['failure_detail']}")
        if ev.get("suggestion"):
            lines.append(f"- **建议:** {ev['suggestion']}")
        lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    return str(out)


def load_failure_events(record_path: str, *, session_id: Optional[str] = None) -> list[dict[str, Any]]:
    path = Path(record_path)
    if not path.is_file():
        return []
    events = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if session_id and ev.get("session_id") != session_id:
                continue
            events.append(enrich_failure_event(ev))
    return events


def format_failures_digest(record_path: str, *, session_id: Optional[str] = None) -> str:
    """从 JSONL 生成终端可读 digest。"""
    events = load_failure_events(record_path, session_id=session_id)
    if not events:
        return f"（无失败记录: {record_path}）"
    lines = [
        "=" * 55,
        "  Trace Debugger — 失败记录 digest",
        "=" * 55,
        f"  来源: {record_path}",
        f"  条数: {len(events)}" + (f"  会话: {session_id}" if session_id else ""),
        "",
    ]
    for ev in events:
        lines.append(format_event_readable(ev))
        lines.append("")
    lines.append("=" * 55)
    return "\n".join(lines)


def aggregate_failure_stats(events: list[dict[str, Any]]) -> dict[str, Any]:
    """按失败类型聚合统计。"""
    from collections import Counter, defaultdict

    if not events:
        return {
            "n_events": 0,
            "n_sessions": 0,
            "by_type": [],
            "by_severity": {},
            "by_event_type": {},
        }

    type_counts: Counter[str] = Counter()
    severity_counts: Counter[str] = Counter()
    event_type_counts: Counter[str] = Counter()
    action_counts: dict[str, Counter[str]] = defaultdict(Counter)
    sessions: set[str] = set()
    session_by_type: dict[str, set[str]] = defaultdict(set)
    examples_by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for ev in events:
        ft = ev.get("failure_type") or "unknown"
        type_counts[ft] += 1
        severity_counts[ev.get("severity") or failure_severity(
            ft, event_type=ev.get("event_type") or "step_failure"
        )] += 1
        event_type_counts[ev.get("event_type") or "step_failure"] += 1

        sid = ev.get("session_id") or ""
        if sid:
            sessions.add(sid)
            session_by_type[ft].add(sid)

        ctx = ev.get("context") or {}
        action = ev.get("action") or ctx.get("action") or ""
        if action:
            action_counts[ft][action] += 1

        if len(examples_by_type[ft]) < 3:
            examples_by_type[ft].append({
                "session_id": sid,
                "summary": ev.get("summary") or build_failure_summary(
                    failure_type=ft,
                    step_index=ev.get("step_index"),
                    action=action,
                    event_type=ev.get("event_type") or "step_failure",
                ),
                "step_index": ev.get("step_index"),
                "recorded_at": (ev.get("recorded_at") or "")[:19],
            })

    total = len(events)
    by_type: list[dict[str, Any]] = []
    for ft, cnt in type_counts.most_common():
        top_actions = [
            {"action": name, "count": n}
            for name, n in action_counts[ft].most_common(5)
        ]
        by_type.append({
            "failure_type": ft,
            "label": failure_label(ft),
            "count": cnt,
            "pct": round(cnt / total * 100, 1),
            "unique_sessions": len(session_by_type[ft]),
            "top_actions": top_actions,
            "examples": examples_by_type[ft],
        })

    return {
        "n_events": total,
        "n_sessions": len(sessions),
        "by_type": by_type,
        "by_severity": dict(severity_counts.most_common()),
        "by_event_type": dict(event_type_counts.most_common()),
    }


def failure_stats_from_log(
    record_path: str,
    *,
    session_id: Optional[str] = None,
) -> dict[str, Any]:
    """从 JSONL 加载并聚合。"""
    events = load_failure_events(record_path, session_id=session_id)
    stats = aggregate_failure_stats(events)
    stats["source"] = str(Path(record_path).as_posix())
    if session_id:
        stats["session_filter"] = session_id
    stats["timestamp"] = _utc_now()
    return stats


def format_failure_stats(
    record_path: str,
    *,
    session_id: Optional[str] = None,
) -> str:
    """按失败类型聚合的终端报告。"""
    stats = failure_stats_from_log(record_path, session_id=session_id)
    if stats["n_events"] == 0:
        return f"（无失败记录: {record_path}）"

    lines = [
        "=" * 60,
        "  Trace Debugger — 失败类型聚合统计",
        "=" * 60,
        f"  来源: {stats['source']}",
        f"  事件数: {stats['n_events']}  会话数: {stats['n_sessions']}",
    ]
    if session_id:
        lines.append(f"  筛选会话: {session_id}")
    lines.extend(["", "  ── 按失败类型 ──", ""])
    lines.append(f"  {'type':<20} {'count':>5} {'pct':>6} {'sessions':>8}  中文标签")
    lines.append("  " + "-" * 56)

    for row in stats["by_type"]:
        lines.append(
            f"  {row['failure_type']:<20} {row['count']:5d} {row['pct']:5.1f}% "
            f"{row['unique_sessions']:8d}  {row['label']}"
        )

    sev = stats.get("by_severity") or {}
    if sev:
        lines.extend(["", "  ── 按严重级别 ──", ""])
        for level, cnt in sev.items():
            lines.append(f"  {level:<10} {cnt:5d}")

    evt = stats.get("by_event_type") or {}
    if evt:
        lines.extend(["", "  ── 按事件层级 ──", ""])
        for et, cnt in evt.items():
            label = "逐步失败" if et == "step_failure" else "路径级失败"
            lines.append(f"  {et:<14} {cnt:5d}  ({label})")

    lines.extend(["", "  ── 各类型 Top 工具 & 样例 ──", ""])
    for row in stats["by_type"]:
        lines.append(f"\n  [{row['failure_type']}] {row['label']} × {row['count']}")
        if row.get("top_actions"):
            actions = ", ".join(
                f"{a['action']}({a['count']})" for a in row["top_actions"][:3]
            )
            lines.append(f"    高频工具: {actions}")
        for ex in row.get("examples") or []:
            lines.append(f"    · {ex.get('summary', '')} [{ex.get('session_id', '?')}]")

    lines.extend(["", "=" * 60])
    return "\n".join(lines)


def step_failure_event(
    sa: StepAnalysis,
    *,
    session_id: str,
    query: str,
    model: str,
    path_index: int = 0,
    source_file: str = "",
    thought: str = "",
    action_args: str = "",
    observation: str = "",
) -> dict[str, Any]:
    """构造单步失败事件（运行时即时写入）。"""
    return enrich_failure_event({
        "recorded_at": _utc_now(),
        "event_type": "step_failure",
        "source_file": source_file,
        "session_id": session_id,
        "query": query[:200],
        "model": model,
        "path_index": path_index,
        "step_index": sa.step_index,
        "action": sa.action,
        "action_args": action_args,
        "thought": thought,
        "observation": observation,
        "duration_seconds": sa.duration,
        "failure_type": sa.failure_type,
        "failure_detail": sa.failure_detail,
        "suggestion": sa.suggestion,
    })


def failure_events_from_analysis(
    analysis: TrajectoryAnalysis,
    *,
    source_file: str = "",
    skip_steps: Optional[set[tuple[int, int]]] = None,
) -> list[dict[str, Any]]:
    """从分析结果提取失败事件（用于 JSONL 追加）。"""
    skip_steps = skip_steps or set()
    events: list[dict[str, Any]] = []
    base = {
        "recorded_at": _utc_now(),
        "source_file": source_file,
        "session_id": analysis.session_id,
        "query": analysis.query[:200],
        "model": analysis.model,
    }
    for pa in analysis.paths:
        for sa in pa.step_analyses:
            if sa.success or not sa.failure_type:
                continue
            if (pa.path_index, sa.step_index) in skip_steps:
                continue
            events.append(enrich_failure_event({
                **base,
                "event_type": "step_failure",
                "path_index": pa.path_index,
                "step_index": sa.step_index,
                "action": sa.action,
                "failure_type": sa.failure_type,
                "failure_detail": sa.failure_detail,
                "suggestion": sa.suggestion,
                "duration_seconds": sa.duration,
            }))
        step_types = {sa.failure_type for sa in pa.step_analyses if sa.failure_type}
        for ft in pa.failure_types:
            if ft in step_types:
                continue
            detail = next(
                (d for d in pa.failure_details if FailureType.LABELS.get(ft, ft) in d or ft in d),
                "",
            )
            events.append(enrich_failure_event({
                **base,
                "event_type": "path_failure",
                "path_index": pa.path_index,
                "failure_type": ft,
                "failure_detail": detail,
                "suggestion": _suggestion_for_type(ft),
            }))
    return events


def _suggestion_for_type(failure_type: str) -> str:
    mapping = {
        FailureType.TOOL_ERROR: "检查工具参数是否正确，或增加参数校验",
        FailureType.SEARCH_EMPTY: "调整搜索词策略，先确认需求再搜索",
        FailureType.SEARCH_TIMEOUT: "限制搜索范围或添加缓存层",
        FailureType.LLM_OFFTRACK: "在 system prompt 中强化约束，或增加意图校验",
        FailureType.CONTEXT_OVERFLOW: "压缩上下文或启用摘要/窗口滑动",
        FailureType.DUPLICATE_ATTEMPT: "添加状态追踪，避免重复相同尝试",
        FailureType.NO_FINAL_ANSWER: "确保 Agent 在结束前输出 FINAL ANSWER",
    }
    return mapping.get(failure_type, "检查执行环境和输入")


def append_failure_events(
    analysis: TrajectoryAnalysis,
    record_path: str,
    *,
    source_file: str = "",
    skip_steps: Optional[set[tuple[int, int]]] = None,
) -> int:
    """追加失败事件到 JSONL，返回写入条数。"""
    events = failure_events_from_analysis(
        analysis, source_file=source_file, skip_steps=skip_steps,
    )
    n = append_events(record_path, events)
    if n:
        write_session_summary(
            record_path,
            session_id=analysis.session_id,
            query=analysis.query,
            model=analysis.model,
            events=events,
            overall_assessment=analysis.overall_assessment,
        )
    return n


def build_scan_snapshot(
    directory: str,
    n: int,
    trajs: list[Trajectory],
    analyses: list[TrajectoryAnalysis],
    *,
    source_files: Optional[list[str]] = None,
) -> dict[str, Any]:
    """构建可归档、可对比的扫描快照。"""
    dist = failure_distribution(analyses)
    rows = []
    for i, (traj, analysis) in enumerate(zip(trajs, analyses)):
        fails = sorted({ft for pa in analysis.paths for ft in pa.failure_types})
        fail_labels = [failure_label(ft) for ft in fails]
        row: dict[str, Any] = {
            "session_id": traj.session_id,
            "query": (traj.query or "")[:120],
            "assessment": analysis.overall_assessment,
            "failure_types": fails,
            "failure_labels": fail_labels,
            "failure_summary": "、".join(fail_labels) if fail_labels else "无",
            "num_steps": traj.num_steps,
        }
        if source_files and i < len(source_files):
            row["file"] = os.path.basename(source_files[i])
        ep = (traj.metadata or {}).get("task_episode_id")
        if ep:
            row["task_episode_id"] = ep
        ac = (traj.metadata or {}).get("acceptance_criteria")
        if ac:
            row["acceptance_criteria"] = ac
        rows.append(row)
    return {
        "report_id": f"tdebug_scan_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "timestamp": _utc_now(),
        "source_dir": str(Path(directory).as_posix()),
        "n_trajectories": len(rows),
        "distribution": dist,
        "distribution_labels": {k: FailureType.LABELS.get(k, k) for k in dist},
        "trajectories": rows,
        "meta": {"tool": "trace-debugger", "note": "启发式失败分类；非 LLM Judge"},
    }


def load_snapshot(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def compare_snapshots(current: dict[str, Any], baseline: dict[str, Any]) -> str:
    """对比两次扫描的失败分布，生成终端报告。"""
    cur_dist = current.get("distribution") or {}
    base_dist = baseline.get("distribution") or {}
    all_types = sorted(set(cur_dist) | set(base_dist))

    lines = [
        "=" * 55,
        "  Trace Debugger — 扫描对比",
        "=" * 55,
        f"  基准: {baseline.get('report_id', '?')} ({baseline.get('timestamp', '?')[:19]})",
        f"        n={baseline.get('n_trajectories', '?')}  dist={base_dist}",
        f"  当前: {current.get('report_id', '?')} ({current.get('timestamp', '?')[:19]})",
        f"        n={current.get('n_trajectories', '?')}  dist={cur_dist}",
        "",
        "  失败类型变化（当前 − 基准）:",
    ]
    if not all_types:
        lines.append("  （两次扫描均未检测到失败类型）")
    else:
        lines.append(f"  {'type':<22} {'base':>5} {'cur':>5} {'delta':>6}  label")
        lines.append("  " + "-" * 50)
        for ft in all_types:
            b = base_dist.get(ft, 0)
            c = cur_dist.get(ft, 0)
            delta = c - b
            sign = "+" if delta > 0 else ""
            label = FailureType.LABELS.get(ft, ft)
            lines.append(f"  {ft:<22} {b:5d} {c:5d} {sign}{delta:5d}  {label}")

    cur_n = current.get("n_trajectories") or 0
    base_n = baseline.get("n_trajectories") or 0
    cur_fail_sessions = sum(1 for r in current.get("trajectories") or [] if r.get("failure_types"))
    base_fail_sessions = sum(1 for r in baseline.get("trajectories") or [] if r.get("failure_types"))
    lines.extend([
        "",
        f"  含失败轨迹数: {base_fail_sessions} → {cur_fail_sessions} "
        f"({cur_fail_sessions - base_fail_sessions:+d})",
        f"  扫描轨迹总数: {base_n} → {cur_n} ({cur_n - base_n:+d})",
        "=" * 55,
    ])
    return "\n".join(lines)
