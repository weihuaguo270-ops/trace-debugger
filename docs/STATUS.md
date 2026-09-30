# 项目状态

## 定位与边界

本地 Agent 轨迹失败检测与 CI 规则回归工具：负责发现并输出失败证据，不负责最终发布裁决。
不宣称生产 APM、云 tracing、自动修复或多租户平台。

## 当前

- 版本基线：v0.6.0 failure-gate（2026-09-14 Unreleased 增量）
- 最近验证：黄金集 32 条、OpenAI/Anthropic adapter、`search_weak`、`--fail-on`
- 可声称：本地/CI 轨迹失败分类、baseline 对比、JSONL findings 导出
- 不能声称：生产 APM、云 tracing、自动修复、多租户
- 证据摘要：黄金集 32 条（11 类 taxonomy 全覆盖）；OpenAI/Anthropic adapter 与结构化失败信号；baseline 对比 / findings 导出 / `--fail-on` CI 门禁

## P0

发布稳定版本，并补 adapter 兼容矩阵与外部脱敏样例。

## 验证

```bash
pytest tests/test_failure_golden.py -q
```

完整本地验证命令与受限 runner 说明见 [CONTRIBUTING.md](../CONTRIBUTING.md)。
