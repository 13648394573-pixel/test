import pytest

from app.local_runner.ma5800.actions import MA5800Actions
from app.local_runner.ma5800.transport import CommandTranscript
from test_ma5800_actions import context, observation, transcript


class PortExecutor:
    def __init__(self, rows):
        self.rows = rows
        self.commands = []

    def run(self, command):
        self.commands.append(command.action_code)
        if command.action_code == 'display_ont_port':
            output = self.rows + '\nMA5800-X7(config-if-gpon-0/2)#'
        elif command.action_code == 'display_ont_by_sn':
            output = 'Failure: The ONT does not exist\nMA5800-X7#'
        elif command.action_code == 'display_autofind':
            return transcript(command.action_code, 'autofind.txt')
        else:
            output = 'Command executed successfully\nMA5800-X7#'
        return CommandTranscript(command.action_code, output, output, 'MA5800-X7#', 'a' * 64)


@pytest.mark.parametrize('fsp', ['0/2/10', '0/ 2/10', '0 / 2 / 10', '0/\t2/10'])
def test_free_id_counts_spaced_target_rows_and_ignores_neighbor_port(fsp):
    executor = PortExecutor(
        f'{fsp} 0 48575443DD91BBBB active offline initial initial no\n'
        f'{fsp} 1 4857544311223344 active online normal match no\n'
        f'{fsp} 36 4857544355667788 active offline initial initial no\n'
        '0/2/100 2 4857544399AABBCC active online normal match no')
    outcome = MA5800Actions(executor).find_free_ont_id(context('find_free_ont_id'))
    assert outcome.status == 'PASS'
    assert observation(outcome, 'olt.free_ont_id') == 2
    assert executor.commands == ['display_ont_port']


@pytest.mark.parametrize('fsp', ['0/2/10', '0/ 2/10', '0 / 2 / 10'])
def test_registration_blocks_occupied_id_with_spaced_port(fsp):
    executor = PortExecutor(f'{fsp} 36 4857544311223344 active offline initial initial no')
    actions = MA5800Actions(executor)
    preview = observation(actions.register_ont(context('register_ont')), 'mutation.preview')
    outcome = actions.register_ont(context('register_ont', mutation_approval={
        'approved': True, 'preview_hash': preview['preview_hash']}))
    assert outcome.status == 'BLOCKED'
    assert outcome.error_code == 'OLT_ONT_ID_IN_USE'
    assert executor.commands == ['display_ont_by_sn', 'display_ont_port']


def test_free_id_rejects_neighbor_port_only_table():
    executor = PortExecutor('0/ 2/100 0 48575443DD91BBBB active offline initial initial no')
    outcome = MA5800Actions(executor).find_free_ont_id(context('find_free_ont_id'))
    assert outcome.status == 'BLOCKED'
    assert outcome.error_code == 'OLT_PORT_READ_UNRECOGNIZED'


def test_free_id_never_reuses_occupied_id_on_full_spaced_port():
    rows = '\n'.join(f'0/ 2/10 {i} 48575443DD91BBBB active offline initial initial no' for i in range(128))
    outcome = MA5800Actions(PortExecutor(rows)).find_free_ont_id(context('find_free_ont_id'))
    assert outcome.status == 'BLOCKED'
    assert outcome.error_code == 'NO_FREE_ONT_ID'
