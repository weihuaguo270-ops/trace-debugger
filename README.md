# Trace Debugger

[![CI](https://github.com/weihuaguo270-ops/trace-debugger/actions/workflows/test.yml/badge.svg)](https://github.com/weihuaguo270-ops/trace-debugger/actions/workflows/test.yml) [![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org) [![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**面向中小型 Agent 团队的本地失败治理工具** — 把难以阅读的执行轨迹，变成可统计、可复盘、**可进 CI** 的失败信号。

> **主定位：Agent 回归测试与失败治理门禁**（非完整 APM、非云 tracing）  
> 独立项目 · 框架无关 · [react-agent](https://github.com/weihuaguo270-ops/react-agent) 仅为参考集成

## 业务目标

我把这个项目定位为 **Agent 发布前的失败治理门禁**：开发者接入标准轨迹后，质量负责人可以知道“哪里坏了、是否比上一版变差、能否安全发版”，而不是把日志堆成一个不可行动的总分。

| 业务环节 | 项目交付 | 决策用途 |
|----------|----------|----------|
| 运行采集 | Format B 轨迹、StepWatcher、Artifact 引用 | 保留可复盘的执行证据 |
| 失败识别 | 7 类可解释启发式、JSONL findings、统计聚合 | 定位工具、检索、策略和轨迹问题 |
| 版本比较 | baseline、`scan --compare`、golden CI | 检查发版后失败分布是否退化 |
| 负责人协作 | 可读报告、修复边界、intervention ledger | 支持 review/hold 与后续复盘 |

**当前阶段：** 适合本地或 CI 的低成本回归门禁，不是完整 APM、云 tracing 或自动修复系统；真实团队接入仍需脱敏、权限、时序存储和外部复现验证。

---

## 主场景（优先用这个讲清楚价值）

Agent 团队把运行轨迹接入 trace-debugger 之后：

1. **自动识别** 7 类常见失败（工具报错、搜索空结果、重复调用等）
2. **形成记录** — JSONL + 可读 log，便于复盘
3. **发版前对比** — `tdebug scan` + `--compare` 发现失败分布是否变差
4. **结构化 findings** — `--findings-out` 输出门禁判定 + 修复边界（Harness Health，v0.2.7+）
5. **CI 门禁** — 黄金集 27 条 + 可选分布快照

```bash
pip install -e .
tdebug scan trajectories/ 50 \
  --json-out snapshots/latest.json \
  --compare snapshots/baseline.json \
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
| 7 类启发式 + CLI | `tdebug` / `stats` / `validate` |
| 黄金集 + CI | 27/27 — 规则回归 |
| 发版 compare | `--compare` + 试点 baseline / 案例 |
| **Harness Health** (v0.2.7) | 五维 Agent Work Loop · 证据状态 · `findings.json` · intervention ledger |

| 试点（v0.2.7） | 链接 |
|----------------|------|
| Phase 0–5 + 能力 manifest | [docs/pilot/README.md](docs/pilot/README.md) |
| held-out 基线 7/80 | [docs/pilot/CAPABILITY_HELD_OUT_RUN.md](docs/pilot/CAPABILITY_HELD_OUT_RUN.md) |
| 发版前决策案例 | [docs/cases/regression_gate_20260730.md](docs/cases/regression_gate_20260730.md) |
| 干预 ledger（Learning Capture） | [docs/intervention_ledger.json](docs/intervention_ledger.json) |
| 业务证明自评 ~65% | [docs/VALUE.md](docs/VALUE.md) |

仍缺：真人秒表、非模拟 PR hold、外部团队复现。

Golden CI：[docs/golden_evidence_baseline.md](docs/golden_evidence_baseline.md)

---

## 命令参考

| 命令 | 说明 |
|------|------|
| `tdebug scan <dir> [N] --compare baseline.json` | **主路径**：批量 + 回归对比 |
| `tdebug scan … --findings-out findings.json` | Harness Health：门禁判定 + 修复建议 |
| `tdebug <file.json>` | 单条分析 |
| `tdebug stats [jsonl]` | 失败类型聚合 |
| `tdebug validate <file.json>` | Format B 校验 |

<details>
<summary>完整命令与选项</summary>

```bash
tdebug fixtures/failure_golden/tool_error.json --record
tdebug failures .tdebug/failures.jsonl
tdebug judge offtrack.json --prompt-out judge.txt
```

选项：`--json-out` · `--findings-out` · `--project-root` · `--record` · `--compare` · `--session` · `--schema`（validate）

</details>

---

## 轨迹格式与集成

- Schema：[schemas/agent_trajectory.schema.json](schemas/agent_trajectory.schema.json)
- 集成：[docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) · Adapters：[examples/adapters/](examples/adapters/)
- Analyzer 可配置：`final_answer_markers`、`search_tool_names` 等

---

## 文档

| 文档 | 说明 |
|------|------|
| [docs/VALUE.md](docs/VALUE.md) | **价值、主场景、业务证明缺口、下一步** |
| [docs/pilot/WORKFLOW.md](docs/pilot/WORKFLOW.md) | 试点 scan + compare + findings 工作流 |
| [docs/intervention_ledger.json](docs/intervention_ledger.json) | 纵向干预记录（Learning Capture） |
| [schemas/findings.schema.json](schemas/findings.schema.json) | findings.json 契约 |
| [docs/RISKS.md](docs/RISKS.md) | 风险与边界 |
| [docs/GOLDEN_FAILURE_INDEX.md](docs/GOLDEN_FAILURE_INDEX.md) | 黄金集 |
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
