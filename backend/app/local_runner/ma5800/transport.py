from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import re
import time
from typing import Callable, Protocol

import paramiko

from app.local_runner.ma5800.parsers import normalize_cli_output


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


_SAFE_COMMANDS: dict[str, Callable[[tuple[str, ...]], str]] = {
    "display_autofind": lambda arguments: "display ont autofind all"
    if not arguments
    else _invalid_arguments("display_autofind"),
}


def _invalid_arguments(action_code: str):
    raise ValueError(f"Invalid arguments for allow-listed action: {action_code}")


@dataclass(frozen=True)
class SafeMA5800Command:
    action_code: str
    arguments: tuple[str, ...]

    def render(self) -> str:
        builder = _SAFE_COMMANDS.get(self.action_code)
        if builder is None:
            raise ValueError(f"Command is not allow-listed: {self.action_code}")
        return builder(self.arguments)


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
    def __init__(self, client_factory: Callable[[], paramiko.SSHClient] = paramiko.SSHClient):
        self.client_factory = client_factory

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
            username=username,
            password=password,
            timeout=timeout_seconds,
            look_for_keys=False,
            allow_agent=False,
        )
        return client
