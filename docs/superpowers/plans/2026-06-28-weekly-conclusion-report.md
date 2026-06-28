# Weekly Conclusion Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only weekly conclusion entry point that combines US, CN, and HK screening outputs with automation checks into one Chinese Markdown report and one JSON payload.

**Architecture:** Add a focused Python module that reads existing artifacts, normalizes market candidates, validates freshness, and renders Markdown/JSON without fetching data or changing model parameters. Add a thin PowerShell wrapper, update documentation/static contracts, and wire the real Codex automation prompt to run the report after weekly ops history.

**Tech Stack:** Python standard library, `unittest`, PowerShell wrapper, Markdown, JSON.

---

## File Structure

- Create `weekly_conclusion_report.py`: read market artifacts, merge candidate fields, evaluate status, render Markdown, expose CLI.
- Create `scripts/show_weekly_conclusion.ps1`: stable PowerShell entry point for recurring automation and manual checks.
- Create `tests/test_weekly_conclusion_report.py`: behavior tests for complete inputs, missing inputs, freshness failures, CLI output, and PowerShell contract.
- Modify `tests/test_weekly_automation.py`: static weekly automation contract must mention the new script and outputs.
- Modify `tests/test_codex_automation_audit.py`: audit contract must require `show_weekly_conclusion.ps1` in the HK closing automation.
- Modify `codex_automation_audit.py`: inspect automation prompt for the new weekly conclusion step.
- Modify `docs/美股每周自动运行说明.md`: document command, output files, and research-only boundary.
- Update real Codex automation `automation-2`: append `show_weekly_conclusion.ps1` after `show_weekly_ops_history.ps1` and require the final reply to summarize the conclusion report.

### Task 1: Complete Input Report Contract

**Files:**
- Create: `tests/test_weekly_conclusion_report.py`
- Create: `weekly_conclusion_report.py`

- [ ] **Step 1: Write the failing complete-input test**

Create `tests/test_weekly_conclusion_report.py` with helpers that build a temporary project tree:

```python
import csv
import json
import tempfile
import unittest
from pathlib import Path


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig")


def write_json(path, payload):
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_market(root, market_dir, ticker, company):
    base = Path(root) / "outputs" / market_dir
    write_text(base / "latest_run_summary.md", "# summary\nCandidate count: 1\n")
    write_csv(
        base / "candidate_pool.csv",
        [{"ticker": ticker, "company": company, "total_score": "82.5"}],
    )
    write_csv(
        base / "valuation_targets.csv",
        [
            {
                "ticker": ticker,
                "target_price": "120.00",
                "buy_price": "96.00",
                "expected_return": "24.5%",
                "trend_label": "uptrend_watch",
                "trend_confidence": "medium",
                "valuation_confidence": "high",
                "reason": "估值折价且质量分稳定",
            }
        ],
    )
    write_text(base / "valuation_report.md", f"# valuation\n## {ticker}\n估值折价且质量分稳定\n")
    write_text(base / "latest_investment_summary.md", f"# investment\n## {ticker}\n风险：行业景气回落\n")


class WeeklyConclusionReportTests(unittest.TestCase):
    def test_builds_ready_markdown_and_json_from_three_markets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_market(root, "us_universe", "MSFT", "Microsoft")
            write_market(root, "cn_universe", "000300.SZ", "沪深样本")
            write_market(root, "hk_universe", "0700.HK", "腾讯控股")
            write_json(
                root / "outputs" / "automation" / "latest_automation_check.json",
                {"as_of_date": "2026-06-28", "status": "ready"},
            )
            write_json(
                root / "outputs" / "automation" / "latest_weekly_ops_check.json",
                {"as_of_date": "2026-06-28", "status": "ready"},
            )
            write_json(
                root / "outputs" / "automation" / "latest_weekly_ops_history_summary.json",
                {"latest_as_of_date": "2026-06-28", "latest_status": "ready"},
            )

            from weekly_conclusion_report import build_weekly_conclusion, render_markdown

            payload = build_weekly_conclusion(root, today="2026-06-28")
            markdown = render_markdown(payload)

            self.assertEqual(payload["conclusion_schema"], "weekly_conclusion")
            self.assertEqual(payload["conclusion_version"], 1)
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["recommended_action"], "monitor_next_run")
            self.assertEqual(payload["candidate_count_total"], 3)
            self.assertEqual([market["market"] for market in payload["markets"]], ["US", "CN", "HK"])
            self.assertEqual(payload["candidates"][0]["ticker"], "MSFT")
            self.assertEqual(payload["candidates"][0]["target_price"], "120.00")
            self.assertEqual(payload["candidates"][0]["buy_price"], "96.00")
            self.assertEqual(payload["candidates"][0]["risk_reason"], "行业景气回落")
            self.assertIn("# 每周低估候选统一结论", markdown)
            self.assertIn("| US | MSFT | Microsoft | 82.5 | 120.00 | 96.00 |", markdown)
            self.assertIn("研究筛选和人工复核用途", markdown)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_conclusion_report.WeeklyConclusionReportTests.test_builds_ready_markdown_and_json_from_three_markets
```

