from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.test_intelligence import (
    SkillEvidenceRule,
    SkillExecutionRule,
    SkillParameter,
    SkillStep,
    TestSkill,
)


def make_skill(**overrides) -> TestSkill:
    values = {
        "skill_code": "ONU-VLAN-PORT-BINDING",
        "version": "1.0.0",
        "spec_version": "1.0",
        "name": "VLAN port binding",
        "objective": "Verify LAN port binding to the configured service VLAN.",
        "status": "DRAFT",
        "applicable_devices": [],
        "preconditions": [],
        "environment_requirements": [],
        "validation_methods": [],
        "outputs": [],
        "tags": ["VLAN"],
    }
    values.update(overrides)
    return TestSkill(**values)


def test_skill_semantic_identity_is_unique(db_session) -> None:
    db_session.add_all([make_skill(), make_skill(name="Duplicate")])

    with pytest.raises(IntegrityError):
        db_session.commit()


@pytest.mark.parametrize(
    ("status", "published_at"),
    [("DRAFT", datetime.now(UTC).replace(tzinfo=None)), ("PUBLISHED", None)],
)
def test_skill_publication_timestamp_matches_status(
    db_session,
    status,
    published_at,
) -> None:
    db_session.add(make_skill(status=status, published_at=published_at))

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_sensitive_skill_parameter_cannot_have_default(db_session) -> None:
    skill = make_skill()
    skill.parameters.append(
        SkillParameter(
            param_key="olt_password",
            label="OLT password",
            data_type="STRING",
            source="RUN",
            required=True,
            default_value="secret",
            constraints_json={},
            sensitive=True,
            display_order=1,
        )
    )
    db_session.add(skill)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_skill_parameter_display_order_is_unique(db_session) -> None:
    skill = make_skill()
    skill.parameters.extend(
        [
            SkillParameter(
                param_key="vlan_id",
                label="VLAN ID",
                data_type="INTEGER",
                source="CASE",
                required=True,
                constraints_json={},
                sensitive=False,
                display_order=1,
            ),
            SkillParameter(
                param_key="lan_port",
                label="LAN port",
                data_type="STRING",
                source="DEVICE",
                required=True,
                constraints_json={},
                sensitive=False,
                display_order=1,
            ),
        ]
    )
    db_session.add(skill)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_skill_step_rejects_unknown_execution_mode(db_session) -> None:
    skill = make_skill()
    skill.steps.append(
        SkillStep(
            step_no=1,
            title="Configure VLAN",
            action="Configure ${vlan_id}.",
            expected_observation="Configuration is accepted.",
            execution_mode="SHELL",
            required=True,
            evidence_rule_refs=[],
        )
    )
    db_session.add(skill)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_standard_rule_requires_standard_binding(db_session) -> None:
    skill = make_skill()
    skill.execution_rules.append(
        SkillExecutionRule(
            rule_code="STD-VLAN-MATCH",
            result_type="PASS",
            fact_key="observed_vlan",
            operator="EQ",
            required=True,
            priority=1,
            message="Observed VLAN matches the selected standard.",
            evaluation_source="STANDARD",
        )
    )
    db_session.add(skill)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_execution_rule_rejects_unrestricted_operator(db_session) -> None:
    skill = make_skill()
    skill.execution_rules.append(
        SkillExecutionRule(
            rule_code="UNSAFE",
            result_type="FAIL",
            fact_key="observed_vlan",
            operator="PYTHON",
            expected_value=100,
            required=True,
            priority=1,
            message="Unsafe operator must be rejected.",
            evaluation_source="FIXED",
        )
    )
    db_session.add(skill)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_evidence_rule_rejects_maximum_below_minimum(db_session) -> None:
    skill = make_skill()
    skill.evidence_rules.append(
        SkillEvidenceRule(
            rule_code="VLAN-SCREENSHOT",
            category="SCREENSHOT",
            title="VLAN result",
            required_for=["PASS", "FAIL"],
            min_count=2,
            max_count=1,
            description="Capture the configured and observed VLAN.",
            sensitive_content="REDACT",
            display_order=1,
        )
    )
    db_session.add(skill)

    with pytest.raises(IntegrityError):
        db_session.commit()
