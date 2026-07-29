# Trace Debugger

[![CI](https://github.com/weihuaguo270-ops/trace-debugger/actions/workflows/test.yml/badge.svg)](https://github.com/weihuaguo270-ops/trace-debugger/actions/workflows/test.yml) [![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org) [![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Agent 轨迹失败治理工具** — 读标准 JSON 轨迹，做启发式失败检测、记录、聚合统计与复盘；可嵌入任意 ReAct 类 Harness 的运行时 hook。

> 独立项目：不依赖 LangChain / LangGraph / LangSmith，也不依赖特定 Agent 运行时。  
> [react-agent](https://github.com/weihuaguo270-ops/react-agent) 是**参考集成**，不是前置条件。

---

## 要解决什么问题

Agent 跑完只留下 JSON 轨迹，失败行为分散、难复盘、难汇总。本工具提供一条可本地运行的闭环：

| 环节 | 能力 |
|------|------|
| **检测** | 7 类启发式失败分类（非 LLM Judge） |
| **记录** | JSONL 事件流 + 可读 `.log` + 会话 Markdown 摘要 |
| **复盘** | 单条报告、逐步回放、Judge prompt |
| **聚合** | 按失败类型统计（次数、占比、高频工具） |
| **对比** | 扫描快照 vs 历史 baseline |

**输入**：符合 [Format B](schemas/agent_trajectory.schema.json) 的轨迹 JSON  
**输出**：根因标签、失败日志、分布表、可读 digest

---

## 给谁用

| 角色 | 典型用法 |
|------|---------|
| **Agent 开发者** | 任意 Harness 落盘 JSON → `tdebug` 复盘；可选 `StepWatcher` 边跑边记 |
| **项目负责人** | `failures.log`、`sessions/*.md`、周报与 golden 证据 |
| **CI / 质量门禁** | 黄金集 27 条、`publish_golden_evidence`、失败分布快照 |

---

## 与其他工具的关系

| 工具 | 关系 |
|------|------|
| **LangSmith** | 不同路线：LangSmith 服务 LangChain 生态的云 tracing；本工具是**本地、Schema 驱动、无账号**的失败治理 |
| **react-agent** | 第一个官方参考集成（Harness + StepWatcher），[见集成指南](docs/INTEGRATIONS.md) |
| **llm-eval-engine** | 下游：`tdebug judge` 导出 prompt，可接 Process Reward |

---

## 典型工作流

### 1. 离线：已有轨迹 JSON

```bash
pip install -e .
tdebug fixtures/failure_golden/tool_error.json
tdebug scan fixtures/failure_golden 27 --record
tdebug stats .tdebug/failures.jsonl
```

### 2. 运行时：嵌入你的 Agent 循环

推荐用 **`FailureHarness`** + **`StepEvent`**（框架无关，只需写适配器）：

```python
from trace_debugger.harness import FailureHarness, RunContext, StepEvent

harness = FailureHarness(RunContext(session_id, query, model))
harness.after_observation(StepEvent(step_index=1, tool_name="search", tool_input={...}, observation="..."))
harness.finish(final_answer=answer, total_duration=elapsed)
```

演示：`python examples/portable_harness_demo.py` · 指南：[docs/INTEGRATIONS.md](docs/INTEGRATIONS.md)  
环境变量：`TDEBUG_RECORD_PATH`

### 3. 集成 react-agent（可选）

```bash
pip install -e ../trace-debugger   # 在 react-agent 仓内
# 见 docs/INTEGRATIONS.md
```

---

## 交付状态

| 能力 | 状态 |
|------|------|
| Format B 解析（含多路径） | ✅ |
| 7 类失败启发式 + CLI | ✅ |
| 失败记录 v2 + `tdebug stats` | ✅ |
| StepWatcher 运行时 | ✅ |
| 黄金证据集 27 条 + CI | ✅ **100%** |
| 自动修复 Agent | ❌ 不在范围 |

证据：[docs/golden_evidence_baseline.md](docs/golden_evidence_baseline.md)

---

## 命令参考

| 命令 | 说明 |
|------|------|
| `tdebug <file.json>` | 分析轨迹 |
| `tdebug replay <file.json>` | 逐步回放 |
| `tdebug judge <file.json>` | 生成 Judge prompt |
| `tdebug scan <目录> [N]` | 批量扫描 |
| `tdebug failures [jsonl]` | 失败 digest |
| `tdebug stats [jsonl]` | 按类型聚合 |
| `tdebug validate <file.json>` | 校验 Format B（`--schema` 严格模式） |

常用选项：`--json-out` · `--record [PATH]` · `--compare PATH` · `--session ID` · `--stats-json-out`

<details>
<summary>命令示例</summary>

```bash
tdebug fixtures/failure_golden/tool_error.json --json-out report.json --record
tdebug failures .tdebug/failures.jsonl
tdebug stats .tdebug/failures.jsonl --stats-json-out stats.json
tdebug scan fixtures/failure_golden 27 --compare docs/snapshots/prev.json
```

</details>

---

## 轨迹格式

Canonical schema：**[schemas/agent_trajectory.schema.json](schemas/agent_trajectory.schema.json)**

要点：

- `step` **1-based**；字段 `thought` / `action` / `observation`
- 多路径：`paths[]` 或 step 上 `path_id` / `branch_id`
- 失败标记（可选）：`failure_tags`、`failure_summary`、`failure` 块

Fixtures：

- `fixtures/failure_golden/` — 27 条标准证据集 + `manifest.json`
- `examples/failure_bundle/` — 5 条快速演示
- `examples/adapters/` — graph / react 两种框架 adapter 样板

**Analyzer 可配置**（跨 Agent 语义差异）：

```python
Analyzer(
    final_answer_markers=("FINAL ANSWER", "ANSWER:"),
    search_tool_names=("tavily_query", "web_lookup"),
    search_tool_substrings=("search", "query"),
)
```

---

## 文档

| 文档 | 说明 |
|------|------|
| [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) | 接入任意 Harness + react-agent 参考集成 |
| [schemas/README.md](schemas/README.md) | Format B 互操作规则 |
| [docs/GOLDEN_FAILURE_INDEX.md](docs/GOLDEN_FAILURE_INDEX.md) | 黄金集索引 |
| [docs/FAILURE_INDEX.md](docs/FAILURE_INDEX.md) | 失败分布周报 |

---

## 诚实边界

- 启发式检测，非 ground truth
- 不自动修复；优化靠人工或外部 eval
- 不替代 LangSmith / 生产 APM

---

## License

MIT — [CONTRIBUTING.md](CONTRIBUTING.md) · [SECURITY.md](SECURITY.md) · [CHANGELOG.md](CHANGELOG.md)
