"""Logging มาตรฐานสำหรับ PDF Form Marker — ไฟล์หมุนเวียนในเครื่องลูกค้า"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

APP_LOGGER_NAME = "pdfmarker"
_MAX_BYTES = 1_500_000
_BACKUP_COUNT = 5


class _ErrorOnlyFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= logging.ERROR


def init_logging(log_dir: Path, *, console: bool = True) -> logging.Logger:
    """สร้าง app.log + errors.log ภายใต้ log_dir แล้วคืน root logger ของแอป"""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "reports").mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(APP_LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    app_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(fmt)
    logger.addHandler(app_handler)

    err_handler = RotatingFileHandler(
        log_dir / "errors.log",
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    err_handler.setLevel(logging.ERROR)
    err_handler.setFormatter(fmt)
    err_handler.addFilter(_ErrorOnlyFilter())
    logger.addHandler(err_handler)

    if console:
        cons = logging.StreamHandler(sys.stderr)
        cons.setLevel(logging.INFO)
        cons.setFormatter(fmt)
        logger.addHandler(cons)

    # ให้ exception จาก werkzeug/flask ที่ใช้ logging.getLogger(__name__) ไหลเข้าไฟล์ด้วย
    for name in ("werkzeug", "flask.app"):
        lg = logging.getLogger(name)
        lg.setLevel(logging.INFO)
        if not lg.handlers:
            lg.addHandler(app_handler)
            lg.addHandler(err_handler)

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    if name:
        return logging.getLogger(f"{APP_LOGGER_NAME}.{name}")
    return logging.getLogger(APP_LOGGER_NAME)
