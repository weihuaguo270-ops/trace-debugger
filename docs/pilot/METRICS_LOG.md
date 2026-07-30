# 试点指标记录表

每次 **scan / compare** 或发版决策后追加一行。  
字段与 [THRESHOLDS.md](./THRESHOLDS.md) 门禁规则对齐。

---

## 字段说明

| 列 | 说明 |
|----|------|
| **日期** | 扫描或决策日（UTC+8） |
| **阶段** | Phase 0–5 或 `routine` |
| **react-agent SHA** | 轨迹来源仓 commit（短 SHA） |
| **tdebug SHA / 版本** | trace-debugger commit 或 release tag |
| **N** | scan 样本量 |
| **distribution** | 路径级计数摘要，如 `offtrack:6,tool:2` |
| **fail_sessions** | 含失败轨迹数 / N（占比 %） |
| **compare 基准** | 对比的快照文件名 |
| **最大 delta** | 单类型最大正 delta，或 fail_rate delta_pp |
| **触发规则** | A / B / C / — |
| **决策** | pass / review / hold / fix |
| **备注** | 链接案例、PR、脱敏说明 |

---

## 记录

| 日期 | 阶段 | react-agent | tdebug | N | distribution | fail_sessions | compare 基准 | 最大 delta | 触发规则 | 决策 | 备注 |
|------|------|-------------|--------|---|--------------|---------------|--------------|------------|----------|------|------|
| 2026-07-30 | capability | `bbe48ee` | v0.2.5 | 80 ho | off:2,tool:5,dup:3 | 7/80 (8.8%) | — | — | — | pass | [CAPABILITY_HELD_OUT_RUN.md](./CAPABILITY_HELD_OUT_RUN.md) 能力轨 baseline |
| 2026-07-30 | Phase 5 | `bbe48ee` | v0.2.5 | 10 cases | — | — | — | — | — | pass | [PHASE5.md](./PHASE5.md) 人工代理 10/10 更快；缺秒表 |
| 2026-07-30 | Phase 4 | `bbe48ee` | `42fe027` | — | — | — | — | — | — | pass | [regression_gate_20260730](../cases/regression_gate_20260730.md) 案例 A+B |
| 2026-07-30 | Phase 3 Run A | `bbe48ee` | `42fe027` | 100 | 同 baseline | 36/100 | pilot_baseline | 0 | — | pass | [PHASE3.md](./PHASE3.md) |
| 2026-07-30 | Phase 3 Run B | `bbe48ee` | `42fe027` | 100 | +offtrack:4 | 40/100 (+4pp) | pilot_baseline | +4 offtrack | A | review | 劣化模拟 offtrack=0.45 |
| 2026-07-30 | Phase 3 Run B nm | `bbe48ee` | `42fe027` | 100 | +offtrack:9 | 15/100 (+8pp) | pilot_baseline_no_mock | +9 offtrack | A,B† | review | †8pp 必看档 |
| 2026-07-30 | Phase 2 | `bbe48ee` | `42fe027` | 100 | search_empty:30, tool:6 | 36/100 (36%) | — | — | — | pass | 冻结 [BASELINE.md](./BASELINE.md) |
| 2026-07-30 | Phase 1 | `bbe48ee` | `42fe027` | 100 | search_empty:30, tool:6 | 36/100 (36%) | real_20260715 | +30 search_empty | A,B* | review | [PHASE1.md](./PHASE1.md)；*样本零重叠，不 block |
| 2026-07-30 | Phase 0 | `bbe48ee` | `42fe027` (v0.2.4) | — | — | — | — | — | — | pass | 定点完成：445 条轨迹可用；阈值见 THRESHOLDS v1 |
| 2026-07-15 | 历史参照 | `89abfc1` | — | 100 | offtrack:6, tool:2, dup:1, no_answer:1 | 9/100 (9%) | — | — | — | — | [tdebug_failure_real_20260715](../tdebug_failure_real_20260715.md)；Phase 1 漂移对照 |

---

## 模板（复制追加）

```markdown
| YYYY-MM-DD | Phase N | `<sha>` | `<sha>` | 100 | ... | x/100 (x%) | pilot_baseline.json | ... | A | review | ... |
```

---

## 文档维护

| 日期 | 说明 |
|------|------|
| 2026-07-30 | Phase 0 建表 + 历史参照行 |
