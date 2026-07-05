import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def official_html_with_ticker_count(count=400):
    rows = [
        "<tr><td>ABT</td><td>Abbott Laboratories</td></tr>",
        "<tr><td>ADM</td><td>Archer Daniels Midland</td></tr>",
    ]
    rows.extend(
        f"<tr><td>T{i:03d}</td><td>Test Company {i}</td></tr>"
        for i in range(max(0, count - len(rows)))
    )
    return "\n".join(
        [
            "<html><body>",
            "<table>",
            "<tr><th>Symbol</th><th>Company</th></tr>",
            *rows,
            "</table>",
            "</body></html>",
        ]
    )


OFFICIAL_HTML = official_html_with_ticker_count()

OFFICIAL_SHELL_HTML = """
<html><body>
<h2>Full Constituents List</h2>
<table>
  <tr><th>Symbol</th><th>Company</th></tr>
</table>
</body></html>
"""

OFFICIAL_LOW_CONFIDENCE_HTML = """
<html><body>
<table>
  <tr><th>Symbol</th><th>Company</th></tr>
  <tr><td>ABT</td><td>Abbott Laboratories</td></tr>
  <tr><td>ADM</td><td>Archer Daniels Midland</td></tr>
</table>
</body></html>
"""


def write_template(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "ticker",
                "membership_evidence",
                "membership_source_url",
                "source_as_of_date",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "ticker": "ABT",
                "membership_evidence": "verified",
                "membership_source_url": "",
                "source_as_of_date": "",
                "notes": "",
            }
        )
        writer.writerow(
            {
                "ticker": "ZZZ",
                "membership_evidence": "verified",
                "membership_source_url": "",
                "source_as_of_date": "",
                "notes": "",
            }
        )


