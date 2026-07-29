# 风险登记（Risk Register）

项目负责人视角：trace-debugger 的**能力边界与上线前须知**。  
适用于对外说明、简历引用、集成评审。

| 编号 | 类别 | 当前等级 | 说明 |
|------|------|----------|------|
| R1 | 准确率 | 中 | 启发式非 ground truth |
| R2 | 数据安全 | 高（企业场景） | 记录含用户/工具内容，无内置治理 |
| R3 | 运行可靠性 | 中 | 本地 JSONL，非生产级存储 |
| R4 | 产品竞争 | 低–中 | 需坚持窄定位 |

---

## R1 — 准确率风险

### 描述

7 类失败检测均为**可配置启发式**，不是 LLM-as-Judge，也不是 ground truth。

`llm_offtrack` 尤其依赖：

- 查询与最终答案的**内容词重叠**
- 对「grounded 答案」（工具观测已支撑）的豁免规则
- 对短事实/含数字问答的特殊处理

### 易误判场景

| 场景 | 原因 |
|------|------|
| 跨语言（中问英答等） | 词表不重叠 |
| 摘要 / 改写 | 表述与 query 词面差异大 |
| 代码生成 | 关键词与 natural language query 重叠低 |
| 创意 / 开放式写作 | 「偏离」难以用词重叠衡量 |
| 时间 / 计算类短问答 | 曾出现假阳性（100 条真实轨迹报告中 `llm_offtrack` 偏高；后续 analyzer 已加 grounded/数字豁免，**规则仍需持续校准**） |

### 现有缓解

- 黄金集 27 条 + held_out 分栏 + CI 门禁（检测**回归**，非证明**正确**）
- `Analyzer(offtrack_overlap=...)`、`final_answer_markers` 等可配置
- 文档与报告统一标注「启发式 / 学习用途」

### 未做 / 后续

- [ ] 按任务类型（QA / 代码 / 创意）分配置或关闭 `llm_offtrack`
- [ ] 假阳性基准集（与 golden 负例分离）
- [ ] 与 llm-eval-engine Judge 的分工：规则门禁 + 抽样 Judge 复核

**对外表述建议**：引用 golden 通过率时，同时说明「held_out + 真实轨迹校准历史」；不把 `llm_offtrack` 计数当作业务 KPI。

---

## R2 — 数据安全风险

### 描述

`trace_debugger/record.py` 在 `--record` 或 `StepWatcher` 路径下会持久化：

| 字段 | 示例 |
|------|------|
| `query` | 用户原始问题（截断至 200 字符） |
| `thought` | Agent 思考全文写入事件 |
| `action_args` | 工具参数 |
| `observation` | 工具返回 |
| `context.*_preview` | 上述内容的可读预览 |

写入位置默认 `.tdebug/failures.jsonl`、`failures.log`、`sessions/{id}.md`。

### 当前缺口

- ❌ 无 PII / 密钥 / token 脱敏
- ❌ 无保留期限（TTL）与自动清理
- ❌ 无访问控制（文件系统权限依赖部署方）
- ❌ 无敏感字段过滤或分级记录

### 企业上线前必须（由集成方或后续版本承担）

1. **最小化**：只记录 failure 类型 + step 索引，不记录 thought/observation 全文
2. **脱敏**：接入方在 `StepEvent` / adapter 层 redact 后再调用 `FailureHarness`
3. **隔离**：`.tdebug/` 权限、gitignore、不进 CI  artifact
4. **合规**：保留周期、删除流程、审计策略

详见 [SECURITY.md](../SECURITY.md)。

---

## R3 — 运行可靠性风险

### 描述

当前存储模型：

```text
append_events() → failures.jsonl（追加写）
                 → failures.log（追加写）
                 → sessions/*.md（按会话写）
```

### 当前缺口

| 能力 | 状态 |
|------|------|
| 并发多进程追加 | ❌ 无文件锁 |
| 日志轮转 / 大小上限 | ❌ |
| 幂等消费 / 去重 | ❌（仅 StepWatcher 步级 dedupe） |
| 数据库 / 队列 | ❌ |
| 崩溃恢复 / 事务 | ❌ |

### 适用 / 不适用

| 场景 | 建议 |
|------|------|
| 本地开发、单机 Agent、CI golden | ✅ 合适 |
| 高并发生产 Agent、多副本写入同一 JSONL | ❌ 需外置存储或只离线 `tdebug scan` |

### 后续可选

- [ ] 可选 `fcntl`/portalocker 追加锁
- [ ] `--record` 轮转或按 session 分文件
- [ ] 导出到 OTel / 企业日志栈，本仓只做 analyzer

---

## R4 — 产品竞争风险

### 描述

LangSmith、Langfuse、Phoenix 等已覆盖 cloud tracing、eval、团队协作、生产监控。

### 本项目的可持续定位

坚持 **窄而深**，不扩张为完整 APM：

| 坚持 | 不做（短期） |
|------|----------------|
| 轻量、本地、无账号 | 云 SaaS 多租户 |
| 框架无关 + Format B | 绑定单一 Agent SDK |
| 规则门禁 + 可验证 golden | 全量 LLM Judge |
| 失败治理闭环（检测→记录→stats） | 分布式 trace 拓扑 |

**竞争策略**：与 react-agent / 自建 Harness **配套**；与 Langfuse 等 **互补**（本仓离线规则 + 对方生产 tracing），而非正面替代。

---

## 风险与版本

| 版本 | 说明 |
|------|------|
| 初版 | 2026-07-29，与 v0.2.2 能力对齐 |

变更本登记时请同步更新 [CHANGELOG.md](../CHANGELOG.md) 与 README「诚实边界」。
