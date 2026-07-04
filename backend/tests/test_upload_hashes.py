"""
Upload dedup index + image-format sniffing (offline — no Vertex/Cognee).

Covers the two smallest testable pieces of the dedup/images work:
  - upload_hashes.record() then lookup() round-trips; an unseen hash is None.
  - sniff_format() recognises the newly-accepted image extensions.
"""

from __future__ import annotations

from pathlib import Path

from app.intake import upload_hashes
from app.intake.pipeline import sniff_format


def test_record_then_lookup_round_trips(tmp_path, monkeypatch):
    monkeypatch.setattr(upload_hashes, "_HASHES_FILE", tmp_path / "upload_hashes.json")

    assert upload_hashes.lookup("deadbeef") is None  # unseen hash -> None

    upload_hashes.record("deadbeef", "UP-P001-abc123", "P001", "labs.pdf")
    hit = upload_hashes.lookup("deadbeef")

    assert hit is not None
    assert hit["doc_id"] == "UP-P001-abc123"
    assert hit["patient_id"] == "P001"
    assert hit["filename"] == "labs.pdf"
    assert hit["uploaded_at"]  # timestamp recorded


def test_lookup_unseen_hash_is_none(tmp_path, monkeypatch):
    monkeypatch.setattr(upload_hashes, "_HASHES_FILE", tmp_path / "upload_hashes.json")
    assert upload_hashes.lookup("never-seen") is None


def test_sniff_format_recognises_images():
    # The picker now accepts these; the sniffer must route them to the vision path.
    for name in ("scan.webp", "photo.HEIC", "note.heif", "chart.jpg", "record.png"):
        assert sniff_format(name, b"\x00\x01\x02") == "image", name
    # Non-image formats still route correctly.
    assert sniff_format("note.txt", b"hello") == "text"
