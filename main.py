import sys
from PySide6.QtWidgets import QApplication
from views.main_window import MainWindow
import config

if __name__ == '__main__':
    # The main entry point for the application.
    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setApplicationVersion(config.APP_VERSION)

    window = MainWindow()
    window.showMaximized()

    sys.exit(app.exec())