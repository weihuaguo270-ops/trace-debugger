# Phase 3 报告 — 回归工作流验证（Run A / Run B）

**日期：** 2026-07-30  
**状态：** ✅ 完成

---

## 目标

验证 [WORKFLOW.md](./WORKFLOW.md) 中的 scan + compare 能否：

1. **Run A**：无害重扫 → diff ≈ 0 → `pass`
2. **Run B**：故意劣化 → 门禁触发 → `review` / `hold`

---

## Run A — 无害重扫（同 commit `bbe48ee`）

### 主 baseline（含 mock）

```bash
tdebug scan ../react-agent/src/react_agent/trajectories 100 \
  --json-out docs/snapshots/pilot_run_a.json \
  --compare docs/snapshots/pilot_baseline.json
```

| 指标 | baseline | current | delta |
|------|----------|---------|-------|
| search_empty | 30 | 30 | 0 |
| tool_error | 6 | 6 | 0 |
| 含失败 session | 36 | 36 | 0 |
| N | 100 | 100 | 0 |

**门禁：** 无触发 → **决策 `pass`**

### no_mock 变体

```bash
python scripts/build_pilot_scan.py --exclude-mock -n 100 \
  --json-out docs/snapshots/pilot_run_a_no_mock.json
```

与 `pilot_baseline_no_mock.json`：**distribution 相同**，fail sessions 7/100 → **pass**

---

## Run B — 故意劣化（模拟）

不修改 react-agent 代码；对 **同一批 baseline 文件** 用更激进的 analyzer 重分析，模拟「prompt 劣化 / offtrack 规则回退」。

### 主 baseline 对照

| 参数 | 值 |
|------|-----|
| 方法 | `Analyzer(offtrack_overlap=0.45)`（默认 0.15） |
| 快照 | [pilot_run_b_degraded.json](../snapshots/pilot_run_b_degraded.json) |

| 指标 | baseline | degraded | delta |
|------|----------|----------|-------|
| search_empty | 30 | 30 | 0 |
| tool_error | 6 | 6 | 0 |
| llm_offtrack | 0 | **4** | **+4** |
| 含失败 session | 36 | 40 | **+4pp** |

| 规则 | 结果 |
|------|------|
| **A**（单类型 +≥2） | ✅ 触发：`llm_offtrack +4` |
| **B**（fail_rate +≥10pp） | ❌ 未触发（+4pp） |

**决策：`review`**（规则 A 必看；主 baseline 已 36% 失败率，B 门槛较高）

复现：

```bash
python scripts/build_pilot_scan.py --from-snapshot docs/snapshots/pilot_baseline.json \
  --offtrack-overlap 0.45 \
  --json-out docs/snapshots/pilot_run_b_degraded.json \
  --report-id pilot_run_b_degraded_20260730
```

### no_mock 对照（生产向）

| 参数 | 值 |
|------|-----|
| 方法 | `Analyzer(offtrack_overlap=0.55)` |
| 快照 | [pilot_run_b_no_mock.json](../snapshots/pilot_run_b_no_mock.json) |

| 指标 | baseline | degraded | delta |
|------|----------|----------|-------|
| tool_error | 6 | 6 | 0 |
| no_answer | 1 | 1 | 0 |
| llm_offtrack | 0 | **9** | **+9** |
| 含失败 session | 7 (7%) | 15 (15%) | **+8pp** |

| 规则 | 结果 |
|------|------|
| **A** | ✅ 触发：`llm_offtrack +9` |
| **B** | ⚠️ **+8pp** → 落入「5–9pp 必看」档（未达 10pp `hold`） |

**决策：`review`**（若 +10pp 则为 `hold`）

复现：

```bash
python scripts/build_pilot_scan.py --exclude-mock -n 100 --offtrack-overlap 0.55 \
  --json-out docs/snapshots/pilot_run_b_no_mock.json \
  --report-id pilot_run_b_no_mock_20260730
```

---

## 数据分析

以下基于 Phase 2 冻结快照与 Phase 3 产出 JSON 的统计（N=100，react-agent `bbe48ee`）。

### 1. 样本时间窗与模型构成

| 快照 | session 日期范围 | mock | deepseek-v4-flash |
|------|------------------|-----:|------------------:|
| `pilot_baseline`（主） | 2026-07-17 → 2026-07-29 | 30 | 70 |
| `pilot_baseline_no_mock` | 2026-07-16 → 2026-07-27 | 0 | 100 |

