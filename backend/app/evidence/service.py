from pathlib import Path
from typing import BinaryIO

from app.evidence import parser
from app.evidence.repository import EvidenceRepository
from app.evidence.storage import (
    EvidenceFileMissingError,
    EvidenceFileTooLargeError,
    EvidenceStorage,
)
from app.models.evidence import Evidence


class EvidenceNotFoundError(Exception):
    pass


class EvidenceOwnerNotFoundError(Exception):
    pass


class EvidenceConflictError(Exception):
    pass


class EvidenceGoneError(Exception):
    pass


class EvidenceTooLargeError(Exception):
    pass


class InvalidEvidenceError(Exception):
    pass


class EvidenceService:
    CATEGORIES = {"SCREENSHOT", "LOG", "CONFIG", "OTHER"}

    def __init__(
        self,
        repository: EvidenceRepository,
        storage: EvidenceStorage,
    ) -> None:
        self.repository = repository
        self.storage = storage

    def list_for_run_result(self, result_id: str) -> list[Evidence]:
        if self.repository.get_run_result(result_id) is None:
            raise EvidenceOwnerNotFoundError(result_id)
        return self.repository.list_for_run_result(result_id)

    def list_for_defect(self, defect_id: str) -> list[Evidence]:
        if self.repository.get_defect(defect_id) is None:
            raise EvidenceOwnerNotFoundError(defect_id)
        return self.repository.list_for_defect(defect_id)

    def create_for_run_result(self, result_id: str, **values) -> Evidence:
        run_result = self.repository.get_run_result(result_id)
        if run_result is None:
            raise EvidenceOwnerNotFoundError(result_id)
        if run_result.integrity_status != "DRAFT":
            raise EvidenceConflictError("Locked result evidence is read-only")
        return self._create(
            owner_kind="run-results",
            owner_id=result_id,
            run_result_id=result_id,
            defect_id=None,
            **values,
        )

    def create_for_defect(self, defect_id: str, **values) -> Evidence:
        defect = self.repository.get_defect(defect_id)
        if defect is None:
            raise EvidenceOwnerNotFoundError(defect_id)
        if defect.status == "CLOSED":
            raise EvidenceConflictError("Closed defect evidence is read-only")
        return self._create(
            owner_kind="defects",
            owner_id=defect_id,
            run_result_id=None,
            defect_id=defect_id,
            **values,
        )

    def create_batch_for_results(
        self,
        result_ids: list[str],
        files: list[dict],
        *,
        category: str,
        description: str | None,
    ) -> list[Evidence]:
        unique_ids = list(dict.fromkeys(result_ids))
        if not 1 <= len(unique_ids) <= 50:
            raise InvalidEvidenceError("Select between 1 and 50 results")
        if not 1 <= len(files) <= 20:
            raise InvalidEvidenceError("Upload between 1 and 20 files")
        if category not in self.CATEGORIES:
            raise InvalidEvidenceError("Invalid evidence category")
        results = self.repository.get_run_results(unique_ids)
        if len(results) != len(unique_ids):
            raise EvidenceOwnerNotFoundError("run result")
        if len({result.run_id for result in results}) != 1:
            raise EvidenceConflictError("Evidence targets must belong to one run")
        if any(result.integrity_status != "DRAFT" for result in results):
            raise EvidenceConflictError("Locked result evidence is read-only")

        stored_items = []
        values_list = []
        try:
            for item in files:
                safe_name = Path(str(item["original_name"]).strip()).name
                if not safe_name:
                    raise InvalidEvidenceError("Filename is required")
                stored = self.storage.store(
                    "run-results",
                    unique_ids[0],
                    safe_name,
                    item["stream"],
                )
                stored_items.append(stored)
                values_list.append(
                    {
                        "run_result_id": unique_ids[0],
                        "defect_id": None,
                        "category": category,
                        "original_name": safe_name,
                        "storage_path": stored.storage_path,
                        "media_type": item.get("media_type")
                        or "application/octet-stream",
                        "file_size": stored.file_size,
                        "sha256": stored.sha256,
                        "description": (
                            description.strip()
                            if description and description.strip()
                            else None
                        ),
                        "parsed_metadata": self._parse_stored_evidence(
                            stored.storage_path,
                            item.get("media_type")
                            or "application/octet-stream",
                        ),
                    }
                )
            return self.repository.create_batch(values_list, unique_ids)
        except EvidenceFileTooLargeError as exception:
            for stored in stored_items:
                self.storage.delete(stored.storage_path)
            raise EvidenceTooLargeError from exception
        except Exception:
            for stored in stored_items:
                self.storage.delete(stored.storage_path)
            raise

    def get_download(self, evidence_id: str) -> tuple[Evidence, object]:
        evidence = self._get(evidence_id)
        try:
            path = self.storage.open_path(evidence.storage_path)
        except EvidenceFileMissingError as exception:
            raise EvidenceGoneError(evidence_id) from exception
        return evidence, path

    def delete(self, evidence_id: str) -> None:
        evidence = self._get(evidence_id)
        if evidence.run_result_id:
            owners = [item.run_result for item in evidence.result_links]
            if not owners:
                owner = self.repository.get_run_result(evidence.run_result_id)
                owners = [owner] if owner is not None else []
            if not owners:
                raise EvidenceOwnerNotFoundError(evidence.run_result_id)
            if any(owner.integrity_status != "DRAFT" for owner in owners):
                raise EvidenceConflictError(
                    "Locked result evidence is read-only"
                )
        else:
            owner = self.repository.get_defect(str(evidence.defect_id))
            if owner is None:
                raise EvidenceOwnerNotFoundError(str(evidence.defect_id))
            if owner.status in {"RESOLVED", "CLOSED"}:
                raise EvidenceConflictError(
                    "Defect evidence cannot be deleted in this status"
                )
        self.repository.delete(evidence)
        self.storage.delete(evidence.storage_path)

    def _create(
        self,
        *,
        owner_kind: str,
        owner_id: str,
        run_result_id: str | None,
        defect_id: str | None,
        category: str,
        original_name: str,
        media_type: str,
        description: str | None,
        stream: BinaryIO,
    ) -> Evidence:
        if category not in self.CATEGORIES:
            raise InvalidEvidenceError("Invalid evidence category")
        safe_name = Path(original_name.strip()).name
        if not safe_name:
            raise InvalidEvidenceError("Filename is required")
        try:
            stored = self.storage.store(
                owner_kind,
                owner_id,
                safe_name,
                stream,
            )
        except EvidenceFileTooLargeError as exception:
            raise EvidenceTooLargeError from exception
        try:
            return self.repository.create(
                {
                    "run_result_id": run_result_id,
                    "defect_id": defect_id,
                    "category": category,
                    "original_name": safe_name,
                    "storage_path": stored.storage_path,
                    "media_type": media_type or "application/octet-stream",
                    "file_size": stored.file_size,
                    "sha256": stored.sha256,
                    "description": (
                        description.strip()
                        if description and description.strip()
                        else None
                    ),
                    "parsed_metadata": self._parse_stored_evidence(
                        stored.storage_path,
                        media_type or "application/octet-stream",
                    ),
                }
            )
        except Exception:
            self.storage.delete(stored.storage_path)
            raise

    def _parse_stored_evidence(
        self,
        storage_path: str,
        media_type: str,
    ) -> str | None:
        """Best-effort structured parse of text evidence at upload time."""
        if not media_type.startswith("text/"):
            return None
        try:
            path = self.storage.open_path(storage_path)
            raw = path.read_text(encoding="utf-8", errors="replace")
        except (EvidenceFileMissingError, OSError):
            return None
        return parser.dumps(parser.parse_payload(raw))

    def _get(self, evidence_id: str) -> Evidence:
        evidence = self.repository.get(evidence_id)
        if evidence is None:
            raise EvidenceNotFoundError(evidence_id)
        return evidence
