# Security Policy

## 报告安全问题

小工具项目。安全问题请邮件 **weihuaguo270@gmail.com**。  
**请勿**在公开 Issue/PR 中粘贴真实轨迹、API Key 或用户数据。

---

## 数据处理说明

trace-debugger 会在启用 `--record` 或 `StepWatcher` 时，将失败相关事件写入本地文件（默认 `.tdebug/`）：

- `failures.jsonl` — 机器可读事件
- `failures.log` — 人类可读文本
- `sessions/{session_id}.md` — 会话摘要

事件可能包含：**用户 query、模型 thought、工具参数、工具 observation 预览**。  
实现见 `trace_debugger/record.py`（`step_failure_event`、`build_failure_context`、`append_events`）。

### 当前版本不提供

- 自动脱敏（PII、密钥、token）
- 保留期限（TTL）与自动删除
- 访问控制（依赖操作系统文件权限）
- 传输加密（纯本地文件）

### 部署建议

| 环境 | 建议 |
|------|------|
| 个人 / 学习 | 默认即可；`.tdebug/` 已建议 gitignore |
| 团队 / 企业 | 集成前阅读 [docs/RISKS.md](docs/RISKS.md) R2；在 adapter 层 redact；限制目录权限；定义保留与删除策略 |
| CI | 只用 `fixtures/` 合成数据；勿上传真实 failures.jsonl |

### 集成方责任

在调用 `FailureHarness.after_observation()` 或 `--record` 之前，由 Agent 运行时决定：

1. 是否记录 thought / observation 全文
2. 是否在 `StepEvent` 中预先脱敏
3. 日志目录权限与生命周期

---

## 依赖与安全更新

- CI 运行 `pip-audit`（见 `.github/workflows/test.yml`）
- 可选严格 JSON 校验：`pip install 'trace-debugger[schema]'`

完整风险登记：[docs/RISKS.md](docs/RISKS.md)
