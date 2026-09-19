from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from threading import Lock

from app.lab_compatibility.contracts import (
    CompatibilityCheckView,
    CompatibilityStage,
    CreateCompatibilityCheck,
    OverallStatus,
    StageCode,
)
from app.lab_compatibility.olt_probe import MA5800ReadOnlyProbe, OLTProbeRequest
from app.lab_compatibility.store import CompatibilityReportStore
from app.local_runner.contracts import ActionContext, ActionOutcome, ArtifactPayload
from app.local_runner.credentials import CredentialResolver
from app.local_runner.onu_web.neutral import NeutralONUWebAdapter
from app.local_runner.pc_probe import PCProbe, ProbeRequest


class ActiveCompatibilityCheckExists(Exception):
    pass


class HostKeyFingerprintChanged(Exception):
    pass


class LabCompatibilityService:
    def __init__(
        self,
        store: CompatibilityReportStore,
        credential_resolver: CredentialResolver,
        olt_probe: MA5800ReadOnlyProbe,
        onu_adapter: NeutralONUWebAdapter,
        pc_probe: PCProbe,
    ) -> None:
        self.store = store
        self.credential_resolver = credential_resolver
        self.olt_probe = olt_probe
        self.onu_adapter = onu_adapter
        self.pc_probe = pc_probe
        self._guard = Lock()
        self._active_check_id: str | None = None

    def preview_host_key(self, host: str, port: int) -> str:
        return self.olt_probe.preview_host_key(host, port)

    def create(self, command: CreateCompatibilityCheck) -> CompatibilityCheckView:
        with self._guard:
            if self._active_check_id is not None:
                raise ActiveCompatibilityCheckExists(self._active_check_id)
            view = self.store.create(command)
            self._active_check_id = view.check_id
            return view

    def get(self, check_id: str) -> CompatibilityCheckView:
        return self.store.get(check_id)

    def list_evidence(self, check_id: str) -> tuple[ArtifactPayload, ...]:
        return self.store.list_evidence(check_id)

    def execute(self, check_id: str) -> CompatibilityCheckView:
        command = self.store.get_command(check_id)
        view = replace(
            self.store.get(check_id), lifecycle="RUNNING", updated_at=datetime.now(UTC)
        )
        self.store.save(view)
        try:
            view = self._set_stage(view, "LOCAL_ENV", "VERIFIED", "本地证据目录可用")
            self.store.save(view)

            actual_fingerprint = self.olt_probe.preview_host_key(
                command.olt_host, command.olt_port
            )
            if actual_fingerprint != command.expected_host_key_fingerprint:
                raise HostKeyFingerprintChanged(actual_fingerprint)

            olt_username = self.credential_resolver.resolve(command.olt_username_ref)
            olt_password = self.credential_resolver.resolve(command.olt_password_ref)
            olt_result = self.olt_probe.run(
                OLTProbeRequest(
                    command.olt_host,
                    command.olt_port,
                    command.expected_host_key_fingerprint,
                    command.onu_serial_number,
                    command.frame,
                    command.slot,
                    command.pon_port,
                    command.ont_id,
                ),
                olt_username,
                olt_password,
            )
            view = self._set_stage(view, "OLT_CONNECT", "VERIFIED", "OLT 连接和主机指纹已验证")
            olt_evidence = self._write_olt_evidence(
                check_id, olt_result.transcripts, (olt_username.reveal(), olt_password.reveal())
            )
            view = self._set_stage(
                view, "OLT_AUTOFIND", "VERIFIED", "OLT 自动发现查询可解析", olt_evidence
            )
            complete_target = all(
                value is not None
                for value in (command.frame, command.slot, command.pon_port, command.ont_id)
            )
            current_verified = complete_target and (
                olt_result.current_registration_found or olt_result.current_wan_found
            )
            view = self._set_stage(
                view,
                "OLT_CURRENT_STATE",
                "VERIFIED" if current_verified else "NEEDS_INPUT",
                "OLT 当前 ONU/WAN 状态可读取"
                if current_verified
                else "请提供完整 F/S/P 与 ONT ID，或先确认 ONU 当前已注册",
            )
            self.store.save(view)

            onu_username = self.credential_resolver.resolve(command.onu_web_username_ref)
            onu_password = self.credential_resolver.resolve(command.onu_web_password_ref)
            onu_result = self.onu_adapter.check_compatibility(
                ActionContext(
                    check_id,
                    "check_compatibility",
                    {"onu_web_url": command.onu_web_url},
                    {
                        "onu_web_username": onu_username,
                        "onu_web_password": onu_password,
                    },
                )
            )
            wan_evidence = self._write_action_evidence(
                check_id, "onu/wan", onu_result.wan_outcome
            )
            ping_evidence = self._write_action_evidence(
                check_id, "onu/ping-page", onu_result.ping_page_outcome
            )
            view = self._set_stage(
                view,
                "ONU_WEB_WAN",
                self._action_status(onu_result.wan_outcome),
                self._action_message(onu_result.wan_outcome, "ONU Web WAN 页面可读取"),
                wan_evidence,
            )
            view = self._set_stage(
                view,
                "ONU_WEB_PING_PAGE",
                self._action_status(onu_result.ping_page_outcome),
                self._action_message(onu_result.ping_page_outcome, "ONU Web Ping 控件可识别"),
                ping_evidence,
            )
            self.store.save(view)

            pc = self.pc_probe.run(
                ProbeRequest(
                    interface_name=command.pc_interface_name,
                    source_address=command.pc_source_address,
                    ping_target=command.pc_ping_target,
                    evidence_base=f"{check_id}/pc/ping",
                )
            )
            if pc.status == "PASS":
                view = self._set_stage(view, "PC_INTERFACE", "VERIFIED", "指定网卡和源地址可用")
                view = self._set_stage(view, "PC_PING", "VERIFIED", "电脑侧基础 Ping 可执行", pc.artifacts)
            elif pc.status == "WAITING_OPERATOR":
                view = self._set_stage(
                    view, "PC_INTERFACE", "NEEDS_INPUT", pc.instructions or "请连接指定网卡"
                )
            else:
                view = self._set_stage(view, "PC_INTERFACE", "VERIFIED", "指定网卡和源地址可用")
                view = self._set_stage(
                    view, "PC_PING", "BLOCKED", pc.instructions or "电脑侧 Ping 无法完成", pc.artifacts
                )
            return self._complete(view)
        except HostKeyFingerprintChanged:
            view = self._set_stage(
                view, "OLT_CONNECT", "BLOCKED", "OLT 主机指纹与已确认值不一致，请停止并核对设备"
            )
            return self._complete(view)
        except Exception as exception:
            first = next((item.code for item in view.stages if item.status == "NOT_RUN"), None)
            if first is not None:
                view = self._set_stage(view, first, "BLOCKED", self._safe_error(exception))
            return self._complete(view)
        finally:
            with self._guard:
                if self._active_check_id == check_id:
                    self._active_check_id = None

    def _complete(self, view: CompatibilityCheckView) -> CompatibilityCheckView:
        status: OverallStatus
        if any(item.status == "BLOCKED" for item in view.stages):
            status = "BLOCKED"
        elif all(item.status == "VERIFIED" for item in view.stages):
            status = "READY"
        else:
            status = "PARTIAL"
        completed = replace(
            view,
            lifecycle="COMPLETED",
            overall_status=status,
            updated_at=datetime.now(UTC),
        )
        self.store.save(completed)
        return completed

    @staticmethod
    def _set_stage(
        view: CompatibilityCheckView,
        code: StageCode,
        status,
        message: str,
        evidence: tuple[ArtifactPayload, ...] = (),
    ) -> CompatibilityCheckView:
        stages = tuple(
            CompatibilityStage(code, status, message, evidence)
            if item.code == code
            else item
            for item in view.stages
        )
        return replace(view, stages=stages, updated_at=datetime.now(UTC))

    def _write_olt_evidence(self, check_id, transcripts, secrets):
        writer = self.store.evidence_writer(check_id)
        artifacts = []
        for index, transcript in enumerate(transcripts, start=1):
            if not transcript.action_code.startswith("display_"):
                continue
            artifacts.extend(
                writer.write_text_and_png(
                    f"olt/{index:02d}-{transcript.action_code}",
                    title=transcript.action_code,
                    text=transcript.normalized_output,
                    redaction_values=secrets,
                )
            )
        return tuple(artifacts)

    def _write_action_evidence(self, check_id, prefix, outcome: ActionOutcome):
        writer = self.store.evidence_writer(check_id)
        return tuple(
            writer.register_artifact(f"{prefix}/{item.original_name}", item)
            for item in outcome.artifacts
        )

    @staticmethod
    def _action_status(outcome: ActionOutcome):
        return "VERIFIED" if outcome.status == "PASS" else "BLOCKED"

    @staticmethod
    def _action_message(outcome: ActionOutcome, passed: str) -> str:
        return passed if outcome.status == "PASS" else (outcome.detail or outcome.error_code or "页面检查受阻")

    @staticmethod
    def _safe_error(exception: Exception) -> str:
        name = type(exception).__name__
        messages = {
            "UnavailableCredentialError": "本机凭据不存在，请先录入后重试",
            "CommandTimeoutError": "OLT 查询超时，请检查网络和设备状态",
            "PermissionError": "本地证据目录不可写",
        }
        return messages.get(name, f"兼容性检查受阻：{name}")
