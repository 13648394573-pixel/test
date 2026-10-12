from hashlib import sha256
from ipaddress import ip_address
from math import isfinite
from pathlib import Path
import re
from typing import Annotated, Protocol
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.dependencies import get_session
from app.evidence.storage import EvidenceStorage, EvidenceFileMissingError
from app.local_runner.contracts import ActionContext, ActionOutcome
from app.local_runner.ma5800.actions import ParameterValidationError
from app.local_runner.credentials import InvalidCredentialReferenceError, UnavailableCredentialError
from app.models.evidence import Evidence
from app.models.test_execution import RunResult
from app.skill_execution.coordinator import SkillCoordinator
from app.skill_execution.repository import SkillExecutionRepository
from app.skill_execution.service import SkillExecutionService
from app.skill_execution.schemas import (
    ExecutionCreate, ExecutionRead, InteractionResponse, ExecutionEvidenceRead,
)


class ExecutionRuntime(Protocol):
    """Trusted, locally configured composition; never supplied by an HTTP client."""
    def available(self, reference: str) -> bool: ...
    def secrets_for(self, parameters: dict, action: str) -> dict: ...
    def execute(self, context: ActionContext) -> ActionOutcome: ...


router = APIRouter(prefix='/skill-executions', tags=['skill-executions'])
SessionDependency = Annotated[Session, Depends(get_session)]
_BOOLEAN_FACTS = frozenset({
    'olt.autofind.matched', 'olt.registration.ready',
    'ipoe.address.valid', 'pppoe.address.valid', 'ipoe.internet.pass', 'pppoe.internet.pass',
})
_EVENT_TYPES = frozenset({
    'CREATED', 'ACTION_STARTED', 'ACTION_OUTCOME', 'STEP_COMPLETED',
    'WAITING_OPERATOR', 'OPERATOR_RESPONSE', 'FINALIZED',
})


def _unconfigured_action(_context):
    raise RuntimeError('Local runner is not configured')


def build_service(session, settings, resolver, runtime=None):
    repo = SkillExecutionRepository(session)
    service = SkillExecutionService(repo,
        credential_available=runtime.available if runtime is not None else resolver.available)
    service.coordinator = SkillCoordinator(repo,
        execute=runtime.execute if runtime is not None else _unconfigured_action,
        secrets_for=runtime.secrets_for if runtime is not None else None,
        storage=EvidenceStorage(settings.evidence_root, max_bytes=settings.evidence_max_size_mb * 1024 * 1024),
        workspace=Path(settings.local_runner_evidence_root) / 'skill-executions')
    return service


def _local_request(request):
    host = request.app.state.settings.api_bind_host
    local = local_host = False
    try:
        local = host.casefold() == 'localhost' or ip_address(host).is_loopback
        request_host = request.url.hostname or ''
        local_host = request_host.casefold() == 'localhost' or ip_address(request_host).is_loopback
    except ValueError:
        local_host = False
    origin = request.headers.get('origin')
    if not local or not local_host or (origin and urlparse(origin).netloc != request.url.netloc):
        raise HTTPException(403, 'Skill execution requires local same-origin access')
    if request.headers.get('sec-fetch-site') == 'cross-site':
        raise HTTPException(403, 'Cross-site execution request rejected')


def get_service(request: Request, session: SessionDependency):
    _local_request(request)
    return build_service(session, request.app.state.settings, request.app.state.credential_resolver,
        getattr(request.app.state, 'skill_execution_runtime', None))


ServiceDependency = Annotated[SkillExecutionService, Depends(get_service)]


def _execution(service, session_id):
    try:
        execution = service.repository.get(session_id)
    except LookupError:
        raise HTTPException(404, 'Skill execution not found') from None
    result = service.repository.session.get(RunResult, execution.run_result_id) if execution.run_result_id else None
    if (execution.mode != 'DEVELOPMENT' or not execution.plugin_snapshot or
        execution.plugin_snapshot.get('code') != 'ONU_LOCAL_RUNNER' or result is None or
        result.result_source != 'LOCAL_RUNNER' or not result.skill_snapshot):
        raise HTTPException(404, 'Skill execution not found')
    return execution, result


