# 集成指南

trace-debugger 通过 **Format B JSON** 与任意 Agent 解耦。推荐用本仓提供的可移植层 `trace_debugger.harness`，只需实现「你的 step → `StepEvent`」映射。

如果上游同时需要业务终态验证和发布分栏，可直接传入
`evaluation-episode/v1` envelope：

```python
from trace_debugger import import_evaluation_episode, analyze_trajectory_dict

episode = import_evaluation_episode(payload)
analysis = analyze_trajectory_dict(episode.trajectory)
```

导入器会保留 `framework`、`agent_version`、`split` 和 `state_verification`，
但不会重新计算业务终态；该验证由业务 Verifier 或 llm-eval-engine 负责。

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

样板 adapter：[`examples/adapters/`](../examples/adapters/)（`react_loop` 推荐对照；`graph_style` 仅作「已有工具边界事件」时的有限示例，见下节）

---

## 主流执行流与 Format B（缺口与边界）

Format B 描述的是 **线性（或显式多 path）的 ReAct / tool-call 步骤序列**，不是通用执行图 IR。接入前先判断：你的运行时是否**本来就有**「一轮模型输出 + 可选工具 + 观测」这种步。

### OpenAI / Anthropic tool-calling — 语义够，落盘有缺口

Chat Completions / Messages API、Anthropic Messages、多数 Agents SDK 的 tool loop **语义上**能覆盖 Format B（assistant 文本/tool_use → tool result → … → 最终文本）。缺口在**形状与约定**，不是「能不能跑工具」：

| Format B 需要 | 主流 API / SDK 常见现状 | 建议补法 |
|---------------|------------------------|----------|
| `session_id` | 往往只有 request id / 无稳定 run id | 接入方生成 UUID，整次 tool loop 共用 |
| `query` | 在 messages[0] 或 thread 里 | 抽出首条 user（或多轮则约定「本 run 的任务句」） |
| `steps[]` 扁平列表 | messages / content blocks 是交错列表 | **按轮展平**：一轮 = 一次 assistant（含 0..N 个 tool_use）+ 对应 tool results；`step` 从 **1** 起 |
| 单步 `action.name` + `arguments` | OpenAI：`tool_calls[].function.name/arguments`（arguments 常已是 JSON **字符串**）；Anthropic：`tool_use.name` + `input`（多为 **object**） | 写入 `action.arguments`（object 可原样或 `json.dumps`）；Anthropic 的 `input` 不要丢字段 |
| 同轮多个 tool_calls | 一条 assistant 消息带多个 tool_calls | **不要**强行揉成一步；优先拆成多步，或一步用 `actions[]`（Format B 支持多 tool）并保证观测顺序对齐 |
| `observation` | 下一条 `role=tool` / `tool_result` | 按 `tool_call_id` 对齐；错误要进 observation 或可解析的 error 字段，否则 `tool_error` 启发式可能漏检 |
| 顶层 `final_answer` | 常是「最后一条无 tool_calls 的 assistant 文本」 | 显式拷到顶层；不要只留在 messages 末尾 |
| 结束标记 | 一般没有 `FINAL ANSWER` 字样 | 配置 `Analyzer(final_answer_markers=...)` 或接受「仅靠顶层 `final_answer`」；否则易误报 `no_answer` |
| 并行 tool + 流式 | 流式 delta、部分 SDK 并行执行 | 先落**完整**一轮再映射；半截流式帧不要当一步 |

推荐接入姿态：

1. 在 **tool loop 结束时**（或每轮 commit 后）从 messages 导出 Format B，而不是改模型 API。  
2. 用 `tdebug validate` 卡字段；再用单条 `tdebug` 看启发式是否符合预期。  
3. 搜索类工具名若不含 `search`，配置 `search_tool_names`。

OpenAI / Anthropic **原生 JSON ≠ Format B**；差一层「messages → steps」exporter，本仓已实现无 SDK 依赖的 `trace_debugger.adapters.openai_messages_to_trajectory` / `anthropic_messages_to_trajectory`（见 examples/adapters/）。

流式 / Responses 半截导出：

| 参数 | 行为 |
|------|------|
| `on_incomplete="reject"`（**默认**） | 无 `finish_reason` / Item `in_progress` → 抛 `IncompleteStreamError`，不落盘 |
| `on_incomplete="mark"` | 尽力 coalesce / 映射，Format B 带 `meta.incomplete=true`，并打 `incomplete_stream`（rule_id=`responses.incomplete`） |

