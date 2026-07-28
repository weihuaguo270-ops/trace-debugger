"""Trace Debugger — Agent 执行轨迹复盘分析工具

读取 Harness 记录的轨迹 JSON，分析 Agent 执行过程中的每一条路径：
  - 哪些路走通了？哪些路走不通？
  - 走不通的原因是什么？（工具报错 / 搜索无结果 / LLM 跑偏 / 超时）
  - 最终方案是否真的可靠？是否遗漏了更好的路？

与 react-agent 框架的关系：
  Agent 执行 → Harness StepWatcher（实时）→ 失败 JSONL + 轨迹 JSON → Trace Debugger 复盘
"""
__version__ = "0.2.1"

from trace_debugger.analyzer import (
    Analyzer,
    TrajectoryAnalysis,
    PathAnalysis,
    StepAnalysis,
    FailureType,
    failure_distribution,
)
from trace_debugger.reader import Trajectory, Path, Step
from trace_debugger.reporter import format_report, format_json, build_judge_prompt, analysis_to_dict
from trace_debugger.record import (
    append_failure_events,
    append_events,
    build_scan_snapshot,
    compare_snapshots,
    step_failure_event,
    format_failure_stats,
    failure_stats_from_log,
    aggregate_failure_stats,
    DEFAULT_RECORD_PATH,
)
from trace_debugger.runtime import StepWatcher, failure_tags_from_step
from trace_debugger.golden import load_manifest, run_golden_suite, GoldenCase
