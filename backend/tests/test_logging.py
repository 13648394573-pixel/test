import logging

from app.core.logging import configure_logging


def test_configure_logging_writes_application_messages(tmp_path) -> None:
    log_file = tmp_path / "nested" / "test-workbench.log"
    configure_logging(log_file=log_file, level="INFO")

    logging.getLogger("test_workbench").info("foundation-ready")
    logging.shutdown()

    assert "foundation-ready" in log_file.read_text(encoding="utf-8")
