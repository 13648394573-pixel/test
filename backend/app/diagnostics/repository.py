from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models.diagnostic import (
    DiagnosticAttempt,
    DiagnosticAttemptEvidence,
    DiagnosticSession,
)
from app.models.test_execution import RunResult


class DiagnosticRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_result(self, result_id: str) -> RunResult | None:
        return self.session.get(RunResult, result_id)

    def get_session(self, session_id: str) -> DiagnosticSession | None:
        statement = (
            select(DiagnosticSession)
            .options(
                selectinload(DiagnosticSession.attempts).selectinload(
                    DiagnosticAttempt.evidence_links
                )
            )
            .where(DiagnosticSession.id == session_id)
        )
        return self.session.scalar(statement)

    def list_for_result(self, result_id: str) -> list[DiagnosticSession]:
        statement = (
            select(DiagnosticSession)
            .options(selectinload(DiagnosticSession.attempts))
            .where(DiagnosticSession.run_result_id == result_id)
            .order_by(DiagnosticSession.created_at.desc(), DiagnosticSession.id.desc())
        )
        return list(self.session.scalars(statement))

    def get_active_for_result(self, result_id: str) -> DiagnosticSession | None:
        statement = select(DiagnosticSession).where(
            DiagnosticSession.run_result_id == result_id,
            DiagnosticSession.status.in_(("PENDING", "RUNNING")),
        )
        return self.session.scalar(statement)

    def create_session(
        self,
        result_id: str,
        adapter_key: str,
        adapter_version: str,
        wan_mode: str,
        policy_snapshot: Mapping[str, Any],
        *,
        retry_of_session_id: str | None = None,
    ) -> DiagnosticSession:
        diagnostic = DiagnosticSession(
            run_result_id=result_id,
            retry_of_session_id=retry_of_session_id,
            adapter_key=adapter_key,
            adapter_version=adapter_version,
            wan_mode=wan_mode,
            policy_snapshot=dict(policy_snapshot),
            snapshot_version=1,
        )
        self.session.add(diagnostic)
        self._commit()
        return self.get_session(diagnostic.id) or diagnostic

    def mark_running(self, diagnostic: DiagnosticSession, started_at: datetime) -> DiagnosticSession:
        diagnostic.status = "RUNNING"
        diagnostic.started_at = started_at
        diagnostic.error_code = None
        diagnostic.error_message = None
        self._commit()
        self.session.refresh(diagnostic)
        return diagnostic

    def append_attempt(
        self, diagnostic: DiagnosticSession, values: Mapping[str, Any]
    ) -> DiagnosticAttempt:
        attempt = DiagnosticAttempt(session_id=diagnostic.id, **dict(values))
        self.session.add(attempt)
        self._commit()
        self.session.refresh(attempt)
        return attempt

    def mark_terminal(
        self,
        diagnostic: DiagnosticSession,
        status: str,
        completed_at: datetime,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> DiagnosticSession:
        diagnostic.status = status
        diagnostic.completed_at = completed_at
        diagnostic.error_code = error_code
        diagnostic.error_message = error_message
        self._commit()
        self.session.refresh(diagnostic)
        return diagnostic

    def link_evidence(self, attempt_id: str, evidence_id: str) -> None:
        self.session.add(
            DiagnosticAttemptEvidence(
                diagnostic_attempt_id=attempt_id,
                evidence_id=evidence_id,
            )
        )
        self._commit()

    def interrupt_running(self, completed_at: datetime) -> int:
        statement = select(DiagnosticSession).where(DiagnosticSession.status == "RUNNING")
        sessions = list(self.session.scalars(statement))
        for diagnostic in sessions:
            diagnostic.status = "INTERRUPTED"
            diagnostic.completed_at = completed_at
            diagnostic.error_code = "PROCESS_RESTARTED"
            diagnostic.error_message = "Diagnostic interrupted by application restart"
        self._commit()
        return len(sessions)

    def _commit(self) -> None:
        try:
            self.session.commit()
        except (SQLAlchemyError, ValueError):
            self.session.rollback()
            raise
