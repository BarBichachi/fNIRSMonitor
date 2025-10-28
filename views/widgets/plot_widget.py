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

    def update_data(self, processed_data):
        # Adds a new data sample to the plot and scrolls the view.

        # --- Shift Data Buffers ---
        # Roll the arrays one position to the left. The oldest data point is discarded.
        self.data['O2Hb'] = np.roll(self.data['O2Hb'], -1, axis=1)
        self.data['HHb'] = np.roll(self.data['HHb'], -1, axis=1)

        # --- Add New Data ---
        # Place the new data sample at the end of the arrays.
        self.data['O2Hb'][:, -1] = processed_data['O2Hb']
        self.data['HHb'][:, -1] = processed_data['HHb']

        # --- Dynamically set Y-Range ---
        # Find the min and max across all channels for both O2Hb and HHb in the buffer.
        global_min = min(np.min(self.data['O2Hb']), np.min(self.data['HHb']))
        global_max = max(np.max(self.data['O2Hb']), np.max(self.data['HHb']))

        # Add a 10% padding to the range for a tighter zoom.
        data_range = global_max - global_min
        padding = data_range * 0.1

        # Handle the edge case where the data is flat to prevent a zero-height plot.
        if padding < 1e-5:  # A very small number
            padding = 0.001  # Set a minimal default padding

        if self.first_plot:
            self.first_plot.setYRange(global_min - padding, global_max + padding)

        # --- Update Plot Curves ---
        # Redraw all curves with the updated data buffers and the fixed x-axis.
        for i, name in enumerate(config.CHANNEL_NAMES):
            self.plot_curves[name]['O2Hb'].setData(x=self.x_axis, y=self.data['O2Hb'][i, :])
            self.plot_curves[name]['HHb'].setData(x=self.x_axis, y=self.data['HHb'][i, :])