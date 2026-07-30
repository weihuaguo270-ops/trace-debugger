# held-out 首轮统计（2026-07-30）

**目的：** 在冻结 manifest 上建立 **能力轨 baseline**，后续 prompt/模型变更只对比 held-out，避免特化 dev 集。

**Manifest：** [capability_manifest.json](./capability_manifest.json)  
**快照：** [capability_held_out_run_20260730.json](./capability_held_out_run_20260730.json)  
**react-agent 轨迹目录：** `../react-agent/src/react_agent/trajectories`  
**trace-debugger：** v0.2.5 · 当前 analyzer

---

## 汇总

| 分集 | N | 含失败 session | fail_rate | distribution（路径级） |
|------|--:|---------------:|----------:|------------------------|
| **held-out** | 80 | **7** | **8.8%** | offtrack:2 · tool_error:5 · duplicate:3 |
| dev（对照） | 50 | 9 | 18.0% | offtrack:2 · tool_error:7 · duplicate:4 |
| no_mock baseline（试点） | 100 | 7 | 7.0% | tool_error:6 · no_answer:1 |

**解读：**

- held-out **8.8%** 与 no_mock 回归基线 **7%** 同量级——manifest 没有系统性偏「更难」或「更易」。  
- dev **18%** 更高，符合设计（dev 多 fail case 供调优，**不得**用 dev 数字当能力分）。  
- 80/80、50/50 文件均在磁盘，无缺失。

---

## held-out 7 条失败 session

| 文件 | failure_types | 步数 |
|------|---------------|-----:|
| `traj_20260713_113622_rdoh.json` | llm_offtrack | 4 |
| `traj_20260713_140901_bax8.json` | llm_offtrack | 4 |
| `traj_20260716_090523_71ag.json` | duplicate, tool_error | 4 |
| `traj_20260716_091135_opop.json` | duplicate, tool_error | 4 |
| `traj_20260716_091213_5mcs.json` | duplicate, tool_error | 3 |
| `traj_20260727_215701_pr0y.json` | tool_error | 7 |
| `traj_20260727_220426_46q8.json` | tool_error | 5 |

**聚类：** tool_error 路径 **5** · offtrack **2** · duplicate **3**（duplicate 均与 tool_error 共现）。

---

## 与回归轨的关系

| 轨道 | 基准 | 本轮 |
|------|------|------|
| 能力 held-out | **本文件**（8.8% / dist 如上） | 冻结对比点 |
| 回归 no_mock | [pilot_baseline_no_mock.json](../snapshots/pilot_baseline_no_mock.json) | 发版 compare |

合并前建议 **两个都看**：held-out fail_rate 不升 + regression delta 可接受。

---

## 复现

```bash
cd trace-debugger
python scripts/run_capability_eval.py
```

或：

```bash
python -c "
import json
from pathlib import Path
from trace_debugger.reader import load
from trace_debugger.analyzer import Analyzer

m = json.load(open('docs/pilot/capability_manifest.json', encoding='utf-8'))
traj = Path('../react-agent/src/react_agent/trajectories')
A = Analyzer()
for row in m['held_out']['trajectories']:
    t = load(str(traj / row['file']))
    a = A.analyze(t)
    fts = {ft for pa in a.paths for ft in pa.failure_types}
    if fts: print(row['file'], sorted(fts))
"
```

---

## 下一步（改 Agent 时）

1. **只在 dev(50) 上**改 prompt/tool，重跑 dev fail_rate  
2. 合并前重跑 held-out，对比本文件 **7/80** 与 distribution  
3. 发版前仍跑 `pilot_baseline_no_mock` compare  

**禁止：** 针对 held-out 7 个文件名做 targeted patch 后再测 held-out（泄漏）。

---

## 修订

| 日期 | 说明 |
|------|------|
| 2026-07-30 | 首轮 held-out + dev 统计 |
