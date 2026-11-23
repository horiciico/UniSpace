"""Shared by every ETL pipeline: small helpers that do not depend on one pipeline."""

import json
import os
from pathlib import Path


def write_json_atomic(path: Path, document: dict, indent: int | None) -> int:
    """Write UTF-8 JSON to a temporary file, then rename it. Returns the file size in bytes.

    A failed or interrupted write never leaves a half-written file under the final name.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / (path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=indent)
    os.replace(temporary, path)
    return path.stat().st_size