def _observations(events):
    items = {}
    for event in events:
        if event.event_type != 'ACTION_OUTCOME':
            continue
        for item in event.payload_json.get('observations', []):
            key, value, source = item.get('fact_key'), item.get('value'), item.get('source')
            if source not in {'MA5800', 'ONU_WEB', 'PC_PROBE'}:
                continue
            if key in _BOOLEAN_FACTS and isinstance(value, bool):
                items[key] = dict(fact_key=key, value=value, source=source)
            elif (isinstance(key, str) and re.fullmatch(
                r'(ipoe|pppoe)\.ping\.(packets_sent|packets_received|loss_percent|latency_avg_ms)', key)
                and type(value) in (float, int) and isfinite(value)):
                items[key] = dict(fact_key=key, value=value, source=source)
    return list(items.values())


def _pending(execution, result):
    pending = next((item for item in execution.operator_interactions if item.status == 'PENDING'), None)
    if pending is None:
        return None
    preview = pending.impact_preview or {}
    raw = preview.get('target', preview)
    target = {}
    for key in ('frame', 'slot', 'pon_port', 'ont_id'):
        value = raw.get(key)
        if type(value) is int and 0 <= value <= 65535:
            target[key] = value
    fsp = raw.get('target_fsp')
    if isinstance(fsp, str) and re.fullmatch(r'\d+/\d+/\d+', fsp):
        target['fsp'] = fsp
    serial = raw.get('serial_number', raw.get('onu_serial_number'))
    if isinstance(serial, str) and re.fullmatch(r'[0-9A-Fa-f]{16}', serial):
        target['serial_number'] = serial
    step = next((s for s in result.run.execution_plan_snapshot['steps']
        if s['ref'] == pending.interaction_ref), {})
    ports = [value for value in preview.get('affected_service_ports', [])
        if type(value) is int and 0 <= value <= 65535]
    return dict(id=pending.id, ref=pending.interaction_ref, type=pending.interaction_type,
        risk_level=pending.risk_level, title=pending.interaction_ref,
        instructions='请核对目标及影响范围；确认后不会立即执行，需再次推进。UNABLE/CANCEL 将阻塞或转入恢复。',
        completion_condition='选择有效选项，并确认当前 preview_hash。',
        options=pending.options_json, preview_hash=preview.get('preview_hash', ''), target=target,
        action_code=step.get('action'), affected_service_ports=ports)


def _view(service, session_id, configured):
    execution, result = _execution(service, session_id)
    events = service.repository.events(session_id)
    return dict(session_id=execution.id, test_run_id=execution.test_run_id, run_result_id=result.id,
        skill_code=result.skill_snapshot['skill_code'], skill_version=result.skill_snapshot['version'],
        wan_mode=result.parameter_snapshot['execution_mode'], mode=execution.mode, status=execution.status,
        integrity_status=result.integrity_status, result=result.result, functional_verdict=result.functional_verdict,
        evidence_complete=(result.evidence_validation or {}).get('complete'), runner_configured=configured,
        events=[dict(sequence_no=e.sequence_no, type=e.event_type, step_ref=e.step_ref, occurred_at=e.occurred_at)
            for e in events if e.event_type in _EVENT_TYPES], observations=_observations(events),
        pending_interaction=_pending(execution, result),
        recovery_tasks=[dict(id=t.id, status=t.status,
            instructions='请人工核对注册、WAN 和 service-port；未确认恢复前不要重复执行。') for t in execution.recovery_tasks])


def _configured(request):
    return getattr(request.app.state, 'skill_execution_runtime', None) is not None


def _no_store(response):
    response.headers['Cache-Control'] = 'no-store'


