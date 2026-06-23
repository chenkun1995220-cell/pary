from copy import deepcopy
from datetime import date

import sec_financial_metrics


def _parse_iso_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def filter_company_facts_as_of(payload, as_of_date):
    as_of = _parse_iso_date(as_of_date)
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
                    filed = _parse_iso_date(entry.get("filed"))
                    if filed is None or filed > as_of:
                        continue
                    filtered_entries.append(entry)

                units[unit] = filtered_entries

    return filtered


def calculate_metrics_as_of(payload, as_of_date):
    filtered = filter_company_facts_as_of(payload, as_of_date)

    metrics = sec_financial_metrics.calculate_financial_metrics(filtered)
    latest_filed = ""
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
                    filed = entry.get("filed")
                    if filed is None:
                        continue
                    if filed > latest_filed:
                        latest_filed = filed

    return {
        **metrics,
        "backtest_date": as_of_date,
        "latest_source_filed": latest_filed,
        "leakage_status": "ready",
    }
