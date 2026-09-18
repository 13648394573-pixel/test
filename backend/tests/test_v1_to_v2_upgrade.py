from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.db.session import create_database_engine


BACKEND_ROOT = Path(__file__).resolve().parents[1]
V1_TABLES = (
    "devices",
    "test_cases",
    "case_steps",
    "test_projects",
    "project_case_selections",
    "test_runs",
    "run_results",
    "evidences",
    "defects",
    "regressions",
    "reports",
    "archives",
)


def migration_config(database_path: Path) -> Config:
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")
    return config


def table_counts(connection) -> dict[str, int]:
    return {
        table: connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        for table in V1_TABLES
    }


def seed_v1_0007(connection) -> None:
    connection.execute(text("INSERT INTO devices (id, device_type, vendor, model, serial_number, hardware_version, software_version) VALUES ('device-1','ONU','UNPON','U-GPON','SN-0001','V1','1.0.0')"))
    connection.execute(text("INSERT INTO test_cases (id, case_code, title, device_type, category, priority, enabled) VALUES ('case-1','ONU-VLAN-001','VLAN binding','ONU','VLAN','P1',1)"))
    connection.execute(text("INSERT INTO case_steps (id, test_case_id, step_number, action, expected_result) VALUES ('step-1','case-1',1,'Configure VLAN 100','Traffic passes')"))
    connection.execute(text("INSERT INTO test_projects (id, name, version, description) VALUES ('project-1','Overseas acceptance','V1','Customer A')"))
    connection.execute(text("INSERT INTO project_case_selections (project_id, case_source_id) VALUES ('project-1','case-1')"))
    connection.execute(text("INSERT INTO test_runs (id, project_id, device_source_id, device_snapshot, snapshot_version, status, started_at, finished_at) VALUES ('run-1','project-1','device-1','{\"model\":\"U-GPON\"}',1,'COMPLETED','2026-07-30 09:00:00','2026-07-30 09:30:00')"))
    connection.execute(text("INSERT INTO run_results (id, run_id, case_source_id, case_snapshot, snapshot_version, result, executed_at, integrity_status, actual_result, locked_at) VALUES ('result-1','run-1','case-1','{\"case_code\":\"ONU-VLAN-001\"}',1,'FAIL','2026-07-30 09:20:00','LOCKED','VLAN mismatch','2026-07-30 09:21:00')"))
    connection.execute(text("INSERT INTO defects (id, defect_code, source_run_result_id, title, description, reproduction_steps, severity, status) VALUES ('defect-1','DEF-0001','result-1','VLAN mismatch','Observed VLAN 200','Run case','S2','RESOLVED')"))
    connection.execute(text("INSERT INTO regressions (id, defect_id, verification_run_result_id, result, notes, executed_at) VALUES ('regression-1','defect-1','result-1','PASS','Verified','2026-07-30 10:00:00')"))
    connection.execute(text("INSERT INTO evidences (id, run_result_id, defect_id, category, original_name, storage_path, media_type, file_size, sha256, description) VALUES ('evidence-1','result-1',NULL,'LOG','vlan.log','run-results/vlan.log','text/plain',8,:sha,'OLT output')"), {"sha": "a" * 64})
    connection.execute(text("INSERT INTO reports (id, report_no, project_id, test_run_id, report_version, title, snapshot_version, report_snapshot, html_storage_path, html_sha256, html_file_size, generated_at) VALUES ('report-1','RPT-0001','project-1','run-1',1,'Acceptance',1,'{\"result\":\"FAIL\"}','reports/rpt.html',:sha,128,'2026-07-30 11:00:00')"), {"sha": "b" * 64})
    connection.execute(text("INSERT INTO archives (id, archive_no, report_id, project_id, manifest_version, manifest_snapshot, archive_storage_path, archive_sha256, archive_file_size, archived_at) VALUES ('archive-1','ARC-0001','report-1','project-1',1,'{\"report\":\"RPT-0001\"}','archives/arc.zip',:sha,256,'2026-07-30 12:00:00')"), {"sha": "c" * 64})


def assert_database_integrity(connection) -> None:
    assert connection.execute(text("PRAGMA quick_check")).scalar_one() == "ok"
    assert connection.execute(text("PRAGMA foreign_key_check")).all() == []


