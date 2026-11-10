from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
from ipaddress import ip_address
import re
import time
from typing import Any, Callable, Protocol

import paramiko

from app.local_runner.ma5800.parsers import normalize_cli_output
from .service_port_contracts import ServicePortMapping


class CommandTimeoutError(Exception):
    pass


class MissingHostKeyApprovalRequired(Exception):
    pass


class HostKeyFingerprintMismatchError(Exception):
    pass


class ShellChannel(Protocol):
    def send(self, value: str) -> object: ...

    def recv_ready(self) -> bool: ...

    def recv(self, size: int) -> bytes: ...


def _invalid_arguments(action_code: str):
    raise ValueError(f"Invalid arguments for allow-listed action: {action_code}")


def _int_arg(value: Any, *, maximum: int = 4095) -> int:
    if isinstance(value, bool):
        raise ValueError("Boolean is not a valid numeric command argument")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.isascii() and value.isdigit():
        result = int(value)
    else:
        raise ValueError("Unsafe numeric command argument")
    if not 0 <= result <= maximum:
        raise ValueError("Numeric command argument is out of range")
    return result


def _serial_arg(value: Any) -> str:
    serial = str(value).upper()
    if not re.fullmatch(r"[0-9A-F]{16}", serial):
        raise ValueError("Unsafe ONU serial number")
    return serial


def _fsp_arg(value: Any) -> str:
    fsp = str(value).replace(" ", "")
    if not re.fullmatch(r"\d+/\d+/\d+", fsp):
        raise ValueError("Unsafe F/S/P argument")
    return fsp


def _secret_arg(value: Any) -> str:
    reveal = getattr(value, "reveal", None)
    if not callable(reveal):
        raise ValueError("Sensitive command argument must be SecretValue")
    secret = reveal()
    if not secret or not re.fullmatch(r"[A-Za-z0-9._@%+=:,/#~-]+", secret):
        raise ValueError("Unsafe sensitive command argument")
    return secret


def _no_args(code: str, text: str):
    def build(arguments: tuple[Any, ...]) -> str:
        if arguments:
            return _invalid_arguments(code)
        return text
    return build


def _display_ont_by_sn(arguments: tuple[Any, ...]) -> str:
    if len(arguments) != 1:
        return _invalid_arguments("display_ont_by_sn")
    return f"display ont info by-sn {_serial_arg(arguments[0])}"


def _display_ont_port(arguments: tuple[Any, ...]) -> str:
    if len(arguments) != 1:
        return _invalid_arguments("display_ont_port")
    return f"display ont info {_int_arg(arguments[0], maximum=255)} all"


def _display_wan_info(arguments: tuple[Any, ...]) -> str:
    if len(arguments) != 2:
        return _invalid_arguments("display_wan_info")
    return f"display ont wan-info {_int_arg(arguments[0], maximum=255)} {_int_arg(arguments[1], maximum=255)}"


def _display_service_ports(arguments: tuple[Any, ...]) -> str:
    if len(arguments) != 2:
        return _invalid_arguments("display_service_ports")
    return f"display service-port port {_fsp_arg(arguments[0])} ont {_int_arg(arguments[1], maximum=255)}"


def _enter_gpon_interface(arguments: tuple[Any, ...]) -> str:
    if len(arguments) != 2:
        return _invalid_arguments("enter_gpon_interface")
    frame = _int_arg(arguments[0], maximum=15)
    slot = _int_arg(arguments[1], maximum=31)
    return f"interface gpon {frame}/{slot}"


def _delete_ont(arguments: tuple[Any, ...]) -> str:
    if len(arguments) != 2:
        return _invalid_arguments("delete_ont")
    return f"ont delete {_int_arg(arguments[0], maximum=255)} {_int_arg(arguments[1], maximum=255)}"


def _register_ont(arguments: tuple[Any, ...]) -> str:
    if len(arguments) != 6:
        return _invalid_arguments("register_ont")
    port, ont_id, serial, line_profile, service_profile, auth_mode = arguments
    if auth_mode != "sn-auth":
        raise ValueError("Only SN authentication is allow-listed")
    return (
        f"ont add {_int_arg(port, maximum=255)} {_int_arg(ont_id, maximum=255)} "
        f"sn-auth {_serial_arg(serial)} omci "
        f"ont-lineprofile-id {_int_arg(line_profile)} "
        f"ont-srvprofile-id {_int_arg(service_profile)}"
    )


def _provision_ipoe(arguments: tuple[Any, ...]) -> str:
    if len(arguments) not in {3, 4}:
        return _invalid_arguments("provision_ipoe")
    port, ont_id, vlan = arguments[:3]
    index = _int_arg(arguments[3], maximum=255) if len(arguments) == 4 else 1
    return (
        f"ont ipconfig {_int_arg(port, maximum=255)} {_int_arg(ont_id, maximum=255)} "
        f"ip-index {index} dhcp vlan {_int_arg(vlan)} priority 0"
    )


