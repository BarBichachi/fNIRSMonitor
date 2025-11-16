from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox, QPushButton, QLineEdit
from PySide6.QtCore import Qt


class ConnectionBar(QWidget):
    # A widget for the top bar, handling stream connection and recording controls.
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        # Initializes the UI elements for this bar.
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        # --- Stream Connection Section ---
        layout.addWidget(QLabel("Stream:"))
        self.stream_dropdown = QComboBox()
        self.stream_dropdown.setMinimumWidth(200)
        self.stream_dropdown.addItem("Press Refresh to search")
        layout.addWidget(self.stream_dropdown)

        self.refresh_button = QPushButton("Refresh")
        layout.addWidget(self.refresh_button)

        # --- "Searching..." indicator label ---
        self.search_indicator_label = QLabel("Searching...")
        self.search_indicator_label.setStyleSheet("color: #0078d4;")  # Blue text
        self.search_indicator_label.hide()  # Initially hidden
        layout.addWidget(self.search_indicator_label)

        # Connect button and status indicator
        self.connect_button = QPushButton("Connect")
        layout.addWidget(self.connect_button)
        layout.addWidget(QLabel("Status:"))
        self.status_indicator = QLabel("●")  # A circle character
        self.status_indicator.setStyleSheet("color: #d32f2f;")  # Red
        layout.addWidget(self.status_indicator)

        layout.addStretch(1)

        # --- Recording Section ---
        layout.addWidget(QLabel("File:"))
        self.filename_input = QLineEdit("session_01")
        layout.addWidget(self.filename_input)

        self.record_button = QPushButton("Record")
        self.record_button.setCheckable(True)
        layout.addWidget(self.record_button)

        self.record_timer_label = QLabel("00:00:00")
        self.record_timer_label.setMinimumWidth(70)
        self.record_timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.record_timer_label)