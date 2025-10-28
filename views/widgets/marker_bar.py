from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLineEdit, QLabel
import config

class MarkerBar(QWidget):
    # A widget for the bottom bar, handling preset and custom event markers.
    def __init__(self, parent=None):
        super().__init__(parent)
        self.preset_buttons = []
        self._init_ui()

    def _init_ui(self):
        # Initializes the UI elements for this bar.
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        layout.addWidget(QLabel("<b>Markers:</b>"))

        # --- Preset Marker Buttons ---
        for marker_text in config.PRESET_MARKERS:
            button = QPushButton(marker_text)
            self.preset_buttons.append(button)
            layout.addWidget(button)

        layout.addStretch(1)

        # --- Custom Marker Section ---
        layout.addWidget(QLabel("Custom:"))
        self.custom_marker_input = QLineEdit()
        layout.addWidget(self.custom_marker_input)
        self.add_custom_marker_button = QPushButton("Add Custom")
        layout.addWidget(self.add_custom_marker_button)