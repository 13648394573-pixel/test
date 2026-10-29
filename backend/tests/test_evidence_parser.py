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


def test_evidence_read_exposes_parsed_metadata_as_object() -> None:
    from app.evidence.schemas import EvidenceRead

    read = EvidenceRead.model_validate(
        {
            "id": "ev-1",
            "run_result_id": "rr-1",
            "defect_id": None,
            "run_result_ids": ["rr-1"],
            "category": "LOG",
            "original_name": "ont.txt",
            "storage_path": "run-results/rr-1/ev-1.txt",
            "media_type": "text/plain",
            "file_size": 10,
            "sha256": "a" * 64,
            "description": None,
            "parsed_metadata": '{"parser_version": 1, "checks": {"ont_online": true}}',
            "created_at": "2026-10-29T00:00:00",
        }
    )
    assert isinstance(read.parsed_metadata, dict)
    assert read.parsed_metadata["checks"]["ont_online"] is True


def test_evidence_read_tolerates_bad_json_and_null() -> None:
    from app.evidence.schemas import EvidenceRead

    base = {
        "id": "ev-2",
        "run_result_id": None,
        "defect_id": None,
        "run_result_ids": [],
        "category": "OTHER",
        "original_name": "x.bin",
        "storage_path": "run-results/x/ev-2.bin",
        "media_type": "application/octet-stream",
        "file_size": 1,
        "sha256": "b" * 64,
        "description": None,
        "created_at": "2026-10-29T00:00:00",
    }
    assert EvidenceRead.model_validate({**base, "parsed_metadata": None}).parsed_metadata is None
    assert EvidenceRead.model_validate({**base, "parsed_metadata": "not-json"}).parsed_metadata is None
