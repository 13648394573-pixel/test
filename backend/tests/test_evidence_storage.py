from io import BytesIO

import pytest

from app.evidence.storage import (
    EvidenceFileMissingError,
    EvidenceFileTooLargeError,
    EvidenceStorage,
)


def test_storage_streams_content_to_uuid_path_and_calculates_integrity(
    tmp_path,
) -> None:
    storage = EvidenceStorage(tmp_path, max_bytes=100)

    stored = storage.store(
        "run-results",
        "result-1",
        "../console.log",
        BytesIO(b"hello evidence"),
    )

    assert stored.storage_path.startswith("run-results/result-1/")
    assert stored.storage_path.endswith(".log")
    assert stored.file_size == 14
    assert stored.sha256 == (
        "9af4c73b2a919f220f4b008e466b5280"
        "8a1987122d95ff0f2dde00968e36e844"
    )
    assert storage.resolve(stored.storage_path).read_bytes() == b"hello evidence"


def test_storage_rejects_oversized_file_and_removes_temporary_content(
    tmp_path,
) -> None:
    storage = EvidenceStorage(tmp_path, max_bytes=3)

    with pytest.raises(EvidenceFileTooLargeError):
        storage.store("defects", "defect-1", "large.bin", BytesIO(b"1234"))

    assert list(tmp_path.rglob("*.*")) == []


def test_storage_rejects_escape_paths_and_reports_missing_files(tmp_path) -> None:
    storage = EvidenceStorage(tmp_path, max_bytes=100)

    with pytest.raises(ValueError, match="outside evidence root"):
        storage.resolve("../secret.txt")
    with pytest.raises(EvidenceFileMissingError):
        storage.open_path("run-results/missing/file.log")
