from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
import re
from typing import Any
from sqlalchemy import select
from app.models.device import Device
from app.models.environment import EnvironmentProfile, RunEnvironmentSnapshot
from app.models.execution_session import ExecutionSession
from app.models.test_execution import TestProject, TestRun, RunResult
from app.models.test_intelligence import TestSkill
from app.skill_catalog.onu_registration_dual_wan import CATALOG
from app.skill_catalog.service import SkillCatalogService, catalog_definition_hash
from app.skill_catalog.repository import SkillCatalogRepository
from app.test_execution.run_numbers import next_run_no
from app.test_execution.snapshots import build_device_snapshot, build_case_snapshot
from app.environments.snapshots import build_environment_snapshot
from app.skill_execution.repository import SkillExecutionRepository


@dataclass(frozen=True)
class CreateSkillExecutionCommand:
    project_id: str
    device_id: str
    environment_id: str
    skill_id: str
    parameters: dict[str, Any]


class RuntimeBindingRequiredError(ValueError):
    pass


class SkillExecutionService:
    def __init__(self, repository: SkillExecutionRepository, *, credential_available, coordinator=None,
                 binding_resolver=None, runtime_factory=None):
        self.repository = repository
        self.credential_available = credential_available
        self.coordinator = coordinator
        self.binding_resolver = binding_resolver
        self.runtime_factory = runtime_factory

    def create_execution(self, command: CreateSkillExecutionCommand) -> ExecutionSession:
        db = self.repository.session
        try:
            # Serialize create/check/allocation on SQLite without a new schema.
            connection = db.connection()
            if connection.dialect.name != 'sqlite':
                raise ValueError('Local SQLite execution repository required')
            if connection.connection.driver_connection.in_transaction:
                raise ValueError('Creation requires a clean transaction boundary')
            connection.exec_driver_sql('BEGIN IMMEDIATE')
            project = db.get(TestProject, command.project_id)
            device = db.get(Device, command.device_id)
            environment = db.get(EnvironmentProfile, command.environment_id)
            skill = db.get(TestSkill, command.skill_id)
            if project is None or device is None or environment is None or not environment.enabled:
                raise ValueError('Project, device and enabled environment are required')
            active = list(db.scalars(select(ExecutionSession).join(TestRun,
                ExecutionSession.test_run_id == TestRun.id).where(
                    TestRun.device_source_id == device.id,
                    ExecutionSession.status.not_in(['COMPLETED','BLOCKED','ERROR','CANCELLED']))))
            if active:
                raise ValueError('Device already has an active execution')
            if skill is None or skill.skill_code != CATALOG.skill_code or skill.version != CATALOG.version or skill.status != 'DRAFT':
                raise ValueError('Only the exact development ONU catalog is supported')
            catalog = SkillCatalogService(SkillCatalogRepository(db)).get(skill.id)
            if catalog['definition_hash'] != catalog_definition_hash():
                raise ValueError('Catalog definition conflict')
            if catalog['runner_statuses'] != ['DEVELOPMENT']:
                raise ValueError('Development runner binding required')
            parameters = {p.key: deepcopy(p.default) for p in CATALOG.parameters if p.default is not None}
            parameters.update({p.param_key: p.param_value for p in environment.parameters})
            parameters.update(deepcopy(command.parameters))
            self._validate_parameters(parameters, device)
            runtime_binding = self.binding_resolver(parameters) if self.binding_resolver else None
            profile = SkillCatalogRepository(db).get_profile(CATALOG.standard_profile_code)
            if profile is None or profile.status != 'DRAFT' or not skill.case_bindings:
                raise ValueError('Development standard and case binding required')
            rules = [{'code': binding.requirement.requirement_code, 'fact_key': binding.fact_key,
                'operator': binding.requirement.operator, 'expected': deepcopy(binding.requirement.expected_value),
                'required': binding.requirement.requirement_level == 'MANDATORY',
                'standard_code': binding.requirement.standard.standard_code,
                'standard_version': binding.requirement.standard.version}
                for binding in skill.standard_bindings]
            evidence_rules = [{'rule_code': item.rule_code, 'min_count': item.min_count,
                'capture_methods': list(next(e.capture_methods for e in CATALOG.evidence if e.code == item.rule_code))}
                for item in skill.evidence_rules]
            from app.skill_execution.coordinator import build_plan, build_service_port_plan
            frozen_profile = runtime_binding.service_port_profile if runtime_binding is not None else None
            plan_snapshot = (build_service_port_plan(parameters, frozen_profile) if frozen_profile is not None
                             else {'version': 1, 'steps': build_plan(parameters)})
            run = TestRun(run_no=next_run_no(db), project_id=project.id, device_source_id=device.id,
                device_snapshot=build_device_snapshot(device), source='LOCAL_RUNNER',
                execution_status='CREATED', execution_plan_snapshot=plan_snapshot,
                standard_profile_source_id=profile.id,
                standard_snapshot={'profile_code': profile.profile_code, 'version': profile.version, 'rules': rules})
            result = RunResult(case_source_id=skill.case_bindings[0].test_case_id,
                case_snapshot=build_case_snapshot(skill.case_bindings[0].test_case), skill_source_id=skill.id,
                skill_snapshot={**deepcopy(catalog), 'evidence_rules': evidence_rules},
                parameter_snapshot=deepcopy(parameters), result_source='LOCAL_RUNNER', recovery_status='NOT_REQUIRED')
            run.results = [result]
            run.environment_snapshot = RunEnvironmentSnapshot(environment_profile_source_id=environment.id,
                profile_snapshot=build_environment_snapshot(environment, datetime.now(UTC)))
            db.add(run)
            db.flush()
            plugin_snapshot = {'code': 'ONU_LOCAL_RUNNER', 'version': CATALOG.version}
            if runtime_binding is not None:
                plugin_snapshot['runtime_binding'] = runtime_binding.model_dump(mode='json')
            execution = ExecutionSession(test_run_id=run.id, run_result_id=result.id,
                mode='DEVELOPMENT', status='CREATED', plugin_snapshot=plugin_snapshot)
            db.add(execution)
            db.flush()
            result.execution_session_id = execution.id
            self.repository.append_event(execution.id, 'CREATED', {'schema_version': 1}, 'created')
            db.commit()
            return execution
        except Exception:
            db.rollback()
            raise

    def _validate_parameters(self, parameters, device):
        extra = {'ipoe_ip_index', 'pppoe_ip_index', 'olt_vendor'}
        allowed = {p.key for p in CATALOG.parameters} | extra
        if set(parameters) - allowed:
            raise ValueError('Unknown or unsafe execution parameter')
        for definition in CATALOG.parameters:
            value = parameters.get(definition.key)
            if definition.required and (value is None or value == ''):
                raise ValueError('Required execution parameter missing')
            if definition.data_type == 'INTEGER':
                if isinstance(value, str) and value.isascii() and value.isdigit():
                    value = parameters[definition.key] = int(value)
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ValueError('Integer parameter required')
                if value < definition.constraints.get('minimum', 0) or value > definition.constraints.get('maximum', 4095):
                    raise ValueError('Integer parameter out of range')
            elif definition.data_type == 'ENUM' and value not in definition.constraints['choices']:
                raise ValueError('Unsupported enum value')
            elif definition.data_type == 'STRING' and not isinstance(value, str):
                raise ValueError('String parameter required')
            if definition.sensitive:
                if not re.fullmatch(r'[A-Za-z0-9._:-]{1,200}', value):
                    raise ValueError('Credential reference required, never plaintext')
                if not self.credential_available(value):
                    raise ValueError('Credential reference unavailable')
        if parameters.get('olt_vendor', 'Huawei MA5800-X7') != 'Huawei MA5800-X7':
            raise ValueError('Unsupported OLT vendor')
        if parameters['evaluation_policy'] != 'STRICT_PER_WAN':
            raise ValueError('Simplified policy has no approved customer standard')
        if parameters['onu_serial_number'].upper() != device.serial_number.upper():
            raise ValueError('Device and execution serial do not match')
        from app.local_runner.ma5800.actions import _validated_target, _wan_indexes
        _validated_target(parameters)
        try:
            _wan_indexes(parameters)
        except Exception as error:
            raise ValueError('Invalid WAN indexes') from error
        if not re.fullmatch(r'[A-Za-z0-9.-]{1,253}', parameters['ping_target']):
            raise ValueError('Invalid Ping target')

    def advance(self, session_id):
        if self.coordinator is None:
            raise RuntimeError('Runner coordinator is not configured')
        self._bind_runtime(session_id)
        return self.coordinator.advance(session_id)

    def respond(self, session_id, interaction_id, response):
        if self.coordinator is None:
            raise RuntimeError('Runner coordinator is not configured')
        self._bind_runtime(session_id)
        return self.coordinator.respond(session_id, interaction_id, response)

    def _bind_runtime(self, session_id):
        if self.runtime_factory is None:
            return  # Existing lower-level offline service composition remains supported.
        from app.local_runner.configuration import RuntimeBinding
        execution = self.repository.get(session_id)
        snapshot = execution.plugin_snapshot or {}
        try:
            binding = RuntimeBinding.model_validate(snapshot['runtime_binding'])
        except (KeyError, ValueError, TypeError):
            raise RuntimeBindingRequiredError('RUNTIME_BINDING_REQUIRED') from None
        runtime = self.runtime_factory.for_binding(binding,
            lambda: self.repository.events(session_id))
        self.coordinator.execute = runtime.execute
        self.coordinator.secrets_for = runtime.secrets_for

    def get_view(self, session_id):
        execution = self.repository.get(session_id)
        return {'session_id': execution.id, 'test_run_id': execution.test_run_id,
                'run_result_id': execution.run_result_id, 'status': execution.status,
                'events': [{'type': event.event_type, 'step_ref': event.step_ref,
                            'payload': deepcopy(event.payload_json)} for event in self.repository.events(session_id)]}
