import logging
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

import config
from utils.log_setup import setup_logging, install_exception_hook
from views.main_window import MainWindow


def _show_excepthook_dialog(message: str) -> None:
    # Best-effort GUI surface for unhandled exceptions. Safe to call from the
    # main thread only. The full traceback is already in the log file.
    try:
        QMessageBox.critical(None, "fNIRS Monitor", f"Unhandled error:\n{message}\n\nSee log for details.")
    except Exception:
        pass


def main() -> int:
    setup_logging()
    log = logging.getLogger("fnirs.main")
    log.info("Starting %s %s", config.APP_NAME, config.APP_VERSION)

    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setApplicationVersion(config.APP_VERSION)

    install_exception_hook(qt_dialog_callback=_show_excepthook_dialog)

    window = MainWindow()
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
