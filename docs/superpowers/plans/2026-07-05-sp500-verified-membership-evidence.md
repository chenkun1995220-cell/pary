# S&P 500 Verified Membership Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a conservative S&P 500 membership evidence path that can upgrade current and historical rows to `verified` only when source provenance is strong enough.

**Architecture:** Keep the existing secondary fallback as an execution unblocker, but add a separate verified-evidence workflow. The workflow will classify sources, ingest only approved official or exchange-traceable evidence, preview membership upgrades, and keep formal backtest upgrades disabled until verified coverage reaches the project gate.

**Tech Stack:** Python standard library CSV/JSON/date handling, existing PowerShell orchestration, existing `unittest` suite, S&P DJI official pages, SEC ticker reconciliation, ETF issuer holdings only as cross-check evidence.

---

## Current State

- `latest_sp500_current_membership_sources.json` reports `status=secondary_ready`, `source_trust_level=secondary`, `parsed_secondary_ticker_count=503`, `matched_count=50`, `missing_count=0`.
- `latest_membership_evidence_import_plan.json` reports `ready_to_import_count=0`, `missing_source_count=0`, `invalid_source_count=50`, `invalid_source_weeks_affected=7800`, `formal_backtest_upgrade_allowed=false`.
- S&P DJI's public S&P 500 page is the primary official source, but the visible public page only exposes the Top 10 table in normal HTML and references a `Full Constituents List` UI section.
- iShares IVV, SPY, and Vanguard VOO holdings pages can corroborate current exposure, but ETF holdings are fund portfolios and must not be treated as direct S&P DJI membership authority.

## Source Policy

### Verified

Rows may become `verified` only when all conditions below are true:

- Source domain is `spglobal.com`, `www.spglobal.com`, or an S&P DJI controlled subdomain.
- Source material directly identifies S&P 500 constituents or an S&P 500 add/remove event.
- The imported file or page evidence includes a retrieval date, source URL, and ticker column mapping.
- The ticker can be reconciled to SEC `company_tickers_exchange.json` or an accepted share-class mapping.
- The row passes dry-run validation before writing `data/config/us_sp500_current_membership_sources.csv` or `data/config/us_sp500_membership_evidence.csv`.

### Quasi-Official Cross-Check

Rows remain below `verified` when the source is an ETF issuer holding file:

- BlackRock iShares IVV holdings.
- State Street SPY holdings.
- Vanguard VOO holdings.

These sources may be used to mark `cross_checked=true`, detect ticker mismatches, or prioritize manual review, but they must not set `membership_evidence=verified`.

### Secondary

Rows remain `secondary` when sourced from public mirrors or community-maintained lists:

- Wikipedia S&P 500 constituent list.
- Existing `data/config/us_universe_symbols.csv` fallback.
- Any scraped or cached non-S&P page without direct official S&P DJI provenance.

## File Structure

- Modify: `sp500_membership_source_policy.py`
  - Add a small source classification module with `verified`, `cross_check`, and `secondary` outcomes.
  - Centralize allowed S&P DJI domains and ETF cross-check domains.
- Modify: `sp500_current_membership_sources.py`
  - Replace inline source-trust checks with the new policy helper.
  - Preserve the current secondary fallback behavior.
- Modify: `membership_evidence_import_plan.py`
  - Add `cross_check_count`, `verified_candidate_count`, and `blocked_by_source_policy_count`.
  - Continue rejecting `secondary` and `cross_check` rows for formal import.
- Modify: `backtest_membership_inputs.py`
  - Keep official S&P DJI URLs as the only current-source path that can survive as `verified`.
- Modify: `tests/test_sp500_membership_source_policy.py`
  - Add direct tests for source classification.
- Modify: `tests/test_sp500_current_membership_sources.py`
  - Add regression tests proving ETF holdings cannot upgrade current membership to `verified`.
- Modify: `tests/test_membership_evidence_import_plan.py`
  - Add tests for cross-check reporting without formal import.
- Modify: `docs/回测成分证据补强队列.md`
  - Document the source policy and explain why secondary fallback does not unlock formal backtest upgrades.
- Modify: `docs/美股每周自动运行说明.md`
  - Add the weekly operator path for official CSV, cross-check sources, and rejection reasons.

## Task 1: Add Source Policy Module

**Files:**
- Create: `sp500_membership_source_policy.py`
- Create: `tests/test_sp500_membership_source_policy.py`

- [ ] **Step 1: Write source policy tests**

Create `tests/test_sp500_membership_source_policy.py`:

