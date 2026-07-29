# Agent Adapter 样板

将**不同框架的内部 step 格式**映射为 `trace_debugger.harness.StepEvent`。

| 文件 | 模拟框架 | 要点 |
|------|----------|------|
| [`graph_style.py`](graph_style.py) | 节点/状态机（类 LangGraph） | 工具名 `tavily_query` → 需 `Analyzer(search_tool_names=...)` |
| [`react_loop.py`](react_loop.py) | ReAct 循环 | 字段接近 Format B，映射简单 |

测试：`pytest tests/test_adapters.py -v`

```bash
python examples/portable_harness_demo.py
tdebug validate fixtures/failure_golden/tool_error.json
```
