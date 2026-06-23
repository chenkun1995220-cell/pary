import csv
import copy
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

from historical_sp500 import (
    EVIDENCE_LEVELS,
    MEMBERSHIP_FIELDS,
    build_weekly_membership,
    load_change_events_csv,
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


def changes_html_with_interference():
    return """
    <table class="wikitable" id="interference">
      <tr><th>Date</th><th>Removed</th><th>Added</th><th>Reason</th></tr>
      <tr><th>Ticker</th><th>Ticker</th><th>Ticker</th><th>Reason</th></tr>
      <tr><td>June 1, 2025</td><td>BAD</td><td>WORSE</td><td>Noise row</td></tr>
    </table>
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
            evidence_config={("2025-06-03", "NEW-A", "OLD-B"): "https://www.spglobal.com/change"},
        )

        self.assertEqual("2025-06-03", parsed[0]["effective_date"])
        self.assertEqual("NEW-A", parsed[0]["added_ticker"])
        self.assertEqual("Old Co", parsed[0]["removed_company_name"])
        self.assertEqual("secondary", parsed[0]["membership_evidence"])
        self.assertEqual("", parsed[0]["membership_source_url"])
        self.assertEqual("verified", verified[0]["membership_evidence"])

    def test_html_changes_parser_respects_explicit_evidence_and_source_fields_in_config(self):
        html = changes_html()
        official_key = ("2025-06-03", "NEW-A", "OLD-B")

        downgraded = parse_change_events_html(
            html,
            evidence_config={
                official_key: {
                    "membership_evidence": "secondary",
                    "membership_source_url": "https://www.spglobal.com/spdji/en/announcements/",
                }
            },
        )
        self.assertEqual("secondary", downgraded[0]["membership_evidence"])

        non_official = parse_change_events_html(
            html,
            evidence_config={
                official_key: {
                    "membership_evidence": "verified",
                    "membership_source_url": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
                }
            },
        )
        self.assertEqual("secondary", non_official[0]["membership_evidence"])

        official = parse_change_events_html(
            html,
            evidence_config={
                official_key: {
                    "membership_evidence": "verified",
                    "membership_source_url": "https://www.spglobal.com/spdji/en/announcements/",
                }
            },
        )
        self.assertEqual("verified", official[0]["membership_evidence"])

    def test_html_changes_parser_rejects_invalid_date_after_data_begins(self):
        html = changes_html().replace(
            "</table>",
            "<tr><td>not a date</td><td>BAD</td><td>Bad Co</td>"
            "<td>OLD</td><td>Old Co</td><td>Bad date</td></tr></table>",
        )

        with self.assertRaises(ValueError) as raised:
            parse_change_events_html(html)

        self.assertIn("row 4", str(raised.exception))
        self.assertIn("not a date", str(raised.exception))
        self.assertIn("BAD", str(raised.exception))

    def test_html_changes_parser_rejects_bad_five_cell_date_after_data_begins(self):
        html = changes_html().replace(
            "</table>",
            "<tr><td>not a date</td><td>NEW</td><td>New Co</td>"
            "<td>OLD</td><td>Old Co</td></tr></table>",
        )

        with self.assertRaises(ValueError) as raised:
            parse_change_events_html(html)

        self.assertIn("row 4", str(raised.exception))
        self.assertIn("not a date", str(raised.exception))

    def test_html_changes_parser_rejects_bad_first_data_row(self):
        html = changes_html().replace(
            "      <tr><td>June 3, 2025</td><td>new.a</td><td>New &amp; Co</td><td>old.b</td><td>Old Co</td><td>Rebalance</td></tr>\n",
            "<tr><td>???</td><td>BAD</td><td>Bad Co</td><td>OLD</td><td>Old Co</td><td>Bad first</td></tr>\n"
            "<tr><td>June 10, 2025</td><td>new.a</td><td>New &amp; Co</td><td>old.b</td><td>Old Co</td><td>Rebalance</td></tr>\n",
        )

        with self.assertRaises(ValueError) as raised:
            parse_change_events_html(html)

        self.assertIn("row 3", str(raised.exception))
        self.assertIn("BAD", str(raised.exception))

    def test_html_changes_parser_rejects_invalid_evidence_entry_in_config(self):
        official_key = ("2025-06-03", "NEW-A", "OLD-B")

        for entry in ([1, 2, 3], 10):
            with self.subTest(entry_type=type(entry).__name__):
                with self.assertRaisesRegex(ValueError, "invalid evidence_config|event"):
                    parse_change_events_html(
                        changes_html(),
                        evidence_config={official_key: entry},
                    )

    def test_html_changes_parser_allows_blank_date_five_cell_continuation(self):
        html = changes_html().replace(
            "</table>",
            "<tr><td>  </td><td>NEXT</td><td>Next Co</td>"
            "<td>PREV</td><td>Prev Co</td></tr></table>",
        )

        parsed = parse_change_events_html(html)

        self.assertEqual(2, len(parsed))
        self.assertEqual("2025-06-03", parsed[1]["effective_date"])
        self.assertEqual("NEXT", parsed[1]["added_ticker"])
        self.assertEqual("PREV", parsed[1]["removed_ticker"])
        self.assertEqual("", parsed[1]["reason"])

    def test_html_changes_parser_allows_blank_date_six_cell_continuation_with_reason(self):
        html = changes_html().replace(
            "</table>",
            "<tr><td>  </td><td>NEXT</td><td>Next Co</td>"
            "<td>PREV</td><td>Prev Co</td><td>Carry forward</td></tr></table>",
        )

        parsed = parse_change_events_html(html)

        self.assertEqual(2, len(parsed))
        self.assertEqual("2025-06-03", parsed[1]["effective_date"])
        self.assertEqual("NEXT", parsed[1]["added_ticker"])
        self.assertEqual("PREV", parsed[1]["removed_ticker"])
        self.assertEqual("Carry forward", parsed[1]["reason"])

    def test_html_changes_parser_rejects_bad_six_cell_date_after_data_begins(self):
        html = changes_html().replace(
            "</table>",
            "<tr><td>not a date</td><td>NEW</td><td>New Co</td>"
            "<td>OLD</td><td>Old Co</td><td>Bad six</td></tr></table>",
        )

        with self.assertRaises(ValueError) as raised:
            parse_change_events_html(html)

        self.assertIn("row 4", str(raised.exception))
        self.assertIn("not a date", str(raised.exception))
        self.assertIn("NEW", str(raised.exception))

    def test_html_changes_parser_skips_interference_table_and_uses_real_target_table(self):
        parsed = parse_change_events_html(changes_html_with_interference())

        self.assertEqual(1, len(parsed))
        self.assertEqual("NEW-A", parsed[0]["added_ticker"])
        self.assertEqual("OLD-B", parsed[0]["removed_ticker"])

    def test_html_changes_parser_rejects_short_row_after_data_begins(self):
        html = changes_html().replace(
            "</table>",
            "<tr><td>June 10, 2025</td><td>SHORT</td></tr></table>",
        )

        with self.assertRaises(ValueError) as raised:
            parse_change_events_html(html)

        self.assertIn("row 4", str(raised.exception))
        self.assertIn("June 10, 2025", str(raised.exception))
        self.assertIn("SHORT", str(raised.exception))

    def test_html_changes_parser_rejects_short_first_data_row(self):
        html = changes_html().replace(
            "</table>",
            "<tr><td>June 10, 2025</td><td>SHORT</td></tr>"
            "<tr><td>June 11, 2025</td><td>NEW</td><td>New Co</td><td>OLD</td><td>Old Co</td><td>Next</td></tr></table>",
        )

        with self.assertRaises(ValueError) as raised:
            parse_change_events_html(html)

        self.assertIn("row 4", str(raised.exception))
        self.assertIn("June 10, 2025", str(raised.exception))
        self.assertIn("SHORT", str(raised.exception))

    def test_html_changes_parser_rejects_empty_tickers_after_data_begins(self):
        html = changes_html().replace(
            "</table>",
            "<tr><td>June 10, 2025</td><td></td><td>Added Name</td>"
            "<td></td><td>Removed Name</td><td>Missing tickers</td></tr></table>",
        )

        with self.assertRaises(ValueError) as raised:
            parse_change_events_html(html)

        self.assertIn("row 4", str(raised.exception))
        self.assertIn("June 10, 2025", str(raised.exception))
        self.assertIn("Missing tickers", str(raised.exception))

    def test_html_changes_parser_rejects_incomplete_membership_transitions(self):
        cases = [
            (
                "missing-added",
                "<tr><td>June 10, 2025</td><td></td><td>Added Name</td>"
                "<td>OLD</td><td>Removed Name</td><td>Missing added</td></tr>",
                "OLD",
            ),
            (
                "missing-removed",
                "<tr><td>June 10, 2025</td><td>NEW</td><td>Added Name</td>"
                "<td></td><td>Removed Name</td><td>Missing removed</td></tr>",
                "NEW",
            ),
        ]

        for name, row, ticker in cases:
            with self.subTest(name=name):
                html = changes_html().replace("</table>", f"{row}</table>")

                with self.assertRaisesRegex(ValueError, "incomplete membership transition") as raised:
                    parse_change_events_html(html)

                self.assertIn("row 4", str(raised.exception))
                self.assertIn("June 10, 2025", str(raised.exception))
                self.assertIn(ticker, str(raised.exception))

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
                        ("2025-06-03", "NEW-A", "OLD-B"): {
                            "source_url": source_url,
                            "membership_evidence": "verified",
                        }
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

    def test_load_change_events_csv_normalizes_rows_and_legacy_source_url(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=[
                        "effective_date",
                        "added_ticker",
                        "added_company",
                        "removed_ticker",
                        "removed_company",
                        "membership_evidence",
                        "source_url",
                        "reason",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "effective_date": "2025-06-01",
                        "added_ticker": "new.a",
                        "added_company": "New Co",
                        "removed_ticker": "old.b",
                        "removed_company": "Old Co",
                        "membership_evidence": "verified",
                        "source_url": "https://www.spglobal.com/change",
                        "reason": "Rebalance",
                    }
                )

            loaded = load_change_events_csv(path)

        self.assertEqual(
            [
                {
                    "effective_date": "2025-06-01",
                    "added_ticker": "NEW-A",
                    "added_company_name": "New Co",
                    "removed_ticker": "OLD-B",
                    "removed_company_name": "Old Co",
                    "membership_evidence": "verified",
                    "membership_source_url": "https://www.spglobal.com/change",
                    "reason": "Rebalance",
                }
            ],
            loaded,
        )

    def test_load_change_events_csv_downgrades_unofficial_verified_sources(self):
        cases = [
            (
                "wikipedia",
                "membership_source_url",
                "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            ),
            (
                "lookalike",
                "membership_source_url",
                "https://spglobal.com.example.test/change",
            ),
            (
                "http",
                "source_url",
                "http://www.spglobal.com/change",
            ),
        ]

        with tempfile.TemporaryDirectory() as directory:
            for name, source_field, source_url in cases:
                with self.subTest(name=name):
                    path = Path(directory) / f"{name}.csv"
                    fieldnames = [
                        "effective_date",
                        "added_ticker",
                        "removed_ticker",
                        "membership_evidence",
                        source_field,
                    ]
                    with path.open("w", encoding="utf-8", newline="") as stream:
                        writer = csv.DictWriter(stream, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerow(
                            {
                                "effective_date": "2025-06-01",
                                "added_ticker": "NEW",
                                "removed_ticker": "OLD",
                                "membership_evidence": "verified",
                                source_field: source_url,
                            }
                        )

                    loaded = load_change_events_csv(path)

                    self.assertEqual("secondary", loaded[0]["membership_evidence"])
                    self.assertEqual(source_url, loaded[0]["membership_source_url"])

    def test_restore_membership_downgrades_unofficial_current_verified_sources(self):
        current = {
            "WIKI": constituent(
                "WIKI",
                "Wikipedia Sourced",
                source_url="https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            ),
            "LOOK": constituent(
                "LOOK",
                "Lookalike",
                source_url="https://spglobal.com.example.test/current",
            ),
            "HTTP": constituent(
                "HTTP",
                "HTTP Source",
                source_url="http://www.spglobal.com/current",
            ),
            "OFF": constituent(
                "OFF",
                "Official Source",
                source_url="https://www.spglobal.com/current",
            ),
            "LEG": {
                "ticker": "LEG",
                "company_name": "Legacy Source",
                "membership_evidence": "verified",
                "source_url": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            },
        }

        restored = restore_membership(current, [], "2025-05-31")

        self.assertEqual("secondary", restored["WIKI"]["membership_evidence"])
        self.assertEqual("secondary", restored["LOOK"]["membership_evidence"])
        self.assertEqual("secondary", restored["HTTP"]["membership_evidence"])
        self.assertEqual("verified", restored["OFF"]["membership_evidence"])
        self.assertEqual("secondary", restored["LEG"]["membership_evidence"])
        self.assertEqual(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            restored["LEG"]["membership_source_url"],
        )

    def test_load_change_events_csv_rejects_bad_data_rows(self):
        cases = [
            (
                "bad-date",
                "effective_date,added_ticker,removed_ticker,membership_evidence\nnot a date,NEW,OLD,secondary\n",
                "line 2",
            ),
            (
                "bad-evidence",
                "effective_date,added_ticker,removed_ticker,membership_evidence\n2025-06-01,NEW,OLD,unknown\n",
                "line 2",
            ),
            (
                "short-row",
                "effective_date,added_ticker,removed_ticker,membership_evidence\n2025-06-01,NEW\n",
                "line 2",
            ),
        ]

        with tempfile.TemporaryDirectory() as directory:
            for name, content, message in cases:
                with self.subTest(name=name):
                    path = Path(directory) / f"{name}.csv"
                    path.write_text(content, encoding="utf-8")

                    with self.assertRaisesRegex(ValueError, message):
                        load_change_events_csv(path)

    def test_load_change_events_csv_rejects_incomplete_membership_transitions(self):
        cases = [
            (
                "missing-added",
                "effective_date,added_ticker,removed_ticker,membership_evidence\n2025-06-01,,OLD,secondary\n",
            ),
            (
                "missing-removed",
                "effective_date,added_ticker,removed_ticker,membership_evidence\n2025-06-01,NEW,,secondary\n",
            ),
        ]

        with tempfile.TemporaryDirectory() as directory:
            for name, content in cases:
                with self.subTest(name=name):
                    path = Path(directory) / f"{name}.csv"
                    path.write_text(content, encoding="utf-8")

                    with self.assertRaisesRegex(ValueError, "incomplete membership transition"):
                        load_change_events_csv(path)

    def test_input_objects_are_not_mutated(self):
        current = {"new": constituent("new", "New Co")}
        events = [event("2025-06-01", "new", "old")]
        current_before = copy.deepcopy(current)
        events_before = copy.deepcopy(events)

        restore_membership(current, events, "2025-05-31")

        self.assertEqual(current_before, current)
        self.assertEqual(events_before, events)

    def test_156_weeks_are_stably_sorted_with_weekly_intervals(self):
        current = {
            "ZZZ": constituent("ZZZ", "Z Co"),
            "AAA": constituent("AAA", "A Co"),
        }
        latest_week = date(2025, 12, 26)
        weeks = [
            (latest_week - timedelta(weeks=offset)).isoformat()
            for offset in range(156)
        ]
        changes = [
            event("2022-12-30", "NEW", "OLD", removed_name="Old Co"),
        ]

        rows = build_weekly_membership(current, changes, weeks)
        row_weeks = sorted({date.fromisoformat(row["week"]) for row in rows})
        intervals = [
            (later - earlier).days
            for earlier, later in zip(row_weeks, row_weeks[1:])
        ]

        self.assertEqual(156, len(weeks))
        self.assertEqual(156, len(row_weeks))
        self.assertEqual(312, len(rows))
        self.assertEqual(sorted((row["week"], row["ticker"]) for row in rows), [(row["week"], row["ticker"]) for row in rows])
        self.assertTrue(all(interval == 7 for interval in intervals))
        self.assertEqual(MEMBERSHIP_FIELDS, list(rows[0]))

    def test_156_weeks_reject_empty_history_events(self):
        latest_week = date(2025, 12, 26)
        weeks = [
            (latest_week - timedelta(weeks=offset)).isoformat()
            for offset in range(156)
        ]

        with self.assertRaisesRegex(ValueError, "coverage|insufficient|history"):
            build_weekly_membership({"AAA": constituent("AAA", "A Co")}, [], weeks)

    def test_156_weeks_reject_insufficient_history_coverage(self):
        latest_week = date(2025, 12, 26)
        weeks = [
            (latest_week - timedelta(weeks=offset)).isoformat()
            for offset in range(156)
        ]
        changes = [event("2023-01-13", "NEW", "OLD")]

        with self.assertRaisesRegex(ValueError, "coverage|insufficient|history"):
            build_weekly_membership({"AAA": constituent("AAA", "A Co")}, changes, weeks)

    def test_156_weeks_require_regular_weekly_intervals(self):
        current = {"ZZZ": constituent("ZZZ", "Z Co")}
        latest_week = date(2025, 12, 26)
        weeks = []
        for offset in range(156):
            if offset == 80:
                weeks.append((latest_week - timedelta(days=offset * 7 + 1)).isoformat())
            else:
                weeks.append((latest_week - timedelta(weeks=offset)).isoformat())

        with self.assertRaisesRegex(ValueError, "weekly|7"):
            build_weekly_membership(
                current,
                [event("2022-12-30", "NEW", "OLD", removed_name="Old Co")],
                weeks,
            )

    def test_default_build_weekly_membership_requires_minimum_weeks(self):
        with self.assertRaisesRegex(ValueError, "minimum|156"):
            build_weekly_membership(
                {"AAA": constituent("AAA", "A Co")},
                [],
                ["2025-01-03", "2025-01-10"],
            )

    def test_build_weekly_membership_can_skip_minimum_weeks_gate(self):
        rows = build_weekly_membership(
            {"AAA": constituent("AAA", "A Co")},
            [],
            ["2025-01-03", "2025-01-10"],
            require_minimum_weeks=False,
        )

        self.assertEqual(2, len(rows))
        self.assertEqual("A Co", rows[0]["company_name"])

    def test_duplicate_weeks_are_rejected(self):
        duplicate_week = "2025-01-03"

        with self.assertRaisesRegex(ValueError, "duplicate week"):
            build_weekly_membership(
                {},
                [],
                [duplicate_week, duplicate_week],
                require_minimum_weeks=False,
            )

    def test_atomic_csv_output_has_utf8_bom_and_replaces_existing_file(self):
        rows = build_weekly_membership(
            {"AAA": constituent("AAA", "中文公司")},
            [],
            ["2025-01-03"],
            require_minimum_weeks=False,
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

    def test_atomic_csv_closes_raw_descriptor_when_fdopen_fails(self):
        original_mkstemp = tempfile.mkstemp
        raw_descriptors = []

        def capture_mkstemp(*args, **kwargs):
            descriptor, name = original_mkstemp(*args, **kwargs)
            raw_descriptors.append(descriptor)
            return descriptor, name

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "historical_membership.csv"
            failure = RuntimeError("fdopen failed")
            try:
                with mock.patch(
                    "historical_sp500.tempfile.mkstemp", side_effect=capture_mkstemp
                ), mock.patch("historical_sp500.os.fdopen", side_effect=failure):
                    with self.assertRaisesRegex(RuntimeError, "fdopen failed"):
                        write_historical_membership_csv(output, [])
                self.assertEqual([], list(output.parent.glob(f".{output.name}.*.tmp")))
            finally:
                for descriptor in raw_descriptors:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass
                for temporary in output.parent.glob(f".{output.name}.*.tmp"):
                    temporary.unlink()

    def test_atomic_csv_preserves_writerows_error_when_cleanup_errors(self):
        original_unlink = Path.unlink

        def unlink_then_error(path, *args, **kwargs):
            original_unlink(path, *args, **kwargs)
            raise PermissionError("cleanup failed")

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "historical_membership.csv"
            writer = mock.Mock()
            writer.writerows.side_effect = RuntimeError("writerows failed")

            with mock.patch("historical_sp500.csv.DictWriter", return_value=writer), mock.patch(
                "historical_sp500.Path.unlink", side_effect=unlink_then_error, autospec=True
            ):
                with self.assertRaisesRegex(RuntimeError, "writerows failed"):
                    write_historical_membership_csv(output, [])

            self.assertEqual([], list(output.parent.glob(f".{output.name}.*.tmp")))

    def test_atomic_csv_removes_temp_when_replace_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "historical_membership.csv"

            with mock.patch(
                "historical_sp500.os.replace", side_effect=RuntimeError("replace failed")
            ):
                with self.assertRaisesRegex(RuntimeError, "replace failed"):
                    write_historical_membership_csv(output, [])

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