```python
import unittest

from sp500_membership_source_policy import classify_membership_source


class Sp500MembershipSourcePolicyTests(unittest.TestCase):
    def test_spglobal_constituents_url_is_verified(self):
        result = classify_membership_source(
            "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
            evidence_kind="current_constituents",
        )
        self.assertEqual(result["trust_level"], "verified")
        self.assertTrue(result["can_upgrade_membership"])

    def test_spglobal_announcement_pdf_is_verified(self):
        result = classify_membership_source(
            "https://www.spglobal.com/spdji/en/documents/indexnews/announcements/example.pdf",
            evidence_kind="index_announcement",
        )
        self.assertEqual(result["trust_level"], "verified")
        self.assertTrue(result["can_upgrade_membership"])

    def test_etf_holdings_are_cross_check_only(self):
        result = classify_membership_source(
            "https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf",
            evidence_kind="etf_holdings",
        )
        self.assertEqual(result["trust_level"], "cross_check")
        self.assertFalse(result["can_upgrade_membership"])

    def test_wikipedia_remains_secondary(self):
        result = classify_membership_source(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            evidence_kind="current_constituents",
        )
        self.assertEqual(result["trust_level"], "secondary")
        self.assertFalse(result["can_upgrade_membership"])
```

- [ ] **Step 2: Run failing policy tests**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_sp500_membership_source_policy -v
```

Expected before implementation: `ModuleNotFoundError: No module named 'sp500_membership_source_policy'`.

- [ ] **Step 3: Implement source policy**

Create `sp500_membership_source_policy.py`:

```python
from urllib.parse import urlparse


VERIFIED_SPGLOBAL_HOSTS = {"spglobal.com", "www.spglobal.com"}
VERIFIED_SPGLOBAL_SUFFIXES = (".spglobal.com",)
CROSS_CHECK_HOST_SUFFIXES = (
    ".ishares.com",
    ".blackrock.com",
    ".ssga.com",
    ".vanguard.com",
)


def _host(url):
    parsed = urlparse((url or "").strip())
    return (parsed.hostname or "").lower()


def _is_spglobal(host):
    return host in VERIFIED_SPGLOBAL_HOSTS or host.endswith(VERIFIED_SPGLOBAL_SUFFIXES)


def _is_cross_check(host):
    return any(host == suffix.lstrip(".") or host.endswith(suffix) for suffix in CROSS_CHECK_HOST_SUFFIXES)


def classify_membership_source(source_url, evidence_kind=""):
    host = _host(source_url)
    kind = (evidence_kind or "").strip().lower()
    if _is_spglobal(host) and kind in {"current_constituents", "index_announcement"}:
        return {
            "trust_level": "verified",
            "can_upgrade_membership": True,
            "reason": "official_spglobal_membership_evidence",
        }
    if _is_cross_check(host):
        return {
            "trust_level": "cross_check",
            "can_upgrade_membership": False,
            "reason": "etf_holdings_are_not_index_membership_authority",
        }
    return {
        "trust_level": "secondary",
        "can_upgrade_membership": False,
        "reason": "source_not_official_spglobal_membership_evidence",
    }
```

- [ ] **Step 4: Run policy tests**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_sp500_membership_source_policy -v
```

Expected: `Ran 4 tests` and `OK`.

## Task 2: Route Current Source Trust Through Policy

**Files:**
- Modify: `sp500_current_membership_sources.py`
- Modify: `tests/test_sp500_current_membership_sources.py`

- [ ] **Step 1: Add regression test for ETF downgrade**

Add a test that builds a current membership source from an IVV holdings-style CSV and asserts:

```python
self.assertEqual(payload["source_trust_level"], "cross_check")
self.assertFalse(payload["formal_backtest_upgrade_allowed"])
self.assertEqual(rows[0]["membership_evidence"], "secondary")
```

- [ ] **Step 2: Run the new regression test**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_sp500_current_membership_sources -v
```

Expected before implementation: failure because current logic does not expose `cross_check` as a distinct trust level.

- [ ] **Step 3: Use `classify_membership_source()` in current source builder**

Replace local URL-domain trust checks with:

```python
from sp500_membership_source_policy import classify_membership_source
```

For official S&P source-file imports, pass `evidence_kind="current_constituents"`.

For ETF holdings import paths implemented in this plan, pass `evidence_kind="etf_holdings"` and force output rows to `membership_evidence=secondary`.

- [ ] **Step 4: Run current membership tests**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_sp500_current_membership_sources -v
```

Expected: all tests pass.

## Task 3: Extend Import Plan Diagnostics

**Files:**
- Modify: `membership_evidence_import_plan.py`
- Modify: `tests/test_membership_evidence_import_plan.py`

- [ ] **Step 1: Add diagnostics test**

