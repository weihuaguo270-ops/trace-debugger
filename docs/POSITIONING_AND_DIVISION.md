# 跨仓定位与分工：trace-debugger × llm-eval-engine

**读者：** 两仓维护者、简历/评审口径、集成方  
**用途：** 固定「谁回答什么问题、谁产出什么证据、谁做最终发布裁决」，避免定位重复与路线图撞车。  
**状态：** 约定稿（2026-09-13）  
**对端副本：** 请在 [llm-eval-engine](https://github.com/weihuaguo270-ops/llm-eval-engine) 同步同名文档 `docs/POSITIONING_AND_DIVISION.md`；若内容冲突，以两边 README「业务目标」+ 本文最近修订日期较新者为准，并开 PR 对齐。

相关仓：

| 仓 | 仓库 |
|----|------|
| 轨迹失败信号 | [trace-debugger](https://github.com/weihuaguo270-ops/trace-debugger) |
| 评测决策 | [llm-eval-engine](https://github.com/weihuaguo270-ops/llm-eval-engine) |
| Agent 运行时 / capability | [react-agent](https://github.com/weihuaguo270-ops/react-agent) |

---

## 1. 一句话分工

| 项目 | 一句话定位（对外主表述） |
|------|--------------------------|
| **trace-debugger** | Agent **轨迹失败检测与规则回归**：把 Format B / Episode 变成可解释、可统计、可进 CI 的**确定性失败信号**。 |
| **llm-eval-engine** | LLM/Agent **发布前评测决策**：回答数据是否可信、Judge 是否校准、过程/业务是否退化、**是否应当发布**。 |
| **react-agent**（对照） | Agent **执行运行时** + capability **任务规则打分**主集；不替代上述两仓。 |

**闭环（推荐对外口径）：**

```text
react-agent（或任意 Agent）产出轨迹 / Episode
    → trace-debugger：规则打标 · scan/compare · findings（便宜、可复现）
    → llm-eval-engine：Process Reward · 校准 · Benchmark · 多证据汇总
    → 发布结论 pass / review / hold（仅 eval-engine 编排裁决）
```

---

## 2. 各回答什么问题

| 问题 | 归属 |
|------|------|
| 这条轨迹有没有工具报错、空检索、无答案、验收失败等**硬失败**？ | **trace-debugger** |
| 相对上一版 baseline，**失败类型分布**有没有变差？ | **trace-debugger**（规则层回归） |
| 修复应落在工具 / 检索 / harness / 策略哪一侧？（工程线索） | **trace-debugger**（Harness Health / ledger） |
| 步骤过程质量如何？根因步在哪？（语义/过程分） | **llm-eval-engine**（Process Reward） |
| Judge 与人是否一致？κ 够不够进门禁？ | **llm-eval-engine** |
| 业务终态、安全、时延/成本、切片漂移如何？该不该发版？ | **llm-eval-engine** |
| 这道 capability 题答对了没有？ | **react-agent `eval/`** |

---

## 3. 做 / 不做（硬边界）

### 3.1 trace-debugger

| 做 | 不做 |
|----|------|
| Format B / Episode 读取、校验、本地 CLI | 云 tracing / 多租户观测大盘（Langfuse 类） |
| 可解释**启发式**失败标签（扩展中）+ golden 规则 CI | 内置执行 LLM-as-Judge / Process Reward |
| `tdebug scan` + `--compare` **失败分布**回归 | 人机校准（κ/MAE）、Judge drift 门禁 |
| `findings` / intervention **修复边界线索** | 最终 `pass/review/hold` 发布裁决 |
| `tdebug judge --prompt-out` **只导出 prompt** | Eval Loop、动态 rubric、Benchmark 多模型决策榜 |
| 为下游提供稳定的 failure / findings 导出 | 数据切分泄漏治理、安全对抗主集、双人标注仲裁 |
| 盲评标注表 + **单标注者**根因判对率（`tdebug adjudicate`） | 评审者间 κ / 双人仲裁（归 llm-eval-engine） |

**对外忌用主卖点：**「发布评测决策系统」「Judge 校准」「能否发版的最终依据」。  
**对外可用：**「失败信号 / 规则回归 / 给发布评测提供 failure-gate 证据」。

### 3.2 llm-eval-engine

| 做 | 不做 |
|----|------|
| Process Reward、动态 rubric、Eval Loop | Agent 运行时本身 |
| Judge 调用与**人机校准**（κ 等） | 把 offline κ 表述为线上 SLA |
| 固定 Benchmark、切片漂移、质量/时延/成本门禁 | 替代 tdebug 的**廉价启发式主路径** |
| 多证据发布判断（业务 + 过程 + **失败门** + 性能） | Format B schema **主维护**（共享约定，改 schema 需跨仓协商） |
| 消费上游 `failures.json` / findings 作为 failure-gate 输入 | 再实现第二套「仅词重叠 / 工具报错」规则检测器作为主产品 |

**对外忌用主卖点：**「本地轨迹启发式 debugger」「零成本规则打标替代 Judge」。  
**仓内若已有 failure taxonomy：** 限定为 **Judge 低分 / 过程失败归因**，命名与文档上与 tdebug 的 `tool_error` 等规则标签区分（见 §5）。

---

## 4. 交接契约（避免两边各算一套）

| 产物 | 生产者 | 消费者 | 约定 |
|------|--------|--------|------|
| Format B 轨迹 JSON | Agent / adapter | 两仓 | Schema 共享；字段变更需双仓验证 |
| `evaluation-episode/v1` | Agent / 编排 | 两仓 | tdebug 可导入分析；**不重算**业务终态 |
| `failures.json` / scan 快照 / findings | **trace-debugger** | **llm-eval-engine** `failure-gate` | 稳定字段：`failure_types`、轨迹 id、可选 step 证据 |
| Judge prompt 文件 | tdebug `--prompt-out`（可选） | 人工或 eval-engine | tdebug **不**保证 Judge 执行结果 |
| Process / calibration / release 报告 | **llm-eval-engine** | 负责人 / CI 发布岗 | 唯一「是否发布」叙事出口 |
| capability 对错 | react-agent eval | 能力轨 | 与失败规则轨、Judge 轨分离 |

推荐编排示例（概念）：

```bash
# 1) 规则层失败信号（本仓）
tdebug scan trajectories/ 50 \
  --json-out snapshots/failures.json \
  --compare snapshots/baseline_failures.json \
  --findings-out snapshots/findings.json

# 2) 评测与发布裁决（对端仓；失败门消费上一步产物）
python examples/run_cross_agent_release.py episodes/ \
  --failure-gate snapshots/failures.json \
  --process-quality process.json \
  --performance performance.json
```

---

## 5. 命名与叙事防撞

| 易混说法 | 建议归属写法 |
|----------|----------------|
| 「失败治理门禁」 | **拆开写**：tdebug = **规则失败回归门**；eval-engine = **发布评测门** |
| 「失败 taxonomy」 | tdebug = **启发式 failure_types**；eval-engine = **过程/Judge 归因类型**（勿共用同一套对外口号） |
| 「baseline / --compare」 | tdebug 比 **失败分布**；eval-engine 比 **Benchmark/质量/成本切片** |
| 「hold」 | **仅** eval-engine（或 delivery 编排）输出最终 hold；tdebug 最多输出「失败变差 / findings 建议 review」 |
| 「回归 CI」 | tdebug = golden 规则不破；eval-engine = 校准与 benchmark 门禁 |

---

## 6. 后续调整清单

### 6.1 trace-debugger（建议）

| 项 | 动作 | 状态 |
|----|------|------|
| README / VALUE 主定位 | 收窄为「轨迹失败检测与规则回归」；发版最终决策指向 llm-eval-engine | 已做 |
| 「能否发版」表述 | 改为「提供失败证据，供评测决策消费」 | 已做 |
| 路线图 | 步骤证据、假阳性集、tool 契约、`--task-type`、failure-gate 导出；**不**做 κ/Judge/Eval Loop | **0.6.0 已落地** |
| Adapters + 结构化信号 | Messages/stream/Responses；computer/shell、`approval_denied`、`incomplete` mark、`search_weak`、`protocol_mode`、`--fail-on` | **已合并（#6）** |
| 可验证 findings + 盲评 | `verification_ref` 回归锁 + `--require-verification`（进 CI 门禁）；`tdebug adjudicate` 盲表/评分（单标注者根因判对率、逐类型 P/R） | **已合并（#8）** |
| INTEGRATIONS | failures → failure-gate 字段说明；半截流/协议项策略 | 已做 |
| 与 AgentRx/Hindsight 类能力 | 若做步骤归因，保持**确定性/可解释**；语义归因交给对端 | 持续 |

### 6.2 llm-eval-engine（建议）

| 项 | 动作 |
|----|------|
| README 跨仓表 | 增加与 **trace-debugger** 一行：失败规则信号上游 / 本仓不重复主做启发式 |
| `failure_taxonomy` 文档 | 标明「Judge/过程归因」，并链到 tdebug 规则标签 |
| 发布 CLI | 文档示例默认展示 `--failure-gate` 来自 tdebug 导出 |
| 路线图 | Judge、校准、Benchmark、安全、漂移、发布编排继续加深；不新开「本地 tdebug 替代品」 |

### 6.3 共同维护

- 本文两仓各存一份，重大边界变更必须 **双仓 PR**（或先改本文再改两边 README）。  
- Schema / Episode 变更：先改共享约定，再跑两边最小 CI。  
- 简历/答辩：**三仓各讲一句话**（§1），禁止把两仓都说成「发布评测平台」。

---

## 7. 允许的有限重叠（有意为之）

下列重叠 **允许**，但必须说明层次不同：

| 重叠点 | 如何不重复 |
|--------|------------|
| 都读 Format B | 共享 schema，不是两套格式 |
| 都谈「失败」 | 规则硬失败 vs Judge/过程失败 |
| 都有 compare | 失败分布 vs 评测分数/切片 |
| 都服务「发布」 | tdebug 供证；eval-engine 裁决 |

**不允许的重叠：** 两边各自宣传为唯一的「Agent 发布门禁 / 评测决策系统」。

---

## 8. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-09-13 | 初版：固定双仓定位、硬边界、交接契约与后续调整清单 |
| 2026-09-13 | v0.6.0：tdebug 落地证据链 / contracts / FP CI / failure-gate/v1 / 规则 R |
| 2026-09-14 | Unreleased：adapters + P0–P2 规则信号；golden 29；文档口径对齐（仍不做语义 Judge） |
| 2026-09-30 | golden **32**（11 类全覆盖）；`verification_ref` 回归锁 + `--require-verification` 进 CI；`tdebug adjudicate` 盲评（单标注者）；`looks_cross_language` 跨语言假阳性豁免（FP 7） |
