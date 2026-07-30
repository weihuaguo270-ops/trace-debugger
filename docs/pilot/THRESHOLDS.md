# 回归门禁阈值（试点 v1）

本文定义 **Phase 3 发版 / PR compare** 时，何种分布变化视为「变差」，需要人工 review 或暂缓合并。

阈值基于 **路径级失败类型计数**（`distribution`）与 **含失败 session 占比**（`trajectories` 中 `failure_types` 非空的比例）。  
与 `tdebug scan --compare` 输出字段一致。

---

## 术语

| 术语 | 含义 |
|------|------|
| **baseline** | Phase 2 冻结的 `pilot_baseline.json` |
| **current** | 本次 `pilot_latest.json` 或 CI 产出 |
| **路径级计数** | 一条轨迹可含多种失败类型，各类型在 `distribution` 中分别 +1 |
| **含失败 session** | `failure_types` 数组非空的轨迹条数 |

---

## 门禁规则（初版）

### 规则 A — 单类型计数上升

| 条件 | 动作 |
|------|------|
| 任一失败类型 `distribution[type]` **增加 ≥ 2** | **必看**：发版 review 须解释 delta 或修复后再 compare |
| 任一失败类型增加 **+1** | **留意**：记录在 [METRICS_LOG.md](./METRICS_LOG.md)，不自动 block |

**示例（baseline → current）：**

```
llm_offtrack: 1 → 4  (+3)  → 触发规则 A（≥2）
tool_error:   2 → 3  (+1)  → 仅留意
```

### 规则 B — 含失败 session 占比

| 条件 | 动作 |
|------|------|
| 含失败 session 占比 **上升 ≥ 10 个百分点（pp）** | **暂缓**：prompt / 工具相关 PR 合并前须复测或修复 |
| 上升 **5–9 pp** | **必看** |
| 上升 **< 5 pp** | 记录即可 |

**计算公式：**

```
fail_rate = (含 failure_types 的轨迹数) / n_trajectories × 100%
delta_pp  = current_fail_rate - baseline_fail_rate
```

**历史参照（非 baseline）：**  
[tdebug_failure_real_20260715](../snapshots/tdebug_failure_real_20260715.json) 中 N=100，含失败 session **9 条（9%）**，分布 `llm_offtrack:6, tool_error:2, duplicate:1, no_answer:1`。

### 规则 C — 未覆盖的新失败模式

| 条件 | 动作 |
|------|------|
| golden 27 未覆盖、且 baseline 中未出现的新 `failure_types` 组合 | **人工判定**：补 golden fixture 或调整 analyzer 规则（见 [RISKS.md](../RISKS.md) §1） |

---

## 与 `--compare` 输出的对应关系

`compare_snapshots` 终端报告包含：

1. 各类型 `base / cur / delta` → 对照 **规则 A**
2. `含失败轨迹数: X → Y (+Z)` → 换算占比后对照 **规则 B**
3. `扫描轨迹总数` 变化 → 若 `n` 不一致，先对齐 N 再比（试点固定 N=100）

---

## 决策枚举（写入 METRICS_LOG）

| 决策 | 含义 |
|------|------|
| `pass` | 未触发 block 条件 |
| `review` | 触发「必看」，已人工确认可接受 |
| `hold` | 触发暂缓，未合并 / 未发版 |
| `fix` | 发现问题并已修复后重扫 |

---

## 刻意不纳入 v1 的条件

- 单条轨迹 query 内容变化（compare 不看语义）
- golden CI 通过率（独立门禁，与 pilot compare 并行）
- 绝对失败数为 0 的要求（小样本下噪声大）

---

## 文档维护

| 版本 | 日期 | 说明 |
|------|------|------|
| v1 | 2026-07-30 | Phase 0 初版；待 Phase 3 跑 2 次 compare 后校准 |
