# Agent Trajectory Schema (Format B)

**Canonical wire format for [trace-debugger](https://github.com/weihuaguo270-ops/trace-debugger).**

Any ReAct-style Agent that emits this JSON can use offline analysis (`tdebug`), failure recording, and optional runtime `StepWatcher` — without coupling to a specific Agent framework.

## File

[`agent_trajectory.schema.json`](agent_trajectory.schema.json)

## Interop rules

1. `step` is **1-based** (never emit `0` from new producers).
2. Prefer `action.arguments` as a **JSON string**; `args` object is accepted.
3. Prefer singular `action`; use `actions[]` only for multi-tool steps.
4. Required top-level: `session_id`, `query`, `steps`, `final_answer`.
5. **Multi-path**: either top-level `paths[]`, or flat `steps[]` with `path_id` / `branch_id`.
6. **Failure tags** (optional, usually from StepWatcher): `failure_tags`, `failure_summary`, `failure`, etc.

## Producers

| Runtime | Role |
|---------|------|
| **Any custom harness** | Emit Format B JSON after each run |
| [react-agent](https://github.com/weihuaguo270-ops/react-agent) | Reference integration + StepWatcher bridge |
| [llm-eval-engine](https://github.com/weihuaguo270-ops/llm-eval-engine) | Consumer for Process Reward / eval |

## Consumers in this repo

- `trace_debugger.reader.parse()` — load trajectory
- `trace_debugger.analyzer.Analyzer` — heuristic failure classification
- `trace_debugger.runtime.StepWatcher` — runtime detection + JSONL record

Fixtures: `fixtures/failure_golden/` (27 cases, CI gate).

## Legacy alias

react-agent historically published the same format as `harness_trajectory.schema.json`. New integrations should reference **this file** as the source of truth.
