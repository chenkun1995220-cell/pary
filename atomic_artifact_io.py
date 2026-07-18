import json
import os
import tempfile
from pathlib import Path


def write_text_atomic(path, text, encoding="utf-8-sig"):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=encoding,
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, output)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return output


def write_json_atomic(path, payload, sort_keys=False):
    text = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=sort_keys,
    ) + "\n"
    return write_text_atomic(path, text)
