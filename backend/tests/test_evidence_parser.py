import json

import pytest

from app.evidence.parser import parse_payload


def test_parse_payload_olt_cli_detects_offline_ont() -> None:
    raw = (
        "display ont info by-sn 48575443DD91BBBB\n"
        "  F/S/P                   : 0/2/10\n"
        "  ONT-ID                  : 36\n"
        "  Run state               : offline\n"
        "  Last down cause         : LOSi/LOBi\n"
    )
    payload = parse_payload(raw)
    assert payload is not None
    assert payload["parsed"]["type"] == "olt_cli"
    assert payload["parsed"]["onts"][0]["fsp"] == "0/2/10"
    assert payload["parsed"]["onts"][0]["run_state"] == "offline"
    assert payload["checks"]["ont_online"] is False


def test_parse_payload_ping_diag_passes_thresholds() -> None:
    raw = (
        "PING www.baidu.com (183.2.172.177): 56 data bytes\n"
        "4 packets transmitted, 4 packets received, 0% packet loss\n"
        "round-trip min/avg/max = 10.078/12.006/16.779 ms\n"
    )
    payload = parse_payload(raw)
    assert payload["parsed"]["packet_loss_percent"] == 0
    assert payload["parsed"]["rtt_avg_ms"] == 12.006
    assert payload["checks"]["no_packet_loss"] is True
    assert payload["checks"]["avg_rtt_below_limit"] is True


def test_parse_payload_pon_status_o5_and_optical() -> None:
    raw = (
        "Tx Power\t2.488809 dBm\n"
        "Rx Power\t-6.619421 dBm\n"
        "ONU State\tO5\n"
        "LOID Status\tLOID Error\n"
    )
    payload = parse_payload(raw)
    assert payload["parsed"]["onu_state"] == "O5"
    assert payload["parsed"]["rx_power_dbm"] == -6.619421
    assert payload["checks"]["onu_o5"] is True
    assert payload["checks"]["rx_power_above_threshold"] is True


def test_parse_payload_returns_none_for_unknown_text() -> None:
    assert parse_payload("random page content") is None
