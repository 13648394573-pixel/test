from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


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
    parsed_metadata: str | None
    created_at: datetime
