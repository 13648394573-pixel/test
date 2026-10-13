from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Any, Callable, Mapping, Protocol

from app.local_runner.contracts import ActionContext, ActionOutcome, Observation
from app.local_runner.credentials import SecretValue
from app.local_runner.ma5800.parsers import (
    parse_autofind,
    parse_command_result,
    parse_ont_state,
    parse_service_ports,
    parse_wan_info,
)
from app.local_runner.ma5800.transport import CommandTranscript, SafeMA5800Command
from app.local_runner.registry import LocalActionRegistry


class ParameterValidationError(Exception):
    pass


class CommandExecutor(Protocol):
    def run(self, command: SafeMA5800Command) -> CommandTranscript: ...


@dataclass(frozen=True)
class MutationPreview:
    action_code: str
    target_fsp: str
    ont_id: int
    serial_number: str
    affected_service_ports: tuple[int, ...]
    summary: str

    def to_payload(self) -> dict[str, Any]:
        values = asdict(self)
        values["affected_service_ports"] = list(self.affected_service_ports)
        encoded = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
        return {**values, "preview_hash": hashlib.sha256(encoded).hexdigest()}


def _integer(value: Any, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise ParameterValidationError(f"{name} must be an integer")
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and value.isascii() and value.isdigit():
        number = int(value)
    else:
        raise ParameterValidationError(f"{name} must be an integer")
    if not minimum <= number <= maximum:
        raise ParameterValidationError(f"{name} is out of range")
    return number


def validate_gpon_port(value: Any) -> int:
    return _integer(value, "pon_port", 0, 255)


def _validated_target(parameters: Mapping[str, Any]) -> dict[str, Any]:
    serial = str(parameters.get("onu_serial_number", "")).upper()
    if not re.fullmatch(r"[0-9A-F]{16}", serial):
        raise ParameterValidationError("onu_serial_number must be 16 hexadecimal characters")
    return {
        "frame": _integer(parameters.get("frame"), "frame", 0, 15),
        "slot": _integer(parameters.get("slot"), "slot", 0, 31),
        "pon_port": validate_gpon_port(parameters.get("pon_port")),
        "ont_id": _integer(parameters.get("ont_id"), "ont_id", 0, 127),
        "serial": serial,
    }


def build_register_command(parameters: Mapping[str, Any]) -> SafeMA5800Command:
    target = _validated_target(parameters)
    line_profile = _integer(parameters.get("line_profile_id"), "line_profile_id", 0, 4095)
    service_profile = _integer(parameters.get("service_profile_id"), "service_profile_id", 0, 4095)
    return SafeMA5800Command(
        "register_ont",
        (target["pon_port"], target["ont_id"], target["serial"], line_profile, service_profile, "sn-auth"),
    )


def build_delete_command(parameters: Mapping[str, Any]) -> SafeMA5800Command:
    target = _validated_target(parameters)
    return SafeMA5800Command("delete_ont", (target["pon_port"], target["ont_id"]))


def build_ipoe_command(parameters: Mapping[str, Any]) -> SafeMA5800Command:
    target = _validated_target(parameters)
    vlan = _integer(parameters.get("ipoe_vlan"), "ipoe_vlan", 1, 4094)
    ipoe_index, _ = _wan_indexes(parameters)
    return SafeMA5800Command("provision_ipoe", (target["pon_port"], target["ont_id"], vlan, ipoe_index))


def _wan_indexes(parameters: Mapping[str, Any]) -> tuple[int, int]:
    ipoe = _integer(parameters.get("ipoe_ip_index", 1), "ipoe_ip_index", 0, 255)
    pppoe = _integer(parameters.get("pppoe_ip_index", 0), "pppoe_ip_index", 0, 255)
    if ipoe == pppoe:
        raise ParameterValidationError("IPoE and PPPoE must use distinct IP Host indexes")
    return ipoe, pppoe


def build_pppoe_command(
    parameters: Mapping[str, Any], *, username: SecretValue, password: SecretValue
) -> SafeMA5800Command:
    target = _validated_target(parameters)
    vlan = _integer(parameters.get("pppoe_vlan"), "pppoe_vlan", 1, 4094)
    _, pppoe_index = _wan_indexes(parameters)
    return SafeMA5800Command(
        "provision_pppoe",
        (target["pon_port"], target["ont_id"], username, password, vlan, pppoe_index),
    )


class MA5800Actions:
    def __init__(self, executor: CommandExecutor):
        self.executor = executor

    def preflight(self, context: ActionContext) -> ActionOutcome:
        target = _validated_target(context.parameters)
        return self._pass("olt.preflight.valid", {**target, "fsp": self._fsp(target)})

    def discover_onts(self, _context: ActionContext) -> ActionOutcome:
        transcript = self.executor.run(SafeMA5800Command("display_autofind", ()))
        items = [asdict(item) for item in parse_autofind(transcript.normalized_output)]
        if self._read_failed(transcript) or (not items and not re.search(
                r'(?i)The number of GPON autofind ONT is\s+0\b', transcript.normalized_output)):
            return ActionOutcome("BLOCKED", (), (), "OLT_READ_UNRECOGNIZED")
        return self._pass("olt.autofind.items", items, transcript)

    def snapshot_ont(self, context: ActionContext) -> ActionOutcome:
        target = _validated_target(context.parameters)
        registration_transcript = self.executor.run(
            SafeMA5800Command("display_ont_by_sn", (target["serial"],))
        )
        if re.search(r'(?i)\bONT\b.*\b(?:does not exist|not exist|not found)\b',
                     registration_transcript.normalized_output):
            return self._pass("olt.configuration_snapshot",
                              {"registration": None, "wan": [], "service_ports": []},
                              registration_transcript)
        registration = asdict(parse_ont_state(registration_transcript.normalized_output))
        if not self._same_identity(registration, target):
            return ActionOutcome("BLOCKED", (), (), "OLT_TARGET_IDENTITY_MISMATCH")
        wan_transcript = self.executor.run(
            SafeMA5800Command("display_wan_info", (target["pon_port"], target["ont_id"]))
        )
        port_transcript = self.executor.run(
            SafeMA5800Command("display_service_ports", (self._fsp(target), target["ont_id"]))
        )
        wan = [asdict(item) for item in parse_wan_info(wan_transcript.normalized_output)]
        if not self._wan_read_valid(wan_transcript, wan) or self._read_failed(port_transcript):
            return ActionOutcome("BLOCKED", (), (), "OLT_READ_UNRECOGNIZED")
        service_ports = [asdict(item) for item in parse_service_ports(port_transcript.normalized_output)]
        return self._pass(
            "olt.configuration_snapshot",
            {"registration": registration, "wan": wan, "service_ports": service_ports},
        )

    def find_free_ont_id(self, context: ActionContext) -> ActionOutcome:
        target = _validated_target(context.parameters)
        transcript = self.executor.run(
            SafeMA5800Command("display_ont_port", (target["pon_port"],))
        )
        if not self._port_read_valid(transcript, target):
            return ActionOutcome("BLOCKED", (), (), "OLT_PORT_READ_UNRECOGNIZED")
        used = {
            int(item)
            for item in re.findall(
                rf"(?m)^[ \t]*{self._port_pattern(target)}[ \t]+(\d+)[ \t]+", transcript.normalized_output
            )
        }
        free = next((item for item in range(128) if item not in used), None)
        if free is None:
            return ActionOutcome("BLOCKED", (), (), "NO_FREE_ONT_ID", "No free ONT ID")
        return self._pass("olt.free_ont_id", free, transcript)

    def delete_ont(self, context: ActionContext) -> ActionOutcome:
        return self._guarded_mutation(
            context,
            summary="Delete the existing ONU registration and affected service ports.",
            command_factory=lambda: build_delete_command(context.parameters),
        )

    def register_ont(self, context: ActionContext) -> ActionOutcome:
        return self._guarded_mutation(
            context,
            summary="Register the target ONU with the selected line and service profiles.",
            command_factory=lambda: build_register_command(context.parameters),
        )

    def provision_ipoe(self, context: ActionContext) -> ActionOutcome:
        index, _ = _wan_indexes(context.parameters)
        vlan = _integer(context.parameters.get("ipoe_vlan"), "ipoe_vlan", 1, 4094)
        return self._guarded_mutation(
            context,
            summary=f"Provision IPoE on IP Host {index}, VLAN {vlan}.",
            command_factory=lambda: build_ipoe_command(context.parameters),
        )

    def provision_pppoe(self, context: ActionContext) -> ActionOutcome:
        username = context.secrets.get("pppoe_username")
        password = context.secrets.get("pppoe_password")
        if username is None or password is None:
            return ActionOutcome("BLOCKED", (), (), "PPPOE_CREDENTIAL_UNAVAILABLE", "PPPoE credential is unavailable")
        _, index = _wan_indexes(context.parameters)
        vlan = _integer(context.parameters.get("pppoe_vlan"), "pppoe_vlan", 1, 4094)
        return self._guarded_mutation(
            context,
            summary=f"Provision PPPoE on IP Host {index}, VLAN {vlan}.",
            command_factory=lambda: build_pppoe_command(
                context.parameters, username=username, password=password
            ),
        )

    def read_wan_info(self, context: ActionContext) -> ActionOutcome:
        target = _validated_target(context.parameters)
        transcript = self.executor.run(
            SafeMA5800Command("display_wan_info", (target["pon_port"], target["ont_id"]))
        )
        items = [asdict(item) for item in parse_wan_info(transcript.normalized_output)]
        if not self._wan_read_valid(transcript, items):
            return ActionOutcome("BLOCKED", (), (), "OLT_READ_UNRECOGNIZED")
        return self._pass(
            "olt.wan.items",
            items,
            transcript,
        )

    def remove_test_services(self, context: ActionContext) -> ActionOutcome:
        service_ports = self._service_ports(context.parameters)
        if not service_ports:
            return self._pass("olt.removed_service_ports", [])
        return self._guarded_mutation(
            context,
            summary="Remove the listed test service ports before WAN isolation or recovery.",
            command_factory=lambda: SafeMA5800Command("remove_service_port", (service_ports[0],)),
        )

    def restore_snapshot(self, context: ActionContext) -> ActionOutcome:
        snapshot = context.parameters.get("configuration_snapshot")
        if not isinstance(snapshot, dict) or set(snapshot) != {"registration", "wan", "service_ports"}:
            return ActionOutcome(
                "ERROR", (), (), "RECOVERY_REQUIRED",
                "Snapshot is incomplete or contains an unsupported restore scope; perform manual recovery.",
            )
        registration = snapshot.get("registration")
        if not isinstance(registration, dict):
            return ActionOutcome("ERROR", (), (), "RECOVERY_REQUIRED", "Registration snapshot is unavailable")
        restore_parameters = {
            **context.parameters,
            "ont_id": registration.get("ont_id"),
            "onu_serial_number": registration.get("serial_number"),
            "line_profile_id": registration.get("line_profile_id"),
            "service_profile_id": registration.get("service_profile_id"),
        }
        restore_context = ActionContext(
            session_id=context.session_id,
            action_code=context.action_code,
            parameters=restore_parameters,
            secrets=context.secrets,
            workspace=context.workspace,
        )
        return self._guarded_mutation(
            restore_context,
            summary="Restore the immutable pre-test ONU registration snapshot.",
            command_factory=lambda: build_register_command(restore_parameters),
        )

    def verify_restore(self, context: ActionContext) -> ActionOutcome:
        snapshot = context.parameters.get("configuration_snapshot")
        if not isinstance(snapshot, dict) or not isinstance(snapshot.get("registration"), dict):
            return ActionOutcome("ERROR", (), (), "RECOVERY_REQUIRED", "Cannot verify an incomplete snapshot")
        target = _validated_target(context.parameters)
        transcript = self.executor.run(SafeMA5800Command("display_ont_by_sn", (target["serial"],)))
        observed = asdict(parse_ont_state(transcript.normalized_output))
        expected = snapshot["registration"]
        keys = ("fsp", "ont_id", "serial_number", "line_profile_id", "service_profile_id")
        matches = all(observed.get(key) == expected.get(key) for key in keys)
        if not matches:
            return ActionOutcome(
                "ERROR",
                (Observation("olt.restore.matches_snapshot", False, "MA5800"),),
                (),
                "RECOVERY_REQUIRED",
                "Restored ONU state does not match the immutable snapshot.",
            )
        return self._pass("olt.restore.matches_snapshot", True, transcript)

    def _guarded_mutation(
        self,
        context: ActionContext,
        *,
        summary: str,
        command_factory: Callable[[], SafeMA5800Command],
    ) -> ActionOutcome:
        target = _validated_target(context.parameters)
        preview = MutationPreview(
            action_code=context.action_code,
            target_fsp=self._fsp(target),
            ont_id=target["ont_id"],
            serial_number=target["serial"],
            affected_service_ports=tuple(self._service_ports(context.parameters)),
            summary=summary,
        ).to_payload()
        approval = context.parameters.get("mutation_approval")
        if not isinstance(approval, dict) or approval.get("approved") is not True or approval.get("preview_hash") != preview["preview_hash"]:
            return ActionOutcome(
                "WAITING_OPERATOR",
                (Observation("mutation.preview", preview, "MA5800"),),
                (),
                detail="Operator approval is required for this exact mutation preview.",
            )
        refusal = self._revalidate_mutation(context, target)
        if refusal:
            return ActionOutcome("BLOCKED", (), (), refusal)
        transcript = self.executor.run(command_factory())
        result = parse_command_result(transcript.normalized_output)
        if not result.success:
            return ActionOutcome("ERROR", (), (), result.code, result.message)
        return self._pass("olt.mutation.transcript_sha256", transcript.sha256, transcript)

    @staticmethod
    def _read_failed(transcript):
        return bool(re.search(r'(?im)^(?:Failure\s*:|Error\s*:|%\s*)',
                              transcript.normalized_output))

    @staticmethod
    def _same_identity(registration, target):
        return (registration.get("fsp") == MA5800Actions._fsp(target)
                and registration.get("ont_id") == target["ont_id"]
                and registration.get("serial_number") == target["serial"])

    @classmethod
    def _wan_read_valid(cls, transcript, items):
        if cls._read_failed(transcript):
            return False
        if items:
            return all(item["mode"] in {"IPOE", "PPPOE"}
                       and item["status"] in {"CONNECTED", "UP", "ONLINE", "DISCONNECTED", "DOWN", "OFFLINE"}
                       for item in items)
        return bool(re.search(r'(?i)The number of (?:ONT )?WAN (?:entries|configurations) is\s+0\b',
                              transcript.normalized_output))

    @classmethod
    def _port_read_valid(cls, transcript, target):
        text = transcript.normalized_output
        return not cls._read_failed(transcript) and bool(
            re.search(rf'(?im)^[ \t]*{cls._port_pattern(target)}[ \t]+\d+[ \t]+[0-9a-f]{{16}}\b', text)
            or re.search(r'(?i)The number of ONTs is\s+0\b', text))

    def _revalidate_mutation(self, context, target):
        transcript = self.executor.run(SafeMA5800Command("display_ont_by_sn", (target["serial"],)))
        absent = bool(re.search(r'(?i)\bONT\b.*\b(?:does not exist|not exist|not found)\b',
                                transcript.normalized_output))
        if context.action_code in {"register_ont", "restore_snapshot"}:
            if not absent:
                return "OLT_REGISTRATION_NOT_ABSENT"
            port = self.executor.run(SafeMA5800Command("display_ont_port", (target["pon_port"],)))
            if not self._port_read_valid(port, target):
                return "OLT_PORT_READ_UNRECOGNIZED"
            if re.search(rf'(?m)^[ \t]*{self._port_pattern(target)}[ \t]+{target["ont_id"]}[ \t]+',
                         port.normalized_output):
                return "OLT_ONT_ID_IN_USE"
            discovery = self.executor.run(SafeMA5800Command("display_autofind", ()))
            if self._read_failed(discovery) or not any(
                    item.fsp == self._fsp(target) and item.serial_number == target["serial"]
                    for item in parse_autofind(discovery.normalized_output)):
                return "OLT_AUTOFIND_IDENTITY_UNCONFIRMED"
            return None
        if absent or self._read_failed(transcript):
            return "OLT_TARGET_IDENTITY_UNCONFIRMED"
        try:
            registration = asdict(parse_ont_state(transcript.normalized_output))
        except ValueError:
            return "OLT_TARGET_IDENTITY_UNCONFIRMED"
        if not self._same_identity(registration, target):
            return "OLT_TARGET_IDENTITY_MISMATCH"
        requested = self._service_ports(context.parameters)
        if requested:
            ports = self.executor.run(SafeMA5800Command("display_service_ports", (self._fsp(target), target["ont_id"])))
            owned = {item.service_port_id for item in parse_service_ports(ports.normalized_output)
                     if item.fsp == self._fsp(target) and item.ont_id == target["ont_id"]}
            if self._read_failed(ports) or not set(requested) <= owned:
                return "OLT_SERVICE_PORT_OWNERSHIP_UNCONFIRMED"
        return None

    @staticmethod
    def _service_ports(parameters: Mapping[str, Any]) -> list[int]:
        values = parameters.get("affected_service_ports", [])
        if not isinstance(values, list):
            raise ParameterValidationError("affected_service_ports must be a list")
        return [_integer(item, "service_port", 0, 65535) for item in values]

    @staticmethod
    def _fsp(target: Mapping[str, Any]) -> str:
        return f"{target['frame']}/{target['slot']}/{target['pon_port']}"

    @classmethod
    def _port_pattern(cls, target: Mapping[str, Any]) -> str:
        return r"[ \t]*/[ \t]*".join(re.escape(part) for part in cls._fsp(target).split("/"))

    @staticmethod
    def _pass(
        fact_key: str,
        value: Any,
        transcript: CommandTranscript | None = None,
    ) -> ActionOutcome:
        observations = [Observation(fact_key, value, "MA5800")]
        if transcript is not None:
            observations.append(
                Observation("olt.transcript_sha256", transcript.sha256, "MA5800")
            )
        return ActionOutcome("PASS", tuple(observations), ())


class _BoundActionHandler:
    def __init__(self, method: Callable[[ActionContext], ActionOutcome]):
        self.method = method

    def execute(self, context: ActionContext) -> ActionOutcome:
        return self.method(context)


def register_default_ma5800_actions(
    registry: LocalActionRegistry, actions: MA5800Actions
) -> None:
    for action_code in (
        "preflight",
        "discover_onts",
        "snapshot_ont",
        "find_free_ont_id",
        "delete_ont",
        "register_ont",
        "provision_ipoe",
        "provision_pppoe",
        "read_wan_info",
        "remove_test_services",
        "restore_snapshot",
        "verify_restore",
    ):
        registry.register("ma5800", action_code, _BoundActionHandler(getattr(actions, action_code)))
