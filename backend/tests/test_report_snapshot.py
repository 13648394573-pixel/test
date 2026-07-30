from datetime import datetime
from types import SimpleNamespace

from app.reports.renderer import render_report_html
from app.reports.snapshots import build_report_snapshot


def test_snapshot_collects_locked_results_evidence_defects_and_regressions() -> None:
    result = SimpleNamespace(
        id="result-1",
        case_source_id="case-1",
        case_snapshot={
            "case_code": "WAN-001",
            "title": "WAN <connectivity>",
            "steps": [],
        },
        snapshot_version=1,
        result="FAIL",
        integrity_status="LOCKED",
        actual_result="No address",
        blocked_reason=None,
        test_notes="Retried",
        executed_at=datetime(2026, 7, 30, 15, 0, 0),
        locked_at=datetime(2026, 7, 30, 15, 1, 0),
    )
    run = SimpleNamespace(
        id="run-1",
        project_id="project-1",
        project=SimpleNamespace(
            id="project-1",
            name="ONU Release",
            version="R1",
            description="Acceptance",
        ),
        status="COMPLETED",
        started_at=datetime(2026, 7, 30, 14, 0, 0),
        finished_at=datetime(2026, 7, 30, 15, 1, 0),
        device_source_id="device-1",
        device_snapshot={"serial_number": "ONU-001", "vendor": "Example"},
        snapshot_version=1,
        environment_snapshot=None,
        results=[result],
    )
    evidences = [
        SimpleNamespace(
            id="evidence-1",
            run_result_id="result-1",
            defect_id=None,
            category="LOG",
            original_name="wan.log",
            storage_path="run_result/result-1/wan.log",
            media_type="text/plain",
            file_size=3,
            sha256="a" * 64,
            description="WAN log",
            created_at=datetime(2026, 7, 30, 15, 2, 0),
        )
    ]
    defect = SimpleNamespace(
        id="defect-1",
        defect_code="DEF-000001",
        source_run_result_id="result-1",
        title="WAN fails",
        description="No address",
        reproduction_steps="Reconnect",
        severity="S1",
        status="RESOLVED",
        resolution_notes="Fixed",
        created_at=datetime(2026, 7, 30, 15, 3, 0),
        updated_at=datetime(2026, 7, 30, 15, 4, 0),
        resolved_at=datetime(2026, 7, 30, 15, 4, 0),
        closed_at=None,
        regressions=[
            SimpleNamespace(
                id="regression-1",
                result="PASS",
                notes="Verified",
                executed_at=datetime(2026, 7, 30, 15, 5, 0),
                created_at=datetime(2026, 7, 30, 15, 5, 0),
            )
        ],
    )

    snapshot = build_report_snapshot(
        run,
        evidences,
        [defect],
        datetime(2026, 7, 30, 16, 0, 0),
    )

    assert snapshot["summary"] == {
        "total": 1,
        "pass": 0,
        "fail": 1,
        "blocked": 0,
        "defects": 1,
    }
    assert snapshot["environment_snapshot"] is None
    assert snapshot["results"][0]["evidences"][0]["sha256"] == "a" * 64
    assert snapshot["defects"][0]["regressions"][0]["result"] == "PASS"
    html = render_report_html(snapshot)
    assert "WAN &lt;connectivity&gt;" in html
    assert "WAN <connectivity>" not in html
    assert "DEF-000001" in html
