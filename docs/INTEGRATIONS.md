# 集成指南

trace-debugger 通过 **Format B JSON** 与任意 Agent 解耦。推荐用本仓提供的可移植层 `trace_debugger.harness`，只需实现「你的 step → `StepEvent`」映射。

---

## 可移植集成（推荐）

### 核心类型

| 类型 | 作用 |
|------|------|
| `RunContext` | 一次运行的 `session_id` / `query` / `model` |
| `StepEvent` | 中性 step 事件（thought、tool、observation） |
| `FailureHarness` | 运行时：`after_observation()` + `finish()` |
| `build_trajectory_dict()` | 离线：只导出 Format B，不跑 Agent |
| `enrich_trajectory_dict()` | 离线：补全 `failure_tags` 等字段 |
| `validate_trajectory_dict()` | 导出前轻量校验 |

### 运行时（2 个 hook）

```python
from trace_debugger.harness import FailureHarness, RunContext, StepEvent

harness = FailureHarness(RunContext(session_id="run-1", query="...", model="gpt-4"))

for i, raw in enumerate(agent.run(), start=1):
    event = your_adapter(raw, step_index=i)   # ← 唯一需要自定义的函数
    harness.after_observation(event)
    step_record.update(harness.last_failure_tags())  # 可选

harness.finish(final_answer=answer, total_duration=elapsed)
save_json(harness.trajectory_dict())
```

演示：`python examples/portable_harness_demo.py`

### 离线 exporter-only

Agent 已落盘 JSON，或只想事后分析：

```python
from trace_debugger.harness import build_trajectory_dict, enrich_trajectory_dict, RunContext, StepEvent

traj = build_trajectory_dict(context, events, final_answer=answer)
traj = enrich_trajectory_dict(traj)   # 可选：补 failure 字段
# 或 CLI: tdebug saved.json
```

### 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `TDEBUG_RECORD_PATH` | `.tdebug/failures.jsonl` | `FailureHarness` / StepWatcher 默认记录路径 |

---

## 适配器要写什么

实现一个函数，把**你框架的 step** 转成 `StepEvent`：

```python
def your_adapter(raw_step, *, step_index: int) -> StepEvent:
    return StepEvent(
        step_index=step_index,
        thought=raw_step.llm_text,
        tool_name=raw_step.tool or "",
        tool_input=raw_step.tool_input,   # str 或 dict 均可
        observation=raw_step.tool_output or "",
        duration=raw_step.elapsed_sec,
        tokens=raw_step.token_count,
    )
```

检查清单：

- [ ] `step_index` 从 **1** 开始
- [ ] 工具参数通过 `tool_input` 传入（自动序列化为 JSON 字符串）
- [ ] 最终答案写入轨迹顶层 `final_answer`
- [ ] 导出前 `validate_trajectory_dict(traj)` 无报错

Schema：[`schemas/agent_trajectory.schema.json`](../schemas/agent_trajectory.schema.json)

导出前校验：

```bash
tdebug validate my_run.json
tdebug validate my_run.json --schema   # pip install 'trace-debugger[schema]'
```

### Analyzer 配置（工具名 / 结束标记与框架对齐）

```python
from trace_debugger import Analyzer

analyzer = Analyzer(
    final_answer_markers=("FINAL ANSWER", "ANSWER:"),
    search_tool_names=("tavily_query", "web_lookup"),
    search_tool_substrings=("search",),
)
FailureHarness(context, analyzer=analyzer)
```

样板 adapter：[`examples/adapters/`](../examples/adapters/)（graph-style + react-loop）

---

## 低级 API（仍可用）

直接使用 `StepWatcher` / `failure_tags_from_step` 与 `FailureHarness` 等价，见 [`examples/harness_step_watcher.py`](../examples/harness_step_watcher.py)。

---

## react-agent（参考集成）

[react-agent](https://github.com/weihuaguo270-ops/react-agent) 已实现 `StepEvent` 等价映射，供对照：

- `src/react_agent/harness/step_watcher_bridge.py`
- 环境变量：`REACT_AGENT_STEP_WATCHER`、`REACT_AGENT_FAILURE_LOG`

**非必须** — 仅作参考实现。

---

## llm-eval-engine（可选下游）

```bash
tdebug judge run.json --prompt-out judge.txt
```
