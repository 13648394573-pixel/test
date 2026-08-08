from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, Protocol


WanMode = Literal["IPOE", "PPPOE"]
DiagnosticLayer = Literal["GATEWAY", "PUBLIC_IP", "DOMAIN"]
AttemptStatus = Literal["PASS", "FAIL", "ERROR"]


@dataclass(frozen=True)
class DiagnosticContext:
    device_snapshot: Mapping[str, Any]
    environment_snapshot: Mapping[str, Any] | None
    wan_mode: WanMode


@dataclass(frozen=True)
class PingRequest:
    layer: DiagnosticLayer
    target: str
    packet_count: int
    timeout_seconds: int


@dataclass(frozen=True)
class PingObservation:
    status: AttemptStatus
    packets_sent: int
    packets_received: int
    loss_percent: Decimal
    latency_min_ms: Decimal | None
    latency_avg_ms: Decimal | None
    latency_max_ms: Decimal | None
    raw_output: str
    error_code: str | None = None


class PingAdapter(Protocol):
    key: str
    version: str

    def supports(self, device_snapshot: Mapping[str, Any]) -> bool: ...

    def ping(self, context: DiagnosticContext, request: PingRequest) -> PingObservation: ...


PingExecutor = Callable[[DiagnosticContext, PingRequest], str]
