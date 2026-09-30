# Trace Debugger

## 项目定位

面向中小型 Agent 团队的本地轨迹失败检测与 CI 规则回归工具，负责发现和输出失败证据，不负责最终发布裁决。

## 对外口径

可以表述为本地/CI 失败治理工具；不能表述为生产 APM、云 tracing 或自动修复系统。当前状态与 P0 见 [`docs/STATUS.md`](docs/STATUS.md)。

## 结构入口

核心代码在 `trace_debugger/`，轨迹契约在 `schemas/`，黄金集与回归测试在 `fixtures/`、`tests/`，定位与证据在 `docs/`。

[![CI](https://github.com/weihuaguo270-ops/trace-debugger/actions/workflows/test.yml/badge.svg)](https://github.com/weihuaguo270-ops/trace-debugger/actions/workflows/test.yml) [![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org) [![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**面向中小型 Agent 团队的本地失败治理工具** — 把难以阅读的执行轨迹，变成可统计、可复盘、**可进 CI** 的失败信号。

> **主定位：Agent 轨迹失败检测与规则回归**（确定性失败信号；非完整 APM、非云 tracing）  
> 发版最终裁决在 [llm-eval-engine](https://github.com/weihuaguo270-ops/llm-eval-engine) · 分工见 [docs/POSITIONING_AND_DIVISION.md](docs/POSITIONING_AND_DIVISION.md)  
> 独立项目 · 框架无关 · [react-agent](https://github.com/weihuaguo270-ops/react-agent) 仅为参考集成

## 业务目标

本项目是 **Agent 轨迹失败检测与规则回归**工具：接入标准轨迹后，判断「哪里出现硬失败、失败分布是否比上一版变差」，并产出可供 [llm-eval-engine](https://github.com/weihuaguo270-ops/llm-eval-engine) 消费的失败证据；**不**自行做最终发版裁决。

| 业务环节 | 项目交付 | 决策用途 |
|----------|----------|----------|
| 运行采集 | Format B 轨迹、StepWatcher、Artifact 引用 | 保留可复盘的执行证据 |
| 失败识别 | 可解释启发式失败标签、JSONL findings、统计聚合 | 定位工具、检索、验收、策略和轨迹问题 |
| 版本比较 | baseline、`scan --compare`、golden CI | 检查规则层失败分布是否退化 |
| 下游交接 | failures / findings 导出 | 供评测仓 failure-gate 与复盘使用 |

**当前阶段：** 适合本地或 CI 的低成本回归门禁。已在独立 GitHub 沙箱中复现验收失败，输出
`acceptance_failed` 并交给评测引擎形成 `hold`；这属于 `external_real_sandbox`，不是生产团队接入。
项目仍不是完整 APM、云 tracing 或自动修复系统；真实团队接入仍需脱敏、权限和时序存储。

**2026-09-14 文档更新：** Unreleased 进展对齐 — OpenAI/Anthropic adapters（含 Responses/stream）、
结构化 computer/shell 失败、`approval_denied`、`incomplete` mark、`search_weak`、`protocol_mode`、
`--fail-on`；黄金集 **29** 条。契约与门禁仍以 v0.6.0 failure-gate 为主干。

---

## 主场景（优先用这个讲清楚价值）

Agent 团队把运行轨迹接入 trace-debugger 之后：

1. **自动识别** 常见硬失败（工具报错、验收失败、搜索空/弱结构、批准拒绝、半截流打标、重复调用等）
2. **形成记录** — JSONL + 可读 log，便于复盘
3. **发版前对比** — `tdebug scan` + `--compare` 发现失败分布是否变差
4. **结构化 findings** — `--findings-out` 输出门禁判定 + 修复边界（Harness Health，v0.2.7+）
5. **CI 门禁** — 黄金集 32 条 + 可选 `--fail-on` 拦 CI

```bash
pip install -e .
tdebug scan trajectories/ 50 \
  --json-out snapshots/latest.json \
  --compare snapshots/baseline.json \
  --fail-on hold \
  --findings-out snapshots/latest_findings.json \
  --project-root .
python -m pytest tests/test_failure_golden.py   # CI 同款
```

输入：[Format B](schemas/agent_trajectory.schema.json) 轨迹 JSON · 输出：失败标签、分布表、回归 diff

完整价值说明（含**已证明 / 未证明**）：[docs/VALUE.md](docs/VALUE.md)

---

## 何时选本项目

| 选 trace-debugger | 选 Langfuse / LangSmith 等 |
|-------------------|----------------------------|
| 只需本地 JSON 轨迹 + 失败分类 | 需要生产链路 tracing、团队看板 |
| 要极低成本建 **回归基线 + CI 门禁** | 要云 SaaS、采样、告警一体化 |
| 规则可解释、可 git 验证 | 深度集成特定 Agent SDK 栈 |

---

## 给谁用

| 角色 | 在主场景里的作用 |
|------|------------------|
| **Agent 开发者** | 接入轨迹 / adapter；本地 `tdebug` 查单条 |
| **质量 / 测试** | 维护 baseline、`--compare`、CI golden |
| **项目负责人** | 看失败分布与周报；判断能否发版 |

---

## 辅助能力（非主卖点）

<details>
<summary>运行时 StepWatcher、单条复盘、Judge prompt</summary>

- **运行时**：`FailureHarness` + `StepEvent` — 边跑边记，见 [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md)
- **调试**：`tdebug replay`、`tdebug judge`（导出 prompt 接 eval）
- **演示**：`examples/portable_harness_demo.py`、`examples/adapters/`

</details>

---

## 交付与证据

| 已交付 | 说明 |
|--------|------|
| 启发式失败标签 + CLI | `tdebug` / `stats` / `validate`（含 adapters 结构化信号） |
| 黄金集 + CI | 32/32 — 规则回归（含 `approval_denied` / `search_weak` / `acceptance_failed` / `incomplete_stream`） |
| 发版 compare | `--compare` + 试点 baseline / 案例 |
| **Harness Health** (v0.2.7) | 五维 Agent Work Loop · 证据状态 · `findings.json` · intervention ledger |
| **跨 Agent Episode** (v0.4.0) | 导入 `evaluation-episode/v1`，保留框架、Agent 版本、split 与业务终态校验证据；无需安装轨迹生产方 SDK |
| **可移植数据目录** (v0.4.0) | failure log 默认写入平台用户数据目录；`TDEBUG_DATA_DIR` / `TDEBUG_RECORD_PATH` 可覆盖 |

| 试点与当前集成 | 链接 |
|----------------|------|
| Phase 0–5 + 能力 manifest | [docs/pilot/README.md](docs/pilot/README.md) |
| held-out 基线 7/80 | [docs/pilot/CAPABILITY_HELD_OUT_RUN.md](docs/pilot/CAPABILITY_HELD_OUT_RUN.md) |
| 发版前决策案例 | [docs/cases/regression_gate_20260730.md](docs/cases/regression_gate_20260730.md) |
| 干预 ledger（Learning Capture） | [docs/intervention_ledger.json](docs/intervention_ledger.json) |
| 业务证明自评 ~65% | [docs/VALUE.md](docs/VALUE.md) |

外部沙箱证据：[`agent-delivery-sandbox`](https://github.com/weihuaguo270-ops/agent-delivery-sandbox)
已完成非模拟 PR 的接受、拒绝、回滚，以及 `acceptance_failed -> hold` 故障回流。

仍缺：真人执行耗时基线、生产团队接入复现、长期时序数据和告警闭环。

Golden CI：[docs/golden_evidence_baseline.md](docs/golden_evidence_baseline.md)

---

## 命令参考

| 命令 | 说明 |
|------|------|
| `tdebug scan <dir> [N] --compare baseline.json` | **主路径**：批量 + 规则回归对比（含率差） |
| `tdebug scan … --failures-out failures.json` | **failure-gate/v1**：供 llm-eval-engine 消费 |
| `tdebug scan … --compare baseline.json --fail-on hold` | 门禁达 hold（或 `--fail-on review`）则 **exit 1** 拦 CI |
| `tdebug scan … --findings-out findings.json` | Harness Health：门禁判定 + 修复建议 |
| `tdebug scan … --task-type qa\|code\|creative` | 任务类型分析配置 |
| `tdebug … --contracts` | 启用 tool contract → `tool_error` |
| `tdebug <file.json>` | 单条分析（含步骤证据） |
| `tdebug stats [jsonl]` | 失败类型聚合 |
| `tdebug validate <file.json>` | Format B 校验 |

<details>
<summary>完整命令与选项</summary>

```bash
tdebug fixtures/failure_golden/tool_error.json --record
tdebug failures .tdebug/failures.jsonl
tdebug judge offtrack.json --prompt-out judge.txt
```

选项：`--json-out` · `--findings-out` · `--project-root` · `--record` · `--compare` · `--fail-on` · `--incomplete` · `--session` · `--schema`（validate）

</details>

---

## 轨迹格式与集成

- Schema：[schemas/agent_trajectory.schema.json](schemas/agent_trajectory.schema.json)
- 集成：[docs/INTEGRATIONS.md](docs/INTEGRATIONS.md)（含 OpenAI/Anthropic 缺口、LangGraph 不硬转 steps）· Adapters：[examples/adapters/](examples/adapters/)
- **Adapters（已实现，无 SDK）：** messages / stream coalesce / Responses Items → Format B；见 `trace_debugger.adapters` 与 [examples/adapters/](examples/adapters/)
- Responses：`on_incomplete`、`protocol_mode`（协议失败 ≠ 任务失败）；结构化 computer/shell/MCP 失败信号
- Episode：`evaluation-episode/v1` 可由不同 Agent SDK 导出后离线导入；本仓不依赖 LangGraph、OpenAI Agents SDK 或生产方 Python 包
- **LangGraph / 状态机：** 不要把整图强制拍平为 `steps`；仅在明确的工具/ReAct 边界上局部导出 Format B（见 INTEGRATIONS）
- 运行数据：[docs/PORTABILITY.md](docs/PORTABILITY.md)；默认不再写入已安装包目录
- Analyzer 可配置：`final_answer_markers`、`search_tool_names`、`search_min_results` / `search_require_url`（qa profile）等

---

## 文档

| 文档 | 说明 |
|------|------|
| [docs/POSITIONING_AND_DIVISION.md](docs/POSITIONING_AND_DIVISION.md) | **与 llm-eval-engine 定位分工（避免重复）** |
| [docs/VALUE.md](docs/VALUE.md) | **价值、主场景、业务证明缺口、下一步** |
| [docs/pilot/WORKFLOW.md](docs/pilot/WORKFLOW.md) | 试点 scan + compare + findings 工作流 |
| [docs/intervention_ledger.json](docs/intervention_ledger.json) | 纵向干预记录（Learning Capture） |
| [schemas/findings.schema.json](schemas/findings.schema.json) | findings.json 契约 |
| [docs/RISKS.md](docs/RISKS.md) | 风险与边界 |
| [docs/GOLDEN_FAILURE_INDEX.md](docs/GOLDEN_FAILURE_INDEX.md) | 黄金集 |
| [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) | Format B、Episode 与运行时 Hook 接入 |
| [docs/PORTABILITY.md](docs/PORTABILITY.md) | failure log 路径和 SDK 解耦约定 |
| [SECURITY.md](SECURITY.md) | 数据安全 |

---

## 诚实边界

我们有意收窄 scope，避免对外过度承诺：

- **准确率**：规则是 CI 门禁，不是判决书；`llm_offtrack` 曾有真实批次假阳性（6→1 校准）→ [RISKS.md](docs/RISKS.md) §1
- **业务价值**：试点 Phase 0–5 + held-out 能力轨；[VALUE.md](docs/VALUE.md) · [CAPABILITY_MANIFEST.md](docs/pilot/CAPABILITY_MANIFEST.md)
- **数据安全**：`--record` 落盘 query/thought；企业须 adapter 脱敏 → [SECURITY.md](SECURITY.md)
- **定位**：失败治理门禁，**不**替代完整 APM

---

## Artifact 轨迹字段

Format B 支持 input_artifacts、output_artifacts 和步骤级 artifacts。
Trace Debugger 将这些字段作为轨迹引用保存和校验，不计算图片、视频或音频的语义质量。

## License

MIT — [CONTRIBUTING.md](CONTRIBUTING.md) · [CHANGELOG.md](CHANGELOG.md)