def test_upgrade_from_v1_0007_preserves_complete_closed_loop(tmp_path) -> None:
    database_path = tmp_path / "v1-0007.db"
    config = migration_config(database_path)
    command.upgrade(config, "20260730_0007")
    engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.begin() as connection:
        seed_v1_0007(connection)
        before_counts = table_counts(connection)
        before = connection.execute(
            text(
                "SELECT rr.result, rr.integrity_status, e.sha256, r.html_sha256, "
                "a.archive_sha256 FROM run_results rr "
                "JOIN evidences e ON e.run_result_id=rr.id "
                "JOIN test_runs tr ON tr.id=rr.run_id "
                "JOIN reports r ON r.test_run_id=tr.id "
                "JOIN archives a ON a.report_id=r.id WHERE rr.id='result-1'"
            )
        ).one()
        assert_database_integrity(connection)
    engine.dispose()

    command.upgrade(config, "head")

    upgraded = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    with upgraded.connect() as connection:
        assert table_counts(connection) == before_counts
        after = connection.execute(
            text(
                "SELECT rr.result, rr.integrity_status, e.sha256, r.html_sha256, "
                "a.archive_sha256 FROM run_results rr "
                "JOIN evidences e ON e.run_result_id=rr.id "
                "JOIN test_runs tr ON tr.id=rr.run_id "
                "JOIN reports r ON r.test_run_id=tr.id "
                "JOIN archives a ON a.report_id=r.id WHERE rr.id='result-1'"
            )
        ).one()
        assert after == before
        legacy_run = connection.execute(text("SELECT run_no, execution_schema_version, source, template_snapshot, standard_snapshot FROM test_runs WHERE id='run-1'")).one()
        legacy_result = connection.execute(text("SELECT result_source, skill_snapshot, functional_verdict, recovery_status FROM run_results WHERE id='result-1'")).one()
        assert legacy_run == ("RUN-000001", 1, "MANUAL", None, None)
        assert legacy_result == ("MANUAL", None, None, None)
        assert connection.execute(text("SELECT COUNT(*) FROM test_skills")).scalar_one() == 0
        assert connection.execute(text("SELECT COUNT(*) FROM test_standards")).scalar_one() == 0
        assert_database_integrity(connection)


def test_upgrade_from_current_v1_0010_preserves_shared_evidence_link(tmp_path) -> None:
    database_path = tmp_path / "v1-0010.db"
    config = migration_config(database_path)
    command.upgrade(config, "20260811_0010")
    engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO test_projects (id,name,version) VALUES ('project-1','Current V1','V1')"))
        connection.execute(text("INSERT INTO test_runs (id,run_no,project_id,device_source_id,device_snapshot,snapshot_version,status) VALUES ('run-1','RUN-000099','project-1','device-1','{}',1,'COMPLETED')"))
        connection.execute(text("INSERT INTO run_results (id,run_id,case_source_id,case_snapshot,snapshot_version,result,integrity_status) VALUES ('result-1','run-1','case-1','{}',1,'PASS','LOCKED')"))
        connection.execute(text("INSERT INTO evidences (id,run_result_id,category,original_name,storage_path,media_type,file_size,sha256) VALUES ('evidence-1','result-1','SCREENSHOT','pass.png','run-results/pass.png','image/png',16,:sha)"), {"sha": "d" * 64})
        connection.execute(text("INSERT INTO evidence_run_result_links (evidence_id,run_result_id) VALUES ('evidence-1','result-1')"))
        assert connection.execute(text("SELECT COUNT(*) FROM evidence_run_result_links")).scalar_one() == 1
    engine.dispose()

    command.upgrade(config, "head")

    upgraded = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    with upgraded.connect() as connection:
        assert connection.execute(text("SELECT run_no, execution_schema_version, source FROM test_runs")).one() == ("RUN-000099", 1, "MANUAL")
        assert connection.execute(text("SELECT evidence_id, run_result_id FROM evidence_run_result_links")).one() == ("evidence-1", "result-1")
        assert connection.execute(text("SELECT sha256 FROM evidences")).scalar_one() == "d" * 64
        assert_database_integrity(connection)
