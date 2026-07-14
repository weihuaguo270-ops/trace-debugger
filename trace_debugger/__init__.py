"""Trace Debugger — Agent 执行轨迹复盘分析工具

读取 Harness 记录的轨迹 JSON，分析 Agent 执行过程中的每一条路径：
  - 哪些路走通了？哪些路走不通？
  - 走不通的原因是什么？（工具报错 / 搜索无结果 / LLM 跑偏 / 超时）
  - 最终方案是否真的可靠？是否遗漏了更好的路？

与 react-agent 框架的关系：
  Agent 执行 → Harness 记录轨迹 JSON → Trace Debugger 读取 → 复盘报告 → 用户决策
"""
__version__ = "0.1.0"

from trace_debugger.analyzer import (
    Analyzer,
    TrajectoryAnalysis,
    PathAnalysis,
    StepAnalysis,
    FailureType,
    failure_distribution,
)
from trace_debugger.reader import Trajectory, Path, Step
from trace_debugger.reporter import format_report, format_json
