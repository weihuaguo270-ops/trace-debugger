# 失败分布周报索引

本目录存放 **trace-debugger** 批量扫描得到的失败类型分布快照（启发式，学习用途）。

## 报告一览

| 报告 | 来源 | 轨迹数 | 分布摘要 |
|------|------|--------|----------|
| [tdebug_failure_flywheel_20260716.md](./tdebug_failure_flywheel_20260716.md) | `failure_bundle`（飞轮首跑） | 5 | 全类型演示；闭环见 react-agent `FAILURE_FLYWHEEL.md` |
| [tdebug_failure_real_20260715.md](./tdebug_failure_real_20260715.md) | `react-agent` 本地 `trajectories/`（gitignore） | **100** | tool_error×2, llm_offtrack×6, duplicate×1, no_answer×1 |
| [tdebug_failure_20260715.md](./tdebug_failure_20260715.md) | `examples/failure_bundle`（演示样例） | 5 | 全类型演示：tool_error / no_answer / duplicate / offtrack / overflow |

## 一键发布

```bash
# 真实本地轨迹（推荐写进简历的周报）
python examples/publish_failure_snapshot.py --dir ../react-agent/src/react_agent/trajectories --n 100 --stem tdebug_failure_real_YYYYMMDD

# 演示样例（CI / 无本地轨迹时）
python examples/publish_failure_snapshot.py --dir examples/failure_bundle
tdebug scan examples/failure_bundle 20
```

## 诚实边界

- 分类为规则/启发式，**不是** LLM-as-Judge
- **真实周报**：源目录在 react-agent `trajectories/`，默认 gitignore，不进公开仓库；公开物是本仓 `docs/snapshots/*.json` 摘要
- `failure_bundle` 仅用于 taxonomy 演示；投简历请优先引用 `*_real_*` 报告
