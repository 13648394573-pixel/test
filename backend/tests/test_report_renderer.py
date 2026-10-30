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


def test_renders_user_template_structure() -> None:
    snapshot = base_snapshot()
    snapshot["customer_code"] = "CUST-2026-001"
    html = render_report_html(snapshot, mode="formal")
    # 模板头部信息行（中文版面）
    assert "<h1>Acceptance Report</h1>" in html
    assert "版本 rc1" in html
    assert "客户代码 CUST-2026-001" in html
    assert "生成时间：2026-08-08T02:57:27" in html
    assert "被测设备：UN-769XR / SN-1" in html
    assert "测试环境：Lab MA5800-X7" in html
    # 模板计数条
    assert "<strong>总数 1</strong>" in html
    assert "<strong>通过 1</strong>" in html
    assert "<strong>失败 0</strong>" in html
    assert "<strong>阻塞 0</strong>" in html
    assert "<strong>缺陷 0</strong>" in html
    # 模板表格列
    assert "<th>用例</th>" in html and "<th>实际结果</th>" in html
    assert "<th>阻塞原因</th>" in html
    assert "<th>编号</th>" in html and "<th>严重级</th>" in html
    assert "<h2>测试结果</h2>" in html and "<h2>缺陷</h2>" in html
    # 证据截图（用户明确要求）
    assert "ont_online.txt" in html
    # 不包含自主添加的版面
    assert "测试执行人" not in html
    assert "通过率" not in html
    assert "文档信息" not in html
    assert "已知问题" not in html


def test_modes_render_same_public_template() -> None:
    formal = render_report_html(base_snapshot(), mode="formal")
    internal = render_report_html(base_snapshot(), mode="internal")
    # 正式 / 内部公用同一版式
    assert formal == internal


def test_unknown_mode_is_rejected() -> None:
    with pytest.raises(ValueError):
        render_report_html(base_snapshot(), mode="public")
