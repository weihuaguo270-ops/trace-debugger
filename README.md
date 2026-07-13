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
| `search_empty` | 搜索无有效结果（观测过短） | 已实现 |
| `search_timeout` | 单步耗时过长（默认 >20s） | 已实现 |
| `duplicate` | 相邻步重复相同工具名+参数 | 已实现 |
| `no_answer` | 无 `FINAL ANSWER` 且无 `final_answer` 字段 | 已实现 |
| `llm_offtrack` | LLM 偏离用户意图 | **规划中** |
| `context_overflow` | 上下文窗口溢出 | **规划中** |

## 快速开始

```bash
pip install -e .
tdebug trajectory.json
tdebug replay trajectory.json    # 逐步骤回放
tdebug scan ./trajectories/      # 批量目录扫描
# 等价入口：trace-debug / python -m trace_debugger
```

## 输入格式

Trace Debugger 读取 Harness 格式的轨迹（thought/action/observation 序列）。兼容任何按此 schema 记录执行轨迹的 ReAct Agent。

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
     Step 0: web_search "AI industry trends 2026" ✓
     Step 1: web_search "中国 AI 市场 2026 趋势" ✓
     Step 2: 整理信息 ✓
     Step 3: 撰写报告 ✓

评估: ✅ 执行顺利，3 步无错误
```

更多示例见 [`examples/sample_trajectory.json`](examples/sample_trajectory.json)。

## License

MIT

## 贡献与安全

见 [CONTRIBUTING.md](CONTRIBUTING.md) / [SECURITY.md](SECURITY.md)。
