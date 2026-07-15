# 失败分布周报索引

本目录存放 **trace-debugger** 批量扫描得到的失败类型分布快照（启发式，学习用途）。

## 报告一览

| 报告 | 来源 | 轨迹数 | 分布摘要 |
|------|------|--------|----------|
| [tdebug_failure_20260715.md](./tdebug_failure_20260715.md) | `examples/failure_bundle` | 5 | tool_error / no_answer / duplicate / llm_offtrack / context_overflow（+ search_empty） |

## 一键发布

```bash
python examples/publish_failure_snapshot.py --dir examples/failure_bundle
# 真实周报：指向本周轨迹目录
python examples/publish_failure_snapshot.py --dir ../react-agent/src/react_agent/trajectories --n 30
tdebug scan examples/failure_bundle 20
```

## 诚实边界

- 分类为规则/启发式，**不是** LLM-as-Judge
- `failure_bundle` 为可复现演示样例；投简历时注明样本来源与日期
