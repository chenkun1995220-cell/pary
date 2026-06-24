# US Membership Evidence Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local, auditable S&P 500 historical membership evidence pack that can upgrade verified official events while preserving conservative backtest quality gates.

**Architecture:** Extend `backtest_membership_inputs.py` so it can optionally read a CSV evidence pack, validate events through `historical_sp500.py`, and use those events to produce weekly membership evidence levels. Keep the default behavior unchanged when no evidence pack is present. Wire the PowerShell orchestrator to pass the default evidence pack path only when the file exists.

**Tech Stack:** Python standard library CSV/date handling, existing `historical_sp500.py` validation helpers, PowerShell, `unittest`, UTF-8 BOM CSV outputs.

---

## File Structure

- Modify: `backtest_membership_inputs.py`
  - Add optional evidence pack loading.
  - Apply evidence events to active universe rows before writing weekly membership.
  - Preserve existing `--max-companies` and no-pack behavior.
- Modify: `scripts/run_us_point_in_time_backtest.ps1`
  - Define `data\config\us_sp500_membership_evidence.csv`.
  - Print the evidence pack path/status.
  - Pass `--evidence-pack` to `backtest_membership_inputs.py` only when the file exists.
- Modify: `tests/test_backtest_membership_inputs.py`
  - Add tests for official verified events, unofficial downgrade, missing pack fallback, and invalid pack failure.
- Modify: `tests/test_weekly_automation.py`
  - Assert the orchestrator exposes and conditionally passes the evidence pack path.
- Modify: `docs/美股每周自动运行说明.md`
  - Document evidence pack purpose, fields, and conservative source rules.

## Task 1: Evidence Pack Parsing In Membership Builder

**Files:**
- Modify: `tests/test_backtest_membership_inputs.py`
- Modify: `backtest_membership_inputs.py`

- [ ] **Step 1: Write failing test for official verified evidence**

Append this test to `BacktestMembershipInputsTests`:

```python
    def test_evidence_pack_official_source_can_upgrade_membership(self):
        rows = [
            {
                "ticker": "NEW",
                "cik": "1",
                "company_name": "New Co",
                "industry": "Technology",
                "gics_sub_industry": "Software",
                "date_added": "2025-01-01",
                "enabled": "1",
            },
            {
                "ticker": "OLD",
                "cik": "2",
                "company_name": "Old Co",
                "industry": "Technology",
                "gics_sub_industry": "Hardware",
                "date_added": "2020-01-01",
                "enabled": "1",
            },
        ]
        evidence_rows = [
            {
                "effective_date": "2025-01-01",
                "added_ticker": "NEW",
                "removed_ticker": "OLD",
                "membership_evidence": "verified",
                "membership_source_url": "https://www.spglobal.com/spdji/en/index-announcements/article",
            }
        ]

        membership = build_backtest_membership(
            rows,
            weeks=1,
            end_date="2025-01-03",
            evidence_rows=evidence_rows,
        )

        by_ticker = {row["ticker"]: row for row in membership}
        self.assertEqual(by_ticker["NEW"]["membership_evidence"], "verified")
        self.assertEqual(by_ticker["NEW"]["membership_source_url"], evidence_rows[0]["membership_source_url"])
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_backtest_membership_inputs.BacktestMembershipInputsTests.test_evidence_pack_official_source_can_upgrade_membership -v
```

Expected: `FAIL` or `ERROR` because `build_backtest_membership()` does not accept `evidence_rows`.

- [ ] **Step 3: Implement minimal evidence application**

In `backtest_membership_inputs.py`, import existing event normalization:

```python
from historical_sp500 import restore_membership
```

Change the function signature:

```python
def build_backtest_membership(
    universe_rows,
    weeks=156,
    end_date=None,
    market="US",
    evidence="secondary",
    source_url="data/config/us_universe_symbols.csv",
    company_limit=0,
    evidence_rows=None,
):
```

Create this helper above `build_backtest_membership()`:

```python
def _current_membership_map(active_rows, evidence, source_url):
    current = {}
    for row in active_rows:
        current[row["ticker"]] = {
            "ticker": row["ticker"],
            "company_name": row.get("company_name", ""),
            "effective_date": row.get("date_added", ""),
            "membership_evidence": evidence,
            "membership_source_url": source_url,
            "_source_row": row,
        }
    return current
```

Inside the week loop, replace the direct active row iteration with:

