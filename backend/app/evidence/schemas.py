from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_result_id: str | None
    defect_id: str | None
    run_result_ids: list[str]
    category: Literal["SCREENSHOT", "LOG", "CONFIG", "OTHER"]
    original_name: str
    storage_path: str
    media_type: str
    file_size: int
    sha256: str
    description: str | None
    parsed_metadata: dict[str, Any] | None
    created_at: datetime

    @field_validator("parsed_metadata", mode="before")
    @classmethod
    def _decode_parsed_metadata(cls, value: Any) -> Any:
        """Stored as JSON text; expose it as an object to API consumers."""
        if isinstance(value, str):
            try:
                import json

                return json.loads(value)
            except ValueError:
                return None
        return value
