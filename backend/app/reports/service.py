from collections.abc import Callable
import base64
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError

from app.models.report import Archive, Report
from app.reports.renderer import REPORT_MODES, render_report_html
from app.reports.repository import ReportRepository
from app.reports.snapshots import build_report_snapshot
from app.reports.storage import (
    ArtifactIntegrityError,
    ArtifactMissingError,
    ReportStorage,
    StoredArtifact,
)


class ReportSourceNotFoundError(Exception):
    pass


class ReportNotFoundError(Exception):
    pass


class ArchiveNotFoundError(Exception):
    pass


class ReportNotReadyError(Exception):
    pass


class ReportModeError(Exception):
    pass


class ArchiveAlreadyExistsError(Exception):
    pass


class ReportArtifactConflictError(Exception):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class ReportService:
    def __init__(
        self,
        repository: ReportRepository,
        storage: ReportStorage,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.clock = clock

    def generate_report(
        self,
        run_id: str,
        title: str | None = None,
        mode: str = "formal",
        customer_code: str | None = None,
    ) -> Report:
        if mode not in REPORT_MODES:
            raise ReportModeError(mode)
        run = self.repository.get_run_graph(run_id)
        if run is None:
            raise ReportSourceNotFoundError(run_id)
        if run.status != "COMPLETED" or not run.results or any(
            result.integrity_status != "LOCKED" for result in run.results
        ):
            raise ReportNotReadyError(run_id)

        result_ids = [result.id for result in run.results]
        defects = self.repository.list_defects(result_ids)
        evidences = self.repository.list_evidence(
            result_ids,
            [defect.id for defect in defects],
        )
        generated_at = self.clock()
        version = self.repository.next_report_version(run.id)
        report_id = str(uuid4())
        report_title = (
            title.strip()
            if title and title.strip()
            else f"{run.project.name} {run.project.version} Test Report"
        )
        snapshot = build_report_snapshot(
            run,
            evidences,
            defects,
            generated_at,
        )
        report_no = self.repository.next_report_no()
        snapshot["report_title"] = report_title
        snapshot["report_no"] = report_no
        snapshot["report_version"] = version
        snapshot["customer_code"] = (
            customer_code.strip() if customer_code and customer_code.strip() else None
        )
        self._inline_screenshot_evidence(snapshot)
        stored = self.storage.write_html(
            report_id,
            render_report_html(snapshot, mode=mode),
        )
        values = {
            "id": report_id,
            "report_no": report_no,
            "project_id": run.project_id,
            "test_run_id": run.id,
            "report_version": version,
            "title": report_title,
            "snapshot_version": 1,
            "report_snapshot": snapshot,
            "html_storage_path": stored.storage_path,
            "html_sha256": stored.sha256,
            "html_file_size": stored.file_size,
            "generated_at": generated_at,
        }
        try:
            return self.repository.create_report(values)
        except SQLAlchemyError:
            self.storage.delete(stored.storage_path)
            raise

    def _inline_screenshot_evidence(self, snapshot: dict[str, Any]) -> None:
        """Embed image evidence as base64 data URIs (SHA256-verified reads).

        Text evidence stays referenced by name/hash only, keeping report
        size bounded; screenshots are small enough to inline so that the
        HTML report is self-contained for customer delivery.
        """
        entries: list[dict[str, Any]] = []
        for result in snapshot["results"]:
            entries.extend(result.get("evidences") or [])
        for defect in snapshot.get("defects") or []:
            entries.extend(defect.get("evidences") or [])
        for item in entries:
            media_type = str(item.get("media_type") or "")
            if not media_type.startswith("image/"):
                continue
            storage_path = item.get("storage_path")
            expected = item.get("sha256")
            if not storage_path or not expected:
                continue
            try:
                path = ReportStorage._resolve_within(
                    self.storage.evidence_root,
                    storage_path,
                )
                if not path.is_file() or ReportStorage._hash(path) != expected:
                    continue
                payload = base64.b64encode(path.read_bytes()).decode("ascii")
            except (OSError, ValueError):
                continue
            item["data_uri"] = f"data:{media_type};base64,{payload}"

    def get_report(self, report_id: str) -> Report:
        report = self.repository.get_report(report_id)
        if report is None:
            raise ReportNotFoundError(report_id)
        return report

    def list_for_run(self, run_id: str) -> list[Report]:
        if self.repository.get_run_graph(run_id) is None:
            raise ReportSourceNotFoundError(run_id)
        return self.repository.list_for_run(run_id)

    def list_for_project(self, project_id: str) -> list[Report]:
        return self.repository.list_for_project(project_id)

    def download_report(self, report_id: str) -> Path:
        report = self.get_report(report_id)
        try:
            return self.storage.open_verified(
                report.html_storage_path,
                report.html_sha256,
            )
        except (ArtifactMissingError, ArtifactIntegrityError) as error:
            raise ReportArtifactConflictError(str(error)) from error

    def create_archive(self, report_id: str) -> Archive:
        report = self.get_report(report_id)
        if self.repository.get_archive_for_report(report.id) is not None:
            raise ArchiveAlreadyExistsError(report.id)
        archive_id = str(uuid4())
        archived_at = self.clock()
        evidences = self._snapshot_evidences(report.report_snapshot)
        manifest = {
            "manifest_version": 1,
            "archived_at": archived_at.isoformat(),
            "report": {
                "report_id": report.id,
                "report_no": report.report_no,
                "report_version": report.report_version,
                "html_sha256": report.html_sha256,
                "html_file_size": report.html_file_size,
            },
            "files": [
                {
                    "path": "report.html",
                    "sha256": report.html_sha256,
                    "file_size": report.html_file_size,
                },
                *[
                    {
                        "path": f"evidence/{item['storage_path']}",
                        "original_name": item["original_name"],
                        "sha256": item["sha256"],
                        "file_size": item["file_size"],
                    }
                    for item in evidences
                ],
            ],
        }
        try:
            stored = self.storage.create_archive(
                archive_id,
                report.html_storage_path,
                report.html_sha256,
                evidences,
                manifest,
            )
        except (ArtifactMissingError, ArtifactIntegrityError) as error:
            raise ReportArtifactConflictError(str(error)) from error
        values = {
            "id": archive_id,
            "archive_no": self.repository.next_archive_no(),
            "report_id": report.id,
            "project_id": report.project_id,
            "manifest_version": 1,
            "manifest_snapshot": manifest,
            "archive_storage_path": stored.storage_path,
            "archive_sha256": stored.sha256,
            "archive_file_size": stored.file_size,
            "archived_at": archived_at,
        }
        try:
            return self.repository.create_archive(values)
        except SQLAlchemyError as error:
            self.storage.delete(stored.storage_path)
            if self.repository.get_archive_for_report(report.id) is not None:
                raise ArchiveAlreadyExistsError(report.id) from error
            raise

    def get_archive_for_report(self, report_id: str) -> Archive:
        self.get_report(report_id)
        archive = self.repository.get_archive_for_report(report_id)
        if archive is None:
            raise ArchiveNotFoundError(report_id)
        return archive

    def get_archive(self, archive_id: str) -> Archive:
        archive = self.repository.get_archive(archive_id)
        if archive is None:
            raise ArchiveNotFoundError(archive_id)
        return archive

    def download_archive(self, archive_id: str) -> Path:
        archive = self.get_archive(archive_id)
        try:
            return self.storage.open_verified(
                archive.archive_storage_path,
                archive.archive_sha256,
            )
        except (ArtifactMissingError, ArtifactIntegrityError) as error:
            raise ReportArtifactConflictError(str(error)) from error

    @staticmethod
    def _snapshot_evidences(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        evidences: dict[str, dict[str, Any]] = {}
        for result in snapshot["results"]:
            for item in result["evidences"]:
                existing = evidences.get(item["id"])
                if existing is not None and existing != item:
                    raise ReportArtifactConflictError(
                        f"Conflicting Evidence snapshot {item['id']}"
                    )
                evidences[item["id"]] = item
        for defect in snapshot["defects"]:
            for item in defect["evidences"]:
                existing = evidences.get(item["id"])
                if existing is not None and existing != item:
                    raise ReportArtifactConflictError(
                        f"Conflicting Evidence snapshot {item['id']}"
                    )
                evidences[item["id"]] = item
        return [evidences[item_id] for item_id in sorted(evidences)]
