from copy import deepcopy
from datetime import date, datetime, timezone

import sec_financial_metrics


def _parse_payload_filed_date(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.date()
        return value.astimezone(timezone.utc)
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
        if isinstance(parsed, datetime):
            if parsed.tzinfo is None:
                return parsed.date()
            return parsed.astimezone(timezone.utc)
        return parsed
    except (TypeError, ValueError):
        return None


def _normalize_filed_for_compare(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return datetime(value.year, value.month, value.day)
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    raise TypeError(f"unsupported filed date type: {type(value)!r}")


def _normalize_filed_for_filter_compare(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise TypeError(f"unsupported filed date type: {type(value)!r}")


def _as_of_for_compare(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.date()
        return value
    if isinstance(value, date):
        return value
    raise TypeError(f"unsupported as_of date type: {type(value)!r}")


def _is_filed_after_as_of(filed, as_of):
    as_of_cmp = _as_of_for_compare(as_of)
    if isinstance(as_of_cmp, datetime):
        if isinstance(filed, datetime):
            if filed.tzinfo is None:
                filed_date = filed.date()
                return filed_date > as_of_cmp.date()
            return filed > as_of_cmp
        return filed > as_of_cmp.date()

    filed_date = _normalize_filed_for_filter_compare(filed)
    return filed_date > as_of_cmp


def _format_filed_date(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return ""


def filter_company_facts_as_of(payload, as_of_date):
    if not isinstance(payload, dict):
        raise TypeError(f"payload must be dict, got {type(payload)!r}")

    as_of = _parse_payload_filed_date(as_of_date)
    if as_of is None:
        raise ValueError("as_of_date must be ISO date string")

    filtered = deepcopy(payload)
    facts = filtered.get("facts")
    if "facts" not in filtered:
        return filtered
    if not isinstance(facts, dict):
        filtered["facts"] = {}
        return filtered

    for taxonomy in facts.values():
        if not isinstance(taxonomy, dict):
            continue
        for concept, concept_data in list(taxonomy.items()):
            if not isinstance(concept_data, dict):
                taxonomy[concept] = {}
                concept_data = taxonomy[concept]

            if "units" not in concept_data:
                continue
            units = concept_data.get("units")
            if not isinstance(units, dict):
                concept_data["units"] = {}
                continue

            normalized_units = {}
            for unit, entries in list(units.items()):
                if not isinstance(entries, list):
                    continue

                filtered_entries = []
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    filed = _parse_payload_filed_date(entry.get("filed"))
                    if filed is None or _is_filed_after_as_of(filed, as_of):
                        continue
                    filtered_entries.append(entry)

                normalized_units[unit] = filtered_entries

            concept_data["units"] = normalized_units

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
            units = concept.get("units")
            if not isinstance(units, dict):
                continue
            for unit_entries in units.values():
                if not isinstance(unit_entries, list):
                    continue
                for entry in unit_entries:
                    if not isinstance(entry, dict):
                        continue
                    filed = _parse_payload_filed_date(entry.get("filed"))
                    if filed is None:
                        continue
                    if latest_filed is None or _normalize_filed_for_compare(filed) > _normalize_filed_for_compare(
                        latest_filed
                    ):
                        latest_filed = filed

    return {
        **metrics,
        "backtest_date": as_of_date,
        "latest_source_filed": _format_filed_date(latest_filed),
        "leakage_status": "ready",
    }
