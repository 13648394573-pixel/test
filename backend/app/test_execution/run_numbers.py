from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.test_execution import TestRun


class RunNumberConflictError(Exception):
    pass


def is_run_number_conflict(exception: Exception) -> bool:
    message = str(exception)
    return (
        "test_runs.run_no" in message
        or "uq_test_runs_run_no" in message
    )


def next_run_no(session: Session) -> str:
    values = session.scalars(select(TestRun.run_no)).all()
    numbers = [
        int(value.removeprefix("RUN-"))
        for value in values
        if value
        and value.startswith("RUN-")
        and value.removeprefix("RUN-").isdigit()
    ]
    return f"RUN-{max(numbers, default=0) + 1:06d}"
