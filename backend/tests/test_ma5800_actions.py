from pathlib import Path

import pytest

from app.local_runner.contracts import ActionContext
from app.local_runner.credentials import SecretValue
from app.local_runner.ma5800.actions import (
    MA5800Actions,
    ParameterValidationError,
    build_delete_command,
    build_ipoe_command,
    build_pppoe_command,
    build_register_command,
    register_default_ma5800_actions,
    validate_gpon_port,
)
from app.local_runner.ma5800.transport import CommandTranscript
from app.local_runner.registry import LocalActionRegistry


FIXTURES = Path(__file__).parent / "fixtures" / "ma5800"


def transcript(action_code: str, fixture: str) -> CommandTranscript:
    raw = (FIXTURES / fixture).read_text(encoding="utf-8")
    return CommandTranscript(action_code, raw, raw, "MA5800-X7#", "a" * 64)


class FakeExecutor:
    def __init__(self):
        self.commands = []

    def run(self, command):
        self.commands.append(command)
        fixture = {
            "display_autofind": "autofind.txt",
            "display_ont_by_sn": "ont_online.txt",
            "display_wan_info": "wan_ipoe.txt",
        }.get(command.action_code)
        if fixture:
            return transcript(command.action_code, fixture)
        if command.action_code == "display_service_ports":
            return CommandTranscript(command.action_code, "", "21 1000 0/2/10 36 1 1000\nMA5800-X7#", "MA5800-X7#", "b" * 64)
        return CommandTranscript(
            command.action_code,
            "Command executed successfully\nMA5800-X7#",
            "Command executed successfully\nMA5800-X7#",
            "MA5800-X7#",
            "b" * 64,
        )


def valid_registration_parameters() -> dict:
    return {
        "frame": 0,
        "slot": 2,
        "pon_port": 10,
        "ont_id": 36,
        "onu_serial_number": "48575443DD91BBBB",
        "line_profile_id": 10,
        "service_profile_id": 10,
    }


def context(action_code: str, **parameters) -> ActionContext:
    return ActionContext(
        session_id="session-1",
        action_code=action_code,
        parameters={**valid_registration_parameters(), **parameters},
    )


def observation(outcome, fact_key: str):
    return next(item.value for item in outcome.observations if item.fact_key == fact_key)


def test_register_action_builds_command_only_from_validated_fields() -> None:
    command = build_register_command(valid_registration_parameters())
    assert command.text == (
        "ont add 10 36 sn-auth 48575443DD91BBBB omci "
        "ont-lineprofile-id 10 ont-srvprofile-id 10"
    )


@pytest.mark.parametrize("value", ["10;quit", "../10", "10\nundo service-port 1"])
def test_numeric_fields_reject_command_injection(value) -> None:
    with pytest.raises(ParameterValidationError):
        validate_gpon_port(value)


def test_wan_builders_keep_pppoe_secret_out_of_repr() -> None:
    ipoe = build_ipoe_command({**valid_registration_parameters(), "ipoe_vlan": 1000})
    pppoe = build_pppoe_command(
        {**valid_registration_parameters(), "pppoe_vlan": 1000},
        username=SecretValue("lab-user"),
        password=SecretValue("lab-pass"),
    )
    assert ipoe.text == "ont ipconfig 10 36 ip-index 1 dhcp vlan 1000 priority 0"
    assert "lab-user" in pppoe.text and "lab-pass" in pppoe.text
    assert "lab-user" not in repr(pppoe) and "lab-pass" not in repr(pppoe)


@pytest.mark.parametrize("unsafe", ["bad user", "bad;undo", "bad\nvalue"])
def test_pppoe_cli_rejects_unsafe_secret_token(unsafe: str) -> None:
    command = build_pppoe_command(
        {**valid_registration_parameters(), "pppoe_vlan": 1000},
        username=SecretValue(unsafe),
        password=SecretValue("safe-value"),
    )
    with pytest.raises(ValueError, match="Unsafe sensitive"):
        _ = command.text


def test_delete_waits_for_matching_preview_approval() -> None:
    executor = FakeExecutor()
    actions = MA5800Actions(executor)
    first = actions.delete_ont(context("delete_ont", affected_service_ports=[21]))
    preview = observation(first, "mutation.preview")

    assert first.status == "WAITING_OPERATOR"
    assert executor.commands == []

    wrong = actions.delete_ont(
        context(
            "delete_ont",
            affected_service_ports=[21],
            mutation_approval={"approved": True, "preview_hash": "wrong"},
        )
    )
    assert wrong.status == "WAITING_OPERATOR"
    assert executor.commands == []

    approved = actions.delete_ont(
        context(
            "delete_ont",
            affected_service_ports=[21],
            mutation_approval={
                "approved": True,
                "preview_hash": preview["preview_hash"],
            },
        )
    )
    assert approved.status == "PASS"
    assert [command.action_code for command in executor.commands] == [
        "display_ont_by_sn", "display_service_ports", "delete_ont"]
    assert executor.commands[-1] == build_delete_command(valid_registration_parameters())


def test_snapshot_captures_registration_wan_and_service_port_scope() -> None:
    executor = FakeExecutor()
    outcome = MA5800Actions(executor).snapshot_ont(
        context("snapshot_ont", service_ports=[])
    )
    snapshot = observation(outcome, "olt.configuration_snapshot")

    assert outcome.status == "PASS"
    assert snapshot["registration"]["ont_id"] == 36
    assert snapshot["registration"]["line_profile_id"] == 10
    assert snapshot["wan"][0]["mode"] == "IPOE"
    assert snapshot["service_ports"][0]["service_port_id"] == 21


def test_restore_rejects_unsupported_snapshot_without_sending_commands() -> None:
    executor = FakeExecutor()
    outcome = MA5800Actions(executor).restore_snapshot(
        context(
            "restore_snapshot",
            configuration_snapshot={"unsupported": {"raw": "data"}},
        )
    )
    assert outcome.status == "ERROR"
    assert outcome.error_code == "RECOVERY_REQUIRED"
    assert executor.commands == []


def test_default_registry_exposes_only_named_ma5800_actions() -> None:
    registry = LocalActionRegistry()
    register_default_ma5800_actions(registry, MA5800Actions(FakeExecutor()))

    assert registry.resolve("ma5800", "discover_onts")
    assert registry.resolve("ma5800", "verify_restore")
    with pytest.raises(Exception):
        registry.resolve("ma5800", "run_raw_command")
