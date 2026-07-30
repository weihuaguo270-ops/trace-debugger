# Phase 1 报告 — 首次 scan 与漂移对照

**日期：** 2026-07-30  
**状态：** ✅ 完成

---

## 执行内容

| 项 | 结果 |
|----|------|
| `tdebug scan` N=100 | ✅ 写入 [pilot_latest.json](../snapshots/pilot_latest.json) |
| 与 `tdebug_failure_real_20260715` compare | ✅ 已跑（见下文解读） |
| 基线文件重分析（漂移检查） | ✅ 100/100 仍在磁盘，95/100 标签一致 |
| `tdebug validate` 抽样 3 条 | ✅ 全部 OK |

### validate 抽样

| 文件 | 场景 | 结果 |
|------|------|------|
| `traj_20260727_221000_9vtd.json` | 多步 PASS | OK |
| `traj_20260729_134107_zhf4.json` | mock / search_empty | OK |
| `traj_20260713_141821_9ydt.json` | 历史 tool_error | OK |

---

## pilot_latest 摘要

| 字段 | 值 |
|------|-----|
| report_id | `tdebug_scan_20260730_001702` |
| N | 100 |
| distribution | `search_empty:30`, `tool_error:6` |
| 含失败 session | **36 / 100（36%）** |
| 时间窗口 | 约 2026-07-17 → 2026-07-29（最新 100 条） |

大量 `search_empty` 来自 **StepWatcher / mock 证据轨迹**（`model: mock`，query 为 `q` / `正常流程` 等），属预期失败模式，非生产回归。

---

## compare 解读（重要）

### 终端 diff（latest vs real_20260715）

```
基准 dist: tool_error:2, duplicate:1, llm_offtrack:6, no_answer:1  (fail sessions 9)
当前 dist: search_empty:30, tool_error:6                              (fail sessions 36)
```

| 变化 | delta |
|------|-------|
| search_empty | +30 |
| tool_error | +4 |
| llm_offtrack | -6 |
| duplicate | -1 |
| no_answer | -1 |
| 含失败 session | 9 → 36 (+27) |

### 为何不能直接当作「质量变差」

**两次 scan 的 100 个文件零重叠**（`latest_only=100`, `base_only=100`）。

- 2026-07-15 基准：当时目录内「最新 100 条」（以 7/13 批次为主）
- 2026-07-30 当前：目录已有 445 条，最新 100 条以 7/17–7/29 为主，含大量 mock 证据 run

因此 `--compare` 在此刻衡量的是 **样本构成变化 + 新失败类型出现**，不是同一批轨迹上的版本回归。  
**Phase 2 的 `pilot_baseline.json` 必须在固定 commit 上冻结**，后续 compare 才可用于门禁。

---

## Analyzer 漂移检查（正确方法）

对 `tdebug_failure_real_20260715` 中列出的 **同一 100 个文件** 用当前 analyzer 重跑：

| 指标 | 值 |
|------|-----|
| 文件仍在磁盘 | 100/100 |
| 失败标签完全一致 | **95/100** |
| 不一致 | **5/100** |

5 条不一致均为：`llm_offtrack`（2026-07-15）→ `[]`（当前），与 [RISKS.md](../RISKS.md) 记载的 **offtrack 规则校准（6→1）** 一致，属**有意收紧**，非意外回归。

| 文件 | 2026-07-15 | 当前 |
|------|------------|------|
| traj_20260713_141236_0nai.json | llm_offtrack | — |
| traj_20260713_141224_jqg2.json | llm_offtrack | — |
| traj_20260713_140456_lj4s.json | llm_offtrack | — |
| traj_20260713_140446_n8x3.json | llm_offtrack | — |
| traj_20260713_135417_y1xp.json | llm_offtrack | — |

**结论：** analyzer 在重叠文件上行为可解释；**未观察到非 offtrack 类的意外漂移**。

---

## 门禁阈值触发（对照 THRESHOLDS v1）

对 **latest vs real_20260715** 的 naive compare：

| 规则 | 是否触发 | 说明 |
|------|----------|------|
| A（单类型 +≥2） | 是（search_empty +30, tool_error +4） | **样本不同，不应用于 hold** |
| B（fail_rate +≥10pp） | 是（+27pp） | 同上 |

**决策：** `review` — 记录为 Phase 1 发现；**不**视为发版 block。Phase 2 建 baseline 后重新 compare。

---

## 数据分析

以下对 **2026-07-15 历史快照** 与 **2026-07-30 pilot_latest** 做并列统计，并解释 naive compare 为何会产生「虚假劣化」。

### 1. 两次 scan 不是同一批数据

| 维度 | `tdebug_failure_real_20260715` | `pilot_latest`（Phase 1） |
|------|-------------------------------|---------------------------|
| 扫描日 | 2026-07-15 | 2026-07-30 |
| react-agent git | `89abfc1` | `bbe48ee`（目录现状） |
| session 日期范围 | **仅 2026-07-13**（单日） | **2026-07-17 → 2026-07-29** |
| 文件重叠 | — | **0 / 100** |
| 含失败 session | 9 / 100（**9%**） | 36 / 100（**36%**） |
| 模型构成 | deepseek-v4-flash **100%** | mock **30** + deepseek-v4-flash **70** |

