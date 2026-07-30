import json
from io import BytesIO
from zipfile import ZipFile

import pytest

from app.evidence.storage import EvidenceStorage
from app.reports.storage import (
    ArtifactIntegrityError,
    ReportStorage,
)


def test_storage_writes_and_verifies_html_and_rejects_tampering(tmp_path) -> None:
    storage = ReportStorage(tmp_path / "reports", tmp_path / "evidence")
    stored = storage.write_html("report-1", "<html>stable</html>")

    assert storage.open_verified(stored.storage_path, stored.sha256).is_file()
    storage.resolve(stored.storage_path).write_text("<html>changed</html>")
    with pytest.raises(ArtifactIntegrityError):
        storage.open_verified(stored.storage_path, stored.sha256)
    with pytest.raises(ValueError):
        storage.resolve("../outside.html")


def test_archive_contains_only_report_manifest_and_verified_evidence(
    tmp_path,
) -> None:
    evidence_storage = EvidenceStorage(
        tmp_path / "evidence",
        max_bytes=1024,
    )
    evidence = evidence_storage.store(
        "run_result",
        "result-1",
        "wan.log",
        BytesIO(b"log"),
    )
    storage = ReportStorage(tmp_path / "reports", tmp_path / "evidence")
    report = storage.write_html("report-1", "<html>stable</html>")
    evidence_item = {
        "id": "evidence-1",
        "original_name": "wan.log",
        "storage_path": evidence.storage_path,
        "sha256": evidence.sha256,
        "file_size": evidence.file_size,
    }
    manifest = {"manifest_version": 1, "files": []}

    archived = storage.create_archive(
        "archive-1",
        report.storage_path,
        report.sha256,
        [evidence_item],
        manifest,
    )

    with ZipFile(storage.resolve(archived.storage_path)) as package:
        assert set(package.namelist()) == {
            "report.html",
            "manifest.json",
            "evidence/evidence-1/wan.log",
        }
        loaded_manifest = json.loads(package.read("manifest.json"))
        assert loaded_manifest["manifest_version"] == 1
        assert not any(name.endswith(".db") for name in package.namelist())

    evidence_storage.resolve(evidence.storage_path).write_bytes(b"tampered")
    with pytest.raises(ArtifactIntegrityError):
        storage.create_archive(
            "archive-2",
            report.storage_path,
            report.sha256,
            [evidence_item],
            manifest,
        )
