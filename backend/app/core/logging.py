import logging.config
from pathlib import Path


def configure_logging(log_file: str | Path, level: str = "INFO") -> None:
    destination = Path(log_file)
    destination.parent.mkdir(parents=True, exist_ok=True)
    normalized_level = level.upper()

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "level": normalized_level,
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": str(destination),
                    "formatter": "standard",
                    "level": normalized_level,
                    "maxBytes": 5_242_880,
                    "backupCount": 3,
                    "encoding": "utf-8",
                },
            },
            "root": {
                "handlers": ["console", "file"],
                "level": normalized_level,
            },
        }
    )
