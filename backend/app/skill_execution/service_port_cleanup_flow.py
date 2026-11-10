"""Explicit end/recovery cleanup, without altering frozen execution plans."""
from copy import deepcopy
from uuid import uuid4
from app.local_runner.contracts import ActionContext
from app.local_runner.ma5800.service_port_contracts import PortOperation, PortPreview, read_port_payload
from app.models.test_execution import RunResult
from app.skill_execution.service_port_ledger import replay_port_ledger
from app.skill_execution.service_port_lifecycle import ServicePortLifecycle, cleanup_batch_payload


def cleanup_stage(repository, session_id):
    execution = repository.get(session_id)
    result = repository.session.get(RunResult, execution.run_result_id)
    waiting_end = (execution.status == 'WAITING_OPERATOR' and
        any(i.status == 'PENDING' and i.interaction_ref == 'END_POLICY' for i in execution.operator_interactions) and
        all(i.interaction_ref == 'END_POLICY' for i in execution.operator_interactions if i.status == 'PENDING'))
    recovery = execution.status == 'RECOVERY_REQUIRED' and result.recovery_status == 'MANUAL_REQUIRED'
    if (execution.mode != 'DEVELOPMENT' or execution.plugin_snapshot.get('code') != 'ONU_LOCAL_RUNNER'
        or result.integrity_status != 'DRAFT' or result.run.execution_plan_snapshot.get('version') != 2
        or result.parameter_snapshot.get('end_policy') != 'KEEP' or not (waiting_end or recovery)):
        raise ValueError('Cleanup requires end confirmation or manual recovery')
    return execution, result


class ServicePortCleanupFlow:
    def __init__(self, coordinator):
        self.engine = coordinator
        self.repository = coordinator.repository

    def _request_scope(self, sid):
        execution, result = cleanup_stage(self.repository, sid)
        resources = replay_port_ledger(sid, self.repository.events(sid))
        if any(r.state not in {'REUSED', 'ACTIVE', 'RETAINED', 'DELETED'} for r in resources):
            raise ValueError('Uncertain resource must not acquire cleanup authority')
        events = self.repository.events(sid)
        finished = {e.payload_json['preview_hash'] for e in events if e.event_type == 'SERVICE_PORT_CLEANUP_OUTCOME'}
        if any(e.event_type == 'SERVICE_PORT_CLEANUP_STARTED' and e.payload_json['preview_hash'] not in finished for e in events):
            raise ValueError('Interrupted cleanup cannot be retried')
        return execution, result, resources

    def _lifecycle(self, sid, result):
        engine, repo = self.engine, self.repository
        def context(action, mapping, operation=None, approval=None):
            parameters = deepcopy(result.parameter_snapshot)
            parameters['service_port_mapping'] = mapping.model_dump(mode='json')
            if operation is not None:
                parameters.update(port_operation=operation.model_dump(mode='json'), port_approval=approval)
            return ActionContext(sid, action, parameters, engine.secrets_for(parameters, action), engine.workspace / sid)
        inspect = lambda _sid, mapping: engine.execute(context('inspect_service_port', mapping))
        return ServicePortLifecycle(repo, inspect_device=inspect, inspect_cleanup_device=inspect,
            create_device=None, delete_device=lambda op, approval: engine.execute(context('delete_service_port', op.mapping, op, approval)),
            persist_evidence=lambda _sid, outcome: engine._store_artifacts(repo.get(sid), result,
                dict(step='FINISH', method='OLT_RENDER'), outcome.artifacts), storage=engine.storage, cleanup_flow=True)

    def preview(self, sid):
        _, result, resources = self._request_scope(sid)
        retained = frozenset(c for r in resources if r.state == 'RETAINED' for c in r.consumers)
        previews = self._lifecycle(sid, result).preview_cleanup(sid, retained)
        batch = cleanup_batch_payload(previews, retained)
        self.repository.append_event(sid, 'SERVICE_PORT_CLEANUP_REQUESTED', batch, 'cleanup-request-' + uuid4().hex)
        self.repository.session.commit()
        return self.repository.get(sid)

    def execute(self, sid, approval_hash, approved):
        if approved is not True:
            raise ValueError('Explicit cleanup approval required')
        # Check immutable/terminal scope even for repeated requests; never resurrect history.
        execution, result = cleanup_stage(self.repository, sid)
        events = self.repository.events(sid)
        request = next((e for e in reversed(events) if e.event_type == 'SERVICE_PORT_CLEANUP_REQUESTED'), None)
        if request is None or request.payload_json.get('preview_hash') != approval_hash:
            raise ValueError('Cleanup approval is stale')
        if any(e.event_type == 'SERVICE_PORT_CLEANUP_OUTCOME' and e.payload_json['preview_hash'] == approval_hash for e in events):
            return execution  # Durable final outcome: no reads, writes or retry, including failed batches.
        self._request_scope(sid)
        batch = request.payload_json
        previews = tuple(PortPreview(PortOperation.model_validate(p['operation']), read_port_payload(p['read'])) for p in batch['previews'])
        if cleanup_batch_payload(previews, frozenset(batch['retained_consumers'])) != batch:
            raise ValueError('Cleanup scope cannot be verified')
        for interaction in execution.operator_interactions:
            if interaction.status == 'PENDING':
                interaction.status = 'CANCELLED'
        self.engine._recovery(execution)
        self.repository.append_event(sid, 'SERVICE_PORT_CLEANUP_STARTED', {'preview_hash': approval_hash}, 'cleanup-start-' + approval_hash, require_new=True)
        self.repository.session.commit()  # Intent survives interruption before any device I/O.
        outcome = self._lifecycle(sid, result).cleanup(sid, previews, approval_hash)
        cleanup_stage(self.repository, sid)  # Never resurrect a terminal/LOCKED scope changed during I/O.
        items = next((o.value for o in outcome.observations if o.fact_key == 'port.cleanup.items'), [])
        self.repository.append_event(sid, 'SERVICE_PORT_CLEANUP_OUTCOME',
            dict(preview_hash=approval_hash, status=outcome.status, items=items), 'cleanup-outcome-' + approval_hash)
        self.engine._recovery(self.repository.get(sid))
        self.repository.session.commit()
        return self.repository.get(sid)

    def view(self, sid):
        events = self.repository.events(sid)
        try:
            self._request_scope(sid)
            available = True
        except ValueError:
            available = False
        request = next((e for e in reversed(events) if e.event_type == 'SERVICE_PORT_CLEANUP_REQUESTED'), None)
        finished = next((e for e in reversed(events) if e.event_type == 'SERVICE_PORT_CLEANUP_OUTCOME'), None)
        pending = request.payload_json if available and request is not None and not any(
            e.event_type in {'SERVICE_PORT_CLEANUP_STARTED', 'SERVICE_PORT_CLEANUP_OUTCOME'} and
            e.payload_json['preview_hash'] == request.payload_json['preview_hash'] for e in events) else None
        return available, pending, finished.payload_json if finished else None
