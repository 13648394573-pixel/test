from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping


ANSI_ESCAPE = re.compile(r"\x1B(?:\[[0-?]*[ -/]*[@-~]|[@-_])")
PAGING_MARKER = re.compile(r"----\s*More(?:\s*\([^\r\n]*\))?\s*----", re.IGNORECASE)
PROMPT_LINE = re.compile(r"^MA5800-X7(?:\([^\r\n)]*\))?[>#]\s*$", re.MULTILINE)
SENSITIVE_FIELD = re.compile(
    r"(?i)(password|passwd|user(?:\s*name)?|account|loid|token|secret)"
)


@dataclass(frozen=True)
class AutofindObservation:
    fsp: str
    serial_number: str
    equipment_id: str | None
    autofind_time: str | None
    raw_fields: Mapping[str, str]


@dataclass(frozen=True)
class OntStateObservation:
    fsp: str
    ont_id: int
    serial_number: str
    run_state: str
    config_state: str
    match_state: str
    line_profile_id: int | None
    service_profile_id: int | None


@dataclass(frozen=True)
class WanObservation:
    mode: str
    ip_index: int
    vlan: int | None
    status: str
    ip_address: str | None
    subnet_mask: str | None
    gateway: str | None
    primary_dns: str | None
    service_type: str | None
    raw_fields: Mapping[str, str]


@dataclass(frozen=True)
class ServicePortObservation:
    service_port_id: int
    vlan: int
    fsp: str
    ont_id: int
    gemport: int
    user_vlan: int


@dataclass(frozen=True)
class CommandResult:
    success: bool
    code: str
    message: str | None
    normalized_output: str


def normalize_cli_output(value: str) -> str:
    normalized = value.replace("\r\r\n", "\n").replace("\r\n", "\n").replace("\r", "\n")
    normalized = ANSI_ESCAPE.sub("", normalized)
    normalized = PAGING_MARKER.sub("", normalized)
    lines = [line.strip() for line in normalized.splitlines()]
    return "\n".join(line for line in lines if line)


