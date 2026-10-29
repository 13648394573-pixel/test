"""Structured parsing and auto-judgement for captured evidence text.

Parses Huawei MA5800-X7 OLT CLI logs, ONU web status pages and ping
diagnostics into machine-checkable metadata, and applies shared PASS/FAIL
judgement rules (O5 state, optical power threshold, packet loss, RTT).

The parsed payload is stored on the evidence row at upload time as JSON
(`parsed_metadata`); original evidence files are never modified.
"""
from __future__ import annotations

import json
import re
from typing import Any

PARSER_VERSION = 1

# Typical GPON Class B+ receiver sensitivity threshold (dBm).
RX_POWER_THRESHOLD_DBM = -27.0
# Shared expectation for WAN connectivity checks.
MAX_AVG_RTT_MS = 100.0


def _match(match: "re.Match[str] | None") -> str | None:
    return match.group(1).strip() if match else None


def parse_olt_cli(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {"type": "olt_cli", "onts": []}
    for block in re.split(r"(?=display ont info)", text):
        if "ONT-ID" not in block:
            continue
        data["onts"].append(
            {
                "fsp": _match(re.search(r"F/S/P\s*:\s*(\S+)", block)),
                "ont_id": _match(re.search(r"ONT-ID\s*:\s*(\S+)", block)),
                "run_state": _match(re.search(r"Run state\s*:\s*(\S+)", block)),
                "config_state": _match(
                    re.search(r"Config state\s*:\s*(\S+)", block)
                ),
                "match_state": _match(
                    re.search(r"Match state\s*:\s*(\S+)", block)
                ),
                "sn": _match(re.search(r"SN\s*:\s*(\S+)", block)),
                "authentic_type": _match(
                    re.search(r"Authentic type\s*:\s*(\S+)", block)
                ),
                "last_down_cause": _match(
                    re.search(r"Last down cause\s*:\s*(\S+)", block)
                ),
                "last_up_time": _match(
                    re.search(r"Last up time\s*:\s*(.+)", block)
                ),
            }
        )
    return data


def parse_ping_diag(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {"type": "ping_diag"}
    stats = re.search(
        r"(\d+) packets transmitted,\s*(\d+) packets received,"
        r"\s*(\d+)% packet loss",
        text,
    )
    if stats:
        data.update(
            {
                "packets_transmitted": int(stats.group(1)),
                "packets_received": int(stats.group(2)),
                "packet_loss_percent": int(stats.group(3)),
            }
        )
    rtt = re.search(
        r"round-trip min/avg/max\s*=\s*([\d.]+)/([\d.]+)/([\d.]+)\s*ms",
        text,
    )
    if rtt:
        data.update(
            {
                "rtt_min_ms": float(rtt.group(1)),
                "rtt_avg_ms": float(rtt.group(2)),
                "rtt_max_ms": float(rtt.group(3)),
            }
        )
    return data


def parse_pon_status(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {"type": "pon_status"}
    mapping = {
        "temperature_c": r"Temperature\s+([\d.-]+)\s*C",
        "voltage_v": r"Voltage\s+([\d.-]+)\s*V",
        "tx_power_dbm": r"Tx Power\s+([\d.-]+)\s*dBm",
        "rx_power_dbm": r"Rx Power\s+([\d.-]+)\s*dBm",
        "bias_current_ma": r"Bias Current\s+([\d.-]+)\s*mA",
    }
    for key, pattern in mapping.items():
        match = re.search(pattern, text)
        if match:
            data[key] = float(match.group(1))
    state = re.search(r"ONU State\s+(\S+)", text)
    if state:
        data["onu_state"] = state.group(1)
    onu_id = re.search(r"ONU ID\s+(\S+)", text)
    if onu_id:
        data["onu_id"] = onu_id.group(1)
    loid = re.search(r"LOID Status\s+([\w ]+\S)", text)
    if loid:
        data["loid_status"] = loid.group(1)
    return data


def parse_text(text: str) -> dict[str, Any]:
    if "display ont info" in text:
        return parse_olt_cli(text)
    if "packets transmitted" in text and "packet loss" in text:
        return parse_ping_diag(text)
    if "Rx Power" in text or "ONU State" in text:
        return parse_pon_status(text)
    return {"type": "unknown"}


def judge(parsed: dict[str, Any]) -> dict[str, Any]:
    """Auto-judgement rules shared by all parsers."""
    checks: dict[str, Any] = {}
    if parsed.get("type") == "olt_cli" and parsed.get("onts"):
        checks["ont_online"] = all(
            ont.get("run_state") == "online" for ont in parsed["onts"]
        )
    if parsed.get("type") == "pon_status":
        if "onu_state" in parsed:
            checks["onu_o5"] = parsed["onu_state"] == "O5"
        if "rx_power_dbm" in parsed:
            checks["rx_power_above_threshold"] = (
                parsed["rx_power_dbm"] > RX_POWER_THRESHOLD_DBM
            )
            checks["rx_power_threshold_dbm"] = RX_POWER_THRESHOLD_DBM
    if parsed.get("type") == "ping_diag":
        if "packet_loss_percent" in parsed:
            checks["no_packet_loss"] = parsed["packet_loss_percent"] == 0
        if "rtt_avg_ms" in parsed:
            checks["avg_rtt_below_limit"] = parsed["rtt_avg_ms"] < MAX_AVG_RTT_MS
            checks["avg_rtt_limit_ms"] = MAX_AVG_RTT_MS
    return checks


def parse_payload(raw_text: str) -> dict[str, Any] | None:
    """Parse evidence text into storable metadata; None if unrecognized."""
    parsed = parse_text(raw_text)
    if parsed.get("type") == "unknown":
        return None
    return {
        "parser_version": PARSER_VERSION,
        "parsed": parsed,
        "checks": judge(parsed),
    }


def dumps(payload: dict[str, Any] | None) -> str | None:
    return json.dumps(payload, ensure_ascii=False) if payload else None


def loads(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None
