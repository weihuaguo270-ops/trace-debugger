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
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Optional

from .evidence import EvidenceItem, evidence
from .reader import Trajectory, Path, Step
from .tool_contracts import check_tool_contract, merge_contracts


# ── 失败分类 ──

class FailureType:
    """失败原因分类"""
    TOOL_ERROR = "tool_error"           # 工具调用报错
    ACCEPTANCE_FAILED = "acceptance_failed"  # 验收测试失败
    APPROVAL_DENIED = "approval_denied"  # MCP / 策略批准被拒绝
    INCOMPLETE_STREAM = "incomplete_stream"  # 半截流 / in_progress 打标
    SEARCH_EMPTY = "search_empty"       # 搜索无结果
    SEARCH_WEAK = "search_weak"         # 有结果但缺 url/title 等结构（非语义质量）
    SEARCH_TIMEOUT = "search_timeout"   # 搜索超时
    LLM_OFFTRACK = "llm_offtrack"      # LLM 跑偏（答非所问）
    CONTEXT_OVERFLOW = "context_overflow"  # 上下文溢出
    DUPLICATE_ATTEMPT = "duplicate"     # 重复相同尝试
    NO_FINAL_ANSWER = "no_answer"       # 没给出最终答案
    UNKNOWN = "unknown"                 # 无法分类

    LABELS = {
        "tool_error": "工具调用报错",
        "acceptance_failed": "验收测试失败",
        "approval_denied": "批准被拒绝",
        "incomplete_stream": "半截流/未完成",
        "search_empty": "搜索无有效结果",
        "search_weak": "搜索结果结构过弱",
        "search_timeout": "搜索超时",
        "llm_offtrack": "LLM 偏离用户意图",
        "context_overflow": "上下文窗口溢出",
        "duplicate": "重复相同尝试",
        "no_answer": "未给出最终答案",
        "unknown": "未知原因",
    }


def _is_approval_denied(action_name: str, observation: str, error_message: str) -> bool:
    """MCP / policy approval denied (not a generic tool crash)."""
    name = (action_name or "").lower()
    blob = f"{observation or ''}\n{error_message or ''}".lower()
    if "mcp approval denied" in blob or "responses.mcp.approval_denied" in blob:
        return True
    return "mcp_approval_response" in name and (
        "approval denied" in blob or "approve=false" in blob.replace(" ", "")
    )


def _is_incomplete_stream(action_name: str, observation: str, error_message: str) -> bool:
    """Marked half-finished stream / Responses in_progress item."""
    name = (action_name or "").lower()
    blob = f"{observation or ''}\n{error_message or ''}".lower()
    if "responses.incomplete" in blob or "incomplete stream" in blob:
        return True
    return name == "incomplete_stream"


def _parse_json_blob(text: str) -> Any:
    raw = (text or "").strip()
    if not raw or raw[0] not in "{[":
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def extract_search_result_items(observation: str) -> Optional[list[Any]]:
    """If observation is JSON with a ``results`` list (or is a list), return it.

    Returns ``None`` when the observation is not structured search payload
    (plain text stays on the short-obs ``search_empty`` path).
    """
    data = _parse_json_blob(observation)
    if data is None:
        return None
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return None
    for key in ("results", "items", "organic", "web_results"):
        if key in data and isinstance(data[key], list):
            return data[key]
    nested = data.get("output") or data.get("data") or data.get("response")
    if isinstance(nested, dict):
        for key in ("results", "items"):
            if key in nested and isinstance(nested[key], list):
                return nested[key]
    if isinstance(nested, list):
        return nested
    # Explicit empty results key
    if "results" in data and data["results"] is None:
        return []
    return None


def _hit_has_url(hit: Any) -> bool:
    if not isinstance(hit, dict):
        return False
    for key in ("url", "link", "href", "source_url", "permalink"):
        val = hit.get(key)
        if isinstance(val, str) and val.strip():
            return True
        if isinstance(val, dict) and (val.get("url") or val.get("href")):
            return True
    return False


