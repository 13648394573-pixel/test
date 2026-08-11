from copy import deepcopy
from datetime import datetime
from typing import Any


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _evidence_snapshot(item) -> dict[str, Any]:
    return {
        "id": item.id,
        "category": item.category,
        "original_name": item.original_name,
        "storage_path": item.storage_path,
        "media_type": item.media_type,
        "file_size": item.file_size,
        "sha256": item.sha256,
        "description": item.description,
        "created_at": _iso(item.created_at),
    }


def build_report_snapshot(
    run,
    evidences,
    defects,
    generated_at: datetime,
) -> dict[str, Any]:
    result_evidence: dict[str, list] = {}
    defect_evidence: dict[str, list] = {}
    for item in evidences:
        linked_result_ids = [
            link.run_result_id for link in getattr(item, "result_links", [])
        ]
        if not linked_result_ids and item.run_result_id:
            linked_result_ids = [item.run_result_id]
        for result_id in linked_result_ids:
            result_evidence.setdefault(result_id, []).append(item)
        if item.defect_id:
            defect_evidence.setdefault(item.defect_id, []).append(item)

    results = []
    counts = {"PASS": 0, "FAIL": 0, "BLOCKED": 0}
    for result in sorted(
        run.results,
        key=lambda item: (
            item.case_snapshot.get("case_code", ""),
            item.id,
        ),
    ):
        if result.result in counts:
            counts[result.result] += 1
        results.append(
            {
                "id": result.id,
                "case_source_id": result.case_source_id,
                "case_snapshot": deepcopy(result.case_snapshot),
                "snapshot_version": result.snapshot_version,
                "result": result.result,
                "integrity_status": result.integrity_status,
                "actual_result": result.actual_result,
                "blocked_reason": result.blocked_reason,
                "test_notes": result.test_notes,
                "executed_at": _iso(result.executed_at),
                "locked_at": _iso(result.locked_at),
                "evidences": [
                    _evidence_snapshot(item)
                    for item in result_evidence.get(result.id, [])
                ],
            }
        )

    defect_items = []
    for defect in sorted(defects, key=lambda item: item.defect_code):
        defect_items.append(
            {
                "id": defect.id,
                "defect_code": defect.defect_code,
                "source_run_result_id": defect.source_run_result_id,
                "title": defect.title,
                "description": defect.description,
                "reproduction_steps": defect.reproduction_steps,
                "severity": defect.severity,
                "status": defect.status,
                "resolution_notes": defect.resolution_notes,
                "created_at": _iso(defect.created_at),
                "updated_at": _iso(defect.updated_at),
                "resolved_at": _iso(defect.resolved_at),
                "closed_at": _iso(defect.closed_at),
                "evidences": [
                    _evidence_snapshot(item)
                    for item in defect_evidence.get(defect.id, [])
                ],
                "regressions": [
                    {
                        "id": regression.id,
                        "result": regression.result,
                        "notes": regression.notes,
                        "executed_at": _iso(regression.executed_at),
                        "created_at": _iso(regression.created_at),
                    }
                    for regression in defect.regressions
                ],
            }
        )

    environment = None
    if run.environment_snapshot is not None:
        environment = {
            "environment_profile_source_id": (
                run.environment_snapshot.environment_profile_source_id
            ),
            "snapshot_version": run.environment_snapshot.snapshot_version,
            "profile_snapshot": deepcopy(
                run.environment_snapshot.profile_snapshot
            ),
            "created_at": _iso(run.environment_snapshot.created_at),
        }

    return {
        "snapshot_version": 1,
        "generated_at": generated_at.isoformat(),
        "project": {
            "id": run.project.id,
            "name": run.project.name,
            "version": run.project.version,
            "description": run.project.description,
        },
        "run": {
            "id": run.id,
            "run_no": getattr(run, "run_no", None),
            "status": run.status,
            "started_at": _iso(run.started_at),
            "finished_at": _iso(run.finished_at),
        },
        "device_snapshot": deepcopy(run.device_snapshot),
        "environment_snapshot": environment,
        "summary": {
            "total": len(results),
            "pass": counts["PASS"],
            "fail": counts["FAIL"],
            "blocked": counts["BLOCKED"],
            "defects": len(defect_items),
        },
        "results": results,
        "defects": defect_items,
    }
