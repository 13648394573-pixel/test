import pytest
from app.skill_execution.evaluator import evaluate


RULES = [{'code': 'ONLINE', 'fact_key': 'onu.ready', 'operator': 'EQ', 'expected': True, 'required': True}]
EVIDENCE = [{'rule_code': 'E3', 'min_count': 2, 'capture_methods': ['OLT_RENDER', 'ONU_WEB']}]


def evidence(method, token):
    return dict(id=token, rule_code='E3', capture_method=method, category='SCREENSHOT', redacted=True, hash_valid=True)


def test_pass_requires_distinct_valid_sources():
    verdict = evaluate({'onu.ready': True}, RULES, EVIDENCE, [evidence('OLT_RENDER', 'a'), evidence('ONU_WEB', 'b')])
    assert verdict.overall_result == 'PASS'
    assert verdict.evidence_complete is True


@pytest.mark.parametrize('items', [[], [evidence('OLT_RENDER','a'), evidence('OLT_RENDER','b')],
    [evidence('OLT_RENDER','a'), evidence('ONU_WEB','a')],
    [evidence('OLT_RENDER','a'), {**evidence('ONU_WEB','b'), 'hash_valid': False}],
    [evidence('OLT_RENDER','a'), {**evidence('ONU_WEB','b'), 'redacted': False}],
])
def test_missing_tampered_or_duplicate_evidence_cannot_pass(items):
    verdict = evaluate({'onu.ready': True}, RULES, EVIDENCE, items)
    assert verdict.functional_verdict == 'PASS'
    assert verdict.overall_result == 'BLOCKED'


def test_fail_remains_functional_fail_when_evidence_incomplete():
    verdict = evaluate({'onu.ready': False}, RULES, EVIDENCE, [])
    assert verdict.functional_verdict == 'FAIL'
    assert verdict.overall_result == 'BLOCKED'


def test_missing_prerequisite_is_blocked_not_fail():
    assert evaluate({}, RULES, [], []).functional_verdict == 'BLOCKED'


def test_early_failure_is_not_erased_by_missing_downstream_facts():
    rules = RULES + [dict(code='WAN', fact_key='wan.ready', operator='EQ', expected=True, required=True)]
    verdict = evaluate({'onu.ready': False}, rules, EVIDENCE, [])
    assert verdict.functional_verdict == 'FAIL'
    assert verdict.overall_result == 'BLOCKED'
    assert evaluate({'onu.ready': False}, rules, [], [], blocked=True).functional_verdict == 'BLOCKED'


def test_snapshot_threshold_drives_verdict():
    rules = [{'code':'PING','fact_key':'latency','operator':'LT','expected':100,'required':True}]
    assert evaluate({'latency': 101}, rules, [], []).overall_result == 'FAIL'
    rules[0]['expected'] = 200
    assert evaluate({'latency': 101}, rules, [], []).overall_result == 'PASS'
