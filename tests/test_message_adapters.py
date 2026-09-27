"""OpenAI / Anthropic messages → Format B adapters (no SDK)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from trace_debugger.adapters import (
    anthropic_messages_to_trajectory,
    openai_messages_to_trajectory,
)
from trace_debugger.analyzer import Analyzer
from trace_debugger.harness import analyze_trajectory_dict
from trace_debugger.validate import validate_trajectory_dict, validate_trajectory_file


SAMPLE_OPENAI = [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "现在几点了？"},
    {
        "role": "assistant",
        "content": "我来查一下时间",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_time", "arguments": "{}"},
            }
        ],
    },
    {"role": "tool", "tool_call_id": "call_1", "content": "2026-09-14 10:57:00"},
    {
        "role": "assistant",
        "content": "当前时间是 2026年9月14日 10时57分。",
    },
]

SAMPLE_OPENAI_MULTI_TOOLS = [
    {"role": "user", "content": "查天气并搜索新闻"},
    {
        "role": "assistant",
        "content": "并行调用",
        "tool_calls": [
            {
                "id": "c1",
                "type": "function",
                "function": {
                    "name": "web_search",
                    "arguments": '{"query": "weather"}',
                },
            },
            {
                "id": "c2",
                "type": "function",
                "function": {
                    "name": "web_search",
                    "arguments": '{"query": "news"}',
                },
            },
        ],
    },
    {"role": "tool", "tool_call_id": "c1", "content": "sunny and warm today in the city"},
    {"role": "tool", "tool_call_id": "c2", "content": "top headlines about markets today"},
    {"role": "assistant", "content": "天气晴好；新闻见上。"},
]

SAMPLE_ANTHROPIC = [
    {"role": "user", "content": "100除以7等于多少？"},
    {
        "role": "assistant",
        "content": [
            {"type": "text", "text": "计算一下"},
            {
                "type": "tool_use",
                "id": "toolu_1",
                "name": "calculator",
                "input": {"expr": "100/7"},
            },
        ],
    },
    {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_1",
                "content": "14.2857142857",
            }
        ],
    },
    {
        "role": "assistant",
        "content": [{"type": "text", "text": "约等于 14.29。"}],
    },
]

SAMPLE_ANTHROPIC_ERROR = [
    {"role": "user", "content": "读文件"},
    {
        "role": "assistant",
        "content": [
            {
                "type": "tool_use",
                "id": "toolu_err",
                "name": "read_file",
                "input": {"path": "/nope"},
            }
        ],
    },
    {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_err",
                "content": "not found",
                "is_error": True,
            }
        ],
    },
    {"role": "assistant", "content": "无法读取文件。"},
]


def test_openai_messages_to_format_b():
    traj = openai_messages_to_trajectory(
        SAMPLE_OPENAI,
        session_id="oa_demo",
        model="gpt-4o-mini",
    )
    assert traj["session_id"] == "oa_demo"
    assert traj["query"] == "现在几点了？"
    assert traj["final_answer"].startswith("当前时间")
    assert len(traj["steps"]) == 2
    assert traj["steps"][0]["action"]["name"] == "get_time"
    assert "2026" in traj["steps"][0]["observation"]
    assert traj["steps"][0]["step"] == 1
    assert validate_trajectory_dict(traj) == []

    analysis = analyze_trajectory_dict(
        traj, analyzer=Analyzer(enable_offtrack=True)
    )
    fails = {ft for pa in analysis.paths for ft in pa.failure_types}
    assert "llm_offtrack" not in fails


def test_openai_parallel_tool_calls_split_steps():
    traj = openai_messages_to_trajectory(SAMPLE_OPENAI_MULTI_TOOLS, session_id="oa_multi")
    tool_steps = [s for s in traj["steps"] if s.get("action")]
    assert len(tool_steps) == 2
    assert tool_steps[0]["action"]["name"] == "web_search"
    assert "weather" in tool_steps[0]["action"]["arguments"]
    assert "news" in tool_steps[1]["action"]["arguments"]
    assert validate_trajectory_dict(traj) == []


def test_anthropic_messages_to_format_b():
    traj = anthropic_messages_to_trajectory(
        SAMPLE_ANTHROPIC,
        session_id="anth_demo",
        model="claude",
    )
    assert traj["query"] == "100除以7等于多少？"
    assert "14.29" in traj["final_answer"]
    assert traj["steps"][0]["action"]["name"] == "calculator"
    args = traj["steps"][0]["action"]["arguments"]
    assert "100/7" in args
    assert validate_trajectory_dict(traj) == []


def test_anthropic_tool_result_is_error():
    traj = anthropic_messages_to_trajectory(SAMPLE_ANTHROPIC_ERROR, session_id="anth_err")
    analysis = analyze_trajectory_dict(traj)
    fails = {ft for pa in analysis.paths for ft in pa.failure_types}
    assert "tool_error" in fails


def test_openai_roundtrip_file_validate():
    traj = openai_messages_to_trajectory(SAMPLE_OPENAI, session_id="oa_file")
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "oa.json"
        path.write_text(json.dumps(traj, ensure_ascii=False), encoding="utf-8")
        assert validate_trajectory_file(str(path)) == []
