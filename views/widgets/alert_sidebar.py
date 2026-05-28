from PySide6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QLabel, QDoubleSpinBox, QSpinBox, \
    QGridLayout, QGraphicsOpacityEffect, QSizePolicy, QPushButton
from PySide6.QtCore import Qt, QByteArray, QPropertyAnimation, QEasingCurve, Signal
from utils.enums import CognitiveState

class AlertSidebar(QWidget):
    # Right sidebar: per-subject calibration trigger, alert rule controls,
    # current state badge with a subtle pulse animation on state change.

    calibrate_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(300)
        self.setObjectName("AlertSidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._init_ui()
        self._init_animation()

        # Initial style
        self.update_state_indicator(CognitiveState.NOMINAL)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setSpacing(10)

        # --- Subject Calibration Group ---
        # Per-subject 60s rest baseline drives the LoadDetector. Before this
        # runs the detector returns NOMINAL regardless of the signal.
        self.calibration_group = QGroupBox("Subject Calibration")
        self.calibration_group.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        cal_layout = QVBoxLayout(self.calibration_group)
        cal_layout.setContentsMargins(14, 12, 14, 14)
        cal_layout.setSpacing(8)

        self.calibrate_button = QPushButton("Calibrate Subject (60s)")
        self.calibrate_button.setObjectName("PrimaryButton")
        self.calibrate_button.clicked.connect(self.calibrate_clicked)
        cal_layout.addWidget(self.calibrate_button)

        self.calibration_status_label = QLabel("Not calibrated yet.")
        self.calibration_status_label.setWordWrap(True)
        cal_layout.addWidget(self.calibration_status_label)

        layout.addWidget(self.calibration_group)

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
        self.threshold_spinbox.setDecimals(1)
        self.threshold_spinbox.setSingleStep(0.5)
        self.threshold_spinbox.setValue(4.0)
        self.threshold_spinbox.setSuffix(" µM")

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
        # Legacy: these values are passed through to the controller but ignored
        # by the current LoadDetector. Phase 6 replaces these spinboxes with
        # k_sd / active-window / min-elevated-channels controls bound to the
        # detector.
        return {
            'threshold': self.threshold_spinbox.value(),
            'duration': self.duration_spinbox.value()
        }

    def update_calibration_status(self, status: dict) -> None:
        # Called by MainWindow on a poll timer. Reflects whether the detector
        # is calibrating, calibrated, or waiting.
        if status.get("is_calibrating"):
            progress = float(status.get("progress", 0.0)) * 100.0
            self.calibrate_button.setEnabled(False)
            self.calibrate_button.setText("Calibrating...")
            self.calibration_status_label.setText(f"Calibrating: {progress:.0f}%")
            return

        if status.get("is_calibrated"):
            self.calibrate_button.setEnabled(True)
            self.calibrate_button.setText("Recalibrate Subject (60s)")
            summary = status.get("baseline_summary") or {}
            asym_mean = summary.get("asymmetry_mean", 0.0)
            asym_sd = summary.get("asymmetry_std", 0.0)
            self.calibration_status_label.setText(
                f"Calibrated.\nAsymmetry baseline: {asym_mean:+.3f} +/- {asym_sd:.3f} uM"
            )
            return

        # Not calibrating, not calibrated.
        self.calibrate_button.setEnabled(True)
        self.calibrate_button.setText("Calibrate Subject (60s)")
        self.calibration_status_label.setText("Not calibrated yet.")

    def update_state_indicator(self, state):
        # Updates the state badge text/style and plays a pulse animation.
        # Update Text
        self.state_indicator_label.setText(state.value.upper())

        # Decide which visual state to apply
        if state == CognitiveState.LOAD:
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