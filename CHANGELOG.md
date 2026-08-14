# Changelog

## Unreleased

## 0.5.0 (2026-08-14)

### Added

- `acceptance_failed` classification for failed delivery test and release-validation steps
- Regression coverage from the real GitHub delivery sandbox fault-injection trajectory

### Changed

- Acceptance failures now fail the path instead of being reported as a successful tool step

### Documentation

- Added Episode v1 and portable failure-log capabilities to the project overview
- Aligned the react-agent pilot index with the completed Phase 0-5 scope

## 0.4.0 (2026-08-12)

### Added

- EvaluationEpisode v1 import without the producing Agent SDK
- Framework, Agent version, split, and state-verification evidence preservation
- Portable failure-log directory with `TDEBUG_DATA_DIR` and explicit overrides
- Linux portability checks

### Changed

- Default failure logs use the platform user-data directory
- Historical evidence paths use `${WORKSPACE_ROOT}`

### Verified

- Full regression: 75 passed

## 0.3.0 (2026-08-11)

### Added

- Format B Schema 支持 input_artifacts、output_artifacts 和步骤级 artifacts
- Artifact 字段限制为引用和技术元数据，禁止内嵌 data/base64 内容

### Changed

- README 明确 Trace Debugger 只保存和校验媒体引用，不负责媒体语义评分

## 0.2.7 (2026-07-30)

### Added

- **Harness Health** — `trace_debugger/harness_health.py`：Agent Work Loop 五维、证据状态、THRESHOLDS 门禁 → `findings.json`
- **CLI** — `tdebug scan … --findings-out` · `--project-root`；compare 时输出 `门禁判定`
- **Schema** — `schemas/findings.schema.json` · `schemas/intervention_ledger.schema.json`
- **Format B** — 轨迹可选 `task_episode_id` · `acceptance_criteria`（scan 快照透传）
- **docs/intervention_ledger.json** — 纵向干预记录（offtrack 6→1 等）
- **react-agent/docs/HARNESS_HEALTH.md** — 五维映射与使用说明

## 0.2.6 (2026-07-30)

### Added

- **Phase 5** — [docs/pilot/PHASE5.md](docs/pilot/PHASE5.md) failure 调查耗时；`scripts/phase5_timing_study.py`
- **能力评估 manifest** — dev 50 / held-out 80 分离；[CAPABILITY_MANIFEST.md](docs/pilot/CAPABILITY_MANIFEST.md)
- **held-out 首轮统计** — 7/80（8.8%）；[CAPABILITY_HELD_OUT_RUN.md](docs/pilot/CAPABILITY_HELD_OUT_RUN.md)
- **scripts/build_capability_manifest.py** · **scripts/run_capability_eval.py**

### Changed

- **docs/VALUE.md** — 业务自评 ~65%；能力/回归双轨说明
- **docs/pilot/** — METRICS_LOG、README 更新

## 0.2.5 (2026-07-30)

### Added

- **docs/pilot/** — react-agent 试点 Phase 0–4：baseline、THRESHOLDS、PHASE1/3 报告、WORKFLOW、METRICS_LOG
- **docs/cases/regression_gate_20260730.md** — 发版前 compare 决策案例（假阳性纠正 + 生产向 review 模拟）
- **docs/cases/TEMPLATE.md** — 后续案例模板
- **docs/snapshots/pilot_*.json** — 试点扫描 / baseline / Run A·B 脱敏快照（8 个）
- **scripts/build_pilot_scan.py** — 试点 scan（`--exclude-mock`、`--from-snapshot`、`--offtrack-overlap`）

### Changed

- **docs/VALUE.md** — 业务证明自评 ~55%；项目负责人口吻
- **README.md** — 试点证据与案例链接；交付表更新
- **docs/FAILURE_INDEX.md** — 试点与案例索引
- **docs/RISKS.md** — 与 VALUE / 试点结论对齐

## 0.2.4 (2026-07-29)

### Changed

- **docs/RISKS.md** / **SECURITY.md** / README「诚实边界」：项目负责人决策口吻（含 100 条轨迹 offtrack 6→1 案例）；去除 risk-register 模板化写法

## 0.2.3 (2026-07-29)

### Added

- **风险登记** [docs/RISKS.md](docs/RISKS.md)：准确率 / 数据安全 / 运行可靠性 / 产品竞争
- **SECURITY.md** 扩充：record 数据范围、部署建议、集成方责任

### Changed

- README「诚实边界」链接 RISKS 四类风险摘要
- `record.py` 模块 docstring 增加数据安全提示

## 0.2.2 (2026-07-29)

### Added

- **Format B schema 本仓 canonical** — `schemas/agent_trajectory.schema.json`
- **可移植 harness** — `FailureHarness`、`StepEvent`、`RunContext`；离线 `build_trajectory_dict` / `enrich_trajectory_dict`
- **Adapters 示例** — `examples/adapters/`（graph_style、react_loop）
- **`tdebug validate`** — Format B 轻量校验；可选 `[schema]` extra + `--schema`
- **docs/INTEGRATIONS.md** — 集成指南；Analyzer 可配置 markers / search patterns

### Changed

- **docs/FAILURE_INDEX.md** — golden 证据优先；react-agent 降为附录

## 0.2.1 (2026-07-29)

### Fixed

- **CI packaging** — `pyproject.toml` `[tool.setuptools.packages.find] include = ["trace_debugger*"]`
- **test_basic.py** lint

## 0.2.0 (2026-07-29)

### Added

- **失败治理闭环** — record、StepWatcher、golden 27、stats
- **CLI 闭环** — `tdebug judge`；analyze/scan 的 `--json-out`、`--record`、`--compare`
- **证据发布** — `examples/publish_golden_evidence.py`；`docs/golden_evidence_baseline.md`

## 0.1.x

早期版本见 git history。
