import csv
import tempfile
import unittest
from pathlib import Path

from backtest_membership_inputs import (
    build_backtest_membership,
    prepare_backtest_membership,
    write_backtest_membership_csv,
)


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class BacktestMembershipInputsTests(unittest.TestCase):
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

    def test_evidence_pack_unofficial_verified_source_is_downgraded(self):
        rows = [
            {
                "ticker": "NEW",
                "cik": "1",
                "company_name": "New Co",
                "industry": "Tech",
                "gics_sub_industry": "Software",
                "date_added": "2025-01-01",
                "enabled": "1",
            },
            {
                "ticker": "OLD",
                "cik": "2",
                "company_name": "Old Co",
                "industry": "Tech",
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
                "membership_source_url": "https://example.com/not-official",
            }
        ]

        membership = build_backtest_membership(rows, weeks=1, end_date="2025-01-03", evidence_rows=evidence_rows)

        by_ticker = {row["ticker"]: row for row in membership}
        self.assertEqual(by_ticker["NEW"]["membership_evidence"], "secondary")

    def test_missing_evidence_pack_keeps_secondary_default(self):
        rows = [
            {
                "ticker": "AAPL",
                "cik": "320193",
                "company_name": "Apple Inc.",
                "industry": "Technology",
                "gics_sub_industry": "Hardware",
                "date_added": "2020-01-01",
                "enabled": "1",
            },
        ]

        membership = build_backtest_membership(rows, weeks=1, end_date="2025-01-03")

        self.assertEqual(membership[0]["membership_evidence"], "secondary")

    def test_evidence_pack_ignores_events_outside_limited_universe(self):
        rows = [
            {
                "ticker": "AAPL",
                "cik": "320193",
                "company_name": "Apple Inc.",
                "industry": "Technology",
                "gics_sub_industry": "Hardware",
                "date_added": "2020-01-01",
                "enabled": "1",
            },
        ]
        evidence_rows = [
            {
                "effective_date": "2025-09-22",
                "added_ticker": "APP",
                "removed_ticker": "MKTX",
                "membership_evidence": "verified",
                "membership_source_url": "https://www.spglobal.com/spdji/en/documents/indexnews/announcements/example.pdf",
            }
        ]

        membership = build_backtest_membership(
            rows,
            weeks=1,
            end_date="2025-09-19",
            evidence_rows=evidence_rows,
        )

        self.assertEqual(["AAPL"], [row["ticker"] for row in membership])

    def test_prepare_membership_reads_evidence_pack_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            universe = root / "universe.csv"
            evidence_pack = root / "evidence.csv"
            output = root / "membership.csv"
            write_csv(
                universe,
                [
                    {
                        "ticker": "NEW",
                        "cik": "1",
                        "company_name": "New Co",
                        "industry": "Tech",
                        "gics_sub_industry": "Software",
                        "date_added": "2025-01-01",
                        "enabled": "1",
                    },
                    {
                        "ticker": "OLD",
                        "cik": "2",
                        "company_name": "Old Co",
                        "industry": "Tech",
                        "gics_sub_industry": "Hardware",
                        "date_added": "2020-01-01",
                        "enabled": "1",
                    },
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

            with output.open(encoding="utf-8-sig", newline="") as handle:
                loaded = list(csv.DictReader(handle))
            self.assertEqual(result["rows"], 1)
            self.assertEqual(loaded[0]["ticker"], "NEW")
            self.assertEqual(loaded[0]["membership_evidence"], "verified")

    def test_invalid_evidence_pack_fails_before_writing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            universe = root / "universe.csv"
            evidence_pack = root / "evidence.csv"
            output = root / "membership.csv"
            write_csv(
                universe,
                [
                    {
                        "ticker": "NEW",
                        "cik": "1",
                        "company_name": "New Co",
                        "industry": "Tech",
                        "gics_sub_industry": "Software",
                        "date_added": "2025-01-01",
                        "enabled": "1",
                    },
                    {
                        "ticker": "OLD",
                        "cik": "2",
                        "company_name": "Old Co",
                        "industry": "Tech",
                        "gics_sub_industry": "Hardware",
                        "date_added": "2020-01-01",
                        "enabled": "1",
                    },
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

            with self.assertRaisesRegex(ValueError, "effective_date|YYYY-MM-DD"):
                prepare_backtest_membership(
                    universe,
                    output,
                    weeks=1,
                    end_date="2025-01-03",
                    evidence_pack=evidence_pack,
                )

            self.assertFalse(output.exists())

    def test_builds_weekly_membership_with_cik_and_date_added_gate(self):
        rows = [
            {
                "ticker": "AAPL",
                "company_name": "Apple Inc.",
                "industry": "Information Technology",
                "gics_sub_industry": "Technology Hardware",
                "cik": "320193",
                "date_added": "1982-11-30",
                "enabled": "1",
            },
            {
                "ticker": "NEW",
                "company_name": "New Co.",
                "industry": "Industrials",
                "gics_sub_industry": "Machinery",
                "cik": "123456",
                "date_added": "2025-01-10",
                "enabled": "1",
            },
            {
                "ticker": "OLD",
                "company_name": "Disabled Co.",
                "industry": "Utilities",
                "gics_sub_industry": "Utilities",
                "cik": "999999",
                "date_added": "2020-01-01",
                "enabled": "0",
            },
        ]

        membership = build_backtest_membership(rows, weeks=3, end_date="2025-01-17")

        by_week = {}
        for row in membership:
            by_week.setdefault(row["week"], []).append(row["ticker"])
            self.assertEqual(row["market"], "US")
            self.assertEqual(row["membership_evidence"], "secondary")
            self.assertEqual(row["available_at"], row["week"])
        self.assertEqual(by_week["2025-01-03"], ["AAPL"])
        self.assertEqual(by_week["2025-01-10"], ["AAPL", "NEW"])
        self.assertEqual(by_week["2025-01-17"], ["AAPL", "NEW"])
        self.assertEqual({row["cik"] for row in membership}, {"320193", "123456"})

    def test_writes_backtest_membership_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "historical_membership.csv"
            rows = build_backtest_membership(
                [
                    {
                        "ticker": "AAPL",
                        "company_name": "Apple Inc.",
                        "industry": "Information Technology",
                        "cik": "320193",
                        "date_added": "1982-11-30",
                        "enabled": "1",
                    }
                ],
                weeks=1,
                end_date="2025-01-03",
            )

            write_backtest_membership_csv(output, rows)

            with output.open(encoding="utf-8-sig", newline="") as handle:
                loaded = list(csv.DictReader(handle))
            self.assertEqual(loaded[0]["ticker"], "AAPL")
            self.assertEqual(loaded[0]["cik"], "320193")
            self.assertIn("available_at", loaded[0])

    def test_rejects_empty_enabled_universe(self):
        with self.assertRaisesRegex(ValueError, "enabled"):
            build_backtest_membership(
                [{"ticker": "AAPL", "cik": "320193", "date_added": "2020-01-01", "enabled": "0"}],
                weeks=1,
                end_date="2025-01-03",
            )

    def test_company_limit_restricts_each_week_to_stable_ticker_order(self):
        rows = [
            {"ticker": "MSFT", "company_name": "Microsoft", "industry": "Technology", "cik": "789019", "date_added": "1986-03-13", "enabled": "1"},
            {"ticker": "AAPL", "company_name": "Apple", "industry": "Technology", "cik": "320193", "date_added": "1982-11-30", "enabled": "1"},
            {"ticker": "AMZN", "company_name": "Amazon", "industry": "Consumer Discretionary", "cik": "1018724", "date_added": "2005-11-18", "enabled": "1"},
        ]

        membership = build_backtest_membership(rows, weeks=2, end_date="2025-01-10", company_limit=2)

        by_week = {}
        for row in membership:
            by_week.setdefault(row["week"], []).append(row["ticker"])
        self.assertEqual(by_week["2025-01-03"], ["AAPL", "AMZN"])
        self.assertEqual(by_week["2025-01-10"], ["AAPL", "AMZN"])


if __name__ == "__main__":
    unittest.main()
