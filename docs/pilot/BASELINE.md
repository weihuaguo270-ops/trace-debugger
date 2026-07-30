# 试点 Baseline（Phase 2）

**冻结日期：** 2026-07-30  
**用途：** Phase 3+ 发版 / PR 前 `--compare` 的回归基准

---

## 冻结配置

| 字段 | 值 |
|------|-----|
| react-agent commit | [`bbe48ee`](https://github.com/weihuaguo270-ops/react-agent/commit/bbe48ee) |
| trace-debugger | `42fe027` (v0.2.4) |
| 轨迹目录 | `../react-agent/src/react_agent/trajectories` |
| 样本量 N | **100** |
| 选取逻辑 | 目录内按 **mtime 最新** 100 条（与 `tdebug scan` 默认一致） |

---

## 快照文件

| 文件 | 变体 | 说明 |
|------|------|------|
| [pilot_baseline.json](../snapshots/pilot_baseline.json) | `latest_by_mtime` | **主 baseline**；与 CLI scan 同逻辑 |
| [pilot_baseline_no_mock.json](../snapshots/pilot_baseline_no_mock.json) | `latest_non_mock_by_mtime` | 排除 `model: mock`；更适合生产向门禁 |

### pilot_baseline.json（主）

| 指标 | 值 |
|------|-----|
| report_id | `pilot_baseline_20260730` |
| distribution | `search_empty:30`, `tool_error:6` |
| 含失败 session | **36 / 100（36%）** |
| mock 轨迹 | **30 条**（StepWatcher 证据 run） |

> 主 baseline 含 mock 是故意的：与 `tdebug scan … 100` 默认行为一致，Phase 3「无害改动」应对 diff≈0。  
> 发版 review 时若只关心生产 run，请用 **no_mock** 变体（见下）。

### pilot_baseline_no_mock.json（生产向）

| 指标 | 值 |
|------|-----|
| report_id | `pilot_baseline_no_mock_20260730` |
| distribution | `tool_error:6`, `no_answer:1` |
| 含失败 session | **7 / 100（7%）** |
| 选取 | 跳过 `model: mock`，取最新 100 条非 mock |

> 当前 CLI **无** `--exclude-model`；no_mock 快照由冻结脚本生成（见「复现」）。  
> 后续可在独立 PR 为 `tdebug scan` 增加过滤选项。

---

## 与 Phase 1 pilot_latest 的一致性

Phase 2 冻结时，`pilot_baseline.json` 与 Phase 1 的 `pilot_latest.json`：

- **文件集合相同**（100/100）
- **distribution 相同**

因此 Phase 3 Run A（无害改动）在同一 commit 上重扫，预期 **diff ≈ 0**。

---

## Baseline 更新策略

| 场景 | 动作 |
|------|------|
| **常规 PR / prompt 小改** | 不更新 baseline；只 `--compare pilot_baseline.json` |
| **Analyzer 规则 intentional 变更** | 重拍 baseline + 更新本文件 + METRICS_LOG 记 `review` |
| **react-agent 大版本 / 轨迹 schema 变更** | 重拍两套 baseline；旧快照移入 `docs/snapshots/archive/` |
| **mock 证据批量写入后** | 主 baseline 会漂移；优先看 **no_mock** 或先清理 mock 轨迹 |
| **确认质量改进后** | 可选「晋级 baseline」：新 stable commit 重扫并替换 json |

**禁止：** 在 compare 显示变差后，未经 team review 直接覆盖 baseline 以「刷绿」。

---

## 标准 compare 命令

```bash
# 主 baseline（含 mock，与 CLI 默认一致）
tdebug scan ../react-agent/src/react_agent/trajectories 100 \
  --json-out docs/snapshots/pilot_latest.json \
  --compare docs/snapshots/pilot_baseline.json
```

生产向对照（暂用手动脚本，见 [WORKFLOW.md](./WORKFLOW.md)）：

```bash
python scripts/build_pilot_scan.py --exclude-mock --n 100 \
  --json-out docs/snapshots/pilot_latest_no_mock.json
# 再 compare pilot_baseline_no_mock.json
```

---

## 复现冻结

```bash
cd trace-debugger
python scripts/build_pilot_scan.py --n 100 --baseline-out docs/snapshots/pilot_baseline.json
python scripts/build_pilot_scan.py --n 100 --exclude-mock \
  --baseline-out docs/snapshots/pilot_baseline_no_mock.json
```

---

## 文档维护

| 日期 | 说明 |
|------|------|
| 2026-07-30 | Phase 2 冻结；主 + no_mock 双 baseline |
