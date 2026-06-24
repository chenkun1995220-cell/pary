import csv
import json
import tempfile
import unittest
from pathlib import Path

from backtest_sec_cache import prepare_company_facts_cache


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class BacktestSecCacheTests(unittest.TestCase):
    def test_prepares_unique_company_facts_cache_from_membership_ciks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            membership = root / "historical_membership.csv"
            cache = root / "sec_companyfacts"
            write_csv(
                membership,
                [
                    {"week": "2025-01-03", "ticker": "AAPL", "cik": "320193"},
                    {"week": "2025-01-10", "ticker": "AAPL", "cik": "0000320193"},
                    {"week": "2025-01-03", "ticker": "MSFT", "cik": "789019"},
                ],
            )
            fetched = []

            def fetcher(cik, user_agent):
                fetched.append((cik, user_agent))
                return {"cik": int(cik), "entityName": cik, "facts": {}}

            result = prepare_company_facts_cache(
                membership,
                cache,
                user_agent="Test test@example.com",
                fetcher=fetcher,
                minimum_coverage=1.0,
            )

            self.assertEqual(result["company_count"], 2)
            self.assertEqual(result["ready_count"], 2)
            self.assertEqual([cik for cik, _ in fetched], ["0000320193", "0000789019"])
            self.assertTrue((cache / "CIK0000320193.json").exists())
            self.assertTrue((cache / "CIK0000789019.json").exists())

    def test_reuses_existing_cache_without_fetching(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            membership = root / "historical_membership.csv"
            cache = root / "sec_companyfacts"
            cache.mkdir()
            write_csv(membership, [{"week": "2025-01-03", "ticker": "AAPL", "cik": "320193"}])
            (cache / "CIK0000320193.json").write_text(
                json.dumps({"cik": 320193, "entityName": "Cached Apple", "facts": {}}),
                encoding="utf-8",
            )

            result = prepare_company_facts_cache(
                membership,
                cache,
                user_agent="Test test@example.com",
                fetcher=lambda cik, user_agent: (_ for _ in ()).throw(AssertionError("must not fetch")),
                minimum_coverage=1.0,
            )

            self.assertEqual(result["cache_hits"], 1)
            self.assertEqual(result["ready_count"], 1)

    def test_low_coverage_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            membership = root / "historical_membership.csv"
            write_csv(
                membership,
                [
                    {"week": "2025-01-03", "ticker": "AAPL", "cik": "320193"},
                    {"week": "2025-01-03", "ticker": "MSFT", "cik": "789019"},
                ],
            )

            def fetcher(cik, user_agent):
                if cik == "0000320193":
                    return {"cik": 320193, "facts": {}}
                raise OSError("SEC unavailable")

            with self.assertRaisesRegex(RuntimeError, "SEC company facts coverage"):
                prepare_company_facts_cache(
                    membership,
                    root / "cache",
                    user_agent="Test test@example.com",
                    fetcher=fetcher,
                    minimum_coverage=0.80,
                )

    def test_empty_membership_ciks_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            membership = root / "historical_membership.csv"
            write_csv(membership, [{"week": "2025-01-03", "ticker": "AAPL", "cik": ""}])

            with self.assertRaisesRegex(ValueError, "CIK"):
                prepare_company_facts_cache(
                    membership,
                    root / "cache",
                    user_agent="Test test@example.com",
                    fetcher=lambda cik, user_agent: {"cik": int(cik), "facts": {}},
                )


if __name__ == "__main__":
    unittest.main()
