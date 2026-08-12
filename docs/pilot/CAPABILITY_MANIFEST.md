# 能力评估 Manifest（dev / held-out 分离）

**日期：** 2026-07-30  
**维护：** trace-debugger 试点

我们把 **「能力评估」** 和 **「失败治理回归」** 拆开，避免 Agent 变成「特化于 trajectories 日志的 Agent」。

---

## 问题：现有 445 条能否当能力考卷？

| 事实 | 含义 |
|------|------|
| 45 条 mock + 30/100 在主 baseline | 测集成证据，**不是** LLM 能力 |
| 7/13 单日 181 条 | 时间扎堆，不能代表长期分布 |
| 212/400 非 mock 带「相关记忆」前缀 | query 分布偏，易过拟合模板 |
| golden 27 | **analyzer 规则回归**，不是能力维度 |

**结论：** 全库不能直接当能力分；但经 **分层抽样 + 隔离 mock + dev/held-out 分离** 后，可支撑**有限度**的能力观测。

---

## 双轨制（与 trace-debugger 试点对齐）

| 轨道 | 数据集 | 指标 | 能否用来改 prompt |
|------|--------|------|-------------------|
| **A 能力** | 本文 held-out（80） | 任务成功率 / 答案质量（需另定义） | **禁止** |
| **B 开发** | 本文 dev（50） | 同上 + 单条复盘 | **允许** |
| **C 回归** | `pilot_baseline_no_mock` | fail_rate、distribution delta | compare 驱动，不刷题 |
| **D 规则** | golden 27 | 27/27 | 只改 analyzer |

```
改 prompt / 工具  →  只在 dev(50) 上迭代
合并前            →  跑 held-out(80)，只看不动
发版前            →  scan + compare no_mock baseline
改 analyzer       →  golden CI
```

---

## Manifest 文件

| 文件 | 说明 |
|------|------|
| [capability_manifest.json](./capability_manifest.json) | 完整元数据 + 80 held-out + 50 dev |
| [capability_held_out_files.txt](./capability_held_out_files.txt) | held-out 文件名列表 |
| [capability_dev_files.txt](./capability_dev_files.txt) | dev 文件名列表 |

**生成（可复现）：**

```bash
python scripts/build_capability_manifest.py
python scripts/run_capability_eval.py
```

**首轮结果：** [CAPABILITY_HELD_OUT_RUN.md](./CAPABILITY_HELD_OUT_RUN.md) — held-out **7/80（8.8%）** 冻结为能力轨 baseline。

参数：`SEED=20260730`，`HELD_OUT_N=80`，`DEV_N=50`，**排除全部 mock**，单日日期占比上限 **28%**。

---

## 抽样结果摘要（非 mock pool = 400）

### held-out（80 条）— 冻结，不参与调参

| 维度 | 分布 |
|------|------|
| 步数 | short 1–2: 50 · mid 3–4: 24 · long 5–6: 2 · long 7+: 4 |
|  outcome | pass: 73 · **fail: 7** |
| 日期 | 7/13: 22 · 7/16: 22 · 7/15: 13 · 其余分散 |
| 失败类型 | tool_error: 5 · duplicate: 3 · offtrack: 2 |

### dev（50 条）— 与 held-out **零重叠**

| 维度 | 分布 |
|------|------|
| 步数 | short: 31 · mid: 12 · long 5–6: 4 · long 7+: 3 |
| outcome | pass: 41 · **fail: 9** |
| 失败类型 | tool_error: 7 · duplicate: 4 · offtrack: 2 |

**刻意设计：** dev 里 **fail 占比更高**（9/50 vs 7/80），方便调 prompt/tool；held-out 更接近全库 pass 比例，减少「在失败题上过拟合」。

---

## 诚实边界

| 已改善 | 仍不足 |
|--------|--------|
| mock 隔离 | 无人工标注的「标准答案」 |
| dev/held-out disjoint | 记忆前缀仍占多数，外部效度有限 |
| 单日占比封顶 28% | 仍来自同一模型、同一环境 |
| 分层（步数 × pass/fail） | long 5–6 / 7+ 样本仍少（全库只有 24 条） |