Expected: FAIL with `ModuleNotFoundError: No module named 'weekly_conclusion_report'`.

- [ ] **Step 3: Implement the minimal report builder**

Create `weekly_conclusion_report.py` with:

```python
MARKETS = (
    {"market": "US", "label": "美股", "dir": "us_universe"},
    {"market": "CN", "label": "A股", "dir": "cn_universe"},
    {"market": "HK", "label": "港股", "dir": "hk_universe"},
)


def build_weekly_conclusion(project_root, today=None, max_age_days=8):
    project_root = Path(project_root)
    as_of_date = today or date.today().isoformat()
    missing_inputs = []
    warnings = []
    markets = []
    candidates = []
    automation = read_automation_state(project_root, as_of_date, max_age_days, warnings, missing_inputs)
    for market_config in MARKETS:
        market_result = read_market(project_root, market_config, missing_inputs, warnings)
        markets.append(market_result["summary"])
        candidates.extend(market_result["candidates"])
    status = decide_status(markets, candidates, automation, missing_inputs, warnings)
    return build_payload(as_of_date, status, automation, markets, candidates, missing_inputs, warnings, project_root)


def render_markdown(payload, per_market_limit=10):
    lines = ["# 每周低估候选统一结论", ""]
    lines.extend(render_automation_section(payload))
    lines.extend(render_market_section(payload))
    lines.extend(render_candidate_section(payload, per_market_limit=per_market_limit))
    lines.extend(render_risk_section(payload))
    lines.extend(render_output_section(payload))
    lines.extend(render_boundary_section())
    return "\n".join(lines).rstrip() + "\n"
```

Implementation requirements:
- Read market files from `outputs/us_universe`, `outputs/cn_universe`, and `outputs/hk_universe`.
- Use market display order `US`, `CN`, `HK`.
- Read candidates from `candidate_pool.csv` and merge fields from `valuation_targets.csv` by ticker.
- Extract `risk_reason` from lines in `latest_investment_summary.md` matching `风险：` followed by non-empty text.
- Set `status` to `ready` only when required files exist, automation checks are acceptable, and all three markets are readable.
- Include `outputs` paths for the Markdown and JSON default destinations.

- [ ] **Step 4: Verify the complete-input test passes**

Run the same command as Step 2.

Expected: PASS.

### Task 2: Missing Inputs And Freshness Boundaries

**Files:**
- Modify: `tests/test_weekly_conclusion_report.py`
- Modify: `weekly_conclusion_report.py`

- [ ] **Step 1: Write failing tests for missing and stale inputs**

Append two tests:

