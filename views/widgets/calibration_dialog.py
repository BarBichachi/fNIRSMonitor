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
        self.setObjectName("CalibrationDialog")
        self.setModal(True)  # This blocks interaction with the main window
        self.setFixedSize(300, 150)

        # --- UI Elements ---
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.info_label = QLabel("Calibrating baseline, please wait...")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setWordWrap(True)

        self.countdown_label = QLabel(str(config.CALIBRATION_DURATION))
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown_label.setStyleSheet("font-size: 24px; font-weight: bold;")

        self.stop_button = QPushButton("Stop Calibration")
        self.stop_button.setObjectName("CalibrationStopButton")

        layout.addWidget(self.info_label)
        layout.addWidget(self.countdown_label)
        layout.addStretch(1)
        layout.addWidget(self.stop_button, alignment=Qt.AlignmentFlag.AlignCenter)

        # --- Connect Signals ---
        self.stop_button.clicked.connect(self._on_stop_clicked)

    def update_countdown(self, seconds_left):
        # Updates the countdown timer label.
        self.countdown_label.setText(str(seconds_left))

    def show_message(self, title, message, detailed_text=None):
        # Shows a message box, with details section.
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        if detailed_text:
            msg_box.setInformativeText(detailed_text)
        msg_box.exec()

    def _on_stop_clicked(self):
        # User explicitly requested to stop calibration
        self.stop_requested.emit()
        self.reject()  # close the dialog (will NOT emit stop_requested again)
