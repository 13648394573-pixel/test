from pathlib import Path

from app.local_runner.ma5800.parsers import (
    normalize_cli_output,
    parse_autofind,
    parse_command_result,
    parse_ont_state,
    parse_service_ports,
    parse_wan_info,
)


FIXTURES = Path(__file__).parent / "fixtures" / "ma5800"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_autofind_extracts_target_and_ignores_secret_field() -> None:
    result = parse_autofind(load_fixture("autofind.txt"))

    assert len(result) == 1
    assert result[0].fsp == "0/2/10"
    assert result[0].serial_number == "48575443DD91BBBB"
    assert result[0].equipment_id == "ONU-4GE-DUALBAND"
    assert "Password" not in result[0].raw_fields


def test_parse_autofind_distinguishes_empty_result_from_command_failure() -> None:
    empty = parse_command_result(
        "The number of GPON autofind ONT is 0\nMA5800-X7#",
        expected_kind="AUTOFIND",
    )
    failure = parse_command_result(load_fixture("command_failure.txt"))

    assert empty.success is True
    assert empty.code == "NO_AUTOFIND_RESULT"
    assert failure.success is False
    assert failure.code == "OLT_COMMAND_FAILED"


def test_parse_ont_state_requires_explicit_online_and_match_fields() -> None:
    state = parse_ont_state(load_fixture("ont_online.txt"))

    assert state.fsp == "0/2/10"
    assert state.ont_id == 36
    assert state.run_state == "online"
    assert state.match_state == "match"
    assert state.line_profile_id == 10
    assert state.service_profile_id == 10


def test_parse_wan_info_extracts_ipoe_and_pppoe_without_account_data() -> None:
    ipoe = parse_wan_info(load_fixture("wan_ipoe.txt"))[0]
    pppoe = parse_wan_info(load_fixture("wan_pppoe.txt"))[0]

    assert (ipoe.mode, ipoe.ip_index, ipoe.vlan, ipoe.status) == (
        "IPOE",
        1,
        1000,
        "CONNECTED",
    )
    assert ipoe.ip_address == "192.0.2.10"
    assert ipoe.gateway == "192.0.2.1"
    assert (pppoe.mode, pppoe.ip_index, pppoe.ip_address) == (
        "PPPOE",
        0,
        "198.51.100.20",
    )
    assert "User name" not in pppoe.raw_fields


def test_normalize_removes_paging_and_ansi_cursor_sequences() -> None:
    raw = "first\r\n---- More ( Press 'Q' to break ) ----\x1b[37D      \x1b[37Dsecond\r\n"
    assert normalize_cli_output(raw).splitlines() == ["first", "second"]


def test_parse_service_ports_extracts_structured_rows() -> None:
    output = """
INDEX  VLAN  F/S/P   ONT  GEM  USER-VLAN
21     1000  0/2/10 36   1    1000
MA5800-X7(config)#
"""
    ports = parse_service_ports(output)
    assert [(item.service_port_id, item.fsp, item.ont_id) for item in ports] == [
        (21, "0/2/10", 36)
    ]

