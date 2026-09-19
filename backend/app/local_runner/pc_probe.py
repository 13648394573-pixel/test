from __future__ import annotations

from dataclasses import dataclass
import http.client
from ipaddress import ip_address
import locale
import re
import socket
import subprocess
from typing import Callable, Sequence
from urllib.parse import urlparse

from app.local_runner.contracts import ArtifactPayload
from app.local_runner.evidence import GeneratedEvidenceWriter


class ProbeValidationError(Exception):
    pass


@dataclass(frozen=True)
class InterfaceAddress:
    interface_name: str
    address: str
    is_up: bool


@dataclass(frozen=True)
class ProbeRequest:
    interface_name: str
    source_address: str
    ping_target: str
    dns_name: str | None = None
    https_url: str | None = None
    ping_count: int = 4
    ping_timeout_seconds: int = 3
    https_timeout_seconds: int = 5
    evidence_base: str | None = None


@dataclass(frozen=True)
class PingProbeResult:
    sent: int
    received: int
    loss_percent: int
    minimum_ms: int | None
    maximum_ms: int | None
    average_ms: int | None
    raw_output: str


@dataclass(frozen=True)
class ProbeObservation:
    status: str
    ping: PingProbeResult | None
    dns_success: bool | None
    dns_addresses: tuple[str, ...]
    https_status: int | None
    artifacts: tuple[ArtifactPayload, ...] = ()
    error_code: str | None = None
    instructions: str | None = None


_PACKETS_EN = re.compile(
    r"Sent\s*=\s*(\d+)\s*,\s*Received\s*=\s*(\d+)\s*,\s*Lost\s*=\s*(\d+)\s*\((\d+)%\s*loss\)",
    re.IGNORECASE,
)
_PACKETS_ZH = re.compile(
    r"已发送\s*=\s*(\d+)\s*[，,]\s*已接收\s*=\s*(\d+)\s*[，,]\s*丢失\s*=\s*(\d+)\s*\((\d+)%\s*丢失\)",
)
_TIMES_EN = re.compile(
    r"Minimum\s*=\s*(\d+)ms\s*,\s*Maximum\s*=\s*(\d+)ms\s*,\s*Average\s*=\s*(\d+)ms",
    re.IGNORECASE,
)
_TIMES_ZH = re.compile(
    r"最短\s*=\s*(\d+)ms\s*[，,]\s*最长\s*=\s*(\d+)ms\s*[，,]\s*平均\s*=\s*(\d+)ms",
)


def parse_windows_ping(value: str) -> PingProbeResult:
    packets = _PACKETS_EN.search(value) or _PACKETS_ZH.search(value)
    if packets is None:
        raise ValueError("Windows Ping summary was not found")
    times = _TIMES_EN.search(value) or _TIMES_ZH.search(value)
    return PingProbeResult(
        sent=int(packets.group(1)),
        received=int(packets.group(2)),
        loss_percent=int(packets.group(4)),
        minimum_ms=int(times.group(1)) if times else None,
        maximum_ms=int(times.group(2)) if times else None,
        average_ms=int(times.group(3)) if times else None,
        raw_output=value[:65536],
    )


