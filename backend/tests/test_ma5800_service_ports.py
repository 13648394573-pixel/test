import pytest

from app.local_runner.ma5800.parsers import parse_service_ports
from app.local_runner.ma5800.actions import MA5800Actions
from app.local_runner.ma5800.transport import CommandTranscript
from test_ma5800_actions import FakeExecutor, context, observation


HEADER = 'Switch-Oriented Flow List\nINDEX VLAN VLAN PORT F/ S/ P VPI VCI FLOW FLOW RX TX STATE\nID ATTR TYPE TYPE PARA\n'
ROW = '288 1000 common gpon 0/2 /10 36 1 vlan 1000 - - up'


def table(row=ROW, total=1):
    return HEADER + row + f'\nTotal : {total} (Up/Down : 1/0)\nMA5800-X7(config)#'


def test_full_huawei_table_preserves_all_service_port_identity_fields():
    ports = parse_service_ports(table())
    assert [(p.service_port_id, p.vlan, p.fsp, p.ont_id, p.gemport, p.user_vlan) for p in ports] == [
        (288, 1000, '0/2/10', 36, 1, 1000)]


def test_compact_service_port_format_remains_supported():
    ports = parse_service_ports('21 1000 0/2/10 36 1 1000\nMA5800-X7#')
    assert [(p.service_port_id, p.fsp, p.ont_id) for p in ports] == [(21, '0/2/10', 36)]


def test_only_explicit_zero_total_is_an_empty_service_port_table():
    assert parse_service_ports(HEADER + 'Total : 0\nMA5800-X7#') == ()


@pytest.mark.parametrize('output', [
    'Command executed successfully\nMA5800-X7#',
    HEADER + 'unknown nonempty service row\nTotal : 0\nMA5800-X7#',
    HEADER + 'Total : 0.5\nMA5800-X7#',
    HEADER + 'Total : 0 garbage\nMA5800-X7#',
    'INDEX VLAN PORT F/ S/ P VPI VCI\nunknown nonempty service row\nTotal : 0\nMA5800-X7#',
    HEADER + 'Total : 0\nunknown nonempty service row\nMA5800-X7#',
    HEADER + 'Total : 1\nMA5800-X7#',
    HEADER + ROW + '\nMA5800-X7#',
    'Failure: Query failed\nTotal : 0\nMA5800-X7#',
    table(ROW.replace('vlan 1000', 'unknown 1000')),
    table(ROW + '\n289 unexpected columns', total=2),
    table(ROW, total=2),
    table(ROW, total=0),
    table(ROW + '\n' + ROW, total=2),
])
def test_unrecognized_partial_or_inconsistent_tables_never_silently_become_empty(output):
    with pytest.raises(ValueError):
        parse_service_ports(output)


class ServicePortExecutor(FakeExecutor):
    def __init__(self, output):
        super().__init__()
        self.output = output

    def run(self, command):
        result = super().run(command)
        if command.action_code == 'display_service_ports':
            return CommandTranscript(command.action_code, self.output, self.output, 'MA5800-X7#', 'b' * 64)
        return result


def test_snapshot_includes_real_table_service_port_instead_of_empty_scope():
    outcome = MA5800Actions(ServicePortExecutor(table())).snapshot_ont(context('snapshot_ont'))
    assert outcome.status == 'PASS'
    assert observation(outcome, 'olt.configuration_snapshot')['service_ports'] == [dict(
        service_port_id=288, vlan=1000, fsp='0/2/10', ont_id=36, gemport=1, user_vlan=1000)]


@pytest.mark.parametrize('output', [table('', total=1), table(ROW.replace('0/2 /10', '0/2 /100')),
    table(ROW.replace(' 36 1 ', ' 37 1 '))])
def test_snapshot_refuses_incomplete_or_wrong_target_service_port_scope(output):
    outcome = MA5800Actions(ServicePortExecutor(output)).snapshot_ont(context('snapshot_ont'))
    assert outcome.status == 'BLOCKED'
    assert outcome.error_code == 'OLT_SERVICE_PORT_READ_UNRECOGNIZED'
    assert not any(o.fact_key == 'olt.configuration_snapshot' for o in outcome.observations)


@pytest.mark.parametrize('output,expected', [
    (table(), 'PASS'),
    (table(ROW.replace('0/2 /10', '0/2 /100')), 'BLOCKED'),
    (table(ROW.replace(' 36 1 ', ' 37 1 ')), 'BLOCKED'),
    (table('', total=1), 'BLOCKED'),
])
def test_approved_mutation_still_requires_confirmed_service_port_ownership(output, expected):
    executor = ServicePortExecutor(output)
    actions = MA5800Actions(executor)
    first = actions.delete_ont(context('delete_ont', affected_service_ports=[288]))
    assert first.status == 'WAITING_OPERATOR' and not executor.commands
    preview = observation(first, 'mutation.preview')
    outcome = actions.delete_ont(context('delete_ont', affected_service_ports=[288],
        mutation_approval={'approved': True, 'preview_hash': preview['preview_hash']}))
    assert outcome.status == expected
    if expected == 'BLOCKED':
        assert outcome.error_code == 'OLT_SERVICE_PORT_OWNERSHIP_UNCONFIRMED'
        assert [c.action_code for c in executor.commands] == ['display_ont_by_sn', 'display_service_ports']
    else:
        assert [c.action_code for c in executor.commands] == ['display_ont_by_sn', 'display_service_ports', 'delete_ont']
