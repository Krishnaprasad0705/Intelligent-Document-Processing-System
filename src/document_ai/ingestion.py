"""
Document Ingestion Module.
Validates file extension, magic byte signatures, file size limits,
computes cryptographic checksums, and manages temporary file life-cycles safely.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from typing import Generator, Tuple, BinaryIO, Union

from document_ai.config import get_settings
from document_ai.exceptions import (
    CorruptedFileError,
    FileSizeLimitError,
    UnsupportedFileTypeError,
)
from document_ai.logging_config import get_logger
from document_ai.schemas import DocumentMetadata

logger = get_logger("ingestion")

# Magic byte signatures for genuine format detection
MAGIC_SIGNATURES = {
    b"%PDF": "pdf",
    b"\x89PNG\r\n\x1a\n": "png",
    b"\xff\xd8\xff": "jpeg",
}


def compute_sha256(file_path: Path) -> str:
    """Computes SHA-256 hash of a file safely in 64KB blocks."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def detect_file_type_from_bytes(head: bytes) -> str:
    """Inspects header bytes to confirm actual file format."""
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    return "unknown"


def validate_file(file_path: Path) -> DocumentMetadata:
    """
    Validates file existence, non-emptiness, size limit, extension,
    and genuine magic byte header.
    Returns DocumentMetadata if valid, raises appropriate IngestionError otherwise.
    """
    settings = get_settings()

    if not file_path.exists():
        raise CorruptedFileError(f"Target file does not exist: {file_path.name}")

    file_size = file_path.stat().st_size
    if file_size == 0:
        raise CorruptedFileError(f"Uploaded file '{file_path.name}' is empty (0 bytes).")

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if file_size > max_bytes:
        raise FileSizeLimitError(
            f"File '{file_path.name}' ({file_size / (1024 * 1024):.2f} MB) exceeds "
            f"maximum upload limit of {settings.max_upload_size_mb} MB."
        )

    # Extension check
    suffix = file_path.suffix.lower()
    if suffix not in settings.allowed_extensions:
        raise UnsupportedFileTypeError(
            f"File extension '{suffix}' is not supported. Allowed extensions: {', '.join(settings.allowed_extensions)}"
        )

    # Magic byte validation
    with open(file_path, "rb") as f:
        head = f.read(16)

    detected_type = detect_file_type_from_bytes(head)
    expected_type = "pdf" if suffix == ".pdf" else "png" if suffix == ".png" else "jpeg"

    if detected_type != expected_type:
        # Check if jpg/jpeg variance is acceptable
        if not (expected_type == "jpeg" and detected_type == "jpeg"):
            raise UnsupportedFileTypeError(
                f"File content signature '{detected_type}' does not match expected extension '{suffix}'."
            )

    checksum = compute_sha256(file_path)
    created_at = datetime.now(timezone.utc).isoformat()

    return DocumentMetadata(
        filename=file_path.name,
        file_type=detected_type,
        file_size_bytes=file_size,
        page_count=1,  # Updated during extraction for multi-page docs
        created_at=created_at,
        checksum_sha256=checksum,
    )


@contextmanager
def temporary_upload_file(
    file_source: Union[Path, BinaryIO, bytes],
    original_filename: str
) -> Generator[Tuple[Path, DocumentMetadata], None, None]:
    """
    Context manager that safely writes uploaded stream or bytes to a temporary file,
    validates it, yields (temp_path, metadata), and guarantees temporary file deletion
    upon context exit.
    """
    settings = get_settings()
    settings.temp_dir.mkdir(parents=True, exist_ok=True)

    safe_name = Path(original_filename).name
    # Create isolated temp file with matching extension
    suffix = Path(safe_name).suffix.lower()
    temp_fd, temp_path_str = tempfile.mkstemp(suffix=suffix, dir=str(settings.temp_dir))
    temp_path = Path(temp_path_str)

    try:
        with os.fdopen(temp_fd, "wb") as dst:
            if isinstance(file_source, (bytes, bytearray)):
                dst.write(file_source)
            elif isinstance(file_source, Path):
                with open(file_source, "rb") as src:
                    shutil.copyfileobj(src, dst)
            else:
                # BinaryIO (e.g. Streamlit UploadedFile)
                file_source.seek(0)
                shutil.copyfileobj(file_source, dst)

        metadata = validate_file(temp_path)
        metadata.filename = safe_name
        yield temp_path, metadata

    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError as err:
                logger.warning(f"Failed to remove temp file {temp_path}: {err}")
