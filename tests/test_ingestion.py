"""
Tests for document ingestion, validation, and safe temp file handling.
"""

from pathlib import Path
import pytest
from document_ai.config import get_settings
from document_ai.exceptions import (
    CorruptedFileError,
    FileSizeLimitError,
    UnsupportedFileTypeError,
)
from document_ai.ingestion import (
    compute_sha256,
    detect_file_type_from_bytes,
    temporary_upload_file,
    validate_file,
)


def test_magic_byte_detection():
    assert detect_file_type_from_bytes(b"%PDF-1.4 header") == "pdf"
    assert detect_file_type_from_bytes(b"\x89PNG\r\n\x1a\n...") == "png"
    assert detect_file_type_from_bytes(b"\xff\xd8\xff\xe0...") == "jpeg"
    assert detect_file_type_from_bytes(b"RANDOM_BYTES") == "unknown"


def test_validate_nonexistent_file(tmp_path: Path):
    non_file = tmp_path / "does_not_exist.pdf"
    with pytest.raises(CorruptedFileError):
        validate_file(non_file)


def test_validate_empty_file(tmp_path: Path):
    empty_file = tmp_path / "empty.pdf"
    empty_file.touch()
    with pytest.raises(CorruptedFileError):
        validate_file(empty_file)


def test_validate_unsupported_extension(tmp_path: Path):
    bad_file = tmp_path / "document.exe"
    bad_file.write_bytes(b"%PDF-1.4 dummy")
    with pytest.raises(UnsupportedFileTypeError):
        validate_file(bad_file)


def test_validate_mismatched_magic_bytes(tmp_path: Path):
    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_bytes(b"THIS_IS_NOT_A_PDF")
    with pytest.raises(UnsupportedFileTypeError):
        validate_file(fake_pdf)


def test_validate_size_limit(tmp_path: Path, monkeypatch):
    settings = get_settings()
    # Temporarily set max size to 1 MB for testing
    monkeypatch.setattr(settings, "max_upload_size_mb", 1)

    big_file = tmp_path / "oversized.pdf"
    # Write 1.5 MB of dummy data starting with PDF magic bytes
    big_file.write_bytes(b"%PDF-1.4 " + b"0" * (1500 * 1024))

    with pytest.raises(FileSizeLimitError):
        validate_file(big_file)


def test_temporary_upload_file_cleanup(tmp_path: Path):
    test_content = b"%PDF-1.4 valid test pdf content"
    yielded_path = None

    with temporary_upload_file(test_content, "test_doc.pdf") as (path, meta):
        yielded_path = path
        assert path.exists()
        assert meta.filename == "test_doc.pdf"
        assert meta.file_type == "pdf"
        assert meta.file_size_bytes == len(test_content)
        assert len(meta.checksum_sha256) == 64

    # Verify temp file was cleaned up on context exit
    assert not yielded_path.exists()
