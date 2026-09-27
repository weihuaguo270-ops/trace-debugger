"""Streaming coalesce + OpenAI Responses API → Format B coverage."""
from __future__ import annotations

import pytest

from trace_debugger.adapters import (
    IncompleteStreamError,
    coalesce_chat_completion_chunks,
    messages_from_chat_stream,
    openai_messages_to_trajectory,
    openai_responses_to_trajectory,
)
from trace_debugger.validate import validate_trajectory_dict


def _chunk(delta: dict, *, finish_reason=None) -> dict:
    choice = {"delta": delta, "index": 0}
    if finish_reason is not None:
        choice["finish_reason"] = finish_reason
    else:
        choice["finish_reason"] = None
    return {"id": "chatcmpl_x", "object": "chat.completion.chunk", "choices": [choice]}


def test_stream_incomplete_without_finish_reason_raises():
    chunks = [
        _chunk({"role": "assistant", "content": "Hel"}),
        _chunk({"content": "lo"}),
        # cut off — no finish_reason
    ]
    with pytest.raises(IncompleteStreamError, match="finish_reason"):
        coalesce_chat_completion_chunks(chunks)


def test_stream_incomplete_mark_trajectory():
    """on_incomplete=mark → validate 通过且 incomplete_stream / meta.incomplete。"""
    from trace_debugger.adapters import chat_stream_to_trajectory
    from trace_debugger.harness import analyze_trajectory_dict

    prior = [{"role": "user", "content": "你好"}]
    chunks = [
        _chunk({"role": "assistant", "content": "你"}),
        _chunk({"content": "好"}),
    ]
    traj = chat_stream_to_trajectory(
        prior, chunks, on_incomplete="mark", session_id="stream_mark",
    )
    assert traj.get("meta", {}).get("incomplete") is True
    assert validate_trajectory_dict(traj) == []
    analysis = analyze_trajectory_dict(traj)
    fails = {ft for pa in analysis.paths for ft in pa.failure_types}
    assert "incomplete_stream" in fails
    rules = [
        e.rule_id
        for pa in analysis.paths
        for sa in pa.step_analyses
        for e in (sa.evidence or [])
    ]
    assert "responses.incomplete" in rules


def test_stream_coalesce_then_trajectory():
    prior = [{"role": "user", "content": "现在几点了？"}]
    chunks = [
        _chunk({"role": "assistant", "content": ""}),
        _chunk({
            "tool_calls": [{
                "index": 0,
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_time", "arguments": ""},
            }]
        }),
        _chunk({
            "tool_calls": [{
                "index": 0,
                "function": {"arguments": "{}"},
            }]
        }),
        _chunk({}, finish_reason="tool_calls"),
    ]
    messages = messages_from_chat_stream(
        prior,
        chunks,
        tool_results=[
            {"role": "tool", "tool_call_id": "call_1", "content": "2026-09-14 11:00:00"},
        ],
    )
    # append final non-stream assistant for simplicity
    messages.append({
        "role": "assistant",
        "content": "当前时间是 2026年9月14日 11时。",
    })
    traj = openai_messages_to_trajectory(messages, session_id="stream_ok")
    assert traj["steps"][0]["action"]["name"] == "get_time"
    assert traj["steps"][0]["action"]["arguments"] == "{}"
    assert validate_trajectory_dict(traj) == []


def test_stream_incomplete_tool_name_raises():
    chunks = [
        _chunk({
            "tool_calls": [{
                "index": 0,
                "id": "call_x",
                "type": "function",
                "function": {"name": "", "arguments": "{"},
            }]
        }),
        _chunk({}, finish_reason="tool_calls"),
    ]
    with pytest.raises(IncompleteStreamError, match="tool_call name"):
        coalesce_chat_completion_chunks(chunks)


