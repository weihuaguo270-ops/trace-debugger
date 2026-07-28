# Changelog

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
