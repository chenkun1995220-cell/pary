# 三市场周任务完成屏障实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为美股、A股、港股周任务增加可审计的原子运行状态，并在统一周度收口生成任何治理产物前阻断运行中、失败、过期或相互矛盾的市场批次。

**Architecture:** 使用独立的 `weekly_market_run_state.py` 负责原子状态写入，使用 `weekly_market_completion_gate.py` 负责读取三个固定市场状态并交叉核对摘要与候选文件。三个市场 PowerShell 入口只负责在开始、成功和失败路径调用状态写入器；统一收口将完成屏障作为第一个关键步骤。

**Tech Stack:** Python 3 标准库、Windows PowerShell 5.1、`unittest`、JSON、CSV。

## Global Constraints

- 正式筛选模型和估值模型参数不得修改。
- 状态和屏障产物固定 `formal_model_change_allowed=false`。
- 不允许缓存回退被视为市场任务成功。
- `DryRun` 不写文件、不访问网络。
- 保留现有命名互斥锁和完整产物一致性复核。
- 不修改当前未提交的 `data/config/us_sp500_current_membership_sources.csv`。
- 不修改当前未提交的 `data/samples/hk_universe_companies.csv`。

---

### Task 1: 原子市场运行状态

**Files:**
- Create: `weekly_market_run_state.py`
- Create: `tests/test_weekly_market_run_state.py`

**Interfaces:**
- Produces: `write_market_run_state(output, market, status, run_started_at, run_completed_at="", summary_path="", candidate_path="", log_path="", failure_step="", failure_message="") -> dict`
- Produces CLI arguments: `--output`, `--market`, `--status`, `--run-started-at`, `--run-completed-at`, `--summary-path`, `--candidate-path`, `--log-path`, `--failure-step`, `--failure-message`

- [ ] **Step 1: Write failing tests for schema, transitions and atomic replacement**

```python
def test_writes_ready_state_with_hard_safety_boundary(self):
    payload = write_market_run_state(
        output,
        "US",
        "ready",
        "2026-07-18 14:05:00",
        run_completed_at="2026-07-18 14:08:00",
        summary_path=str(summary),
        candidate_path=str(candidates),
        log_path=str(log),
    )
    self.assertEqual(payload["run_state_schema"], "weekly_market_run_state")
    self.assertEqual(payload["status"], "ready")
    self.assertEqual(payload["as_of_date"], "2026-07-18")
    self.assertFalse(payload["formal_model_change_allowed"])
    self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["status"], "ready")

def test_rejects_invalid_market_status_or_missing_failure_message(self):
    with self.assertRaisesRegex(ValueError, "market_invalid"):
        write_market_run_state(output, "EU", "running", "2026-07-18 14:05:00")
    with self.assertRaisesRegex(ValueError, "failure_message_required"):
        write_market_run_state(output, "US", "failed", "2026-07-18 14:05:00")
```

- [ ] **Step 2: Run the state tests and confirm RED**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_market_run_state -v
```

Expected: fail because `weekly_market_run_state` does not exist.

- [ ] **Step 3: Implement validation and atomic JSON writing**

Implementation must:

```python
RUN_STATE_SCHEMA = "weekly_market_run_state"
RUN_STATE_VERSION = 1
MARKETS = {"US", "CN", "HK"}
STATUSES = {"running", "ready", "failed"}

def _atomic_write_json(path, payload):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)
```

Validation must reject invalid market/status, invalid start timestamp, `ready` without completion timestamp, and `failed` without failure message. `as_of_date` is derived from `run_started_at`.

- [ ] **Step 4: Run state tests and confirm GREEN**

Use the Step 2 command. Expected: all tests pass.

- [ ] **Step 5: Commit Task 1**

```powershell
git add weekly_market_run_state.py tests/test_weekly_market_run_state.py
git commit -m "feat: persist weekly market run state"
```

### Task 2: 收口前完成屏障

**Files:**
- Create: `weekly_market_completion_gate.py`
- Create: `scripts/run_weekly_market_completion_gate.ps1`
- Create: `tests/test_weekly_market_completion_gate.py`

**Interfaces:**
- Consumes: `outputs/<market>/latest_run_state.json`, `latest_run_summary.md`, `candidate_pool.csv`
- Produces: `build_weekly_market_completion_gate(project_root=".", as_of_date=None) -> dict`
- Produces: `render_weekly_market_completion_gate(payload) -> str`
- Produces CLI output JSON and Markdown; exit code `0` only when `status=ready`

- [ ] **Step 1: Write failing ready and blocked gate tests**

```python
def test_ready_requires_three_same_day_completed_markets(self):
    root = make_project(statuses={"US": "ready", "CN": "ready", "HK": "ready"})
    payload = build_weekly_market_completion_gate(root, "2026-07-18")
    self.assertEqual(payload["status"], "ready")
    self.assertEqual(payload["ready_market_count"], 3)
    self.assertEqual(payload["candidate_count_total"], 6)
    self.assertEqual(payload["issues"], [])

def test_running_or_failed_market_blocks_with_stable_issue(self):
    root = make_project(statuses={"US": "failed", "CN": "ready", "HK": "running"})
    payload = build_weekly_market_completion_gate(root, "2026-07-18")
    self.assertEqual(payload["status"], "blocked")
    self.assertIn("us_run_status_failed", payload["issues"])
    self.assertIn("hk_run_status_running", payload["issues"])
