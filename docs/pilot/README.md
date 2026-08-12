# react-agent 试点（Phase 0–4）

我们在 sibling 项目 [react-agent](https://github.com/weihuaguo270-ops/react-agent) 上跑完一轮**发版前 compare 试点**，配置、快照和决策记录都在本目录。  
主场景说明见 [VALUE.md](../VALUE.md)。

---

## 阶段进度

| 阶段 | 状态 | 产出 |
|------|------|------|
| Phase 0 准备 | ✅ | [THRESHOLDS.md](./THRESHOLDS.md) · [METRICS_LOG.md](./METRICS_LOG.md) |
| Phase 1 试点接入 | ✅ | [PHASE1.md](./PHASE1.md) · [pilot_latest.json](../snapshots/pilot_latest.json)（含数据分析） |
| Phase 2 baseline | ✅ | [BASELINE.md](./BASELINE.md) · `pilot_baseline.json` · `pilot_baseline_no_mock.json` |
| Phase 3 回归工作流 | ✅ | [PHASE3.md](./PHASE3.md) · Run A/B 完成 |
| Phase 4 拦截案例 | ✅ | [cases/regression_gate_20260730.md](../cases/regression_gate_20260730.md) |
| Phase 5 耗时验证 | ✅ | [PHASE5.md](./PHASE5.md) · [phase5_timing_results.json](./phase5_timing_results.json) |
| 能力 manifest | ✅ | [CAPABILITY_MANIFEST.md](./CAPABILITY_MANIFEST.md) · [CAPABILITY_HELD_OUT_RUN.md](./CAPABILITY_HELD_OUT_RUN.md) |

---

## Phase 0 完成清单

| 项 | 状态 | 说明 |
|----|------|------|
| 选定试点项目 | ✅ | [react-agent](https://github.com/weihuaguo270-ops/react-agent) |
| 固定轨迹目录 | ✅ | 见下方「轨迹源」 |
| 固定扫描样本量 N | ✅ | **100**（与历史 `tdebug_failure_real_20260715` 一致） |
| 定义「变差」门禁阈值 | ✅ | [THRESHOLDS.md](./THRESHOLDS.md) |
| 建立指标记录表 | ✅ | [METRICS_LOG.md](./METRICS_LOG.md) |

**Phase 0 完成日期：** 2026-07-30

---

## 为何选 react-agent

| 理由 | 说明 |
|------|------|
| Format B 已对齐 | `schemas/harness_trajectory.schema.json` 指向本仓 canonical schema |
| 轨迹存量充足 | 本地 `trajectories/` 持续写入，适合 scan + compare |
| 有历史对照 | [tdebug_failure_real_20260715](../tdebug_failure_real_20260715.md) 已扫过同目录 100 条 |
| 集成参考 | StepWatcher bridge、adapter 示例均在 sibling 仓 |

react-agent 是**参考集成与证据来源**，不是 trace-debugger 的运行时依赖。

---

## 轨迹源（固定配置）

| 字段 | 值 |
|------|-----|
| **目录（绝对路径）** | `${WORKSPACE_ROOT}/react-agent\src\react_agent\trajectories` |
| **相对路径（自 trace-debugger 根）** | `../react-agent/src/react_agent/trajectories` |
| **格式** | Format B JSON（`traj_YYYYMMDD_HHMMSS_xxxx.json`） |
| **写入方** | react-agent `harness/recorder.py` |
| **扫描命令中的 N** | `100` |

### 2026-07-30 盘点

| 指标 | 值 |
|------|-----|
| 目录内 JSON 总数 | **445** |
| 最早文件 | `traj_20260713_100846_kknq.json`（2026-07-13） |
| 最新文件 | `traj_20260729_134107_zhf4.json`（2026-07-29） |
| react-agent `git` | `bbe48ee`（2026-07-29，StepWatcher bridge） |
| trace-debugger `git` | `42fe027`（v0.2.4） |

> `tdebug scan` 按文件名排序取**最新 N 条**。N=100 时样本覆盖约 7/13–7/29 的运行，与 2026-07-15 历史批次部分重叠、部分更新——Phase 1 将与 `tdebug_failure_real_20260715` 对照 analyzer 是否漂移。

---

## 历史参照快照

| 文件 | 用途 |
|------|------|
| [../snapshots/tdebug_failure_real_20260715.json](../snapshots/tdebug_failure_real_20260715.json) | Phase 1 对照：同目录、N=100、2026-07-15 扫描 |
| `pilot_baseline.json` | Phase 2 | 主 baseline（latest 100 by mtime） |
| `pilot_baseline_no_mock.json` | Phase 2 | 生产向 baseline（排除 mock） |
| （Phase 1 创建）`pilot_latest.json` | 每次 compare 的 current |

---

## 标准命令（Phase 1 起使用）

```bash
# 自 trace-debugger 根目录
tdebug scan ../react-agent/src/react_agent/trajectories 100 \
  --json-out docs/snapshots/pilot_latest.json \
  --compare docs/snapshots/pilot_baseline.json
```

Phase 2 建立 baseline 前，`--compare` 可改为 `--compare docs/snapshots/tdebug_failure_real_20260715.json` 做漂移检查。

---

## 数据与隐私

轨迹 JSON 可能含用户 query、工具参数与记忆上下文。**勿将原始轨迹提交到 trace-debugger 仓库**；仅提交脱敏后的快照 JSON 与案例叙事（见 [RISKS.md](../RISKS.md) §2）。

---

## 后续阶段

| 阶段 | 文档 / 产出 |
|------|-------------|
| Phase 1 | [PHASE1.md](./PHASE1.md) + `pilot_latest.json` + 漂移对照 |
| Phase 2 | [BASELINE.md](./BASELINE.md) + 双 baseline + [WORKFLOW.md](./WORKFLOW.md) |
| Phase 3 | [PHASE3.md](./PHASE3.md) + Run A/B 快照 |
| Phase 4 | [regression_gate_20260730.md](../cases/regression_gate_20260730.md) |

---

## 文档维护

| 日期 | 说明 |
|------|------|
| 2026-07-30 | Phase 0：定点 react-agent、N=100、阈值与指标表 |
