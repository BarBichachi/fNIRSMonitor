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

        # Data buffers
        self.buffer_size = max(1, int(config.SAMPLE_RATE * 10))
        self.x_axis = np.linspace(-10, 0, self.buffer_size, endpoint=False)
        self.data = {
            'O2Hb': np.zeros((len(config.CHANNEL_NAMES), self.buffer_size)),
            'HHb': np.zeros((len(config.CHANNEL_NAMES), self.buffer_size))
        }

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
            plot_widget.setXRange(self.x_axis[0], self.x_axis[-1], padding=0)

            # Disable user panning/zoom
            vb = plot_widget.getViewBox()
            vb.setMouseEnabled(x=False, y=False)

            # Softer axis colors
            plot_widget.getAxis('bottom').setPen(axis_color)
            plot_widget.getAxis('left').setPen(axis_color)
            plot_widget.getAxis('bottom').setTextPen(axis_color)
            plot_widget.getAxis('left').setTextPen(axis_color)

            # Link Y-axes
            if self.first_plot is None:
                self.first_plot = plot_widget
                self.first_plot.getViewBox().disableAutoRange()
            else:
                plot_widget.setYLink(self.first_plot)

            # --- Curves: O2Hb blue, HHb red ---------------------------------
            o2hb_curve = plot_widget.plot(
                pen=pg.mkPen((100, 181, 246), width=2),  # blue
                name=f"{name} O2Hb"
            )
            hhb_curve = plot_widget.plot(
                pen=pg.mkPen((239, 83, 80), width=2),   # red
                name=f"{name} HHb"
            )
            self.plot_curves[name] = {'O2Hb': o2hb_curve, 'HHb': hhb_curve}

            layout.addWidget(frame, row, col)

    def set_time_window(self, seconds: int, sample_rate: int):
        # Resize buffers/x-axis to always represent the last <seconds> at the given sample_rate
        if sample_rate is None or sample_rate <= 0:
            return

        new_len = max(1, int(seconds * sample_rate))
        new_x = np.linspace(-seconds, 0, new_len, endpoint=False)

        # Preserve history tail
        old_O2 = self.data['O2Hb']
        old_HH = self.data['HHb']
        n_ch = old_O2.shape[0]
        keep = min(old_O2.shape[1], new_len)

        self.data['O2Hb'] = np.zeros((n_ch, new_len), dtype=float)
        self.data['HHb'] = np.zeros((n_ch, new_len), dtype=float)

        if keep:
            self.data['O2Hb'][:, -keep:] = old_O2[:, -keep:]
            self.data['HHb'][:, -keep:] = old_HH[:, -keep:]

        self.buffer_size = new_len
        self.x_axis = new_x

        if self.first_plot:
            self.first_plot.setXRange(self.x_axis[0], self.x_axis[-1], padding=0)

    def push_sample(self, processed_data):
        # Append one new processed sample at the TRUE data cadence
        self.data['O2Hb'] = np.roll(self.data['O2Hb'], -1, axis=1)
        self.data['HHb'] = np.roll(self.data['HHb'], -1, axis=1)
        self.data['O2Hb'][:, -1] = processed_data['O2Hb']
        self.data['HHb'][:, -1] = processed_data['HHb']

    def repaint_curves(self):
        # Only recompute ranges and redraw curves (UI timer)
        global_min = min(np.min(self.data['O2Hb']), np.min(self.data['HHb']))
        global_max = max(np.max(self.data['O2Hb']), np.max(self.data['HHb']))
        data_range = (global_max - global_min)
        padding = max(data_range * 0.1, 0.001)

        if self.first_plot:
            self.first_plot.setYRange(global_min - padding, global_max + padding)
            self.first_plot.setXRange(self.x_axis[0], self.x_axis[-1], padding=0)

        for i, name in enumerate(config.CHANNEL_NAMES):
            self.plot_curves[name]['O2Hb'].setData(x=self.x_axis, y=self.data['O2Hb'][i, :])
            self.plot_curves[name]['HHb'].setData(x=self.x_axis, y=self.data['HHb'][i, :])

    def reset(self):
        # Clear all data and repaint as a flat baseline
        self.data['O2Hb'].fill(0.0)
        self.data['HHb'].fill(0.0)
        self.repaint_curves()