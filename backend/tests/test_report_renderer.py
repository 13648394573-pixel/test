import pytest

from app.reports.renderer import render_report_html


def base_snapshot() -> dict:
    return {
        "snapshot_version": 1,
        "report_no": "RPT-000001",
        "report_version": 1,
        "report_title": "Acceptance Report",
        "generated_at": "2026-08-08T02:57:27",
        "project": {"name": "V1 Beta", "version": "rc1", "description": None},
        "run": {"id": "run-1", "status": "COMPLETED"},
        "device_snapshot": {
            "vendor": "XPON",
            "model": "UN-769XR",
            "serial_number": "SN-1",
        },
        "environment_snapshot": {
            "snapshot_version": 1,
            "profile_snapshot": {"profile_name": "Lab MA5800-X7"},
            "parameters_snapshot": [
                {
                    "section": "OLT",
                    "param_key": "fsp",
                    "param_value": "0/2/10",
                }
            ],
        },
        "summary": {"total": 1, "pass": 1, "fail": 0, "blocked": 0, "defects": 0},
        "results": [
            {
                "id": "result-1",
                "case_snapshot": {
                    "case_code": "CASE-1",
                    "title": "PON online",
                    "priority": "P0",
                    "category": "PON",
                },
                "result": "PASS",
                "actual_result": "O5 reached",
                "blocked_reason": None,
                "executed_at": "2026-08-08T02:57:27",
                "locked_at": "2026-08-08T02:57:27",
                "evidences": [
                    {
                        "original_name": "ont_online.txt",
                        "category": "LOG",
                        "sha256": "a" * 64,
                    }
                ],
            }
        ],
        "defects": [],
    }


def test_formal_mode_renders_signoff_and_document_info() -> None:
    html = render_report_html(base_snapshot(), mode="formal")
    assert "正式验收报告" in html
    assert "测试执行人" in html
    assert "审核人" in html
    assert "批准人" in html
    assert "RPT-000001" in html


def test_internal_mode_renders_run_id_and_technical_detail() -> None:
    html = render_report_html(base_snapshot(), mode="internal")
    assert "内部存档报告" in html
    assert "run-1" in html
    assert "locked" in html.lower() or "锁定" in html


def test_unknown_mode_is_rejected() -> None:
    with pytest.raises(ValueError):
        render_report_html(base_snapshot(), mode="public")
