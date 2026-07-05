from urllib.parse import urlparse


VERIFIED_SPGLOBAL_HOSTS = {"spglobal.com", "www.spglobal.com"}
VERIFIED_SPGLOBAL_SUFFIXES = (".spglobal.com",)
CROSS_CHECK_HOST_SUFFIXES = (
    ".ishares.com",
    ".blackrock.com",
    ".ssga.com",
    ".vanguard.com",
)
VERIFIED_EVIDENCE_KINDS = {"current_constituents", "index_announcement"}


def _host(url):
    try:
        parsed = urlparse((url or "").strip())
    except ValueError:
        return ""
    return (parsed.hostname or "").lower()


def is_official_spglobal_source(source_url):
    try:
        parsed = urlparse(str(source_url or "").strip())
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return (
        parsed.scheme.lower() == "https"
        and parsed.username is None
        and parsed.password is None
        and parsed.port in {None, 443}
        and (host in VERIFIED_SPGLOBAL_HOSTS or host.endswith(VERIFIED_SPGLOBAL_SUFFIXES))
    )


def _is_cross_check(host):
    return any(host == suffix.lstrip(".") or host.endswith(suffix) for suffix in CROSS_CHECK_HOST_SUFFIXES)


def classify_membership_source(source_url, evidence_kind=""):
    kind = (evidence_kind or "").strip().lower()
    if str(source_url or "").strip().lower() == "local://sp500_crosscheck_substitute":
        return {
            "trust_level": "crosscheck_substitute",
            "can_upgrade_membership": False,
            "reason": "crosscheck_substitute_is_not_official_index_membership_evidence",
        }
    if is_official_spglobal_source(source_url) and kind in VERIFIED_EVIDENCE_KINDS:
        return {
            "trust_level": "verified",
            "can_upgrade_membership": True,
            "reason": "official_spglobal_membership_evidence",
        }
    if _is_cross_check(_host(source_url)):
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


def trusted_membership_evidence(level, source_url, evidence_kind="current_constituents"):
    evidence = str(level or "").strip().lower()
    policy = classify_membership_source(source_url, evidence_kind=evidence_kind)
    if evidence == "verified" and not policy["can_upgrade_membership"]:
        return "secondary"
    return evidence
