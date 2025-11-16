import pyqtgraph as pg
import numpy as np
from PySide6.QtWidgets import QWidget, QGridLayout
import config


class PlotWidget(QWidget):
    # A widget for the main real-time data plot, now arranged in a grid.
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plots = {}
        self.plot_curves = {}
        self._init_ui()

    def _init_ui(self):
        # Initializes the pyqtgraph plots in a grid layout.
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # --- Data Buffers and Fixed X-Axis ---
        self.buffer_size = config.SAMPLE_RATE * 10 # Buffer size is dynamic based on sample rate
        self.x_axis = np.linspace(-10, 0, self.buffer_size)
        self.data = {
            'O2Hb': np.zeros((len(config.CHANNEL_NAMES), self.buffer_size)),
            'HHb': np.zeros((len(config.CHANNEL_NAMES), self.buffer_size))
        }

        # --- Create a Grid of Plots (4 rows, 2 columns) ---
        self.first_plot = None  # Store a reference to the first plot for Y-axis linking
        for i, name in enumerate(config.CHANNEL_NAMES):
            row, col = divmod(i, 2)  # Arrange L/R channels in columns

            # --- Create Plot Widget ---
            plot_widget = pg.PlotWidget()
            self.plots[name] = plot_widget
            layout.addWidget(plot_widget, row, col)

            # --- Configure Plot Aesthetics ---
            plot_widget.setBackground('#1a1a1a')
            plot_widget.showGrid(x=True, y=True, alpha=0.3)
            plot_widget.setLabel('left', 'ΔμM')
            plot_widget.setLabel('bottom', 'Time (s ago)')
            plot_widget.setTitle(name)

            # --- Set Fixed Plot Range ---
            plot_widget.enableAutoRange(x=False, y=False)
            plot_widget.setXRange(-10, 0)
            plot_widget.getViewBox().setMouseEnabled(x=False)  # Disable horizontal panning/zooming

            # --- Link Y-Axes of all plots ---
            if self.first_plot:
                plot_widget.setYLink(self.first_plot)
            else:
                self.first_plot = plot_widget

            # --- Create Plot Curves ---
            o2hb_curve = plot_widget.plot(pen=pg.mkPen(color=(255, 80, 80), width=2), name=f"{name} O2Hb")
            hhb_curve = plot_widget.plot(pen=pg.mkPen(color=(80, 80, 255), width=2), name=f"{name} HHb")
            self.plot_curves[name] = {'O2Hb': o2hb_curve, 'HHb': hhb_curve}

        # --- Disable auto-ranging on the Y-axis to have full manual control ---
        if self.first_plot:
            self.first_plot.getViewBox().disableAutoRange()

    def set_time_window(self, seconds: int, sample_rate: int):
        """Resize buffers/x-axis to always represent the last <seconds> at the given sample_rate."""
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
        """Append one new processed sample at the TRUE data cadence."""
        self.data['O2Hb'] = np.roll(self.data['O2Hb'], -1, axis=1)
        self.data['HHb'] = np.roll(self.data['HHb'], -1, axis=1)
        self.data['O2Hb'][:, -1] = processed_data['O2Hb']
        self.data['HHb'][:, -1] = processed_data['HHb']

    def repaint_curves(self):
        """Only recompute ranges and redraw curves (UI timer)."""
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