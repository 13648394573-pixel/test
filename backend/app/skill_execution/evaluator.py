from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EvaluationResult:
    functional_verdict: str
    evidence_complete: bool
    overall_result: str
    matched_rule_codes: tuple[str, ...]
    evaluations: tuple[dict[str, Any], ...]
    missing_evidence: tuple[str, ...]


def evaluate(facts, rules, evidence_rules, evidence, *, blocked=False) -> EvaluationResult:
    evaluations = []
    missing = False
    failed = False
    for rule in rules:
        value = facts.get(rule['fact_key'])
        expected = rule['expected']
        operator = rule['operator']
        if value is None:
            verdict = 'BLOCKED'
        else:
            try:
                if operator == 'EQ':
                    matches = type(value) is type(expected) and value == expected
                elif operator in {'LT', 'LTE', 'GT', 'GTE'}:
                    if isinstance(value, bool) or not isinstance(value, (int, float)):
                        raise ValueError('Numeric observation required')
                    matches = {'LT': value < expected, 'LTE': value <= expected,
                               'GT': value > expected, 'GTE': value >= expected}[operator]
                elif operator == 'IN':
                    matches = value in expected
                else:
                    raise ValueError('Unsupported standard operator')
                verdict = 'PASS' if matches else 'FAIL'
            except (ValueError, TypeError):
                verdict = 'BLOCKED'
        evaluations.append({'code': rule['code'], 'fact_key': rule['fact_key'],
                            'expected': expected, 'observed': value, 'verdict': verdict})
        if rule.get('required', True):
            missing |= verdict == 'BLOCKED'
            failed |= verdict == 'FAIL'
    functional = ('BLOCKED' if blocked or not rules else 'FAIL' if failed
                  else 'BLOCKED' if missing else 'PASS')
    incomplete = []
    for rule in evidence_rules:
        items = {item['id']: item for item in evidence if
                 item.get('rule_code') == rule['rule_code'] and item.get('hash_valid') is True
                 and item.get('redacted') is True and item.get('category') == 'SCREENSHOT'}
        methods = {item.get('capture_method') for item in items.values()}
        required_methods = set(rule.get('capture_methods', []))
        if 'OPERATOR' in required_methods:
            required_methods.discard('OPERATOR')
            if 'OPERATOR' in methods:
                required_methods.discard('PC_PROBE')
        if len(items) < rule['min_count'] or not required_methods <= methods:
            incomplete.append(rule['rule_code'])
    complete = not incomplete
    return EvaluationResult(functional, complete, functional if complete else 'BLOCKED',
                            tuple(item['code'] for item in evaluations if item['verdict'] == 'PASS'),
                            tuple(evaluations), tuple(incomplete))
