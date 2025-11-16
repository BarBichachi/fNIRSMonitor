from PySide6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QPushButton, QLabel, QDoubleSpinBox, QSpinBox, \
    QGridLayout, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, QByteArray, QPropertyAnimation, QEasingCurve


class AlertSidebar(QWidget):
    # A widget for the right sidebar, handling calibration and state detection alerts.
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(300)
        self._init_ui()
        self._init_animation()

        # Initial style
        self.update_state_indicator("Nominal")

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setSpacing(10)

        # --- Alert Rules Group ---
        self.rules_group = QGroupBox("Alert Rules")
        self.rules_group.setObjectName("AlertRulesGroup")
        rules_layout = QGridLayout(self.rules_group)
        rules_layout.setContentsMargins(10, 8, 10, 10)
        rules_layout.setHorizontalSpacing(6)
        rules_layout.setVerticalSpacing(6)

        # Threshold
        label_if = QLabel("IF O2Hb >")
        self.threshold_spinbox = QDoubleSpinBox()
        self.threshold_spinbox.setDecimals(3)
        self.threshold_spinbox.setSingleStep(0.001)
        self.threshold_spinbox.setValue(0.004)
        self.threshold_spinbox.setSuffix(" ΔµM")

        rules_layout.addWidget(label_if, 0, 0, Qt.AlignmentFlag.AlignLeft)
        rules_layout.addWidget(self.threshold_spinbox, 0, 1)

        # Duration
        label_for = QLabel("for >")
        self.duration_spinbox = QSpinBox()
        self.duration_spinbox.setMinimum(1)
        self.duration_spinbox.setValue(3)
        self.duration_spinbox.setSuffix(" s")

        rules_layout.addWidget(label_for, 1, 0, Qt.AlignmentFlag.AlignLeft)
        rules_layout.addWidget(self.duration_spinbox, 1, 1)

        layout.addWidget(self.rules_group)

        layout.addStretch(1)

        # --- Current State Card ----------------------------------------------
        state_group = QGroupBox("Current State")
        state_group.setObjectName("StateGroup")
        state_layout = QVBoxLayout(state_group)
        state_layout.setContentsMargins(10, 10, 10, 10)

        self.state_indicator_label = QLabel("NOMINAL")
        self.state_indicator_label.setObjectName("StateBadge")
        self.state_indicator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        state_layout.addWidget(self.state_indicator_label)
        layout.addWidget(state_group)

    def _init_animation(self):
        # Subtle opacity pulse whenever state changes
        self._opacity_effect = QGraphicsOpacityEffect(self.state_indicator_label)
        self.state_indicator_label.setGraphicsEffect(self._opacity_effect)

        self._pulse_anim = QPropertyAnimation(self._opacity_effect, QByteArray(b"opacity"), self)
        self._pulse_anim.setDuration(250)
        self._pulse_anim.setStartValue(0.4)
        self._pulse_anim.setEndValue(1.0)
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.OutQuad)

    def get_alert_rules(self):
        # Returns the current alert rule values from the UI
        return {
            'threshold': self.threshold_spinbox.value(),
            'duration': self.duration_spinbox.value()
        }

    def update_state_indicator(self, state: str):
        # Normalize state text
        display_text = state.upper().replace("_", " ")
        self.state_indicator_label.setText(display_text)

        if state == "Cognitive Load":
            style_colors = ("background-color: #e53935; "
                            "color: #ffffff; "
                            "border: 1px solid "
                            "#ff8a80;")
        else:
            # Treat any other value as nominal / safe
            style_colors = ("background-color: #43a047; "
                            "color: #ffffff; "
                            "border: 1px solid #a5d6a7;")

        self.state_indicator_label.setStyleSheet(f"""
            font-size: 24px;
            font-weight: 600;
            padding: 18px 10px;
            border-radius: 16px;
            letter-spacing: 1px;
            {style_colors}
        """)

        # Restart pulse animation each time the state changes
        self._pulse_anim.stop()
        self._opacity_effect.setOpacity(0.4)
        self._pulse_anim.start()