def _provision_pppoe(arguments: tuple[Any, ...]) -> str:
    if len(arguments) not in {5, 6}:
        return _invalid_arguments("provision_pppoe")
    port, ont_id, username, password, vlan = arguments[:5]
    index = _int_arg(arguments[5], maximum=255) if len(arguments) == 6 else 0
    return (
        f"ont ipconfig {_int_arg(port, maximum=255)} {_int_arg(ont_id, maximum=255)} "
        f"ip-index {index} pppoe user-account username {_secret_arg(username)} password {_secret_arg(password)} "
        f"vlan {_int_arg(vlan)}"
    )


def _remove_service_port(arguments: tuple[Any, ...]) -> str:
    if len(arguments) != 1:
        return _invalid_arguments("remove_service_port")
    return f"undo service-port {_int_arg(arguments[0], maximum=65535)}"


def _display_service_port_by_id(arguments):
    if len(arguments) != 1 or type(arguments[0]) is not int:
        return _invalid_arguments('display_service_port_by_id')
    return f'display service-port {_int_arg(arguments[0], maximum=65535)}'


def _read_profile_gem(arguments):
    if len(arguments) != 1 or type(arguments[0]) is not int:
        return _invalid_arguments('read_profile_gem')
    return f'display ont-lineprofile gpon profile-id {_int_arg(arguments[0])}'


def _create_service_port(arguments):
    if len(arguments) != 8:
        return _invalid_arguments('create_service_port')
    port_id, vlan, fsp, ont_id, gemport, user_vlan, transform, business_type = arguments
    spec = ServicePortMapping(candidate_id=port_id, vlan=vlan, fsp=fsp, ont_id=ont_id,
        gemport=gemport, user_vlan=user_vlan, tag_transform=transform, business_type=business_type,
        olt_binding_hash='0' * 64)
    if spec.candidate_id is None:
        return _invalid_arguments('create_service_port')
    return (f'service-port {spec.candidate_id} vlan {spec.vlan} gpon {spec.fsp} ont {spec.ont_id} '
            f'gemport {spec.gemport} multi-service user-vlan {spec.user_vlan} tag-transform translate')


_SAFE_COMMANDS: dict[str, Callable[[tuple[Any, ...]], str]] = {
    "enable": _no_args("enable", "enable"),
    "disable_paging": _no_args("disable_paging", "screen-length 0 temporary"),
    "enter_config": _no_args("enter_config", "config"),
    "enter_gpon_interface": _enter_gpon_interface,
    "leave_gpon_interface": _no_args("leave_gpon_interface", "quit"),
    "display_autofind": _no_args("display_autofind", "display ont autofind all"),
    "display_ont_by_sn": _display_ont_by_sn,
    "display_ont_port": _display_ont_port,
    "display_wan_info": _display_wan_info,
    "display_service_ports": _display_service_ports,
    "delete_ont": _delete_ont,
    "register_ont": _register_ont,
    "provision_ipoe": _provision_ipoe,
    "provision_pppoe": _provision_pppoe,
    "remove_service_port": _remove_service_port,
    "display_service_port_by_id": _display_service_port_by_id,
    "read_profile_gem": _read_profile_gem,
    "create_service_port": _create_service_port,
}


@dataclass(frozen=True)
class SafeMA5800Command:
    action_code: str
    arguments: tuple[Any, ...]

    def render(self) -> str:
        builder = _SAFE_COMMANDS.get(self.action_code)
        if builder is None:
            raise ValueError(f"Command is not allow-listed: {self.action_code}")
        return builder(self.arguments)

    @property
    def text(self) -> str:
        return self.render()


@dataclass(frozen=True)
class CommandTranscript:
    action_code: str
    raw_output: str
    normalized_output: str
    prompt: str
    sha256: str


PROMPT = re.compile(r"(?m)(MA5800-X7(?:\([^\r\n)]*\))?[>#])\s*$")


