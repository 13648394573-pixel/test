from sqlalchemy import text

from app.db.session import create_database_engine, create_session_factory


def test_sqlite_engine_creates_parent_directory_and_executes_query(tmp_path) -> None:
    database_file = tmp_path / "nested" / "workbench.db"
    engine = create_database_engine(f"sqlite:///{database_file.as_posix()}")

    with engine.connect() as connection:
        value = connection.execute(text("SELECT 1")).scalar_one()

    assert value == 1
    assert database_file.exists()


def test_session_factory_binds_sessions_to_engine(tmp_path) -> None:
    engine = create_database_engine(
        f"sqlite:///{(tmp_path / 'sessions.db').as_posix()}"
    )
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        value = session.execute(text("SELECT 2")).scalar_one()

    assert value == 2


def test_sqlite_engine_enables_foreign_key_enforcement(tmp_path) -> None:
    engine = create_database_engine(
        f"sqlite:///{(tmp_path / 'foreign-keys.db').as_posix()}"
    )

    with engine.connect() as connection:
        enabled = connection.execute(text("PRAGMA foreign_keys")).scalar_one()

    assert enabled == 1