@router.post('', response_model=ExecutionRead, status_code=201)
def create_execution(payload: ExecutionCreate, request: Request, response: Response, service: ServiceDependency):
    _no_store(response)
    with request.app.state.skill_execution_lock:
        try:
            execution = service.create_execution(payload.to_command())
        except ValueError as error:
            code = 409 if str(error) == 'Device already has an active execution' else 422
            raise HTTPException(code, 'Active execution conflict' if code == 409 else 'Invalid execution parameters') from None
        except (ParameterValidationError, InvalidCredentialReferenceError, UnavailableCredentialError):
            raise HTTPException(422, 'Invalid execution parameters or credential references') from None
        except IntegrityError:
            raise HTTPException(409, 'Execution creation conflict') from None
        return _view(service, execution.id, _configured(request))


@router.get('/{session_id}', response_model=ExecutionRead)
def get_execution(session_id: str, request: Request, response: Response, service: ServiceDependency):
    _no_store(response)
    return _view(service, session_id, _configured(request))


def _mutate(request, service, session_id, operation):
    with request.app.state.skill_execution_lock:
        _execution(service, session_id)
        if not _configured(request):
            raise HTTPException(409, 'Local runner is not configured; no action executed')
        try:
            operation()
        except (ValueError, IntegrityError):
            service.repository.session.rollback()
            raise HTTPException(409, 'Execution state or operator approval conflict') from None
        return _view(service, session_id, True)


@router.post('/{session_id}/advance', response_model=ExecutionRead)
def advance_execution(session_id: str, request: Request, response: Response, service: ServiceDependency):
    _no_store(response)
    return _mutate(request, service, session_id, lambda: service.advance(session_id))


@router.post('/{session_id}/interactions/{interaction_id}/respond', response_model=ExecutionRead)
def respond_execution(session_id: str, interaction_id: str, payload: InteractionResponse,
    request: Request, response: Response, service: ServiceDependency):
    _no_store(response)
    return _mutate(request, service, session_id,
        lambda: service.respond(session_id, interaction_id, payload.model_dump()))


@router.get('/{session_id}/evidence', response_model=list[ExecutionEvidenceRead])
def execution_evidence(session_id: str, request: Request, response: Response, service: ServiceDependency):
    _no_store(response)
    _execution(service, session_id)
    artifacts = service.repository.session.scalars(select(Evidence).where(
        Evidence.execution_session_id == session_id).order_by(Evidence.created_at, Evidence.id)).all()
    for item in artifacts:
        _verified_content(service, item)
    return [dict(id=item.id, category=item.category, media_type=item.media_type,
        file_size=item.file_size, sha256=item.sha256, created_at=item.created_at,
        step_ref=item.step_ref, rule_code=item.evidence_rule_code, capture_method=item.capture_method,
        redacted=item.redacted, download_url=request.app.state.settings.api_prefix +
            '/skill-executions/' + session_id + '/evidence/' + item.id + '/download')
        for item in artifacts]


def _verified_content(service, item):
    try:
        content = service.coordinator.storage.open_path(item.storage_path).read_bytes()
    except EvidenceFileMissingError:
        raise HTTPException(410, 'Evidence file is missing') from None
    except (OSError, ValueError):
        raise HTTPException(409, 'Evidence integrity cannot be verified') from None
    if len(content) != item.file_size or sha256(content).hexdigest() != item.sha256 or item.redacted is not True:
        raise HTTPException(409, 'Evidence integrity check failed')
    return content


@router.get('/{session_id}/evidence/{evidence_id}/download')
def download_execution_evidence(session_id: str, evidence_id: str, service: ServiceDependency):
    _execution(service, session_id)
    item = service.repository.session.scalar(select(Evidence).where(
        Evidence.id == evidence_id, Evidence.execution_session_id == session_id))
    if item is None:
        raise HTTPException(404, 'Execution evidence not found')
    content = _verified_content(service, item)
    # Return exactly the bytes checked, not a file reopened after validation.
    extension = {'image/png': '.png', 'text/plain': '.txt'}.get(item.media_type, '.bin')
    return Response(content=content, media_type='application/octet-stream', headers={
        'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
        'Content-Disposition': 'attachment; filename="' + item.id + extension + '"',
    })
