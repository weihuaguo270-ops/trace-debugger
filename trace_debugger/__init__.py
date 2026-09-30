"""Trace Debugger — Agent 轨迹失败检测与规则回归

读取 Agent Trajectory (Format B) JSON，分析执行过程中的失败行为：
  - 8 类启发式失败分类 + 步骤证据链
  - JSONL / 可读日志 / 会话摘要
  - failure-gate/v1 导出（供 llm-eval-engine）
  - 运行时 StepWatcher（可嵌入任意 Harness）

Schema: schemas/agent_trajectory.schema.json
集成: docs/INTEGRATIONS.md · 分工: docs/POSITIONING_AND_DIVISION.md
"""
__version__ = "0.6.0"

from trace_debugger.analyzer import (
    Analyzer,
    TrajectoryAnalysis,
    PathAnalysis,
    StepAnalysis,
    FailureType,
    failure_distribution,
    is_final_thought,
    is_search_tool,
    looks_cross_language,
    script_profile,
)
from trace_debugger.reader import Trajectory, Path, Step
from trace_debugger.reporter import format_report, format_json, build_judge_prompt, analysis_to_dict
from trace_debugger.record import (
    append_failure_events,
    append_events,
    build_scan_snapshot,
    build_failures_export,
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
from trace_debugger.harness_health import (
    build_findings_report,
    evaluate_regression_gate,
    probe_project_mechanisms,
    should_fail_on_gate,
)
from trace_debugger.verification import (
    build_verification_ref,
    fixture_coverage,
    known_case_ids,
    validate_findings_report,
)
from trace_debugger.adjudication import (
    build_key,
    build_sheet,
    score_sheet,
    format_score,
)
from trace_debugger.profiles import resolve_analyzer, PROFILE_NAMES
from trace_debugger.evidence import EvidenceItem, evidence_chain_from_analysis
from trace_debugger.golden import (
    load_manifest,
    run_golden_suite,
    run_false_positive_suite,
    GoldenCase,
)
from trace_debugger.validate import (
    format_validation_report,
    validate_trajectory_dict,
    validate_trajectory_file,
)
from trace_debugger.episode import (
    EPISODE_SCHEMA_VERSION,
    ImportedEpisode,
    import_evaluation_episode,
)
from trace_debugger.adapters import (
    openai_messages_to_trajectory,
    anthropic_messages_to_trajectory,
    openai_responses_to_trajectory,
    chat_stream_to_trajectory,
    coalesce_chat_completion_chunks,
    IncompleteStreamError,
)