**held-out 不能单独给出「通用 Agent 能力分」**——它给出的是：**在固定 manifest 上，这版相对上版有没有掉**（需你定义成功标准，见下）。

与 react-agent 自有 [capability_dataset.json](https://github.com/weihuaguo270-ops/react-agent/blob/main/src/react_agent/eval/capability_dataset.json) **互补**：那边是任务定义；这边是 **真实 trajectory 文件的 frozen manifest**。

---

## 成功标准（需团队补一层，manifest 不提供）

trace-debugger 只给 **failure_types**，不给「答案对不对」。能力评估建议二选一或并用：

| 级别 | 做法 |
|------|------|
| **L1 弱** | held-out 上 **fail_rate** 不升（与 regression 轨重叠，但 cohort 固定） |
| **L2 中** | 规则校验：数字题、是否含 FINAL ANSWER、tool 是否被调用 |
| **L3 强** | 人工或 llm-eval-engine 判任务成功（held-out 仅评测） |

**我们当前只正式支持 L1**；L2/L3 要在 react-agent eval 侧接。

---

## 推荐使用流程

### 1. 合并前 — held-out（只读）

```bash
# 对 manifest 内文件批量跑（示例：统计 failure 分布）
python -c "
import json
from pathlib import Path
from trace_debugger.reader import load
from trace_debugger.analyzer import Analyzer

manifest = json.load(open('docs/pilot/capability_manifest.json', encoding='utf-8'))
traj_dir = Path('../react-agent/src/react_agent/trajectories')
A = Analyzer()
fail = 0
for row in manifest['held_out']['trajectories']:
    t = load(str(traj_dir / row['file']))
    a = A.analyze(t)
    fts = {ft for pa in a.paths for ft in pa.failure_types}
    if fts: fail += 1
print('held-out fail', fail, '/', len(manifest['held_out']['trajectories']))
"
```

记录到 [METRICS_LOG.md](./METRICS_LOG.md)，**不得**根据结果回头改 dev 里的题。

### 2. 日常调优 — dev

- 失败 case 从 dev 9 条或 [capability_dev_files.txt](./capability_dev_files.txt) 里选  
- `tdebug <file>` 复盘 → 改 prompt/tool → **只在 dev 上重跑**验证  

### 3. 发版 — regression（与 Phase 2 相同）

```bash
python scripts/build_pilot_scan.py --exclude-mock -n 100 \
  --json-out docs/snapshots/pilot_latest_no_mock.json
# compare pilot_baseline_no_mock.json
```

**三者同时看：** held-out 不恶化 + dev 改善 + regression delta 可接受。

---

## 防止特化 Agent 的铁律

1. **held-out 文件名不得进入 prompt / few-shot / 测试脚本里的「修复列表」**  
2. **不得**为了 held-out 降 fail 而改 analyzer 阈值（那是轨道 D）  
3. **baseline 更新**必须写 METRICS_LOG 理由（intentional 改进 vs 刷绿）  
4. mock 轨迹 **永不**进入 capability manifest（已排除；请迁到独立目录）  
5. 对外只报 **held-out + regression** 两个数，不混 golden CI

---

## 何时重生成 manifest

- trajectories 全库换模型 / 换 prompt 体系（大版本）  
-  deliberate 扩充 long 多步场景后，要提高 5–6 / 7+ 步配额  

小改动 **不要**重抽 held-out，否则失去纵向可比性。

---

## 关联

| 文档 | 链接 |
|------|------|
| 回归 baseline | [BASELINE.md](./BASELINE.md) |
| 试点总览 | [README.md](./README.md) |
| 价值与边界 | [VALUE.md](../VALUE.md) |

---

## 修订

| 日期 | 说明 |
|------|------|
| 2026-07-30 | 初版；80 held-out + 50 dev，seed 固定 |