**结构结论：** compare 的 +27pp fail_rate **100% 来自样本替换**，不是同一 cohort 上的 before/after。

```
历史 100 条 ←── 2026-07-13 单日 eval batch（已被挤出「最新 100」）
当前 100 条 ←── 2026-07-17~29 run + 30 条 mock 证据
         ↑
    零重叠 → delta 不可解释为 Agent 质量下降
```

### 2. 目录增长与「最新 N」选取效应

当前 `trajectories/` 共 **445** 条 JSON，按日期分布（Top）：

| 日期 | 条数 | 备注 |
|------|-----:|------|
| 2026-07-13 | 181 | 历史 scan 所在日 |
| 2026-07-16 | 124 | |
| 2026-07-27 | 68 | Phase 1 latest 主要来源 |
| 2026-07-15 | 37 | |
| 2026-07-17 | 20 | |
| 2026-07-26 / 29 | 15 | 含 mock 证据 batch |

2026-07-15 扫的是当时「最新 100」→ 几乎全是 **7/13 单日**数据。  
15 天后目录增至 445 条，「最新 100」**完全不包含** 7/13 文件 → 与 Phase 3 固定 baseline 文件集 compare 形成对比。

### 3. 历史批次（2026-07-15）失败画像

**distribution（路径级）：** `llm_offtrack:6` · `tool_error:2` · `duplicate:1` · `no_answer:1`

| 失败类型 | session 数 | 步数特征 | 典型场景 |
|----------|----------:|----------|----------|
| llm_offtrack | 6 | 2–4 步（多数 **2 步**） | 短数学/时间 query（如 100÷7、东京时间） |
| tool_error | 2 | 4–7 步 | 多步任务（Python 学习计划、维基搜索链） |
| duplicate + tool_error | 1 | 7 步 | 同上搜索链，重复尝试叠加 |
| no_answer | 1 | 4 步 | Python vs JavaScript 对比 |

| 指标 | 失败 session | 成功 session |
|------|-------------:|-------------:|
| 平均步数 | **3.2** | **1.9** |

与 Phase 3 no_mock 结论一致：**多步 run 更易暴露 tool_error**；offtrack 集中在短答场景。

**9 条失败 session 明细：**

| 文件 | failure_types | 步数 |
|------|---------------|-----:|
| `traj_20260713_141821_9ydt.json` | tool_error | 4 |
| `traj_20260713_141323_jayb.json` | duplicate, tool_error | 7 |
| `traj_20260713_141236_0nai.json` | llm_offtrack | 2 |
| `traj_20260713_141224_jqg2.json` | llm_offtrack | 2 |
| `traj_20260713_140901_bax8.json` | llm_offtrack | 4 |
| `traj_20260713_140836_2vmw.json` | no_answer | 4 |
| `traj_20260713_140456_lj4s.json` | llm_offtrack | 2 |
| `traj_20260713_140446_n8x3.json` | llm_offtrack | 2 |
| `traj_20260713_135417_y1xp.json` | llm_offtrack | 2 |

历史 2 条 tool_error 文件**仍在目录**，但已不在「最新 100」内 → 当前 scan 的 tool_error:6 是**新 cohort 的 6 条**，与历史 2 条无文件级对应关系。

### 4. Phase 1 pilot_latest 失败结构

**distribution：** `search_empty:30` · `tool_error:6`

| 来源 | 条数 | 失败类型 | 说明 |
|------|-----:|----------|------|
| mock 证据 | 30 | search_empty（100%） | query 三分：`q` / `正常流程` / `正常流程（带风险）`；均 2 步 |
| deepseek-v4-flash | 6 | tool_error | 与 Phase 3 no_mock 中 6 条同源（7/17–7/27 多步 run） |

**36% fail_rate 拆解：**

| 成分 | 占 100 条 | 占 36 失败条 |
|------|----------:|-------------:|
| mock search_empty | 30% | **83%** |
| 真实 tool_error | 6% | 17% |

若 Phase 1 当时就有 no_mock 视图：fail_rate 约为 **7%**（6 tool_error + 潜在 no_answer），与历史 9% **量级接近**，而非 naive compare 暗示的 9%→36% 跃升。

### 5. naive compare 的 delta 分解

| 失败类型 | 历史 → 当前 | 可解释原因 |
|----------|------------|------------|
| search_empty | 0 → **+30** | 新 cohort 引入 mock 证据 batch；历史 scan 无 mock |
| tool_error | 2 → 6（+4） | **不同文件**；新 cohort 多步 run 更多 |
| llm_offtrack | 6 → 0（−6） | 7/13 文件已不在最新 100；非规则单独导致 |
| duplicate | 1 → 0 | 同上 |
| no_answer | 1 → 0 | 同上 |
| fail session | 9 → 36（**+27pp**） | mock +30 为主；**不可用于 hold** |

**反事实：** 若两次 scan 文件重叠 100%，fail_rate 变化才反映 analyzer 或 Agent 变化；Phase 1 实际重叠 **0%**。