def _safe_fields(value: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in normalize_cli_output(value).splitlines():
        match = re.match(r"^([^:]+?)\s*:\s*(.*?)\s*$", line)
        if not match:
            continue
        key, field_value = match.groups()
        key = key.strip()
        if not SENSITIVE_FIELD.search(key):
            fields[key] = field_value.strip()
    return fields


def _get(fields: Mapping[str, str], *names: str) -> str | None:
    folded = {key.casefold(): value for key, value in fields.items()}
    for name in names:
        if name.casefold() in folded:
            return folded[name.casefold()]
    return None


def _required(fields: Mapping[str, str], *names: str) -> str:
    value = _get(fields, *names)
    if value is None or not value:
        raise ValueError(f"Required MA5800 field is missing: {names[0]}")
    return value


def _optional_int(value: str | None) -> int | None:
    if value is None or not value.isdigit():
        return None
    return int(value)


def parse_autofind(value: str) -> tuple[AutofindObservation, ...]:
    normalized = normalize_cli_output(value)
    starts = list(re.finditer(r"(?im)^F/S/P\s*:\s*", normalized))
    observations: list[AutofindObservation] = []
    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(normalized)
        fields = _safe_fields(normalized[start.start():end])
        serial = _get(fields, "Ont SN", "SN")
        if serial:
            observations.append(
                AutofindObservation(
                    fsp=_required(fields, "F/S/P").replace(" ", ""),
                    serial_number=serial.upper(),
                    equipment_id=_get(fields, "Ont EquipmentID", "Equipment ID"),
                    autofind_time=_get(fields, "Ont autofind time"),
                    raw_fields=fields,
                )
            )
    return tuple(observations)


def _parse_ont_serial(value: str) -> str:
    serial_fields = re.findall(
        r"(?im)^(?:SN|Ont SN)[ \t]*:[ \t]*(.*)$", normalize_cli_output(value)
    )
    if len(serial_fields) != 1:
        raise ValueError("Expected exactly one MA5800 serial field")
    match = re.fullmatch(
        r"([0-9a-f]{16})(?:[ \t]+\(([a-z0-9]{4})-([0-9a-f]{8})\))?",
        serial_fields[0],
        re.IGNORECASE | re.ASCII,
    )
    if match is None:
        raise ValueError("Invalid MA5800 serial format")
    serial, vendor, suffix = match.groups()
    serial = serial.upper()
    if vendor is not None:
        try:
            expected_vendor = bytes.fromhex(serial[:8]).decode("ascii").upper()
        except UnicodeDecodeError as exc:
            raise ValueError("Invalid MA5800 serial annotation") from exc
        if vendor.upper() != expected_vendor or suffix.upper() != serial[8:]:
            raise ValueError("Inconsistent MA5800 serial annotation")
    return serial


def parse_ont_state(value: str) -> OntStateObservation:
    fields = _safe_fields(value)
    return OntStateObservation(
        fsp=_required(fields, "F/S/P").replace(" ", ""),
        ont_id=int(_required(fields, "ONT-ID", "ONT ID")),
        serial_number=_parse_ont_serial(value),
        run_state=_required(fields, "Run state").lower(),
        config_state=_required(fields, "Config state").lower(),
        match_state=_required(fields, "Match state").lower(),
        line_profile_id=_optional_int(_get(fields, "Line profile ID")),
        service_profile_id=_optional_int(_get(fields, "Service profile ID")),
    )


def parse_wan_info(value: str) -> tuple[WanObservation, ...]:
    normalized = normalize_cli_output(value)
    starts = list(re.finditer(r"(?im)^(?:WAN index|Index)\s*:\s*", normalized))
    observations: list[WanObservation] = []
    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(normalized)
        fields = _safe_fields(normalized[start.start():end])
        access_type = (_get(fields, "IPv4 access type", "L2 encap-type") or "").upper()
        mode = "PPPOE" if "PPPOE" in access_type else "IPOE" if access_type in {"DHCP", "IPOE"} else "UNKNOWN"
        status = (_get(fields, "IPv4 Connection status", "Connection status", "Status") or "UNKNOWN").upper()
        observations.append(
            WanObservation(
                mode=mode,
                ip_index=int(_required(fields, "WAN index", "Index")),
                vlan=_optional_int(_get(fields, "VLAN", "VLAN ID", "Manage VLAN")),
                status=status,
                ip_address=_get(fields, "IPv4 address", "IP address"),
                subnet_mask=_get(fields, "IPv4 subnet mask", "Subnet mask"),
                gateway=_get(fields, "IPv4 default gateway", "Gateway", "Default gateway"),
                primary_dns=_get(fields, "IPv4 Primary DNS", "Primary DNS"),
                service_type=_get(fields, "Service type"),
                raw_fields=fields,
            )
        )
    return tuple(observations)


def parse_ont_port_target(value: str, fsp: str, ont_id: int) -> OntStateObservation | None:
    row = re.compile(
        r"(?im)^\s*(\d+\s*/\s*\d+\s*/\s*\d+)\s+(\d+)\s+"
        r"([0-9a-f]{16})\s+\S+\s+(online|offline)\s+(\S+)\s+(\S+)\b"
    )
    for match in row.finditer(normalize_cli_output(value)):
        port, target_id, serial, run, config, matched = match.groups()
        if port.replace(" ", "") == fsp and int(target_id) == ont_id:
            return OntStateObservation(fsp, ont_id, serial.upper(), run.lower(),
                                       config.lower(), matched.lower(), None, None)
    return None


def parse_service_ports(value: str) -> tuple[ServicePortObservation, ...]:
    normalized = normalize_cli_output(value)
    if re.search(r'(?im)^(?:Failure\s*:|Error\s*:|%\s*)', normalized):
        raise ValueError('Service-port query failed')
    observations: list[ServicePortObservation] = []
    compact = re.compile(
        r"(\d+)\s+(\d+)\s+(\d+\s*/\s*\d+\s*/\s*\d+)\s+(\d+)\s+(\d+)\s+(\d+)"
    )
    full = re.compile(
        r"(\d+)\s+(\d+)\s+common\s+gpon\s+(\d+\s*/\s*\d+\s*/\s*\d+)"
        r"\s+(\d+)\s+(\d+)\s+vlan\s+(\d+)\s+(?:-|\d+)\s+(?:-|\d+)\s+(?:up|down)",
        re.IGNORECASE,
    )
    full_table = 'switch-oriented flow list' in normalized.casefold()
    totals: list[int] = []
    header_tokens = {'INDEX', 'VLAN', 'PORT', 'F/', 'S/', 'P', 'F/S/P', 'VPI', 'VCI',
                     'FLOW', 'RX', 'TX', 'STATE', 'ID', 'ATTR', 'TYPE', 'PARA',
                     'ONT', 'GEM', 'USER-VLAN'}
    legend_lines = {
        'Note : F--Frame, S--Slot, P--Port,',
        'VPI indicates ONT ID for PON, VCI indicates GEM index for GPON,',
        'v/e--vlan/encap, pritag--priority-tagged,',
        'ppp--pppoe, ip--ipoe, ip4--ipv4oe, ip6--ipv6oe, vxl--vxlan.',
        'When FLOW TYPE is plist, the value of FLOW PARA is a byte in',
        'hexadecimal format and indicates a priority list. Eight bits',
        'of its binary value indicate priorities 0-7 from the least',
        'significant bit to the most significant bit. Value 1 indicates',
        'that the priority is used. For example, if FLOW PARA is 0x23 and',
        'its binary format is 0010 0011, priorities 0, 1 and 5 are used',
    }
    seen_ids: set[int] = set()
    for line in normalized.splitlines():
        if line.casefold() == 'switch-oriented flow list':
            continue
        if re.match(r'(?i)^Total\b', line):
            footer = re.fullmatch(r'Total\s*:\s*(\d+)(?:\s+\(Up/Down\s*:\s*\d+/\d+\))?',
                                  line, re.IGNORECASE)
            if footer is None:
                raise ValueError('Invalid service-port total')
            totals.append(int(footer.group(1)))
            continue
        if not re.match(r'^\d', line):
            envelope = (PROMPT_LINE.fullmatch(line) or line == 'Command:' or
                re.fullmatch(r'\{[ \t]*<cr>[^{}]*\}:', line) or
                re.fullmatch(r'display service-port port \d+\s*/\s*\d+\s*/\s*\d+ ont \d+', line))
            if not (envelope or re.fullmatch(r'-+', line) or
                    all(token in header_tokens for token in line.upper().split()) or
                    (totals and ' '.join(line.split()) in legend_lines)):
                raise ValueError('Unrecognized service-port table content')
            continue
        match = compact.fullmatch(line) or full.fullmatch(line)
        if match is None:
            raise ValueError('Unrecognized service-port row')
        full_table |= full.fullmatch(line) is not None
        service_port, vlan, fsp, ont_id, gemport, user_vlan = match.groups()
        if int(service_port) in seen_ids:
            raise ValueError('Duplicate service-port identity')
        seen_ids.add(int(service_port))
        observations.append(
            ServicePortObservation(
                service_port_id=int(service_port),
                vlan=int(vlan),
                fsp=re.sub(r'\s', '', fsp),
                ont_id=int(ont_id),
                gemport=int(gemport),
                user_vlan=int(user_vlan),
            )
        )
    if len(totals) > 1 or (totals and totals[0] != len(observations)):
        raise ValueError('Service-port total does not match parsed rows')
    if (full_table and not totals) or (not observations and totals != [0]):
        raise ValueError('Service-port completeness cannot be confirmed')
    return tuple(observations)


def parse_command_result(value: str, *, expected_kind: str | None = None) -> CommandResult:
    normalized = normalize_cli_output(value)
    failure = re.search(
        r"(?im)^(?:(?:Failure|Error)\s*:\s*|%\s*)(.+)$", normalized
    )
    if failure:
        return CommandResult(False, "OLT_COMMAND_FAILED", failure.group(1).strip(), normalized)
    if expected_kind == "AUTOFIND" and re.search(
        r"The number of GPON autofind ONT is\s+0\b", normalized, re.IGNORECASE
    ):
        return CommandResult(True, "NO_AUTOFIND_RESULT", None, normalized)
    if PROMPT_LINE.search(normalized):
        return CommandResult(True, "COMMAND_COMPLETED", None, normalized)
    return CommandResult(False, "UNRECOGNIZED_OUTPUT", "OLT prompt was not observed", normalized)

