# views/widgets/control_sidebar.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QGridLayout, QLabel
from PySide6.QtCore import Qt
import config

class ControlSidebar(QWidget):
    # A widget for the left sidebar, handling channel selection and signal quality.
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)
        self.quality_indicators = []

        # labels for sample-rate info (stream + processing)
        self.stream_rate_value_label = None
        self.processing_rate_value_label = None

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setSpacing(10)

        # --- Plot Legend card ---
        legend_group = QGroupBox("Plot Legend")
        legend_group.setObjectName("CardGroupBox")
        legend_layout = QVBoxLayout()
        legend_layout.setSpacing(4)

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
        rate_layout.setSpacing(2)

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
        quality_layout = QGridLayout()
        quality_layout.setHorizontalSpacing(6)
        quality_layout.setVerticalSpacing(4)

        # Create a grid of labels and indicators
        for i, name in enumerate(config.CHANNEL_NAMES):
            row, col = divmod(i, 2)
            chan_label = QLabel(name)
            chan_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            quality_layout.addWidget(chan_label, row, col * 2)

            indicator = QLabel("●")
            indicator.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            indicator.setStyleSheet("color: #d32f2f;")  # default red
            self.quality_indicators.append(indicator)
            quality_layout.addWidget(indicator, row, col * 2 + 1)

        quality_group.setLayout(quality_layout)
        layout.addWidget(quality_group)

        layout.addStretch(1)

    def update_quality_indicators(self, quality_states):
        color_map = {
            'green': '#4caf50',
            'red': '#d32f2f'
        }
        for i, state in enumerate(quality_states):
            if i < len(self.quality_indicators):
                color = color_map.get(state, '#d32f2f')
                self.quality_indicators[i].setStyleSheet(f"color: {color};")

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