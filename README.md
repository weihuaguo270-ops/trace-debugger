# Trace Debugger

[![CI](https://github.com/weihuaguo270-ops/trace-debugger/actions/workflows/test.yml/badge.svg)](https://github.com/weihuaguo270-ops/trace-debugger/actions/workflows/test.yml) [![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org) [![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Agent 执行轨迹分析小工具（学习/配套实验）** — 读取 Harness 轨迹 JSON，识别失败根因，逐步骤回放，批量扫描发现系统性问题。

## 解决的问题

Agent 的执行轨迹通常以原始 JSON 记录——机器能读，人看不懂。Trace Debugger 将这些轨迹"翻译"成对人类有意义的复盘分析。

**输入：** Harness 轨迹 JSON → **输出：** 根因分析、失败分类、交互式回放

## 功能

| 命令 | 说明 |
|------|------|
| `tdebug <file.json>` | 分析轨迹，识别每条路径的成败原因 |
| `tdebug replay <file.json>` | 逐步骤回放，按 Enter 推进 |
| `tdebug scan <目录>` | 批量分析目录中最新 N 条轨迹 |

## 失败原因分类

| 类型 | 检测内容 | 状态 |
|------|---------|------|
| `tool_error` | 工具调用报错（参数错误/执行异常） | 已实现 |
| `search_empty` | 搜索无有效结果（观测过短；含 `web_search`） | 已实现 |
| `search_timeout` | 单步耗时过长（默认 >20s） | 已实现 |
| `duplicate` | 相邻步重复相同工具名+参数 | 已实现 |
| `no_answer` | 无 `FINAL ANSWER` 且无 `final_answer` 字段 | 已实现 |
| `llm_offtrack` | 查询与最终答案内容词重叠过低（启发式；答案 grounded 于工具观测 / 短事实+数字时跳过） | 已实现 |
| `context_overflow` | 单步/累计 token 超预算，或观测含上下文溢出文案 | 已实现 |

> `llm_offtrack` / `context_overflow` 为可配置启发式（见 `Analyzer(token_budget=..., offtrack_overlap=...)`），不是 LLM Judge。

## 快速开始

```bash
pip install -e .
tdebug trajectory.json
tdebug replay trajectory.json    # 逐步骤回放
tdebug scan ./trajectories/ 10   # 批量扫描 + 失败类型分布
# 等价入口：trace-debug / python -m trace_debugger
```

## 输入格式

读取 **Harness Format B** 轨迹（`thought` / `action` / `observation`）。约定：

- `step` 为 **1-based**
- 工具参数优先 `action.arguments`（字符串）；也接受 `args`（对象）
- 同一步多工具可用 `actions[]`（reader 取首个作主调用）

权威 JSON Schema：[react-agent/schemas/harness_trajectory.schema.json](https://github.com/weihuaguo270-ops/react-agent/blob/main/schemas/harness_trajectory.schema.json)

一键闭环（含本工具失败分类 + eval-engine 评分）：

```bash
# 在 react-agent 仓
python examples/harness_closed_loop.py --fixture
```

## 失败分布周报

```bash
# 发布 Markdown + 归档 JSON（默认证件束演示样例）
python examples/publish_failure_snapshot.py --dir examples/failure_bundle
# 索引见 docs/FAILURE_INDEX.md
tdebug scan examples/failure_bundle 20
```

公开快照示例：
- 真实轨迹：[docs/tdebug_failure_real_20260715.md](docs/tdebug_failure_real_20260715.md)（100 条）
- 演示样例：[docs/tdebug_failure_20260715.md](docs/tdebug_failure_20260715.md)
- 飞轮扫描：[docs/tdebug_failure_flywheel_20260716.md](docs/tdebug_failure_flywheel_20260716.md)

## 相关项目

- [react-agent](https://github.com/weihuaguo270-ops/react-agent) — 生成 Harness 格式轨迹的 ReAct Agent 学习实现
- [llm-eval-engine](https://github.com/weihuaguo270-ops/llm-eval-engine) — 可对轨迹做 Process Reward 评分的实验框架

## 示例输出

```text
$ tdebug examples/sample_trajectory.json

📊 轨迹分析报告
═══════════════════════════════════════

会话 ID: demo_001
查询: 写一份关于 AI 行业趋势的简短报告
模型: gpt-4

路径分析:
  ✅ 路径 0（主路径）:
     Step 1: web_search "AI industry trends 2026" ✓
     Step 2: web_search "中国 AI 市场 2026 趋势" ✓
     Step 3: 整理信息 ✓
     Step 4: 撰写报告 ✓

评估: ✅ 执行顺利，4 步无错误
```

更多示例见 [`examples/sample_trajectory.json`](examples/sample_trajectory.json)。

## License

MIT

## 贡献与安全

见 [CONTRIBUTING.md](CONTRIBUTING.md) / [SECURITY.md](SECURITY.md)。
