# 价值说明

**读者：** 项目负责人、质量负责人、集成评审  
**用途：** 说明 trace-debugger 对谁有用、我们证明到哪一步、还缺什么——不是功能说明书。

---

## 一句话

> trace-debugger 是面向中小型 Agent 团队的本地失败治理工具：把难读的执行轨迹变成可统计、可复盘、可进 CI 的失败信号。

---

## 我们已经有把握的（功能约 80%）

### 解决什么问题

Agent 跑挂之后，轨迹散在 JSON 里，难分类、难汇总、难在发版前说清「有没有变差」。

### 谁在用、关心什么

| 角色 | 关心点 |
|------|--------|
| Agent 开发 | 哪一步、哪类失败 |
| 质量 / 测试 | 版本间失败分布是否变差 |
| 项目负责人 | 有没有证据支撑发版 / 暂缓，而不是口头感觉 |

### 相对完整 APM 的差异

- 本地、轻量，JSON/JSONL 即可，无云账号
- Format B + adapter，不绑框架
- 规则可解释、可 git 验证，不依赖 LLM Judge
- golden 27 条 + 扫描快照 + `--compare`，结果可审计

### 边界

我们只做失败检测与治理信号，**不**自动修 Agent，**不**替代 Langfuse / LangSmith 类生产观测。

---

## 主场景（我们对外只推这一条）

**Agent 回归测试与失败治理门禁**

```
轨迹 JSON → 7 类失败标签 → JSONL / log 记录
    → 发版前 scan + --compare baseline
    → CI golden 27 条
```

调试、StepWatcher、Judge prompt 都有，但**简历和 README 先讲门禁**，其余折叠。

---

## 业务价值证明（2026-07-30 自评）

### 已经站得住的

- Format B 打标签、报告、JSONL 记录 — 黄金集 27/27 + CI
- react-agent 100 条轨迹上做过 offtrack 校准（6→1，见 [RISKS.md](./RISKS.md)）
- **react-agent 试点 Phase 0–5**（[pilot/README.md](./pilot/README.md)）：
  - 冻结 baseline + no_mock；Run A/B；[决策案例](./cases/regression_gate_20260730.md)
  - [Phase 5 耗时](./pilot/PHASE5.md)：10 条失败轨迹，人工代理模型 10/10 tdebug 更快（待秒表）

### 还没有数据支撑的

| 问题 | 状态 |
|------|------|
| 复盘耗时降了多少 | ⚠️ [Phase 5 人工代理模型](./pilot/PHASE5.md) 10/10 更快；**缺真人秒表** |
| 接入后 Agent 失败率是否下降 | 没做 |
| 真实生产 PR 被 hold | 只有试点案例；案例 B 是模拟 |
| 比 grep JSON 省多少人力 | 同上，代理估计非实测 |

**自评：** 功能 ~80%，场景 ~75%，业务量化 ~**65%**（Phase 0–5 收口；耗时为模型估计，PR hold 仍缺生产记录）。

---

## 选型（我们怎么跟集成方讲）

**适合：** 有本地 JSON 轨迹、要低成本建 taxonomy + baseline + CI 门禁、接受启发式规则的团队。

**不适合：** 要分布式 trace、多租户大盘、或把本工具当唯一 observability 后端的团队。

与 Langfuse / Phoenix：**互补**，不是替换。

---

## 接下来做什么

试点 Phase 0–5 已收口。剩余：

1. **真人秒表**（可选）
2. **held-out 成功标准 L2/L3**（接 react-agent eval）
3. 真实 PR hold 案例
4. `tdebug scan --exclude-model mock`

**能力 / 回归分离：** [CAPABILITY_MANIFEST.md](./pilot/CAPABILITY_MANIFEST.md)

**案例与数据：** [cases/regression_gate_20260730.md](./cases/regression_gate_20260730.md) · [pilot/METRICS_LOG.md](./pilot/METRICS_LOG.md)

---

## 修订

| 日期 | 说明 |
|------|------|
| 2026-07-29 | 初版；主定位定为回归门禁 |
| 2026-07-30 | 试点 Phase 0–5、案例、自评 65%（Phase 5 代理耗时） |
| 2026-07-30 | v0.2.5：改项目负责人口吻 |
