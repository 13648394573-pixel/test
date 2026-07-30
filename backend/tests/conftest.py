from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import create_database_engine
import app.models  # noqa: F401


@pytest.fixture
def db_session(tmp_path) -> Iterator[Session]:
    engine = create_database_engine(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    )
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    engine.dispose()
