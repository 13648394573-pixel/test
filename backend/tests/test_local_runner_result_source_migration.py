from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import create_database_engine
from app.local_runner.runtime import LocalRuntimeFactory
from app.main import create_app
from app.models.execution_session import ExecutionSession
from app.models.test_execution import RunResult, TestRun
from local_runner_binding_fixtures import enrolled_resolver, valid_config
from app.local_runner.configuration import RunnerConfig
from test_skill_execution_repository import execution_fixture  # noqa: F401


def migration_config(path):
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / 'alembic.ini'))
    config.set_main_option('sqlalchemy.url', f'sqlite:///{path.as_posix()}')
    return config


@pytest.fixture
def db_session(tmp_path):
    path = tmp_path / 'migrated.db'
    command.upgrade(migration_config(path), 'head')
    engine = create_database_engine(f'sqlite:///{path.as_posix()}')
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def test_api_creates_local_runner_session_on_real_migrated_database(execution_fixture, tmp_path):
    _, repo, cmd = execution_fixture
    cmd.parameters.update(olt_access_ref='lab.olt.access', onu_web_access_ref='lab.onu.access',
                          pppoe_access_ref='lab.ppp.access')
    settings = Settings(_env_file=None, database_url=str(repo.session.get_bind().url),
        evidence_root=str(tmp_path / 'evidence'), local_runner_evidence_root=str(tmp_path / 'runner'),
        log_file=str(tmp_path / 'app.log'))
    resolver = enrolled_resolver()
    runtime = LocalRuntimeFactory(RunnerConfig.model_validate(valid_config()), resolver)
    app = create_app(settings, credential_resolver=resolver, skill_execution_runtime=runtime)
    with TestClient(app, base_url='http://127.0.0.1') as client:
        response = client.post('/api/skill-executions', json=dict(project_id=cmd.project_id,
            device_id=cmd.device_id, environment_id=cmd.environment_id,
            skill_id=cmd.skill_id, parameters=cmd.parameters))
        assert response.status_code == 201, response.text
        view = response.json()
        assert view['status'] == 'CREATED'
        assert view['integrity_status'] == 'DRAFT'
        assert [e['type'] for e in view['events']] == ['CREATED']
        assert client.get('/api/skill-executions/' + view['session_id']).status_code == 200
    repo.session.expire_all()
    result = repo.session.get(RunResult, view['run_result_id'])
    assert result.result_source == 'LOCAL_RUNNER'
    assert result.execution_session_id == view['session_id']
    assert repo.session.get(ExecutionSession, view['session_id']).test_run_id == view['test_run_id']
    assert repo.session.get(TestRun, view['test_run_id']).source == 'LOCAL_RUNNER'
    assert repo.session.execute(text('PRAGMA foreign_key_check')).all() == []


def seed_legacy(engine):
    with engine.begin() as db:
        db.execute(text("INSERT INTO test_projects (id,project_code,name,version,status) "
                        "VALUES ('p','PRJ-LEGACY','Legacy','V1','DRAFT')"))
        db.execute(text("INSERT INTO test_runs (id,run_no,project_id,device_source_id,device_snapshot,status) "
                        "VALUES ('r','RUN-LEGACY','p','device','{\"model\":\"keep\"}','COMPLETED')"))
        for source in ('MANUAL', 'RULE_ENGINE'):
            db.execute(text("INSERT INTO run_results (id,run_id,case_source_id,case_snapshot,result_source,"
                "result,integrity_status,actual_result) VALUES (:id,'r',:id,'{\"title\":\"keep\"}',"
                ":source,'PASS','LOCKED','unchanged')"), dict(id=source, source=source))
        db.execute(text("INSERT INTO evidences (id,run_result_id,category,original_name,storage_path,"
            "media_type,file_size,sha256) VALUES ('e','MANUAL','LOG','keep.txt','keep.txt','text/plain',1,:sha)"),
            dict(sha='a' * 64))
        db.execute(text("INSERT INTO evidence_run_result_links (evidence_id,run_result_id) "
                        "VALUES ('e','MANUAL')"))


def legacy_rows(engine):
    with engine.connect() as db:
        return {table: db.execute(text(f'SELECT * FROM {table} ORDER BY 1,2')).all()
                for table in ('test_projects','test_runs','run_results','evidences','evidence_run_result_links')}


def test_upgrade_preserves_locked_legacy_results_snapshots_and_evidence(tmp_path):
    path = tmp_path / 'legacy.db'
    config = migration_config(path)
    command.upgrade(config, '20260918_0021')
    engine = create_database_engine(f'sqlite:///{path.as_posix()}')
    try:
        seed_legacy(engine)
        before = legacy_rows(engine)
        command.upgrade(config, 'head')
        assert legacy_rows(engine) == before
        with engine.begin() as db:
            db.execute(text("INSERT INTO run_results (id,run_id,case_source_id,case_snapshot,result_source) "
                            "VALUES ('local','r','local','{}','LOCAL_RUNNER')"))
            assert db.execute(text('PRAGMA foreign_key_check')).all() == []
        with pytest.raises(IntegrityError):
            with engine.begin() as db:
                db.execute(text("INSERT INTO run_results (id,run_id,case_source_id,case_snapshot,result_source) "
                                "VALUES ('invalid','r','invalid','{}','UNKNOWN')"))
        with pytest.raises(RuntimeError, match='LOCAL_RUNNER'):
            command.downgrade(config, '20260918_0021')
        with engine.connect() as db:
            assert db.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == '20261012_0022'
            assert db.execute(text("SELECT result_source FROM run_results WHERE id='local'")).scalar_one() == 'LOCAL_RUNNER'
    finally:
        engine.dispose()


def test_downgrade_without_runner_results_preserves_legacy_and_rejects_runner(tmp_path):
    path = tmp_path / 'downgrade.db'
    config = migration_config(path)
    command.upgrade(config, '20260918_0021')
    engine = create_database_engine(f'sqlite:///{path.as_posix()}')
    try:
        seed_legacy(engine)
        before = legacy_rows(engine)
        command.upgrade(config, 'head')
        command.downgrade(config, '20260918_0021')
        assert legacy_rows(engine) == before
        with pytest.raises(IntegrityError):
            with engine.begin() as db:
                db.execute(text("INSERT INTO run_results (id,run_id,case_source_id,case_snapshot,result_source) "
                                "VALUES ('local','r','local','{}','LOCAL_RUNNER')"))
    finally:
        engine.dispose()