```python
        if evidence_rows:
            current = _current_membership_map(active_rows, evidence, source_url)
            week_members = restore_membership(current, evidence_rows, week)
            week_rows = []
            active_by_ticker = {row["ticker"]: row for row in active_rows}
            for ticker, restored in sorted(week_members.items()):
                source = restored.get("_source_row") or active_by_ticker.get(ticker, {})
                if not source:
                    continue
                week_rows.append((source, restored))
        else:
            week_rows = []
            for row in sorted(active_rows, key=lambda item: item["ticker"]):
                added = _iso_date(row.get("date_added"), "date_added")
                if added <= week_date:
                    week_rows.append((row, {
                        "effective_date": row.get("date_added", ""),
                        "membership_evidence": evidence,
                        "membership_source_url": source_url,
                    }))
```

Then build output rows from `week_rows`:

```python
        for row, restored in week_rows:
            output.append(
                {
                    "week": week,
                    "market": str(market).upper(),
                    "ticker": row["ticker"],
                    "cik": row["cik"],
                    "company_name": row.get("company_name", ""),
                    "industry": row.get("industry", ""),
                    "gics_sub_industry": row.get("gics_sub_industry", ""),
                    "date_added": row.get("date_added", ""),
                    "effective_date": restored.get("effective_date", row.get("date_added", "")),
                    "membership_evidence": restored.get("membership_evidence", evidence),
                    "membership_source_url": restored.get("membership_source_url", source_url),
                    "available_at": week,
                }
            )
```

- [ ] **Step 4: Run test and confirm pass**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_backtest_membership_inputs.BacktestMembershipInputsTests.test_evidence_pack_official_source_can_upgrade_membership -v
```

Expected: `OK`.

- [ ] **Step 5: Add downgrade and fallback tests**

Add:

```python
    def test_evidence_pack_unofficial_verified_source_is_downgraded(self):
        rows = [
            {"ticker": "NEW", "cik": "1", "company_name": "New Co", "industry": "Tech", "gics_sub_industry": "Software", "date_added": "2025-01-01", "enabled": "1"},
            {"ticker": "OLD", "cik": "2", "company_name": "Old Co", "industry": "Tech", "gics_sub_industry": "Hardware", "date_added": "2020-01-01", "enabled": "1"},
        ]
        evidence_rows = [
            {
                "effective_date": "2025-01-01",
                "added_ticker": "NEW",
                "removed_ticker": "OLD",
                "membership_evidence": "verified",
                "membership_source_url": "https://example.com/not-official",
            }
        ]

        membership = build_backtest_membership(rows, weeks=1, end_date="2025-01-03", evidence_rows=evidence_rows)

        by_ticker = {row["ticker"]: row for row in membership}
        self.assertEqual(by_ticker["NEW"]["membership_evidence"], "secondary")

    def test_missing_evidence_pack_keeps_secondary_default(self):
        rows = [
            {"ticker": "AAPL", "cik": "320193", "company_name": "Apple Inc.", "industry": "Technology", "gics_sub_industry": "Hardware", "date_added": "2020-01-01", "enabled": "1"},
        ]

        membership = build_backtest_membership(rows, weeks=1, end_date="2025-01-03")

        self.assertEqual(membership[0]["membership_evidence"], "secondary")
```

- [ ] **Step 6: Run membership tests**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_backtest_membership_inputs -v
```

Expected: all tests in `tests.test_backtest_membership_inputs` pass.

- [ ] **Step 7: Commit Task 1**

```powershell
git add backtest_membership_inputs.py tests/test_backtest_membership_inputs.py
git commit -m "Add membership evidence pack application"
```

## Task 2: Evidence Pack File Loading And CLI

**Files:**
- Modify: `tests/test_backtest_membership_inputs.py`
- Modify: `backtest_membership_inputs.py`

- [ ] **Step 1: Write failing test for CSV evidence pack file loading**

Add:

