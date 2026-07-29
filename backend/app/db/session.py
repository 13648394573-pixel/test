from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker


def ensure_database_directory(database_url: str) -> None:
    url = make_url(database_url)
    if url.drivername.startswith("sqlite"):
        if url.database and url.database != ":memory:":
            Path(url.database).expanduser().resolve().parent.mkdir(
                parents=True,
                exist_ok=True,
            )


def create_database_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    connect_args: dict[str, bool] = {}

    ensure_database_directory(database_url)
    if url.drivername.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(database_url, connect_args=connect_args)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
