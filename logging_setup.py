"""Logging มาตรฐานสำหรับ PDF Form Marker — ไฟล์หมุนเวียนในเครื่องลูกค้า"""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

APP_LOGGER_NAME = "pdfmarker"
_MAX_BYTES = 1_500_000
_BACKUP_COUNT = 5


class _ErrorOnlyFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= logging.ERROR


def _loopback_host(host: str | None = None) -> bool:
    h = (host if host is not None else os.environ.get("HOST", "127.0.0.1")).strip().lower()
    return h in ("127.0.0.1", "localhost", "::1")


def use_per_worker_logs() -> bool:
    """แยกไฟล์ log ต่อ pid เมื่อหลาย worker / bind นอก loopback — กัน rotation ชนกัน"""
    raw = os.environ.get("LOG_PER_WORKER")
    if raw is not None and raw.strip() != "":
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return not _loopback_host()


def init_logging(log_dir: Path, *, console: bool = True) -> logging.Logger:
    """สร้าง app.log + errors.log ภายใต้ log_dir แล้วคืน root logger ของแอป"""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(APP_LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if use_per_worker_logs():
        suffix = f"-{os.getpid()}"
        app_name = f"app{suffix}.log"
        err_name = f"errors{suffix}.log"
    else:
        app_name = "app.log"
        err_name = "errors.log"

    app_handler = RotatingFileHandler(
        log_dir / app_name,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(fmt)
    logger.addHandler(app_handler)

    err_handler = RotatingFileHandler(
        log_dir / err_name,
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

    # flask.app ERROR+ ลงไฟล์ — ไม่ดึง werkzeug access (ทุก /page/*.png) เข้า rotation
    flask_lg = logging.getLogger("flask.app")
    flask_lg.setLevel(logging.INFO)
    if not flask_lg.handlers:
        flask_lg.addHandler(app_handler)
        flask_lg.addHandler(err_handler)

    wz = logging.getLogger("werkzeug")
    wz.setLevel(logging.WARNING)

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    if name:
        return logging.getLogger(f"{APP_LOGGER_NAME}.{name}")
    return logging.getLogger(APP_LOGGER_NAME)