主 baseline 与 no_mock **文件重叠 70 条**；主 baseline 多出的 30 条全部为 mock，no_mock 多出的 30 条为更早的非 mock 运行（被 mock 挤出「最新 100」窗口）。

### 2. 失败类型 × 模型（主 baseline）

| 模型 | 失败类型 | 路径级计数 | 说明 |
|------|----------|----------:|------|
| `mock` | search_empty | 30 | 30/30 mock session 均命中；固定 2 步、0s |
| `deepseek-v4-flash` | tool_error | 6 | 全部来自真实 LLM run |

**结构结论：** 主 baseline 的 36% 失败率中，**30/36（83%）由 mock 证据轨迹贡献**；真实 LLM 路径仅 6 条 tool_error（6% of 100 sessions）。

### 3. mock 轨迹画像（30 条）

| 属性 | 值 |
|------|-----|
| query 模式 | 各 10 条：`q` / `正常流程` / `正常流程（带风险）` |
| 步数 | 全部为 **2 步** |
| 失败类型 | 全部为 **search_empty** |
| 来源 | StepWatcher 证据 batch（2026-07-26 ~ 07-29） |

mock 不是「随机噪声」，而是**结构化、可预期的失败簇**——compare 时若 mock 批量写入/清理，主 baseline 的 fail_rate 会整体平移，与 prompt 质量无关。

### 4. 生产向 baseline（no_mock）失败画像

**分布：** `tool_error:6` · `no_answer:1` · 含失败 **7/100（7%）**

| 失败类型 | 条数 | 步数特征 | 备注 |
|----------|-----:|----------|------|
| tool_error | 6 | 5–8 步（均值 **5.9**） | 多步工具链 run；含记忆上下文的长 query |
| no_answer | 1 | 4 步 | `traj_20260716_181136_ztgc.json` |
| 无失败 | 93 | 均值 **3.1** 步 | 短任务、单轮问答居多 |

**对比：** 失败 session 平均步数约为成功 session 的 **1.9 倍**——门禁关注的劣化更可能出现在**多步工具调用**场景，而非 1–2 步短问答。

**6 条 tool_error session（文件名）：**

- `traj_20260727_220616_o20u.json`（6 步）
- `traj_20260727_220517_h8zm.json`（6 步）
- `traj_20260727_220426_46q8.json`（5 步）
- `traj_20260727_220233_k6v8.json`（5 步）
- `traj_20260727_215701_pr0y.json`（7 步）
- `traj_20260717_095838_566v.json`（8 步）

### 5. 主 baseline 评估分布（overall_assessment）

| 类别 | 条数 | 占比 |
|------|-----:|-----:|
| `[FAIL]` 执行问题较多 | 33 | 33% |
| `[PASS]` 执行顺利 | 64 | 64% |
| `[WARN]` 有少量问题 | 3 | 3% |

33 条 FAIL 与 36 条含失败 session 接近（差 3 条为 WARN 但未进 `failure_types` 计数逻辑边界 case）。

### 6. Run A 稳定性（逐条对照）

对 `pilot_run_a.json` 与 `pilot_baseline.json` **100/100 文件**逐条比对：

| 检查项 | 结果 |
|--------|------|
| 文件名一致 | 100/100 |
| `failure_types` 一致 | 100/100 |
| distribution | 完全相同 |

**说明：** 在 ~14 分钟间隔内重扫（baseline 00:19 → Run A 00:20 UTC），analyzer 与目录 mtime 排序**可重复**。

### 7. Run B 变化分解

#### 主 baseline（offtrack_overlap 0.45 → +4 offtrack）

新增 `llm_offtrack` 的 4 条 session **原先均为 PASS**（无 failure_types），全部来自 `deepseek-v4-flash`：

| 文件 | 步数 | query 主题（脱敏摘要） |
|------|-----:|------------------------|
| `traj_20260727_220131_bwe4.json` | 2 | 记忆上下文 + 安全/CPU 规范类 |
| `traj_20260727_202857_bigi.json` | 3 | Python vs Java 主要区别 |
| `traj_20260726_091357_leg5.json` | 1 | 重复堆叠的「AI 改变行业」摘要 |
| `traj_20260726_091317_3guk.json` | 1 | Python vs Java 主要区别 |

**模式：** 短步数（1–3 步）、答案与 query 字面重叠低 → 提高 offtrack 阈值后被标出。原有 30 mock + 6 tool_error **未变化**。

#### no_mock（offtrack_overlap 0.55 → +9 offtrack）

