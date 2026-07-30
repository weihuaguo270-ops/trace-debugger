# 回归门禁案例：react-agent 试点

**案例 ID：** `regression_gate_20260730`  
**记录人：** trace-debugger 维护方（项目负责人视角）  
**项目：** [react-agent](https://github.com/weihuaguo270-ops/react-agent) 参考集成  
**版本：** trace-debugger v0.2.5 · 试点 Phase 0–4  

我们在 react-agent 上跑完一轮发版前 compare 试点，记下两起决策：**一起差点误拦发版，一起验证劣化信号能拉出来**。证据是脱敏快照，不含 query 全文。

---

## 案例 A — 差点按规则 hold，查数据后放行

**类型：** 假阳性纠正  

### 怎么回事

2026-07-30，我们按「发版前对照历史周报」的习惯，把新 scan 和 2026-07-15 的 `tdebug_failure_real_20260715` 做了 `--compare`。

| | 2026-07-15 历史 | 2026-07-30 新 scan |
|--|----------------:|-------------------:|
| 含失败 session | 9 / 100（9%） | 36 / 100（36%） |
| 主要分布 | offtrack:6, tool:2, … | search_empty:30, tool:6 |

按 [THRESHOLDS v1](../pilot/THRESHOLDS.md)：**规则 A、B 都会触发**，表面上是该 hold 的。

### 我们查了什么

- 两次 scan 的 100 个文件 **零重叠**（[PHASE1.md](../pilot/PHASE1.md) §数据分析）
- +30 的 `search_empty` 全部来自 **mock 证据轨迹**（StepWatcher batch），不是 LLM 变差
- 去掉 mock 后 fail_rate 约 **7%**，和历史 **9%** 同一量级

### 决策

| 项 | 内容 |
|----|------|
| 决策 | **不 block 发版**；记 `review`，改流程 |
| 动作 | 立项 Phase 2：冻结 baseline；禁止跨时间直接 compare「最新 N」 |
| 若没查数据 | 会错误 hold——这是本次试点最有价值的一课 |

**证据：** [pilot_latest.json](../snapshots/pilot_latest.json) · [tdebug_failure_real_20260715.json](../snapshots/tdebug_failure_real_20260715.json)

---

## 案例 B — 同文件集上，劣化信号能进 review

**类型：** 模拟演练（**不是真实 PR**；流程与发版相同）  

### 怎么回事

Phase 3 我们要验证：如果有人想合并「放宽 offtrack 判定」，compare 能不能在发版前拦住。

我们在 **同一批 100 个非 mock 文件**上，用 `offtrack_overlap=0.55` 重跑 analyzer（默认 0.15），模拟规则回退。

| | baseline (no_mock) | 模拟劣化 |
|--|-------------------:|---------:|
| llm_offtrack | 0 | **9** |
| 含失败 session | 7 / 100（7%） | 15 / 100（15%） |

### 门禁

- 规则 A：offtrack +9 → 触发  
- 规则 B：+8pp → 进「5–9pp 必看」；再 +2pp 就是 hold  

### 决策

| 项 | 内容 |
|----|------|
| 决策 | **review**；若是真实 PR，我们会暂缓合并 analyzer 放宽，直到解释或修规则 |
| 说明 | 9 条新增 offtrack 集中在短答、对比题——和机制一致，不是随机噪声 |

**复现：**

```bash
python scripts/build_pilot_scan.py --from-snapshot docs/snapshots/pilot_baseline_no_mock.json \
  --offtrack-overlap 0.55 \
  --json-out docs/snapshots/pilot_run_b_no_mock.json
```

**证据：** [PHASE3.md](../pilot/PHASE3.md) · `pilot_baseline_no_mock.json` / `pilot_run_b_no_mock.json`

---

## 我们对外怎么讲（诚实版）

**可以说：**

- 发版前 compare 帮我们**避免了一次因样本漂移导致的误 hold**
- 在生产向 baseline 上，**同文件集 compare 能拉出 offtrack 劣化并进入 review**

**不能说：**

- 「已经在生产环境拦过真实 PR」——案例 B 是模拟
- 「接入后失败率下降 X%」——没测

---

## 关联

[pilot/README.md](../pilot/README.md) · [THRESHOLDS.md](../pilot/THRESHOLDS.md) · [METRICS_LOG.md](../pilot/METRICS_LOG.md) · [VALUE.md](../VALUE.md)

---

## 修订

| 日期 | 说明 |
|------|------|
| 2026-07-30 | 初稿 |
| 2026-07-30 | v0.2.5：项目负责人口吻 |
