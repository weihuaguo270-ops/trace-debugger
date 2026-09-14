"""Extended Responses Item mappings: computer / MCP / multimodal / etc."""
from __future__ import annotations

from trace_debugger.adapters import openai_responses_to_trajectory
from trace_debugger.harness import analyze_trajectory_dict
from trace_debugger.validate import validate_trajectory_dict


def test_responses_computer_call_with_output():
    items = [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "打开浏览器"}],
        },
        {
            "type": "computer_call",
            "call_id": "comp_1",
            "status": "completed",
            "action": {"type": "click", "x": 10, "y": 20},
        },
        {
            "type": "computer_call_output",
            "call_id": "comp_1",
            "output": {"type": "computer_screenshot", "file_id": "file_abc"},
        },
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "已点击。"}],
            "status": "completed",
        },
    ]
    traj = openai_responses_to_trajectory(items, session_id="comp")
    tool = next(s for s in traj["steps"] if s.get("action"))
    assert tool["action"]["name"].startswith("computer_call")
    assert "file_abc" in tool["observation"]
    assert validate_trajectory_dict(traj) == []


def test_responses_mcp_call_inline_error():
    items = [
        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "查库"}]},
        {
            "type": "mcp_call",
            "id": "mcp_1",
            "name": "query_db",
            "server_label": "db",
            "arguments": '{"sql": "select 1"}',
            "status": "failed",
            "error": {"message": "permission denied"},
        },
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "失败了"}],
            "status": "completed",
        },
    ]
    traj = openai_responses_to_trajectory(items, session_id="mcp")
    tool = next(s for s in traj["steps"] if (s.get("action") or {}).get("name") == "query_db")
    assert "错误" in tool["observation"] or "permission" in tool["observation"].lower()
    analysis = analyze_trajectory_dict(traj)
    fails = {ft for pa in analysis.paths for ft in pa.failure_types}
    assert "tool_error" in fails


def test_responses_mcp_protocol_and_list_tools():
    items = [
        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "工具?"}]},
        {
            "type": "mcp_list_tools",
            "id": "list_1",
            "server_label": "files",
            "tools": [{"name": "read"}, {"name": "write"}],
        },
        {
            "type": "mcp_approval_request",
            "id": "apr_1",
            "name": "write",
            "server_label": "files",
            "arguments": '{"path": "/tmp/x"}',
        },
        {
            "type": "mcp_approval_response",
            "id": "apr_r",
            "approval_request_id": "apr_1",
            "approve": True,
        },
    ]
    traj = openai_responses_to_trajectory(items, session_id="mcp_proto")
    names = [(s.get("action") or {}).get("name") for s in traj["steps"] if s.get("action")]
    assert "mcp_list_tools" in names or "files" in names
    assert "mcp_approval_request" in names
    assert "mcp_approval_response" in names
    assert validate_trajectory_dict(traj) == []
    analysis = analyze_trajectory_dict(traj)
    fails = {ft for pa in analysis.paths for ft in pa.failure_types}
    assert "approval_denied" not in fails
    assert "tool_error" not in fails


def test_mcp_approval_denied_is_failure():
    """approve=False → approval_denied + responses.mcp.approval_denied."""
    items = [
        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "写文件"}]},
        {
            "type": "mcp_approval_request",
            "id": "apr_deny",
            "name": "write",
            "server_label": "files",
            "arguments": '{"path": "/tmp/x"}',
        },
        {
            "type": "mcp_approval_response",
            "id": "apr_r_deny",
            "approval_request_id": "apr_deny",
            "approve": False,
        },
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "未批准"}],
            "status": "completed",
        },
    ]
    traj = openai_responses_to_trajectory(items, session_id="mcp_deny")
    deny = next(
        s for s in traj["steps"]
        if (s.get("action") or {}).get("name") == "mcp_approval_response"
    )
    assert deny["observation"].startswith("[错误] mcp approval denied")
    analysis = analyze_trajectory_dict(traj)
    fails = {ft for pa in analysis.paths for ft in pa.failure_types}
    assert "approval_denied" in fails
    assert "tool_error" not in fails
    rules = [
        e.rule_id
        for pa in analysis.paths
        for sa in pa.step_analyses
        for e in (sa.evidence or [])
    ]
    assert "responses.mcp.approval_denied" in rules


def test_responses_web_and_file_search():
    items = [
        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "搜一下"}]},
        {
            "type": "web_search_call",
            "id": "ws_1",
            "status": "completed",
            "queries": ["AI agents 2026"],
            "results": [{"title": "Report", "url": "https://example.com"}],
        },
        {
            "type": "file_search_call",
            "id": "fs_1",
            "status": "completed",
            "queries": ["policy"],
            "results": [{"file_id": "f1", "score": 0.9}],
        },
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "搜到了。"}],
            "status": "completed",
        },
    ]
    traj = openai_responses_to_trajectory(items, session_id="search")
    actions = [(s.get("action") or {}).get("name") for s in traj["steps"] if s.get("action")]
    assert "web_search_call" in actions
    assert "file_search_call" in actions
    assert validate_trajectory_dict(traj) == []


