import pytest

from app.models.environment import RunEnvironmentSnapshot


def test_environment_snapshot_payload_is_immutable_after_assignment() -> None:
    snapshot = RunEnvironmentSnapshot(
        test_run_id="run-1",
        environment_profile_source_id="profile-1",
        profile_snapshot={"profile_name": "Lab A"},
    )

    with pytest.raises(ValueError, match="immutable"):
        snapshot.profile_snapshot = {"profile_name": "Lab B"}


def test_environment_snapshot_version_cannot_change() -> None:
    snapshot = RunEnvironmentSnapshot(
        test_run_id="run-1",
        environment_profile_source_id="profile-1",
        profile_snapshot={"profile_name": "Lab A"},
        snapshot_version=1,
    )

    with pytest.raises(ValueError, match="immutable"):
        snapshot.snapshot_version = 2
