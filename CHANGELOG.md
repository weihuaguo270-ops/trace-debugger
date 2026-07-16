# Changelog

## Unreleased

### Added
- 失败分布周报发布：`examples/publish_failure_snapshot.py` + `examples/failure_bundle/` + `docs/FAILURE_INDEX.md`

### Changed
- `llm_offtrack`：答案 grounded 于工具观测或短事实+数字时不再误报（配合 react-agent 飞轮闭环）
- CLI / reporter 评估文案改用 `[PASS]/[WARN]/[FAIL]`，避免 Windows GBK 控制台崩溃

## 0.1.0 (2026-07-12)

### Added
- 初始版本
- 轨迹分析、回放、扫描功能
- 测试套件
- GitHub Actions CI 工作流
