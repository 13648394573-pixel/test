from datetime import datetime
from typing import Any

from app.models.environment import EnvironmentProfile

# Convention: a parameter value of "credential:<credential_target_ref>"
# points at a keyring-stored credential (see CredentialReference). The
# secret itself never enters the environment profile or any snapshot.
CREDENTIAL_VALUE_PREFIX = "credential:"
REDACTED_VALUE = "***"


def _redact(value: str) -> tuple[str, str | None]:
    if value.startswith(CREDENTIAL_VALUE_PREFIX):
        return REDACTED_VALUE, value.removeprefix(CREDENTIAL_VALUE_PREFIX)
    return value, None


def build_environment_snapshot(
    profile: EnvironmentProfile,
    captured_at: datetime,
) -> dict[str, Any]:
    parameters = sorted(
        profile.parameters,
        key=lambda item: (item.display_order, item.param_key),
    )
    entries = []
    for parameter in parameters:
        value, credential_ref = _redact(parameter.param_value)
        entry = {
            "section": parameter.section,
            "param_key": parameter.param_key,
            "param_value": value,
            "display_order": parameter.display_order,
        }
        if credential_ref:
            entry["credential_ref"] = credential_ref
        entries.append(entry)
    return {
        "profile_name": profile.name,
        "description": profile.description,
        "profile_updated_at": profile.updated_at.isoformat(),
        "captured_at": captured_at.isoformat(),
        "parameters": entries,
    }
