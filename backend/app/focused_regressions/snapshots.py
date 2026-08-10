from datetime import datetime
from typing import Any

from app.models.defect import Defect


def build_defect_snapshot(
    defect: Defect,
    source_run_result_id: str,
    captured_at: datetime,
) -> dict[str, Any]:
    return {
        "defect_code": defect.defect_code,
        "title": defect.title,
        "severity": defect.severity,
        "status": defect.status,
        "resolution_notes": defect.resolution_notes,
        "source_run_result_id": source_run_result_id,
        "captured_at": captured_at.isoformat(),
    }
