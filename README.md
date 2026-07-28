# Trace Debugger

[![CI](https://github.com/weihuaguo270-ops/trace-debugger/actions/workflows/test.yml/badge.svg)](https://github.com/weihuaguo270-ops/trace-debugger/actions/workflows/test.yml) [![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org) [![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Agent 执行失败的可观测与复盘层（学习/配套）** — 在运行或事后，把 Harness 轨迹里的失败行为检测出来、记录下来、汇总成可读的复盘材料，供人工或 eval 迭代优化。

> 定位：不是替代 LangSmith / 生产 APM，而是 react-agent 学习栈里的**失败治理配套**——轻量、可验证、可归档。

---

## 要解决什么问题

Agent 跑完只留下 JSON 轨迹，常见痛点：

| 痛点 | 本项目的回应 |
|------|-------------|
| 失败散落在各 step，人眼难扫 | 7 类启发式打标签 + 逐步摘要 |
| 事后才想起来复盘，上下文已丢 | react-agent 运行时 **StepWatcher** 边跑边记 |
| 只知道「又失败了」，不知道模式 | `tdebug stats` 按类型聚合（次数、占比、高频工具） |
| 改 prompt/工具后说不清有没有变好 | 扫描快照 + `--compare` 对比历史 baseline |

**核心闭环**：检测 → 记录 → 复盘 → 聚合 → 对比 →（人工/eval）优化

---

## 给谁用

| 角色 | 典型用法 |
|------|---------|
| **Agent 开发者** | 单条轨迹复盘、`replay` 逐步看、`judge` 生成深度分析 prompt |
| **项目负责人 / 复盘者** | 看 `failures.log`、`sessions/*.md`、周报与 golden 证据 |
| **CI / 质量门禁** | 黄金集 27 条、`publish_golden_evidence`、失败分布快照 |

---

## 在生态中的位置

```
react-agent（运行 + Harness 录轨迹）
       ↓ StepWatcher 实时写入
trace-debugger（本仓：检测 / 记录 / 聚合 / 离线复盘）
       ↓ judge prompt / 结构化 JSON
llm-eval-engine（可选：Process Reward / 深度 Judge）
       ↓
人工改 prompt、工具、策略 → 再跑 → 对比 baseline
```

| 仓库 | 职责 | 本仓**不做** |
|------|------|-------------|
| [react-agent](https://github.com/weihuaguo270-ops/react-agent) | Agent 运行时、轨迹 Schema、Harness 录制 | 不跑 Agent、不托管模型 |
| **trace-debugger** | 失败分类、JSONL/日志、统计、复盘 CLI | 不自动修复、不做 LLM Judge |
| [llm-eval-engine](https://github.com/weihuaguo270-ops/llm-eval-engine) | 评分与 Judge 流水线 | 不替代其评分逻辑 |

---

## 典型工作流（负责人视角）

### 日常：边跑边记

1. react-agent 开启 StepWatcher（默认 `REACT_AGENT_STEP_WATCHER=1`）
2. 每步工具返回后写入 `.tdebug/failures.jsonl` + 可读 `failures.log`
3. 会话结束生成 `sessions/{session_id}.md` 摘要

### 复盘：看单条或单会话

```bash
tdebug failures .tdebug/failures.jsonl              # 可读 digest
tdebug failures .tdebug/failures.jsonl --session ID
tdebug examples/failure_bundle/tool_error.json      # 离线单条复盘
```

### 周报：看模式、看趋势

```bash
tdebug stats .tdebug/failures.jsonl                 # 按失败类型聚合
tdebug scan examples/failure_bundle 20 \
  --json-out docs/snapshots/latest.json \
  --compare docs/snapshots/prev.json                # 与上周对比
python examples/publish_golden_evidence.py          # 刷新黄金集证据报告
```

### 优化：人工或 eval 闭环

- 根据 `tool_error` / `duplicate` 等分布改工具或 prompt
- `tdebug judge <轨迹>` 导出 prompt → 接 llm-eval-engine 或人工审阅
- 重跑 agent → 新快照 vs 旧 baseline，验证是否改善

---

## 交付状态与可信度

| 能力 | 状态 | 说明 |
|------|------|------|
| 7 类失败启发式检测 | ✅ 已交付 | 见下表 taxonomy |
| 离线复盘 CLI（analyze / replay / scan / judge） | ✅ 已交付 | |
| 失败记录 v2（JSONL + log + session md） | ✅ 已交付 | schema v2，含 `failure_summary` 等 |
| 按类型聚合 `tdebug stats` | ✅ 已交付 | |
| 运行时 StepWatcher + react-agent 集成 | ✅ 已交付 | 需 `pip install -e ../trace-debugger` |
| 扫描对比飞轮 `--compare` | ✅ 已交付 | |
| 黄金证据集 + CI 门禁 | ✅ 已交付 | **27/27 通过**（golden 21 + held_out 6） |
| 自动修复 Agent | ❌ 不在范围 | 优化靠人工或外部 eval |
| LLM-as-Judge 内置执行 | ❌ 不在范围 | 只生成 prompt，Judge 交 eval 栈 |

**证据入口**：[docs/golden_evidence_baseline.md](docs/golden_evidence_baseline.md) · [docs/GOLDEN_FAILURE_INDEX.md](docs/GOLDEN_FAILURE_INDEX.md) · [docs/FAILURE_INDEX.md](docs/FAILURE_INDEX.md)

CI：Ubuntu + Windows（3.10/3.11）、覆盖率门禁、mypy、pip-audit。

---

## 诚实边界

- 分类是**可配置启发式**，不是 ground truth；对外引用请区分 golden / held_out
- **不承诺**零假阳性/假阴性；`llm_offtrack` 等规则会持续用真实轨迹校准
- **不自动改** Agent 行为；报告里的建议是模板提示，非交互式修复
- 真实轨迹目录（如 react-agent `trajectories/`）通常 gitignore；公开物是 `docs/` 下的摘要与快照

---

## 快速开始

```bash
pip install -e .

# 离线复盘一条演示轨迹
tdebug examples/failure_bundle/tool_error.json

# 与 react-agent 联调（ sibling 安装）
pip install -e ../trace-debugger   # 在 react-agent 仓内
# REACT_AGENT_STEP_WATCHER=1 默认开启

# 跑黄金集门禁
python scripts/generate_failure_golden.py
python -m pytest tests/test_failure_golden.py -v
```

---

## 命令参考

| 命令 | 说明 |
|------|------|
| `tdebug <file.json>` | 分析轨迹，识别每条路径的成败原因 |
| `tdebug replay <file.json>` | 逐步骤回放 |
| `tdebug judge <file.json>` | 生成 LLM Judge prompt |
| `tdebug scan <目录> [N]` | 批量分析最新 N 条 |
| `tdebug failures [jsonl]` | 失败事件可读 digest |
| `tdebug stats [jsonl]` | 按失败类型聚合统计 |

常用选项：`--json-out` · `--record [PATH]` · `--compare PATH` · `--prompt-out` · `--stats-json-out` · `--session ID`

<details>
<summary>命令示例（展开）</summary>

```bash
tdebug examples/failure_bundle/tool_error.json --json-out report.json --record
tdebug failures .tdebug/failures.jsonl
tdebug stats .tdebug/failures.jsonl --stats-json-out stats.json
tdebug judge examples/failure_bundle/offtrack.json --prompt-out judge.txt
tdebug scan examples/failure_bundle 20 --json-out docs/snapshots/latest.json --compare docs/snapshots/prev.json
```

</details>

### 记录产物（`.tdebug/`）

| 文件 | 读者 | 用途 |
|------|------|------|
| `failures.jsonl` | 机器 / CI | 事件流，下游聚合 |
| `failures.log` | 人 | 分段可读文本 |
| `sessions/{id}.md` | 人 | 单次会话 Markdown 摘要 |

Step 字段：`failure_tags` · `failure_summary` · `failure_label` · `failure_context` · `failure`（结构化块）

---

## 失败类型（taxonomy）

| 类型 | 检测内容 |
|------|---------|
| `tool_error` | 工具调用报错 |
| `search_empty` | 搜索无有效结果 |
| `search_timeout` | 单步耗时过长（默认 >20s） |
| `duplicate` | 相邻步重复相同工具+参数 |
| `no_answer` | 无最终答案 |
| `llm_offtrack` | 答案与查询内容词重叠过低（有 grounded 豁免） |
| `context_overflow` | token 超预算或溢出文案 |

---

## 技术附录

<details>
<summary>输入格式（Harness Format B）</summary>

- `step` 为 **1-based**；字段：`thought` / `action` / `observation`
- 工具参数：`action.arguments` 或 `args`；多工具 `actions[]`（reader 取首个）
- 多路径：顶层 `paths[]`，或 step 上 `path_id` / `branch_id`
- Schema：[react-agent/schemas/harness_trajectory.schema.json](https://github.com/weihuaguo270-ops/react-agent/blob/main/schemas/harness_trajectory.schema.json)
- Fixture：`examples/failure_bundle/`（5 条）· `fixtures/failure_golden/`（27 条）

</details>

<details>
<summary>StepWatcher API（嵌入其他 Harness）</summary>

```python
from trace_debugger.runtime import StepWatcher, failure_tags_from_step

watcher = StepWatcher(session_id, query, model, record_path=".tdebug/failures.jsonl")
sa = watcher.on_step(step_index=1, action_name="web_search", observation="...", ...)
step_dict.update(failure_tags_from_step(sa, thought=..., action_args=..., observation=...))
analysis = watcher.on_finish(final_answer=answer, total_duration=elapsed)
```

演示：`python examples/harness_step_watcher.py`

</details>

<details>
<summary>示例报告输出</summary>

```text
$ tdebug examples/failure_bundle/tool_error.json

=======================================================
  Trace Debugger — 执行复盘报告
=======================================================
  会话:    fail_tool_error
  ...
  ── 总体评估 ──
  [FAIL] 执行问题较多（1/2 步），建议检查

  ── 路径 0 （主路径） [PASS] ──
    [FAIL] Step 1 [calculator]  0.2s
      原因: calculator 调用失败: ...
      建议: 检查 calculator 的参数或重试
```

</details>

---

## License

MIT — 见 [CONTRIBUTING.md](CONTRIBUTING.md) · [SECURITY.md](SECURITY.md) · [CHANGELOG.md](CHANGELOG.md)