def test_responses_shell_and_code_interpreter():
    items = [
        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "跑命令"}]},
        {
            "type": "local_shell_call",
            "id": "sh_1",
            "call_id": "sh_1",
            "status": "completed",
            "action": {"type": "exec", "command": ["ls", "-la"], "env": {}},
        },
        {
            "type": "local_shell_call_output",
            "id": "sh_out",
            "call_id": "sh_1",
            "output": '{"stdout": "a.txt\\n"}',
        },
        {
            "type": "code_interpreter_call",
            "id": "ci_1",
            "status": "completed",
            "outputs": [{"type": "logs", "logs": "ok"}],
        },
    ]
    traj = openai_responses_to_trajectory(items, session_id="shell")
    shell = next(
        s for s in traj["steps"]
        if (s.get("action") or {}).get("name") in ("local_shell_call", "local_shell_call.exec")
        or "ls" in str((s.get("action") or {}).get("arguments", ""))
    )
    assert "a.txt" in shell["observation"] or "stdout" in shell["observation"]
    assert any(
        (s.get("action") or {}).get("name") == "code_interpreter_call"
        for s in traj["steps"] if s.get("action")
    )


def test_responses_image_generation_omits_base64():
    huge = "A" * 5000
    items = [
        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "画图"}]},
        {
            "type": "image_generation_call",
            "id": "img_1",
            "status": "completed",
            "output_format": "png",
            "result": huge,
        },
    ]
    traj = openai_responses_to_trajectory(items, session_id="img")
    obs = next(s["observation"] for s in traj["steps"] if s.get("action"))
    assert huge not in obs
    assert "omitted" in obs.lower() or "len=" in obs


def test_responses_multimodal_user_message_refs():
    items = [
        {
            "type": "message",
            "role": "user",
            "content": [
                {"type": "input_text", "text": "这是什么"},
                {
                    "type": "input_image",
                    "image_url": "https://example.com/a.png",
                    "detail": "high",
                },
            ],
        },
        {
            "type": "message",
            "role": "assistant",
            "content": [
                {"type": "output_text", "text": "一只猫"},
                {"type": "output_image", "image_url": "https://example.com/out.png"},
            ],
            "status": "completed",
        },
    ]
    traj = openai_responses_to_trajectory(items, session_id="mm")
    assert traj["query"] == "这是什么"
    assert any("input_image" in (s.get("thought") or "") or "output_image" in (s.get("thought") or "")
               for s in traj["steps"])
    assert validate_trajectory_dict(traj) == []


def test_shell_nonzero_exit_without_english_error_word():
    """exit_code!=0 → tool_error; observation 可不含英文 error。"""
    items = [
        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "跑脚本"}]},
        {
            "type": "local_shell_call",
            "call_id": "sh_fail",
            "status": "completed",
            "action": {"type": "exec", "command": ["false"], "env": {}},
        },
        {
            "type": "local_shell_call_output",
            "call_id": "sh_fail",
            "output": '{"stdout": "", "stderr": "失败", "exit_code": 1}',
        },
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "命令未成功"}],
            "status": "completed",
        },
    ]
    traj = openai_responses_to_trajectory(items, session_id="shell_exit")
    tool = next(s for s in traj["steps"] if s.get("action"))
    assert "error" not in tool["observation"].lower().replace("nonzero_exit", "")
    # Allow rule id token; strip it for the english-error check
    obs_check = tool["observation"].replace("responses.shell.nonzero_exit", "")
    assert "error" not in obs_check.lower()
    assert "exit_code=1" in tool["observation"]
    analysis = analyze_trajectory_dict(traj)
    fails = {ft for pa in analysis.paths for ft in pa.failure_types}
    assert "tool_error" in fails
    rules = [
        e.rule_id
        for pa in analysis.paths
        for sa in pa.step_analyses
        for e in (sa.evidence or [])
    ]
    assert "responses.shell.nonzero_exit" in rules


def test_computer_structured_error_field_chinese_only():
    """output.error 仅为结构化字段，detail 中文、无英文 error 字样 → tool_error。"""
    items = [
        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "点击"}]},
        {
            "type": "computer_call",
            "call_id": "c_err",
            "status": "completed",
            "action": {"type": "click", "x": 1, "y": 2},
        },
        {
            "type": "computer_call_output",
            "call_id": "c_err",
            "output": {
                "error": {"code": "timeout", "message": "操作超时"},
            },
        },
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "未完成"}],
            "status": "completed",
        },
    ]
    traj = openai_responses_to_trajectory(items, session_id="comp_struct")
    tool = next(s for s in traj["steps"] if s.get("action"))
    # Strip rule id then assert no english word "error"
    obs_check = tool["observation"].replace("responses.computer.failed", "")
    assert "error" not in obs_check.lower()
    assert "操作超时" in tool["observation"] or "timeout" in tool["observation"]
    analysis = analyze_trajectory_dict(traj)
    assert "tool_error" in {ft for pa in analysis.paths for ft in pa.failure_types}
    rules = [
        e.rule_id
        for pa in analysis.paths
        for sa in pa.step_analyses
        for e in (sa.evidence or [])
    ]
    assert "responses.computer.failed" in rules


