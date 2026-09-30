# 根因判对率评测（Adjudication）

**目的：** 回答「analyzer 报出来的失败根因，有多少是对的」。这是本仓唯一需要**人工独立判断**
才能得到的数字——规则不能给自己打分。

**读者：** 质量/测试负责人。标注者须**未参与规则编写**。

---

## 为什么必须盲评

标注表（sheet）里**不含** analyzer 的判定，判定单独存在 key 文件，评分时才合并。
若标注者先看到 analyzer 的结论，得到的是一致性而不是正确性——那是确认，不是测量。

---

## 流程

### 1. 生成盲评表

```bash
tdebug adjudicate <轨迹目录> 50 \
  --sheet-out .tdebug/adjudication/sheet.jsonl \
  --key-out   .tdebug/adjudication/key.jsonl
```

默认写入 `.tdebug/adjudication/`（已在 `.gitignore` 内）。表中含原始 query / observation，
**不要提交进 git**；对外分享前按 [SECURITY.md](../../SECURITY.md) 脱敏。

### 2. 人工标注（唯一的人工步骤）

逐行读 `query` / `final_answer` / `steps`，填写 `human_label`：

- 留空 `[]` = 该轨迹**没有**失败
- 有失败则填类型，多个用逗号分隔：
  `tool_error` · `acceptance_failed` · `approval_denied` · `incomplete_stream` · `search_empty` ·
  `search_weak` · `search_timeout` · `llm_offtrack` · `context_overflow` · `duplicate` · `no_answer`
- `human_note` 写一句理由（评分时用来区分「未标注」与「已判为无失败」）

判定口径与 README 一致：只看**硬失败信号**，不做语义质量评判。例如「答案文风不好」不算失败，
「工具调用返回了错误」算。

### 3. 评分

```bash
tdebug adjudicate --score \
  --sheet .tdebug/adjudication/sheet.jsonl \
  --key   .tdebug/adjudication/key.jsonl \
  --json-out .tdebug/adjudication/report.json
```

输出四项：

| 指标 | 含义 |
|------|------|
| **根因判对率** | 标签集合与人工**完全一致**的用例占比（严格口径） |
| **有无失败一致率** | 只比「有失败 / 无失败」，不含类型 |
| **按类型 precision / recall** | precision = 报出来的有多少是对的（假阳性看这里） |
| **分歧清单** | `analyzer_false_positive` / `analyzer_miss` / `type_mismatch` |

---

## 数字出来之后怎么用

| 发现 | 动作 |
|------|------|
| 某类型 precision 低（误报多） | 误报用例落进 `fixtures/failure_fp/`，再改规则 / 加豁免 / 换 `--task-type` |
| 某类型 recall 低（漏报多） | 补 `fixtures/failure_golden/` 负例 |
| 分歧集中在某类 query | 参照 [THRESHOLDS.md](./THRESHOLDS.md) 考虑关掉该信号，或交给下游 Judge |

所有改动仍须过 `--require-verification`：修完根因要能指到回归锁。

---

## 诚实边界

- **单人标注不是 κ**：这里只产出「与一位标注者的一致率」，不做人机校准（κ/MAE 属
  [llm-eval-engine](../POSITIONING_AND_DIVISION.md)）
- **标注者须独立**：由规则作者自评会系统性高估
- **样本量**：<30 条只能当线索；要下结论建议每类型 ≥10 条
- golden 夹具的期望标签来自 analyzer 交叉验证，**不能**当作本评测的 ground truth
- 目前**尚无真实判对率数字**——需要在真实轨迹上跑完上述 1–3 步
