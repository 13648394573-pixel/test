from copy import deepcopy
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.execution_session import ExecutionEvent, ExecutionSession


class SkillExecutionRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, session_id: str) -> ExecutionSession:
        self.session.expire_all()
        execution = self.session.get(ExecutionSession, session_id)
        if execution is None:
            raise LookupError('Skill execution not found')
        return execution

    def events(self, session_id: str) -> list[ExecutionEvent]:
        return list(self.session.scalars(select(ExecutionEvent).where(
            ExecutionEvent.session_id == session_id).order_by(ExecutionEvent.sequence_no)))

    def append_event(self, session_id, event_type, payload, key, *, step_ref=None, action_ref=None, require_new=False):
        existing = self.session.scalar(select(ExecutionEvent).where(
            ExecutionEvent.session_id == session_id, ExecutionEvent.idempotency_key == key))
        if existing is not None:
            if require_new or existing.event_type != event_type or existing.payload_json != payload:
                raise ValueError('Event idempotency conflict')
            return existing
        sequence = self.session.scalar(select(func.max(ExecutionEvent.sequence_no)).where(
            ExecutionEvent.session_id == session_id)) or 0
        event = ExecutionEvent(session_id=session_id, sequence_no=sequence + 1,
            event_type=event_type, payload_json=deepcopy(payload), idempotency_key=key,
            step_ref=step_ref, action_ref=action_ref)
        self.session.add(event)
        self.session.flush()
        return event
