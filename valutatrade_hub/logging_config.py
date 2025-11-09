import logging
import os
from logging.handlers import RotatingFileHandler

from valutatrade_hub.infra.settings import SettingsLoader

_LOGGER_NAME = "valutatrade.actions"
_configured = False


def get_logger() -> logging.Logger:
    global _configured
    logger = logging.getLogger(_LOGGER_NAME)
    if _configured:
        return logger

    settings = SettingsLoader()

    # <-- ключи ДОЛЖНЫ быть строками
    log_dir = settings.get("LOG_DIR", "logs")
    log_file = settings.get("LOG_FILE", "actions.log")
    level_nm = settings.get("LOG_LEVEL", "INFO").upper()
    fmt = settings.get("LOG_FORMAT", "%(levelname)s %(asctime)s %(message)s")
    datefmt = settings.get("LOG_DATEFMT", "%Y-%m-%dT%H:%M:%S")

    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_file)

    level = getattr(logging, level_nm, logging.INFO)
    logger.setLevel(level)

    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    fh = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,  # 1 MB
        backupCount=5,
        encoding="utf-8",
    )
    fh.setLevel(level)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    _configured = True
    return logger
