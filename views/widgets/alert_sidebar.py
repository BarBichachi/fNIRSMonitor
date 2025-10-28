# views/widgets/alert_sidebar.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QPushButton, QLabel, QDoubleSpinBox, QSpinBox, \
    QHBoxLayout, QGridLayout
from PySide6.QtCore import Qt


class AlertSidebar(QWidget):
    # A widget for the right sidebar, handling calibration and state detection alerts.
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(300)
        self._init_ui()

    def _init_ui(self):
        # Initializes the UI elements for this sidebar.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 10, 5, 10)

        # --- Calibration Group ---
        self.calibrate_button = QPushButton("Recalibrate Baseline")
        layout.addWidget(self.calibrate_button)

        # --- Alert Rules Group ---
        self.rules_group = QGroupBox("Alert Rules")
        rules_layout = QGridLayout()
        self.rules_group.setLayout(rules_layout)

        # --- Threshold Rule ---
        rules_layout.addWidget(QLabel("IF O2Hb >"), 0, 0)
        self.threshold_spinbox = QDoubleSpinBox()
        self.threshold_spinbox.setDecimals(3)
        self.threshold_spinbox.setSingleStep(0.001)
        self.threshold_spinbox.setValue(0.004)
        self.threshold_spinbox.setSuffix(" ΔμM")
        rules_layout.addWidget(self.threshold_spinbox, 0, 1)

        # --- Duration Rule ---
        rules_layout.addWidget(QLabel("for >"), 1, 0)
        self.duration_spinbox = QSpinBox()
        self.duration_spinbox.setMinimum(1)
        self.duration_spinbox.setValue(3)
        self.duration_spinbox.setSuffix(" s")
        rules_layout.addWidget(self.duration_spinbox, 1, 1)

        layout.addWidget(self.rules_group)
        layout.addStretch(1)

        # --- Current State Indicator ---
        state_group = QGroupBox("Current State")
        state_layout = QVBoxLayout()
        self.state_indicator_label = QLabel("NOMINAL")
        self.state_indicator_label.setAlignment(Qt.AlignCenter)
        state_layout.addWidget(self.state_indicator_label)
        state_group.setLayout(state_layout)
        layout.addWidget(state_group)

        # --- Set initial state color ---
        self.update_state_indicator("Nominal")

    def get_alert_rules(self):
        # Returns the current alert rule values from the UI.
        return {
            'threshold': self.threshold_spinbox.value(),
            'duration': self.duration_spinbox.value()
        }

    def update_state_indicator(self, state):
        # Updates the text and color of the state indicator.
        self.state_indicator_label.setText(state.upper().replace("_", " "))
        if state == "Cognitive Load":
            style = "background-color: #d32f2f; color: white;"  # Red for alert
        else:
            style = "background-color: #4caf50; color: white;"  # Green for nominal

        self.state_indicator_label.setStyleSheet(f"""
            font-size: 24px; font-weight: bold;
            border-radius: 8px; padding: 20px;
            {style}
        """)