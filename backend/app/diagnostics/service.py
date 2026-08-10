import logging
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from io import BytesIO
from ipaddress import ip_address
from typing import Any, Callable

from app.diagnostics.contracts import DiagnosticContext, PingRequest
from app.diagnostics.registry import AdapterMismatchError, AdapterRegistry
from app.diagnostics.repository import DiagnosticRepository
from app.models.diagnostic import DiagnosticSession
from app.evidence.service import EvidenceService


logger = logging.getLogger(__name__)


class DiagnosticNotFoundError(Exception):
    pass


class DiagnosticResultNotFoundError(Exception):
    pass


class LockedDiagnosticResultError(Exception):
    pass


class ActiveDiagnosticConflictError(Exception):
    pass


class InvalidDiagnosticPolicyError(Exception):
    pass


class UnsupportedDiagnosticAdapterError(Exception):
    pass


_DOMAIN = re.compile(r"^(?=.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}$")


class DiagnosticService:
    def __init__(
        self,
        repository: DiagnosticRepository,
        registry: AdapterRegistry,
        *,
        clock: Callable[[], datetime] | None = None,
        evidence_service: EvidenceService | None = None,
    ) -> None:
        self.repository = repository
        self.registry = registry
        self.clock = clock or (lambda: datetime.now(UTC).replace(tzinfo=None))
        self.evidence_service = evidence_service

    def create(self, result_id: str, values: Mapping[str, Any]) -> DiagnosticSession:
        result = self.repository.get_result(result_id)
        if result is None:
            raise DiagnosticResultNotFoundError(result_id)
        if result.integrity_status != "DRAFT":
            raise LockedDiagnosticResultError(result_id)
        if self.repository.get_active_for_result(result_id) is not None:
            raise ActiveDiagnosticConflictError(result_id)
        policy = self._validate_policy(values)
        try:
            adapter = self.registry.match(result.run.device_snapshot, values.get("adapter_key"))
        except AdapterMismatchError as exception:
            raise UnsupportedDiagnosticAdapterError(str(exception)) from exception
        if adapter is None:
            raise UnsupportedDiagnosticAdapterError(result_id)
        return self.repository.create_session(
            result_id,
            adapter.key,
            adapter.version,
            str(values["wan_mode"]),
            policy,
        )

    def get(self, session_id: str) -> DiagnosticSession:
        diagnostic = self.repository.get_session(session_id)
        if diagnostic is None:
            raise DiagnosticNotFoundError(session_id)
        return diagnostic

    def list_for_result(self, result_id: str) -> list[DiagnosticSession]:
        if self.repository.get_result(result_id) is None:
            raise DiagnosticResultNotFoundError(result_id)
        return self.repository.list_for_result(result_id)

    def execute(self, session_id: str) -> DiagnosticSession:
        diagnostic = self.get(session_id)
        result = self.repository.get_result(diagnostic.run_result_id)
        if result is None:
            raise DiagnosticResultNotFoundError(diagnostic.run_result_id)
        if result.integrity_status != "DRAFT":
            raise LockedDiagnosticResultError(result.id)
        adapter = self.registry.match(result.run.device_snapshot, diagnostic.adapter_key)
        if adapter is None:
            raise UnsupportedDiagnosticAdapterError(diagnostic.adapter_key)
        self.repository.mark_running(diagnostic, self.clock())
        context = DiagnosticContext(
            result.run.device_snapshot,
            (
                result.run.environment_snapshot.profile_snapshot
                if result.run.environment_snapshot is not None
                else None
            ),
            diagnostic.wan_mode,
        )
        policy = diagnostic.policy_snapshot
        sequence = 0
        try:
            for layer, target_key in (
                ("GATEWAY", "gateway_target"),
                ("PUBLIC_IP", "public_ip_target"),
                ("DOMAIN", "domain_target"),
            ):
                layer_passed = False
                for attempt_number in range(1, int(policy["max_attempts_per_layer"]) + 1):
                    if self.repository.get_result(result.id).integrity_status != "DRAFT":
                        raise LockedDiagnosticResultError(result.id)
                    started_at = self.clock()
                    observation = adapter.ping(
                        context,
                        PingRequest(
                            layer,
                            str(policy[target_key]),
                            int(policy["packet_count"]),
                            int(policy["timeout_seconds"]),
                        ),
                    )
                    sequence += 1
                    attempt = self.repository.append_attempt(
                        diagnostic,
                        {
                            "sequence": sequence,
                            "layer": layer,
                            "target": str(policy[target_key]),
                            "attempt_number": attempt_number,
                            "status": observation.status,
                            "packets_sent": observation.packets_sent,
                            "packets_received": observation.packets_received,
                            "loss_percent": observation.loss_percent,
                            "latency_min_ms": observation.latency_min_ms,
                            "latency_avg_ms": observation.latency_avg_ms,
                            "latency_max_ms": observation.latency_max_ms,
                            "raw_output": observation.raw_output,
                            "error_code": observation.error_code,
                            "started_at": started_at,
                            "finished_at": self.clock(),
                        },
                    )
                    self._record_evidence(diagnostic, attempt, observation.raw_output)
                    if observation.status == "PASS":
                        layer_passed = True
                        break
                if not layer_passed:
                    break
            self.repository.mark_terminal(diagnostic, "COMPLETED", self.clock())
        except Exception as exception:
            error_message = self._sanitize_failure_message(str(exception))
            self.repository.mark_terminal(
                diagnostic,
                "FAILED",
                self.clock(),
                error_code=type(exception).__name__.upper(),
                error_message=error_message[:500],
            )
            try:
                self._record_failure_evidence(diagnostic, exception)
            except Exception:
                logger.exception(
                    "Failed to record diagnostic failure evidence",
                    extra={"diagnostic_id": diagnostic.id},
                )
            raise
        return self.get(diagnostic.id)

    def _record_evidence(self, diagnostic, attempt, raw_output: str) -> None:
        if self.evidence_service is None:
            return
        evidence = self.evidence_service.create_for_run_result(
            diagnostic.run_result_id,
            category="LOG",
            original_name=f"diagnostic-{attempt.layer}-{attempt.attempt_number:02d}.txt",
            media_type="text/plain; charset=utf-8",
            description=f"Diagnostic {diagnostic.id} {attempt.layer} attempt {attempt.attempt_number}",
            stream=BytesIO(raw_output.encode("utf-8")),
        )
        self.repository.link_evidence(attempt.id, evidence.id)

    def _record_failure_evidence(
        self,
        diagnostic: DiagnosticSession,
        exception: Exception,
    ) -> None:
        if self.evidence_service is None:
            return
        stage = str(getattr(exception, "stage", "EXECUTION"))
        message = self._sanitize_failure_message(str(exception))[:1000]
        content = (
            f"diagnostic_id={diagnostic.id}\n"
            f"stage={stage}\n"
            f"error_type={type(exception).__name__}\n"
            f"message={message}\n"
        )
        self.evidence_service.create_for_run_result(
            diagnostic.run_result_id,
            category="LOG",
            original_name="diagnostic-failure.txt",
            media_type="text/plain; charset=utf-8",
            description=f"Diagnostic {diagnostic.id} failure at {stage}",
            stream=BytesIO(content.encode("utf-8")),
        )

    @staticmethod
    def _sanitize_failure_message(message: str) -> str:
        sanitized = re.sub(
            r"(?i)\b(https?://)[^/@\s]+@",
            r"\1[REDACTED]@",
            message,
        )
        sanitized = re.sub(
            r"(?i)\bcookie\s*[:=]\s*[^\r\n]*",
            "Cookie=[REDACTED]",
            sanitized,
        )
        return re.sub(
            r"(?i)\b(password|access_token|token|authorization)"
            r"\s*[:=]\s*(?:bearer\s+)?[^\s]+",
            r"\1=[REDACTED]",
            sanitized,
        )

    @staticmethod
    def _validate_policy(values: Mapping[str, Any]) -> dict[str, Any]:
        wan_mode = values.get("wan_mode")
        if wan_mode not in {"IPOE", "PPPOE"}:
            raise InvalidDiagnosticPolicyError("wan_mode must be IPOE or PPPOE")
        try:
            gateway = str(ip_address(str(values["gateway_target"])))
            public_ip = str(ip_address(str(values["public_ip_target"])))
        except (KeyError, ValueError) as exception:
            raise InvalidDiagnosticPolicyError("gateway and public targets must be IP addresses") from exception
        domain = str(values.get("domain_target", "")).strip().lower()
        if not _DOMAIN.fullmatch(domain):
            raise InvalidDiagnosticPolicyError("domain_target is invalid")
        packet_count = int(values.get("packet_count", 3))
        timeout_seconds = int(values.get("timeout_seconds", 5))
        max_attempts = int(values.get("max_attempts_per_layer", 3))
        if not 1 <= packet_count <= 5 or not 1 <= timeout_seconds <= 30 or not 1 <= max_attempts <= 3:
            raise InvalidDiagnosticPolicyError("diagnostic limits are invalid")
        return {
            "gateway_target": gateway,
            "public_ip_target": public_ip,
            "domain_target": domain,
            "packet_count": packet_count,
            "timeout_seconds": timeout_seconds,
            "max_attempts_per_layer": max_attempts,
            "layers": ["GATEWAY", "PUBLIC_IP", "DOMAIN"],
        }
