import csv
import copy
import tempfile
import unittest
from pathlib import Path

from historical_sp500 import (
    EVIDENCE_LEVELS,
    MEMBERSHIP_FIELDS,
    build_weekly_membership,
    parse_change_events_html,
    restore_membership,
    write_historical_membership_csv,
)


def constituent(ticker, name, evidence="verified", source_url="https://example.com/current"):
    return {
        "ticker": ticker,
        "company_name": name,
        "effective_date": "2026-01-01",
        "membership_evidence": evidence,
        "membership_source_url": source_url,
    }


def event(date, added, removed, added_name="Added Co", removed_name="Removed Co", **extra):
    row = {
        "effective_date": date,
        "added_ticker": added,
        "added_company_name": added_name,
        "removed_ticker": removed,
        "removed_company_name": removed_name,
        "membership_evidence": "secondary",
        "membership_source_url": "https://example.com/change",
    }
    row.update(extra)
    return row


def changes_html():
    return """
    <table class="wikitable" id="changes">
      <tr><th>Date</th><th colspan="2">Added</th><th colspan="2">Removed</th><th>Reason</th></tr>
      <tr><th></th><th>Ticker</th><th>Security</th><th>Ticker</th><th>Security</th><th></th></tr>
      <tr><td>June 3, 2025</td><td>new.a</td><td>New &amp; Co</td><td>old.b</td><td>Old Co</td><td>Rebalance</td></tr>
    </table>
    """


