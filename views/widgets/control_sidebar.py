# views/widgets/control_sidebar.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QGridLayout, QLabel, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt, Signal
import config

class ControlSidebar(QWidget):
    # Left sidebar: plot legend, sample-rate readout, acquisition parameters
    # (DPF/distance) with an Edit shortcut, and per-channel signal quality dots.

    edit_acquisition_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)
        self.setObjectName("ControlSidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.quality_indicators = []

        # labels for sample-rate info (stream + processing)
        self.stream_rate_value_label = None
        # Acquisition card labels for refresh after settings reload.
        self._dpf_value_label = None
        self._distance_value_label = None

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # --- Plot Legend card ---
        legend_group = QGroupBox("Plot Legend")
        legend_group.setObjectName("CardGroupBox")
        legend_group.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        legend_layout = QVBoxLayout()
        legend_layout.setSpacing(4)
        legend_layout.addSpacing(10)

        # Red O2Hb (Updated Text)
        o2hb_label = QLabel("● O₂Hb (Red): Oxygenated")
        o2hb_label.setObjectName("LegendO2HbLabel")

        # Blue HHb (Updated Text)
        hhb_label = QLabel("● HHb (Blue): Deoxygenated")
        hhb_label.setObjectName("LegendHHbLabel")

        # Y-axis explanation
        yaxis_label = QLabel("Y-axis: Δconcentration (µM) relative to OxySoft reference")
        yaxis_label.setWordWrap(True)
        yaxis_label.setObjectName("LegendYAxisLabel")

        legend_layout.addWidget(o2hb_label)
        legend_layout.addWidget(hhb_label)
        legend_layout.addWidget(yaxis_label)
        legend_group.setLayout(legend_layout)
        layout.addWidget(legend_group)

        # --- Sample Rate card ---
        rate_group = QGroupBox("Sample Rate")
        rate_group.setObjectName("CardGroupBox")
        rate_layout = QVBoxLayout()
        rate_layout.setSpacing(4)
        rate_layout.addSpacing(10)

        stream_label = QLabel("Detected LSL stream:")
        self.stream_rate_value_label = QLabel("– Hz")
        self.stream_rate_value_label.setObjectName("RateValueLabel")

        rate_layout.addWidget(stream_label)
        rate_layout.addWidget(self.stream_rate_value_label)

        rate_group.setLayout(rate_layout)
        layout.addWidget(rate_group)

        # --- Acquisition card (DPF + interoptode distance) ---
        # Always visible so the operator knows exactly what's being applied to
        # the data. "Edit" opens the Settings dialog; disabled mid-recording.
        acq_group = QGroupBox("Acquisition")
        acq_group.setObjectName("CardGroupBox")
        acq_layout = QVBoxLayout()
        acq_layout.setSpacing(4)
        acq_layout.addSpacing(10)

        self._dpf_value_label = QLabel()
        self._distance_value_label = QLabel()
        self._refresh_acquisition_labels()
        acq_layout.addWidget(self._dpf_value_label)
        acq_layout.addWidget(self._distance_value_label)

        edit_btn = QPushButton("Edit...")
        edit_btn.setObjectName("HeaderButton")
        edit_btn.clicked.connect(self.edit_acquisition_requested)
        acq_layout.addWidget(edit_btn)

        acq_group.setLayout(acq_layout)
        layout.addWidget(acq_group)

        # --- Signal Quality card ---
        quality_group = QGroupBox("Signal Quality")
        quality_group.setObjectName("CardGroupBox")
        # Outer layout (this allows addSpacing like the other cards)
        quality_outer = QVBoxLayout()
        quality_outer.setContentsMargins(0, 0, 0, 0)
        quality_outer.setSpacing(10)  # << same as the other cards
        quality_outer.addSpacing(10)  # << identical behavior to Plot Legend & Rate cards

        # Inner grid layout
        quality_layout = QGridLayout()
        quality_layout.setContentsMargins(10, 10, 10, 10)
        quality_layout.setVerticalSpacing(6)

        # Create a grid of label+dot pairs (2 columns: left/right)
        for i, name in enumerate(config.CHANNEL_NAMES):
            row, col = divmod(i, 2)

            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)

            chan_label = QLabel(name)

            indicator = QLabel()
            indicator.setObjectName("SignalDot")
            indicator.setProperty("state", "red")  # default
            indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)

            self.quality_indicators.append(indicator)

            row_layout.addWidget(chan_label)
            row_layout.addWidget(indicator)
            row_layout.addStretch(1)

            quality_layout.addWidget(row_widget, row, col)

        quality_outer.addLayout(quality_layout)

        quality_group.setLayout(quality_outer)
        layout.addWidget(quality_group)

        layout.addStretch(1)

    def update_signals_quality_indicators(self, signals_quality_states):
        for i, state in enumerate(signals_quality_states):
            if i >= len(self.quality_indicators):
                break

            label = self.quality_indicators[i]
            # Accept green / yellow / red; anything else falls back to red.
            normalized = state if state in ("green", "yellow", "red") else "red"
            label.setProperty("state", normalized)

            # Re-apply stylesheet so the [state="..."] selector takes effect
            label.style().unpolish(label)
            label.style().polish(label)

    def set_sample_rate_info(self, detected_hz: float | None):
        # Updates the label for detected LSL stream rate.
        if detected_hz is None:
            self.stream_rate_value_label.setText("– Hz")
        else:
            self.stream_rate_value_label.setText(f"{detected_hz:.1f} Hz")

    def reset_signals_quality_indicators(self):
        for dot in self.quality_indicators:
            dot.setProperty("state", "red")
            dot.style().unpolish(dot)
            dot.style().polish(dot)

    def refresh_acquisition_labels(self) -> None:
        # Called by MainWindow after the Settings dialog applies new values.
        self._refresh_acquisition_labels()

    def _refresh_acquisition_labels(self) -> None:
        if self._dpf_value_label is not None:
            self._dpf_value_label.setText(f"DPF: {float(config.DPF):.2f}")
        if self._distance_value_label is not None:
            self._distance_value_label.setText(
                f"Distance: {float(config.INTEROPTODE_DISTANCE):.2f} cm"
            )