"""Generate fixtures/failure_golden trajectories + verified manifest."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trace_debugger.analyzer import Analyzer  # noqa: E402
from trace_debugger.reader import load  # noqa: E402

GOLDEN = ROOT / "fixtures" / "failure_golden"
LONG = (
    "Python official documentation covers tutorial library reference and "
    "standard modules in detail. " * 2
)
SEARCH_OK = (
    "Machine learning is a subset of artificial intelligence focused on "
    "learning from data and patterns. " * 2
)


def save(name: str, data: dict) -> None:
    (GOLDEN / name).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> int:
    GOLDEN.mkdir(parents=True, exist_ok=True)

    save("tool_error.json", {
        "session_id": "golden_tool_error", "query": "计算 2+2", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:00:01Z",
        "steps": [
            {"step": 1, "thought": "调用 calculator",
             "action": {"name": "calculator", "arguments": "{\"expression\": \"2++\"}"},
             "observation": "{\"error\": \"表达式语法错误\"}", "duration_seconds": 0.2},
            {"step": 2, "thought": "FINAL ANSWER: 无法完成", "observation": ""},
        ],
        "final_answer": "无法完成", "total_duration_seconds": 0.5,
    })

    save("search_empty.json", {
        "session_id": "golden_search_empty", "query": "搜索 Rust 2026 趋势", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:00:02Z",
        "steps": [
            {"step": 1, "thought": "search",
             "action": {"name": "web_search", "arguments": "{\"query\": \"Rust 2026\"}"},
             "observation": "no hits", "duration_seconds": 1.0},
            {"step": 2, "thought": "FINAL ANSWER: 未找到", "observation": ""},
        ],
        "final_answer": "未找到", "total_duration_seconds": 1.2,
    })

    save("search_timeout.json", {
        "session_id": "golden_search_timeout", "query": "抓取大型页面", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:00:03Z",
        "steps": [
            {"step": 1, "thought": "fetch",
             "action": {"name": "fetch_page", "arguments": "{\"url\": \"https://slow.example\"}"},
             "observation": LONG, "duration_seconds": 25.5},
            {"step": 2, "thought": "FINAL ANSWER: done", "observation": ""},
        ],
        "final_answer": "done", "total_duration_seconds": 26.0,
    })

    save("duplicate_with_empty.json", {
        "session_id": "golden_dup_empty", "query": "搜索 Python 文档", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:00:04Z",
        "steps": [
            {"step": 1, "thought": "search",
             "action": {"name": "web_search", "arguments": "{\"query\": \"Python docs\"}"},
             "observation": "少", "duration_seconds": 1.0},
            {"step": 2, "thought": "retry same",
             "action": {"name": "web_search", "arguments": "{\"query\": \"Python docs\"}"},
             "observation": "少", "duration_seconds": 1.1},
            {"step": 3, "thought": "FINAL ANSWER: python.org", "observation": ""},
        ],
        "final_answer": "python.org", "total_duration_seconds": 2.5,
    })

    save("duplicate_only.json", {
        "session_id": "golden_dup_only", "query": "查 Python 官方文档", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:00:05Z",
        "steps": [
            {"step": 1, "thought": "search",
             "action": {"name": "web_search", "arguments": "{\"query\": \"Python docs\"}"},
             "observation": LONG, "duration_seconds": 1.0},
            {"step": 2, "thought": "same again",
             "action": {"name": "web_search", "arguments": "{\"query\": \"Python docs\"}"},
             "observation": LONG, "duration_seconds": 1.1},
            {"step": 3, "thought": "FINAL ANSWER: see docs.python.org", "observation": ""},
        ],
        "final_answer": "see docs.python.org", "total_duration_seconds": 2.5,
    })

    save("no_answer.json", {
        "session_id": "golden_no_answer", "query": "北京今天天气如何？", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:00:06Z",
        "steps": [{"step": 1, "thought": "我需要查天气...", "observation": ""}],
        "final_answer": "", "total_duration_seconds": 0.3,
    })

    save("offtrack.json", {
        "session_id": "golden_offtrack",
        "query": "写一份关于人工智能行业趋势的详细分析报告", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:00:07Z",
        "steps": [{"step": 1, "thought": "FINAL ANSWER: 今天天气很好，适合出门散步。", "observation": ""}],
        "final_answer": "今天天气很好，适合出门散步。周末还可以去公园野餐，欣赏美丽的风景。",
        "total_duration_seconds": 0.3,
    })

    save("overflow_step.json", {
        "session_id": "golden_overflow_step", "query": "summarize long page", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:00:08Z",
        "steps": [
            {"step": 1, "thought": "fetch",
             "action": {"name": "fetch_page", "arguments": "{\"url\": \"https://x.com\"}"},
             "observation": "Error: maximum context length exceeded for this model",
             "duration_seconds": 0.5, "tokens_estimated": 100},
            {"step": 2, "thought": "FINAL ANSWER: failed", "observation": ""},
        ],
        "final_answer": "failed", "total_duration_seconds": 0.8, "total_tokens_estimated": 9000,
    })

    save("overflow_meta.json", {
        "session_id": "golden_overflow_meta", "query": "long context task", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:00:09Z",
        "steps": [
            {"step": 1, "thought": "read",
             "action": {"name": "read_file", "arguments": "{\"path\": \"big.txt\"}"},
             "observation": LONG, "duration_seconds": 0.4, "tokens_estimated": 2000},
            {"step": 2, "thought": "FINAL ANSWER: partial", "observation": ""},
        ],
        "final_answer": "partial summary", "total_duration_seconds": 0.6,
        "total_tokens_estimated": 9500,
    })

    save("pass_clean.json", {
        "session_id": "golden_pass_clean", "query": "What is Python?", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:00:10Z",
        "steps": [
            {"step": 1, "thought": "search",
             "action": {"name": "web_search", "arguments": "{\"query\": \"Python programming\"}"},
             "observation": SEARCH_OK, "duration_seconds": 1.0},
            {"step": 2, "thought": "FINAL ANSWER: Python is a programming language.", "observation": ""},
        ],
        "final_answer": "Python is a programming language widely used for web and data science.",
        "total_duration_seconds": 1.5,
    })

    save("pass_grounded_qa.json", {
        "session_id": "golden_pass_grounded", "query": "现在几点了？", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:00:11Z",
        "steps": [
            {"step": 1, "thought": "查时间", "action": {"name": "get_time", "arguments": "{}"},
             "observation": "2026-07-28 14:12:25", "duration_seconds": 0.1},
            {"step": 2, "thought": "FINAL ANSWER: 当前时间是 2026年7月28日 14时12分25秒", "observation": ""},
        ],
        "final_answer": "当前时间是 **2026年7月28日 14时12分25秒**（本地时间）。",
        "total_duration_seconds": 0.3,
    })

    save("pass_multi_step.json", {
        "session_id": "golden_pass_multi", "query": "Explain ML pipeline", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:00:12Z",
        "steps": [
            {"step": 1, "thought": "search ml",
             "action": {"name": "web_search", "arguments": "{\"query\": \"ML pipeline steps\"}"},
             "observation": SEARCH_OK, "duration_seconds": 1.2},
            {"step": 2, "thought": "search eval",
             "action": {"name": "web_search", "arguments": "{\"query\": \"ML model evaluation\"}"},
             "observation": "Model evaluation uses metrics like accuracy precision recall on held-out data sets.",
             "duration_seconds": 1.0},
            {"step": 3, "thought": "FINAL ANSWER: ML pipeline includes data prep, training, evaluation.",
             "observation": ""},
        ],
        "final_answer": "An ML pipeline includes data preparation, model training, and evaluation.",
        "total_duration_seconds": 3.0,
    })

    save("tool_error_recovered.json", {
        "session_id": "golden_tool_recovered", "query": "Run calculation", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:00:13Z",
        "steps": [
            {"step": 1, "thought": "calc",
             "action": {"name": "calculator", "arguments": "{\"expression\": \"1/0\"}"},
             "observation": "Error: division by zero", "duration_seconds": 0.2},
            {"step": 2, "thought": "retry",
             "action": {"name": "calculator", "arguments": "{\"expression\": \"2+2\"}"},
             "observation": "4", "duration_seconds": 0.1},
            {"step": 3, "thought": "FINAL ANSWER: 4", "observation": ""},
        ],
        "final_answer": "4", "total_duration_seconds": 0.5,
    })

    save("no_duplicate_diff_args.json", {
        "session_id": "golden_no_dup", "query": "Research AI and ML", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:00:14Z",
        "steps": [
            {"step": 1, "thought": "search ai",
             "action": {"name": "web_search", "arguments": "{\"query\": \"AI trends\"}"},
             "observation": SEARCH_OK, "duration_seconds": 1.0},
            {"step": 2, "thought": "search ml",
             "action": {"name": "web_search", "arguments": "{\"query\": \"ML trends\"}"},
             "observation": SEARCH_OK, "duration_seconds": 1.0},
            {"step": 3, "thought": "FINAL ANSWER: AI and ML both evolving rapidly.", "observation": ""},
        ],
        "final_answer": "AI and ML are both evolving rapidly in 2026.", "total_duration_seconds": 2.5,
    })

    save("multi_paths.json", {
        "session_id": "golden_multi_paths", "query": "explore options", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:00:15Z", "steps": [],
        "paths": [
            {"path_id": 0, "is_main": False, "success": False, "steps": [
                {"step": 1, "thought": "bad branch",
                 "action": {"name": "calculator", "arguments": "{}"},
                 "observation": "{\"error\": \"invalid\"}", "duration_seconds": 0.2},
            ]},
            {"path_id": 1, "is_main": True, "success": True,
             "final_answer": "When exploring options, AI trends are growing in 2026.", "steps": [
                {"step": 1, "thought": "good branch",
                 "action": {"name": "web_search", "arguments": "{\"query\": \"AI trends 2026\"}"},
                 "observation": SEARCH_OK, "duration_seconds": 1.0},
                {"step": 2, "thought": "FINAL ANSWER: exploring options shows AI trends growing.",
                 "observation": ""},
            ]},
        ],
        "final_answer": "When exploring options, AI trends are growing in 2026 with enterprise adoption.",
        "total_duration_seconds": 1.5,
    })

    save("path_id_branch.json", {
        "session_id": "golden_path_id", "query": "branch test", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:00:16Z", "main_path_index": 1,
        "steps": [
            {"step": 1, "path_id": 0, "thought": "fail branch",
             "action": {"name": "calc", "arguments": "{}"},
             "observation": "{\"error\": \"fail\"}", "duration_seconds": 0.2},
            {"step": 1, "path_id": 1, "thought": "FINAL ANSWER: ok", "observation": ""},
        ],
        "final_answer": "ok", "total_duration_seconds": 0.4,
    })

    save("search_empty_cn.json", {
        "session_id": "golden_search_cn", "query": "搜索行业报告", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:00:17Z",
        "steps": [
            {"step": 1, "thought": "搜索",
             "action": {"name": "网络搜索", "arguments": "{\"q\": \"AI\"}"},
             "observation": "无", "duration_seconds": 0.8},
            {"step": 2, "thought": "FINAL ANSWER: 无结果", "observation": ""},
        ],
        "final_answer": "无结果", "total_duration_seconds": 1.0,
    })

    save("search_timeout_slow.json", {
        "session_id": "golden_timeout_slow", "query": "slow web search", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:00:18Z",
        "steps": [
            {"step": 1, "thought": "search",
             "action": {"name": "web_search", "arguments": "{\"query\": \"slow query\"}"},
             "observation": SEARCH_OK, "duration_seconds": 22.0},
            {"step": 2, "thought": "FINAL ANSWER: found", "observation": ""},
        ],
        "final_answer": "found", "total_duration_seconds": 22.5,
    })

    save("no_answer_empty_final.json", {
        "session_id": "golden_no_ans_empty", "query": "hello", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:00:19Z",
        "steps": [
            {"step": 1, "thought": "thinking...", "observation": ""},
            {"step": 2, "thought": "still thinking", "observation": ""},
        ],
        "final_answer": "   ", "total_duration_seconds": 0.5,
    })

    save("offtrack_subtle.json", {
        "session_id": "golden_offtrack_subtle",
        "query": "撰写量子计算在金融科技中的应用综述", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:00:20Z",
        "steps": [{"step": 1,
                   "thought": "FINAL ANSWER: 推荐三款适合夏季跑步的运动鞋，透气轻便。",
                   "observation": ""}],
        "final_answer": "推荐三款适合夏季跑步的运动鞋，透气轻便，适合日常慢跑与健身训练。",
        "total_duration_seconds": 0.4,
    })

    save("overflow_cumulative.json", {
        "session_id": "golden_overflow_cum", "query": "accumulate context", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:00:21Z",
        "steps": [
            {"step": 1, "thought": "s1", "action": {"name": "read", "arguments": "{}"},
             "observation": LONG, "duration_seconds": 0.3, "tokens_estimated": 3500},
            {"step": 2, "thought": "s2", "action": {"name": "read", "arguments": "{\"path\": \"b.txt\"}"},
             "observation": LONG, "duration_seconds": 0.3, "tokens_estimated": 3500},
            {"step": 3, "thought": "FINAL ANSWER: ok", "observation": "", "tokens_estimated": 2000},
        ],
        "final_answer": "ok", "total_duration_seconds": 1.0,
    })

    save("held_out_pass_report.json", {
        "session_id": "held_pass_report",
        "query": "写一份关于 AI 行业趋势的简短报告", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:01:01Z",
        "steps": [
            {"step": 1, "thought": "search trends",
             "action": {"name": "web_search", "arguments": "{\"query\": \"AI industry trends 2026\"}"},
             "observation": "AI industry trends in 2026 show strong growth in agents and enterprise adoption worldwide.",
             "duration_seconds": 1.1},
            {"step": 2, "thought": "search china",
             "action": {"name": "web_search", "arguments": "{\"query\": \"中国 AI 市场 2026 趋势\"}"},
             "observation": "中国 AI 市场在 2026 年继续保持增长，企业级 Agent 与自动化需求显著上升。",
             "duration_seconds": 1.0},
            {"step": 3, "thought": "FINAL ANSWER: 2026年 AI 行业趋势包括 Agent 普及与企业采用加速。",
             "observation": ""},
        ],
        "final_answer": "2026年 AI 行业趋势包括 Agent 普及、多模态模型与企业采用加速。",
        "total_duration_seconds": 2.5,
    })

    save("held_out_mixed_warn.json", {
        "session_id": "held_mixed_warn", "query": "打开网页并总结", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:01:02Z",
        "steps": [
            {"step": 1, "thought": "fetch",
             "action": {"name": "fetch_page", "arguments": "{\"url\": \"bad://\"}"},
             "observation": "{\"error\": \"Invalid URL scheme\"}", "duration_seconds": 0.2},
            {"step": 2, "thought": "search instead",
             "action": {"name": "web_search", "arguments": "{\"query\": \"summary topic\"}"},
             "observation": SEARCH_OK, "duration_seconds": 1.0},
            {"step": 3, "thought": "FINAL ANSWER: 已打开网页并完成总结。", "observation": ""},
        ],
        "final_answer": "已打开网页并根据搜索结果完成总结。",
        "total_duration_seconds": 1.5,
    })

    save("held_out_search_chain.json", {
        "session_id": "held_search_chain", "query": "查找 rare topic xyz123", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:01:03Z",
        "steps": [
            {"step": 1, "thought": "s1",
             "action": {"name": "web_search", "arguments": "{\"query\": \"xyz123 rare\"}"},
             "observation": "[]", "duration_seconds": 0.9},
            {"step": 2, "thought": "s2",
             "action": {"name": "web_search", "arguments": "{\"query\": \"xyz123 alternative\"}"},
             "observation": "n/a", "duration_seconds": 0.8},
            {"step": 3, "thought": "FINAL ANSWER: not found", "observation": ""},
        ],
        "final_answer": "not found", "total_duration_seconds": 2.0,
    })

    save("held_out_offtrack_calc.json", {
        "session_id": "held_offtrack_calc", "query": "计算 15 的平方是多少", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:01:04Z",
        "steps": [
            {"step": 1, "thought": "calc",
             "action": {"name": "calculator", "arguments": "{\"expression\": \"15**2\"}"},
             "observation": "225", "duration_seconds": 0.1},
            {"step": 2, "thought": "FINAL ANSWER: 15 的平方是 225", "observation": ""},
        ],
        "final_answer": "15 的平方是 225。", "total_duration_seconds": 0.3,
    })

    save("held_out_no_answer_maxsteps.json", {
        "session_id": "held_no_answer_max", "query": "复杂调研任务", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:01:05Z",
        "steps": [
            {"step": 1, "thought": "start research",
             "action": {"name": "web_search", "arguments": "{\"query\": \"topic\"}"},
             "observation": SEARCH_OK, "duration_seconds": 1.0},
            {"step": 2, "thought": "need more", "observation": ""},
        ],
        "final_answer": "", "total_duration_seconds": 1.2,
    })

    save("held_out_duplicate_blocked.json", {
        "session_id": "held_dup_blocked", "query": "搜索文档", "model": "mock-gpt",
        "timestamp": "2026-07-28T00:01:06Z",
        "steps": [
            {"step": 1, "thought": "search",
             "action": {"name": "web_search", "arguments": "{\"query\": \"docs\"}"},
             "observation": "x", "duration_seconds": 0.5},
            {"step": 2, "thought": "blocked dup",
             "action": {"name": "web_search", "arguments": "{\"query\": \"docs\"}"},
             "observation": "[Harness] 已阻止重复调用 web_search（参数与上一次完全相同）。",
             "duration_seconds": 0.1},
            {"step": 3, "thought": "FINAL ANSWER: use docs", "observation": ""},
        ],
        "final_answer": "use docs", "total_duration_seconds": 0.8,
    })

    specs = [
        ("golden_tool_error", "tool_error.json", "golden", "negative", ["tool_error"], [],
         [{"step": 1, "type": "tool_error"}]),
        ("golden_search_empty", "search_empty.json", "golden", "negative", ["search_empty"], [],
         [{"step": 1, "type": "search_empty"}]),
        ("golden_search_timeout", "search_timeout.json", "golden", "negative", ["search_timeout"], [],
         [{"step": 1, "type": "search_timeout"}]),
        ("golden_duplicate_with_empty", "duplicate_with_empty.json", "golden", "negative",
         ["duplicate", "search_empty"], [], []),
        ("golden_duplicate_only", "duplicate_only.json", "golden", "negative", ["duplicate"],
         ["search_empty"], [{"step": 2, "type": "duplicate"}]),
        ("golden_no_answer", "no_answer.json", "golden", "negative", ["no_answer"], [], []),
        ("golden_offtrack", "offtrack.json", "golden", "negative", ["llm_offtrack"], [], []),
        ("golden_overflow_step", "overflow_step.json", "golden", "negative", ["context_overflow"], [],
         [{"step": 1, "type": "context_overflow"}]),
        ("golden_overflow_meta", "overflow_meta.json", "golden", "negative", ["context_overflow"], [], []),
        ("golden_pass_clean", "pass_clean.json", "golden", "positive", [],
         ["tool_error", "search_empty", "llm_offtrack", "no_answer"], []),
        ("golden_pass_grounded_qa", "pass_grounded_qa.json", "golden", "positive", [],
         ["llm_offtrack"], []),
        ("golden_pass_multi_step", "pass_multi_step.json", "golden", "positive", [],
         ["duplicate", "llm_offtrack"], []),
        ("golden_tool_error_recovered", "tool_error_recovered.json", "golden", "negative",
         ["tool_error"], [], [{"step": 1, "type": "tool_error"}]),
        ("golden_no_duplicate_diff_args", "no_duplicate_diff_args.json", "golden", "positive", [],
         ["duplicate"], []),
        ("golden_multi_paths", "multi_paths.json", "golden", "negative", ["tool_error"], [],
         [{"step": 1, "type": "tool_error", "path": 0}]),
        ("golden_path_id_branch", "path_id_branch.json", "golden", "negative", ["tool_error"], [],
         [{"step": 1, "type": "tool_error", "path": 0}]),
        ("golden_search_empty_cn", "search_empty_cn.json", "golden", "negative", ["search_empty"], [], []),
        ("golden_search_timeout_slow", "search_timeout_slow.json", "golden", "negative",
         ["search_timeout"], [], [{"step": 1, "type": "search_timeout"}]),
        ("golden_no_answer_empty_final", "no_answer_empty_final.json", "golden", "negative",
         ["no_answer"], [], []),
        ("golden_offtrack_subtle", "offtrack_subtle.json", "golden", "negative", ["llm_offtrack"], [], []),
        ("golden_overflow_cumulative", "overflow_cumulative.json", "golden", "negative",
         ["context_overflow"], [], []),
        ("held_out_pass_report", "held_out_pass_report.json", "held_out", "positive", [],
         ["llm_offtrack", "tool_error"], []),
        ("held_out_mixed_warn", "held_out_mixed_warn.json", "held_out", "negative", ["tool_error"], [],
         [{"step": 1, "type": "tool_error"}]),
        ("held_out_search_chain", "held_out_search_chain.json", "held_out", "negative",
         ["search_empty"], [], []),
        ("held_out_offtrack_calc", "held_out_offtrack_calc.json", "held_out", "positive", [],
         ["llm_offtrack"], []),
        ("held_out_no_answer_maxsteps", "held_out_no_answer_maxsteps.json", "held_out", "negative",
         ["no_answer"], [], []),
        ("held_out_duplicate_blocked", "held_out_duplicate_blocked.json", "held_out", "negative",
         ["duplicate", "search_empty"], [], []),
    ]

    analyzer = Analyzer()
    manifest_cases = []
    mismatches = []
    for sid, fname, split, cat, exp, must_not, step_exp in specs:
        analysis = analyzer.analyze(load(str(GOLDEN / fname)))
        detected = sorted({ft for pa in analysis.paths for ft in pa.failure_types})
        if set(detected) != set(exp):
            mismatches.append((sid, exp, detected))
        manifest_cases.append({
            "id": sid,
            "file": fname,
            "split": split,
            "category": cat,
            "expected_failures": exp,
            "must_not_detect": must_not,
            "expected_step_failures": step_exp,
            "notes": f"verified detected={detected}",
        })

    manifest = {
        "schema_version": "1",
        "description": "黄金失败集 — 7 类 taxonomy + 正例 + held-out；供证据链与 CI 门禁",
        "n_cases": len(manifest_cases),
        "cases": manifest_cases,
    }
    (GOLDEN / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Generated {len(manifest_cases)} golden cases under {GOLDEN}")
    if mismatches:
        print("MISMATCHES:")
        for m in mismatches:
            print(" ", m)
        return 1
    print("All expectations verified against Analyzer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