```python
    def test_prepare_membership_reads_evidence_pack_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            universe = root / "universe.csv"
            evidence_pack = root / "evidence.csv"
            output = root / "membership.csv"
            write_csv(
                universe,
                [
                    {"ticker": "NEW", "cik": "1", "company_name": "New Co", "industry": "Tech", "gics_sub_industry": "Software", "date_added": "2025-01-01", "enabled": "1"},
                    {"ticker": "OLD", "cik": "2", "company_name": "Old Co", "industry": "Tech", "gics_sub_industry": "Hardware", "date_added": "2020-01-01", "enabled": "1"},
                ],
            )
            write_csv(
                evidence_pack,
                [
                    {
                        "effective_date": "2025-01-01",
                        "added_ticker": "NEW",
                        "removed_ticker": "OLD",
                        "membership_evidence": "verified",
                        "membership_source_url": "https://www.spglobal.com/spdji/en/index-announcements/article",
                        "notes": "official fixture",
                    }
                ],
            )

            result = prepare_backtest_membership(
                universe,
                output,
                weeks=1,
                end_date="2025-01-03",
                evidence_pack=evidence_pack,
            )

            loaded = list(csv.DictReader(output.open(encoding="utf-8-sig", newline="")))
            self.assertEqual(result["rows"], 1)
            self.assertEqual(loaded[0]["ticker"], "NEW")
            self.assertEqual(loaded[0]["membership_evidence"], "verified")
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_backtest_membership_inputs.BacktestMembershipInputsTests.test_prepare_membership_reads_evidence_pack_file -v
```

Expected: `ERROR` because `prepare_backtest_membership()` does not accept `evidence_pack`.

- [ ] **Step 3: Implement evidence pack loading**

Add helper:

```python
def _read_optional_csv(path):
    if not path:
        return []
    evidence_path = Path(path)
    if not evidence_path.exists():
        return []
    return _read_csv(evidence_path)
```

Change signature:

```python
def prepare_backtest_membership(
    universe_config,
    output,
    weeks=156,
    end_date=None,
    market="US",
    company_limit=0,
    evidence_pack=None,
):
```

Pass rows:

```python
        evidence_rows=_read_optional_csv(evidence_pack),
```

In `main()`, add:

```python
    parser.add_argument("--evidence-pack")
```

and pass:

```python
        evidence_pack=args.evidence_pack,
```

- [ ] **Step 4: Run evidence file test**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_backtest_membership_inputs.BacktestMembershipInputsTests.test_prepare_membership_reads_evidence_pack_file -v
```

Expected: `OK`.

- [ ] **Step 5: Add invalid CSV evidence test**

Add:

```python
    def test_invalid_evidence_pack_fails_before_writing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            universe = root / "universe.csv"
            evidence_pack = root / "evidence.csv"
            output = root / "membership.csv"
            write_csv(
                universe,
                [
                    {"ticker": "NEW", "cik": "1", "company_name": "New Co", "industry": "Tech", "gics_sub_industry": "Software", "date_added": "2025-01-01", "enabled": "1"},
                    {"ticker": "OLD", "cik": "2", "company_name": "Old Co", "industry": "Tech", "gics_sub_industry": "Hardware", "date_added": "2020-01-01", "enabled": "1"},
                ],
            )
            write_csv(
                evidence_pack,
                [
                    {
                        "effective_date": "bad-date",
                        "added_ticker": "NEW",
                        "removed_ticker": "OLD",
                        "membership_evidence": "verified",
                        "membership_source_url": "https://www.spglobal.com/spdji/en/index-announcements/article",
                    }
                ],
            )

            with self.assertRaisesRegex(ValueError, "effective_date|ISO|YYYY-MM-DD"):
                prepare_backtest_membership(
                    universe,
                    output,
                    weeks=1,
                    end_date="2025-01-03",
                    evidence_pack=evidence_pack,
                )

            self.assertFalse(output.exists())
```

- [ ] **Step 6: Run membership tests and compile**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_backtest_membership_inputs -v
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m py_compile backtest_membership_inputs.py
```

Expected: tests pass and compile command exits 0.

- [ ] **Step 7: Commit Task 2**

```powershell
git add backtest_membership_inputs.py tests/test_backtest_membership_inputs.py
git commit -m "Load membership evidence pack input"
```

## Task 3: Orchestrator Wiring

**Files:**
- Modify: `tests/test_weekly_automation.py`
- Modify: `scripts/run_us_point_in_time_backtest.ps1`

- [ ] **Step 1: Write failing static contract test**

In `test_point_in_time_backtest_script_static_contract`, add:

```python
        self.assertIn("us_sp500_membership_evidence.csv", script)
        self.assertIn("EvidencePack", script)
        self.assertIn("--evidence-pack", script)
```