```

Also cover missing/invalid state, stale/future date, market/date/path mismatch, missing summary/candidate file, summary date mismatch and candidate count mismatch.

- [ ] **Step 2: Run gate tests and confirm RED**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_market_completion_gate -v
```

Expected: fail because the gate module does not exist.

- [ ] **Step 3: Implement fixed-market gate and report writers**

Use fixed paths:

```python
MARKETS = {
    "US": "us_universe",
    "CN": "cn_universe",
    "HK": "hk_universe",
}
```

Each market result must expose market, status, as-of date, run timestamps, summary count, candidate count, state/summary/candidate paths and issues. Top-level status is `ready` only when all market issue lists and global issues are empty.

- [ ] **Step 4: Implement PowerShell wrapper**

Wrapper behavior:

```powershell
param(
  [string]$ProjectRoot = "",
  [string]$AsOfDate = (Get-Date -Format "yyyy-MM-dd"),
  [switch]$DryRun
)
```

`DryRun` prints the gate plan and exits zero without creating files. Normal execution calls the Python module with output paths under `outputs\automation` and propagates its exit code.

- [ ] **Step 5: Run gate tests and wrapper dry-run**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_market_completion_gate -v
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\run_weekly_market_completion_gate.ps1 -DryRun
```

Expected: tests pass; dry-run returns zero and does not write outputs.

- [ ] **Step 6: Commit Task 2**

```powershell
git add weekly_market_completion_gate.py scripts/run_weekly_market_completion_gate.ps1 tests/test_weekly_market_completion_gate.py
git commit -m "feat: gate weekly closure on market completion"
```

### Task 3: 接入三个市场入口和统一收口

**Files:**
- Modify: `scripts/run_us_universe_weekly.ps1`
- Modify: `scripts/run_cn_weekly.ps1`
- Modify: `scripts/run_hk_weekly.ps1`
- Modify: `scripts/run_weekly_reporting_bundle.ps1`
- Modify: `tests/test_weekly_automation.py`

**Interfaces:**
- Consumes: Task 1 CLI state writer
- Consumes: Task 2 PowerShell gate wrapper
- Produces: each market's `latest_run_state.json`

- [ ] **Step 1: Write failing static contract tests**

Add tests asserting every market script contains:

```python
self.assertIn("weekly_market_run_state.py", script)
self.assertIn('"running"', script)
self.assertIn('"ready"', script)
self.assertIn('"failed"', script)
self.assertIn('"latest_run_state.json"', script)
```

Add a bundle-order test asserting `run_weekly_market_completion_gate` is the first item in `$postSteps` and appears before `run_self_analysis`.

- [ ] **Step 2: Run targeted automation tests and confirm RED**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_automation -v
```

Expected: new contract tests fail because scripts do not yet write state or invoke the gate.

- [ ] **Step 3: Integrate state transitions into each market script**

For each script:

- Define `latest_run_state.json`, summary and candidate paths before the `try`.
- After acquiring the mutex and creating the log, invoke state writer with `running`.
- After writing `latest_run_summary.md`, invoke state writer with `ready`.
- In `catch`, invoke state writer with `failed`, preserving the original exception as the pipeline failure.
- State-writer failure must never hide the original market failure.
- Dry-run remains before state creation.

- [ ] **Step 4: Make gate the first critical bundle step**

The first `$postSteps` row must be:

```powershell
@{ Label = "run_weekly_market_completion_gate"; Script = "run_weekly_market_completion_gate.ps1"; Critical = $true }
```

The existing fail-closed loop will stop before `run_self_analysis` when the gate exits nonzero.

- [ ] **Step 5: Run targeted automation and gate tests**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_market_run_state tests.test_weekly_market_completion_gate tests.test_weekly_automation -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 3**

```powershell
git add scripts/run_us_universe_weekly.ps1 scripts/run_cn_weekly.ps1 scripts/run_hk_weekly.ps1 scripts/run_weekly_reporting_bundle.ps1 tests/test_weekly_automation.py
git commit -m "feat: guard weekly closure with market states"
```

### Task 4: 文档、回归与完成核验

**Files:**
- Modify: `docs/美股每周自动运行说明.md`
- Modify: `docs/提交前复核清单.md`

**Interfaces:**
- Documents the new state and gate artifacts without changing model governance.

- [ ] **Step 1: Document operator behavior**

Document:

- three market state files and their status meanings;
- the gate as the first closure step;
- stable blocked reason examples;
- same-day rerun behavior;
- no trade/model-change boundary.

- [ ] **Step 2: Run focused tests**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_market_run_state tests.test_weekly_market_completion_gate tests.test_weekly_automation tests.test_weekly_artifact_consistency -v
```

Expected: all focused tests pass.

- [ ] **Step 3: Run the full suite**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests -v
```

Expected: zero failures and zero errors.

- [ ] **Step 4: Verify source boundaries and worktree scope**

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors; pre-existing data modifications remain untouched and outside the feature commits.

- [ ] **Step 5: Commit Task 4**

```powershell
git add docs/美股每周自动运行说明.md docs/提交前复核清单.md
git commit -m "docs: describe weekly market completion gate"
```

- [ ] **Step 6: Push verified commits**

Push the implementation branch only after all tests pass and the final diff contains no unrelated files.
