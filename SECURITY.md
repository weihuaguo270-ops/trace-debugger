# Security Policy

## 报告漏洞

请邮件 **weihuaguo270@gmail.com**。  
勿在公开 Issue/PR 里贴真实轨迹、API Key 或用户对话。

---

## `--record` 会写什么

启用 `--record` 或 `StepWatcher` 时，失败事件写入 `.tdebug/`（JSONL、log、session md）。  
**可能包含**：用户 query、模型 thought、工具参数、工具返回。实现见 `trace_debugger/record.py`。

我们**当前不提供**自动脱敏、TTL、访问控制、传输加密——依赖部署方的目录权限与集成方在 adapter 层的 redact 策略。

| 场景 | 建议 |
|------|------|
| 个人 / 学习 | 默认即可；`.tdebug/` 不要 commit |
| CI | 只用 `fixtures/` 合成数据 |
| 团队 / 企业 | 先读 [docs/RISKS.md](docs/RISKS.md) §2；在 `StepEvent` 入 harness 前脱敏 |

集成方在调用 `FailureHarness` 或 `--record` 前，应自行决定：记多少、记多久、谁可读。

---

## 依赖

CI 跑 `pip-audit`。可选 JSON Schema 校验：`pip install 'trace-debugger[schema]'`。

风险与边界总览：[docs/RISKS.md](docs/RISKS.md)
