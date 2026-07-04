"""Run-local file writes used by data feeds and sources."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Write text through a same-directory temp file, then replace atomically."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        tmp_path.replace(path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        finally:
            raise


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def write_receipt_bundle(
    receipt_path: Path,
    run_dir: Path,
    payload: Mapping[str, Any],
    *,
    run_payload: Mapping[str, Any] | None = None,
) -> Path:
    """Write latest and run-scoped receipt files atomically.

    `receipt_path` remains the component's latest task receipt for compatibility.
    `<run_dir>/completion_receipt.json` is the immutable run-scoped receipt copy
    that downstream receipt collection should prefer when it needs a specific run.
    """

    receipt_path = Path(receipt_path)
    run_receipt_path = Path(run_dir) / "completion_receipt.json"
    atomic_write_json(run_receipt_path, run_payload or payload)
    atomic_write_json(receipt_path, payload)
    return run_receipt_path


__all__ = ["atomic_write_json", "atomic_write_text", "write_receipt_bundle"]
