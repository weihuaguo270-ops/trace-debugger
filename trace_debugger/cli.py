"""Trace Debugger CLI"""
from __future__ import annotations
import json
import os
import sys

from .reader import load, load_recent_paths
from .analyzer import Analyzer, FailureType, failure_distribution
from .reporter import format_report, format_json, build_judge_prompt
from .record import (
    DEFAULT_RECORD_PATH,
    append_failure_events,
    build_scan_snapshot,
    compare_snapshots,
    load_snapshot,
    format_failures_digest,
    format_failure_stats,
    failure_stats_from_log,
)
from .validate import format_validation_report, validate_trajectory_file


def main():
    """CLI 入口"""
    argv = sys.argv[1:]
    if not argv:
        print("用法: tdebug <轨迹.json> | replay <轨迹.json> | scan <目录> | judge <轨迹.json>")
        print("      tdebug -h  查看帮助")
        sys.exit(1)

    if argv[0] in ("-h", "--help"):
        _print_help()
        return

    cmd = argv[0]

    if cmd == "replay":
        rest = argv[1:]
        if not rest:
            print("用法: tdebug replay <轨迹.json>")
            sys.exit(1)
        _cmd_replay(rest[0])
    elif cmd == "judge":
        filepath, flags = _parse_analyze_args(argv[1:])
        _cmd_judge(filepath, flags)
    elif cmd == "scan":
        directory, n, flags = _parse_scan_args(argv[1:])
        _cmd_scan(directory, n, flags)
    elif cmd == "failures":
        rest, flags = _parse_flags(argv[1:])
        record_path = rest[0] if rest else flags.get("json_out", DEFAULT_RECORD_PATH)
        session = flags.get("session") or None
        if flags.get("stats"):
            _safe_print(format_failure_stats(record_path, session_id=session))
            if flags.get("stats_json_out"):
                stats = failure_stats_from_log(record_path, session_id=session)
                _write_text(flags["stats_json_out"], json.dumps(stats, ensure_ascii=False, indent=2))
                print(f"\n[已写入统计 JSON] {flags['stats_json_out']}")
        else:
            _safe_print(format_failures_digest(record_path, session_id=session))
    elif cmd == "stats":
        rest, flags = _parse_flags(argv[1:])
        record_path = rest[0] if rest else DEFAULT_RECORD_PATH
        session = flags.get("session") or None
        _safe_print(format_failure_stats(record_path, session_id=session))
        if flags.get("stats_json_out"):
            stats = failure_stats_from_log(record_path, session_id=session)
            _write_text(flags["stats_json_out"], json.dumps(stats, ensure_ascii=False, indent=2))
            print(f"\n[已写入统计 JSON] {flags['stats_json_out']}")
    elif cmd == "validate":
        filepath, flags = _parse_analyze_args(argv[1:])
        _cmd_validate(filepath, flags)
    elif cmd.endswith(".json"):
        filepath, flags = _parse_analyze_args(argv)
        _cmd_analyze(filepath, flags)
    else:
        print(f"未知命令: {cmd}")
        _print_help()
        sys.exit(1)


def _print_help():
    print("Trace Debugger — Agent 执行轨迹复盘分析工具")
    print()
    print("用法:")
    print("  tdebug <file.json> [选项]         复盘单条轨迹")
    print("  tdebug replay <file.json>         逐步骤回放")
    print("  tdebug judge <file.json> [选项]   生成 LLM Judge 分析 prompt")
    print("  tdebug failures [jsonl] [选项]    失败 digest 或 --stats 聚合统计")
    print("  tdebug stats [jsonl] [选项]       按失败类型聚合（同 failures --stats）")
    print("  tdebug validate <轨迹.json> [选项]  校验 Format B（可选 jsonschema）")
    print("  tdebug scan <directory> [N] [选项]  扫描最新 N 条轨迹")
    print()
    print("选项（analyze / judge）:")
    print("  --json-out PATH    写入结构化 JSON 分析结果")
    print("  --record [PATH]    追加失败事件到 JSONL（默认 .tdebug/failures.jsonl）")
    print("  --prompt-out PATH  judge 模式：将 prompt 写入文件")
    print("  --session ID       failures/stats：只统计指定 session")
    print("  --stats            failures 模式：输出聚合统计而非明细")
    print("  --stats-json-out PATH  将聚合统计写入 JSON")
    print()
    print("选项（validate）:")
    print("  --schema           使用 jsonschema 严格校验（需 pip install trace-debugger[schema]）")
    print()
    print("选项（scan）:")
    print("  --json-out PATH    写入扫描快照 JSON（可归档、可对比）")
    print("  --findings-out PATH  写入 Harness Health findings.json（需 --compare 时含门禁判定）")
    print("  --project-root PATH  探测项目机制（golden/baseline/ledger）用于 findings")
    print("  --record [PATH]    为每条轨迹追加失败事件到 JSONL")
    print("  --compare PATH     与历史快照对比失败分布变化")
    print()
    print("示例:")
    print("  tdebug traj.json --json-out report.json --record")
    print("  tdebug judge traj.json --prompt-out judge.txt")
    print("  tdebug failures .tdebug/failures.jsonl --stats --stats-json-out stats.json")