class PCProbe:
    def __init__(
        self,
        *,
        subprocess_runner: Callable[..., object] = subprocess.run,
        interface_provider: Callable[[], Sequence[InterfaceAddress]] | None = None,
        dns_resolver: Callable[[str], Sequence[str]] | None = None,
        https_probe: Callable[[str, str, int], int] | None = None,
        evidence_writer: GeneratedEvidenceWriter | None = None,
    ) -> None:
        self.subprocess_runner = subprocess_runner
        self.interface_provider = interface_provider or self._local_interfaces
        self.dns_resolver = dns_resolver or self._resolve_dns
        self.https_probe = https_probe or self._probe_https
        self.evidence_writer = evidence_writer

    def run(self, request: ProbeRequest) -> ProbeObservation:
        self._validate(request)
        available = any(
            item.is_up
            and item.interface_name.casefold() == request.interface_name.casefold()
            and item.address == request.source_address
            for item in self.interface_provider()
        )
        if not available:
            return ProbeObservation(
                status="WAITING_OPERATOR",
                ping=None,
                dns_success=None,
                dns_addresses=(),
                https_status=None,
                error_code="PC_INTERFACE_UNAVAILABLE",
                instructions=(
                    f"请将测试电脑连接到 ONU，并确认网卡“{request.interface_name}”"
                    f"已启用且地址为 {request.source_address}，然后重试。"
                ),
            )

        completed = self.subprocess_runner(
            [
                "ping.exe",
                "-n",
                str(request.ping_count),
                "-w",
                str(request.ping_timeout_seconds * 1000),
                "-S",
                request.source_address,
                request.ping_target,
            ],
            shell=False,
            capture_output=True,
            text=True,
            encoding=locale.getpreferredencoding(False),
            errors="replace",
            timeout=request.ping_count * request.ping_timeout_seconds + 5,
        )
        output = f"{getattr(completed, 'stdout', '')}\n{getattr(completed, 'stderr', '')}".strip()
        try:
            ping = parse_windows_ping(output)
        except ValueError:
            return ProbeObservation(
                status="BLOCKED",
                ping=None,
                dns_success=None,
                dns_addresses=(),
                https_status=None,
                error_code="PC_PING_OUTPUT_UNRECOGNIZED",
                instructions="请确认 Windows Ping 可用后重试。",
            )

        dns_success: bool | None = None
        dns_addresses: tuple[str, ...] = ()
        if request.dns_name:
            try:
                dns_addresses = tuple(dict.fromkeys(self.dns_resolver(request.dns_name)))
                dns_success = bool(dns_addresses)
            except OSError:
                dns_success = False

        https_status: int | None = None
        if request.https_url:
            try:
                https_status = self.https_probe(
                    request.https_url,
                    request.source_address,
                    request.https_timeout_seconds,
                )
            except OSError:
                https_status = 0

        passed = (
            ping.sent > 0
            and ping.received == ping.sent
            and ping.loss_percent == 0
            and (dns_success is not False)
            and (https_status is None or 200 <= https_status < 400)
        )
        artifacts = self._write_evidence(
            request,
            output,
            dns_success,
            dns_addresses,
            https_status,
        )
        return ProbeObservation(
            status="PASS" if passed else "FAIL",
            ping=ping,
            dns_success=dns_success,
            dns_addresses=dns_addresses,
            https_status=https_status,
            artifacts=artifacts,
            error_code=None if passed else "PC_CONNECTIVITY_FAILED",
        )

    @staticmethod
    def _validate(request: ProbeRequest) -> None:
        if not re.fullmatch(r"[\w .()_-]{1,100}", request.interface_name):
            raise ProbeValidationError("Unsafe interface name")
        try:
            source = ip_address(request.source_address)
        except ValueError as exception:
            raise ProbeValidationError("Invalid source address") from exception
        if not (source.is_private or source.is_loopback or source.is_link_local):
            raise ProbeValidationError("Source address must be local")
        if not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", request.ping_target):
            raise ProbeValidationError("Unsafe Ping target")
        if not 1 <= request.ping_count <= 10:
            raise ProbeValidationError("Ping count is out of range")
        if not 1 <= request.ping_timeout_seconds <= 30:
            raise ProbeValidationError("Ping timeout is out of range")
        if request.dns_name and not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", request.dns_name):
            raise ProbeValidationError("Unsafe DNS name")
        if request.https_url:
            parsed = urlparse(request.https_url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise ProbeValidationError("HTTPS URL must not contain credentials")
        if not 1 <= request.https_timeout_seconds <= 30:
            raise ProbeValidationError("HTTPS timeout is out of range")

    def _write_evidence(
        self,
        request: ProbeRequest,
        ping_output: str,
        dns_success: bool | None,
        dns_addresses: tuple[str, ...],
        https_status: int | None,
    ) -> tuple[ArtifactPayload, ...]:
        if self.evidence_writer is None or not request.evidence_base:
            return ()
        transcript = (
            f"Interface: {request.interface_name}\n"
            f"Source: {request.source_address}\n"
            f"\n{ping_output}\n\n"
            f"DNS success: {dns_success}; addresses: {', '.join(dns_addresses)}\n"
            f"HTTPS status: {https_status}\n"
        )
        return self.evidence_writer.write_text_and_png(
            request.evidence_base,
            title="PC-side connectivity probe",
            text=transcript,
        )

    @staticmethod
    def _local_interfaces() -> Sequence[InterfaceAddress]:
        names = [name for _index, name in socket.if_nameindex()]
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(socket.gethostname(), None)
            if item[0] in {socket.AF_INET, socket.AF_INET6}
        }
        return [
            InterfaceAddress(name, address, True)
            for name in names
            for address in addresses
        ]

    @staticmethod
    def _resolve_dns(name: str) -> Sequence[str]:
        return sorted(
            {
                item[4][0]
                for item in socket.getaddrinfo(name, None)
                if item[0] in {socket.AF_INET, socket.AF_INET6}
            }
        )

    @staticmethod
    def _probe_https(url: str, source_address: str, timeout: int) -> int:
        parsed = urlparse(url)
        connection = http.client.HTTPSConnection(
            parsed.hostname,
            parsed.port or 443,
            timeout=timeout,
            source_address=(source_address, 0),
        )
        try:
            path = parsed.path or "/"
            if parsed.query:
                path = f"{path}?{parsed.query}"
            connection.request("GET", path, headers={"User-Agent": "ONU-Test-Workbench/1.0"})
            return connection.getresponse().status
        finally:
            connection.close()
