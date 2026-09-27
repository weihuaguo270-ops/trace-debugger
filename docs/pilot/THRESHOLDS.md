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

## 门禁规则（v1.1）

### 规则 A — 单类型计数上升

| 条件 | 动作 |
|------|------|
| 任一失败类型 `distribution[type]` **增加 ≥ 2** | **hold** |
| 任一失败类型增加 **+1** | **review** |

### 规则 B — 含失败 session 占比

仅当 `n_trajectories` **对齐**时生效：

| 条件 | 动作 |
|------|------|
| 含失败 session 占比 **上升 ≥ 10 pp** | **hold** |
| 上升 **5–9 pp** | **review** |

### 规则 R — 单类型率差（v1.1）

`rate[type] = distribution[type] / n_trajectories`。  
**n 不对齐时规则 B 跳过，规则 R 仍生效**，避免样本量漂移掩盖退化。

| 条件 | 动作 |
|------|------|
| 任一类型 rate **上升 ≥ 10 pp** | **hold** |
| 上升 **5–9 pp** | **review** |

`evaluate_regression_gate` 返回 `stability.distribution_rate_delta_pp`；`--compare` 终端表含 `base%/cur%/d_pp` 列。

### 规则 C — 未覆盖的新失败模式

| 条件 | 动作 |
|------|------|
| golden / FP 集未覆盖、且 baseline 中未出现的新 `failure_types` 组合 | **人工判定**：补 fixture 或调整 analyzer |

---

## 与 `--compare` 输出的对应关系

`compare_snapshots` 终端报告包含：

1. 各类型 `base / cur / delta` → 对照 **规则 A**
2. `含失败轨迹数: X → Y (+Z)` → 换算占比后对照 **规则 B**
3. `扫描轨迹总数` 变化 → 若 `n` 不一致，先对齐 N 再比（试点固定 N=100）
4. `门禁判定: PASS|REVIEW|HOLD` → 与 `--findings-out` 中 `gate_decision` 一致
5. `--fail-on hold|review|pass` → 达到阈值时 **非零退出**（CI 硬拦）；`--fail-on` 必须配合 `--compare`

| `--fail-on` | exit 1 当 |
|-------------|-----------|
| `hold` | 仅 `hold` |
| `review` | `review` 或 `hold` |
| `pass` | 任何非 `pass`（最严） |

默认不加 `--fail-on` 时仍只打印判定，不改退出码。

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
