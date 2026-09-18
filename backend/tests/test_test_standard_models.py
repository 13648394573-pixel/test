from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.test_execution import TestProject
from app.models.test_standard import (
    ProjectStandardProfile,
    StandardProfile,
    StandardProfileItem,
    StandardRequirement,
    TestStandard,
)


def make_standard(**overrides) -> TestStandard:
    values = {
        "standard_code": "INTERNAL-VLAN",
        "version": "1.0",
        "title": "VLAN conformance",
        "source_type": "INTERNAL",
        "issuer": "UNPON",
        "language_code": "en-US",
        "status": "DRAFT",
        "source_reference": "STD-VLAN-001",
    }
    values.update(overrides)
    return TestStandard(**values)


def make_profile(**overrides) -> StandardProfile:
    values = {
        "profile_code": "EU-CUSTOMER-A",
        "version": 1,
        "name": "EU Customer A GPON",
        "merge_policy": "ALL_MANDATORY_MUST_PASS",
        "status": "DRAFT",
    }
    values.update(overrides)
    return StandardProfile(**values)


def test_standard_version_is_unique(db_session) -> None:
    db_session.add_all([make_standard(), make_standard(title="Duplicate")])

    with pytest.raises(IntegrityError):
        db_session.commit()


@pytest.mark.parametrize(
    ("status", "published_at"),
    [("DRAFT", datetime.now(UTC).replace(tzinfo=None)), ("PUBLISHED", None)],
)
def test_standard_publication_timestamp_matches_status(
    db_session,
    status,
    published_at,
) -> None:
    db_session.add(make_standard(status=status, published_at=published_at))

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_requirement_codes_and_order_are_unique_per_standard(db_session) -> None:
    standard = make_standard()
    standard.requirements.extend(
        [
            StandardRequirement(
                requirement_code="VLAN-1",
                title="Tagged forwarding",
                description="Forward tagged frames on the bound service.",
                requirement_level="MANDATORY",
                applicability={},
                data_type="BOOLEAN",
                operator="EQ",
                expected_value=True,
                source_text_reference="Clause 4.1",
                display_order=1,
            ),
            StandardRequirement(
                requirement_code="VLAN-2",
                title="Duplicate order",
                description="Must not share an order.",
                requirement_level="RECOMMENDED",
                applicability={},
                data_type="BOOLEAN",
                operator="EQ",
                expected_value=True,
                source_text_reference="Clause 4.2",
                display_order=1,
            ),
        ]
    )
    db_session.add(standard)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_profile_item_order_is_unique_and_standard_delete_is_restricted(
    db_session,
) -> None:
    first = make_standard(standard_code="STD-A")
    second = make_standard(standard_code="STD-B")
    profile = make_profile()
    profile.items.extend(
        [
            StandardProfileItem(standard=first, required=True, display_order=1),
            StandardProfileItem(standard=second, required=True, display_order=2),
        ]
    )
    db_session.add(profile)
    db_session.commit()

    db_session.delete(first)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_project_can_select_only_one_standard_profile(db_session) -> None:
    project = TestProject(name="Release", version="V2")
    first = make_profile(profile_code="PROFILE-A")
    second = make_profile(profile_code="PROFILE-B")
    db_session.add_all([project, first, second])
    db_session.flush()
    db_session.add_all(
        [
            ProjectStandardProfile(
                project_id=project.id,
                standard_profile_id=first.id,
            ),
            ProjectStandardProfile(
                project_id=project.id,
                standard_profile_id=second.id,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
