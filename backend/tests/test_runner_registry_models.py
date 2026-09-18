from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.runner_registry import RunnerAction, RunnerPlugin, SkillRunnerBinding
from app.models.test_intelligence import TestSkill


def make_plugin(**overrides) -> RunnerPlugin:
    values = {
        "plugin_code": "ONU-VLAN",
        "version": "1.0.0",
        "status": "DEVELOPMENT",
        "manifest_json": {"platform": "windows"},
        "package_sha256": "a" * 64,
        "install_path_ref": "plugins/onu-vlan/1.0.0",
    }
    values.update(overrides)
    return RunnerPlugin(**values)


def make_skill() -> TestSkill:
    return TestSkill(
        skill_code="ONU-VLAN",
        version="1.0.0",
        spec_version="1.0",
        name="VLAN",
        objective="Verify VLAN.",
        status="DRAFT",
        applicable_devices=[],
        preconditions=[],
        environment_requirements=[],
        validation_methods=[],
        outputs=[],
        tags=[],
    )


def test_runner_plugin_version_is_unique(db_session) -> None:
    db_session.add_all([make_plugin(), make_plugin()])
    with pytest.raises(IntegrityError):
        db_session.commit()


@pytest.mark.parametrize(
    "overrides",
    [
        {"package_sha256": "short"},
        {"install_path_ref": "C:/plugins/onu-vlan"},
        {"install_path_ref": "../outside"},
    ],
)
def test_runner_plugin_rejects_untrusted_package_metadata(db_session, overrides) -> None:
    db_session.add(make_plugin(**overrides))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_runner_action_code_is_unique_and_phase_is_controlled(db_session) -> None:
    plugin = make_plugin()
    plugin.actions.extend(
        [
            RunnerAction(
                action_code="verify-vlan",
                phase="VERIFY",
                input_schema={},
                output_schema={},
                timeout_seconds=30,
                idempotent=True,
                recovery_capability="NONE",
                adapter_selector={},
            ),
            RunnerAction(
                action_code="verify-vlan",
                phase="SHELL",
                input_schema={},
                output_schema={},
                timeout_seconds=30,
                idempotent=True,
                recovery_capability="NONE",
                adapter_selector={},
            ),
        ]
    )
    db_session.add(plugin)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_published_runner_plugin_package_identity_is_immutable(db_session) -> None:
    plugin = make_plugin(
        status="PUBLISHED",
        published_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(plugin)
    db_session.commit()

    with pytest.raises(ValueError, match="immutable"):
        plugin.package_sha256 = "b" * 64


def test_skill_runner_binding_has_unique_phase_order_and_valid_action_fk(
    db_session,
) -> None:
    plugin = make_plugin()
    action = RunnerAction(
        action_code="verify-vlan",
        phase="VERIFY",
        input_schema={},
        output_schema={},
        timeout_seconds=30,
        idempotent=True,
        recovery_capability="NONE",
        adapter_selector={},
    )
    plugin.actions.append(action)
    skill = make_skill()
    db_session.add_all([plugin, skill])
    db_session.flush()
    db_session.add_all(
        [
            SkillRunnerBinding(
                skill_id=skill.id,
                runner_action_id=action.id,
                phase="VERIFY",
                parameter_mapping={},
                observation_mapping={},
                adapter_selector={},
                required=True,
                display_order=1,
            ),
            SkillRunnerBinding(
                skill_id=skill.id,
                runner_action_id=action.id,
                phase="VERIFY",
                parameter_mapping={},
                observation_mapping={},
                adapter_selector={},
                required=True,
                display_order=1,
            ),
        ]
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
