# 项目状态

## 定位与边界

本地 Agent 轨迹失败检测与 CI 规则回归工具：负责发现并输出失败证据，不负责最终发布裁决。
不宣称生产 APM、云 tracing、自动修复或多租户平台。

## 当前

- 版本基线：v0.6.0 failure-gate（Unreleased 增量至 2026-09-30）
- 最近验证：黄金集 **32** 条（26 golden / 6 held_out，11 类 taxonomy 全覆盖）；每条 finding 可指到 `verification_ref` 回归锁（`--require-verification` 已进 CI 门禁）；`tdebug adjudicate` 盲评标注/评分可用（**尚无独立第二标注者，因此不给根因判对率数字**）；`looks_cross_language` 跨语言假阳性豁免（FP 集 7 条）
- 可声称：本地/CI 轨迹失败分类、baseline 对比、JSONL findings 导出、逐条 finding 的机器可校验回归锁
- 不能声称：生产 APM、云 tracing、自动修复、多租户；**检测准确率**（需独立人工标注，协议见 [pilot/ADJUDICATION.md](pilot/ADJUDICATION.md)）
- 证据摘要：黄金集 32 条（11 类全覆盖）+ 假阳性集 7 条；`verification_ref` 回归锁与夹具漂移守卫；baseline 对比 / findings 导出 / `--fail-on` / `--require-verification`

## P0

发布稳定版本，并补 adapter 兼容矩阵与外部脱敏样例。

## 验证

```bash
pytest tests/test_failure_golden.py -q
```

完整本地验证命令与受限 runner 说明见 [CONTRIBUTING.md](../CONTRIBUTING.md)。
