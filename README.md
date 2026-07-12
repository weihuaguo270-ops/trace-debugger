# Trace Debugger

**Agent execution trace analyzer** — parse Harness execution trajectories, identify failure root causes, replay step-by-step, and batch-scan for systematic failure patterns.

## Why

Agent execution trajectories are typically stored as raw JSON — machines can read them, humans can't. Trace Debugger translates these trajectories into actionable insights.

**Input:** Harness trajectory JSON → **Output:** Root cause analysis, failure classification, interactive replay

## Commands

| Command | Description |
|---------|-------------|
| `tdebug <file.json>` | Analyze trajectory, identify root causes per path |
| `tdebug replay <file.json>` | Step-by-step replay with Enter advancement |
| `tdebug scan <directory>` | Batch-analyze latest N trajectories in directory |

## Failure Classification

| Type | Detects |
|------|---------|
| `tool_error` | Tool call failure (invalid params, execution exception) |
| `search_empty` | Search returned no useful results |
| `search_timeout` | Search / tool call timed out |
| `llm_offtrack` | LLM deviated from user intent |
| `duplicate` | Repeated identical attempts |
| `no_answer` | No final answer produced |

## Quick Start

```bash
pip install -e .
tdebug trajectory.json
tdebug replay trajectory.json
tdebug scan ./trajectories/
```

## Input Format

Trace Debugger reads trajectories in Harness format (thought/action/observation sequences). Compatible with any ReAct-based agent framework that records execution traces in this schema.

## Related Projects

- [handwritten-react-agent](https://github.com/weihuaguo270-ops/handwritten-react-agent) — ReAct Agent framework that produces Harness-format trajectories

## License

MIT
