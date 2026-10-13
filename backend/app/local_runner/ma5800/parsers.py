from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Mapping

from .service_port_contracts import GemVlanMapping, PortRead, ServicePortDetail, ServicePortMapping


def parse_service_port_detail(text: str, *, binding_hash: str) -> PortRead:
    """Accept only a complete scoped detail response; all ambiguity fails closed."""
    if not isinstance(binding_hash, str) or re.fullmatch(r'[0-9a-f]{64}', binding_hash) is None:
        raise ValueError('Invalid service-port binding hash')
    if not isinstance(text, str):
        raise ValueError('Invalid service-port detail output')
    encoded = json.dumps({'binding_hash': binding_hash, 'text': text},
                         sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    read = PortRead(binding_hash=binding_hash, observation_hash=sha256(encoded).hexdigest())
    normalized = normalize_cli_output(text)
    lines = normalized.splitlines()
    if not lines or not PROMPT_LINE.fullmatch(lines[-1]):
        return read
    query_ids = {int(value) for value in re.findall(r'(?m)^display service-port (0|[1-9][0-9]*)$', normalized)}
    if len(query_ids) != 1 or max(query_ids) > 65535:
        return read
    query_id = next(iter(query_ids))
    preamble = {f'display service-port {query_id}', '{ <cr>||<K> }:', 'Command:'}
    absence = 'Failure: Service virtual port does not exist'
    if absence in lines:
        if all(line in preamble | {absence} for line in lines[:-1]):
            return PortRead(binding_hash, read.observation_hash, 'ABSENT', query_port_id=query_id)
        return read
    blocks = list(re.finditer(r'(?m)^-{10,}\n(Index\s*:.*?)(?=\n-{10,}$)', normalized, re.DOTALL))
    if len(blocks) != 1:
        return read
    block = blocks[0]
    prefix = normalized[:block.start()].splitlines()
    tail = normalize_cli_output(normalized[block.end():]).splitlines()
    notes = {'Note: F--Frame, S--Slot, P--Port', 'v/e--vlan/encap', 'Dvlan--double vlan',
             'pritag--priority-tagged,', 'ppp--pppoe, ip--ipoe, ip4--ipv4oe, ip6--ipv6oe',
             'When the traffic-table is not configured, the system does',
             'not limit the traffic rate and the priority is set to 0'}
    if (any(line not in preamble for line in prefix)
            or any(not re.fullmatch(r'-{10,}', line) and line not in notes
                   for line in tail[:-1])):
        return read
    fields = {}
    for line in block.group(1).splitlines():
        match = re.fullmatch(r'([^:]+?)\s*:\s*(.*?)', line)
        if match is None or match[1].strip() in fields:
            return read
        fields[match[1].strip()] = match[2]
    defaults = {'VLAN attr': 'common', 'Port type': 'gpon', 'Flow type': 'vlan',
        'TX': '-', 'Inbound table name': '-', 'RX': '-', 'Outbound table name': '-',
        'Admin status': 'enable', 'Label': '-', 'Priority': '-', 'PVC bundle': 'no',
        'Max MAC count': '1023', 'Tag transform': 'translate', 'Service-port bundle': '-',
        'Cos': '-', 'Car-Group': '-', 'Static MAC': '', 'IP address': '',
        'Stat. performance': 'disable', 'Subscriber ID': '-'}
    required = set(defaults) | {'Index', 'VLAN ID', 'F/S/P', 'ONT ID', 'GEM port index',
                               'Flow para', 'State', 'Description', 'Remote description'}
    if set(fields) != required or any(fields[key] != value for key, value in defaults.items()):
        return read
    numeric = ('Index', 'VLAN ID', 'ONT ID', 'GEM port index', 'Flow para')
    if any(re.fullmatch(r'(?:0|[1-9][0-9]*)', fields[key]) is None for key in numeric):
        return read
    if int(fields['Index']) != query_id or fields['State'] not in ('up', 'down'):
        return read
    try:
        mapping = ServicePortMapping(olt_binding_hash=binding_hash, fsp=fields['F/S/P'],
            ont_id=int(fields['ONT ID']), vlan=int(fields['VLAN ID']), gemport=int(fields['GEM port index']),
            user_vlan=int(fields['Flow para']), tag_transform='translate', business_type='multi-service')
    except ValueError:
        return read
    return PortRead(binding_hash, read.observation_hash, 'FOUND',
                    (ServicePortDetail(query_id, mapping, fields['State']),), query_port_id=query_id)


def parse_profile_gem(text: str, *, expected_profile_id: int) -> tuple[GemVlanMapping, ...]:
    """Verify the observed GPON ETH/VLAN mapping subset, rejecting partial rows."""
    if type(expected_profile_id) is not int or not 0 <= expected_profile_id <= 4095:
        raise ValueError('Invalid GPON profile ID')
    normalized = normalize_cli_output(text)
    lines = normalized.splitlines()
    if (not lines or not PROMPT_LINE.fullmatch(lines[-1]) or
            len(re.findall(r'(?m)^Binding times\s*:\s*\d+$', normalized)) != 1):
        raise ValueError('Incomplete GPON profile response')
    for key, expected in [('Profile-ID', str(expected_profile_id)), ('Access-type', 'GPON'), ('Mapping mode', 'VLAN')]:
        values = re.findall(r'(?m)^' + re.escape(key) + r'\s*:\s*(.*?)$', normalized)
        if values != [expected]:
            raise ValueError('Unexpected GPON profile mapping')
    queries = {int(value) for value in re.findall(r'(?m)^display ont-lineprofile gpon profile-id (\d+)$', normalized)}
    if queries != {expected_profile_id} or re.search(r'(?im)^(?:Failure:|Error:|%)', normalized):
        raise ValueError('Unconfirmed GPON profile query')
    sections = re.split(r'(?m)^<Gem Index (\d+)>$', normalized)
    mappings, seen_gems = [], set()
    for offset in range(1, len(sections), 2):
        gemport, section = int(sections[offset]), sections[offset + 1]
        if gemport in seen_gems or not 0 <= gemport <= 4095:
            raise ValueError('Ambiguous GEM mapping')
        seen_gems.add(gemport)
        if not re.search(r'\|Serv-Type:ETH\s*\|Encrypt:on\s*\|Cascade:off\s*\|GEM-CAR:-\s*\|', section):
            raise ValueError('Unsupported GEM service type')
        table = re.search(r'Mapping VLAN\s+Priority Port\s+Port\s+Bundle\s+Flow\s+Transparent\n'
            r'index\s+type\s+ID\s+ID\s+CAR\n-{10,}\n(.*?)\n-{10,}', section, re.DOTALL)
        if table is None:
            raise ValueError('Incomplete GEM mapping table')
        indexes, vlans = set(), set()
        for line in table[1].splitlines():
            row = re.fullmatch(r'(\d+)\s+(\d+)(?:\s+-){6}', line)
            if row is None:
                raise ValueError('Unsupported GEM mapping row')
            index, vlan = map(int, row.groups())
            if index in indexes or vlan in vlans or not 1 <= vlan <= 4094:
                raise ValueError('Ambiguous GEM VLAN mapping')
            indexes.add(index)
            vlans.add(vlan)
            mappings.append(GemVlanMapping(expected_profile_id, gemport, vlan))
        if not indexes or indexes != set(range(len(indexes))):
            raise ValueError('Empty or incomplete GEM mapping is unconfirmed')
    if not mappings:
        raise ValueError('No verified GEM mappings')
    known_fields = {'Profile-ID', 'Profile-name', 'Access-type', 'FEC upstream switch',
        'OMCC encrypt switch', 'Qos mode', 'Mapping mode', 'TR069 management', 'TR069 IP index', 'Binding times'}
    field_counts, numeric_rows, table_headers = {}, 0, 0
    notes = {'Notes: Run the display traffic table ip command to query', 'traffic table configuration'}
    for line in lines[:-1]:
        if (line in {f'display ont-lineprofile gpon profile-id {expected_profile_id}', '{ <cr>||<K> }:', 'Command:'}
                or line in notes or re.fullmatch(r'-{10,}', line)
                or re.fullmatch(r'<T-CONT\s+\d+>\s+DBA Profile-ID:\d+', line)
                or re.fullmatch(r'<Gem Index \d+>', line)):
            continue
        if re.fullmatch(r'Mapping VLAN\s+Priority Port\s+Port\s+Bundle\s+Flow\s+Transparent', line):
            table_headers += 1
            continue
        if (re.fullmatch(r'index\s+type\s+ID\s+ID\s+CAR', line)
                or re.fullmatch(r'\|Serv-Type:ETH\s*\|Encrypt:on\s*\|Cascade:off\s*\|GEM-CAR:-\s*\|', line)
                or re.fullmatch(r'\|Upstream-priority-queue:0\s*\|Downstream-priority-queue:-\s*\|', line)):
            continue
        if re.fullmatch(r'\d+\s+\d+(?:\s+-){6}', line):
            numeric_rows += 1
            continue
        field = re.fullmatch(r'([^:]+?)\s*:\s*(.+)', line)
        if field and field[1].strip() in known_fields:
            key = field[1].strip()
            field_counts[key] = field_counts.get(key, 0) + 1
            continue
        raise ValueError('Unrecognized GPON profile content')
    if (set(field_counts) != known_fields or any(count != 1 for count in field_counts.values())
            or numeric_rows != len(mappings) or table_headers != len(seen_gems)):
        raise ValueError('Incomplete or ambiguous GPON profile structure')
    return tuple(mappings)


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