| 指标 | 值 |
|------|-----|
| 新增 offtrack session | 9 |
| 其中已有 tool_error、叠加 offtrack | 1（`220233_k6v8`） |
| 纯新增失败（原 PASS → 有失败） | 8 |

9 条 query 主题聚类：

| 主题 | 条数 |
|------|-----:|
| Python vs Java 对比 | 3 |
| 鲁迅《呐喊》出版年 | 3 |
| 重复/堆叠摘要文本 | 1 |
| 记忆上下文 + 项目配置 | 2 |

**解读：** Run B 并非均匀随机放大，而是对**短答、文学事实、对比类**问题更敏感——与 `_detect_offtrack` 「query–answer 词重叠」机制一致。

### 8. 门禁灵敏度（阈值 vs 数据）

| 对照 | fail_rate 基线 | Run B fail_rate | delta_pp | 规则 A | 规则 B |
|------|---------------:|----------------:|---------:|--------|--------|
| 主 baseline | 36% | 40% | +4 | ✅ offtrack +4 | ❌ |
| no_mock | 7% | 15% | +8 | ✅ offtrack +9 | ⚠️ 5–9pp 必看 |

**灵敏度差异原因：**

1. **主 baseline 基线过高（36%）** — mock 占 30 条失败；+4 条 offtrack 仅 +4pp，远低于 10pp hold 线。
2. **no_mock 基线低（7%）** — 同量级 offtrack 注入（+8 session）即 +8pp，接近 hold。
3. **路径级 vs session 级** — 规则 A 看 `distribution` 计数（1 session 1 类型 +1）；`220233` 同时有 tool_error + offtrack，路径级可能 > session 级。

### 9. 与 Phase 1 的衔接

| 对比 | Phase 1（vs 2026-07-15 历史） | Phase 3（vs Phase 2 baseline） |
|------|------------------------------|--------------------------------|
| 文件重叠 | **0/100**（样本完全不同） | **100/100**（Run A/B 固定 baseline 文件集） |
| 可比性 | 仅适合 analyzer 漂移检查 | 适合回归门禁 |
| 主教训 | 不能直接 compare 不同时间窗口的「最新 100」 | 必须先冻结 baseline 再 compare |

Phase 3 的数据分析补上了 Phase 1 的缺口：**门禁 compare 必须同文件集或同选取规则**，否则 delta 反映的是样本替换而非质量变化。

---

## 结论

### 工作流验证

| 验证项 | 结果 |
|--------|------|
| Run A diff≈0 | ✅ 100/100 文件级一致 |
| Run B 放大 delta | ✅ offtrack 定向增加，mock/tool_error 不变 |
| 规则 A 可触发 | ✅ |
| 规则 B 分档 | ✅ no_mock +8pp → 必看；主 baseline 因 mock 高基线难触发 hold |
| WORKFLOW 可执行 | ✅ |

### 数据洞察（摘要）

1. **主 baseline 36% 失败率中 83% 来自 mock** — 不宜作为生产发版门禁主指标。
2. **no_mock 7% 基线**更能反映真实 LLM run（tool_error 6 + no_answer 1）。
3. **失败 session 步数更长**（5.9 vs 3.1）— 劣化监控应关注多步工具链。
4. **Run B offtrack 命中短答/对比/文学事实类 query** — 与 analyzer 机制一致，非随机噪声。
5. **Run A 证明可重复性** — 同目录同 N 重扫标签稳定。

### 建议

| 优先级 | 动作 |
|--------|------|
| P0 | 发版 compare 默认 **no_mock** + `pilot_baseline_no_mock.json` |
| P1 | mock 轨迹与生产轨迹**分目录或分前缀**，避免挤占「最新 100」 |
| P2 | Phase 4 用**真实 PR/发版**案例替换 Run B 模拟，补业务叙事 |
| P3 | 可选 CLI `--exclude-model mock`，去掉对手动脚本的依赖 |

---

## 产出文件

| 文件 | Run |
|------|-----|
| `pilot_run_a.json` | Run A 主 |
| `pilot_run_a_no_mock.json` | Run A no_mock |
| `pilot_run_b_degraded.json` | Run B 主 |
| `pilot_run_b_no_mock.json` | Run B no_mock |

---

## 文档维护

| 日期 | 说明 |
|------|------|
| 2026-07-30 | Phase 3 Run A/B 完成 |
| 2026-07-30 | 补充数据分析：样本构成、失败画像、Run B 分解、门禁灵敏度 |