CLI 可用 `--incomplete mark` 作为 adapter kwargs 约定（**与** `--fail-on` **无关**：`--fail-on` 只在 `scan --compare` 后门禁 exit code）。

```python
from trace_debugger.adapters import (
    openai_responses_to_trajectory,
    chat_stream_to_trajectory,
)

traj = openai_responses_to_trajectory(items, on_incomplete="mark")
# 或
traj = chat_stream_to_trajectory(prior, chunks, on_incomplete="mark")
```

协议项（list_tools / compaction / additional_tools）策略 — **协议失败 ≠ Agent 任务失败**：

| `protocol_mode` | 行为 |
|-----------------|------|
| `ignore_fail`（**默认**） | 可映射；带 `error` 也不进 scan `failure_types` distribution |
| `audit` | 映射 + `meta.protocol_events`；observation 可带 `[protocol_audit]`；仍不进 distribution |
| `fail_on_error` | 仅 `mcp_list_tools` 带 error → `tool_error`（`responses.protocol.mcp_list_tools`）；compaction / additional_tools 仍只 audit |

```python
traj = openai_responses_to_trajectory(items, protocol_mode="audit")
```

最终 hold/release 裁决仍归 **llm-eval-engine**，本仓只提供可解释规则信号。



### LangGraph / 状态机图 — 不要强硬转化为 `steps`

**本仓不建议**把任意 LangGraph（或同类状态机）的 node/edge/checkpoint **强制拍平**成一条 Format B `steps[]`。

原因：

- 图的语义单位是 **节点与状态迁移**（分支、汇合、retry、子图、interrupt），不是 ReAct 步进。
- 强硬线性化会丢失汇合/并行结构，导致假的「重复调用」「无最终答案」「offtrack」等信号，**比不接入更糟**。
- Format B 的 `paths[]` 只能表达有限分支，**不是**通用 DAG/状态机序列化格式。

推荐做法（按优先级）：

| 做法 | 说明 |
|------|------|
| **1. 只导出工具边界轨迹** | 若图中真正要做失败回归的是 tool 调用链，在 **tool 节点**（或 wrapper）上记录 Format B 步骤；图拓扑仍留在 LangGraph/Langfuse，不交给 tdebug 解释 |
| **2. 双轨存储** | Episode / 元数据保留 `framework=langgraph` 与原生 run/trace id；Format B 仅承载「可选的线性 tool 子轨迹」。本仓 `import_evaluation_episode` **不**把图编译成 steps |
| **3. 不要为了 scan 而伪造 steps** | 若一次 run 主要是路由/状态，没有稳定的 thought→tool→obs 边界，**不要**为过 `validate` 而编造步骤；改用评测仓业务终态 / 过程分，或只对子 Agent（ReAct 子图）接 tdebug |
| **4. `examples/adapters/graph_style.py`** | 仅演示「**已经是**类步骤的节点记录 → StepEvent」；**不是**「把整张 LangGraph 编译成 Format B」的官方方案 |

一句话：**tool-calling 消息流 → 值得映射成 Format B；LangGraph 整图 → 不硬转 steps，只在有明确工具/ReAct 边界时局部导出。**

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

本仓产出失败信号；**发布裁决与 Judge 执行**在对端。分工见 [POSITIONING_AND_DIVISION.md](./POSITIONING_AND_DIVISION.md)。

稳定交接（**failure-gate/v1**）：

```bash
tdebug scan trajectories/ 50 \
  --failures-out snapshots/failures.json \
  --compare snapshots/baseline.json \
  --findings-out snapshots/findings.json \
  --task-type qa
```

- `--failures-out` → `schemas/failures.schema.json`（`schema_version=failure-gate/v1`）  
  字段含 `distribution`、`distribution_rates`、`trajectories[].evidence_chain`  
- 对端示例：`run_cross_agent_release.py ... --failure-gate snapshots/failures.json`

仅导出 Judge prompt（不执行）：

```bash
tdebug judge run.json --prompt-out judge.txt
```

任务类型：`--task-type default|qa|code|creative`（creative/code 关闭词重叠 offtrack）。  
Tool contract：`--contracts` / `--contracts-file`（映射为 `tool_error` + `tool_contract.*` 证据）。