class HistoricalSp500Tests(unittest.TestCase):
    def test_reverse_one_event(self):
        current = {"NEW": constituent("NEW", "New Co")}
        events = [event("2025-06-01", "NEW", "OLD", removed_name="Old Co")]

        restored = restore_membership(current, events, "2025-05-31")

        self.assertEqual(["OLD"], sorted(restored))
        self.assertEqual("Old Co", restored["OLD"]["company_name"])
        self.assertEqual("2025-06-01", restored["OLD"]["effective_date"])
        self.assertEqual("secondary", restored["OLD"]["membership_evidence"])
        self.assertEqual("https://example.com/change", restored["OLD"]["membership_source_url"])

    def test_same_date_code_change_is_deterministic(self):
        current = {"CCC": constituent("CCC", "Final Co")}
        changes = [
            event("2025-06-01", "BBB", "AAA", added_name="Middle Co", removed_name="Original Co"),
            event("2025-06-01", "CCC", "BBB", added_name="Final Co", removed_name="Middle Co"),
        ]

        first = restore_membership(current, changes, "2025-05-31")
        second = restore_membership(current, list(reversed(changes)), "2025-05-31")

        self.assertEqual(first, second)
        self.assertEqual(["AAA"], sorted(first))

    def test_duplicate_and_conflicting_events_are_rejected(self):
        duplicate = event("2025-06-01", "NEW", "OLD")
        with self.assertRaises(ValueError):
            restore_membership({"NEW": constituent("NEW", "New Co")}, [duplicate, dict(duplicate)], "2025-05-31")

        conflicts = [
            event("2025-06-01", "NEW", "OLD"),
            event("2025-06-01", "NEW", "OTHER"),
        ]
        with self.assertRaises(ValueError):
            restore_membership({"NEW": constituent("NEW", "New Co")}, conflicts, "2025-05-31")

    def test_conflicts_are_rejected_even_when_before_cutoff(self):
        conflicts = [
            event("2025-06-01", "NEW", "OLD"),
            event("2025-06-01", "NEW", "OTHER"),
        ]

        with self.assertRaises(ValueError):
            restore_membership({"NEW": constituent("NEW", "New Co")}, conflicts, "2025-06-02")

    def test_insufficient_evidence_is_retained(self):
        change = event(
            "2025-06-01",
            "NEW",
            "OLD",
            membership_evidence="insufficient",
            membership_source_url="",
        )

        restored = restore_membership({"NEW": constituent("NEW", "New Co")}, [change], "2025-05-31")

        self.assertEqual("insufficient", restored["OLD"]["membership_evidence"])
        self.assertEqual("", restored["OLD"]["membership_source_url"])

    def test_ticker_normalization_supports_code_changes(self):
        change = event("2025-06-01", "brk.b", "bf.b", removed_name="Brown-Forman")

        restored = restore_membership({"BRK.B": constituent("brk.b", "Berkshire")}, [change], "2025-05-31")

        self.assertEqual(["BF-B"], sorted(restored))
        self.assertEqual("BF-B", restored["BF-B"]["ticker"])

    def test_html_changes_parser_defaults_to_secondary_and_can_upgrade_from_config(self):
        html = changes_html()

        parsed = parse_change_events_html(html)
        verified = parse_change_events_html(
            html,
            evidence_config={
                ("2025-06-03", "NEW-A", "OLD-B"): {"source_url": "https://www.spglobal.com/change"}
            },
        )

        self.assertEqual("2025-06-03", parsed[0]["effective_date"])
        self.assertEqual("NEW-A", parsed[0]["added_ticker"])
        self.assertEqual("Old Co", parsed[0]["removed_company_name"])
        self.assertEqual("secondary", parsed[0]["membership_evidence"])
        self.assertEqual("", parsed[0]["membership_source_url"])
        self.assertEqual("verified", verified[0]["membership_evidence"])

    def test_only_official_spglobal_domains_can_upgrade_to_verified(self):
        official_urls = [
            "https://spglobal.com/spdji/en/announcements/",
            "https://www.spglobal.com/spdji/en/announcements/",
            "https://press.spglobal.com/2025/change",
        ]

        for source_url in official_urls:
            with self.subTest(source_url=source_url):
                parsed = parse_change_events_html(
                    changes_html(),
                    evidence_config={
                        ("2025-06-03", "NEW-A", "OLD-B"): {"source_url": source_url}
                    },
                )
                self.assertEqual("verified", parsed[0]["membership_evidence"])
                self.assertEqual(source_url, parsed[0]["membership_source_url"])

    def test_non_first_party_and_lookalike_urls_remain_secondary(self):
        rejected_urls = [
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            "https://example.test/change",
            "https://spglobal.com.example.test/change",
            "https://notspglobal.com/change",
            "https://spglobal-example.com/change",
            "https://spglobal.com@example.test/change",
            "spglobal.com/change",
            "javascript:https://spglobal.com/change",
            "https://spglobal.com:bad/change",
            "https://[spglobal.com/change",
            "not a url",
            "",
        ]

        for source_url in rejected_urls:
            with self.subTest(source_url=source_url):
                parsed = parse_change_events_html(
                    changes_html(),
                    evidence_config={
                        ("2025-06-03", "NEW-A", "OLD-B"): {"source_url": source_url}
                    },
                )
                self.assertEqual("secondary", parsed[0]["membership_evidence"])
                self.assertEqual(source_url.strip(), parsed[0]["membership_source_url"])

    def test_invalid_dates_and_evidence_are_rejected(self):
        with self.assertRaises(ValueError):
            restore_membership({}, [event("2025-02-30", "NEW", "OLD")], "2025-01-01")
        with self.assertRaises(ValueError):
            restore_membership({}, [], "June 1, 2025")
        with self.assertRaises(ValueError):
            restore_membership(
                {"NEW": constituent("NEW", "New Co")},
                [event("2025-06-01", "NEW", "OLD", membership_evidence="unknown")],
                "2025-05-31",
            )
        invalid_current = constituent("NEW", "New Co")
        invalid_current["effective_date"] = "2025-13-01"
        with self.assertRaises(ValueError):
            restore_membership({"NEW": invalid_current}, [], "2025-05-31")

    def test_input_objects_are_not_mutated(self):
        current = {"new": constituent("new", "New Co")}
        events = [event("2025-06-01", "new", "old")]
        current_before = copy.deepcopy(current)
        events_before = copy.deepcopy(events)

        restore_membership(current, events, "2025-05-31")

        self.assertEqual(current_before, current)
        self.assertEqual(events_before, events)

    def test_156_weeks_are_stably_sorted(self):
        current = {
            "ZZZ": constituent("ZZZ", "Z Co"),
            "AAA": constituent("AAA", "A Co"),
        }
        weeks = [f"2025-{month:02d}-{day:02d}" for month in range(12, 0, -1) for day in range(28, 15, -1)]

        rows = build_weekly_membership(current, [], weeks)

        self.assertEqual(156, len(weeks))
        self.assertEqual(312, len(rows))
        self.assertEqual(sorted((row["week"], row["ticker"]) for row in rows), [(row["week"], row["ticker"]) for row in rows])
        self.assertEqual(MEMBERSHIP_FIELDS, list(rows[0]))

    def test_atomic_csv_output_has_utf8_bom_and_replaces_existing_file(self):
        rows = build_weekly_membership(
            {"AAA": constituent("AAA", "中文公司")}, [], ["2025-01-03"]
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "historical_membership.csv"
            output.write_text("stale", encoding="utf-8")

            write_historical_membership_csv(output, rows)

            self.assertTrue(output.read_bytes().startswith(b"\xef\xbb\xbf"))
            with output.open(encoding="utf-8-sig", newline="") as stream:
                written = list(csv.DictReader(stream))
            self.assertEqual("中文公司", written[0]["company_name"])
            self.assertEqual(MEMBERSHIP_FIELDS, list(written[0]))
            self.assertEqual([], list(output.parent.glob(f".{output.name}.*.tmp")))

    def test_public_constants(self):
        self.assertEqual({"verified", "secondary", "insufficient"}, EVIDENCE_LEVELS)
        self.assertEqual(
            [
                "week",
                "ticker",
                "company_name",
                "effective_date",
                "membership_evidence",
                "membership_source_url",
            ],
            MEMBERSHIP_FIELDS,
        )


if __name__ == "__main__":
    unittest.main()
