# 黄金失败集证据（golden_evidence_baseline）

- **report_id:** `golden_evidence_20260728_115720`
- **timestamp:** `2026-07-28T11:57:20.892681+00:00`
- **cases:** 27 (pass 27 / fail 0)
- **pass_rate:** 100%
- **git:** `99ae967`

## 分栏通过率

| split | n | passed | pass_rate |
|-------|--:|-------:|----------:|
| `golden` | 21 | 21 | 100% |
| `held_out` | 6 | 6 | 100% |

## 失败类型覆盖（负例轨迹）

| type | count | label |
|------|------:|-------|
| `search_empty` | 5 | 搜索无有效结果 |
| `tool_error` | 5 | 工具调用报错 |
| `context_overflow` | 3 | 上下文窗口溢出 |
| `duplicate` | 3 | 重复相同尝试 |
| `no_answer` | 3 | 未给出最终答案 |
| `llm_offtrack` | 2 | LLM 偏离用户意图 |
| `search_timeout` | 2 | 搜索超时 |

## 用例明细

- `golden_tool_error` [PASS] split=golden expected=[tool_error] detected=[tool_error] — tool_error.json
- `golden_search_empty` [PASS] split=golden expected=[search_empty] detected=[search_empty] — search_empty.json
- `golden_search_timeout` [PASS] split=golden expected=[search_timeout] detected=[search_timeout] — search_timeout.json
- `golden_duplicate_with_empty` [PASS] split=golden expected=[duplicate,search_empty] detected=[duplicate,search_empty] — duplicate_with_empty.json
- `golden_duplicate_only` [PASS] split=golden expected=[duplicate] detected=[duplicate] — duplicate_only.json
- `golden_no_answer` [PASS] split=golden expected=[no_answer] detected=[no_answer] — no_answer.json
- `golden_offtrack` [PASS] split=golden expected=[llm_offtrack] detected=[llm_offtrack] — offtrack.json
- `golden_overflow_step` [PASS] split=golden expected=[context_overflow] detected=[context_overflow] — overflow_step.json
- `golden_overflow_meta` [PASS] split=golden expected=[context_overflow] detected=[context_overflow] — overflow_meta.json
- `golden_pass_clean` [PASS] split=golden expected=[-] detected=[-] — pass_clean.json
- `golden_pass_grounded_qa` [PASS] split=golden expected=[-] detected=[-] — pass_grounded_qa.json
- `golden_pass_multi_step` [PASS] split=golden expected=[-] detected=[-] — pass_multi_step.json
- `golden_tool_error_recovered` [PASS] split=golden expected=[tool_error] detected=[tool_error] — tool_error_recovered.json
- `golden_no_duplicate_diff_args` [PASS] split=golden expected=[-] detected=[-] — no_duplicate_diff_args.json
- `golden_multi_paths` [PASS] split=golden expected=[tool_error] detected=[tool_error] — multi_paths.json
- `golden_path_id_branch` [PASS] split=golden expected=[tool_error] detected=[tool_error] — path_id_branch.json
- `golden_search_empty_cn` [PASS] split=golden expected=[search_empty] detected=[search_empty] — search_empty_cn.json
- `golden_search_timeout_slow` [PASS] split=golden expected=[search_timeout] detected=[search_timeout] — search_timeout_slow.json
- `golden_no_answer_empty_final` [PASS] split=golden expected=[no_answer] detected=[no_answer] — no_answer_empty_final.json
- `golden_offtrack_subtle` [PASS] split=golden expected=[llm_offtrack] detected=[llm_offtrack] — offtrack_subtle.json
- `golden_overflow_cumulative` [PASS] split=golden expected=[context_overflow] detected=[context_overflow] — overflow_cumulative.json
- `held_out_pass_report` [PASS] split=held_out expected=[-] detected=[-] — held_out_pass_report.json
- `held_out_mixed_warn` [PASS] split=held_out expected=[tool_error] detected=[tool_error] — held_out_mixed_warn.json
- `held_out_search_chain` [PASS] split=held_out expected=[search_empty] detected=[search_empty] — held_out_search_chain.json
- `held_out_offtrack_calc` [PASS] split=held_out expected=[-] detected=[-] — held_out_offtrack_calc.json
- `held_out_no_answer_maxsteps` [PASS] split=held_out expected=[no_answer] detected=[no_answer] — held_out_no_answer_maxsteps.json
- `held_out_duplicate_blocked` [PASS] split=held_out expected=[duplicate,search_empty] detected=[duplicate,search_empty] — held_out_duplicate_blocked.json

## 复现

```bash
python scripts/generate_failure_golden.py
python -m pytest tests/test_failure_golden.py -v
python examples/publish_golden_evidence.py
```

## 诚实边界

- 标签为规则/启发式 ground truth，非 LLM Judge
- golden=开发集，held_out=对照集；不可合并为一个准确率数字
