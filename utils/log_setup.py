"""
Application logging setup.

Initializes a rotating file handler in the per-user app data directory and
a console handler. Modules use the standard `logging.getLogger(__name__)`
pattern; setup_logging() should be called once from main() before any other
imports trigger their own loggers.

Why utils/log_setup.py and not utils/logging.py: the stdlib `logging` module
is imported by half the world; shadowing its name causes obscure failures.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from utils.app_paths import app_data_dir


DEFAULT_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _logs_dir() -> Path:
    p = app_data_dir() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def log_file_path() -> Path:
    return _logs_dir() / "fnirs_monitor.log"


def setup_logging(level: int = DEFAULT_LEVEL) -> None:
    # Idempotent: if root already has our handlers, skip.
    root = logging.getLogger()
    if getattr(root, "_fnirs_initialized", False):
        return

    root.setLevel(level)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    file_handler = RotatingFileHandler(
        log_file_path(),
        maxBytes=2 * 1024 * 1024,  # 2 MB per file
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(stream=sys.stderr)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # Quiet down some chatty third-party loggers that bleed into our file.
    logging.getLogger("h5py").setLevel(logging.WARNING)

    root._fnirs_initialized = True


def install_exception_hook(qt_dialog_callback: Optional[callable] = None) -> None:
    # Unhandled exceptions land in the log with their traceback. If a Qt
    # dialog callback is provided (signature: callback(message)), it gets
    # called too -- but only on the main thread, since Qt UI ops are not
    # thread-safe.
    logger = logging.getLogger("fnirs.excepthook")

    def hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger.exception(
            "Unhandled exception", exc_info=(exc_type, exc_value, exc_tb)
        )
        if qt_dialog_callback is not None:
            try:
                qt_dialog_callback(f"{exc_type.__name__}: {exc_value}")
            except Exception:
                # If even the error dialog throws, just give up gracefully.
                pass

    sys.excepthook = hook