Add a test where current source rows contain one `verified`, one `cross_check`, and one `secondary` row. Assert:

```python
self.assertEqual(payload["verified_candidate_count"], 1)
self.assertEqual(payload["cross_check_count"], 1)
self.assertEqual(payload["blocked_by_source_policy_count"], 2)
self.assertEqual(payload["ready_to_import_count"], 1)
```

- [ ] **Step 2: Run diagnostics test**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_membership_evidence_import_plan -v
```

Expected before implementation: failure due missing diagnostic fields.

- [ ] **Step 3: Add diagnostic counters**

In the import-plan builder:

- Count `membership_evidence=verified` and allowed source policy as `verified_candidate_count`.
- Count `source_trust_level=cross_check` or `membership_evidence=cross_check` as `cross_check_count`.
- Count non-importable rows with ticker matches as `blocked_by_source_policy_count`.
- Keep `formal_backtest_upgrade_allowed=false` until the existing verified-ratio gate allows it.

- [ ] **Step 4: Run import-plan tests**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_membership_evidence_import_plan -v
```

Expected: all tests pass.

## Task 4: Document Operator Workflow

**Files:**
- Modify: `docs/回测成分证据补强队列.md`
- Modify: `docs/美股每周自动运行说明.md`

- [ ] **Step 1: Add source hierarchy section**

Add this source hierarchy to both docs:

```markdown
### S&P 500 成分证据来源分级

- `verified`：S&P DJI / S&P Global 官方成分文件、官方指数公告、官方方法库或同域名官方 PDF。
- `cross_check`：IVV、SPY、VOO 等跟踪 S&P 500 的 ETF 官方持仓文件，只用于交叉核对 ticker 和权重，不升级历史或当前成分证据。
- `secondary`：Wikipedia、公开镜像、项目缓存和非官方整理表，只用于解阻运行和发现缺口。
```

- [ ] **Step 2: Add operator commands**

Add these commands:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check_sp500_current_membership_source_inbox.ps1 -ProjectRoot F:\chatgptssd\project2
powershell -ExecutionPolicy Bypass -File scripts\run_sp500_current_membership_sources.ps1 -ProjectRoot F:\chatgptssd\project2 -DryRun -SourceFileInbox inputs\sp500_current_membership\official_constituents.csv
powershell -ExecutionPolicy Bypass -File scripts\run_sp500_current_membership_sources.ps1 -ProjectRoot F:\chatgptssd\project2 -SourceFileInbox inputs\sp500_current_membership\official_constituents.csv
powershell -ExecutionPolicy Bypass -File scripts\run_membership_evidence_import_plan.ps1 -ProjectRoot F:\chatgptssd\project2
powershell -ExecutionPolicy Bypass -File scripts\run_membership_evidence_apply_preview.ps1 -ProjectRoot F:\chatgptssd\project2
```

- [ ] **Step 3: Verify docs mention the gate**

Run:

```powershell
rg -n "cross_check|secondary|formal_backtest_upgrade_allowed|run_membership_evidence_apply_preview" docs
```

Expected: both docs contain the new source hierarchy and the formal upgrade gate remains documented.

## Task 5: End-to-End Verification

**Files:**
- No new files beyond the task files above.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_sp500_membership_source_policy tests.test_sp500_current_membership_sources tests.test_membership_evidence_import_plan tests.test_backtest_membership_inputs -v
```

Expected: all tests pass.

- [ ] **Step 2: Run weekly evidence checks**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_sp500_current_membership_sources.ps1 -ProjectRoot F:\chatgptssd\project2 -DryRun
powershell -ExecutionPolicy Bypass -File scripts\run_membership_evidence_import_plan.ps1 -ProjectRoot F:\chatgptssd\project2
powershell -ExecutionPolicy Bypass -File scripts\run_pre_submit_review.ps1 -ProjectRoot F:\chatgptssd\project2
```

Expected:

- Current fallback remains `secondary_ready` when no official S&P DJI CSV is present.
- Import plan still reports `ready_to_import_count=0` for secondary-only evidence.
- Pre-submit review remains `ready` with `development_priority_actions` containing `supplement_verified_membership_evidence`.

- [ ] **Step 3: Commit**

Run:

```powershell
git add sp500_membership_source_policy.py tests/test_sp500_membership_source_policy.py sp500_current_membership_sources.py membership_evidence_import_plan.py tests/test_sp500_current_membership_sources.py tests/test_membership_evidence_import_plan.py docs/回测成分证据补强队列.md docs/美股每周自动运行说明.md
git commit -m "feat: classify sp500 membership evidence sources"
git push origin codex/regional-valuation-review-categories
```