```python
    def test_missing_required_market_file_marks_needs_attention(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_market(root, "us_universe", "MSFT", "Microsoft")
            write_market(root, "cn_universe", "000300.SZ", "沪深样本")
            write_market(root, "hk_universe", "0700.HK", "腾讯控股")
            (root / "outputs" / "hk_universe" / "valuation_targets.csv").unlink()
            write_json(root / "outputs" / "automation" / "latest_automation_check.json", {"as_of_date": "2026-06-28", "status": "ready"})
            write_json(root / "outputs" / "automation" / "latest_weekly_ops_check.json", {"as_of_date": "2026-06-28", "status": "ready"})
            write_json(root / "outputs" / "automation" / "latest_weekly_ops_history_summary.json", {"latest_status": "ready"})

            from weekly_conclusion_report import build_weekly_conclusion

            payload = build_weekly_conclusion(root, today="2026-06-28")

            self.assertEqual(payload["status"], "needs_attention")
            self.assertIn("outputs/hk_universe/valuation_targets.csv", payload["missing_inputs"])

    def test_stale_or_future_automation_check_marks_needs_attention(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_market(root, "us_universe", "MSFT", "Microsoft")
            write_market(root, "cn_universe", "000300.SZ", "沪深样本")
            write_market(root, "hk_universe", "0700.HK", "腾讯控股")
            write_json(root / "outputs" / "automation" / "latest_automation_check.json", {"as_of_date": "2026-06-01", "status": "ready"})
            write_json(root / "outputs" / "automation" / "latest_weekly_ops_check.json", {"as_of_date": "2026-06-28", "status": "ready"})
            write_json(root / "outputs" / "automation" / "latest_weekly_ops_history_summary.json", {"latest_status": "ready"})

            from weekly_conclusion_report import build_weekly_conclusion

            stale = build_weekly_conclusion(root, today="2026-06-28", max_age_days=8)
            self.assertEqual(stale["status"], "needs_attention")
            self.assertIn("latest_automation_check.json is older than 8 days", stale["warnings"])

            write_json(root / "outputs" / "automation" / "latest_automation_check.json", {"as_of_date": "2026-07-01", "status": "ready"})
            future = build_weekly_conclusion(root, today="2026-06-28", max_age_days=8)
            self.assertEqual(future["status"], "needs_attention")
            self.assertIn("latest_automation_check.json is later than today", future["warnings"])
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_conclusion_report
```

Expected: FAIL because missing/freshness cases are not implemented.

- [ ] **Step 3: Implement exact status boundaries**

Update `weekly_conclusion_report.py`:
- Add `REQUIRED_MARKET_FILES = ("latest_run_summary.md", "candidate_pool.csv", "valuation_targets.csv", "valuation_report.md", "latest_investment_summary.md")`.
- Record missing required paths as repo-relative POSIX-style strings.
- Parse `latest_automation_check.json` `as_of_date` with `datetime.date.fromisoformat`.
- Warn and set `needs_attention` when the check date is later than `today`.
- Warn and set `needs_attention` when the check age is greater than `max_age_days`.
- Set `missing` only when no market candidates can be read and `latest_automation_check.json` is missing.

- [ ] **Step 4: Verify missing/freshness tests pass**

Run the same command as Step 2.

Expected: PASS.

### Task 3: CLI And PowerShell Entry Point

**Files:**
- Modify: `tests/test_weekly_conclusion_report.py`
- Modify: `weekly_conclusion_report.py`
- Create: `scripts/show_weekly_conclusion.ps1`

- [ ] **Step 1: Write failing CLI and PowerShell contract tests**

Append tests:

```python
    def test_cli_writes_markdown_and_json_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_market(root, "us_universe", "MSFT", "Microsoft")
            write_market(root, "cn_universe", "000300.SZ", "沪深样本")
            write_market(root, "hk_universe", "0700.HK", "腾讯控股")
            write_json(root / "outputs" / "automation" / "latest_automation_check.json", {"as_of_date": "2026-06-28", "status": "ready"})
            write_json(root / "outputs" / "automation" / "latest_weekly_ops_check.json", {"as_of_date": "2026-06-28", "status": "ready"})
            write_json(root / "outputs" / "automation" / "latest_weekly_ops_history_summary.json", {"latest_status": "ready"})

            import subprocess
            import sys

            md = root / "outputs" / "automation" / "latest_weekly_conclusion.md"
            js = root / "outputs" / "automation" / "latest_weekly_conclusion.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve().parents[1] / "weekly_conclusion_report.py"),
                    "--project-root",
                    str(root),
                    "--today",
                    "2026-06-28",
                    "--output",
                    str(md),
                    "--json-output",
                    str(js),
                ],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("每周低估候选统一结论", result.stdout)
            self.assertTrue(md.exists())
            self.assertTrue(js.exists())
            self.assertEqual(json.loads(js.read_text(encoding="utf-8-sig"))["status"], "ready")

    def test_powershell_wrapper_static_contract(self):
        script = (Path(__file__).resolve().parents[1] / "scripts" / "show_weekly_conclusion.ps1").read_text(encoding="utf-8-sig")

        self.assertIn("weekly_conclusion_report.py", script)
        self.assertIn("latest_weekly_conclusion.md", script)
        self.assertIn("latest_weekly_conclusion.json", script)
        self.assertIn("-NoProfile -ExecutionPolicy Bypass", script)
        self.assertIn("codex-primary-runtime", script)
```

