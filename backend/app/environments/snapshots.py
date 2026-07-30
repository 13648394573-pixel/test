from datetime import datetime
from typing import Any

from app.models.environment import EnvironmentProfile


def build_environment_snapshot(
    profile: EnvironmentProfile,
    captured_at: datetime,
) -> dict[str, Any]:
    parameters = sorted(
        profile.parameters,
        key=lambda item: (item.display_order, item.param_key),
    )
    return {
        "profile_name": profile.name,
        "description": profile.description,
        "profile_updated_at": profile.updated_at.isoformat(),
        "captured_at": captured_at.isoformat(),
        "parameters": [
            {
                "section": parameter.section,
                "param_key": parameter.param_key,
                "param_value": parameter.param_value,
                "display_order": parameter.display_order,
            }
            for parameter in parameters
        ],
    }
