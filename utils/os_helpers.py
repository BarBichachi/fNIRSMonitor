import os
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl


def open_folder(path: str):
    abs_path = os.path.abspath(path)
    QDesktopServices.openUrl(QUrl.fromLocalFile(abs_path))