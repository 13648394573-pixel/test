from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def migration_config(database_path: Path) -> Config:
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")
    return config


def test_v1_rows_gain_only_explicit_legacy_defaults(tmp_path) -> None:
    database_path = tmp_path / "v1-populated.db"
    config = migration_config(database_path)
    command.upgrade(config, "20260811_0010")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    original_sha256 = "a" * 64
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO test_projects (id, name, version, description) "
                "VALUES ('project-1', 'Legacy release', 'V1', 'Keep me')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO test_runs "
                "(id, run_no, project_id, device_source_id, device_snapshot, "
                "snapshot_version, status) VALUES "
                "('run-1', 'RUN-000001', 'project-1', 'device-1', "
                "'{\"model\":\"ONU\"}', 1, 'COMPLETED')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO run_results "
                "(id, run_id, case_source_id, case_snapshot, snapshot_version, "
                "result, integrity_status, actual_result) VALUES "
                "('result-1', 'run-1', 'case-1', '{\"title\":\"Legacy\"}', "
                "1, 'PASS', 'LOCKED', 'Connected')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO evidences "
                "(id, run_result_id, defect_id, category, original_name, "
                "storage_path, media_type, file_size, sha256, description) VALUES "
                "('evidence-1', 'result-1', NULL, 'LOG', 'legacy.log', "
                "'run-results/legacy.log', 'text/plain', 7, :sha256, 'Keep evidence')"
            ),
            {"sha256": original_sha256},
        )

    command.upgrade(config, "head")

    with engine.connect() as connection:
        run = connection.execute(
            text(
                "SELECT execution_schema_version, source, template_source_id, "
                "template_snapshot, execution_plan_snapshot, "
                "standard_profile_source_id, standard_snapshot "
                "FROM test_runs WHERE id='run-1'"
            )
        ).one()
        result = connection.execute(
            text(
                "SELECT result, result_source, skill_source_id, skill_snapshot, "
                "parameter_snapshot, observations, matched_rule_codes, "
                "standard_evaluations, evidence_validation "
                "FROM run_results WHERE id='result-1'"
            )
        ).one()
        evidence = connection.execute(
            text("SELECT sha256, evidence_rule_code FROM evidences WHERE id='evidence-1'")
        ).one()
        project = connection.execute(
            text("SELECT project_code, name, description FROM test_projects WHERE id='project-1'")
        ).one()

    assert run.execution_schema_version == 1
    assert run.source == "MANUAL"
    assert tuple(run)[2:] == (None, None, None, None, None)
    assert result.result == "PASS"
    assert result.result_source == "MANUAL"
    assert tuple(result)[2:] == (None, None, None, None, None, None, None)
    assert evidence == (original_sha256, None)
    assert project.project_code == "LEGACY-000001"
    assert project.name == "Legacy release"
    assert project.description == "Keep me"
    assert inspect(engine).get_columns("test_runs")
