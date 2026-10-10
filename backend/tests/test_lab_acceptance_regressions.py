import json
from types import SimpleNamespace

import pytest

from app.local_runner.pc_probe import PCProbe
from app.local_runner.evidence import GeneratedEvidenceWriter
from app.local_runner.ma5800.parsers import parse_command_result


def test_windows_interface_addresses_are_bound_to_their_real_alias(monkeypatch):
    from app.local_runner import pc_probe
    rows = [
        {"InterfaceAlias": "\u4ee5\u592a\u7f51 4", "IPAddress": "192.168.1.10", "IsUp": True},
        {"InterfaceAlias": "Other", "IPAddress": "192.168.87.13", "IsUp": False},
    ]
    monkeypatch.setattr(pc_probe.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=json.dumps(rows), returncode=0))
    found = PCProbe._local_interfaces()
    assert [(x.interface_name, x.address, x.is_up) for x in found] == [
        ("\u4ee5\u592a\u7f51 4", "192.168.1.10", True),
        ("Other", "192.168.87.13", False),
    ]


def test_failed_interface_discovery_does_not_invent_addresses(monkeypatch):
    from app.local_runner import pc_probe
    monkeypatch.setattr(pc_probe.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout="", returncode=1))
    assert PCProbe._local_interfaces() == ()


def test_olt_table_serial_is_redacted_before_text_and_png(tmp_path, monkeypatch):
    serial = "AABBCCDDEEFF0011"
    writer = GeneratedEvidenceWriter(tmp_path)
    original_render = writer._render_png
    def checked_render(path, rendered):
        assert serial not in rendered
        original_render(path, rendered)
    monkeypatch.setattr(writer, "_render_png", checked_render)
    artifacts = writer.write_text_and_png("olt/table", title="ONT", text=f"0/ 2/9 12 {serial} active online normal match no")
    text = (tmp_path / artifacts[0].storage_path).read_text(encoding="utf-8")
    assert serial not in text
    assert "online normal match" in text


def test_unknown_cli_command_is_not_success():
    result = parse_command_result("% Unknown command, the error locates at '^'\nMA5800-X7(config-if-gpon-0/2)#")
    assert result.success is False


def test_unsupported_paging_optimization_does_not_block_read_queries():
    from test_lab_compatibility_olt import FakeConnector, FakeTransport
    from app.lab_compatibility.olt_probe import MA5800ReadOnlyProbe, OLTProbeRequest
    from app.local_runner.credentials import SecretValue
    from app.local_runner.ma5800.transport import CommandTranscript
    class UnsupportedPaging(FakeTransport):
        def run(self, command):
            if command.action_code == "disable_paging":
                text = "% Unknown command, the error locates at '^'\nMA5800-X7#"
                return CommandTranscript(command.action_code, text, text, "MA5800-X7#", "hash")
            return super().run(command)
    probe = MA5800ReadOnlyProbe(connector=FakeConnector(), transport_factory=lambda _: UnsupportedPaging())
    result = probe.run(OLTProbeRequest("10.0.0.2",22,"SHA256:approved",None,None,None,None,None),SecretValue("operator"),SecretValue("secret"))
    assert any(x.fact_key == "olt.autofind.items" for x in result.observations)


@pytest.mark.parametrize("target_id,found", [(12, True), (1, False)])
def test_olt_registration_is_detected_by_exact_target_without_serial(target_id, found):
    from test_lab_compatibility_olt import FakeConnector, FakeTransport
    from app.lab_compatibility.olt_probe import MA5800ReadOnlyProbe, OLTProbeRequest
    from app.local_runner.credentials import SecretValue
    from app.local_runner.ma5800.transport import CommandTranscript
    class TableTransport(FakeTransport):
        def run(self, command):
            if command.action_code == "display_ont_port":
                self.commands.append(command.action_code)
                text = "0/ 2/9 12 AABBCCDDEEFF0011 active online normal match no\nMA5800-X7(config-if-gpon-0/2)#"
                return CommandTranscript(command.action_code, text, text, "MA5800-X7(config-if-gpon-0/2)#", "hash")
            return super().run(command)
    transport = TableTransport()
    probe = MA5800ReadOnlyProbe(connector=FakeConnector(), transport_factory=lambda _: transport)
    result = probe.run(OLTProbeRequest("10.0.0.2", 22, "SHA256:approved", None, 0, 2, 9, target_id), SecretValue("operator"), SecretValue("secret"))
    assert result.current_registration_found is found
    assert transport.commands.index("leave_gpon_interface") < transport.commands.index("display_service_ports")
    if found:
        registration = next(x for x in result.observations if x.fact_key == "olt.registration")
        assert registration.value["run_state"] == "online"
