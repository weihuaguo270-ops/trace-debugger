# 试点回归工作流（Phase 3）

Phase 2 已冻结 baseline，本文是 **scan + compare** 的标准操作说明。

---

## 何时跑

| 时机 | 谁跑 | 对比基准 |
|------|------|----------|
| PR 改 prompt / 工具 / analyzer | PR 作者 | `pilot_baseline.json` |
| 发版前 | 发布负责人 | `pilot_baseline.json` |
| 只关心生产 run（无 mock） | 同上 | `pilot_baseline_no_mock.json` + 脚本 |

---

## 主路径（CLI，与 baseline 选取一致）

```bash
cd trace-debugger

tdebug scan ../react-agent/src/react_agent/trajectories 100 \
  --json-out docs/snapshots/pilot_latest.json \
  --compare docs/snapshots/pilot_baseline.json \
  --findings-out docs/snapshots/pilot_latest_findings.json \
  --require-verification \
  --project-root .
```

1. 看终端 **distribution delta**、**含失败轨迹数**、**门禁判定**（`pass` / `review` / `hold`）
2. 对照 [THRESHOLDS.md](./THRESHOLDS.md) 判定 pass / review / hold
3. 检查 `pilot_latest_findings.json`：每条 finding 都带 `verification_ref`（回归锁：必须命中的
   fixture、必须保持干净的假阳性 fixture、复跑命令）。`--require-verification` 会在任何 finding
   缺少可解析回归锁时 exit 1 —— 没有夹具覆盖的失败类型（当前为 `acceptance_failed`、
   `incomplete_stream`）一旦回归就会被拦下，必须先补 golden 用例
4. 可选：检查 `findings[].repair_boundary` 确定修复边界
5. 追加一行到 [METRICS_LOG.md](./METRICS_LOG.md)

---

## 生产向路径（排除 mock）

CLI 暂不支持过滤；使用冻结脚本：

```bash
python scripts/build_pilot_scan.py --exclude-mock -n 100 \
  --json-out docs/snapshots/pilot_latest_no_mock.json

python -c "
from trace_debugger.record import load_snapshot, compare_snapshots
cur = load_snapshot('docs/snapshots/pilot_latest_no_mock.json')
base = load_snapshot('docs/snapshots/pilot_baseline_no_mock.json')
print(compare_snapshots(cur, base))
"
```

---

## Phase 3 验证计划（已执行）

详见 [PHASE3.md](./PHASE3.md)。

| Run | 操作 | 结果 |
|-----|------|------|
| **Run A** | 无害重扫 | ✅ diff = 0，`pass` |
| **Run B** | `offtrack_overlap` 劣化模拟 | ✅ 规则 A 触发，`review` |

---

## PR checklist（试点）

- [ ] `tdebug scan … 100 --compare pilot_baseline.json` 已跑
- [ ] 未触发 hold，或 hold 已解决并附 METRICS_LOG
- [ ] `--require-verification` 通过：每条 finding 都能指到回归锁（否则先补 fixture）
- [ ] golden CI 仍 32/32（独立门禁）

---

## 文档维护

| 日期 | 说明 |
|------|------|
| 2026-07-30 | Phase 2 附带初版；Run A/B 待 Phase 3 执行 |
