# 跨仓定位与分工

本文固定企业内部工作助手、受控变更交付和两个质量配件的对外边界。

## 一句话分工

| 项目 | 一句话定位 |
|---|---|
| work-assistant / react-agent | 企业内部工作助手，办理规范咨询和报销办理并产出轨迹 |
| change-delivery | 规划中的独立受控变更交付，读取 Issue、影子执行、审批后创建 Draft PR |
| trace-debugger | 轨迹失败雷达与 CI 钩子，输出确定性失败证据 |
| llm-eval-engine | 发版前自检，汇总过程/业务证据并输出 pass/review/hold |

## 推荐闭环

~~~
工作助手或受控变更交付产出轨迹
  → trace-debugger：规则失败打标、scan/compare、CI
  → llm-eval-engine：过程/业务证据与失败门
  → pass / review / hold
~~~

## 责任边界

| 问题 | 归属 |
|---|---|
| 规范咨询、报销办理、权限和人工审批 | work-assistant / react-agent |
| Issue 读取、影子执行、隔离测试、Draft PR | change-delivery 规划 |
| 工具报错、空检索、验收失败、审批拒绝等硬失败 | trace-debugger |
| 失败分布是否退化 | trace-debugger |
| 过程质量、Judge 校准、业务终态、性能和发布结论 | llm-eval-engine |

## 做 / 不做

### trace-debugger

做：Format B / Episode 读取、启发式失败标签、baseline、scan/compare、golden CI、findings 和 failure-gate 导出。
不做：Agent 运行时、业务终态、Judge 校准、Process Reward、最终 pass/review/hold、生产 APM、自动修复。

### llm-eval-engine

做：过程评分、动态 rubric、Eval Loop、人机校准、业务/性能证据汇总和 pass/review/hold。
不做：Agent 运行时、主 capability 数据集、tdebug 的规则失败检测器、线上 SLA 或独立评测 SaaS。

### change-delivery

做：读取 Issue、影子执行、人工审批后生成 Draft PR。
当前边界：只做文档计划，代码暂留 react-agent；不复制权限、轨迹或审批实现，不与工作助手两个场景并列宣传。

## 交接产物

| 产物 | 生产者 | 消费者 |
|---|---|---|
| Format B 轨迹 / Episode | work-assistant 或 change-delivery | 两个质量仓 |
| failures / findings / failure-gate | trace-debugger | llm-eval-engine |
| Process / business / release 报告 | llm-eval-engine | 负责人和 CI |

## 命名与简历边界

对外先讲工作助手应用，再讲质量配件。不要把 κ、黄金集数量、模型榜或离线门禁写成主产品名。

简历项目简介：

为企业内部工作助手和受控变更交付构建轨迹失败雷达与 CI 钩子。
将 Format B / Episode 轨迹转换为可解释的工具、检索、验收和审批失败信号。
提供 baseline、scan/compare、golden 回归、findings 导出和 verification_ref 追溯。
通过稳定 failure-gate 产物把规则层证据交给 llm-eval-engine 做过程/业务发布前自检。
当前证据来自本地 CI、黄金集和 external_real_sandbox，不等同生产 APM、线上 SLA 或自动修复系统。