def _hit_has_title(hit: Any) -> bool:
    if not isinstance(hit, dict):
        return False
    for key in ("title", "name", "headline"):
        val = hit.get(key)
        if isinstance(val, str) and val.strip():
            return True
    return False


def search_hit_structurally_ok(
    hit: Any,
    *,
    require_url: bool = False,
    require_title: bool = False,
) -> bool:
    """Structural usability only — no relevance / quality judging."""
    if not isinstance(hit, dict):
        return False
    if require_url and not _hit_has_url(hit):
        return False
    if require_title and not _hit_has_title(hit):
        return False
    # If neither required, still treat "no url and no title" as unusable
    if not require_url and not require_title:
        return _hit_has_url(hit) or _hit_has_title(hit)
    return True


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
    """按已知中英文服务错误文案识别上下文溢出信号。"""
    if not text:
        return False
    low = text.lower()
    return any(re.search(p, low, flags=re.I) for p in _OVERFLOW_PATTERNS)


def is_search_tool(name: str, *, substrings: tuple[str, ...] = ("search",), extra_names: tuple[str, ...] = ()) -> bool:
    """按可配置名称规则判断工具是否属于搜索类。"""
    n = (name or "").lower()
    if any(sub in n for sub in substrings):
        return True
    if "搜索" in (name or ""):
        return True
    return (name or "") in extra_names or n in {x.lower() for x in extra_names}


def _responses_structured_error_rule(
    action_name: str,
    observation: str,
    error_message: str,
) -> str:
    """Pick evidence rule_id for Responses computer/shell structured failures."""
    name = (action_name or "").lower()
    blob = f"{observation or ''}\n{error_message or ''}"
    blob_l = blob.lower()
    if "responses.protocol.mcp_list_tools" in blob_l:
        return "responses.protocol.mcp_list_tools"
    if "responses.shell.nonzero_exit" in blob_l or (
        "shell" in name and "exit_code=" in blob_l
    ):
        return "responses.shell.nonzero_exit"
    if "computer" in name or "responses.computer.failed" in blob_l:
        return "responses.computer.failed"
    if "shell" in name or "responses.shell.failed" in blob_l:
        return "responses.shell.failed"
    return "heuristic.tool_error"


