# Changelog

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
- **可移植集成层** `trace_debugger.harness`：`RunContext`、`StepEvent`、`FailureHarness`、离线 `build/enrich`
- **Adapter 样板** `examples/adapters/`（graph-style + react-loop）+ `tests/test_adapters.py`
- **`trace_debugger.validate`** + `tdebug validate`（`--schema` 需 `pip install trace-debugger[schema]`）
- **Analyzer 配置**：`final_answer_markers`、`search_tool_names`、`search_tool_substrings`
- **`TDEBUG_RECORD_PATH`** 环境变量
- 演示 `examples/portable_harness_demo.py`
- **Canonical schema** `schemas/agent_trajectory.schema.json` + `schemas/README.md`
- **集成指南** `docs/INTEGRATIONS.md`

### Changed
- README / 定位改为**独立 Agent 失败治理工具**；react-agent 降为参考集成
- `docs/FAILURE_INDEX.md`：golden 证据置顶，react-agent 案例降为附录

## 0.2.1 (2026-07-28)

### Fixed
- CI：`fixtures/` 被 setuptools 误识别为包，导致 `pip install -e` 失败；显式限定 `trace_debugger*` 包发现
- CI：flake8 — 移除重复 `import tempfile`，`if __name__` 块移至测试定义之后

## 0.2.0 (2026-07-28)

### Added
- **黄金失败集** `fixtures/failure_golden/`（27 条：golden 21 + held_out 6）+ `manifest.json` + CI 门禁
- **运行时检测** `StepWatcher`（`trace_debugger/runtime.py`）+ react-agent Harness 集成
- **失败记录 v2**：JSONL + `failures.log` + `sessions/{id}.md`；step 上 `failure_summary` / `failure` 块
- **CLI**：`tdebug failures`、`tdebug stats`（按失败类型聚合）；`--stats-json-out`
- **CLI 闭环**：`tdebug judge`；analyze/scan 的 `--json-out`、`--record`、`--compare`
- **证据发布**：`examples/publish_golden_evidence.py`；`docs/golden_evidence_baseline.md`
- **多路径解析**：`paths[]`、`path_id` / `branch_id` 分组
- `trace_debugger/golden.py` — 黄金集加载与断言
- `scripts/generate_failure_golden.py` — 生成并校验 fixture

### Changed
- README 改为**项目负责人视角**：问题 → 角色 → 生态分工 → 工作流 → 交付状态 → 诚实边界；命令/API 下沉附录
- 复盘报告移除未实现的「输入 y/n 交互」提示
- `llm_offtrack`：grounded 答案与短事实+数字豁免（减假阳性）
- CLI / reporter：`[PASS]/[WARN]/[FAIL]`，兼容 Windows GBK

## 0.1.0 (2026-07-12)

### Added
- 初始版本：轨迹分析、回放、扫描
- 7 类失败启发式分类
- 失败分布周报：`examples/publish_failure_snapshot.py` + `examples/failure_bundle/`
- 测试套件与 GitHub Actions CI
