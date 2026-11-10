import pytest
from sqlalchemy import select
from app.models.device import Device
from app.models.environment import EnvironmentProfile
from app.models.test_execution import TestProject, TestRun, RunResult
from app.models.execution_session import ExecutionEvent, ExecutionSession
from app.skill_catalog.repository import SkillCatalogRepository
from app.skill_catalog.service import SkillCatalogService
from app.skill_execution.repository import SkillExecutionRepository
from app.skill_execution.service import CreateSkillExecutionCommand, SkillExecutionService


@pytest.fixture
def execution_fixture(db_session):
    install = SkillCatalogService(SkillCatalogRepository(db_session)).install_onu_registration_dual_wan_draft()
    device = Device(device_type='ONU', vendor='Fixture', model='Fixture', serial_number='AABBCCDDEEFF0011')
    project = TestProject(name='Skill lab', version='fixture')
    environment = EnvironmentProfile(name='Fixture environment', enabled=True)
    db_session.add_all([device, project, environment])
    db_session.commit()
    parameters = dict(olt_target_ref='lab.olt', olt_access_ref='olt.access',
        onu_web_target_ref='lab.onu', onu_web_access_ref='onu.access', pppoe_access_ref='ppp.access',
        onu_serial_number=device.serial_number, frame=0, slot=2, pon_port=9, ont_id=12,
        line_profile_id=10, service_profile_id=10, ipoe_vlan=1000, pppoe_vlan=1000,
        ping_target='example.com', ipoe_ip_index=0, pppoe_ip_index=1)
    command = CreateSkillExecutionCommand(project.id, device.id, environment.id, install.skill_id, parameters)
    repository = SkillExecutionRepository(db_session)
    service = SkillExecutionService(repository, credential_available=lambda ref: True)
    return service, repository, command


def test_create_execution_has_one_run_result_and_snapshotted_session(db_session, execution_fixture):
    service, repo, command = execution_fixture
    execution = service.create_execution(command)
    run = db_session.get(TestRun, execution.test_run_id)
    result = db_session.get(RunResult, execution.run_result_id)
    assert run.source == 'LOCAL_RUNNER'
    assert execution.mode == 'DEVELOPMENT'
    assert execution.status == 'CREATED'
    assert result.parameter_snapshot['execution_mode'] == 'SEQUENTIAL_ISOLATED'
    assert result.skill_snapshot['skill_code'] == 'ONU_REGISTRATION_DUAL_WAN_CONNECTIVITY'
    assert len(repo.events(execution.id)) == 1
    assert db_session.scalars(select(TestRun)).all() == [run]
    command.parameters['ipoe_vlan'] = 99
    assert result.parameter_snapshot['ipoe_vlan'] == 1000


@pytest.mark.parametrize('values', [
    {'mutation_approval': {'approved': True}}, {'password': 'do-not-store'},
    {'execution_mode': 'INVALID'}, {'ipoe_ip_index': 1, 'pppoe_ip_index': 1},
    {'olt_vendor': 'Other'}, {'olt_access_ref': 'http://user:pass@device'},
    {'evaluation_policy': 'CUSTOMER_SIMPLIFIED'}, {'ping_target': ''},
])
def test_invalid_creation_leaves_no_run(db_session, execution_fixture, values):
    service, _, command = execution_fixture
    command.parameters.update(values)
    with pytest.raises(ValueError):
        service.create_execution(command)
    assert db_session.scalars(select(TestRun)).all() == []
    assert db_session.scalars(select(ExecutionSession)).all() == []


def test_creation_requires_enabled_environment_and_available_credentials(db_session, execution_fixture):
    service, _, command = execution_fixture
    service.credential_available = lambda ref: False
    with pytest.raises(ValueError):
        service.create_execution(command)
    assert not db_session.scalars(select(TestRun)).all()
    service.credential_available = lambda ref: True
    db_session.get(EnvironmentProfile, command.environment_id).enabled = False
    db_session.commit()
    with pytest.raises(ValueError):
        service.create_execution(command)


def test_events_are_idempotent_and_payload_conflicts_rejected(execution_fixture):
    service, repo, command = execution_fixture
    execution = service.create_execution(command)
    one = repo.append_event(execution.id, 'TEST', {'value': 1}, 'step:1')
    two = repo.append_event(execution.id, 'TEST', {'value': 1}, 'step:1')
    assert one.id == two.id
    with pytest.raises(ValueError):
        repo.append_event(execution.id, 'TEST', {'value': 2}, 'step:1')
    assert len(repo.events(execution.id)) == 2


def test_creation_rollback_is_atomic(db_session, execution_fixture, monkeypatch):
    service, repo, command = execution_fixture
    monkeypatch.setattr(repo, 'append_event', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('fixture')))
    with pytest.raises(RuntimeError):
        service.create_execution(command)
    assert db_session.scalars(select(TestRun)).all() == []
    assert db_session.scalars(select(RunResult)).all() == []
    assert db_session.scalars(select(ExecutionEvent)).all() == []


def test_same_device_cannot_have_two_active_skill_executions(db_session, execution_fixture):
    service, repo, command = execution_fixture
    first = service.create_execution(command)
    with pytest.raises(ValueError):
        service.create_execution(command)
    assert [item.id for item in db_session.scalars(select(ExecutionSession))] == [first.id]
