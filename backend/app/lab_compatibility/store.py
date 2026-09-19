from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re
from threading import RLock
from uuid import UUID, uuid4

from app.lab_compatibility.contracts import (
    STAGE_CODES,
    CompatibilityCheckView,
    CompatibilityStage,
    CreateCompatibilityCheck,
)
from app.local_runner.contracts import ArtifactPayload
from app.local_runner.evidence import GeneratedEvidenceWriter


class InvalidCompatibilityCheckId(Exception):
    pass


class CompatibilityCheckNotFound(Exception):
    pass


class CompatibilityReportStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def create(self, command: CreateCompatibilityCheck) -> CompatibilityCheckView:
        now = datetime.now(UTC)
        view = CompatibilityCheckView(
            check_id=str(uuid4()),
            lifecycle="PENDING",
            overall_status=None,
            stages=tuple(
                CompatibilityStage(code, "NOT_RUN", "尚未执行")
                for code in STAGE_CODES
            ),
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._write(command, view)
        return view

    def save(self, view: CompatibilityCheckView) -> None:
        with self._lock:
            self._write(self.get_command(view.check_id), view)

    def get(self, check_id: str) -> CompatibilityCheckView:
        return CompatibilityCheckView.from_dict(self._read(check_id)["view"])

    def get_command(self, check_id: str) -> CreateCompatibilityCheck:
        return CreateCompatibilityCheck.from_dict(self._read(check_id)["command"])

    def list_evidence(self, check_id: str) -> tuple[ArtifactPayload, ...]:
        return tuple(
            item for stage in self.get(check_id).stages for item in stage.evidence
        )

    def evidence_writer(self, check_id: str) -> GeneratedEvidenceWriter:
        return GeneratedEvidenceWriter(self._directory(check_id))

    def _read(self, check_id: str) -> dict:
        path = self._directory(check_id) / "report.json"
        if not path.is_file():
            raise CompatibilityCheckNotFound(check_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(
        self, command: CreateCompatibilityCheck, view: CompatibilityCheckView
    ) -> None:
        directory = self._directory(view.check_id)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / "report.json"
        temporary = directory / "report.json.tmp"
        temporary.write_text(
            json.dumps(
                {"command": command.to_dict(), "view": view.to_dict()},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(target)

    def _directory(self, check_id: str) -> Path:
        try:
            normalized = str(UUID(check_id))
        except (ValueError, AttributeError) as exception:
            raise InvalidCompatibilityCheckId(check_id) from exception
        if not re.fullmatch(r"[0-9a-f-]{36}", normalized):
            raise InvalidCompatibilityCheckId(check_id)
        return self.root / normalized
