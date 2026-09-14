# Agent Adapter 样板

将**不同框架的内部事件**映射为 `trace_debugger.harness.StepEvent` / Format B。

| 文件 | 模拟框架 | 怎么用 |
|------|----------|--------|
| [`react_loop.py`](react_loop.py) | ReAct / 线性 tool loop | **推荐对照**；字段接近 Format B |
| [`openai_messages.py`](openai_messages.py) | OpenAI Chat `messages` + `tool_calls` | **已实现**（core: `trace_debugger.adapters.openai_messages`） |
| [`anthropic_messages.py`](anthropic_messages.py) | Anthropic `content` blocks + `tool_use` | **已实现**（core: `trace_debugger.adapters.anthropic_messages`） |
| （包内）`openai_stream` / `openai_responses` | Chat 流式 coalesce；Responses Items | **已实现**；默认半截流拒绝 / `on_incomplete=mark`；`protocol_mode` 控 list_tools 等（默认不当任务失败）；computer/MCP/search/shell + 未知 Item 兜底 |
| [`graph_style.py`](graph_style.py) | 「已是步骤形态」的节点记录 | **有限示例**：仅当节点≈一步时使用；**不要**整图拍平 |

缺口政策与 LangGraph 边界见  
[docs/INTEGRATIONS.md](../../docs/INTEGRATIONS.md)「主流执行流与 Format B」。

```python
from trace_debugger.adapters import openai_messages_to_trajectory

traj = openai_messages_to_trajectory(messages, session_id="run-1")
```

测试：

```bash
pytest tests/test_adapters.py tests/test_message_adapters.py -v
python examples/portable_harness_demo.py
tdebug validate fixtures/failure_golden/tool_error.json
```
