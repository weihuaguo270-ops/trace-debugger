# 项目状态

- 版本基线：v0.6.0 failure-gate（2026-09-14 Unreleased 增量）
- 最近验证：黄金集 29 条、OpenAI/Anthropic adapter、`search_weak`、`--fail-on`
- 可声称：本地/CI 轨迹失败分类、baseline 对比、JSONL findings 导出
- 不能声称：生产 APM、云 tracing、自动修复、多租户
- P0：发布稳定版本并补 adapter 兼容矩阵与外部脱敏样例
- 验证：`python -m pytest tests/test_failure_golden.py`
