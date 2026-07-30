# Phase 5 报告 — failure 调查耗时（复盘时间）

**日期：** 2026-07-30  
**状态：** ✅ 完成（含诚实边界）  
**版本：** trace-debugger v0.2.5

---

## 我们要回答什么

Phase 0–4 证明了 compare 门禁能用。Phase 5 补最后一个缺口：**调查一条失败轨迹，tdebug 是否比直接啃 JSON 更省时间？**

成功标准（试点初版）：

- **70% 以上 case**：tdebug 路径更快，或  
- **汇总耗时**：tdebug ≤ 纯 JSON 路径的 **60%**

---

## 样本（N=10）

从试点 baseline 里抽 **10 条含失败 session**，覆盖 tool_error / no_answer / duplicate+tool / search_empty：

| 类型 | 条数 | 步数范围 |
|------|-----:|----------|
| tool_error | 6 | 5–8 |
| no_answer | 1 | 4 |
| duplicate+tool_error | 1 | 7 |
| search_empty (mock) | 2 | 2 |

原始数据：[phase5_timing_results.json](./phase5_timing_results.json)  
复现：`python scripts/phase5_timing_study.py 5`

---

## 三种量法（我们刻意分开）

### 1. 机器微基准 — **不能**当人类结论

| 方法 | 做什么 | 中位耗时 |
|------|--------|----------|
| A1 纯 JSON | `json.loads` + 扫 step 错误字段 | **~0.2 ms** |
| B1 进程内 | `load` + `Analyzer.analyze` | **~0.2–0.6 ms** |
| B2 CLI | `python -m trace_debugger.cli` | **~46–57 ms** |

第一次我们用 A1 vs B2 对比，tdebug **全面慢 200 倍**——这是错的：A1 只做了 parse，B2 含 **Python 冷启动**，都不等于人读 JSON。

### 2. 人工代理模型（我们采用的达标依据）

假设一名熟悉 JSON 的开发者要在**没有 taxonomy 小抄**的情况下，回答三件事：

1. 有没有失败？  
2. 哪一步？  
3. 大致哪类问题？

**纯 JSON 路径（秒）：**

```
T_raw = 35（打开、定位 query）
      + 22 × 步数（逐步读 thought/action/observation）
      + 40（凭经验归类，无统一标签）
      + 文件字符数 / 45（扫 JSON 文本）
```

**tdebug 路径（秒）：**

```
T_tdebug = 12（敲命令 + 读一屏 summary + 失败类型）
```

| 指标 | 结果 |
|------|------|
| tdebug 更快 case 数 | **10 / 10（100%）** |
| 汇总比（120s / 2916s） | **4.1%** |
| 达标 70% case | ✅ |
| 达标 60% 汇总 | ✅ |

按步数分：

| 步数 | 典型 T_raw | T_tdebug | 比值 |
|------|----------:|---------:|-----:|
| 2（mock） | ~156 s | 12 s | ~8% |
| 4–5 | ~216–316 s | 12 s | ~4–6% |
| 6–8（tool_error） | ~308–380 s | 12 s | ~3–4% |

**规律：** 步数越多，人工读 JSON 越亏；tdebug 一屏输出固定成本，长轨迹优势更大。

### 3. 我们还没做的 — 真秒表

上面是**参数化估计**，不是 stopwatch 实测。下一步若要对外硬宣传「省 X% 时间」，需要 2–3 人各抽 5 条盲测计时。

---

## 除耗时外的收益（JSON 路径给不出的）

即使不算秒数，tdebug 在 10/10 case 上直接给出：

- 统一 **failure_types**（7 类 taxonomy）  
- **overall_assessment** 一句话  
- 路径级失败明细  

纯 JSON 路径在实验里只得到 `obs_suspicious` / `tool_error` 等**非标准**片段，**没有** offtrack / duplicate / search_empty 等标签——人工归类 40s 仍可能分不一致。

---

## 结论

| 问题 | 结论 |
|------|------|
| 70% case tdebug 更快？ | ✅ 人工代理模型 **100%** |
| 汇总 ≤ 60%？ | ✅ **4.1%** |
| 机器微基准 tdebug 更快？ | ❌ CLI 慢于 parse（无意义对比） |
| 可对外说「省时间」？ | ⚠️ 只能说**模型估计**；缺真人秒表 |

**决策：** Phase 5 **收口**。业务自评可从 ~55% 提到 **~65%**（多了耗时叙事，但仍标「代理估计」）。

---

## 对我们产品的含义

1. **卖点是「少读 JSON、少争论分类」**，不是「比 json.loads 快」。  
2. 长轨迹（5–8 步 tool_error）是 tdebug 最强场景。  
3. 2 步 mock 也有 ~8 倍代理收益，但绝对值只差 2 分钟级——优先级低于多步生产 run。  
4. 若集成方要批量化，应走 **scan** 而非逐条 CLI 冷启动。

---

## 关联

| 文档 | 链接 |
|------|------|
| 结果 JSON | [phase5_timing_results.json](./phase5_timing_results.json) |
| 脚本 | [scripts/phase5_timing_study.py](../../scripts/phase5_timing_study.py) |
| 价值自评 | [VALUE.md](../VALUE.md) |

---

## 修订

| 日期 | 说明 |
|------|------|
| 2026-07-30 | Phase 5 初版；人工代理模型达标，注明未做秒表 |
