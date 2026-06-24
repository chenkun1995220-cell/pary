import csv
import hashlib
import json
import tempfile
from pathlib import Path


MANIFEST_CORE_FIELDS = [
    "batch_id",
    "week",
    "status",
    "config_digest",
    "coverage",
    "quality_gate",
    "failure_reason",
    "updated_at",
]

CHECKPOINT_FIELDS = [
    "batch_id",
    "config_digest",
    "last_completed_week",
    "success_count",
    "failure_count",
    "updated_at",
]


def config_digest(config):
    payload = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def should_run_week(row, digest):
    return not row or row.get("status") != "completed" or row.get("config_digest") != digest


def _atomic_write_text(path, text, mode="w", encoding="utf-8"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode=mode, encoding=encoding, delete=False, dir=path.parent
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(text)
        temp_path.replace(path)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def write_checkpoint(path, checkpoint):
    if not all(field in checkpoint for field in CHECKPOINT_FIELDS):
        missing = [field for field in CHECKPOINT_FIELDS if field not in checkpoint]
        raise ValueError(f"missing required checkpoint fields: {missing}")
    payload = json.dumps(checkpoint, ensure_ascii=False, sort_keys=True, indent=2)
    _atomic_write_text(Path(path), payload, encoding="utf-8")


def load_checkpoint(path):
    path = Path(path)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            checkpoint = json.load(handle)
    except (json.JSONDecodeError, OSError, ValueError):
        return None
    if not isinstance(checkpoint, dict):
        return None
    if not all(field in checkpoint for field in CHECKPOINT_FIELDS):
        return None
    return checkpoint


def load_manifest_rows(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def upsert_manifest_row(path, row):
    path = Path(path)
    rows = load_manifest_rows(path)

    key = (str(row.get("batch_id", "")), str(row.get("week", "")))
    rebuilt_rows = []
    inserted = False
    for existing in rows:
        existing_key = (str(existing.get("batch_id", "")), str(existing.get("week", "")))
        if existing_key == key:
            if not inserted:
                rebuilt_rows.append(row)
                inserted = True
            continue
        rebuilt_rows.append(existing)
    if not inserted:
        rebuilt_rows.append(row)
    rows = rebuilt_rows

    fieldnames = list(MANIFEST_CORE_FIELDS)
    extras = set()
    for manifest_row in rows:
        extras.update(manifest_row.keys())
    extras.difference_update(MANIFEST_CORE_FIELDS)
    if extras:
        fieldnames.extend(sorted(extras))

    temp_path = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8-sig", newline="", delete=False, dir=path.parent
        ) as handle:
            temp_path = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        temp_path.replace(path)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()
