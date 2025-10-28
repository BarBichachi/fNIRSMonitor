from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QMessageBox
from PySide6.QtCore import Qt, Signal
import config


class CalibrationDialog(QDialog):
    # A modal dialog to show the progress of the baseline calibration.
    stop_requested = Signal()

    def __init__(self, parent=None):
        # Initializes the CalibrationDialog.
        super().__init__(parent)
        self.setWindowTitle("Calibration in Progress")
        self.setModal(True)  # This blocks interaction with the main window
        self.setFixedSize(300, 150)

        # --- UI Elements ---
        layout = QVBoxLayout(self)
        self.info_label = QLabel("Calibrating baseline, please wait...")
        self.info_label.setAlignment(Qt.AlignCenter)

        self.countdown_label = QLabel(str(config.CALIBRATION_DURATION))
        self.countdown_label.setAlignment(Qt.AlignCenter)
        self.countdown_label.setStyleSheet("font-size: 24px; font-weight: bold;")

        self.stop_button = QPushButton("Stop Calibration")

        layout.addWidget(self.info_label)
        layout.addWidget(self.countdown_label)
        layout.addWidget(self.stop_button)

        # --- Connect Signals ---
        self.stop_button.clicked.connect(self.stop_requested.emit)
        self.stop_button.clicked.connect(self.reject)  # Close the dialog on stop

    def update_countdown(self, seconds_left):
        # Updates the countdown timer label.
        self.countdown_label.setText(str(seconds_left))

    def closeEvent(self, event):
        # Handles the user trying to close the dialog with the 'X' button.
        self.stop_requested.emit()
        event.accept()

    def show_message(self, title, message, detailed_text=None):
        # Shows a message box, with an optional expandable details section.
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        if detailed_text:
            msg_box.setDetailedText(detailed_text)
        msg_box.exec()
