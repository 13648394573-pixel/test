from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
from sqlalchemy import select
from app.evidence.storage import EvidenceStorage
from app.models.evidence import Evidence
from app.models.evidence_link import EvidenceRunResultLink
from app.models.execution_session import ConfigurationSnapshot, ExecutionSession, OperatorInteraction, RecoveryTask
from app.models.test_execution import RunResult, TestRun, seal_result_derived_snapshots
from app.test_execution.repository import TestExecutionRepository
from app.test_execution.service import TestExecutionService
from app.local_runner.contracts import ActionContext
from app.skill_execution.evaluator import evaluate


MUTATIONS = frozenset({'delete_ont','register_ont','provision_ipoe','provision_pppoe',
                       'remove_test_services','restore_snapshot'})
TERMINAL = frozenset({'COMPLETED','BLOCKED','ERROR','CANCELLED'})


def build_plan(parameters):
    def action(ref, code, step, group=None, method='OLT_RENDER', wan=None):
        return dict(ref=ref, action=code, step=step, group=group, method=method, wan=wan)
    def interaction(ref, choices, step):
        return dict(ref=ref, interaction=choices, step=step)
    plan = [action('PREFLIGHT','preflight','PREFLIGHT'),
        action('AUTOFIND','discover_onts','AUTOFIND','E1_OLT_AUTOFIND'),
        action('SNAPSHOT','snapshot_ont','REGISTER'),
        action('FREE_ID','find_free_ont_id','REGISTER'),
        action('DELETE_EXISTING','delete_ont','REGISTER'),
        action('REGISTER','register_ont','REGISTER'),
        action('REGISTER_VERIFY','snapshot_ont','REGISTER','E2_REGISTRATION'),
        action('PROVISION_IPOE','provision_ipoe','IPOE_ADDRESS')]
    concurrent = parameters.get('execution_mode') == 'CONCURRENT_DUAL_WAN'
    if concurrent:
        plan.append(action('PROVISION_PPPOE','provision_pppoe','PPPOE_ADDRESS'))
    for wan, address_group, ping_group in [('IPOE','E3_IPOE_ADDRESS','E4_IPOE_PING'),
                                          ('PPPOE','E5_PPPOE_ADDRESS','E6_PPPOE_PING')]:
        if wan == 'PPPOE' and not concurrent:
            plan += [action('REMOVE_IPOE_SERVICES','remove_test_services','PPPOE_ADDRESS'),
                interaction('ISOLATE_IPOE',['IPOE_DISABLED','UNABLE','CANCEL'],'PPPOE_ADDRESS'),
                action('PROVISION_PPPOE','provision_pppoe','PPPOE_ADDRESS')]
        if concurrent:
            plan.append(interaction(f'SWITCH_{wan}',[f'{wan}_ACTIVE','UNABLE','CANCEL'],f'{wan}_PING'))
        plan += [action(f'{wan}_ADDRESS_OLT','read_wan_info',f'{wan}_ADDRESS',address_group,wan=wan),
                 action(f'{wan}_ADDRESS_WEB','capture_onu_wan',f'{wan}_ADDRESS',address_group,'ONU_WEB',wan),
                 action(f'{wan}_PING_ONU','run_onu_ping',f'{wan}_PING',ping_group,'ONU_WEB',wan),
                 action(f'{wan}_PING_PC','pc_connectivity_probe',f'{wan}_PING',ping_group,'PC_PROBE',wan)]
    return plan + [interaction('END_POLICY',['RESTORE','KEEP','CANCEL'],'FINISH'),
                   action('RESTORE','restore_snapshot','FINISH'),
                   action('RESTORE_VERIFY','snapshot_ont','FINISH')]


def _clean(value, secrets=()):
    if isinstance(value, dict):
        return {key: _clean(item, secrets) for key, item in value.items()
                if not re.search(r'(?i)password|passwd|secret|token|loid|raw_fields|raw_output', key)}
    if isinstance(value, (list, tuple)):
        return [_clean(item, secrets) for item in value]
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, '[REDACTED]')
    return value


