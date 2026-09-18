import json

import pytest

from app.models.test_intelligence import TestSkill
from app.skill_catalog.onu_registration_dual_wan import CATALOG
from app.skill_catalog.repository import SkillCatalogRepository
from app.skill_catalog.service import (
    CatalogVersionConflictError,
    SkillCatalogService,
)


def build_catalog_service(db_session) -> SkillCatalogService:
    return SkillCatalogService(SkillCatalogRepository(db_session))


def test_catalog_definition_covers_approved_modes_and_evidence() -> None:
    parameter_defaults = {
        parameter.key: parameter.default for parameter in CATALOG.parameters
    }
    assert CATALOG.skill_code == "ONU_REGISTRATION_DUAL_WAN_CONNECTIVITY"
    assert CATALOG.version == "1.0.0"
    assert CATALOG.status == "DRAFT"
    assert CATALOG.supported_olts == ("Huawei MA5800-X7",)
    assert parameter_defaults["execution_mode"] == "SEQUENTIAL_ISOLATED"
    assert parameter_defaults["evaluation_policy"] == "STRICT_PER_WAN"
    assert parameter_defaults["end_policy"] == "RESTORE"
    assert {"SEQUENTIAL_ISOLATED", "CONCURRENT_DUAL_WAN"} <= set(
        next(p for p in CATALOG.parameters if p.key == "execution_mode").constraints[
            "choices"
        ]
    )
    assert {"STRICT_PER_WAN", "CUSTOMER_SIMPLIFIED"} <= set(
        next(p for p in CATALOG.parameters if p.key == "evaluation_policy").constraints[
            "choices"
        ]
    )
    assert {"RESTORE", "KEEP"} <= set(
        next(p for p in CATALOG.parameters if p.key == "end_policy").constraints[
            "choices"
        ]
    )
    assert tuple(item.code for item in CATALOG.evidence) == (
        "E1_OLT_AUTOFIND",
        "E2_REGISTRATION",
        "E3_IPOE_ADDRESS",
        "E4_IPOE_PING",
        "E5_PPPOE_ADDRESS",
        "E6_PPPOE_PING",
    )

    serialized = json.dumps(CATALOG.to_dict(), ensure_ascii=False).lower()
    for forbidden in ("password", "secret", "192.168.", "10.0.", "username"):
        assert forbidden not in serialized


def test_catalog_install_is_idempotent(db_session) -> None:
    service = build_catalog_service(db_session)
    first = service.install_onu_registration_dual_wan_draft()
    second = service.install_onu_registration_dual_wan_draft()

    assert first.skill_id == second.skill_id
    assert first.created is True
    assert second.created is False
    assert second.evidence_codes == (
        "E1_OLT_AUTOFIND",
        "E2_REGISTRATION",
        "E3_IPOE_ADDRESS",
        "E4_IPOE_PING",
        "E5_PPPOE_ADDRESS",
        "E6_PPPOE_PING",
    )
    detail = service.get(first.skill_id)
    assert detail["status"] == "DRAFT"
    assert detail["standard"]["status"] == "DRAFT"
    assert detail["standard_profile"]["status"] == "DRAFT"
    assert detail["runner_statuses"] == ["DEVELOPMENT"]
    assert len(detail["evidence_rules"]) == 6


def test_catalog_install_rejects_same_version_with_unknown_definition(db_session) -> None:
    db_session.add(
        TestSkill(
            skill_code=CATALOG.skill_code,
            version=CATALOG.version,
            spec_version="1.0",
            name="Conflicting definition",
            objective="Must not be overwritten.",
            status="DRAFT",
            applicable_devices=[],
            preconditions=[],
            environment_requirements=[],
            validation_methods=[],
            outputs=[],
            tags=[],
        )
    )
    db_session.commit()

    with pytest.raises(CatalogVersionConflictError):
        build_catalog_service(db_session).install_onu_registration_dual_wan_draft()

