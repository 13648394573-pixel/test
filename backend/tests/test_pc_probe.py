from dataclasses import dataclass

import pytest

from app.local_runner.pc_probe import (
    InterfaceAddress,
    PCProbe,
    ProbeRequest,
    ProbeValidationError,
    parse_windows_ping,
)
from app.local_runner.evidence import GeneratedEvidenceWriter


ENGLISH_PING = """
Packets: Sent = 4, Received = 4, Lost = 0 (0% loss),
Approximate round trip times in milli-seconds:
    Minimum = 1ms, Maximum = 3ms, Average = 2ms
"""

CHINESE_PING = """
数据包: 已发送 = 4，已接收 = 3，丢失 = 1 (25% 丢失)，
往返行程的估计时间(以毫秒为单位):
    最短 = 2ms，最长 = 8ms，平均 = 4ms
"""


@dataclass
class Completed:
    stdout: str
    stderr: str = ""
    returncode: int = 0


class FakeSubprocess:
    def __init__(self, output=ENGLISH_PING):
        self.output = output
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append(type("Call", (), {"args": args, **kwargs})())
        return Completed(self.output)


def request(**overrides) -> ProbeRequest:
    values = {
        "interface_name": "Ethernet",
        "source_address": "192.168.1.20",
        "ping_target": "1.1.1.1",
        "dns_name": "example.com",
        "https_url": "https://example.com/health",
        "ping_count": 4,
        "ping_timeout_seconds": 2,
        "https_timeout_seconds": 3,
    }
    values.update(overrides)
    return ProbeRequest(**values)


def interfaces():
    return [InterfaceAddress("Ethernet", "192.168.1.20", True)]


def test_windows_ping_parser_supports_english_and_chinese_output() -> None:
    english = parse_windows_ping(ENGLISH_PING)
    chinese = parse_windows_ping(CHINESE_PING)
    assert (english.sent, english.received, english.loss_percent, english.average_ms) == (
        4,
        4,
        0,
        2,
    )
    assert (chinese.sent, chinese.received, chinese.loss_percent, chinese.average_ms) == (
        4,
        3,
        25,
        4,
    )


def test_probe_uses_argument_list_and_never_shell() -> None:
    fake = FakeSubprocess()
    probe = PCProbe(
        subprocess_runner=fake,
        interface_provider=interfaces,
        dns_resolver=lambda _name: ["93.184.216.34"],
        https_probe=lambda _url, _source, _timeout: 204,
    )
    outcome = probe.run(request())

    assert outcome.status == "PASS"
    assert fake.calls[0].shell is False
    assert fake.calls[0].args[:2] == ["ping.exe", "-n"]
    assert fake.calls[0].args == [
        "ping.exe",
        "-n",
        "4",
        "-w",
        "2000",
        "-S",
        "192.168.1.20",
        "1.1.1.1",
    ]


def test_probe_records_dns_and_https_failures() -> None:
    probe = PCProbe(
        subprocess_runner=FakeSubprocess(),
        interface_provider=interfaces,
        dns_resolver=lambda _name: (_ for _ in ()).throw(OSError("DNS unavailable")),
        https_probe=lambda _url, _source, _timeout: 503,
    )
    outcome = probe.run(request())
    assert outcome.status == "FAIL"
    assert outcome.dns_success is False
    assert outcome.https_status == 503


def test_missing_requested_interface_waits_for_operator_without_running_ping() -> None:
    fake = FakeSubprocess()
    probe = PCProbe(
        subprocess_runner=fake,
        interface_provider=lambda: [],
        dns_resolver=lambda _name: [],
        https_probe=lambda *_args: 200,
    )
    outcome = probe.run(request())
    assert outcome.status == "WAITING_OPERATOR"
    assert outcome.error_code == "PC_INTERFACE_UNAVAILABLE"
    assert "Ethernet" in outcome.instructions
    assert fake.calls == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"interface_name": "Ethernet; Disable-NetAdapter"},
        {"source_address": "8.8.8.8"},
        {"ping_target": "1.1.1.1 & whoami"},
        {"https_url": "http://example.com"},
    ],
)
def test_probe_rejects_unsafe_or_nonlocal_binding_inputs(overrides) -> None:
    with pytest.raises(ProbeValidationError):
        PCProbe(
            subprocess_runner=FakeSubprocess(),
            interface_provider=interfaces,
        ).run(request(**overrides))


def test_ping_packet_loss_fails_mandatory_probe() -> None:
    outcome = PCProbe(
        subprocess_runner=FakeSubprocess(CHINESE_PING),
        interface_provider=interfaces,
    ).run(request(dns_name=None, https_url=None))
    assert outcome.status == "FAIL"
    assert outcome.ping.loss_percent == 25


def test_probe_renders_text_and_png_evidence(tmp_path) -> None:
    outcome = PCProbe(
        subprocess_runner=FakeSubprocess(),
        interface_provider=interfaces,
        evidence_writer=GeneratedEvidenceWriter(tmp_path),
    ).run(
        request(
            dns_name=None,
            https_url=None,
            evidence_base="runs/run-1/session-1/pc-ipoe",
        )
    )
    assert {item.media_type for item in outcome.artifacts} == {
        "text/plain",
        "image/png",
    }
    assert all((tmp_path / item.storage_path).is_file() for item in outcome.artifacts)
