"""
File-hash dedup index for uploads (data/upload_hashes.json).

Maps sha256(raw_bytes) -> {doc_id, patient_id, filename, uploaded_at} so a
re-upload of the exact same file can short-circuit before the (paid) LLM
extraction + full engine run, instead of creating a second UP-* doc.

Same read/write-whole-file JSON pattern records.py already uses for
patients_user.json — no new persistence pattern. Best-effort by design: any
I/O failure degrades to "not a duplicate" (lookup returns None, record is a
no-op) so a broken index can never block a legitimate upload.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"
_HASHES_FILE = _DATA_DIR / "upload_hashes.json"


def _load() -> dict:
    if _HASHES_FILE.exists():
        return json.loads(_HASHES_FILE.read_text(encoding="utf-8"))
    return {}


def lookup(file_hash: str) -> Optional[dict]:
    """Return the recorded upload for a previously-seen hash, or None."""
    try:
        return _load().get(file_hash)
    except Exception:  # pragma: no cover - a broken index must never block upload
        return None


def record(file_hash: str, doc_id: str, patient_id: str, filename: str) -> None:
    """Remember hash -> upload metadata. Best-effort; swallows I/O errors."""
    try:
        data = _load()
        data[file_hash] = {
            "doc_id": doc_id,
            "patient_id": patient_id,
            "filename": filename,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        _HASHES_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:  # pragma: no cover - dedup index is best-effort
        pass
