# 失败分布周报索引

本目录存放 **trace-debugger** 批量扫描得到的失败类型分布快照（启发式，学习用途）。

## 标准证据（推荐引用）

| 报告 | 来源 | 轨迹数 | 说明 |
|------|------|--------|------|
| [golden_evidence_baseline.md](./golden_evidence_baseline.md) | `fixtures/failure_golden` | **27** | CI 门禁 100%；**对外引用首选** |
| [GOLDEN_FAILURE_INDEX.md](./GOLDEN_FAILURE_INDEX.md) | 黄金集索引 | 27 | taxonomy + golden/held_out 分栏 |
| [tdebug_failure_20260715.md](./tdebug_failure_20260715.md) | `examples/failure_bundle` | 5 | 快速演示 bundle |

## 一键发布（本仓自洽，无需外部 Agent）

```bash
# 黄金证据集（CI 同款）
python examples/publish_golden_evidence.py

# 演示 bundle
python examples/publish_failure_snapshot.py --dir examples/failure_bundle
tdebug scan fixtures/failure_golden 27

# 导出前校验
tdebug validate fixtures/failure_golden/tool_error.json
tdebug validate fixtures/failure_golden/tool_error.json --schema   # 需 [schema] 可选依赖
```

## 试点回归门禁（react-agent Phase 0–5）

| 文档 | 说明 |
|------|------|
| [pilot/README.md](./pilot/README.md) | 试点配置、baseline、工作流 |
| [cases/regression_gate_20260730.md](./cases/regression_gate_20260730.md) | **发版前 compare 决策案例**（假阳性纠正 + review） |
| [snapshots/pilot_baseline.json](./snapshots/pilot_baseline.json) | 冻结 baseline（脱敏摘要） |
| [pilot/PHASE5.md](./pilot/PHASE5.md) | 调查耗时代理估计；不作为真人效率结论 |

## 附录：参考集成案例（react-agent）

以下报告来自 [react-agent](https://github.com/weihuaguo270-ops/react-agent) 参考运行时本地轨迹，**非本仓可复现前提**：

| 报告 | 来源 | 轨迹数 |
|------|------|--------|
| [tdebug_failure_real_20260715.md](./tdebug_failure_real_20260715.md) | react-agent `trajectories/`（gitignore） | 100 |
| [tdebug_failure_flywheel_20260716.md](./tdebug_failure_flywheel_20260716.md) | failure_bundle 飞轮首跑 | 5 |
| 闭环对照 | 同批 100 文件重扫 | 见 [flywheel_closed_loop](https://github.com/weihuaguo270-ops/react-agent/blob/main/docs/flywheel_closed_loop_20260716.md) |

```bash
# 仅在本地已安装 react-agent 且存在 trajectories/ 时
python examples/publish_failure_snapshot.py --dir ../react-agent/src/react_agent/trajectories --n 100
```

## 诚实边界

- 分类为规则/启发式，**不是** LLM-as-Judge
- 对外引用请优先 **golden 证据集** + **[回归门禁案例](./cases/regression_gate_20260730.md)**；react-agent 历史周报仅说明参考集成