### 6. Analyzer 漂移（同文件重分析）

对历史 100 个**固定文件名**用当前 analyzer 重跑：

| 指标 | 值 |
|------|-----|
| 文件仍在磁盘 | 100/100 |
| 标签完全一致 | **95/100** |
| 不一致 | **5/100**（均为 offtrack → 清除） |

| 漂移文件 | 历史标签 | 当前 | 步数 | query 模式 |
|----------|----------|------|-----:|------------|
| `…141236_0nai.json` | llm_offtrack | — | 2 | 100÷7 类短数学 |
| `…141224_jqg2.json` | llm_offtrack | — | 2 | 「现在几点了」 |
| `…140456_lj4s.json` | llm_offtrack | — | 2 | 100÷7 |
| `…140446_n8x3.json` | llm_offtrack | — | 2 | 「现在几点了」 |
| `…135417_y1xp.json` | llm_offtrack | — | 2 | 时间工具类 |

**仍保留 offtrack 的 1 条**（`140901_bax8`，4 步，过拟合解释类）→ 与 RISKS 记载「6→1」在**路径级**上为 6→1 session 仍标 offtrack，**5 条短答被校准掉**。

| 检查 | 结果 |
|------|------|
| tool_error / duplicate / no_answer 漂移 | **0 条** |
| 非 offtrack 意外变化 | **无** |

### 7. 门禁阈值误触发分析

对 latest vs real_20260715 若机械套用 [THRESHOLDS.md](./THRESHOLDS.md)：

| 规则 | 表面结果 | 正确解读 |
|------|----------|----------|
| A：search_empty +30 | 触发 | **假阳性** — 新类型 + 新 cohort |
| A：tool_error +4 | 触发 | **不可比** — 非同一批文件 |
| B：+27pp | 触发 hold | **假阳性** — mock 占 +30 session 中 27 的增量 |

**Phase 1 决策逻辑：** 记录为 `review`（方法论发现），**禁止**作为发版 block 依据 → 直接推动 Phase 2 冻结 baseline。

### 8. validate 与 Format B 质量

抽样 3 条覆盖：

| 类型 | 文件 | 结论 |
|------|------|------|
| 多步 PASS（deepseek） | `traj_20260727_221000_9vtd.json` | Schema OK |
| mock FAIL | `traj_20260729_134107_zhf4.json` | Schema OK（失败标签与 schema 无关） |
| 历史 tool_error | `traj_20260713_141821_9ydt.json` | Schema OK |

轨迹格式不是 Phase 1 compare 噪声的来源。

### 9. Phase 1 → Phase 2/3 的方法论沉淀

| 教训 | 后续动作（已执行） |
|------|-------------------|
| 「最新 N」随目录增长漂移 | Phase 2 冻结 `pilot_baseline.json` |
| mock 污染 fail_rate | Phase 2 增加 `pilot_baseline_no_mock.json` |
| 历史快照不可当回归基准 | Phase 3 同文件集 Run A/B |
| offtrack 规则变更需重拍 baseline | 5 条漂移已文档化，非生产回归 |

---

## 结论

### 执行验证

| 项 | 结果 |
|----|------|
| 首次 scan 可产出快照 | ✅ |
| validate 抽样 | ✅ 3/3 |
| analyzer 同文件漂移 | ✅ 可解释（offtrack 校准 5 条） |
| naive compare | ⚠️ 可用作「警示」，**不可**作门禁 |

### 数据洞察（摘要）

1. **零重叠** — Phase 1 compare 测的是 cohort 替换，不是质量退化。
2. **36% vs 9%** — 差距主因是 **+30 mock**，不是 LLM 变差。
3. **历史 7/13 单日 batch** — 181 条集中日，已被新 run 挤出最新 100。
4. **offtrack 6→1（session）** — 5 条短答校准；tool_error 等无漂移。
5. **no_mock 约 7% vs 历史 9%** — 量级可比，支持「应用 no_mock 门禁」决策。

### 建议（Phase 1 产出）

| 优先级 | 动作 | 状态 |
|--------|------|------|
| P0 | 冻结 baseline，禁止对「最新 N」跨时间 compare | → Phase 2 ✅ |
| P0 | 拆分 mock / 生产 fail_rate | → Phase 2 no_mock ✅ |
| P1 | 同文件集验证 compare | → Phase 3 ✅ |
| P2 | 真实拦截案例 | → Phase 4 待做 |

---

## 复现命令

```bash
# Phase 1 scan（已完成）
tdebug scan ../react-agent/src/react_agent/trajectories 100 \
  --json-out docs/snapshots/pilot_latest.json \
  --compare docs/snapshots/tdebug_failure_real_20260715.json

# validate 抽样
tdebug validate ../react-agent/src/react_agent/trajectories/traj_20260727_221000_9vtd.json
```

---

## 文档维护

| 日期 | 说明 |
|------|------|
| 2026-07-30 | Phase 1 首次 scan + 漂移对照 |
| 2026-07-30 | 补充数据分析：cohort 替换、失败画像、delta 分解、漂移明细 |
