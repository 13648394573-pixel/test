from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Callable, Protocol

from app.local_runner.contracts import Observation
from app.local_runner.credentials import SecretValue
from app.local_runner.ma5800.parsers import (
    parse_autofind,
    parse_command_result,
    parse_ont_state,
    parse_service_ports,
    parse_wan_info,
)
from app.local_runner.ma5800.transport import (
    CommandTranscript,
    MA5800SSHConnector,
    MA5800Transport,
    SafeMA5800Command,
)


READ_ONLY_ACTIONS = frozenset(
    {
        "enable",
        "disable_paging",
        "enter_config",
        "enter_gpon_interface",
        "display_autofind",
        "display_ont_by_sn",
        "display_ont_port",
        "display_wan_info",
        "display_service_ports",
    }
)


class ReadOnlyCommandViolation(Exception):
    pass


class OLTProbeBlocked(Exception):
    def __init__(self, reason: str, transcripts: tuple[CommandTranscript, ...]):
        self.reason = reason
        self.transcripts = transcripts
        super().__init__(reason)


class CommandExecutor(Protocol):
    def run(self, command: SafeMA5800Command) -> CommandTranscript: ...


class SessionTransport(CommandExecutor, Protocol):
    def synchronize(self) -> str: ...


class ReadOnlyMA5800Executor:
    def __init__(self, delegate: CommandExecutor):
        self.delegate = delegate

    def run(self, command: SafeMA5800Command) -> CommandTranscript:
        if command.action_code not in READ_ONLY_ACTIONS:
            raise ReadOnlyCommandViolation(command.action_code)
        return self.delegate.run(command)


@dataclass(frozen=True)
class OLTProbeRequest:
    host: str
    port: int
    expected_fingerprint: str
    onu_serial_number: str | None
    frame: int | None
    slot: int | None
    pon_port: int | None
    ont_id: int | None


@dataclass(frozen=True)
class OLTProbeResult:
    observations: tuple[Observation, ...]
    transcripts: tuple[CommandTranscript, ...]
    current_registration_found: bool
    current_wan_found: bool


class MA5800ReadOnlyProbe:
    def __init__(
        self,
        *,
        connector: MA5800SSHConnector | None = None,
        transport_factory: Callable[[object], SessionTransport] = MA5800Transport,
    ) -> None:
        self.connector = connector or MA5800SSHConnector()
        self.transport_factory = transport_factory

    def preview_host_key(self, host: str, port: int) -> str:
        return self.connector.preview_host_key(host, port)

    def run(
        self,
        request: OLTProbeRequest,
        username: SecretValue,
        password: SecretValue,
    ) -> OLTProbeResult:
        target = (request.frame, request.slot, request.pon_port, request.ont_id)
        if any(value is not None for value in target) and not all(
            value is not None for value in target
        ):
            raise ValueError("frame, slot, pon_port, and ont_id must all be provided")

        client = self.connector.connect(
            hostname=request.host,
            port=request.port,
            username=username.reveal(),
            password=password.reveal(),
            expected_fingerprint=request.expected_fingerprint,
            formal_mode=True,
        )
        channel = None
        transcripts: list[CommandTranscript] = []
        observations: list[Observation] = []
        registration_found = False
        wan_found = False
        try:
            channel = client.invoke_shell()
            transport = self.transport_factory(channel)
            transport.synchronize()
            executor = ReadOnlyMA5800Executor(transport)

            def execute(action_code: str, arguments: tuple = ()) -> CommandTranscript:
                transcript = executor.run(SafeMA5800Command(action_code, arguments))
                transcripts.append(transcript)
                return transcript

            execute("enable")
            execute("disable_paging")
            autofind = execute("display_autofind")
            observations.append(
                Observation(
                    "olt.autofind.items",
                    [asdict(item) for item in parse_autofind(autofind.normalized_output)],
                    "MA5800",
                )
            )

            if request.onu_serial_number:
                registration = execute(
                    "display_ont_by_sn", (request.onu_serial_number,)
                )
                command_result = parse_command_result(registration.normalized_output)
                missing_registration = re.search(
                    r"(?i)ONT.*(?:does not exist|not exist|not found)",
                    registration.normalized_output,
                )
                if command_result.success:
                    state = parse_ont_state(registration.normalized_output)
                    registration_found = True
                    observations.append(
                        Observation("olt.registration", asdict(state), "MA5800")
                    )
                elif not missing_registration:
                    raise ValueError(
                        command_result.message or "OLT registration output is unsupported"
                    )

            if all(value is not None for value in target):
                execute("enter_config")
                execute("enter_gpon_interface", (request.frame, request.slot))
                execute("display_ont_port", (request.pon_port,))
                wan = execute("display_wan_info", (request.pon_port, request.ont_id))
                wan_items = parse_wan_info(wan.normalized_output)
                wan_found = bool(wan_items)
                observations.append(
                    Observation(
                        "olt.wan.items",
                        [asdict(item) for item in wan_items],
                        "MA5800",
                    )
                )
                service_ports = execute(
                    "display_service_ports",
                    (f"{request.frame}/{request.slot}/{request.pon_port}", request.ont_id),
                )
                observations.append(
                    Observation(
                        "olt.service_ports",
                        [
                            asdict(item)
                            for item in parse_service_ports(
                                service_ports.normalized_output
                            )
                        ],
                        "MA5800",
                    )
                )
            return OLTProbeResult(
                tuple(observations),
                tuple(transcripts),
                registration_found,
                wan_found,
            )
        except Exception as exception:
            raise OLTProbeBlocked(
                type(exception).__name__, tuple(transcripts)
            ) from exception
        finally:
            close_channel = getattr(channel, "close", None)
            if callable(close_channel):
                close_channel()
            client.close()