def is_final_thought(thought: str, markers: tuple[str, ...]) -> bool:
    """按调用方提供的大小写不敏感标记识别终答思考。"""
    upper = (thought or "").upper()
    return any(m.upper() in upper for m in markers if m)


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
    evidence: list[EvidenceItem] = field(default_factory=list)


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
        enable_offtrack: bool = True,
        timeout_seconds: float = 20.0,
        final_answer_markers: tuple[str, ...] = ("FINAL ANSWER",),
        search_tool_substrings: tuple[str, ...] = ("search",),
        search_tool_names: tuple[str, ...] = (),
        search_min_results: int = 0,
        search_require_url: bool = False,
        search_require_title: bool = False,
        enable_tool_contracts: bool = False,
        tool_contracts: Optional[dict[str, Any]] = None,
        task_type: str = "default",
    ):
        self.token_budget = token_budget
        self.step_token_warn = step_token_warn
        self.offtrack_overlap = offtrack_overlap
        self.enable_offtrack = enable_offtrack
        self.timeout_seconds = timeout_seconds
        self.final_answer_markers = final_answer_markers
        self.search_tool_substrings = search_tool_substrings
        self.search_tool_names = search_tool_names
        self.search_min_results = int(search_min_results or 0)
        self.search_require_url = bool(search_require_url)
        self.search_require_title = bool(search_require_title)
        self.enable_tool_contracts = enable_tool_contracts
        self.tool_contracts = merge_contracts(tool_contracts) if enable_tool_contracts else {}
        self.task_type = task_type or "default"

    @property
    def search_structure_checks_enabled(self) -> bool:
        """True when configurable structural search rules are active."""
        return (
            self.search_min_results > 0
            or self.search_require_url
            or self.search_require_title
        )

    def step_is_final(self, step: Step) -> bool:
        """按当前分析器终答标记判断步骤。"""
        return is_final_thought(step.thought, self.final_answer_markers)

    def tool_is_search(self, name: str) -> bool:
        """按当前分析器搜索工具配置判断名称。"""
        return is_search_tool(
            name,
            substrings=self.search_tool_substrings,
            extra_names=self.search_tool_names,
        )

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
            if step_analyses:
                step_analyses[-1].evidence.append(
                    evidence(
                        "heuristic.context_overflow.meta",
                        detail,
                        excerpt=str(meta_tokens),
                        step_index=step_analyses[-1].step_index,
                        path_index=index,
                        failure_type=FailureType.CONTEXT_OVERFLOW,
                    )
                )

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
                        sa.evidence.append(
                            evidence(
                                "heuristic.duplicate.adjacent",
                                detail,
                                excerpt=f"{step.action_name}({step.action_args[:80]})",
                                step_index=step.index,
                                path_index=index,
                                failure_type=FailureType.DUPLICATE_ATTEMPT,
                            )
                        )
                        break
            prev_key = key

        # 路径级：未给出最终答案
        has_final_marker = any(self.step_is_final(s) for s in path.steps)
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
                    sa.evidence.append(
                        evidence(
                            "heuristic.no_answer",
                            detail,
                            step_index=last.index,
                            path_index=index,
                            failure_type=FailureType.NO_FINAL_ANSWER,
                        )
                    )
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
                        sa.evidence.append(
                            evidence(
                                "heuristic.llm_offtrack.overlap",
                                offtrack,
                                excerpt=(traj.query or "")[:80],
                                step_index=last.index,
                                path_index=index,
                                failure_type=FailureType.LLM_OFFTRACK,
                            )
                        )
                        break

        path_ok = path.success and FailureType.NO_FINAL_ANSWER not in failure_types
        # offtrack / overflow 视为「完成但有问题」仍可能 path.success=True from parse
        if FailureType.LLM_OFFTRACK in failure_types:
            path_ok = False
        if FailureType.ACCEPTANCE_FAILED in failure_types:
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
        if not self.enable_offtrack:
            return ""
        answer = (path.final_answer or traj.final_answer or "").strip()
        if not answer:
            for s in reversed(path.steps):
                if self.step_is_final(s):
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

    def analyze_step(
        self,
        step: Step,
        *,
        cum_tokens: int = 0,
        traj: Optional[Trajectory] = None,
    ) -> StepAnalysis:
        """分析单步（供运行时 StepWatcher 调用）。"""
        return self._analyze_step(step, cum_tokens=cum_tokens, traj=traj)

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
        ev: list[EvidenceItem] = []

        # 上下文溢出：文案或 token
        obs = step.observation or ""
        err = step.error_message or ""
        if looks_like_overflow_text(obs) or looks_like_overflow_text(err):
            failure_type = FailureType.CONTEXT_OVERFLOW
            failure_detail = "观测/错误信息提示上下文或 token 限制"
            suggestion = "压缩上下文或启用摘要/窗口滑动"
            ev.append(
                evidence(
                    "heuristic.context_overflow.text",
                    failure_detail,
                    excerpt=(err or obs)[:120],
                    step_index=step.index,
                    failure_type=failure_type,
                )
            )
        elif step.tokens >= self.step_token_warn:
            failure_type = FailureType.CONTEXT_OVERFLOW
            failure_detail = (
                f"单步 tokens={step.tokens} ≥ 警告阈值 {self.step_token_warn}"
            )
            suggestion = "缩短观测或限制工具返回长度"
            ev.append(
                evidence(
                    "heuristic.context_overflow.step_tokens",
                    failure_detail,
                    excerpt=str(step.tokens),
                    step_index=step.index,
                    failure_type=failure_type,
                )
            )
        elif cum_tokens >= self.token_budget:
            failure_type = FailureType.CONTEXT_OVERFLOW
            failure_detail = (
                f"累计 tokens≈{cum_tokens} ≥ budget={self.token_budget}"
            )
            suggestion = "压缩上下文或启用摘要/窗口滑动"
            ev.append(
                evidence(
                    "heuristic.context_overflow.cum_tokens",
                    failure_detail,
                    excerpt=str(cum_tokens),
                    step_index=step.index,
                    failure_type=failure_type,
                )
            )

        if not failure_type and step.is_action and self.enable_tool_contracts:
            violation = check_tool_contract(
                step.action_name, step.action_args, self.tool_contracts,
            )
            if violation:
                failure_type = FailureType.TOOL_ERROR
                failure_detail = violation["signal"]
                suggestion = f"按 tool contract 补齐 {step.action_name} 参数"
                ev.append(
                    evidence(
                        violation["rule_id"],
                        violation["signal"],
                        excerpt=violation.get("excerpt", ""),
                        step_index=step.index,
                        failure_type=failure_type,
                    )
                )

        if not failure_type and step.is_action:
            observation = (step.observation or "").strip().lower()
            if step.action_name in {
                "run_acceptance_tests",
                "run_tests",
                "pytest",
            } and observation in {"failed", "test_failed", "failure"}:
                failure_type = FailureType.ACCEPTANCE_FAILED
                failure_detail = f"{step.action_name} 返回验收失败"
                suggestion = "保留失败测试输出，修复候选变更后重新执行验收"
                ev.append(
                    evidence(
                        "heuristic.acceptance_failed",
                        failure_detail,
                        excerpt=observation[:80],
                        step_index=step.index,
                        failure_type=failure_type,
                    )
                )
            elif step.has_error and _is_incomplete_stream(
                step.action_name, step.observation, step.error_message
            ):
                failure_type = FailureType.INCOMPLETE_STREAM
                failure_detail = (
                    f"半截流/未完成: "
                    f"{(step.error_message or step.observation or '')[:100]}"
                )
                suggestion = "使用完整 finish_reason / completed 导出，或仅在 CI 调试时 on_incomplete=mark"
                ev.append(
                    evidence(
                        "responses.incomplete",
                        failure_detail,
                        excerpt=(step.error_message or step.observation or "")[:120],
                        step_index=step.index,
                        failure_type=failure_type,
                    )
                )
            elif step.has_error and _is_approval_denied(
                step.action_name, step.observation, step.error_message
            ):
                failure_type = FailureType.APPROVAL_DENIED
                failure_detail = (
                    f"{step.action_name} 批准被拒绝: "
                    f"{(step.error_message or step.observation or '')[:100]}"
                )
                suggestion = "检查 MCP/策略审批策略，或改用不需批准的工具路径"
                ev.append(
                    evidence(
                        "responses.mcp.approval_denied",
                        failure_detail,
                        excerpt=(step.error_message or step.observation or "")[:120],
                        step_index=step.index,
                        failure_type=failure_type,
                    )
                )
            elif step.has_error:
                failure_type = FailureType.TOOL_ERROR
                failure_detail = f"{step.action_name} 调用失败: {step.error_message[:100]}"
                suggestion = f"检查 {step.action_name} 的参数或重试"
                rule_id = _responses_structured_error_rule(
                    step.action_name, step.observation, step.error_message,
                )
                ev.append(
                    evidence(
                        rule_id,
                        failure_detail,
                        excerpt=(step.error_message or step.observation or "")[:120],
                        step_index=step.index,
                        failure_type=failure_type,
                    )
                )
            elif self.tool_is_search(step.action_name):
                obs = (step.observation or "").strip()
                hits = extract_search_result_items(obs)
                # Empty / tiny text, or structured results=[]
                if (not obs or len(obs) < 20) or (hits is not None and len(hits) == 0):
                    failure_type = FailureType.SEARCH_EMPTY
                    failure_detail = f"搜索 '{step.action_args[:60]}' 无有效结果"
                    suggestion = "换搜索词或尝试其他来源"
                    rule_id = (
                        "heuristic.search_empty.results"
                        if hits is not None and len(hits) == 0
                        else "heuristic.search_empty"
                    )
                    ev.append(
                        evidence(
                            rule_id,
                            failure_detail,
                            excerpt=obs[:80],
                            step_index=step.index,
                            failure_type=failure_type,
                        )
                    )
                elif self.search_structure_checks_enabled and hits is not None:
                    usable = [
                        h
                        for h in hits
                        if search_hit_structurally_ok(
                            h,
                            require_url=self.search_require_url,
                            require_title=self.search_require_title,
                        )
                    ]
                    need = self.search_min_results if self.search_min_results > 0 else 1
                    if len(usable) < need:
                        failure_type = FailureType.SEARCH_WEAK
                        failure_detail = (
                            f"搜索 '{step.action_args[:60]}' 有 {len(hits)} 条结果但"
                            f"结构过弱（可用 {len(usable)} < {need}；"
                            f"require_url={self.search_require_url}）"
                        )
                        suggestion = "检查检索工具是否返回 url/title；勿做语义垃圾评判"
                        ev.append(
                            evidence(
                                "heuristic.search_weak.structure",
                                failure_detail,
                                excerpt=obs[:120],
                                step_index=step.index,
                                failure_type=failure_type,
                            )
                        )
                    elif step.duration > self.timeout_seconds:
                        failure_type = FailureType.SEARCH_TIMEOUT
                        failure_detail = f"{step.action_name} 耗时 {step.duration:.1f}s"
                        suggestion = "考虑限制搜索范围或加缓存"
                        ev.append(
                            evidence(
                                "heuristic.search_timeout",
                                failure_detail,
                                excerpt=f"{step.duration:.1f}s",
                                step_index=step.index,
                                failure_type=failure_type,
                            )
                        )
                elif step.duration > self.timeout_seconds:
                    failure_type = FailureType.SEARCH_TIMEOUT
                    failure_detail = f"{step.action_name} 耗时 {step.duration:.1f}s"
                    suggestion = "考虑限制搜索范围或加缓存"
                    ev.append(
                        evidence(
                            "heuristic.search_timeout",
                            failure_detail,
                            excerpt=f"{step.duration:.1f}s",
                            step_index=step.index,
                            failure_type=failure_type,
                        )
                    )
            elif step.duration > self.timeout_seconds:
                failure_type = FailureType.SEARCH_TIMEOUT
                failure_detail = f"{step.action_name} 耗时 {step.duration:.1f}s"
                suggestion = "考虑限制搜索范围或加缓存"
                ev.append(
                    evidence(
                        "heuristic.search_timeout",
                        failure_detail,
                        excerpt=f"{step.duration:.1f}s",
                        step_index=step.index,
                        failure_type=failure_type,
                    )
                )

        return StepAnalysis(
            step_index=step.index,
            action=step.action_name,
            success=not bool(failure_type),
            duration=step.duration,
            failure_type=failure_type,
            failure_detail=failure_detail,
            suggestion=suggestion,
            evidence=ev,
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
            FailureType.ACCEPTANCE_FAILED: "检查失败断言和候选差异，修复后重新验收",
            FailureType.APPROVAL_DENIED: "检查 MCP/策略审批，确认 approve 或换工具路径",
            FailureType.INCOMPLETE_STREAM: "等待流结束或改用 on_incomplete=mark 仅作调试落盘",
            FailureType.SEARCH_EMPTY: "调整搜索词策略，先确认需求再搜索",
            FailureType.SEARCH_WEAK: "补齐检索结果的 url/title 字段；不做语义质量 Judge",
            FailureType.SEARCH_TIMEOUT: "限制搜索范围或添加缓存层",
            FailureType.LLM_OFFTRACK: "在 system prompt 中强化约束，或增加意图校验",
            FailureType.CONTEXT_OVERFLOW: "压缩上下文或启用摘要/窗口滑动",
            FailureType.DUPLICATE_ATTEMPT: "添加状态追踪，避免重复相同尝试",
            FailureType.NO_FINAL_ANSWER: "确保 Agent 在结束前输出 FINAL ANSWER",
        }
        return mapping.get(failure_type, "检查执行环境和输入")
