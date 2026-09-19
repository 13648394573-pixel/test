import json

import pytest

from app.lab_compatibility.contracts import CreateCompatibilityCheck
from app.lab_compatibility.store import CompatibilityReportStore, InvalidCompatibilityCheckId


def command(**overrides):
    values = {
        "olt_host": "192.168.87.204",
        "olt_port": 22,
        "expected_host_key_fingerprint": "SHA256:approved",
        "olt_username_ref": "olt.lab.username",
        "olt_password_ref": "olt.lab.password",
        "onu_serial_number": "48575443DD91BBBB",
        "frame": 0,
        "slot": 2,
        "pon_port": 10,
        "ont_id": 36,
        "onu_web_url": "http://192.168.1.1",
        "onu_web_username_ref": "onu.lab.username",
        "onu_web_password_ref": "onu.lab.password",
        "onu_adapter_key": "neutral-v1",
        "pc_interface_name": "Ethernet",
        "pc_source_address": "192.168.1.20",
        "pc_ping_target": "192.168.1.1",
    }
    values.update(overrides)
    return CreateCompatibilityCheck(**values)


def test_store_round_trips_pending_view_and_reference_only_command(tmp_path) -> None:
    store = CompatibilityReportStore(tmp_path)

    view = store.create(command())
    loaded = store.get(view.check_id)

    assert loaded.lifecycle == "PENDING"
    assert loaded.overall_status is None
    assert len(loaded.stages) == 8
    report = json.loads(
        (tmp_path / view.check_id / "report.json").read_text(encoding="utf-8")
    )
    assert report["command"]["olt_password_ref"] == "olt.lab.password"
    assert "secret-value" not in json.dumps(report)


def test_store_rejects_non_uuid_check_id(tmp_path) -> None:
    with pytest.raises(InvalidCompatibilityCheckId):
        CompatibilityReportStore(tmp_path).get("../../outside")
