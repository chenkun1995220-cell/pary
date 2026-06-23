from copy import deepcopy
from datetime import date, datetime

import sec_financial_metrics


def _parse_payload_filed_date(value):
    if not isinstance(value, str):
        return None
    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
        if isinstance(parsed, datetime):
            return parsed.date()
        return parsed
    except (TypeError, ValueError):
        return None


def filter_company_facts_as_of(payload, as_of_date):
    if not isinstance(payload, dict):
        raise TypeError(f"payload must be dict, got {type(payload)!r}")

    as_of = _parse_payload_filed_date(as_of_date)
    if as_of is None:
        raise ValueError("as_of_date must be ISO date string")

    filtered = deepcopy(payload)
    facts = filtered.get("facts")
    if not isinstance(facts, dict):
        return filtered

    for taxonomy in facts.values():
        if not isinstance(taxonomy, dict):
            continue
        for concept_data in taxonomy.values():
            if not isinstance(concept_data, dict):
                continue
            units = concept_data.get("units")
            if not isinstance(units, dict):
                continue

            for unit, entries in list(units.items()):
                if not isinstance(entries, list):
                    continue

                filtered_entries = []
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    filed = _parse_payload_filed_date(entry.get("filed"))
                    if filed is None or filed > as_of:
                        continue
                    filtered_entries.append(entry)

                units[unit] = filtered_entries

    return filtered


def calculate_metrics_as_of(payload, as_of_date):
    filtered = filter_company_facts_as_of(payload, as_of_date)

    metrics = sec_financial_metrics.calculate_financial_metrics(filtered)
    latest_filed = None
    facts = filtered.get("facts", {})
    for taxonomy in facts.values():
        if not isinstance(taxonomy, dict):
            continue
        for concept in taxonomy.values():
            if not isinstance(concept, dict):
                continue
            for unit_entries in concept.get("units", {}).values():
                if not isinstance(unit_entries, list):
                    continue
                for entry in unit_entries:
                    if not isinstance(entry, dict):
                        continue
                    filed = _parse_payload_filed_date(entry.get("filed"))
                    if filed is None:
                        continue
                    if latest_filed is None or filed > latest_filed:
                        latest_filed = filed

    return {
        **metrics,
        "backtest_date": as_of_date,
        "latest_source_filed": latest_filed.isoformat() if latest_filed else "",
        "leakage_status": "ready",
    }
