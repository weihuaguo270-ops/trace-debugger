# 黄金失败集证据索引

本目录说明 **trace-debugger** 黄金失败集（`fixtures/failure_golden/`）的证据链用途与复现方式。

## 数据集结构

| 分栏 | 数量 | 用途 |
|------|------|------|
| `golden` | 21 | 开发/回归 — taxonomy 覆盖 + 正例 + 组合失败 |
| `held_out` | 6 | 对照 — 不参与规则微调，只用于门禁 |

**合计 27 条**，每条在 `manifest.json` 含 `expected_failures` / `must_not_detect` / `expected_step_failures`。

## Taxonomy 覆盖

原有 7 类失败均有独立 golden 负例：`tool_error` · `search_empty` · `search_timeout` · `duplicate` · `no_answer` · `llm_offtrack` · `context_overflow`。`acceptance_failed` 由真实交付故障轨迹对应的独立回归测试覆盖，尚未并入历史 golden manifest。

另含：正例（无失败）、多路径、中文搜索工具、工具错误后恢复、Harness 阻止重复等。

## 报告一览

| 报告 | 说明 |
|------|------|
| [golden_evidence_baseline.md](./golden_evidence_baseline.md) | 黄金集全量通过率 + 分布（CI 发布） |
| [snapshots/golden_evidence_baseline.json](./snapshots/golden_evidence_baseline.json) | 机器可读快照 |

## 一键复现

```bash
# 重新生成 fixtures（改 spec 后）
python scripts/generate_failure_golden.py

# 门禁测试
python -m pytest tests/test_failure_golden.py -v

# 发布证据报告
python examples/publish_golden_evidence.py --stem golden_evidence_baseline
```

## 与 failure_bundle 关系

- `examples/failure_bundle/` — 早期 5 条演示（保留兼容）
- `fixtures/failure_golden/` — **标准证据集**（27 条 + manifest）

## 诚实边界

- 期望标签来自 Analyzer 启发式，经生成脚本交叉验证，**不是**人工逐条标注
- golden / held_out 须分栏引用，不可合并为一个「检测准确率」
