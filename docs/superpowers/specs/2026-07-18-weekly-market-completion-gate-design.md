# 三市场周任务完成屏障设计

## 目标

在统一周度收口开始前，可靠确认美股、A股和港股市场任务均已在同一自然日成功完成。上游仍在运行、已经失败、状态过期、摘要缺失或候选数量不一致时，收口必须在生成任何新治理产物前保守停止，并输出精确问题代码。

该功能只治理自动化执行顺序和运行证据，不抓取行情、不重新评分、不修改候选结果，也不修改正式模型 `valuation_trend_v1`。

## 当前问题

三个市场脚本已经分别使用 Windows 命名互斥锁，能够阻止同一市场重复运行，但统一收口只在链路后段通过产物一致性复核发现问题。

因此仍存在以下风险：

- 港股完成后，美股或A股任务仍在运行，收口提前读取正在变化的文件。
- 上游本周失败，但旧的同日或旧周摘要仍存在，收口无法区分最新尝试状态。
- 收口先生成部分治理产物，随后才因三市场日期或候选数不一致失败。
- 手工补跑覆盖 `latest_run_summary.md` 后，失败尝试与成功尝试缺少统一的结构化状态。

## 方案比较

### 方案一：只在收口前检查摘要日期

读取三个 `latest_run_summary.md`，要求 `Run time` 为当天。

优点是改动小；缺点是不能区分任务仍在运行、最新尝试失败或旧的同日成功摘要，因此不能满足无人值守运行的可靠性要求。

### 方案二：检查命名互斥锁和摘要日期

收口进程尝试获取美股和A股互斥锁，再检查摘要日期。

优点是可以发现当前进程仍在运行；缺点是互斥锁只存在于本机当前会话，无法保留失败状态，也不便于跨平台单元测试和后续审计。

### 方案三：持久化市场运行状态并设置收口屏障

每个市场任务原子写入 `running`、`ready` 或 `failed` 状态。统一收口第一步读取三个状态文件，并交叉核对摘要和候选文件。

该方案能够区分运行中、失败和成功状态，具备稳定问题代码和可测试接口，因此采用方案三。

## 运行状态契约

每个市场输出目录新增 `latest_run_state.json`，固定字段如下：

- `run_state_schema=weekly_market_run_state`
- `run_state_version=1`
- `market=US|CN|HK`
- `status=running|ready|failed`
- `as_of_date=YYYY-MM-DD`
- `run_started_at`
- `run_completed_at`
- `summary_path`
- `candidate_path`
- `log_path`
- `failure_step`
- `failure_message`
- `formal_model_change_allowed=false`

状态写入必须使用同目录临时文件加原子替换，避免收口读取半截 JSON。

### 状态转换

1. 市场脚本取得现有互斥锁并创建日志后，写入 `running`。
2. 市场筛选、预测跟踪、审计、投资摘要和 `latest_run_summary.md` 全部成功后，写入 `ready`。
3. 任一步骤抛出异常时，在保留原失败日志的同时写入 `failed`。
4. 港股的 `ready` 表示港股市场任务本身完成；统一治理收口结果继续由现有交付和提交前复核产物表示。
5. 同日补跑可以覆盖同一市场状态，但不得增加连续周六计数。

## 收口屏障

新增独立的 Python 模块和 PowerShell 包装脚本。统一收口在执行 `run_self_analysis` 前先运行该屏障。

屏障要求：

- 三个 `latest_run_state.json` 均存在且结构合法。
- 三个状态均为 `ready`。
- `as_of_date` 均等于屏障日期，且三市场日期唯一。
- 状态中的市场、摘要路径和候选路径与固定市场目录匹配。
- 摘要存在，`Run time` 日期等于状态日期。
- 摘要候选数等于候选 CSV 实际行数。
- 三个市场的候选数之和可被结构化输出。

屏障输出：

- `outputs/automation/latest_weekly_market_completion_gate.json`
- `outputs/automation/latest_weekly_market_completion_gate.md`

顶层字段至少包括：

- `gate_schema=weekly_market_completion_gate`
- `gate_version=1`
- `as_of_date`
- `status=ready|blocked`
- `market_count`
- `ready_market_count`
- `candidate_count_total`
- `markets`
- `issues`
- `formal_model_change_allowed=false`

## 稳定问题代码

问题代码采用小写英文，至少覆盖：

- `us_run_state_missing`
- `cn_run_state_invalid`
- `hk_run_status_running`
- `us_run_status_failed`
- `market_run_date_mismatch`
- `cn_run_state_stale`
- `hk_summary_missing`
- `us_summary_date_mismatch`
- `cn_candidate_pool_missing`
- `hk_candidate_count_mismatch`
- `run_state_path_mismatch`

状态为 `blocked` 时，包装脚本返回非零退出码；统一收口立即停止，不执行任何后续治理步骤。

## 集成边界

- 保留现有三个市场命名互斥锁，不用状态文件替代进程互斥。
- 保留现有 `weekly_artifact_consistency` 作为完整交付后的深度复核。
- 完成屏障只验证市场任务是否可进入收口，不验证后续周结论、交付检查或提交前复核。
- `DryRun` 只展示将写入状态和将执行屏障，不创建状态文件。
- 不更改三个市场的计划时间和筛选参数。

## 测试与验收

### 单元测试

- 三个同日 `ready` 状态、摘要和候选文件一致时返回 `ready`。
- 任一状态为 `running` 或 `failed` 时返回 `blocked` 和精确问题代码。
- 状态文件缺失、损坏、未来日期或非当天日期时保守阻断。
- 三市场日期不一致时阻断。
- 摘要日期、候选数量或固定路径不一致时阻断。
- 输出始终保持 `formal_model_change_allowed=false`。

### 脚本契约测试

- 三个市场脚本均在开始、成功和失败路径更新运行状态。
- `run_weekly_reporting_bundle.ps1` 的第一个执行步骤为完成屏障。
- 屏障失败时不得出现 `run_self_analysis` 的执行输出。
- `DryRun` 不创建任何文件。

### 回归测试

- 现有市场脚本静态契约、周度收口顺序和三市场产物一致性测试继续通过。
- 全量测试通过。

## 不在本次范围

- 自动重排美股、A股和港股计划时间。
- 自动重新运行失败市场。
- 修改候选筛选、估值、预测或审计参数。
- 修复人工复核队列重复项。
- 提交或清理当前两个本地数据文件改动。