def test_computer_safety_check_rejected():
    items = [
        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "危险操作"}]},
        {
            "type": "computer_call",
            "call_id": "c_safe",
            "status": "completed",
            "action": {"type": "type", "text": "rm -rf /"},
            "acknowledged_safety_checks": [
                {"id": "malicious_instructions", "status": "rejected"},
            ],
        },
        {
            "type": "computer_call_output",
            "call_id": "c_safe",
            "output": {"type": "computer_screenshot", "file_id": "f1"},
        },
    ]
    traj = openai_responses_to_trajectory(items, session_id="comp_safe")
    analysis = analyze_trajectory_dict(traj)
    assert "tool_error" in {ft for pa in analysis.paths for ft in pa.failure_types}
    rules = [
        e.rule_id
        for pa in analysis.paths
        for sa in pa.step_analyses
        for e in (sa.evidence or [])
    ]
    assert "responses.computer.failed" in rules


def test_responses_unknown_item_still_mapped():
    items = [
        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "x"}]},
        {"type": "future_widget_call", "id": "w1", "payload": {"k": 1}, "status": "completed"},
    ]
    traj = openai_responses_to_trajectory(items, session_id="unk")
    assert any(
        (s.get("action") or {}).get("name") == "future_widget_call"
        for s in traj["steps"] if s.get("action")
    )
    assert "future_widget_call" in (traj.get("meta") or {}).get("skipped_or_unmapped_types", [])
    assert any(
        "unmapped_responses_item" in (s.get("thought") or "")
        for s in traj["steps"]
    )


def _list_tools_error_items():
    return [
        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "列工具"}]},
        {
            "type": "mcp_list_tools",
            "id": "list_err",
            "server_label": "files",
            "error": {"message": "server unreachable"},
        },
        {
            "type": "compaction",
            "id": "cmp_1",
            "status": "failed",
            "error": {"message": "too large"},
        },
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "列工具未完成"}],
            "status": "completed",
        },
    ]


def test_protocol_mode_ignore_fail_no_distribution():
    """默认 ignore_fail：list_tools/compaction error 不进 failure_types。"""
    traj = openai_responses_to_trajectory(
        _list_tools_error_items(), session_id="proto_ignore",
    )
    assert traj["meta"]["protocol_mode"] == "ignore_fail"
    assert validate_trajectory_dict(traj) == []
    analysis = analyze_trajectory_dict(traj)
    fails = {ft for pa in analysis.paths for ft in pa.failure_types}
    assert "tool_error" not in fails
    # errors recorded as ignored protocol_events
    pe = traj["meta"].get("protocol_events") or []
    assert any(e.get("type") == "mcp_list_tools" and e.get("ignored") for e in pe)


def test_protocol_mode_audit_meta_only():
    traj = openai_responses_to_trajectory(
        _list_tools_error_items(),
        session_id="proto_audit",
        protocol_mode="audit",
    )
    pe = traj["meta"].get("protocol_events") or []
    assert pe
    assert all(e.get("audit") or e.get("type") for e in pe)
    analysis = analyze_trajectory_dict(traj)
    fails = {ft for pa in analysis.paths for ft in pa.failure_types}
    assert "tool_error" not in fails
    assert any("[protocol_audit]" in (s.get("observation") or "") for s in traj["steps"])


def test_protocol_mode_fail_on_error_list_tools_only():
    """fail_on_error：仅 mcp_list_tools error → tool_error；compaction 仍不进 distribution。"""
    traj = openai_responses_to_trajectory(
        _list_tools_error_items(),
        session_id="proto_fail",
        protocol_mode="fail_on_error",
    )
    analysis = analyze_trajectory_dict(traj)
    fails = {ft for pa in analysis.paths for ft in pa.failure_types}
    assert "tool_error" in fails
    rules = [
        e.rule_id
        for pa in analysis.paths
        for sa in pa.step_analyses
        for e in (sa.evidence or [])
    ]
    assert "responses.protocol.mcp_list_tools" in rules
    pe = traj["meta"].get("protocol_events") or []
    assert any(e.get("type") == "mcp_list_tools" and e.get("escalated") for e in pe)
    # compaction stays non-escalated
    assert any(e.get("type") == "compaction" and not e.get("escalated") for e in pe)