class SkillCoordinator:
    """One durable action per call; driver composition is supplied by Task 9."""
    def __init__(self, repository, *, execute, storage: EvidenceStorage, workspace: Path, secrets_for=None):
        self.repository = repository
        self.execute = execute
        self.storage = storage
        self.workspace = Path(workspace)
        self.secrets_for = secrets_for or (lambda parameters, action: {})

    def _set_status(self, execution, status):
        execution.status = status
        self.repository.session.get(TestRun, execution.test_run_id).execution_status = status

    def advance(self, session_id):
        repo = self.repository
        db = repo.session
        execution = repo.get(session_id)
        if execution.status in TERMINAL or execution.status == 'WAITING_OPERATOR':
            return execution
        if execution.status == 'RECOVERY_REQUIRED':
            self._recovery(execution)
            db.commit()
            return execution
        run = db.get(TestRun, execution.test_run_id)
        result = db.get(RunResult, execution.run_result_id)
        if result.integrity_status == 'LOCKED':
            raise ValueError('Locked result cannot execute')
        events = repo.events(session_id)
        starts = {e.idempotency_key.removesuffix(':start') for e in events if e.event_type == 'ACTION_STARTED'}
        outcomes = {e.idempotency_key.removesuffix(':outcome') for e in events if e.event_type == 'ACTION_OUTCOME'}
        if starts - outcomes:
            self._recovery(execution)
            db.commit()
            return execution
        completed = {e.payload_json['ref'] for e in events if e.event_type == 'STEP_COMPLETED'}
        failed = any(e.event_type == 'ACTION_OUTCOME' and e.payload_json['status'] in {'FAIL','BLOCKED','ERROR'} for e in events)
        end = next((e.payload_json.get('choice') for e in events if e.event_type == 'OPERATOR_RESPONSE' and e.step_ref == 'END_POLICY'), None)
        for step in run.execution_plan_snapshot['steps']:
            if step['ref'] in completed:
                continue
            if failed and step['step'] != 'FINISH':
                continue
            if step['ref'] in {'RESTORE','RESTORE_VERIFY'} and end == 'KEEP':
                continue
            if step['ref'] == 'DELETE_EXISTING' and not self._snapshot(execution).get('registration'):
                continue
            if 'interaction' in step:
                self._interaction(execution, step, step['interaction'], self._preview(result, step))
                db.commit()
                return execution
            return self._action(execution, result, step, events)
        return self._finalize(execution)

    def _snapshot(self, execution):
        return deepcopy(execution.configuration_snapshots[0].snapshot_json) if execution.configuration_snapshots else {}

    @staticmethod
    def _owned_snapshot_ports(parameters):
        snapshot = parameters.get('configuration_snapshot')
        ports = snapshot.get('service_ports') if isinstance(snapshot, dict) else None
        if not isinstance(ports, list):
            raise ValueError('Configuration service-port scope is unconfirmed')
        target_fsp = '/'.join(str(parameters[key]) for key in ('frame', 'slot', 'pon_port'))
        seen, owned = set(), []
        for item in ports:
            if (not isinstance(item, dict) or type(item.get('service_port_id')) is not int
                    or not 0 <= item['service_port_id'] <= 65535
                    or not isinstance(item.get('fsp'), str)
                    or re.fullmatch(r'(?:0|[1-9][0-9]*)/(?:0|[1-9][0-9]*)/(?:0|[1-9][0-9]*)', item['fsp']) is None
                    or type(item.get('ont_id')) is not int or not 0 <= item['ont_id'] <= 127
                    or item['service_port_id'] in seen):
                raise ValueError('Configuration service-port scope is unconfirmed')
            seen.add(item['service_port_id'])
            if item['fsp'] == target_fsp and item['ont_id'] == parameters['ont_id']:
                owned.append(item['service_port_id'])
        return sorted(owned)

    def _preview(self, result, step):
        target = {key: result.parameter_snapshot[key] for key in
                  ('frame','slot','pon_port','ont_id','onu_serial_number')}
        payload = {'ref':step['ref'], 'target':target, 'default':result.parameter_snapshot.get('end_policy')}
        return {**payload, 'preview_hash':sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()}

    def _interaction(self, execution, step, choices, preview):
        db = self.repository.session
        pending = next((i for i in execution.operator_interactions if i.interaction_ref == step['ref'] and i.status == 'PENDING'), None)
        if pending is not None:
            return pending
        connection_wait = step.get('action') == 'pc_connectivity_probe'
        interaction = next((i for i in execution.operator_interactions
                            if connection_wait and i.interaction_ref == step['ref']), None)
        if interaction is None:
            interaction = OperatorInteraction(session_id=execution.id, interaction_ref=step['ref'],
                interaction_type='SELECTION' if 'interaction' in step else 'CONFIRMATION',
                risk_level='LOW' if connection_wait else 'HIGH',
                title=step['ref'], instructions='Confirm the exact target and impact; UNABLE/CANCEL blocks execution.',
                completion_condition='Valid choice, explicit approval and exact preview hash.', options_json=choices,
                impact_preview=deepcopy(preview))
            db.add(interaction)
        else:
            # Only a non-mutating wiring check may reopen its interaction. Durable events preserve prior responses.
            interaction.status = 'PENDING'
            interaction.response_json = None
            interaction.responded_at = None
            interaction.impact_preview = deepcopy(preview)
        waiting_key = step['ref'] + ':waiting' + (':' + preview['preview_hash'] if connection_wait else '')
        self.repository.append_event(execution.id,'WAITING_OPERATOR',{'ref':step['ref']},waiting_key,step_ref=step['ref'])
        self._set_status(execution,'WAITING_OPERATOR')
        return interaction

    def respond(self, session_id, interaction_id, response):
        repo = self.repository
        db = repo.session
        execution = repo.get(session_id)
        interaction = db.get(OperatorInteraction, interaction_id)
        if (execution.status != 'WAITING_OPERATOR' or interaction is None or
            interaction.session_id != session_id or interaction.status != 'PENDING'):
            raise ValueError('Stale operator interaction')
        if set(response) - {'choice','approved','preview_hash'}:
            raise ValueError('Unknown operator response field')
        choice = response.get('choice')
        if choice not in interaction.options_json or response.get('preview_hash') != interaction.impact_preview['preview_hash']:
            raise ValueError('Invalid choice or preview hash')
        if choice not in {'CANCEL','UNABLE'} and response.get('approved') is not True:
            raise ValueError('Explicit confirmation required')
        interaction.response_json = deepcopy(response)
        interaction.responded_at = datetime.now(UTC).replace(tzinfo=None)
        interaction.status = 'CANCELLED' if choice == 'CANCEL' else 'UNABLE' if choice == 'UNABLE' else 'COMPLETED'
        response_key = interaction.interaction_ref + ':response'
        if (interaction.impact_preview or {}).get('action_code') == 'pc_connectivity_probe':
            response_key += ':' + interaction.impact_preview['preview_hash']
        repo.append_event(session_id,'OPERATOR_RESPONSE',{'ref':interaction.interaction_ref,'choice':choice},
                          response_key,step_ref=interaction.interaction_ref)
        if choice in {'CANCEL','UNABLE'}:
            if execution.recovery_tasks:
                self._recovery(execution)
                db.commit()
                return execution
            self._set_status(execution, 'RUNNING')
            repo.append_event(session_id,'ACTION_OUTCOME',{'ref':interaction.interaction_ref,'status':'BLOCKED','observations':[]},
                              interaction.interaction_ref + ':blocked')
            return self._finalize(execution)
        if interaction.interaction_type == 'SELECTION':
            repo.append_event(session_id,'STEP_COMPLETED',{'ref':interaction.interaction_ref},interaction.interaction_ref + ':done')
            if interaction.interaction_ref == 'END_POLICY' and choice == 'KEEP':
                for task in execution.recovery_tasks:
                    task.status = 'VERIFIED'
                    task.manual_resolution = 'KEEP explicitly selected; restoration waived, not performed.'
                db.get(RunResult, execution.run_result_id).recovery_status = 'NOT_REQUIRED'
        self._set_status(execution,'RUNNING')
        db.commit()
        return execution

    def _action(self, execution, result, step, events):
        repo = self.repository
        db = repo.session
        parameters = deepcopy(result.parameter_snapshot)
        parameters['wan_mode'] = step.get('wan')
        parameters['configuration_snapshot'] = self._snapshot(execution)
        free = [o['value'] for e in events if e.event_type == 'ACTION_OUTCOME'
                for o in e.payload_json.get('observations', []) if o['fact_key'] == 'olt.free_ont_id']
        if free and step['ref'] not in {'SNAPSHOT','DELETE_EXISTING'}:
            parameters['ont_id'] = free[-1]
        if step['action'] in MUTATIONS:
            parameters['affected_service_ports'] = self._owned_snapshot_ports(parameters)
        interaction = next((i for i in execution.operator_interactions if i.interaction_ref == step['ref'] and i.status == 'COMPLETED'), None)
        if interaction is not None:
            parameters['mutation_approval'] = {'approved':True,'preview_hash':interaction.impact_preview['preview_hash']}
        attempt = 1 + sum(e.event_type == 'ACTION_STARTED' and e.payload_json['ref'] == step['ref'] for e in events)
        key = f"{step['ref']}:{attempt}"
        try:
            repo.append_event(execution.id,'ACTION_STARTED',{'ref':step['ref'],'attempt':attempt},key + ':start',
                              step_ref=step['step'],action_ref=step['action'],require_new=True)
            self._set_status(execution,'RESTORING' if step['step'] == 'FINISH' else 'RUNNING')
            db.commit()
        except Exception:
            db.rollback()
            raise ValueError('Execution action already claimed') from None
        secrets = {}
        try:
            secrets = self.secrets_for(parameters, step['action'])
            outcome = self.execute(ActionContext(execution.id, step['action'], parameters, secrets,
                                                 self.workspace / execution.id))
            secret_values = tuple(value.reveal() for value in secrets.values())
            observations = _clean([asdict(o) for o in outcome.observations], secret_values)
            if outcome.status not in {'PASS','FAIL','BLOCKED','ERROR','WAITING_OPERATOR'}:
                raise ValueError('Invalid action status')
            repo.append_event(execution.id,'ACTION_OUTCOME',{'ref':step['ref'],'status':outcome.status,
                'observations':observations},key + ':outcome',step_ref=step['step'],action_ref=step['action'])
            if outcome.status == 'WAITING_OPERATOR':
                preview = next(o['value'] for o in observations if o['fact_key'] == 'mutation.preview')
                self._interaction(execution,step,['CONFIRM','CANCEL'],preview)
                db.commit()
                return execution
            if step['ref'] == 'SNAPSHOT' and outcome.status == 'PASS':
                snapshot = next(o['value'] for o in observations if o['fact_key'] == 'olt.configuration_snapshot')
                encoded = json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()
                db.add(ConfigurationSnapshot(session_id=execution.id,device_ref=result.run.device_source_id,
                    scope_json={'registration':True,'wan':True,'service_ports':True},capture_action_ref='snapshot_ont',
                    snapshot_json=snapshot,sha256=sha256(encoded).hexdigest()))
            if step['action'] in MUTATIONS and outcome.status != 'WAITING_OPERATOR':
                if not execution.recovery_tasks:
                    db.add(RecoveryTask(session_id=execution.id, status='PENDING',
                        configuration_snapshot_id=execution.configuration_snapshots[0].id if execution.configuration_snapshots else None,
                        restore_action_ref='restore_snapshot',verify_action_ref='snapshot_ont'))
                    result.recovery_status = 'PENDING'
            self._store_artifacts(execution,result,step,outcome.artifacts)
            repo.append_event(execution.id,'STEP_COMPLETED',{'ref':step['ref']},step['ref'] + ':done')
            if step['ref'] == 'RESTORE_VERIFY':
                observed = next((o['value'] for o in observations if o['fact_key'] == 'olt.configuration_snapshot'), None)
                if outcome.status != 'PASS' or observed != self._snapshot(execution):
                    self._recovery(execution)
                    db.commit()
                    return execution
                for task in execution.recovery_tasks:
                    task.status = 'VERIFIED'
                result.recovery_status = 'VERIFIED'
            self._set_status(execution, 'RUNNING')
            db.commit()
            return execution
        except Exception:
            db.rollback()
            execution = repo.get(execution.id)
            self._recovery(execution)
            execution.error_code = 'RUNNER_ACTION_INTERRUPTED'
            execution.error_detail = 'Action or evidence persistence failed; inspect and recover manually.'
            db.commit()
            return execution

    def _store_artifacts(self, execution, result, step, artifacts):
        db = self.repository.session
        for artifact in artifacts:
            if artifact.redacted is not True:
                raise ValueError('Unredacted evidence rejected')
            content = artifact.content
            if content is None:
                if artifact.storage_path is None:
                    raise ValueError('Artifact file missing')
                path = (self.workspace / execution.id / artifact.storage_path).resolve()
                root = (self.workspace / execution.id).resolve()
                if root not in path.parents:
                    raise ValueError('Artifact path outside execution workspace')
                content = path.read_bytes()
            if artifact.sha256 is not None and sha256(content).hexdigest() != artifact.sha256:
                raise ValueError('Generated artifact hash mismatch')
            stored = self.storage.store('run-results',result.id,artifact.original_name,BytesIO(content))
            evidence = Evidence(run_result_id=result.id,execution_session_id=execution.id,
                step_ref=step['step'],evidence_rule_code=step.get('group'),capture_method=step['method'],
                redacted=True,category='SCREENSHOT' if artifact.media_type == 'image/png' else 'LOG',
                original_name=artifact.original_name,media_type=artifact.media_type,storage_path=stored.storage_path,
                file_size=stored.file_size,sha256=stored.sha256)
            db.add(evidence)
            db.flush()
            db.add(EvidenceRunResultLink(evidence_id=evidence.id,run_result_id=result.id))

    def _recovery(self, execution):
        db = self.repository.session
        self._set_status(execution,'RECOVERY_REQUIRED')
        result = db.get(RunResult, execution.run_result_id)
        result.recovery_status = 'MANUAL_REQUIRED'
        if not execution.recovery_tasks:
            db.add(RecoveryTask(session_id=execution.id,status='MANUAL_REQUIRED',
                manual_resolution='Inspect full registration, WAN and service-port state before proceeding.'))
        for task in execution.recovery_tasks:
            task.status = 'MANUAL_REQUIRED'

    def recover_interrupted(self):
        db = self.repository.session
        executions = list(db.scalars(select(ExecutionSession).where(
            ExecutionSession.mode == 'DEVELOPMENT',
            ExecutionSession.run_result_id.is_not(None),
            ExecutionSession.plugin_snapshot['code'].as_string() == 'ONU_LOCAL_RUNNER',
            ExecutionSession.status.in_(['RUNNING','RESTORING']))))
        for execution in executions:
            self._recovery(execution)
        db.commit()
        return len(executions)

    def _finalize(self, execution):
        db = self.repository.session
        result = db.get(RunResult,execution.run_result_id)
        if result.integrity_status == 'LOCKED':
            return execution
        if any(task.status != 'VERIFIED' for task in execution.recovery_tasks):
            self._recovery(execution)
            db.commit()
            return execution
        events = self.repository.events(execution.id)
        facts = {o['fact_key']:o['value'] for e in events if e.event_type == 'ACTION_OUTCOME'
                 for o in e.payload_json.get('observations', []) if o['fact_key'] != 'mutation.preview'}
        rules = deepcopy(result.run.standard_snapshot['rules'])
        if any(e.event_type == 'ACTION_OUTCOME' and e.payload_json['status'] == 'FAIL' for e in events):
            rules.append({'code':'ACTION_FAILURE','fact_key':'actions.pass','operator':'EQ','expected':True,'required':True})
            facts['actions.pass'] = False
        blocked = any(e.event_type == 'ACTION_OUTCOME' and e.payload_json['status'] in {'BLOCKED','ERROR'} for e in events)
        evidence = []
        for item in db.scalars(select(Evidence).where(Evidence.execution_session_id == execution.id)):
            try:
                valid = sha256(self.storage.open_path(item.storage_path).read_bytes()).hexdigest() == item.sha256
            except Exception:
                valid = False
            evidence.append(dict(id=item.id,rule_code=item.evidence_rule_code,capture_method=item.capture_method,
                                 category=item.category,redacted=item.redacted,hash_valid=valid))
        blocked |= any(item['hash_valid'] is not True for item in evidence)
        evaluation = evaluate(facts,rules,result.skill_snapshot['evidence_rules'],evidence,blocked=blocked)
        seal_result_derived_snapshots(result,observations=facts,matched_rule_codes=list(evaluation.matched_rule_codes),
            standard_evaluations=list(evaluation.evaluations),evidence_validation={
                'complete':evaluation.evidence_complete,'missing':list(evaluation.missing_evidence)})
        result.functional_verdict = evaluation.functional_verdict
        result.result = evaluation.overall_result
        result.actual_result = 'Skill evaluation completed from immutable snapshots and verified evidence.'
        result.blocked_reason = 'Required observation or evidence unavailable.' if result.result == 'BLOCKED' else None
        self._set_status(execution,'BLOCKED' if result.result == 'BLOCKED' else 'COMPLETED')
        execution.ended_at = datetime.now(UTC).replace(tzinfo=None)
        self.repository.append_event(execution.id,'FINALIZED',{'result':result.result},'finalized')
        if (execution.plugin_snapshot or {}).get('runtime_binding') is not None:
            # Bound development executions require explicit user approval to LOCK via the existing result API.
            db.commit()
        else:
            TestExecutionService(TestExecutionRepository(db),None,None).lock_result(execution.test_run_id,result.id)
        return execution