def write_official_csv(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Symbol", "Security"])
        writer.writeheader()
        writer.writerow({"Symbol": "ABT", "Security": "Abbott Laboratories"})
        writer.writerow({"Symbol": "ADM", "Security": "Archer Daniels Midland"})
        for index in range(398):
            writer.writerow({"Symbol": f"T{index:03d}", "Security": f"Test Company {index}"})


def write_official_csv_with_ticker_symbol_column(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Ticker Symbol", "Security"])
        writer.writeheader()
        writer.writerow({"Ticker Symbol": "ABT", "Security": "Abbott Laboratories"})
        writer.writerow({"Ticker Symbol": "ADM", "Security": "Archer Daniels Midland"})
        for index in range(398):
            writer.writerow({"Ticker Symbol": f"T{index:03d}", "Security": f"Test Company {index}"})


def write_official_csv_with_metadata_preamble(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["S&P 500 Constituents"])
        writer.writerow(["Source", "S&P Dow Jones Indices"])
        writer.writerow([])
        writer.writerow(["Symbol", "Security"])
        writer.writerow(["ABT", "Abbott Laboratories"])
        writer.writerow(["ADM", "Archer Daniels Midland"])
        for index in range(398):
            writer.writerow([f"T{index:03d}", f"Test Company {index}"])


def write_official_html_xls(path):
    rows = [
        "<tr><th>Symbol</th><th>Security</th></tr>",
        "<tr><td>ABT</td><td>Abbott Laboratories</td></tr>",
        "<tr><td>ADM</td><td>Archer Daniels Midland</td></tr>",
    ]
    rows.extend(
        f"<tr><td>T{index:03d}</td><td>Test Company {index}</td></tr>"
        for index in range(398)
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "<html><body><table>" + "".join(rows) + "</table></body></html>",
        encoding="utf-8",
    )


def write_public_constituents_csv(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["ticker", "company_name", "industry", "cik"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "ticker": "ABT",
                "company_name": "Abbott Laboratories",
                "industry": "Health Care",
                "cik": "1800",
            }
        )
        writer.writerow(
            {
                "ticker": "ADM",
                "company_name": "Archer Daniels Midland",
                "industry": "Consumer Staples",
                "cik": "7084",
            }
        )
        for index in range(398):
            writer.writerow(
                {
                    "ticker": f"T{index:03d}",
                    "company_name": f"Test Company {index}",
                    "industry": "Industrials",
                    "cik": str(100000 + index),
                }
            )


def write_crosscheck_xlsx(path):
    import openpyxl

    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = openpyxl.Workbook()
    summary = workbook.active
    summary.title = "说明"
    summary.append(["S&P 500 全量成分股对照整理版（非官方导出）"])
    summary.append(["结论边界", "此文件是公开来源交叉整理版，不是 S&P DJI 官方全量成分股导出。"])
    sheet = workbook.create_sheet("工作清单_503")
    sheet.append(
        [
            "symbol",
            "name",
            "sector",
            "in_wikipedia",
            "in_github_datahub",
            "in_spy",
            "in_ivv",
            "in_voo",
            "public_list_count",
            "etf_count",
            "evidence_count",
            "inclusion_basis",
        ]
    )
    sheet.append(["ABT", "Abbott Laboratories", "Health Care", 1, 1, 1, 0, 1, 2, 2, 4, "public_lists_agree"])
    sheet.append(["ADM", "Archer Daniels Midland", "Consumer Staples", 1, 1, 1, 0, 1, 2, 2, 4, "public_lists_agree"])
    for index in range(398):
        sheet.append([f"T{index:03d}", f"Test Company {index}", "Industrials", 1, 1, 1, 0, 1, 2, 2, 4, "public_lists_agree"])
    workbook.save(path)


def write_incomplete_official_csv(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Symbol", "Security"])
        writer.writeheader()
        writer.writerow({"Symbol": "ABT", "Security": "Abbott Laboratories"})
        writer.writerow({"Symbol": "ADM", "Security": "Archer Daniels Midland"})


def write_official_csv_for_project_template(path):
    tickers = [
        "ABT",
        "ADM",
        "AEP",
        "BA",
        "BMY",
        "CAT",
        "CL",
        "CMS",
        "COP",
        "CSX",
        "CVS",
        "CVX",
        "DE",
        "DTE",
        "ED",
        "EIX",
        "ETN",
        "ETR",
        "EXC",
        "F",
        "GD",
        "GE",
        "GIS",
        "HAL",
        "HIG",
        "HON",
        "HSY",
        "IBM",
        "IP",
        "KMB",
        "KO",
        "KR",
        "LMT",
        "MMM",
        "MO",
        "MRK",
        "MSI",
        "NOC",
        "NSC",
        "OXY",
        "PEG",
        "PEP",
        "PFE",
        "PG",
        "PPG",
        "RTX",
        "SLB",
        "SO",
        "SPGI",
        "UNP",
    ]
    tickers.extend(f"T{i:03d}" for i in range(400 - len(tickers)))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Symbol", "Security"])
        writer.writeheader()
        for ticker in tickers:
            writer.writerow({"Symbol": ticker, "Security": f"{ticker} Company"})


def write_intake_template(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "expected_ticker",
                "intake_status",
                "required_source_url",
                "required_source_columns",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "expected_ticker": "ABT",
                "intake_status": "official_export_required",
                "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                "required_source_columns": "Symbol or Ticker",
                "notes": "",
            }
        )
        writer.writerow(
            {
                "expected_ticker": "ZZZ",
                "intake_status": "official_export_required",
                "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                "required_source_columns": "Symbol or Ticker",
                "notes": "",
            }
        )


class Sp500CurrentMembershipSourcesTests(unittest.TestCase):
    def test_builds_verified_current_source_rows_only_for_official_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            write_template(template)

            from sp500_current_membership_sources import build_current_membership_sources

            payload = build_current_membership_sources(
                template,
                OFFICIAL_HTML,
                "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                as_of_date="2026-06-30",
            )

            self.assertEqual(payload["source_schema"], "sp500_current_membership_sources")
            self.assertEqual(payload["matched_count"], 1)
            self.assertEqual(payload["missing_count"], 1)
            self.assertFalse(payload["formal_backtest_upgrade_allowed"])
            self.assertEqual(payload["rows"][0]["ticker"], "ABT")
            self.assertEqual(payload["rows"][0]["membership_evidence"], "verified")
            self.assertEqual(
                payload["rows"][0]["membership_source_url"],
                "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
            )
            self.assertEqual(payload["missing_tickers"], ["ZZZ"])
            self.assertEqual(len(payload["missing_ticker_review_queue"]), 1)
            self.assertEqual(payload["missing_ticker_review_queue"][0]["ticker"], "ZZZ")
            self.assertEqual(
                payload["missing_ticker_review_queue"][0]["review_status"],
                "open",
            )
            self.assertIn(
                "official S&P Global current membership source",
                payload["missing_ticker_review_queue"][0]["recommended_check"],
            )

    def test_builds_secondary_rows_from_public_constituents_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            public_source = root / "us_universe_symbols.csv"
            write_template(template)
            write_public_constituents_csv(public_source)

            from sp500_current_membership_sources import (
                build_secondary_current_membership_sources_from_constituents_csv,
            )

            payload = build_secondary_current_membership_sources_from_constituents_csv(
                template,
                public_source,
                as_of_date="2026-07-05",
            )

            self.assertEqual(payload["status"], "secondary_ready")
            self.assertEqual(payload["source_trust_level"], "secondary")
            self.assertEqual(payload["parsed_secondary_ticker_count"], 400)
            self.assertEqual(payload["matched_count"], 1)
            self.assertEqual(payload["missing_tickers"], ["ZZZ"])
            self.assertEqual(payload["rows"][0]["ticker"], "ABT")
            self.assertEqual(payload["rows"][0]["membership_evidence"], "secondary")
            self.assertIn("en.wikipedia.org/wiki/List_of_S%26P_500_companies", payload["rows"][0]["membership_source_url"])
            self.assertIn("SEC company_tickers_exchange", payload["rows"][0]["notes"])
            self.assertEqual(payload["next_action"], "run_screening_with_secondary_current_membership")
            self.assertEqual(payload["recommended_followup"], "obtain_official_spglobal_constituents_csv")
            self.assertFalse(payload["formal_backtest_upgrade_allowed"])

    def test_builds_crosscheck_substitute_rows_from_xlsx_worklist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            crosscheck = root / "sp500_full_constituents_crosscheck_20260705.xlsx"
            write_template(template)
            write_crosscheck_xlsx(crosscheck)

            from sp500_current_membership_sources import (
                build_crosscheck_substitute_current_membership_sources_from_file,
            )

            payload = build_crosscheck_substitute_current_membership_sources_from_file(
                template,
                crosscheck,
                as_of_date="2026-07-05",
            )

            self.assertEqual(payload["status"], "crosscheck_substitute_ready")
            self.assertEqual(payload["source_trust_level"], "crosscheck_substitute")
            self.assertEqual(payload["parsed_crosscheck_ticker_count"], 400)
            self.assertEqual(payload["matched_count"], 1)
            self.assertEqual(payload["missing_tickers"], ["ZZZ"])
            self.assertEqual(payload["rows"][0]["ticker"], "ABT")
            self.assertEqual(payload["rows"][0]["membership_evidence"], "secondary")
            self.assertEqual(payload["next_action"], "run_screening_with_crosscheck_current_membership")
            self.assertEqual(payload["recommended_followup"], "refresh_crosscheck_substitute_weekly")
            self.assertFalse(payload["formal_backtest_upgrade_allowed"])
            self.assertIn("crosscheck_substitute_source", payload["source_quality_flags"])
            self.assertIn("public_lists_are_reference_only", payload["source_quality_flags"])
            self.assertIn("etf_holdings_are_not_index_authority", payload["source_quality_flags"])
            self.assertIn("announcements_are_not_full_current_file", payload["source_quality_flags"])

    def test_etf_holdings_source_is_cross_check_without_verified_upgrade(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            public_source = root / "ivv_holdings.csv"
            write_template(template)
            write_public_constituents_csv(public_source)

            from sp500_current_membership_sources import (
                build_secondary_current_membership_sources_from_constituents_csv,
            )

            payload = build_secondary_current_membership_sources_from_constituents_csv(
                template,
                public_source,
                as_of_date="2026-07-05",
                source_url="https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf",
            )

            self.assertEqual(payload["source_trust_level"], "cross_check")
            self.assertFalse(payload["formal_backtest_upgrade_allowed"])
            self.assertEqual(payload["rows"][0]["membership_evidence"], "secondary")
            self.assertIn("cross_check_source", payload["source_quality_flags"])

    def test_cli_builds_secondary_rows_from_public_constituents_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            public_source = root / "us_universe_symbols.csv"
            output = root / "sources.csv"
            report = root / "sources.md"
            metadata = root / "sources.json"
            intake = root / "intake_template.csv"
            write_template(template)
            write_public_constituents_csv(public_source)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "sp500_current_membership_sources.py"),
                    "--template",
                    str(template),
                    "--secondary-constituents-csv",
                    str(public_source),
                    "--as-of-date",
                    "2026-07-05",
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                    "--json-output",
                    str(metadata),
                    "--intake-template",
                    str(intake),
                    "--source-file-request",
                    "",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            with output.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["ticker"], "ABT")
            self.assertEqual(rows[0]["membership_evidence"], "secondary")
            payload = json.loads(metadata.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["status"], "secondary_ready")
            self.assertEqual(payload["source_trust_level"], "secondary")
            self.assertEqual(payload["matched_count"], 1)
            self.assertEqual(payload["recommended_followup"], "obtain_official_spglobal_constituents_csv")
            self.assertFalse(payload["formal_backtest_upgrade_allowed"])
            report_text = report.read_text(encoding="utf-8-sig")
            self.assertIn("status: secondary_ready", report_text)
            self.assertIn("source_trust_level: secondary", report_text)
            self.assertIn("recommended_followup: obtain_official_spglobal_constituents_csv", report_text)

    def test_cli_builds_crosscheck_substitute_rows_from_xlsx(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            crosscheck = root / "sp500_full_constituents_crosscheck_20260705.xlsx"
            output = root / "sources.csv"
            report = root / "sources.md"
            metadata = root / "sources.json"
            intake = root / "intake_template.csv"
            write_template(template)
            write_crosscheck_xlsx(crosscheck)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "sp500_current_membership_sources.py"),
                    "--template",
                    str(template),
                    "--crosscheck-constituents-file",
                    str(crosscheck),
                    "--as-of-date",
                    "2026-07-05",
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                    "--json-output",
                    str(metadata),
                    "--intake-template",
                    str(intake),
                    "--source-file-request",
                    "",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            with output.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["ticker"], "ABT")
            self.assertEqual(rows[0]["membership_evidence"], "secondary")
            payload = json.loads(metadata.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["status"], "crosscheck_substitute_ready")
            self.assertEqual(payload["source_trust_level"], "crosscheck_substitute")
            self.assertEqual(payload["parsed_crosscheck_ticker_count"], 400)
            self.assertEqual(payload["recommended_followup"], "refresh_crosscheck_substitute_weekly")
            self.assertFalse(payload["formal_backtest_upgrade_allowed"])
            report_text = report.read_text(encoding="utf-8-sig")
            self.assertIn("status: crosscheck_substitute_ready", report_text)
            self.assertIn("source_trust_level: crosscheck_substitute", report_text)
            self.assertIn("parsed_crosscheck_ticker_count: 400", report_text)

    def test_build_marks_official_page_without_constituent_rows_as_source_file_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            write_template(template)

            from sp500_current_membership_sources import build_current_membership_sources

            payload = build_current_membership_sources(
                template,
                OFFICIAL_SHELL_HTML,
                "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                as_of_date="2026-06-30",
            )

            self.assertEqual(payload["status"], "source_file_required")
            self.assertEqual(payload["matched_count"], 0)
            self.assertEqual(payload["parsed_official_ticker_count"], 0)
            self.assertEqual(payload["missing_count"], 2)
            self.assertEqual(payload["rows"], [])
            self.assertEqual(payload["next_action"], "provide_official_constituents_csv")
            self.assertEqual(payload["source_file_required_columns"], ["Symbol", "Ticker"])
            self.assertFalse(payload["formal_backtest_upgrade_allowed"])

    def test_build_rejects_low_confidence_official_page_parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            write_template(template)

            from sp500_current_membership_sources import build_current_membership_sources

            payload = build_current_membership_sources(
                template,
                OFFICIAL_LOW_CONFIDENCE_HTML,
                "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                as_of_date="2026-06-30",
            )

            self.assertEqual(payload["status"], "source_file_required")
            self.assertEqual(payload["matched_count"], 0)
            self.assertEqual(payload["parsed_official_ticker_count"], 2)
            self.assertEqual(payload["minimum_official_ticker_count"], 400)
            self.assertEqual(payload["missing_count"], 2)
            self.assertEqual(payload["rows"], [])
            self.assertEqual(payload["next_action"], "provide_official_constituents_csv")
            self.assertEqual(payload["source_file_required_columns"], ["Symbol", "Ticker"])
            self.assertIn("official_ticker_count_below_minimum", payload["source_quality_flags"])
            self.assertIn("official_top_constituents_only", payload["source_quality_flags"])
            self.assertEqual(
                payload["source_file_rejection_reason"],
                "official_top_constituents_only",
            )
            self.assertFalse(payload["formal_backtest_upgrade_allowed"])

    def test_rejects_unofficial_source_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            write_template(template)

            from sp500_current_membership_sources import build_current_membership_sources

            with self.assertRaisesRegex(ValueError, "official S&P Global"):
                build_current_membership_sources(
                    template,
                    OFFICIAL_HTML,
                    "https://spglobal.com.example.test/sp-500/",
                    as_of_date="2026-06-30",
                )

    def test_cli_writes_source_pack_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            html = root / "official.html"
            output = root / "sources.csv"
            report = root / "sources.md"
            metadata = root / "sources.json"
            intake = root / "intake_template.csv"
            write_template(template)
            html.write_text(OFFICIAL_HTML, encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "sp500_current_membership_sources.py"),
                    "--template",
                    str(template),
                    "--source-html",
                    str(html),
                    "--source-url",
                    "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                    "--as-of-date",
                    "2026-06-30",
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                    "--json-output",
                    str(metadata),
                    "--intake-template",
                    str(intake),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            source_text = output.read_text(encoding="utf-8-sig")
            self.assertIn("ABT,verified,https://www.spglobal.com", source_text)
            self.assertNotIn("ZZZ,verified", source_text)
            self.assertIn("matched_count: 1", report.read_text(encoding="utf-8-sig"))
            payload = json.loads(metadata.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["source_schema"], "sp500_current_membership_sources")
            self.assertEqual(payload["source_version"], 1)
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["next_action"], "review_missing_tickers")
            self.assertEqual(payload["matched_count"], 1)

    def test_cli_reports_source_file_required_when_official_page_has_no_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            html = root / "official_shell.html"
            output = root / "sources.csv"
            report = root / "sources.md"
            metadata = root / "sources.json"
            intake = root / "intake_template.csv"
            source_request = root / "source_file_request.md"
            write_template(template)
            html.write_text(OFFICIAL_SHELL_HTML, encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "sp500_current_membership_sources.py"),
                    "--template",
                    str(template),
                    "--source-html",
                    str(html),
                    "--source-url",
                    "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                    "--as-of-date",
                    "2026-06-30",
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                    "--json-output",
                    str(metadata),
                    "--intake-template",
                    str(intake),
                    "--source-file-request",
                    str(source_request),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(len(output.read_text(encoding="utf-8-sig").splitlines()), 1)
            report_text = report.read_text(encoding="utf-8-sig")
            self.assertIn("status: source_file_required", report_text)
            self.assertIn("next_action: provide_official_constituents_csv", report_text)
            payload = json.loads(metadata.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["status"], "source_file_required")
            self.assertEqual(payload["next_action"], "provide_official_constituents_csv")
            self.assertEqual(payload["source_file_required_columns"], ["Symbol", "Ticker"])
            self.assertIn("source_file_next_command", payload)
            self.assertIn("run_sp500_current_membership_sources.ps1", payload["source_file_next_command"])
            self.assertIn("-SourceFile <official_constituents.csv>", payload["source_file_next_command"])
            self.assertIn("source_file_inbox_next_command", payload)
            self.assertIn("-SourceFileInbox inputs/sp500_current_membership/official_constituents.csv", payload["source_file_inbox_next_command"])
            self.assertIn("source_file_inbox_dry_run_command", payload)
            self.assertIn("-DryRun -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv", payload["source_file_inbox_dry_run_command"])
            self.assertIn("source_file_acceptance_criteria", payload)
            self.assertIn("has_symbol_or_ticker_column", payload["source_file_acceptance_criteria"])
            self.assertIn("at_least_400_tickers", payload["source_file_acceptance_criteria"])
            self.assertEqual(
                payload["source_file_inbox"],
                "inputs/sp500_current_membership/official_constituents.csv",
            )
            self.assertFalse(payload["source_file_inbox_exists"])
            self.assertEqual(payload["source_file_inbox_size_bytes"], 0)
            self.assertEqual(payload["source_file_inbox_sha256"], "")
            self.assertEqual(payload["source_file_inbox_modified_at"], "")
            self.assertEqual(payload["source_file_validation_status"], "missing")
            self.assertIn("source_file_next_command:", report_text)
            self.assertIn("source_file_inbox_next_command:", report_text)
            self.assertIn("source_file_inbox_dry_run_command:", report_text)
            self.assertIn("source_file_inbox_exists: false", report_text)
            self.assertIn("source_file_validation_status: missing", report_text)
            self.assertIn("source_file_inbox_size_bytes: 0", report_text)
            self.assertIn("source_file_inbox_sha256: none", report_text)
            self.assertIn("source_file_inbox_modified_at: none", report_text)
            self.assertIn("at_least_400_tickers", report_text)
            self.assertIn("source_file_user_agent_hint", report_text)
            self.assertIn("-UserAgent <user_agent>", report_text)
            self.assertEqual(payload["source_file_intake_template"], str(intake))
            self.assertEqual(payload["source_file_request_file"], str(source_request))
            self.assertTrue(source_request.exists())
            source_request_text = source_request.read_text(encoding="utf-8-sig")
            self.assertIn("request_manifest_schema: sp500_current_membership_source_file_request", source_request_text)
            self.assertIn("request_manifest_version: 1", source_request_text)
            self.assertIn("status: source_file_required", source_request_text)
            self.assertIn("accepted_ticker_columns: Symbol, Ticker, Ticker Symbol, Constituent Ticker, Constituent Symbol", source_request_text)
            self.assertIn("acceptance_criteria: has_symbol_or_ticker_column, at_least_400_tickers, official_spglobal_constituents_export", source_request_text)
            self.assertIn("source_file_inbox_size_bytes: 0", source_request_text)
            self.assertIn("source_file_inbox_sha256: none", source_request_text)
            self.assertIn("source_file_inbox_modified_at: none", source_request_text)
            self.assertIn("source_file_user_agent_hint", source_request_text)
            self.assertIn("-UserAgent <user_agent>", source_request_text)
            self.assertIn("formal_backtest_upgrade_allowed: false", source_request_text)
            self.assertIn("formal_model_change_allowed: false", source_request_text)
            with intake.open(encoding="utf-8-sig", newline="") as handle:
                intake_rows = list(csv.DictReader(handle))
            self.assertEqual([row["expected_ticker"] for row in intake_rows], ["ABT", "ZZZ"])
            self.assertIn("official_export_required", intake_rows[0]["intake_status"])

    def test_cli_writes_source_pack_from_local_official_csv_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            source_file = root / "official_constituents.csv"
            output = root / "sources.csv"
            report = root / "sources.md"
            metadata = root / "sources.json"
            review_queue = root / "review_queue.csv"
            intake = root / "intake_template.csv"
            write_template(template)
            write_official_csv(source_file)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "sp500_current_membership_sources.py"),
                    "--template",
                    str(template),
                    "--source-file",
                    str(source_file),
                    "--source-url",
                    "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                    "--as-of-date",
                    "2026-06-30",
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                    "--json-output",
                    str(metadata),
                    "--intake-template",
                    str(intake),
                    "--review-queue-output",
                    str(review_queue),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            source_text = output.read_text(encoding="utf-8-sig")
            self.assertIn("ABT,verified,https://www.spglobal.com", source_text)
            self.assertNotIn("ZZZ,verified", source_text)
            report_text = report.read_text(encoding="utf-8-sig")
            self.assertIn("status: ready", report_text)
            self.assertIn("matched_count: 1", report_text)
            self.assertIn("## Missing ticker review queue", report_text)
            self.assertIn("| ZZZ | open |", report_text)
            with review_queue.open(encoding="utf-8-sig", newline="") as handle:
                queue_rows = list(csv.DictReader(handle))
            self.assertEqual([row["ticker"] for row in queue_rows], ["ZZZ"])
            self.assertEqual(queue_rows[0]["review_status"], "open")
            with intake.open(encoding="utf-8-sig", newline="") as handle:
                intake_rows = list(csv.DictReader(handle))
            self.assertEqual([row["expected_ticker"] for row in intake_rows], ["ZZZ"])
            self.assertEqual(
                queue_rows[0]["issue_type"],
                "missing_from_official_current_source",
            )
            payload = json.loads(metadata.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["missing_ticker_review_queue_file"], str(review_queue))

    def test_cli_reports_intake_coverage_after_local_official_csv_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            source_file = root / "official_constituents.csv"
            output = root / "sources.csv"
            report = root / "sources.md"
            metadata = root / "sources.json"
            intake = root / "intake_template.csv"
            write_template(template)
            write_official_csv(source_file)
            write_intake_template(intake)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "sp500_current_membership_sources.py"),
                    "--template",
                    str(template),
                    "--source-file",
                    str(source_file),
                    "--source-url",
                    "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                    "--as-of-date",
                    "2026-06-30",
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                    "--json-output",
                    str(metadata),
                    "--intake-template",
                    str(intake),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(metadata.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["intake_coverage_status"], "partial")
            self.assertEqual(payload["intake_expected_count"], 2)
            self.assertEqual(payload["intake_matched_count"], 1)
            self.assertEqual(payload["intake_missing_count"], 1)
            self.assertEqual(payload["intake_missing_tickers"], ["ZZZ"])
            self.assertEqual(
                payload["recommended_followup"],
                "run_membership_evidence_import_plan_then_apply_preview",
            )
            report_text = report.read_text(encoding="utf-8-sig")
            self.assertIn("intake_coverage_status: partial", report_text)
            self.assertIn(
                "recommended_followup: run_membership_evidence_import_plan_then_apply_preview",
                report_text,
            )
            with intake.open(encoding="utf-8-sig", newline="") as handle:
                remaining_rows = list(csv.DictReader(handle))
            self.assertEqual([row["expected_ticker"] for row in remaining_rows], ["ZZZ"])

    def test_cli_accepts_common_official_csv_ticker_symbol_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            source_file = root / "official_constituents.csv"
            output = root / "sources.csv"
            report = root / "sources.md"
            metadata = root / "sources.json"
            intake = root / "intake_template.csv"
            write_template(template)
            write_official_csv_with_ticker_symbol_column(source_file)
            write_intake_template(intake)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "sp500_current_membership_sources.py"),
                    "--template",
                    str(template),
                    "--source-file",
                    str(source_file),
                    "--source-url",
                    "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                    "--as-of-date",
                    "2026-06-30",
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                    "--json-output",
                    str(metadata),
                    "--intake-template",
                    str(intake),
                    "--validate-source-file-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("status: ready", result.stdout)
            self.assertIn("parsed_official_ticker_count: 400", result.stdout)
            self.assertIn("source_file_ticker_columns: Ticker Symbol", result.stdout)
            self.assertFalse(output.exists())
            self.assertFalse(report.exists())
            self.assertFalse(metadata.exists())

    def test_cli_accepts_official_html_xls_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            source_file = root / "official_constituents.xls"
            output = root / "sources.csv"
            report = root / "sources.md"
            metadata = root / "sources.json"
            intake = root / "intake_template.csv"
            write_template(template)
            write_official_html_xls(source_file)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "sp500_current_membership_sources.py"),
                    "--template",
                    str(template),
                    "--source-file",
                    str(source_file),
                    "--source-url",
                    "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                    "--as-of-date",
                    "2026-07-05",
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                    "--json-output",
                    str(metadata),
                    "--intake-template",
                    str(intake),
                    "--source-file-request",
                    "",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(metadata.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["parsed_official_ticker_count"], 400)
            self.assertEqual(payload["source_file_ticker_columns"], ["Symbol"])
            self.assertEqual(payload["rows"][0]["membership_evidence"], "verified")
            self.assertIn("source_file_ticker_columns: Symbol", report.read_text(encoding="utf-8-sig"))

    def test_cli_validates_source_file_without_writing_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            source_file = root / "official_constituents.csv"
            output = root / "sources.csv"
            report = root / "sources.md"
            metadata = root / "sources.json"
            review_queue = root / "review_queue.csv"
            intake = root / "intake_template.csv"
            write_template(template)
            write_official_csv(source_file)
            write_intake_template(intake)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "sp500_current_membership_sources.py"),
                    "--template",
                    str(template),
                    "--source-file",
                    str(source_file),
                    "--source-url",
                    "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                    "--as-of-date",
                    "2026-06-30",
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                    "--json-output",
                    str(metadata),
                    "--intake-template",
                    str(intake),
                    "--review-queue-output",
                    str(review_queue),
                    "--validate-source-file-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("validation_only: true", result.stdout)
            self.assertIn("matched_count: 1", result.stdout)
            self.assertIn("intake_coverage_status: partial", result.stdout)
            self.assertIn(
                "recommended_followup: run_membership_evidence_import_plan_then_apply_preview",
                result.stdout,
            )
            self.assertFalse(output.exists())
            self.assertFalse(report.exists())
            self.assertFalse(metadata.exists())
            self.assertFalse(review_queue.exists())
            with intake.open(encoding="utf-8-sig", newline="") as handle:
                intake_rows = list(csv.DictReader(handle))
            self.assertEqual([row["expected_ticker"] for row in intake_rows], ["ABT", "ZZZ"])

    def test_cli_validation_reports_invalid_source_file_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            source_file = root / "intake_template_is_not_source.csv"
            output = root / "sources.csv"
            report = root / "sources.md"
            metadata = root / "sources.json"
            intake = root / "intake_template.csv"
            write_template(template)
            write_intake_template(source_file)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "sp500_current_membership_sources.py"),
                    "--template",
                    str(template),
                    "--source-file",
                    str(source_file),
                    "--source-url",
                    "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                    "--as-of-date",
                    "2026-06-30",
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                    "--json-output",
                    str(metadata),
                    "--intake-template",
                    str(intake),
                    "--validate-source-file-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("status: source_file_invalid", result.stdout)
            self.assertIn("validation_only: true", result.stdout)
            self.assertIn("source_file must contain a Symbol or Ticker column", result.stdout)
            self.assertIn(
                "source_file_available_columns: expected_ticker, intake_status, required_source_url, required_source_columns, notes",
                result.stdout,
            )
            self.assertNotIn("Traceback", result.stdout + result.stderr)
            self.assertFalse(output.exists())
            self.assertFalse(report.exists())
            self.assertFalse(metadata.exists())
            self.assertFalse(intake.exists())

    def test_cli_can_write_empty_report_when_fetch_source_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            missing_html = root / "missing.html"
            output = root / "sources.csv"
            report = root / "sources.md"
            metadata = root / "sources.json"
            intake = root / "intake_template.csv"
            source_request = root / "source_file_request.md"
            write_template(template)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "sp500_current_membership_sources.py"),
                    "--template",
                    str(template),
                    "--source-html",
                    str(missing_html),
                    "--source-url",
                    "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                    "--as-of-date",
                    "2026-06-30",
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                    "--json-output",
                    str(metadata),
                    "--intake-template",
                    str(intake),
                    "--source-file-request",
                    str(source_request),
                    "--allow-empty-on-fetch-error",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(len(output.read_text(encoding="utf-8-sig").splitlines()), 1)
            report_text = report.read_text(encoding="utf-8-sig")
            self.assertIn("status: fetch_failed", report_text)
            self.assertIn("missing.html", report_text)
            self.assertIn("official_export_url: https://www.spglobal.com/spdji/en/idsexport/file.xls", report_text)
            payload = json.loads(metadata.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["source_file_intake_template"], str(intake))
            self.assertEqual(payload["recommended_followup"], "provide_official_constituents_csv")
            self.assertEqual(payload["intake_coverage_status"], "none")
            self.assertEqual(payload["intake_expected_count"], 2)
            self.assertEqual(payload["intake_matched_count"], 0)
            self.assertEqual(payload["intake_missing_count"], 2)
            self.assertEqual(payload["intake_missing_tickers"], ["ABT", "ZZZ"])
            self.assertIn("run_sp500_current_membership_sources.ps1", payload["source_file_next_command"])
            self.assertIn("at_least_400_tickers", payload["source_file_acceptance_criteria"])
            self.assertEqual(
                payload["official_export_url"],
                "https://www.spglobal.com/spdji/en/idsexport/file.xls?redesignExport=true&languageId=1&selectedModule=Constituents&selectedSubModule=ConstituentsFullList&indexId=340",
            )
            self.assertEqual([row["ticker"] for row in payload["missing_ticker_review_queue"]], ["ABT", "ZZZ"])
            self.assertEqual(payload["source_file_request_file"], str(source_request))
            request_text = source_request.read_text(encoding="utf-8-sig")
            self.assertIn("# S&P 500 official constituents CSV request", request_text)
            self.assertIn("status: fetch_failed", request_text)
            self.assertIn("official_export_url: https://www.spglobal.com/spdji/en/idsexport/file.xls", request_text)
            self.assertIn("required_columns: Symbol or Ticker", request_text)
            self.assertIn(
                "accepted_ticker_columns: Symbol, Ticker, Ticker Symbol, Constituent Ticker, Constituent Symbol",
                request_text,
            )
            self.assertIn("minimum_official_ticker_count: 400", request_text)
            self.assertIn("source_file_inbox: inputs/sp500_current_membership/official_constituents.csv", request_text)
            self.assertIn("source_file_inbox_exists: false", request_text)
            self.assertIn("source_file_validation_status: missing", request_text)
            self.assertIn("## Current source file inbox fingerprint", request_text)
            self.assertNotIn("## Post-import fingerprint fields", request_text)
            self.assertIn("source_file_inbox_size_bytes: 0", request_text)
            self.assertIn("source_file_inbox_sha256: none", request_text)
            self.assertIn("source_file_inbox_modified_at: none", request_text)
            self.assertIn("dry_run_command:", request_text)
            self.assertIn("inbox_dry_run_command:", request_text)
            self.assertIn("-DryRun -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv", request_text)
            self.assertIn("--validate-source-file-only", request_text)
            self.assertIn("import_command:", request_text)
            self.assertIn("inbox_import_command:", request_text)
            self.assertIn("-SourceFileInbox inputs/sp500_current_membership/official_constituents.csv", request_text)
            self.assertIn("-SourceFile <official_constituents.csv>", request_text)
            self.assertIn("| ABT |", request_text)
            self.assertIn("| ZZZ |", request_text)
            with intake.open(encoding="utf-8-sig", newline="") as handle:
                intake_rows = list(csv.DictReader(handle))
            self.assertEqual(len(intake_rows), 2)
            self.assertEqual(intake_rows[0]["expected_ticker"], "ABT")
            self.assertEqual(intake_rows[0]["required_source_url"], "https://www.spglobal.com/spdji/en/indices/equity/sp-500/")

    def test_fetch_failed_payload_classifies_network_permission_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            write_template(template)

            from sp500_current_membership_sources import (
                build_fetch_failed_payload,
                should_write_source_file_request,
            )

            payload = build_fetch_failed_payload(
                template,
                "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                OSError("[WinError 10013] permission denied by local socket policy"),
                as_of_date="2026-07-03",
            )

            self.assertEqual(payload["fetch_error_type"], "network_permission_denied")
            self.assertFalse(payload["fetch_retryable_without_environment_change"])
            self.assertEqual(payload["fetch_error_next_action"], "provide_official_constituents_csv_or_fix_network_permission")
            self.assertIn("official_source_fetch_blocked_by_permission", payload["source_quality_flags"])
            self.assertTrue(should_write_source_file_request(payload))

    def test_fetch_failed_payload_classifies_official_access_denied_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            write_template(template)

            from sp500_current_membership_sources import build_fetch_failed_payload

            payload = build_fetch_failed_payload(
                template,
                "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                Exception("HTTP Error 403: Forbidden"),
                as_of_date="2026-07-03",
            )

            self.assertEqual(payload["fetch_error_type"], "official_source_access_denied")
            self.assertFalse(payload["fetch_retryable_without_environment_change"])
            self.assertEqual(payload["fetch_error_next_action"], "provide_official_constituents_csv")
            self.assertEqual(payload["next_action"], "provide_official_constituents_csv")
            self.assertIn(
                "official_source_fetch_blocked_by_remote_access_policy",
                payload["source_quality_flags"],
            )

    def test_powershell_wrapper_static_contract(self):
        wrapper = (PROJECT_ROOT / "scripts" / "run_sp500_current_membership_sources.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("sp500_current_membership_sources.py", wrapper)
        self.assertIn("us_sp500_current_membership_sources_template.csv", wrapper)
        self.assertIn("us_sp500_current_membership_sources.csv", wrapper)
        self.assertIn("latest_sp500_current_membership_sources.md", wrapper)
        self.assertIn("latest_sp500_current_membership_sources.json", wrapper)
        self.assertIn("sp500_current_membership_source_intake_template.csv", wrapper)
        self.assertIn("--source-url", wrapper)
        self.assertIn("SourceFile", wrapper)
        self.assertIn("SourceFileInbox", wrapper)
        self.assertIn("CrosscheckConstituentsFile", wrapper)
        self.assertIn("UserAgent", wrapper)
        self.assertIn("--user-agent", wrapper)
        self.assertIn("--source-file-inbox", wrapper)
        self.assertIn("inputs\\sp500_current_membership\\official_constituents.csv", wrapper)
        self.assertIn("sp500_crosscheck_*", wrapper)
        self.assertIn("sp500_full_constituents_crosscheck_*.xlsx", wrapper)
        self.assertIn("--crosscheck-constituents-file", wrapper)
        self.assertIn("--validate-source-file-only", wrapper)
        self.assertIn("--source-file", wrapper)
        self.assertIn("--output", wrapper)
        self.assertIn("--json-output", wrapper)
        self.assertIn("--intake-template", wrapper)
        self.assertIn("ReviewQueueOutput", wrapper)
        self.assertIn("--review-queue-output", wrapper)
        self.assertIn("sp500_current_membership_source_review_queue.csv", wrapper)
        self.assertIn("SourceFileRequest", wrapper)
        self.assertIn("--source-file-request", wrapper)
        self.assertIn("sp500_current_membership_source_file_request.md", wrapper)
        self.assertIn("--allow-empty-on-fetch-error", wrapper)

    def test_powershell_wrapper_dry_run_uses_existing_source_file_inbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_file = Path(tmp) / "official_constituents.csv"
            write_official_csv_for_project_template(source_file)

            result = subprocess.run(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "scripts\\run_sp500_current_membership_sources.ps1",
                    "-ProjectRoot",
                    str(PROJECT_ROOT),
                    "-SourceFileInbox",
                    str(source_file),
                    "-DryRun",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertIn("SourceFile: " + str(source_file), output)
            self.assertIn("validation_only: true", output)
            self.assertIn("matched_count: 50", output)

    def test_powershell_wrapper_dry_run_accepts_official_csv_with_metadata_preamble(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_file = Path(tmp) / "official_constituents.csv"
            write_official_csv_with_metadata_preamble(source_file)

            result = subprocess.run(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "scripts\\run_sp500_current_membership_sources.ps1",
                    "-ProjectRoot",
                    str(PROJECT_ROOT),
                    "-SourceFileInbox",
                    str(source_file),
                    "-DryRun",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertIn("validation_only: true", output)
            self.assertIn("source_file_ticker_columns: Symbol", output)
            self.assertIn("matched_count: 2", output)

    def test_inbox_status_reports_missing_official_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            inbox = root / "inputs" / "official_constituents.csv"
            output = root / "latest_inbox_status.json"
            report = root / "latest_inbox_status.md"
            write_template(template)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "sp500_current_membership_source_inbox_status.py"),
                    "--template",
                    str(template),
                    "--source-file-inbox",
                    str(inbox),
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                    "--as-of-date",
                    "2026-07-03",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["status_schema"], "sp500_current_membership_source_inbox_status")
            self.assertEqual(payload["status"], "missing")
            self.assertFalse(payload["source_file_inbox_exists"])
            self.assertEqual(payload["next_action"], "place_official_constituents_csv")
            self.assertTrue(payload["external_input_required"])
            self.assertEqual(payload["blocking_reason"], "official_constituents_csv_missing")
            self.assertEqual(payload["blocking_input"], str(inbox))
            self.assertEqual(
                payload["source_file_user_agent_hint"],
                "Set SEC_USER_AGENT or pass -UserAgent <user_agent> when retrying official S&P Global fetches through PowerShell entrypoints.",
            )
            self.assertEqual(
                payload["official_export_url"],
                "https://www.spglobal.com/spdji/en/idsexport/file.xls?redesignExport=true&languageId=1&selectedModule=Constituents&selectedSubModule=ConstituentsFullList&indexId=340",
            )
            self.assertEqual(payload["requested_count"], 2)
            report_text = report.read_text(encoding="utf-8-sig")
            self.assertIn("status: missing", report_text)
            self.assertIn("external_input_required: true", report_text)
            self.assertIn("blocking_reason: official_constituents_csv_missing", report_text)
            self.assertIn("source_file_user_agent_hint: Set SEC_USER_AGENT", report_text)
            self.assertIn("official_export_url: https://www.spglobal.com/spdji/en/idsexport/file.xls", report_text)

    def test_inbox_status_reports_secondary_fallback_when_official_csv_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            inbox = root / "inputs" / "official_constituents.csv"
            secondary = root / "data" / "us_universe_symbols.csv"
            output = root / "latest_inbox_status.json"
            report = root / "latest_inbox_status.md"
            write_template(template)
            write_public_constituents_csv(secondary)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "sp500_current_membership_source_inbox_status.py"),
                    "--template",
                    str(template),
                    "--source-file-inbox",
                    str(inbox),
                    "--secondary-constituents-csv",
                    str(secondary),
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["status"], "secondary_fallback_available")
            self.assertFalse(payload["source_file_inbox_exists"])
            self.assertEqual(payload["secondary_constituents_csv"], str(secondary))
            self.assertEqual(payload["parsed_secondary_ticker_count"], 400)
            self.assertFalse(payload["external_input_required"])
            self.assertEqual(payload["blocking_reason"], "")
            self.assertEqual(payload["next_action"], "run_sp500_current_membership_sources_with_secondary_fallback")
            report_text = report.read_text(encoding="utf-8-sig")
            self.assertIn("status: secondary_fallback_available", report_text)
            self.assertIn("external_input_required: false", report_text)

    def test_inbox_status_reports_ready_official_csv_with_intake_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            intake = root / "intake_template.csv"
            inbox = root / "inputs" / "official_constituents.csv"
            output = root / "latest_inbox_status.json"
            report = root / "latest_inbox_status.md"
            write_template(template)
            write_intake_template(intake)
            write_official_csv(inbox)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "sp500_current_membership_source_inbox_status.py"),
                    "--template",
                    str(template),
                    "--source-file-inbox",
                    str(inbox),
                    "--intake-template",
                    str(intake),
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                    "--as-of-date",
                    "2026-07-03",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["status"], "ready_for_import_preview")
            self.assertEqual(payload["source_file_validation_status"], "ready")
            self.assertEqual(payload["parsed_official_ticker_count"], 400)
            self.assertEqual(payload["intake_coverage_status"], "partial")
            self.assertEqual(payload["intake_expected_count"], 2)
            self.assertEqual(payload["intake_matched_count"], 1)
            self.assertEqual(payload["intake_missing_tickers"], ["ZZZ"])
            self.assertIn("status: ready_for_import_preview", report.read_text(encoding="utf-8-sig"))

    def test_inbox_status_records_source_file_fingerprint_when_csv_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            inbox = root / "inputs" / "official_constituents.csv"
            output = root / "latest_inbox_status.json"
            report = root / "latest_inbox_status.md"
            write_template(template)
            write_official_csv(inbox)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "sp500_current_membership_source_inbox_status.py"),
                    "--template",
                    str(template),
                    "--source-file-inbox",
                    str(inbox),
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                    "--as-of-date",
                    "2026-07-03",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8-sig"))
            expected_sha256 = hashlib.sha256(inbox.read_bytes()).hexdigest()
            self.assertEqual(payload["source_file_inbox_size_bytes"], inbox.stat().st_size)
            self.assertEqual(payload["source_file_inbox_sha256"], expected_sha256)
            self.assertRegex(payload["source_file_inbox_modified_at"], r"^\d{4}-\d{2}-\d{2}T")
            report_text = report.read_text(encoding="utf-8-sig")
            self.assertIn(f"source_file_inbox_size_bytes: {inbox.stat().st_size}", report_text)
            self.assertIn(f"source_file_inbox_sha256: {expected_sha256}", report_text)

    def test_inbox_status_reports_common_official_csv_ticker_symbol_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            inbox = root / "inputs" / "official_constituents.csv"
            output = root / "latest_inbox_status.json"
            report = root / "latest_inbox_status.md"
            write_template(template)
            write_official_csv_with_ticker_symbol_column(inbox)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "sp500_current_membership_source_inbox_status.py"),
                    "--template",
                    str(template),
                    "--source-file-inbox",
                    str(inbox),
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                    "--as-of-date",
                    "2026-07-03",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["status"], "ready_for_import_preview")
            self.assertEqual(payload["source_file_ticker_columns"], ["Ticker Symbol"])
            self.assertIn(
                "source_file_ticker_columns: Ticker Symbol",
                report.read_text(encoding="utf-8-sig"),
            )

    def test_inbox_status_accepts_official_csv_with_metadata_preamble(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            inbox = root / "inputs" / "official_constituents.csv"
            output = root / "latest_inbox_status.json"
            report = root / "latest_inbox_status.md"
            write_template(template)
            write_official_csv_with_metadata_preamble(inbox)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "sp500_current_membership_source_inbox_status.py"),
                    "--template",
                    str(template),
                    "--source-file-inbox",
                    str(inbox),
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                    "--as-of-date",
                    "2026-07-03",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["status"], "ready_for_import_preview")
            self.assertEqual(payload["source_file_ticker_columns"], ["Symbol"])
            self.assertEqual(payload["parsed_official_ticker_count"], 400)
            self.assertIn("source_file_ticker_columns: Symbol", report.read_text(encoding="utf-8-sig"))

    def test_inbox_status_rejects_incomplete_official_csv_with_machine_readable_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            inbox = root / "inputs" / "official_constituents.csv"
            output = root / "latest_inbox_status.json"
            report = root / "latest_inbox_status.md"
            write_template(template)
            write_incomplete_official_csv(inbox)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "sp500_current_membership_source_inbox_status.py"),
                    "--template",
                    str(template),
                    "--source-file-inbox",
                    str(inbox),
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                    "--as-of-date",
                    "2026-07-03",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["status"], "incomplete")
            self.assertEqual(payload["source_file_validation_status"], "incomplete")
            self.assertTrue(payload["external_input_required"])
            self.assertEqual(payload["blocking_reason"], "official_constituents_csv_incomplete")
            self.assertEqual(
                payload["source_file_rejection_reason"],
                "official_ticker_count_below_minimum",
            )
            self.assertEqual(payload["parsed_official_ticker_count"], 2)
            self.assertEqual(payload["minimum_official_ticker_count"], 400)
            self.assertIn(
                "source_file_rejection_reason: official_ticker_count_below_minimum",
                report.read_text(encoding="utf-8-sig"),
            )

    def test_inbox_status_reports_invalid_source_file_available_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            inbox = root / "inputs" / "official_constituents.csv"
            output = root / "latest_inbox_status.json"
            report = root / "latest_inbox_status.md"
            write_template(template)
            write_intake_template(inbox)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "sp500_current_membership_source_inbox_status.py"),
                    "--template",
                    str(template),
                    "--source-file-inbox",
                    str(inbox),
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                    "--as-of-date",
                    "2026-07-03",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["status"], "invalid")
            self.assertTrue(payload["source_file_is_intake_template"])
            self.assertEqual(
                payload["source_file_rejection_reason"],
                "intake_template_submitted_as_official_csv",
            )
            self.assertEqual(
                payload["source_file_available_columns"],
                [
                    "expected_ticker",
                    "intake_status",
                    "required_source_url",
                    "required_source_columns",
                    "notes",
                ],
            )
            self.assertIn(
                "source_file_available_columns: expected_ticker, intake_status, required_source_url, required_source_columns, notes",
                report.read_text(encoding="utf-8-sig"),
            )
            self.assertIn(
                "source_file_rejection_reason: intake_template_submitted_as_official_csv",
                report.read_text(encoding="utf-8-sig"),
            )

    def test_inbox_status_powershell_wrapper_static_contract(self):
        wrapper = (
            PROJECT_ROOT / "scripts" / "check_sp500_current_membership_source_inbox.ps1"
        ).read_text(encoding="utf-8-sig")

        self.assertIn("sp500_current_membership_source_inbox_status.py", wrapper)
        self.assertIn("official_constituents.csv", wrapper)
        self.assertIn("sp500_current_membership_source_intake_template.csv", wrapper)
        self.assertIn("latest_sp500_current_membership_source_inbox_status.json", wrapper)
        self.assertIn("latest_sp500_current_membership_source_inbox_status.md", wrapper)
        self.assertIn("--source-file-inbox", wrapper)
        self.assertIn("--intake-template", wrapper)


if __name__ == "__main__":
    unittest.main()
