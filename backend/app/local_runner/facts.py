"""Pure conversion of sourced observations into the existing standard facts."""
from ipaddress import ip_address
from math import isfinite
from typing import Mapping, Sequence

from .contracts import Observation


def _number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return number if isfinite(number) else None


def _address(value):
    try:
        address = ip_address(value)
    except (ValueError, TypeError):
        return None
    return None if (address.is_unspecified or address.is_loopback or address.is_multicast
                    or address.is_link_local) else address


def recent_history(history):
    """A newer provisioning attempt invalidates all observations from the old epoch."""
    boundary = None
    for index, event in enumerate(history):
        ref = event.payload_json.get('ref', '')
        if event.event_type in {'ACTION_STARTED', 'ACTION_OUTCOME'} and (
            ref.startswith('PROVISION_') or ref.startswith('REMOVE_')):
            boundary = index
    return list(history[boundary:]) if boundary is not None else []


def historical_observations(history, ref, source):
    for event in reversed(history):
        if event.event_type == 'ACTION_OUTCOME' and event.payload_json.get('ref') == ref:
            if event.payload_json.get('status') != 'PASS':
                return {}
            return {o['fact_key']: o.get('value') for o in event.payload_json.get('observations', [])
                    if o.get('source') == source}
    return {}


def _ping_pass(data, prefix):
    numbers = [_number(data.get(prefix + key)) for key in ('packets_sent', 'packets_received', 'loss_percent')]
    if any(value is None for value in numbers):
        return None
    sent, received, loss = numbers
    if sent <= 0 or not sent.is_integer() or not received.is_integer() or not 0 <= received <= sent or not 0 <= loss <= 100:
        return None
    return sent == received and loss == 0


def derive_standard_facts(action: str, parameters: Mapping, observations: Sequence[Observation],
                          history: Sequence) -> tuple[Observation, ...]:
    result = []
    olt = {o.fact_key: o.value for o in observations if o.source == 'MA5800'}
    web = {o.fact_key: o.value for o in observations if o.source == 'ONU_WEB'}
    pc = {o.fact_key: o.value for o in observations if o.source == 'PC_PROBE'}
    fsp = '/'.join(str(parameters.get(key)) for key in ('frame', 'slot', 'pon_port'))
    serial = str(parameters.get('onu_serial_number', '')).upper()
    def add(key, value, source):
        result.append(Observation(key, value, source))
    if action == 'discover_onts' and isinstance(olt.get('olt.autofind.items'), list):
        add('olt.autofind.matched', any(
            isinstance(item, dict) and item.get('fsp') == fsp
            and str(item.get('serial_number', '')).upper() == serial
            for item in olt['olt.autofind.items']), 'MA5800')
    if action == 'snapshot_ont':
        snapshot = olt.get('olt.configuration_snapshot')
        registration = snapshot.get('registration') if isinstance(snapshot, dict) else None
        required = ('fsp', 'serial_number', 'ont_id', 'line_profile_id', 'service_profile_id', 'run_state', 'match_state')
        if isinstance(registration, dict) and all(registration.get(key) is not None for key in required):
            add('olt.registration.ready', (
                registration['fsp'] == fsp and str(registration['serial_number']).upper() == serial
                and all(type(registration[key]) is int and registration[key] == parameters.get(key)
                        for key in ('ont_id', 'line_profile_id', 'service_profile_id'))
                and str(registration['run_state']).lower() == 'online'
                and str(registration['match_state']).lower() == 'match'), 'MA5800')
    mode = parameters.get('wan_mode')
    if mode not in {'IPOE', 'PPPOE'}:
        return tuple(result)
    prefix = mode.lower()
    recent = recent_history(history)
    if action == 'capture_onu_wan':
        prior = historical_observations(recent, mode + '_ADDRESS_OLT', 'MA5800')
        items = prior.get('olt.wan.items')
        required = [prefix + '.' + key for key in ('status', 'vlan', 'ip_address')]
        if isinstance(items, list) and all(key in web for key in required):
            candidates = [item for item in items if isinstance(item, dict)
                          and item.get('mode') == mode
                          and item.get('ip_index') == parameters.get(prefix + '_ip_index')]
            if len(candidates) == 1:
                item = candidates[0]
                if not all(key in item for key in ('status', 'vlan', 'ip_address')):
                    return tuple(result)
                address = _address(web[prefix + '.ip_address'])
                valid = (
                    address is not None and address == _address(item['ip_address'])
                    and item['vlan'] == web[prefix + '.vlan'] == parameters.get(prefix + '_vlan')
                    and str(item['status']).upper() in {'CONNECTED', 'UP', 'ONLINE'}
                    and str(web[prefix + '.status']).upper() in {'CONNECTED', 'UP', 'ONLINE'}
                    and web.get(prefix + '.protocol', mode).upper() == mode)
            else:
                valid = False
            add(prefix + '.address.valid', valid, 'ONU_WEB')
    if action == 'run_onu_ping':
        for key in ('packets_sent', 'packets_received', 'loss_percent', 'latency_avg_ms'):
            full = prefix + '.ping.' + key
            number = _number(web.get(full))
            if number is not None and number >= 0:
                add(full, number, 'ONU_WEB')
    if action == 'pc_connectivity_probe' and pc.get('pc.wan.attributed') is True:
        prior = historical_observations(recent, mode + '_PING_ONU', 'ONU_WEB')
        onu_pass = _ping_pass(prior, prefix + '.ping.')
        pc_pass = _ping_pass(pc, 'pc.ping.')
        if onu_pass is not None and pc_pass is not None:
            add(prefix + '.internet.pass', onu_pass and pc_pass, 'PC_PROBE')
    return tuple(result)
