"""Trace Debugger — Agent 轨迹失败治理

读取 Agent Trajectory (Format B) JSON，分析执行过程中的失败行为：
  - 7 类启发式失败分类
  - JSONL / 可读日志 / 会话摘要
  - 运行时 StepWatcher（可嵌入任意 Harness）

Schema: schemas/agent_trajectory.schema.json
集成: docs/INTEGRATIONS.md（含 react-agent 参考集成）
"""
__version__ = "0.2.3"

from trace_debugger.analyzer import (
    Analyzer,
    TrajectoryAnalysis,
    PathAnalysis,
    StepAnalysis,
    FailureType,
    failure_distribution,
    is_final_thought,
    is_search_tool,
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
    resolve_record_path,
)
from trace_debugger.runtime import StepWatcher, failure_tags_from_step
from trace_debugger.harness import (
    FailureHarness,
    RunContext,
    StepEvent,
    SCHEMA_PATH,
    analyze_trajectory_dict,
    build_trajectory_dict,
    enrich_trajectory_dict,
    normalize_tool_input,
)
from trace_debugger.golden import load_manifest, run_golden_suite, GoldenCase
from trace_debugger.validate import (
    format_validation_report,
    validate_trajectory_dict,
    validate_trajectory_file,
)
