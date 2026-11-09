# 项目状态

## 产品定位与边界

trace-debugger 是企业内部工作助手（work-assistant）和规划中的受控变更交付（change-delivery）共用的轨迹失败雷达与 CI 钩子。它负责规则失败打标、scan/compare、golden 回归和 findings 导出，不负责最终发版裁决。

llm-eval-engine 消费本仓 failure-gate 与业务/过程证据，输出 pass/review/hold。本仓仍是本地/CI 失败治理原型，不是生产 APM、云 tracing、自动修复或多租户平台。

## 项目命名与边界

| 名称 | 角色 |
|---|---|
| 企业内部工作助手 / work-assistant | 产生规范咨询和报销办理轨迹的主应用 |
| 受控变更交付 / change-delivery | 规划中的独立应用，暂不拆仓 |
| trace-debugger | 本仓，失败信号和 CI 回归 |
| llm-eval-engine | 姊妹仓，发版前自检和最终 pass/review/hold |

## 简历项目简介

为企业内部工作助手和受控变更交付构建轨迹失败雷达与 CI 钩子。
将 Format B / Episode 轨迹转换为可解释的工具、检索、验收和审批失败信号。
提供 baseline、scan/compare、golden 回归、findings 导出和 verification_ref 追溯。
通过稳定 failure-gate 产物把规则层证据交给 llm-eval-engine 做过程/业务发布前自检。
当前证据来自本地 CI、黄金集和 external_real_sandbox，不等同生产 APM、线上 SLA 或自动修复系统。

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
