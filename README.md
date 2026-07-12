# Trace Debugger

**Agent 执行轨迹分析工具** — 读取 Harness 轨迹 JSON，识别失败根因，逐步骤回放，批量扫描发现系统性问题。

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

| 类型 | 检测内容 |
|------|---------|
| `tool_error` | 工具调用报错（参数错误/执行异常） |
| `search_empty` | 搜索无有效结果 |
| `search_timeout` | 搜索/工具调用超时 |
| `llm_offtrack` | LLM 偏离用户意图 |
| `duplicate` | 重复相同尝试 |
| `no_answer` | 未给出最终答案 |

## 快速开始

```bash
pip install -e .
tdebug trajectory.json
tdebug replay trajectory.json    # 逐步骤回放
tdebug scan ./trajectories/      # 批量目录扫描
```

## 输入格式

Trace Debugger 读取 Harness 格式的轨迹（thought/action/observation 序列）。兼容任何按此 schema 记录执行轨迹的 ReAct Agent。

## 相关项目

- [handwritten-react-agent](https://github.com/weihuaguo270-ops/handwritten-react-agent) — 生成 Harness 格式轨迹的 ReAct Agent 框架

## License

MIT
