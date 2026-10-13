"""Incomplete/unverified protocol must never authorize resource ownership."""
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.local_runner.ma5800 import parsers


def detail(text, binding_hash='a' * 64):
    parse = getattr(parsers, 'parse_service_port_detail', None)
    assert callable(parse), 'Missing fail-closed service-port detail boundary'
    return parse(text, binding_hash=binding_hash)


@pytest.mark.parametrize('text', [
    '288 1000 0/2/9 14 1 1000\nMA5800-X7#',
    'Switch-Oriented Flow List\n288 1000 common gpon 0/2 /9 14 1 vlan 1000 - - up\nTotal : 1',
    'Total : 0\nMA5800-X7#',
    'Command executed successfully',
    '',
])
def test_partial_or_unverified_detail_is_unconfirmed(text):
    read = detail(text)
    assert read.status == 'UNCONFIRMED'
    assert read.items == ()
    assert read.evidence_ids == ()


def test_observation_hash_binds_source_and_target_without_retaining_raw_output():
    read = detail('unverified output')
    assert len(read.observation_hash) == 64
    assert read.observation_hash == detail('unverified output').observation_hash
    assert read.observation_hash != detail('different output').observation_hash
    assert read.observation_hash != detail('unverified output', 'b' * 64).observation_hash
    assert 'unverified output' not in repr(read)


@pytest.mark.parametrize('binding_hash', ['', 'a' * 63, 'g' * 64, None, True])
def test_invalid_binding_hash_cannot_identify_a_read(binding_hash):
    with pytest.raises(ValueError):
        detail('unverified', binding_hash)


def test_unconfirmed_read_cannot_be_relabelled_as_verified():
    read = detail('unverified')
    with pytest.raises((FrozenInstanceError, ValueError)):
        read.status = 'FOUND'


FIXTURES = Path(__file__).parent / 'fixtures' / 'ma5800'


def full_detail():
    return (FIXTURES / 'service_port_detail.txt').read_text(encoding='utf-8')


def test_verified_full_detail_preserves_complete_mapping_and_query_scope():
    read = detail(full_detail())
    assert read.status == 'FOUND' and read.query_port_id == 51
    item = read.items[0]
    assert item.port_id == 51
    assert item.mapping.fsp == '0/1/2' and item.mapping.ont_id == 7
    assert (item.mapping.vlan, item.mapping.gemport, item.mapping.user_vlan) == (1000, 1, 1000)
    assert item.mapping.tag_transform == 'translate' and item.mapping.business_type == 'multi-service'


def test_other_ont_global_id_is_found_not_free():
    read = detail(full_detail().replace('ONT ID              : 7', 'ONT ID              : 8'))
    assert read.status == 'FOUND' and read.items[0].mapping.ont_id == 8


def test_absent_requires_exact_scoped_query_response_not_generic_failure():
    text = 'display service-port 53\n{ <cr>||<K> }:\nCommand:\ndisplay service-port 53\nFailure: Service virtual port does not exist\nMA5800-X7(config)#'
    read = detail(text)
    assert read.status == 'ABSENT' and read.query_port_id == 53 and read.items == ()
    assert detail('Failure: Service virtual port does not exist').status == 'UNCONFIRMED'


@pytest.mark.parametrize('old,new', [('Tag transform       : translate', 'Tag transform       : transparent'),
    ('Flow type           : vlan', 'Flow type           : ppp'),
    ('Index               : 51', 'Index               : 52'),
    ('F/S/P               : 0/1/2', 'F/S/P               : 00/1/2'),
    ('TX                  : -', 'TX                  : 10'),
    ('Inbound table name  : -', 'Inbound table name  : custom'),
    ('Tag transform       : translate', ''),
    ('Index               : 51', 'Index               : 51\nIndex : 99'),
    ('MA5800-X7(config)#', '')])
def test_conflicting_incomplete_or_unsupported_details_never_authorize_mapping(old, new):
    assert detail(full_detail().replace(old, new)).status == 'UNCONFIRMED'


def test_profile_gem_parser_confirms_eth_vlan_mapping():
    parse = getattr(parsers, 'parse_profile_gem', None)
    assert callable(parse), 'Missing verified Profile/GEM parser'
    mappings = parse((FIXTURES / 'profile_gem.txt').read_text(), expected_profile_id=10)
    assert [(item.gemport, item.vlan) for item in mappings] == [
        (1, 199), (1, 200), (1, 300), (1, 1000), (1, 6), (1, 10), (1, 100), (1, 2020)]


@pytest.mark.parametrize('old,new', [('Profile-ID          :10', 'Profile-ID          :11'),
    ('Mapping mode        :VLAN', 'Mapping mode        :PORT'),
    ('Serv-Type:ETH', 'Serv-Type:TDM'), ('1000  -', '1000  5'),
    ('Binding times       :85', ''), ('MA5800-X7(config)#', '')])
def test_partial_or_unsupported_profile_is_rejected(old, new):
    parse = getattr(parsers, 'parse_profile_gem', None)
    assert callable(parse), 'Missing verified Profile/GEM parser'
    with pytest.raises(ValueError):
        parse((FIXTURES / 'profile_gem.txt').read_text().replace(old, new), expected_profile_id=10)


@pytest.mark.parametrize('old,new', [
    ('Binding times       :85', '999 malformed mapping row\nBinding times       :85'),
    ('Profile-name        :Fixture GPON', 'Profile-name        :Fixture GPON\nUnexpected-profile-option : enabled'),
    ('3       1000  -        -       -     -       -     -\n', ''),
    ('|Upstream-priority-queue:0', '|Upstream-priority-queue:9'),
])
def test_unrecognized_profile_structure_and_mapping_gaps_are_not_ignored(old, new):
    with pytest.raises(ValueError):
        parsers.parse_profile_gem((FIXTURES / 'profile_gem.txt').read_text().replace(old, new), expected_profile_id=10)
