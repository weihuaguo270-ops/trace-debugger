"""analyzer — 路径分析与失败原因分类

对轨迹中的每条路径进行深度分析：
  - 工具调用是否成功/失败
  - 搜索是否返回有效结果
  - LLM 是否偏离用户意图（启发式）
  - 上下文是否可能溢出（token / 错误文案）
  - 是否存在重复尝试相同方案
  - 最终方案的可靠性评估
"""
from __future__ import annotations
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Optional

from .reader import Trajectory, Path, Step


# ── 失败分类 ──

class FailureType:
    """失败原因分类"""
    TOOL_ERROR = "tool_error"           # 工具调用报错
    SEARCH_EMPTY = "search_empty"       # 搜索无结果
    SEARCH_TIMEOUT = "search_timeout"   # 搜索超时
    LLM_OFFTRACK = "llm_offtrack"      # LLM 跑偏（答非所问）
    CONTEXT_OVERFLOW = "context_overflow"  # 上下文溢出
    DUPLICATE_ATTEMPT = "duplicate"     # 重复相同尝试
    NO_FINAL_ANSWER = "no_answer"       # 没给出最终答案
    UNKNOWN = "unknown"                 # 无法分类

    LABELS = {
        "tool_error": "工具调用报错",
        "search_empty": "搜索无有效结果",
        "search_timeout": "搜索超时",
        "llm_offtrack": "LLM 偏离用户意图",
        "context_overflow": "上下文窗口溢出",
        "duplicate": "重复相同尝试",
        "no_answer": "未给出最终答案",
        "unknown": "未知原因",
    }


_STOPWORDS = {
    "的", "了", "是", "在", "和", "与", "或", "及", "等", "吗", "呢", "吧", "啊",
    "请", "一下", "一个", "什么", "怎么", "如何", "哪些", "这个", "那个", "可以",
    "需要", "帮我", "给我", "进行", "关于", "一份", "一些",
    "a", "an", "the", "is", "are", "was", "were", "be", "to", "of", "in", "on",
    "for", "and", "or", "what", "which", "how", "who", "why", "when", "where",
    "please", "write", "tell", "me", "my", "your", "with", "from", "that", "this",
}

_OVERFLOW_PATTERNS = (
    r"context\s*(length|window|limit)",
    r"maximum\s*context",
    r"token\s*limit",
    r"too\s*many\s*tokens",
    r"上下文.{0,8}(超|满|溢出|不够|超过)",
    r"(超过|超出).{0,8}(上下文|context|token)",
)


def content_tokens(text: str) -> set[str]:
    """抽取内容词：英文按词；中文按 2/3-gram，避免无空格整句糊成一词。"""
    if not text:
        return set()
    text = text.lower()
    tokens: set[str] = set()
    for p in re.findall(r"[a-zA-Z0-9]{2,}", text):
        if p not in _STOPWORDS:
            tokens.add(p)
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        if 2 <= len(run) <= 4 and run not in _STOPWORDS:
            tokens.add(run)
        for n in (2, 3):
            if len(run) < n:
                continue
            for i in range(len(run) - n + 1):
                gram = run[i : i + n]
                if gram not in _STOPWORDS:
                    tokens.add(gram)
    return tokens


def looks_like_overflow_text(text: str) -> bool:
    if not text:
        return False
    low = text.lower()
    return any(re.search(p, low, flags=re.I) for p in _OVERFLOW_PATTERNS)


def is_search_tool(name: str) -> bool:
    n = (name or "").lower()
    return "search" in n or "搜索" in name


def failure_distribution(analyses: list[TrajectoryAnalysis]) -> dict[str, int]:
    """汇总多条轨迹的失败类型计数。"""
    counts: Counter[str] = Counter()
    for analysis in analyses:
        for pa in analysis.paths:
            for ft in pa.failure_types:
                counts[ft] += 1
    return dict(counts)

# ── 分析结果 ──

@dataclass
class StepAnalysis:
    """单步分析结果"""
    step_index: int
    action: str
    success: bool
    duration: float
    failure_type: str = ""
    failure_detail: str = ""
    suggestion: str = ""


@dataclass
class PathAnalysis:
    """单条路径的分析结果"""
    path_index: int
    num_steps: int
    tools_used: list[str]
    success: bool
    is_main: bool
    has_errors: bool
    failure_types: list[str]
    failure_details: list[str]
    step_analyses: list[StepAnalysis]
    summary: str


