# views/widgets/control_sidebar.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QGridLayout, QLabel
from PySide6.QtCore import Qt
import config

class ControlSidebar(QWidget):
    # A widget for the left sidebar, handling channel selection and signal quality.
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(200)
        self.quality_indicators = [] # To hold references to the indicator labels
        self._init_ui()

    def _init_ui(self):
        # Initializes the UI elements for this sidebar.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 10, 5, 10)

        # --- Signal Quality Group ---
        quality_group = QGroupBox("Signal Quality")
        quality_layout = QGridLayout()
        # Create a grid of labels and indicators
        for i, name in enumerate(config.CHANNEL_NAMES):
            row, col = divmod(i, 2)
            quality_layout.addWidget(QLabel(name), row, col * 2)
            indicator = QLabel("●")
            indicator.setStyleSheet("color: #d32f2f;") # Default to Red
            self.quality_indicators.append(indicator) # Store the indicator
            quality_layout.addWidget(indicator, row, col * 2 + 1, Qt.AlignRight)
        quality_group.setLayout(quality_layout)
        layout.addWidget(quality_group)

        layout.addStretch(1) # Push content to the top

    def update_quality_indicators(self, quality_states):
        # Updates the color of each signal quality indicator dot.
        color_map = {
            'green': '#388e3c',
            'red': '#d32f2f'
        }
        for i, state in enumerate(quality_states):
            if i < len(self.quality_indicators):
                color = color_map.get(state, '#d32f2f') # Default to red if state is unknown
                self.quality_indicators[i].setStyleSheet(f"color: {color};")