def test_responses_api_function_call_roundtrip():
    input_items = [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "现在几点了？"}],
        }
    ]
    # First model turn: function_call only
    response_1 = {
        "id": "resp_1",
        "model": "gpt-4.1-mini",
        "output": [
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "get_time",
                "arguments": "{}",
                "status": "completed",
            }
        ],
    }
    # Full transcript after tool executed + final message
    transcript = input_items + response_1["output"] + [
        {
            "type": "function_call_output",
            "call_id": "call_1",
            "output": "2026-09-14 11:05:00",
        },
        {
            "type": "message",
            "role": "assistant",
            "status": "completed",
            "content": [
                {"type": "output_text", "text": "当前时间是 2026年9月14日 11时05分。"}
            ],
        },
    ]
    traj = openai_responses_to_trajectory(
        transcript,
        session_id="resp_demo",
        model="gpt-4.1-mini",
    )
    assert traj["query"] == "现在几点了？"
    assert traj["final_answer"].startswith("当前时间")
    assert traj["steps"][0]["action"]["name"] == "get_time"
    assert "11:05" in traj["steps"][0]["observation"]
    assert validate_trajectory_dict(traj) == []


def test_responses_api_from_response_object_plus_input():
    traj = openai_responses_to_trajectory(
        {
            "id": "resp_2",
            "model": "gpt-4.1-mini",
            "output": [
                {
                    "type": "function_call",
                    "call_id": "c2",
                    "name": "web_search",
                    "arguments": '{"query": "weather"}',
                    "status": "completed",
                },
                {
                    "type": "function_call_output",
                    "call_id": "c2",
                    "output": "sunny and warm in the city center today",
                },
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "今天晴。"}],
                    "status": "completed",
                },
            ],
        },
        input_items=[
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "天气如何"}],
            },
        ],
    )
    assert traj["query"] == "天气如何"
    assert traj["session_id"] == "resp_2"
    assert traj["steps"][0]["action"]["name"] == "web_search"
    assert "sunny" in traj["steps"][0]["observation"]
    assert traj["final_answer"] == "今天晴。"
    assert validate_trajectory_dict(traj) == []


def test_responses_api_parallel_function_calls():
    items = [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "查天气和新闻"}],
        },
        {
            "type": "function_call",
            "call_id": "a",
            "name": "web_search",
            "arguments": '{"query": "weather"}',
            "status": "completed",
        },
        {
            "type": "function_call",
            "call_id": "b",
            "name": "web_search",
            "arguments": '{"query": "news"}',
            "status": "completed",
        },
        {
            "type": "function_call_output",
            "call_id": "a",
            "output": "sunny day report for the region",
        },
        {
            "type": "function_call_output",
            "call_id": "b",
            "output": "market headlines summary today",
        },
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "天气晴，新闻见上。"}],
            "status": "completed",
        },
    ]
    traj = openai_responses_to_trajectory(items, session_id="resp_par")
    tool_steps = [s for s in traj["steps"] if s.get("action")]
    assert len(tool_steps) == 2
    assert "sunny" in tool_steps[0]["observation"]
    assert "market" in tool_steps[1]["observation"]
    assert validate_trajectory_dict(traj) == []

def test_responses_incomplete_item_rejected():
    items = [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "hi"}],
        },
        {
            "type": "function_call",
            "call_id": "c",
            "name": "get_time",
            "arguments": "",
            "status": "in_progress",
        },
    ]
    with pytest.raises(IncompleteStreamError, match="incomplete|in_progress"):
        openai_responses_to_trajectory(items, session_id="resp_bad")


def test_responses_incomplete_item_mark():
    from trace_debugger.harness import analyze_trajectory_dict

    items = [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "hi"}],
        },
        {
            "type": "function_call",
            "call_id": "c",
            "name": "get_time",
            "arguments": "",
            "status": "in_progress",
        },
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "hi 未完成"}],
            "status": "completed",
        },
    ]
    traj = openai_responses_to_trajectory(
        items, session_id="resp_mark", on_incomplete="mark",
    )
    assert traj.get("meta", {}).get("incomplete") is True
    assert validate_trajectory_dict(traj) == []
    analysis = analyze_trajectory_dict(traj)
    fails = {ft for pa in analysis.paths for ft in pa.failure_types}
    assert "incomplete_stream" in fails
    rules = [
        e.rule_id
        for pa in analysis.paths
        for sa in pa.step_analyses
        for e in (sa.evidence or [])
    ]
    assert "responses.incomplete" in rules
