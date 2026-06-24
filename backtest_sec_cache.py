import argparse
import csv
from pathlib import Path

from sec_edgar_adapter import cik_to_10_digits, load_company_facts


def _read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _membership_ciks(rows):
    seen = set()
    ciks = []
    for row in rows:
        raw = str(row.get("cik", "")).strip()
        if not raw:
            continue
        cik = cik_to_10_digits(raw)
        if cik not in seen:
            seen.add(cik)
            ciks.append(cik)
    if not ciks:
        raise ValueError("membership input must contain at least one CIK")
    return ciks


def prepare_company_facts_cache(
    membership_path,
    cache_dir,
    user_agent,
    minimum_coverage=0.80,
    max_age_hours=168,
    fetcher=None,
):
    if not user_agent:
        raise ValueError("SEC user_agent is required")

    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    ciks = _membership_ciks(_read_csv(membership_path))
    ready_count = 0
    cache_hits = 0
    failures = []

    for cik in ciks:
        cache_file = cache / f"CIK{cik}.json"
        was_cached = cache_file.exists()
        try:
            load_company_facts(
                cik,
                user_agent=user_agent,
                cache_dir=cache,
                max_age_hours=max_age_hours,
                fetcher=fetcher,
            )
        except Exception as exc:
            failures.append({"cik": cik, "error": str(exc)})
            continue
        ready_count += 1
        if was_cached:
            cache_hits += 1

    company_count = len(ciks)
    coverage = ready_count / company_count if company_count else 0.0
    if coverage < minimum_coverage:
        raise RuntimeError(f"SEC company facts coverage {coverage:.2%} below required {minimum_coverage:.2%}")

    return {
        "company_count": company_count,
        "ready_count": ready_count,
        "coverage": coverage,
        "cache_hits": cache_hits,
        "failures": failures,
        "cache_dir": cache,
    }


def main():
    parser = argparse.ArgumentParser(description="Prepare SEC Company Facts cache for point-in-time backtests.")
    parser.add_argument("--membership", required=True)
    parser.add_argument("--cache-dir", required=True)
    parser.add_argument("--user-agent", required=True)
    parser.add_argument("--minimum-coverage", type=float, default=0.80)
    parser.add_argument("--max-age-hours", type=float, default=168)
    args = parser.parse_args()
    result = prepare_company_facts_cache(
        args.membership,
        args.cache_dir,
        args.user_agent,
        minimum_coverage=args.minimum_coverage,
        max_age_hours=args.max_age_hours,
    )
    print(f"SEC Company Facts coverage: {result['ready_count']}/{result['company_count']}")
    print(f"SEC Company Facts cache hits: {result['cache_hits']}")
    print(f"SEC Company Facts cache: {result['cache_dir']}")


if __name__ == "__main__":
    main()