def _parse_flags(args: list[str]) -> tuple[list[str], dict]:
    positional: list[str] = []
    flags: dict = {}
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--json-out" and i + 1 < len(args):
            flags["json_out"] = args[i + 1]
            i += 2
        elif a == "--record":
            if i + 1 < len(args) and not args[i + 1].startswith("-"):
                flags["record"] = args[i + 1]
                i += 2
            else:
                flags["record"] = DEFAULT_RECORD_PATH
                i += 1
        elif a == "--compare" and i + 1 < len(args):
            flags["compare"] = args[i + 1]
            i += 2
        elif a == "--findings-out" and i + 1 < len(args):
            flags["findings_out"] = args[i + 1]
            i += 2
        elif a == "--project-root" and i + 1 < len(args):
            flags["project_root"] = args[i + 1]
            i += 2
        elif a == "--prompt-out" and i + 1 < len(args):
            flags["prompt_out"] = args[i + 1]
            i += 2
        elif a == "--session" and i + 1 < len(args):
            flags["session"] = args[i + 1]
            i += 2
        elif a == "--stats":
            flags["stats"] = True
            i += 1
        elif a == "--schema":
            flags["schema"] = True
            i += 1
        elif a == "--stats-json-out" and i + 1 < len(args):
            flags["stats_json_out"] = args[i + 1]
            i += 2
        elif a.startswith("-"):
            print(f"未知选项: {a}")
            sys.exit(1)
        else:
            positional.append(a)
            i += 1
    return positional, flags


def _parse_analyze_args(args: list[str]) -> tuple[str, dict]:
    positional, flags = _parse_flags(args)
    if not positional:
        print("缺少轨迹 JSON 文件路径")
        sys.exit(1)
    return positional[0], flags


def _parse_scan_args(args: list[str]) -> tuple[str, int, dict]:
    positional, flags = _parse_flags(args)
    if not positional:
        print("用法: tdebug scan <directory> [N]")
        sys.exit(1)
    directory = positional[0]
    n = 5
    if len(positional) >= 2:
        try:
            n = int(positional[1])
        except ValueError:
            print(f"无效的 N: {positional[1]}")
            sys.exit(1)
    return directory, n, flags


def _safe_print(text: str) -> None:
    """Avoid UnicodeEncodeError on Windows GBK consoles."""
    try:
        print(text)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(text.encode(enc, errors="replace").decode(enc, errors="replace"))


