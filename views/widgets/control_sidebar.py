# views/widgets/control_sidebar.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QGridLayout, QLabel, QHBoxLayout
from PySide6.QtCore import Qt
import config

class ControlSidebar(QWidget):
    # A widget for the left sidebar, handling channel selection and signal quality.
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)
        self.setObjectName("ControlSidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.quality_indicators = []

        # labels for sample-rate info (stream + processing)
        self.stream_rate_value_label = None
        self.processing_rate_value_label = None

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

        # Blue O2Hb
        o2hb_label = QLabel("● O₂Hb (blue): oxygenated")
        o2hb_label.setObjectName("LegendO2HbLabel")

        # Red HHb
        hhb_label = QLabel("● HHb (red): deoxygenated")
        hhb_label.setObjectName("LegendHHbLabel")

        # Y-axis explanation
        yaxis_label = QLabel("Y-axis: Δconcentration (µM) relative to baseline")
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

        proc_label = QLabel("Processing rate:")
        self.processing_rate_value_label = QLabel("– Hz")
        self.processing_rate_value_label.setObjectName("RateValueLabel")

        rate_layout.addWidget(stream_label)
        rate_layout.addWidget(self.stream_rate_value_label)
        rate_layout.addSpacing(4)
        rate_layout.addWidget(proc_label)
        rate_layout.addWidget(self.processing_rate_value_label)

        rate_group.setLayout(rate_layout)
        layout.addWidget(rate_group)

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
            state = "green" if state == "green" else "red"
            label.setProperty("state", state)

            # Re-apply stylesheet so the [state="..."] selector takes effect
            label.style().unpolish(label)
            label.style().polish(label)

    def set_sample_rate_info(self, detected_hz: float | None, processing_hz: float | None):
        """Update the labels for detected LSL stream rate and processing rate."""
        if detected_hz is None:
            self.stream_rate_value_label.setText("– Hz")
        else:
            self.stream_rate_value_label.setText(f"{detected_hz:.1f} Hz")

        if processing_hz is None:
            self.processing_rate_value_label.setText("– Hz")
        else:
            self.processing_rate_value_label.setText(f"{processing_hz:.1f} Hz")

    def reset_signals_quality_indicators(self):
        for dot in self.quality_indicators:
            dot.setProperty("state", "red")
            dot.style().unpolish(dot)
            dot.style().polish(dot)