class MA5800Transport:
    def __init__(
        self,
        channel: ShellChannel,
        *,
        timeout_seconds: float = 30,
        monotonic: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.channel = channel
        self.timeout_seconds = timeout_seconds
        self.monotonic = monotonic
        self.sleeper = sleeper

    def run(self, command: SafeMA5800Command) -> CommandTranscript:
        text = command.render()
        self.channel.send(f"{text}\n")
        started = self.monotonic()
        chunks: list[str] = []
        handled_more = 0
        handled_cr = 0
        while True:
            if self.channel.recv_ready():
                chunks.append(self.channel.recv(65535).decode("utf-8", errors="replace"))
                raw = "".join(chunks)
                more_count = len(re.findall(r"----\s*More", raw, re.IGNORECASE))
                while handled_more < more_count:
                    self.channel.send(" ")
                    handled_more += 1
                cr_count = len(re.findall(r"\{\s*<cr>[^\r\n]*\}\s*:", raw, re.IGNORECASE))
                while handled_cr < cr_count:
                    self.channel.send("\n")
                    handled_cr += 1
                prompt_match = PROMPT.search(raw)
                if prompt_match:
                    normalized = normalize_cli_output(raw)
                    return CommandTranscript(
                        action_code=command.action_code,
                        raw_output=raw,
                        normalized_output=normalized,
                        prompt=prompt_match.group(1),
                        sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
                    )
            if self.monotonic() - started >= self.timeout_seconds:
                raise CommandTimeoutError(command.action_code)
            self.sleeper(0.05)

    def synchronize(self) -> str:
        started = self.monotonic()
        chunks: list[str] = []
        while True:
            if self.channel.recv_ready():
                chunks.append(self.channel.recv(65535).decode("utf-8", errors="replace"))
                match = PROMPT.search("".join(chunks))
                if match:
                    return match.group(1)
            if self.monotonic() - started >= self.timeout_seconds:
                raise CommandTimeoutError("synchronize")
            self.sleeper(0.05)


def host_key_fingerprint(key) -> str:
    digest = hashlib.sha256(key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


class PinnedHostKeyPolicy(paramiko.MissingHostKeyPolicy):
    def __init__(
        self,
        *,
        expected_fingerprint: str | None,
        formal_mode: bool,
        approved_first_use_fingerprint: str | None = None,
    ) -> None:
        fingerprint = expected_fingerprint or approved_first_use_fingerprint
        if fingerprint is None:
            raise MissingHostKeyApprovalRequired(
                "OLT host key fingerprint requires operator approval"
            )
        self.expected_fingerprint = fingerprint
        self.formal_mode = formal_mode

    def missing_host_key(self, client, hostname: str, key) -> None:
        actual = host_key_fingerprint(key)
        if actual != self.expected_fingerprint:
            raise HostKeyFingerprintMismatchError(
                f"Host key fingerprint mismatch for {hostname}"
            )
        if client is not None:
            client._host_keys.add(hostname, key.get_name(), key)


class MA5800SSHConnector:
    def __init__(
        self,
        client_factory: Callable[[], paramiko.SSHClient] = paramiko.SSHClient,
        transport_factory: Callable[[tuple[str, int]], Any] = paramiko.Transport,
    ):
        self.client_factory = client_factory
        self.transport_factory = transport_factory

    def preview_host_key(
        self,
        hostname: str,
        port: int,
        timeout_seconds: float = 10,
    ) -> str:
        try:
            address = ip_address(hostname)
        except ValueError as exception:
            raise ValueError("OLT host must be a private IP address") from exception
        if not (address.is_private or address.is_loopback or address.is_link_local):
            raise ValueError("OLT host must be a private IP address")
        if not 1 <= port <= 65535:
            raise ValueError("OLT port is out of range")
        transport = self.transport_factory((hostname, port))
        try:
            transport.start_client(timeout=timeout_seconds)
            return host_key_fingerprint(transport.get_remote_server_key())
        finally:
            transport.close()

    def connect(
        self,
        *,
        hostname: str,
        port: int,
        username: str,
        password: str,
        expected_fingerprint: str,
        formal_mode: bool,
        timeout_seconds: float = 10,
    ):
        client = self.client_factory()
        try:
            client.load_system_host_keys()
            client.set_missing_host_key_policy(
                PinnedHostKeyPolicy(
                    expected_fingerprint=expected_fingerprint,
                    formal_mode=formal_mode,
                )
            )
            client.connect(
                hostname=hostname,
                port=port,
                timeout=timeout_seconds,
                banner_timeout=timeout_seconds,
                auth_timeout=timeout_seconds,
                auth_strategy=_PinnedPasswordAuthentication(username, password, expected_fingerprint),
            )
            transport = client.get_transport()
            if transport is None or host_key_fingerprint(transport.get_remote_server_key()) != expected_fingerprint:
                raise HostKeyFingerprintMismatchError('OLT_HOST_KEY_PIN_MISMATCH')
            return client
        except Exception:
            client.close()
            raise


class _PinnedPasswordAuthentication(paramiko.AuthStrategy):
    """Runs after ordinary host-key validation, before any credential is sent."""
    def __init__(self, username, password, fingerprint):
        super().__init__(ssh_config=None)
        self.username, self._password, self.fingerprint = username, password, fingerprint

    def authenticate(self, transport):
        if host_key_fingerprint(transport.get_remote_server_key()) != self.fingerprint:
            raise HostKeyFingerprintMismatchError('OLT_HOST_KEY_PIN_MISMATCH')
        return transport.auth_password(self.username, self._password)
