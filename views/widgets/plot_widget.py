import pyqtgraph as pg
import numpy as np
from PySide6.QtWidgets import QWidget, QGridLayout, QFrame, QVBoxLayout, QLabel
import config


class PlotWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PlotContainer")

        self.plots = {}
        self.plot_curves = {}
        self.first_plot = None

        # Ring Buffer Initialization
        self.buffer_size = max(1, int(config.SAMPLE_RATE * 10))
        self.ptr = 0  # Pointer to the current write position

        # Pre-allocate fixed arrays (Zero-copy optimization)
        self.x_axis = np.linspace(-10, 0, self.buffer_size, endpoint=False)
        self.data = {
            'O2Hb': np.zeros((len(config.CHANNEL_NAMES), self.buffer_size)),
            'HHb': np.zeros((len(config.CHANNEL_NAMES), self.buffer_size))
        }

        # Auto-range control
        self._y_autorange_counter = 0
        self._y_autorange_every = 5  # Every 5 repaints (~12 Hz if repaint is 60 Hz)

        self._init_ui()

    def _init_ui(self):
        layout = QGridLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(8)

        axis_color = (180, 185, 195)

        for i, name in enumerate(config.CHANNEL_NAMES):
            row, col = divmod(i, 2)

            # --- Card frame for each plot -----------------------------------
            frame = QFrame()
            frame.setProperty("class", "PlotCard")
            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(6, 4, 6, 6)
            frame_layout.setSpacing(2)

            # Title label (L1, L2, ...)
            title_label = QLabel(name)
            title_label.setProperty("class", "PlotTitle")
            frame_layout.addWidget(title_label)

            # --- Actual pyqtgraph plot --------------------------------------
            plot_widget = pg.PlotWidget()
            plot_widget.getPlotItem().hideButtons()
            plot_widget.setObjectName(f"Plot_{name}")
            self.plots[name] = plot_widget
            frame_layout.addWidget(plot_widget)

            # Aesthetics
            plot_widget.setBackground((17, 20, 24))  # dark
            plot_widget.showGrid(x=True, y=True, alpha=0.08)

            plot_widget.setLabel('left', 'Δc (µM)')
            plot_widget.setLabel('bottom', 'Time (s ago)')

            plot_widget.enableAutoRange(x=False, y=False)
            plot_widget.setXRange(self.x_axis[0], self.x_axis[-1])

            # Disable user panning/zoom
            vb = plot_widget.getViewBox()
            vb.setMouseEnabled(x=False, y=False)

            # Softer axis colors
            plot_widget.getAxis('bottom').setPen(axis_color)
            plot_widget.getAxis('left').setPen(axis_color)
            plot_widget.getAxis('bottom').setTextPen(axis_color)
            plot_widget.getAxis('left').setTextPen(axis_color)

            # Each plot owns its own Y range (no cross-plot linking), so a
            # large-amplitude channel can't force every other plot's scale.
            if self.first_plot is None:
                self.first_plot = plot_widget
            plot_widget.getViewBox().disableAutoRange()

            # --- Curves: O2Hb red, HHb blued ---------------------------------
            o2hb_curve = plot_widget.plot(
                pen=pg.mkPen((239, 83, 80), width=2),  # red
                name=f"{name} O2Hb"
            )
            hhb_curve = plot_widget.plot(
                pen=pg.mkPen((100, 181, 246), width=2),   # blue
                name=f"{name} HHb"
            )
            self.plot_curves[name] = {'O2Hb': o2hb_curve, 'HHb': hhb_curve}

            layout.addWidget(frame, row, col)

    def set_time_window(self, seconds: int, sample_rate: int):
        # Resize buffers/x-axis to always represent the last <seconds> at the given sample_rate
        if sample_rate is None or sample_rate <= 0:
            return

        new_len = max(1, int(seconds * sample_rate))
        self.buffer_size = new_len
        self.ptr = 0  # Reset pointer

        # Re-allocate buffers (Clears history to avoid complex ring-buffer mapping)
        self.x_axis = np.linspace(-seconds, 0, new_len, endpoint=False)
        self.data['O2Hb'] = np.zeros((len(config.CHANNEL_NAMES), new_len), dtype=float)
        self.data['HHb'] = np.zeros((len(config.CHANNEL_NAMES), new_len), dtype=float)

        # X-axes aren't linked, so update every plot's range explicitly.
        for plot_widget in self.plots.values():
            plot_widget.setXRange(self.x_axis[0], self.x_axis[-1])

    def push_sample(self, processed_data):
        # Writes data to the ring buffer at the current pointer.
        self.data['O2Hb'][:, self.ptr] = processed_data['O2Hb']
        self.data['HHb'][:, self.ptr] = processed_data['HHb']

        # Advance pointer and wrap around
        self.ptr = (self.ptr + 1) % self.buffer_size

    def repaint_curves(self):
        # Unrolls the ring buffer and updates the plots.
        o2_ordered = np.concatenate((self.data['O2Hb'][:, self.ptr:], self.data['O2Hb'][:, :self.ptr]), axis=1)
        hh_ordered = np.concatenate((self.data['HHb'][:, self.ptr:], self.data['HHb'][:, :self.ptr]), axis=1)

        self._y_autorange_counter += 1
        do_autorange = (self._y_autorange_counter % self._y_autorange_every) == 0

        for i, name in enumerate(config.CHANNEL_NAMES):
            o2_row = o2_ordered[i, :]
            hh_row = hh_ordered[i, :]
            self.plot_curves[name]['O2Hb'].setData(x=self.x_axis, y=o2_row)
            self.plot_curves[name]['HHb'].setData(x=self.x_axis, y=hh_row)

            # Auto-range each plot independently against its own channel data.
            if do_autorange:
                ch_min = min(np.min(o2_row), np.min(hh_row))
                ch_max = max(np.max(o2_row), np.max(hh_row))
                data_range = (ch_max - ch_min)
                padding = max(data_range * 0.1, 0.001)
                self.plots[name].setYRange(ch_min - padding, ch_max + padding)

    def reset(self):
        # Clear all data and repaint as a flat baseline
        self.data['O2Hb'].fill(0.0)
        self.data['HHb'].fill(0.0)
        self.ptr = 0
        self.repaint_curves()