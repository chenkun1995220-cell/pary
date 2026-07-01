# 统一每周结论报告设计

## 背景

当前项目已经拆分出美股、A股、港股三条每周筛选任务，并建立了自我分析、自动任务审计、周度运维总检查和运维历史摘要。现有问题是：候选公司、评分、目标价、建议买入价、风险说明和验收状态分散在多个文件中。每周任务结束后，用户仍需要手动打开多个目录，才能判断本周有哪些低估候选、候选理由是否完整、自动化是否可靠。

本设计新增一个只读的统一结论入口，把三市场候选结果和自动化验收状态合并成一份中文报告和一份结构化 JSON。它不抓取行情、不重新评分、不修改模型参数，只汇总本周已经生成的产物。

## 目标

1. 生成 `outputs/automation/latest_weekly_conclusion.md`，作为每周最终阅读入口。
2. 生成 `outputs/automation/latest_weekly_conclusion.json`，供后续自动任务、仪表盘或归档流程读取。
3. 汇总三市场候选数量、候选样例、评分、目标价、建议买入价、预期收益率、走势、置信度、风险理由和来源路径。
4. 合并 `latest_automation_check.json`、`latest_weekly_ops_check.json` 和 `latest_weekly_ops_history_summary.json`，让结论报告开头直接显示本周自动化状态。
5. 严守新鲜度边界：缺失、过期或字段不足时标记为 `needs_attention`，不把旧报告包装成本周结论。

## 非目标

- 不重新计算低估评分、目标价、趋势或风险说明。
- 不联网，不抓行情，不补财务数据。
- 不自动修改 `regional_fundamental_v2`、`valuation_trend_v1` 或任何影子参数。
- 不输出买卖指令；所有候选结论仍标记为研究筛选和人工复核用途。

## 输入

每个市场读取以下文件，文件不存在时该市场状态为 `missing`：

| 市场 | 目录 | 必读文件 | 可选增强文件 |
|---|---|---|---|
| 美股 | `outputs/us_universe` | `latest_run_summary.md`, `candidate_pool.csv`, `valuation_targets.csv`, `valuation_report.md`, `latest_investment_summary.md` | `performance_report.md`, `model_audit.md` |
| A股 | `outputs/cn_universe` | `latest_run_summary.md`, `candidate_pool.csv`, `valuation_targets.csv`, `valuation_report.md`, `latest_investment_summary.md` | `performance_report.md`, `model_audit.md` |
| 港股 | `outputs/hk_universe` | `latest_run_summary.md`, `candidate_pool.csv`, `valuation_targets.csv`, `valuation_report.md`, `latest_investment_summary.md` | `performance_report.md`, `model_audit.md` |

自动化状态读取：

- `outputs/automation/latest_automation_check.json`
- `outputs/automation/latest_weekly_ops_check.json`
- `outputs/automation/latest_weekly_ops_history_summary.json`

## 输出

### Markdown

`latest_weekly_conclusion.md` 包含以下章节：

1. `# 每周低估候选统一结论`
2. `## 自动化状态`
   - 本周日期
   - `automation_status`
   - `weekly_ops_status`
   - `weekly_ops_history_status`
   - 优先动作
3. `## 三市场候选概览`
   - 每个市场候选数量、候选样例、数据状态、来源路径
4. `## 候选公司摘要`
   - 统一展示市场、股票、公司、评分、目标价、建议买入价、预期收益率、趋势、置信度、风险理由
   - 每个市场默认展示前 10 个候选，JSON 保留完整候选列表
5. `## 风险与人工复核`
   - 汇总缺失文件、字段缺口、自动化未通过原因、候选风险说明缺口
6. `## 输出路径`
   - 列出关键输入和本报告输出路径
7. `## 边界`
   - 研究用途说明
   - 不构成投资建议
   - 不修改正式模型参数

### JSON

`latest_weekly_conclusion.json` 顶层结构：

```json
{
  "conclusion_schema": "weekly_conclusion",
  "conclusion_version": 1,
  "as_of_date": "2026-06-28",
  "status": "ready",
  "recommended_action": "monitor_next_run",
  "automation": {},
  "markets": [],
  "candidate_count_total": 0,
  "candidates": [],
  "missing_inputs": [],
  "warnings": [],
  "outputs": {}
}
```

