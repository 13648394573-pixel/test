from pathlib import Path

import pytest

from app.lab_compatibility.olt_probe import (
    MA5800ReadOnlyProbe,
    OLTProbeBlocked,
    OLTProbeRequest,
    ReadOnlyCommandViolation,
    ReadOnlyMA5800Executor,
)
from app.local_runner.credentials import SecretValue
from app.local_runner.ma5800.transport import CommandTranscript, SafeMA5800Command


FIXTURES = Path(__file__).parent / "fixtures" / "ma5800"


class RecordingExecutor:
    def __init__(self):
        self.commands = []

    def run(self, command):
        self.commands.append(command.action_code)
        return CommandTranscript(command.action_code, "", "", "MA5800-X7#", "hash")


class FakeTransport(RecordingExecutor):
    def synchronize(self):
        return "MA5800-X7>"

    def run(self, command):
        self.commands.append(command.action_code)
        fixture = {
            "display_autofind": "autofind.txt",
            "display_ont_by_sn": "ont_online.txt",
            "display_wan_info": "wan_ipoe.txt",
        }.get(command.action_code)
        if fixture:
            output = (FIXTURES / fixture).read_text(encoding="utf-8")
        elif command.action_code == "display_service_ports":
            output = "21 1000 0/2/10 36 1 1000\nMA5800-X7(config)#"
        else:
            output = f"{command.text}\nMA5800-X7#"
        return CommandTranscript(command.action_code, output, output, "MA5800-X7#", "hash")


class NoRegistrationTransport(FakeTransport):
    def run(self, command):
        if command.action_code == "display_ont_by_sn":
            self.commands.append(command.action_code)
            output = "Failure: The ONT does not exist\nMA5800-X7#"
            return CommandTranscript(command.action_code, output, output, "MA5800-X7#", "hash")
        return super().run(command)


class UnsupportedRegistrationTransport(FakeTransport):
    def run(self, command):
        if command.action_code == "display_ont_by_sn":
            self.commands.append(command.action_code)
            output = "Failure: Unknown device response\nMA5800-X7#"
            return CommandTranscript(command.action_code, output, output, "MA5800-X7#", "hash")
        return super().run(command)


class FakeClient:
    def __init__(self):
        self.channel = object()
        self.closed = False

    def invoke_shell(self):
        return self.channel

    def close(self):
        self.closed = True


class FakeConnector:
    def __init__(self):
        self.client = FakeClient()
        self.calls = []

    def connect(self, **kwargs):
        self.calls.append(kwargs)
        return self.client


@pytest.mark.parametrize(
    "action_code",
    [
        "register_ont",
        "delete_ont",
        "provision_ipoe",
        "provision_pppoe",
        "remove_service_port",
        "raw_cli",
    ],
)
def test_read_only_executor_rejects_mutation_before_delegate(action_code) -> None:
    delegate = RecordingExecutor()
    executor = ReadOnlyMA5800Executor(delegate)

    with pytest.raises(ReadOnlyCommandViolation):
        executor.run(SafeMA5800Command(action_code, ()))

    assert delegate.commands == []


def test_probe_runs_only_expected_queries_and_closes_client() -> None:
    connector = FakeConnector()
    transport = FakeTransport()
    probe = MA5800ReadOnlyProbe(
        connector=connector,
        transport_factory=lambda _channel: transport,
    )
    request = OLTProbeRequest(
        host="192.168.87.204",
        port=22,
        expected_fingerprint="SHA256:approved",
        onu_serial_number="48575443DD91BBBB",
        frame=0,
        slot=2,
        pon_port=10,
        ont_id=36,
    )

    result = probe.run(request, SecretValue("operator"), SecretValue("secret"))

    assert transport.commands == [
        "enable",
        "disable_paging",
        "display_autofind",
        "display_ont_by_sn",
        "enter_config",
        "enter_gpon_interface",
        "display_ont_port",
        "display_wan_info",
        "leave_gpon_interface",
        "display_service_ports",
    ]
    assert result.current_registration_found is True
    assert result.current_wan_found is True
    assert connector.client.closed is True
    assert connector.calls[0]["password"] == "secret"


def test_probe_rejects_partial_target_before_connecting() -> None:
    connector = FakeConnector()
    probe = MA5800ReadOnlyProbe(connector=connector)
    request = OLTProbeRequest(
        host="192.168.87.204",
        port=22,
        expected_fingerprint="SHA256:approved",
        onu_serial_number=None,
        frame=None,
        slot=2,
        pon_port=None,
        ont_id=None,
    )

    with pytest.raises(ValueError, match="all be provided"):
        probe.run(request, SecretValue("operator"), SecretValue("secret"))

    assert connector.calls == []


def test_probe_treats_explicit_missing_registration_as_observation() -> None:
    connector = FakeConnector()
    transport = NoRegistrationTransport()
    probe = MA5800ReadOnlyProbe(
        connector=connector,
        transport_factory=lambda _channel: transport,
    )
    request = OLTProbeRequest(
        host="192.168.87.204",
        port=22,
        expected_fingerprint="SHA256:approved",
        onu_serial_number="48575443DD91BBBB",
        frame=None,
        slot=None,
        pon_port=None,
        ont_id=None,
    )

    result = probe.run(request, SecretValue("operator"), SecretValue("secret"))

    assert result.current_registration_found is False
    assert connector.client.closed is True


def test_probe_preserves_read_only_transcripts_when_output_is_unsupported() -> None:
    connector = FakeConnector()
    transport = UnsupportedRegistrationTransport()
    probe = MA5800ReadOnlyProbe(
        connector=connector,
        transport_factory=lambda _channel: transport,
    )
    request = OLTProbeRequest(
        host="10.0.0.2",
        port=22,
        expected_fingerprint="SHA256:approved",
        onu_serial_number="AABBCCDDEEFF0011",
        frame=None,
        slot=None,
        pon_port=None,
        ont_id=None,
    )

    with pytest.raises(OLTProbeBlocked) as captured:
        probe.run(request, SecretValue("operator"), SecretValue("secret"))

    assert [item.action_code for item in captured.value.transcripts][-1] == "display_ont_by_sn"
    assert connector.client.closed is True
