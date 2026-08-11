from app.run_history.repository import RunHistoryRepository
from app.run_history.schemas import RunHistoryFilters
from app.test_execution.service import TestRunNotFoundError


class RunComparisonConflictError(Exception):
    pass


class RunHistoryService:
    def __init__(self, repository: RunHistoryRepository) -> None:
        self.repository = repository

    def search(self, filters: RunHistoryFilters) -> dict:
        runs, total = self.repository.search(filters)
        return {
            "items": [self._item(run) for run in runs],
            "total": total,
            "limit": filters.limit,
            "offset": filters.offset,
        }

    def compare(self, run_ids: list[str]) -> dict:
        runs = self.repository.get_runs(run_ids)
        if len(runs) != len(run_ids):
            found = {run.id for run in runs}
            missing = next(run_id for run_id in run_ids if run_id not in found)
            raise TestRunNotFoundError(missing)
        result_ids = [result.id for run in runs for result in run.results]
        evidence_counts = self.repository.evidence_counts(result_ids)
        aligned = [self._align(run) for run in runs]
        case_codes = sorted(set().union(*(set(items) for items in aligned)))
        rows = []
        base_items = aligned[0]
        for case_code in case_codes:
            base = base_items.get(case_code)
            available = base or next(
                items[case_code] for items in aligned[1:] if case_code in items
            )
            targets = []
            for run, items in zip(runs[1:], aligned[1:], strict=True):
                target = items.get(case_code)
                targets.append(
                    {
                        **self._side(run.id, target, evidence_counts),
                        "change": self._change(base, target),
                    }
                )
            rows.append(
                {
                    "case_code": case_code,
                    "title": available.case_snapshot.get("title", ""),
                    "base": self._side(runs[0].id, base, evidence_counts),
                    "targets": targets,
                }
            )
        return {"runs": [self._item(run) for run in runs], "rows": rows}

    @staticmethod
    def _align(run) -> dict:
        aligned = {}
        for result in run.results:
            case_code = str(result.case_snapshot.get("case_code", ""))
            if case_code in aligned:
                raise RunComparisonConflictError(
                    f"Duplicate case code {case_code} in {run.run_no}"
                )
            aligned[case_code] = result
        return aligned

    @staticmethod
    def _side(run_id: str, result, counts: dict[str, int]) -> dict:
        return {
            "run_id": run_id,
            "result": result.result if result is not None else None,
            "evidence_count": counts.get(result.id, 0) if result is not None else 0,
        }

    @staticmethod
    def _change(base, target) -> str:
        if base is None and target is None:
            return "UNCHANGED"
        if base is None:
            return "ADDED"
        if target is None:
            return "REMOVED"
        if base.result == target.result:
            return "UNCHANGED"
        if base.result in {"FAIL", "BLOCKED"} and target.result == "PASS":
            return "IMPROVED"
        if base.result == "PASS" and target.result in {"FAIL", "BLOCKED"}:
            return "REGRESSED"
        return "CHANGED"

    @staticmethod
    def _item(run) -> dict:
        counts = {"PASS": 0, "FAIL": 0, "BLOCKED": 0, "UNSET": 0}
        for result in run.results:
            counts[result.result or "UNSET"] += 1
        snapshot = run.device_snapshot
        return {
            "id": run.id,
            "run_no": run.run_no,
            "project_id": run.project_id,
            "project_name": run.project.name,
            "project_version": run.project.version,
            "device": {
                "device_type": snapshot.get("device_type"),
                "vendor": snapshot.get("vendor"),
                "model": snapshot.get("model"),
                "serial_number": snapshot.get("serial_number"),
                "software_version": snapshot.get("software_version"),
            },
            "status": run.status,
            "summary": {
                "total": len(run.results),
                "pass": counts["PASS"],
                "fail": counts["FAIL"],
                "blocked": counts["BLOCKED"],
                "unset": counts["UNSET"],
            },
            "started_at": run.started_at,
            "finished_at": run.finished_at,
        }
