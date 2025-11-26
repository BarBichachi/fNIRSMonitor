from PySide6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QPushButton, QLabel, QDoubleSpinBox, QSpinBox, \
    QGridLayout, QGraphicsOpacityEffect, QSizePolicy
from PySide6.QtCore import Qt, QByteArray, QPropertyAnimation, QEasingCurve


class AlertSidebar(QWidget):
    # A widget for the right sidebar, handling calibration and state detection alerts.
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(300)
        self.setObjectName("AlertSidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
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
        self.rules_group.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.rules_group.setObjectName("AlertSideBar")
        rules_layout = QGridLayout(self.rules_group)
        rules_layout.setContentsMargins(14, 12, 14, 14)
        rules_layout.setHorizontalSpacing(10)
        rules_layout.setVerticalSpacing(10)

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
        self.state_group = QGroupBox("Current State")
        self.state_group.setObjectName("StateGroup")
        self.state_group.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        state_layout = QVBoxLayout(self.state_group)
        state_layout.setContentsMargins(10, 10, 10, 10)

        self.state_indicator_label = QLabel("NOMINAL")
        self.state_indicator_label.setObjectName("StateBadge")
        self.state_indicator_label.setProperty("state", "nominal")
        self.state_indicator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.state_indicator_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.state_indicator_label.setMinimumHeight(72)

        state_layout.addWidget(self.state_indicator_label)
        layout.addWidget(self.state_group)

    def _init_animation(self):
        # Subtle opacity pulse whenever state changes
        self._opacity_effect = QGraphicsOpacityEffect(self.state_group)
        self.state_group.setGraphicsEffect(self._opacity_effect)

        self._pulse_anim = QPropertyAnimation(self._opacity_effect, QByteArray(b"opacity"), self)
        self._pulse_anim.setDuration(250)
        self._pulse_anim.setStartValue(0.0)
        self._pulse_anim.setEndValue(1.0)
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

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

        # Decide which visual state to apply
        if state == "Cognitive Load":
            badge_state = "alert"
        else:
            # Treat everything else as nominal (including "Nominal")
            badge_state = "nominal"

        # Set the dynamic 'state' property used by the stylesheet
        self.state_indicator_label.setProperty("state", badge_state)

        # Re-apply stylesheet to reflect property change
        self.state_indicator_label.style().unpolish(self.state_indicator_label)
        self.state_indicator_label.style().polish(self.state_indicator_label)

        # Restart pulse animation each time the state changes
        self._pulse_anim.stop()
        self._opacity_effect.setOpacity(0.0)
        self._pulse_anim.start()