- [ ] **Step 2: Run the CLI/script tests to verify they fail**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_conclusion_report.WeeklyConclusionReportTests.test_cli_writes_markdown_and_json_outputs tests.test_weekly_conclusion_report.WeeklyConclusionReportTests.test_powershell_wrapper_static_contract
```

Expected: FAIL because CLI arguments and/or `scripts/show_weekly_conclusion.ps1` do not exist.

- [ ] **Step 3: Implement CLI**

Add `main()` in `weekly_conclusion_report.py`:

```python
def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--today", default=None)
    parser.add_argument("--max-age-days", type=int, default=8)
    parser.add_argument("--output", default=None)
    parser.add_argument("--json-output", default=None)
    args = parser.parse_args(argv)
    payload = build_weekly_conclusion(args.project_root, today=args.today, max_age_days=args.max_age_days)
    markdown = render_markdown(payload)
    write_outputs(payload, markdown, args.output, args.json_output)
    print(markdown)
    return 0
```

Default output paths must be:
- `outputs/automation/latest_weekly_conclusion.md`
- `outputs/automation/latest_weekly_conclusion.json`

- [ ] **Step 4: Create PowerShell wrapper**

Create `scripts/show_weekly_conclusion.ps1`:

```powershell
param(
  [string]$ProjectRoot = "",
  [string]$Output = "",
  [string]$JsonOutput = "",
  [string]$Today = "",
  [int]$MaxAgeDays = 8
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_weekly_conclusion.md"
}
if (-not $JsonOutput) {
  $JsonOutput = Join-Path $ProjectRoot "outputs\automation\latest_weekly_conclusion.json"
}

# Manual equivalent:
# powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\show_weekly_conclusion.ps1
$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "weekly_conclusion_report.py"
$Args = @("-B", $Script, "--project-root", $ProjectRoot, "--output", $Output, "--json-output", $JsonOutput, "--max-age-days", $MaxAgeDays)
if ($Today) {
  $Args += @("--today", $Today)
}

& $Python @Args
if ($LASTEXITCODE -ne 0) {
  throw "Weekly conclusion report failed with exit code $LASTEXITCODE."
}
```

- [ ] **Step 5: Verify CLI/script tests pass**

Run the same command as Step 2.

Expected: PASS.

### Task 4: Documentation And Static Contracts

**Files:**
- Modify: `docs/美股每周自动运行说明.md`
- Modify: `tests/test_weekly_automation.py`

- [ ] **Step 1: Write failing weekly automation documentation contract**

Add a test to `tests/test_weekly_automation.py`:

```python
    def test_weekly_conclusion_report_documented(self):
        root = Path(__file__).resolve().parents[1]
        doc = (root / "docs" / "美股每周自动运行说明.md").read_text(encoding="utf-8-sig")

        self.assertIn("scripts\\show_weekly_conclusion.ps1", doc)
        self.assertIn("outputs/automation/latest_weekly_conclusion.md", doc)
        self.assertIn("outputs/automation/latest_weekly_conclusion.json", doc)
        self.assertIn("不重新抓取行情", doc)
        self.assertIn("不构成投资建议", doc)
```

- [ ] **Step 2: Run the documentation contract to verify it fails**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_automation.WeeklyAutomationTests.test_weekly_conclusion_report_documented
```

Expected: FAIL because the guide does not yet mention the new report.

- [ ] **Step 3: Update the Chinese operations guide**

