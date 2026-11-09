# trace-debugger：轨迹失败雷达与 CI 钩子

trace-debugger 是企业内部工作助手（work-assistant）及未来受控变更交付（change-delivery）共用的质量配件。它读取 Agent 轨迹，发现确定性的失败信号，做 scan/compare 和 CI 回归；不负责最终发版裁决。

## 一句话定位

把工作助手或交付助手产生的 Format B / Episode 轨迹，转换成可解释、可统计、可进 CI 的失败证据。

## 做什么 / 不做什么

| 做什么 | 不做什么 |
|---|---|
| 工具报错、空检索、验收失败、审批拒绝、半截流和重复调用等规则打标 | 不做生产 APM、云 tracing 或多租户观测大盘 |
| baseline、scan --compare、golden CI 和 findings 导出 | 不执行最终 pass/review/hold 发布裁决 |
| 为 llm-eval-engine 提供 failure-gate 输入和复盘线索 | 不做 Judge 校准、Process Reward 或自动修复 |

当前证据是本地/CI 失败治理原型。黄金集和 external_real_sandbox 用于验收，不能写成生产团队接入或线上 SLA。

## 在工作助手闭环中的位置

~~~
工作助手或 change-delivery 产出轨迹
  → trace-debugger：失败打标、scan/compare、CI
  → llm-eval-engine：过程/业务证据与 pass/review/hold
~~~

- react-agent / work-assistant：产生规范咨询、报销办理及受控执行轨迹。
- trace-debugger：提供便宜、确定、可回归的失败信号。
- llm-eval-engine：消费失败门和业务/过程证据，输出最终发布前结论。

两个质量仓保持独立，也可被 change-delivery 编排进 CI；不会合并成一个交付仓。

## 主路径

~~~bash
pip install -e .
tdebug scan trajectories/ 50 --json-out snapshots/latest.json --compare snapshots/baseline.json --fail-on hold --findings-out snapshots/latest_findings.json --require-verification --project-root .
python -m pytest tests/test_failure_golden.py
~~~

输入是 Format B 轨迹 JSON；输出是失败标签、分布表、回归 diff 和 findings。

## 项目命名与边界

| 名称 | 角色 |
|---|---|
| 企业内部工作助手 / work-assistant | 主应用，负责规范咨询和报销办理 |
| 受控变更交付 / change-delivery | 规划中的独立应用，负责 Issue 到 Draft PR 的受控流程 |
| trace-debugger | 本仓，轨迹失败雷达与 CI 钩子 |
| llm-eval-engine | 姊妹仓，发版前自检并输出 pass/review/hold |

本仓不复制 Agent 运行时、审批或业务终态实现，也不把自己包装为评测 SaaS。

## 简历项目简介

为企业内部工作助手和受控变更交付构建轨迹失败雷达与 CI 钩子。
将 Format B / Episode 轨迹转换为可解释的工具、检索、验收和审批失败信号。
提供 baseline、scan/compare、golden 回归、findings 导出和 verification_ref 追溯。
通过稳定 failure-gate 产物把规则层证据交给 llm-eval-engine 做过程/业务发布前自检。
当前证据来自本地 CI、黄金集和 external_real_sandbox，不等同生产 APM、线上 SLA 或自动修复系统。

## 进一步阅读

- 当前状态：docs/STATUS.md
- 跨仓分工：docs/POSITIONING_AND_DIVISION.md
- 价值与证据：docs/VALUE.md
- 集成契约：docs/INTEGRATIONS.md
