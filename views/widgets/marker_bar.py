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