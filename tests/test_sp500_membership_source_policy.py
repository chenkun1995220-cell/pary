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


if __name__ == "__main__":
    unittest.main()