@dataclass
class TrajectoryAnalysis:
    """完整分析报告"""
    session_id: str
    query: str
    model: str
    total_duration: float
    total_steps: int
    num_paths: int
    paths: list[PathAnalysis]
    main_path_summary: str
    failed_paths_summary: str
    overall_assessment: str
    needs_fix: bool
    fix_suggestions: list[str]


# ── 分析器 ──

class Analyzer:
    """轨迹分析器

    用法：
        analyzer = Analyzer()
        analysis = analyzer.analyze(trajectory)

    启发式说明：
      - llm_offtrack: 查询内容词与最终答案重叠过低
      - context_overflow: 单步/累计 token 超预算，或观测含溢出文案
    """

    def __init__(
        self,
        *,
        token_budget: int = 8192,
        step_token_warn: int = 4096,
        offtrack_overlap: float = 0.15,
        timeout_seconds: float = 20.0,
    ):
        self.token_budget = token_budget
        self.step_token_warn = step_token_warn
        self.offtrack_overlap = offtrack_overlap
        self.timeout_seconds = timeout_seconds

    def analyze(self, traj: Trajectory) -> TrajectoryAnalysis:
        """分析完整轨迹"""
        path_analyses = []
        for i, path in enumerate(traj.paths):
            pa = self._analyze_path(path, i, traj)
            path_analyses.append(pa)

        main = traj.main_path
        main_summary = self._summarize_main(main, path_analyses) if main else "无主路径"

        failed = traj.failed_paths
        failed_summary = self._summarize_failed(failed, path_analyses) if failed else "无失败路径"

        all_failures = []
        for pa in path_analyses:
            all_failures.extend(pa.failure_details)
        needs_fix = len(all_failures) > 0

        return TrajectoryAnalysis(
            session_id=traj.session_id,
            query=traj.query,
            model=traj.model,
            total_duration=traj.total_duration,
            total_steps=traj.num_steps,
            num_paths=traj.num_paths,
            paths=path_analyses,
            main_path_summary=main_summary,
            failed_paths_summary=failed_summary,
            overall_assessment=self._assess_overall(traj, path_analyses),
            needs_fix=needs_fix,
            fix_suggestions=self._generate_suggestions(traj, path_analyses),
        )

    def _analyze_path(self, path: Path, index: int, traj: Trajectory) -> PathAnalysis:
        """分析单条路径"""
        step_analyses = []
        failure_types = set()
        failure_details = []
        cum_tokens = 0

        for step in path.steps:
            cum_tokens += int(step.tokens or 0)
            sa = self._analyze_step(step, cum_tokens=cum_tokens, traj=traj)
            step_analyses.append(sa)
            if not sa.success and sa.failure_type:
                failure_types.add(sa.failure_type)
                if sa.failure_detail:
                    failure_details.append(f"Step {step.index}: {sa.failure_detail}")

        # 路径级：元数据总 token
        meta_tokens = int((traj.metadata or {}).get("total_tokens_estimated") or 0)
        if meta_tokens >= self.token_budget:
            failure_types.add(FailureType.CONTEXT_OVERFLOW)
            detail = f"轨迹 total_tokens_estimated={meta_tokens} ≥ budget={self.token_budget}"
            failure_details.append(detail)

        # 路径级：重复相同工具调用（相邻步同名同参）
        prev_key = None
        for step in path.steps:
            if not step.is_action:
                continue
            key = (step.action_name, step.action_args.strip())
            if prev_key is not None and key == prev_key and key[0]:
                failure_types.add(FailureType.DUPLICATE_ATTEMPT)
                detail = (
                    f"Step {step.index}: 重复调用 "
                    f"{step.action_name}({step.action_args[:60]})"
                )
                failure_details.append(detail)
                for sa in step_analyses:
                    if sa.step_index == step.index and sa.success:
                        sa.success = False
                        sa.failure_type = FailureType.DUPLICATE_ATTEMPT
                        sa.failure_detail = detail
                        sa.suggestion = "添加状态追踪，避免重复相同尝试"
                        break
            prev_key = key

        # 路径级：未给出最终答案
        has_final_marker = any(s.is_final for s in path.steps)
        has_final_text = bool((path.final_answer or "").strip()) or bool(
            (traj.final_answer or "").strip()
        )
        if path.steps and not has_final_marker and not has_final_text:
            failure_types.add(FailureType.NO_FINAL_ANSWER)
            detail = "路径结束时未给出最终答案"
            failure_details.append(detail)
            last = path.steps[-1]
            for sa in step_analyses:
                if sa.step_index == last.index and sa.success:
                    sa.success = False
                    sa.failure_type = FailureType.NO_FINAL_ANSWER
                    sa.failure_detail = detail
                    sa.suggestion = "确保 Agent 在结束前输出 FINAL ANSWER"
                    break

        # 路径级：llm_offtrack（需有最终答案才比较）
        offtrack = self._detect_offtrack(traj, path)
        if offtrack:
            failure_types.add(FailureType.LLM_OFFTRACK)
            failure_details.append(offtrack)
            # 挂到最后一步
            last = path.steps[-1] if path.steps else None
            if last:
                for sa in step_analyses:
                    if sa.step_index == last.index and sa.success:
                        sa.success = False
                        sa.failure_type = FailureType.LLM_OFFTRACK
                        sa.failure_detail = offtrack
                        sa.suggestion = "在 system prompt 中强化约束，或增加意图校验"
                        break

        path_ok = path.success and FailureType.NO_FINAL_ANSWER not in failure_types
        # offtrack / overflow 视为「完成但有问题」仍可能 path.success=True from parse
        if FailureType.LLM_OFFTRACK in failure_types:
            path_ok = False

        summary_parts = []
        if path_ok and not failure_types:
            summary_parts.append("成功")
        elif path_ok:
            summary_parts.append("完成但有问题")
        else:
            summary_parts.append("失败")
        summary_parts.append(f"{len(path.steps)} 步")
        if path.tools_used:
            summary_parts.append(f"工具: {', '.join(path.tools_used)}")
        if failure_types:
            labels = [FailureType.LABELS.get(ft, ft) for ft in failure_types]
            summary_parts.append(f"问题: {'/'.join(labels)}")

        return PathAnalysis(
            path_index=index,
            num_steps=path.num_steps,
            tools_used=path.tools_used,
            success=path_ok,
            is_main=path.is_main_path,
            has_errors=path.has_errors,
            failure_types=list(failure_types),
            failure_details=failure_details,
            step_analyses=step_analyses,
            summary=" | ".join(summary_parts),
        )

    def _detect_offtrack(self, traj: Trajectory, path: Path) -> str:
        """查询与最终答案内容词重叠过低 → llm_offtrack。"""
        answer = (path.final_answer or traj.final_answer or "").strip()
        if not answer:
            for s in reversed(path.steps):
                if s.is_final:
                    answer = s.thought
                    break
        if not answer or not traj.query.strip():
            return ""

        q_tok = content_tokens(traj.query)
        a_tok = content_tokens(answer)
        # 短查询 / 短答案：关键词重叠启发式假阳性高，跳过
        if len(q_tok) < 2 or len(a_tok) < 2:
            return ""
        if len(answer) < 40 and len(a_tok) < 4:
            return ""

        # 工具已给出有效观测，且答案吸收了观测内容 → 视为 grounded，不打 offtrack
        # （修复「现在几点了 / 算一下」类短问答的假阳性）
        if self._answer_grounded_in_observations(path, a_tok, answer):
            return ""

        # 短事实查询（时间/计算/只要数字）且答案含数字：重叠启发式不可靠
        q = traj.query.strip()
        if re.search(r"(几点|多少|计算|等于|平方|阶乘|沸点|首都)", q) and re.search(
            r"\d", answer
        ):
            return ""

        overlap = len(q_tok & a_tok) / len(q_tok)
        if overlap < self.offtrack_overlap:
            return (
                f"最终答案与用户查询内容词重叠过低 "
                f"({overlap:.0%} < {self.offtrack_overlap:.0%})；"
                f"查询词={sorted(q_tok)[:6]} 答案词样例={sorted(a_tok)[:6]}"
            )
        return ""

    def _answer_grounded_in_observations(
        self, path: Path, a_tok: set[str], answer: str
    ) -> bool:
        obs_parts: list[str] = []
        for step in path.steps:
            obs = (step.observation or "").strip()
            if not obs:
                continue
            low = obs.lower()
            if '"error"' in low or low.startswith("[错误]") or "执行错误" in obs[:40]:
                continue
            obs_parts.append(obs)
        if not obs_parts:
            return False
        obs_text = "\n".join(obs_parts)
        obs_tok = content_tokens(obs_text)
        if obs_tok and a_tok:
            # 答案词有一定比例来自观测
            if len(a_tok & obs_tok) / max(len(a_tok), 1) >= 0.12:
                return True
        # 观测中的数字片段出现在答案里（时间/计算结果）
        for m in re.findall(r"\d{2,}", obs_text):
            if m in answer:
                return True
        return False

    def _analyze_step(
        self,
        step: Step,
        *,
        cum_tokens: int = 0,
        traj: Optional[Trajectory] = None,
    ) -> StepAnalysis:
        """分析单步"""
        failure_type = ""
        failure_detail = ""
        suggestion = ""

        # 上下文溢出：文案或 token
        obs = step.observation or ""
        err = step.error_message or ""
        if looks_like_overflow_text(obs) or looks_like_overflow_text(err):
            failure_type = FailureType.CONTEXT_OVERFLOW
            failure_detail = "观测/错误信息提示上下文或 token 限制"
            suggestion = "压缩上下文或启用摘要/窗口滑动"
        elif step.tokens >= self.step_token_warn:
            failure_type = FailureType.CONTEXT_OVERFLOW
            failure_detail = (
                f"单步 tokens={step.tokens} ≥ 警告阈值 {self.step_token_warn}"
            )
            suggestion = "缩短观测或限制工具返回长度"
        elif cum_tokens >= self.token_budget:
            failure_type = FailureType.CONTEXT_OVERFLOW
            failure_detail = (
                f"累计 tokens≈{cum_tokens} ≥ budget={self.token_budget}"
            )
            suggestion = "压缩上下文或启用摘要/窗口滑动"

        if not failure_type and step.is_action:
            if step.has_error:
                failure_type = FailureType.TOOL_ERROR
                failure_detail = f"{step.action_name} 调用失败: {step.error_message[:100]}"
                suggestion = f"检查 {step.action_name} 的参数或重试"
            elif is_search_tool(step.action_name) and (
                not step.observation or len(step.observation) < 20
            ):
                failure_type = FailureType.SEARCH_EMPTY
                failure_detail = f"搜索 '{step.action_args[:60]}' 无有效结果"
                suggestion = "换搜索词或尝试其他来源"
            elif step.duration > self.timeout_seconds:
                failure_type = FailureType.SEARCH_TIMEOUT
                failure_detail = f"{step.action_name} 耗时 {step.duration:.1f}s"
                suggestion = "考虑限制搜索范围或加缓存"

        return StepAnalysis(
            step_index=step.index,
            action=step.action_name,
            success=not bool(failure_type),
            duration=step.duration,
            failure_type=failure_type,
            failure_detail=failure_detail,
            suggestion=suggestion,
        )

    def _summarize_main(self, main: Path, analyses: list[PathAnalysis]) -> str:
        """生成主路径摘要"""
        for pa in analyses:
            if pa.is_main:
                if pa.success:
                    return f"最终通过 {pa.num_steps} 步完成"
                else:
                    return f"已执行 {pa.num_steps} 步但可能不够理想"
        return ""

    def _summarize_failed(self, failed: list[Path], analyses: list[PathAnalysis]) -> str:
        """生成失败路径摘要"""
        parts = []
        for pa in analyses:
            if pa.is_main:
                continue
            parts.append(f"路径 {pa.path_index}: {pa.summary}")
        return "\n".join(parts) if parts else "无"

    def _assess_overall(self, traj: Trajectory, analyses: list[PathAnalysis]) -> str:
        """总体质量评估"""
        total_failures = sum(
            1 for pa in analyses for sa in pa.step_analyses if not sa.success
        )
        total_steps = sum(pa.num_steps for pa in analyses)
        if total_failures == 0:
            return f"[PASS] 执行顺利，{total_steps} 步无错误"
        elif total_failures <= total_steps * 0.3:
            return f"[WARN] 有少量问题（{total_failures}/{total_steps} 步），可考虑优化"
        else:
            return f"[FAIL] 执行问题较多（{total_failures}/{total_steps} 步），建议检查"

    def _generate_suggestions(self, traj: Trajectory, analyses: list[PathAnalysis]) -> list[str]:
        """生成修复建议"""
        suggestions = []
        seen_types = set()
        for pa in analyses:
            for ft in pa.failure_types:
                if ft not in seen_types:
                    seen_types.add(ft)
                    label = FailureType.LABELS.get(ft, ft)
                    suggestions.append(f"修复 {label}：{self._suggestion_for(ft)}")
        return suggestions

    def _suggestion_for(self, failure_type: str) -> str:
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