- [ ] **Step 2: Run static contract test and confirm failure**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_automation.WeeklyAutomationTests.test_point_in_time_backtest_script_static_contract -v
```

Expected: `FAIL` because script does not mention the evidence pack yet.

- [ ] **Step 3: Wire evidence pack in PowerShell**

In `scripts/run_us_point_in_time_backtest.ps1`, after `$UniverseConfig`, add:

```powershell
$EvidencePack = Join-Path $ProjectRoot "data\config\us_sp500_membership_evidence.csv"
```

Add status print:

```powershell
Write-Host "EvidencePack: $EvidencePack"
Write-Host "EvidencePackReady: $((Test-Path -LiteralPath $EvidencePack))"
```

Before calling `backtest_membership_inputs.py`, build argument list:

```powershell
  $membershipArgs = @(
    "-B", "backtest_membership_inputs.py",
    "--universe-config", $UniverseConfig,
    "--output", $HistoricalMembership,
    "--weeks", "$membershipWeeks",
    "--market", "US",
    "--max-companies", "$MaxCompanies"
  )
  if (Test-Path -LiteralPath $EvidencePack) {
    $membershipArgs += @("--evidence-pack", $EvidencePack)
  }
  & $Python @membershipArgs
```

Remove the old direct `& $Python -B backtest_membership_inputs.py ...` call.

- [ ] **Step 4: Run static and dry-run tests**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_automation.WeeklyAutomationTests.test_point_in_time_backtest_script_static_contract tests.test_weekly_automation.WeeklyAutomationTests.test_point_in_time_backtest_dry_run_prints_ordered_pipeline_without_writing_outputs -v
```

Expected: both tests pass.

- [ ] **Step 5: Run script dry run manually**

Run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File scripts\run_us_point_in_time_backtest.ps1 -OutputRoot C:\tmp\codex_us_pit_evidence_dryrun -PilotWeeks 2 -MaxCompanies 3 -SecUserAgent "Pary chenkun1995220@qq.com" -DryRun
```

Expected: exit 0, output includes `EvidencePack` and no files are created at `C:\tmp\codex_us_pit_evidence_dryrun`.

- [ ] **Step 6: Commit Task 3**

```powershell
git add scripts/run_us_point_in_time_backtest.ps1 tests/test_weekly_automation.py
git commit -m "Wire membership evidence pack into backtest script"
```

## Task 4: Documentation And End-To-End Verification

**Files:**
- Modify: `docs/美股每周自动运行说明.md`

- [ ] **Step 1: Update documentation**

Add this paragraph under the “美股严格时点回测” section:

```markdown
历史成分证据包可放在 `data/config/us_sp500_membership_evidence.csv`。字段为 `effective_date, added_ticker, removed_ticker, membership_evidence, membership_source_url, notes`。只有官方 S&P Global HTTPS 来源可保持 `verified`；非官方来源即使写入 `verified` 也会自动降级为 `secondary`。证据包缺失时，脚本仍按当前股票池生成 `secondary` 名单，仅用于机械试跑。
```

- [ ] **Step 2: Run full test suite**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 3: Run compile and whitespace checks**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m py_compile backtest_membership_inputs.py historical_sp500.py us_weekly_replay.py
git diff --check
```

Expected: compile exits 0; `git diff --check` exits 0 except acceptable CRLF warnings.

- [ ] **Step 4: Run small real smoke test without evidence pack**

Run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File scripts\run_us_point_in_time_backtest.ps1 -OutputRoot C:\tmp\codex_us_pit_evidence_smoke -Years 1 -PilotWeeks 2 -MaxCompanies 3 -SecUserAgent "Pary chenkun1995220@qq.com"
```

Expected: exit 0; 3/3 price coverage; 2 completed weeks; manifest still lists `membership_not_verified` because no real evidence pack exists yet.

- [ ] **Step 5: Inspect outputs**

Run:

```powershell
Get-Content -Path C:\tmp\codex_us_pit_evidence_smoke\backtest_report.md -Encoding UTF8
Get-Content -Path C:\tmp\codex_us_pit_evidence_smoke\replay_manifest.csv -Encoding UTF8
git status --short --branch
```

Expected: report exists; manifest has completed rows; working tree contains only intended source/doc changes.

- [ ] **Step 6: Commit Task 4**

```powershell
git add docs/美股每周自动运行说明.md
git commit -m "Document membership evidence pack workflow"
```

- [ ] **Step 7: Push main**

```powershell
git push origin main
```

Expected: `main` is pushed and `git rev-list --left-right --count main...origin/main` returns `0 0`.

## Self-Review Checklist

- Spec coverage: The plan covers evidence file fields, official source downgrade, missing pack fallback, invalid pack errors, PowerShell wiring, docs, and smoke verification.
- Completeness scan: All implementation details are explicit.
- Type consistency: The plan consistently uses `evidence_rows`, `evidence_pack`, `membership_evidence`, and `membership_source_url`.
- Scope check: The plan does not implement network scraping, model upgrades, or quality gate loosening.
