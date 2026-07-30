# 回归门禁案例模板

复制本文件为 `regression_gate_YYYYMMDD.md`，填写下列章节。  
案例用于对外说明「发版前 compare → 决策」闭环，须**诚实**标注模拟/真实。

---

## 元信息

| 字段 | 值 |
|------|-----|
| 案例 ID | `regression_gate_YYYYMMDD` |
| 日期 | YYYY-MM-DD |
| 项目 | react-agent / 其他 |
| 类型 | `真实拦截` / `假阳性纠正` / `模拟演练` |
| 决策 | `pass` / `review` / `hold` / `fix` |

---

## 1. 背景

- 计划发版 / 合并的变更是什么？
- 谁发起 compare？触发点（PR / 发版 checklist）？

---

## 2. 对比配置

| 字段 | 值 |
|------|-----|
| baseline 快照 | `docs/snapshots/...` |
| current 快照 | `docs/snapshots/...` |
| N | |
| 选取规则 | latest_by_mtime / no_mock / 固定文件集 |

---

## 3. compare 结果（数据）

| 失败类型 | baseline | current | delta |
|----------|----------:|--------:|------:|
| | | | |

含失败 session：___ / N（___%）→ ___ / N（___%），**delta ___pp**

---

## 4. 门禁判定（THRESHOLDS v1）

| 规则 | 是否触发 | 说明 |
|------|----------|------|
| A | | |
| B | | |
| C | | |

---

## 5. 团队决策

- 最终决策：
- 理由（引用数据，非主观）：
- 后续动作：

---

## 6. 脱敏证据

- 链接：`docs/snapshots/...`（不含原始 query 全文）
- 可引用的 session_id / 文件名（可选）

---

## 7. 复盘

- 本案例证明什么？
- 若重来会改进什么？
