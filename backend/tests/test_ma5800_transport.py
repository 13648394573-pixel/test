import base64

import pytest

from app.local_runner.ma5800.transport import (
    CommandTimeoutError,
    HostKeyFingerprintMismatchError,
    MissingHostKeyApprovalRequired,
    PinnedHostKeyPolicy,
    SafeMA5800Command,
    MA5800Transport,
    MA5800SSHConnector,
)


class FakeChannel:
    def __init__(self, chunks: list[str]):
        self.chunks = [item.encode("utf-8") for item in chunks]
        self.sent: list[str] = []

    def send(self, value: str) -> None:
        self.sent.append(value)

    def recv_ready(self) -> bool:
        return bool(self.chunks)

    def recv(self, _size: int) -> bytes:
        return self.chunks.pop(0)


class FakeKey:
    def __init__(self, raw: bytes):
        self.raw = raw

    def asbytes(self) -> bytes:
        return self.raw


class FakeParamikoTransport:
    def __init__(self, address):
        self.address = address
        self.closed = False

    def start_client(self, timeout):
        self.timeout = timeout

    def get_remote_server_key(self):
        return FakeKey(b"lab-key")

    def close(self):
        self.closed = True


def test_transport_handles_more_and_cr_prompts() -> None:
    channel = FakeChannel(
        [
            "display ont autofind all\r\n---- More ----",
            "\x1b[14D              \x1b[14D{ <cr>|desc<K> }:",
            "\r\nThe number of GPON autofind ONT is 1\r\nMA5800-X7#",
        ]
    )
    transport = MA5800Transport(channel, timeout_seconds=1, sleeper=lambda _n: None)

    transcript = transport.run(SafeMA5800Command("display_autofind", ()))

    assert channel.sent == ["display ont autofind all\n", " ", "\n"]
    assert transcript.prompt == "MA5800-X7#"
    assert "---- More" not in transcript.normalized_output


def test_transport_times_out_when_prompt_never_returns() -> None:
    channel = FakeChannel(["partial output"])
    times = iter([0.0, 0.2, 1.2])
    transport = MA5800Transport(
        channel,
        timeout_seconds=1,
        monotonic=lambda: next(times),
        sleeper=lambda _n: None,
    )
    with pytest.raises(CommandTimeoutError):
        transport.run(SafeMA5800Command("display_autofind", ()))


def test_formal_host_key_requires_pinned_fingerprint_or_explicit_approval() -> None:
    with pytest.raises(MissingHostKeyApprovalRequired):
        PinnedHostKeyPolicy(expected_fingerprint=None, formal_mode=True)


def test_host_key_policy_rejects_mismatched_fingerprint() -> None:
    expected = "SHA256:" + base64.b64encode(b"not-the-key").decode().rstrip("=")
    policy = PinnedHostKeyPolicy(expected_fingerprint=expected, formal_mode=True)
    with pytest.raises(HostKeyFingerprintMismatchError):
        policy.missing_host_key(None, "olt.lab", FakeKey(b"actual-key"))


def test_safe_command_rejects_unknown_action_code() -> None:
    with pytest.raises(ValueError, match="allow-listed"):
        SafeMA5800Command("raw_cli", ("display current-configuration",)).render()


def test_interface_context_accepts_only_numeric_frame_and_slot() -> None:
    assert SafeMA5800Command("enter_gpon_interface", (0, 2)).render() == (
        "interface gpon 0/2"
    )
    with pytest.raises(ValueError, match="numeric"):
        SafeMA5800Command("enter_gpon_interface", ("0", "2;save")).render()


def test_synchronize_drains_banner_without_sending_input() -> None:
    channel = FakeChannel(["Welcome\r\nMA5800-X7>"])
    transport = MA5800Transport(channel, timeout_seconds=1, sleeper=lambda _n: None)

    assert transport.synchronize() == "MA5800-X7>"
    assert channel.sent == []


def test_preview_host_key_rejects_public_ip_and_closes_transport() -> None:
    created = []

    def factory(address):
        transport = FakeParamikoTransport(address)
        created.append(transport)
        return transport

    connector = MA5800SSHConnector(transport_factory=factory)
    fingerprint = connector.preview_host_key("192.168.87.204", 22)

    assert fingerprint.startswith("SHA256:")
    assert created[0].address == ("192.168.87.204", 22)
    assert created[0].closed is True
    with pytest.raises(ValueError, match="private"):
        connector.preview_host_key("8.8.8.8", 22)