`status` 规则：

- `ready`：三市场摘要可读，自动化总检查为可接受状态，候选字段达到最低展示要求。
- `needs_attention`：任一必读文件缺失、自动化总检查异常、候选字段缺失过多、验收日期过期或晚于当前日期。
- `missing`：统一结论无法读取任何市场候选或核心验收文件。

## 数据抽取规则

1. 候选数量优先来自 `candidate_pool.csv` 实际行数；若 CSV 缺失，再退回 `latest_run_summary.md` 中的候选数量文本，并标记警告。
2. 股票、公司、评分优先来自 `candidate_pool.csv`。
3. 目标价、建议买入价、预期收益率、趋势、估值置信度和风险理由优先从 `valuation_targets.csv` 与 `valuation_report.md` 合并读取。
4. 候选风险说明和质量缺口从 `latest_investment_summary.md` 抽取；抽不到时不编造风险理由，只写入缺口。
5. 同一市场内候选按现有候选池顺序保留，不重新排序。
6. 三市场之间默认按美股、A股、港股展示，不做跨市场投资排序。

## 新鲜度与失败边界

统一结论报告只认当前文件系统中的产物。它不会使用记忆中的候选列表，也不会把历史报告当成本周结论。

最低新鲜度规则：

- `latest_automation_check.json` 的 `as_of_date` 不得晚于当前日期。
- `latest_automation_check.json` 的 `as_of_date` 距当前日期不得超过 8 天。
- 市场候选文件的修改时间不作为单独失败条件，但会写入 JSON，供人工判断是否存在异常。
- 如果验收文件过期，报告仍可输出，但 `status` 必须是 `needs_attention`，并在顶部写明不能复用旧结论。

## 脚本入口

新增：

- `weekly_conclusion_report.py`
- `scripts/show_weekly_conclusion.ps1`

PowerShell 默认入口：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File F:\chatgptssd\project2\scripts\show_weekly_conclusion.ps1
```

默认输出：

- `outputs/automation/latest_weekly_conclusion.md`
- `outputs/automation/latest_weekly_conclusion.json`

## 自动任务接入

港股 14:45 收尾任务后续应在 `show_weekly_ops_history.ps1` 之后追加运行 `show_weekly_conclusion.ps1`。最终回复顺序调整为：

1. 周度运维总检查
2. 周度运维历史摘要
3. 统一每周结论报告摘要
4. 一屏验收结论和港股明细

如果统一结论报告失败，最终回复必须报告失败步骤、警告和最新日志，不得改用旧结论文件。

## 测试策略

新增测试文件：

- `tests/test_weekly_conclusion_report.py`

覆盖场景：

1. 三市场输入完整时生成 Markdown 和 JSON，状态为 `ready`。
2. 候选目标价和风险字段从候选池、估值文件和投资摘要中合并。
3. 缺失某市场必读文件时状态为 `needs_attention`，并记录 `missing_inputs`。
4. 验收日期过期或晚于当前日期时状态为 `needs_attention`。
5. CLI 能写出默认 JSON 和 Markdown。
6. PowerShell 脚本包含固定输出路径、Python 入口和 `-NoProfile -ExecutionPolicy Bypass` 使用约束。

文档测试补充：

- `docs/美股每周自动运行说明.md` 必须记录 `show_weekly_conclusion.ps1` 和两个输出路径。
- `codex_automation_audit.py` 后续应要求港股任务提示词包含 `show_weekly_conclusion.ps1`。

## 实施顺序

1. 写 `tests/test_weekly_conclusion_report.py` 的最小失败测试。
2. 实现 `weekly_conclusion_report.py` 的读入、合并和渲染。
3. 增加 `scripts/show_weekly_conclusion.ps1`。
4. 更新文档和静态契约测试。
5. 更新 Codex 自动任务审计和真实港股自动任务提示词。
6. 运行相关测试、全量测试和真实脚本验证。

## 完成标准

- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\show_weekly_conclusion.ps1` 能在当前工作区生成 Markdown 和 JSON。
- JSON 包含三市场候选数量、候选列表、自动化状态和缺失项。
- Markdown 能直接作为用户每周阅读入口。
- 全量测试通过。
- 真实港股收尾自动任务提示词包含统一结论脚本。
