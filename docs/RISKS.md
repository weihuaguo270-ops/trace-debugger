# 风险与边界说明

本文档记录 **trace-debugger 当前版本（v0.2.x）** 我们在对外集成、写简历、做评审时必须讲清楚的事。  
不是功能清单，是**已知局限与已做决策**。

---

## 项目声明（先说结论）

**我们做什么**

- 读 Agent 轨迹 JSON（Format B），用**可验证的启发式规则**标记常见失败模式
- 本地 CLI + JSONL 记录 + 黄金集 CI 门禁
- 任意 Harness 可通过 `StepEvent` adapter 接入，不绑具体框架

**我们刻意不做**

- 不做云 tracing / 多租户 SaaS
- 不做 LLM-as-Judge 内置执行
- 不做生产级高并发日志管道
- 不承诺检测结果就是 ground truth

**当前版本适合谁**

- 本地开发、学习栈、单机 Agent、CI 规则回归  
- **不适合**直接当作企业线上告警或合规审计的唯一依据

---

## 1. 准确率：规则有用，但不是判决

### 我们怎么检测「跑偏」

`llm_offtrack` 用的是**查询与答案的内容词重叠**（可调 `Analyzer(offtrack_overlap=...)`），外加几条豁免：工具观测 grounded、短事实问答含数字等。  
这是**便宜、可复现**的门禁，不是语义理解。

### 真实教训（2026-07）

我们用 react-agent 本地 **100 条轨迹**跑过一轮分布周报。当时 `llm_offtrack` 报了 **6 次**，其中不少是「现在几点了？」「100/7 等于多少」这类**其实答对了**的短问答——属于规则假阳性，不是 Agent 真跑偏。

我们随后改了 analyzer（grounded 观测豁免、短事实+数字跳过），同批重扫后 offtrack **6→1**。  
这件事说明两件事：

1. 规则要跟着真实数据改，不能只靠合成 golden  
2. **即使改过，也不能把 offtrack 计数当业务 KPI**

### 我们仍担心误判的场景

跨语言（中问英答）、摘要改写、代码生成、开放式写作——词重叠本来就不能衡量「是否答对」。  
这类任务要么关掉 offtrack，要么交给 llm-eval-engine 做 Judge 抽样，我们不在本仓假装能判。

### 已采取的缓解

- 黄金集 27 条 + held_out 分栏：防**代码改坏**，不证明**永远正确**
- 检测器参数可配置（overlap、final_answer_markers、search_tool_names）
- 所有周报和 README 统一写「启发式」

### 后续若继续做

按任务类型分配置（QA / 代码 / 创意）；单独建假阳性基准集；与 eval 栈分工——**规则拦明显问题，Judge 抽复杂 case**。  
暂无时间表，取决于有没有真实使用反馈。

---

## 2. 数据安全：`--record` 会落盘敏感内容

### 事实

启用 `--record` 或 `StepWatcher` 时，`trace_debugger/record.py` 会把失败事件写到 `.tdebug/`，其中包括：

- 用户 `query`（截断 200 字，但仍可能是敏感问题）
- 模型 `thought`（**全文**）
- 工具 `action_args`、`observation`

可读 log 和 session Markdown 里也会有 preview。

### 我们的决策

**当前版本不做内置脱敏、TTL、访问控制。**  
原因：各团队合规要求差太多，我们在 adapter 层留扩展点，比在本仓硬编码一套「假安全」更诚实。

### 集成方必须自己做（企业场景）

1. 在 `StepEvent` 进 `FailureHarness` **之前** redact  
2. 或只记录 `failure_type + step_index`，不记 thought/observation 全文  
3. `.tdebug/` 目录权限、gitignore、保留周期、删除流程——由部署环境负责  

个人学习场景：默认行为即可；**不要把真实用户 failures.jsonl 提交进 Git 或 CI artifact**。

细节见 [SECURITY.md](../SECURITY.md)。

---

## 3. 运行可靠性：本地 JSONL，不是日志基础设施

### 事实

`append_events()` 对 `failures.jsonl` 做**追加写**，无文件锁、无轮转、无队列、无事务。  
StepWatcher 只在步级做了重复写入 dedupe，**扛不住**多进程/多副本同时写同一文件。

### 我们的决策

**v0.2.x 定位就是单机开发与 CI**，不冒充生产 observability backend。  
要高并发生产 tracing，请接 Langfuse / 自建日志栈 / OTel——本仓继续只做**离线分析与规则门禁**，或集成方把 JSONL 当中间产物再 ingest。

### 若以后补

文件锁、按 session 分文件、导出 hook——视实际需求再开 issue，不提前做 APM。

---

## 4. 竞争与定位：窄才能活

LangSmith、Langfuse、Phoenix 等已经把 cloud tracing、团队协作、eval 平台做很深了。  
我们如果也往「全功能 APM」走，会以学习项目的资源正面对打，不划算。

**我们选择的缝**：轻量、本地、框架无关、Format B 契约、规则 + golden 可验证。  
和 react-agent 是**参考集成**，不是父子关系；和 Langfuse 等是**互补**——他们收生产 trace，我们收离线失败治理与 CLI 复盘。

扩张前会先问：有没有破坏「无账号、可 git 验证、adapter 一行映射」这三条。有，就不做。

---

## 文档维护

| 日期 | 说明 |
|------|------|
| 2026-07-29 | 初版，对齐 v0.2.3；R1 案例来自 2026-07 真实轨迹批次 |

改检测逻辑或 record 字段时，请同步改本文与 README「诚实边界」。