def _write_text(path: str, content: str) -> None:
    out = os.path.dirname(path)
    if out:
        os.makedirs(out, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _analyze_file(filepath: str) -> tuple:
    if not os.path.exists(filepath):
        print(f"文件不存在: {filepath}")
        sys.exit(1)
    traj = load(filepath)
    analysis = Analyzer().analyze(traj)
    return traj, analysis


def _cmd_analyze(filepath: str, flags: dict):
    _, analysis = _analyze_file(filepath)
    _safe_print(format_report(analysis))

    if flags.get("json_out"):
        _write_text(flags["json_out"], format_json(analysis))
        print(f"\n[已写入 JSON] {flags['json_out']}")

    if flags.get("record"):
        n = append_failure_events(analysis, flags["record"], source_file=filepath)
        if n:
            print(f"[已记录 {n} 条失败事件] {flags['record']}")


def _cmd_judge(filepath: str, flags: dict):
    _, analysis = _analyze_file(filepath)
    prompt = build_judge_prompt(analysis)

    if flags.get("prompt_out"):
        _write_text(flags["prompt_out"], prompt)
        print(f"[已写入 Judge prompt] {flags['prompt_out']}")
    else:
        _safe_print(prompt)

    if flags.get("json_out"):
        _write_text(flags["json_out"], format_json(analysis))
        print(f"[已写入 JSON] {flags['json_out']}")

    if flags.get("record"):
        n = append_failure_events(analysis, flags["record"], source_file=filepath)
        if n:
            print(f"[已记录 {n} 条失败事件] {flags['record']}")


def _cmd_validate(filepath: str, flags: dict):
    errors = validate_trajectory_file(filepath, use_schema=bool(flags.get("schema")))
    _safe_print(format_validation_report(errors, path=filepath))
    if errors:
        sys.exit(1)


def _cmd_replay(filepath: str):
    if not os.path.exists(filepath):
        print(f"文件不存在: {filepath}")
        sys.exit(1)

    traj = load(filepath)

    print("=" * 55)
    print("  Trace Debugger — 回放模式")
    print(f"  查询: {traj.query[:80]}")
    print("=" * 55)

    for step in traj.steps:
        input(f"\n按 Enter 查看 Step {step.index}...")
        print(f"\n--- Step {step.index} ---")
        if step.thought:
            print(f"  [思考] {step.thought[:300]}")
        if step.action_name:
            print(f"  [工具] {step.action_name}")
            if step.action_args:
                print(f"  [参数] {step.action_args[:200]}")
        if step.observation:
            print(f"  [返回] {step.observation[:300]}")
        if step.has_error:
            print(f"  [错误] {step.error_message[:200]}")
        print(f"  [耗时] {step.duration:.2f}s")

    print(f"\n最终答案: {traj.final_answer[:200]}")
    print("回放完成。")


def _cmd_scan(directory: str, n: int, flags: dict):
    if not os.path.exists(directory):
        print(f"目录不存在: {directory}")
        sys.exit(1)

    trajs, source_files = load_recent_paths(directory, n)
    if not trajs:
        print(f"目录中没有轨迹 JSON 文件: {directory}")
        return

    print("=" * 55)
    print("  Trace Debugger — 扫描结果")
    print(f"  目录: {directory}")
    print(f"  最近 {len(trajs)} 条轨迹")
    print("=" * 55)

    analyses = []
    record_path = flags.get("record")
    total_recorded = 0

    for i, traj in enumerate(trajs):
        analysis = Analyzer().analyze(traj)
        analyses.append(analysis)
        icon = "[PASS]" if "无错误" in analysis.overall_assessment else "[WARN]"
        fails = sorted({ft for pa in analysis.paths for ft in pa.failure_types})
        fail_s = ",".join(fails) if fails else "-"
        print(f"\n  [{i+1}] {icon} {traj.session_id}")
        print(f"      {traj.query[:80]}")
        print(f"      {traj.total_duration:.1f}s / {traj.num_steps} 步 / {traj.model}")
        print(f"      {analysis.overall_assessment}")
        print(f"      失败类型: {fail_s}")

        if record_path:
            src = source_files[i] if i < len(source_files) else ""
            total_recorded += append_failure_events(analysis, record_path, source_file=src)

    dist = failure_distribution(analyses)
    print("\n" + "-" * 55)
    print("  失败类型分布（路径级计数）")
    if not dist:
        print("  （无检测到失败类型）")
    else:
        for ft, cnt in sorted(dist.items(), key=lambda x: (-x[1], x[0])):
            label = FailureType.LABELS.get(ft, ft)
            print(f"  {ft:20s} {cnt:3d}  ({label})")
    print("=" * 55)

    snapshot = build_scan_snapshot(directory, n, trajs, analyses, source_files=source_files)

    if flags.get("json_out"):
        _write_text(flags["json_out"], json.dumps(snapshot, ensure_ascii=False, indent=2))
        print(f"\n[已写入扫描快照] {flags['json_out']}")

    if record_path and total_recorded:
        print(f"[已记录 {total_recorded} 条失败事件] {record_path}")

    if flags.get("compare"):
        if not os.path.exists(flags["compare"]):
            print(f"对比基准不存在: {flags['compare']}")
            sys.exit(1)
        baseline = load_snapshot(flags["compare"])
        _safe_print("\n" + compare_snapshots(snapshot, baseline))
        gate = evaluate_regression_gate(snapshot, baseline)
        _safe_print(f"\n  门禁判定: {gate['decision'].upper()}  触发规则: {gate['triggered_rules'] or '无'}")

    if flags.get("findings_out"):
        baseline = None
        if flags.get("compare") and os.path.exists(flags["compare"]):
            baseline = load_snapshot(flags["compare"])
        project_root = flags.get("project_root") or os.getcwd()
        findings = build_findings_report(
            snapshot, baseline, project_root=project_root,
        )
        _write_text(flags["findings_out"], json.dumps(findings, ensure_ascii=False, indent=2))
        print(f"\n[已写入 findings] {flags['findings_out']}  gate={findings['gate_decision']}")
