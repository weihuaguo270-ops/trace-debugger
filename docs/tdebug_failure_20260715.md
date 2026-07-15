# tdebug 失败分布周报（tdebug_failure_20260715）

- **report_id:** `tdebug_failure_20260715_075232`
- **timestamp:** `2026-07-15T07:52:32.194471+00:00`
- **source:** `D:/agent_learning/trace-debugger/examples/failure_bundle`
- **轨迹数:** 5
- **git:** `b34a3ba`

## 失败类型分布（路径级计数）

| type | count | label |
|------|------:|-------|
| `context_overflow` | 1 | 上下文窗口溢出 |
| `duplicate` | 1 | 重复相同尝试 |
| `llm_offtrack` | 1 | LLM 偏离用户意图 |
| `no_answer` | 1 | 未给出最终答案 |
| `search_empty` | 1 | 搜索无有效结果 |
| `tool_error` | 1 | 工具调用报错 |

## 轨迹明细

- `overflow.json` — ❌ 执行问题较多（2/2 步），建议检查 — fails=[context_overflow] — summarize this long page
- `duplicate.json` — ❌ 执行问题较多（2/3 步），建议检查 — fails=[duplicate,search_empty] — 搜索 Python 文档
- `offtrack.json` — ❌ 执行问题较多（1/1 步），建议检查 — fails=[llm_offtrack] — 写一份关于人工智能行业趋势的详细分析报告
- `no_answer.json` — ❌ 执行问题较多（1/1 步），建议检查 — fails=[no_answer] — 北京今天天气如何？
- `tool_error.json` — ❌ 执行问题较多（1/2 步），建议检查 — fails=[tool_error] — 计算 2+2

## 复现

```bash
python examples/publish_failure_snapshot.py --dir examples/failure_bundle
tdebug scan examples/failure_bundle 20
```

## 诚实边界

- 分类为规则/启发式，不是 Judge 打分
- `failure_bundle` 为演示样例；真实周报应指向本周 `trajectories/`