Add a section named `统一每周结论报告` that documents:
- Command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\show_weekly_conclusion.ps1`
- Markdown output: `outputs/automation/latest_weekly_conclusion.md`
- JSON output: `outputs/automation/latest_weekly_conclusion.json`
- Boundary: read-only summary, does not fetch quotes, does not rescore, does not constitute investment advice.

- [ ] **Step 4: Verify documentation contract passes**

Run the same command as Step 2.

Expected: PASS.

### Task 5: Automation Audit And Real Recurring Task

**Files:**
- Modify: `codex_automation_audit.py`
- Modify: `tests/test_codex_automation_audit.py`
- Update: real Codex automation `automation-2`

- [ ] **Step 1: Write failing audit contract test**

Update `tests/test_codex_automation_audit.py` so the HK closing automation fixture lacks `show_weekly_conclusion.ps1`, then assert the audit reports prompt drift. Add a passing fixture containing:

```text
powershell.exe -NoProfile -ExecutionPolicy Bypass -File F:\chatgptssd\project2\scripts\show_weekly_conclusion.ps1
```

Expected assertions:

```python
self.assertIn("scripts\\show_weekly_conclusion.ps1", result["required_prompt_terms"])
self.assertIn("weekly_conclusion_report", json.dumps(result, ensure_ascii=False))
```

- [ ] **Step 2: Run audit tests to verify they fail**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_codex_automation_audit
```

Expected: FAIL because `codex_automation_audit.py` does not yet require the conclusion script.

- [ ] **Step 3: Update audit implementation**

Modify `codex_automation_audit.py`:
- Add `scripts\\show_weekly_conclusion.ps1` to the required prompt terms for the HK closing automation.
- Add `latest_weekly_conclusion.md` and `latest_weekly_conclusion.json` to expected output evidence if the audit already tracks output paths.
- Add an attention reason named `weekly_conclusion_report_missing` when the term is absent.

- [ ] **Step 4: Verify audit tests pass**

Run the same command as Step 2.

Expected: PASS.

- [ ] **Step 5: Update real Codex automation**

Use the Codex automation tool to update `automation-2`:
- Keep the existing US, CN, and HK commands unchanged.
- After `scripts\show_weekly_ops_history.ps1`, add:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File F:\chatgptssd\project2\scripts\show_weekly_conclusion.ps1
```

- Final reply must include the weekly ops check, weekly ops history, unified weekly conclusion, and HK detail.

- [ ] **Step 6: Re-run audit after updating the real automation**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' codex_automation_audit.py
```

Expected: generated audit output no longer reports `weekly_conclusion_report_missing` for `automation-2`.

### Task 6: Real Script Verification And Commit

**Files:**
- Verify all files changed by Tasks 1-5.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_conclusion_report tests.test_weekly_automation tests.test_codex_automation_audit
```

Expected: PASS.

- [ ] **Step 2: Run full test suite**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests
```

Expected: PASS.

- [ ] **Step 3: Run the real report script**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\show_weekly_conclusion.ps1
```

Expected:
- `outputs/automation/latest_weekly_conclusion.md` exists.
- `outputs/automation/latest_weekly_conclusion.json` exists.
- Console output starts with `# 每周低估候选统一结论`.
- If current inputs are stale or incomplete, JSON status is `needs_attention` and the Markdown explains the warnings instead of presenting stale results as fresh.

- [ ] **Step 4: Run whitespace check**

Run:

```powershell
git diff --check
```

Expected: no output and exit code 0.

- [ ] **Step 5: Commit and push**

Run:

```powershell
git add weekly_conclusion_report.py scripts/show_weekly_conclusion.ps1 tests/test_weekly_conclusion_report.py tests/test_weekly_automation.py tests/test_codex_automation_audit.py codex_automation_audit.py docs/美股每周自动运行说明.md docs/superpowers/plans/2026-06-28-weekly-conclusion-report.md
git commit -m "Add weekly conclusion report"
git push
```

Expected: branch `codex/regional-valuation-review-categories` pushed to GitHub.

## Self-Review

- Spec coverage: Tasks 1-3 implement Markdown/JSON generation, required inputs, candidate merge, freshness status, and wrapper command. Task 4 covers documentation. Task 5 covers automation audit and real Codex automation update. Task 6 covers verification and delivery.
- Placeholder scan: The plan contains no forbidden placeholder terms or unspecified validation steps.
- Type consistency: Public API is `build_weekly_conclusion(project_root, today=None, max_age_days=8)`, `render_markdown(payload, per_market_limit=10)`, `write_outputs(payload, markdown, output=None, json_output=None)`, and `main(argv=None)`. Tests and CLI use the same names.
