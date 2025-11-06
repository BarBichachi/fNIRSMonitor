import numpy as np
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFrame, QApplication
import config

# Import UI components and the AppController
from views.widgets.connection_bar import ConnectionBar
from views.widgets.control_sidebar import ControlSidebar
from views.widgets.alert_sidebar import AlertSidebar
from views.widgets.marker_bar import MarkerBar
from views.widgets.plot_widget import PlotWidget
from views.widgets.calibration_dialog import CalibrationDialog
from logic.app_controller import AppController
from utils.stylesheet import load_stylesheet


class MainWindow(QMainWindow):
    # The main application window (View). It is responsible for displaying the UI.
    def __init__(self):
        super().__init__()
        self.setWindowTitle(config.APP_NAME)
        self.setGeometry(100, 100, config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        self.setStyleSheet(load_stylesheet())

        # Create the controller that will manage all logic
        self.controller = AppController(self)

        # A variable to hold the most recent data sample
        self.latest_data = None

        self._init_ui()
        self._init_plot_timer()
        self._connect_signals()

        # --- Set initial UI state ---
        self._set_analysis_controls_enabled(False) # Disable controls on startup
        self._update_controller_rules()

        # Trigger the initial stream search on startup
        self._handle_refresh_clicked()

    def _init_ui(self):
        # Initializes the main UI layout by assembling the widget components.

        # --- Central Widget & Main Layout ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_v_layout = QVBoxLayout(central_widget)

        # --- Top Connection Bar ---
        self.connection_bar = ConnectionBar()
        main_v_layout.addWidget(self.connection_bar)

        # --- Main Content Area (Layout) ---
        main_h_layout = QHBoxLayout()

        # --- Left Control Sidebar ---
        self.control_sidebar = ControlSidebar()
        main_h_layout.addWidget(self.control_sidebar)

        # --- Center Plot Area ---
        self.plot_widget = PlotWidget()
        main_h_layout.addWidget(self.plot_widget, stretch=1)

        # --- Right Alert Sidebar ---
        self.alert_sidebar = AlertSidebar()
        main_h_layout.addWidget(self.alert_sidebar)

        main_v_layout.addLayout(main_h_layout, stretch=1)

        # --- Bottom Marker Bar ---
        self.marker_bar = MarkerBar()
        main_v_layout.addWidget(self.marker_bar)

        # --- Create Calibration Dialog ---
        self.calibration_dialog = CalibrationDialog(self)

    def _init_plot_timer(self):
        # A dedicated timer for updating the plot at a smooth visual frame rate.
        self.plot_update_timer = QTimer(self)
        self.plot_update_timer.setInterval(10)
        self.plot_update_timer.timeout.connect(self._update_plot)

    def _connect_signals(self):
        # Connects UI actions to the controller and controller signals to UI updates
        self.connection_bar.refresh_button.clicked.connect(self._handle_refresh_clicked)
        self.connection_bar.connect_button.clicked.connect(self._toggle_connection)

        # The view now listens for the final, processed data
        self.controller.streams_found.connect(self._update_stream_dropdown)
        self.controller.connection_status.connect(self._update_connection_status)
        self.controller.processed_data_ready.connect(self._on_processed_data)
        self.controller.alert_state_changed.connect(self.alert_sidebar.update_state_indicator)

        # Connect Calibration Signals
        self.alert_sidebar.calibrate_button.clicked.connect(self.controller.start_calibration)
        self.calibration_dialog.stop_requested.connect(self.controller.abort_calibration)
        self.controller.calibration_started.connect(self.calibration_dialog.exec)
        self.controller.calibration_progress.connect(self.calibration_dialog.update_countdown)
        self.controller.calibration_finished.connect(self._on_calibration_finished)

        # Connect Alert Rule UI to Controller
        self.alert_sidebar.threshold_spinbox.valueChanged.connect(self._update_controller_rules)
        self.alert_sidebar.duration_spinbox.valueChanged.connect(self._update_controller_rules)

    def _update_controller_rules(self):
        # Sends the current alert rule values from the UI to the controller.
        rules = self.alert_sidebar.get_alert_rules()
        self.controller.set_alert_rules(rules)

    def _set_analysis_controls_enabled(self, enabled):
        # Enables or disables all controls that require a calibrated connection.
        self.connection_bar.record_button.setEnabled(enabled)
        self.alert_sidebar.calibrate_button.setEnabled(enabled)
        self.alert_sidebar.rules_group.setEnabled(enabled)
        self.marker_bar.setEnabled(enabled)

    def _on_calibration_finished(self, success, baseline_data):
        # Handles the result of the calibration process.
        self.calibration_dialog.close()
        self._set_analysis_controls_enabled(success)

        if success and baseline_data is not None:
            # --- Format the baseline data for display ---
            detailed_text = "Average Raw Intensity Baseline:\n"
            for i in range(len(config.CHANNEL_NAMES)):
                # Average the two wavelengths for each physical channel
                avg_intensity = np.mean(baseline_data[i * 2: i * 2 + 2])
                detailed_text += f"  {config.CHANNEL_NAMES[i]}: {avg_intensity:.2f}\n"

            self.calibration_dialog.show_message("Success", "Baseline calibration completed successfully.",
                                                 detailed_text)
        else:
            self.calibration_dialog.show_message("Failed", "Baseline calibration failed or was aborted.")

    def _handle_refresh_clicked(self):
        # Disables button, shows indicator, and tells controller to search.
        self.connection_bar.refresh_button.setEnabled(False)
        self.connection_bar.search_indicator_label.show()
        QApplication.processEvents()
        self.controller.find_streams()

    def _toggle_connection(self):
        # Tells the controller to connect or disconnect based on the button text.
        if self.connection_bar.connect_button.text() == "Connect":
            stream_id = self.connection_bar.stream_dropdown.currentData()
            self.controller.connect_to_stream(stream_id)
        else:
            self.controller.disconnect_from_stream()

    def _update_stream_dropdown(self, streams):
        # Updates the dropdown and manages the connect button's state.
        dropdown = self.connection_bar.stream_dropdown
        dropdown.clear()
        if streams:
            for name, source_id in streams:
                dropdown.addItem(name, source_id)
            self.connection_bar.connect_button.setEnabled(True)  # Enable connect button
        else:
            dropdown.addItem("No streams found")
            self.connection_bar.connect_button.setEnabled(False)  # Disable connect button

        self.connection_bar.search_indicator_label.hide()
        self.connection_bar.refresh_button.setEnabled(True)

    def _update_connection_status(self, is_connected, stream_name):
        # Updates the UI elements to reflect the current connection status.
        if is_connected:
            self.connection_bar.connect_button.setText("Disconnect")
            self.connection_bar.status_indicator.setStyleSheet("color: #388e3c;")
            self.connection_bar.refresh_button.setEnabled(False)
            self.plot_widget.set_time_window(10, int(config.SAMPLE_RATE))
            self.plot_update_timer.start()
            self.alert_sidebar.calibrate_button.setEnabled(True)
            self.controller.start_calibration()
        else:
            self._set_analysis_controls_enabled(False)
            self.connection_bar.connect_button.setText("Connect")
            self.connection_bar.status_indicator.setStyleSheet("color: #d32f2f;")
            self.connection_bar.refresh_button.setEnabled(True)
            self.plot_update_timer.stop()
            self._handle_refresh_clicked()

    def _on_processed_data(self, processed_data):
        # push into ring buffer at actual data cadence
        self.plot_widget.push_sample(processed_data)

        # keep your quality UI update
        if 'quality' in processed_data:
            self.control_sidebar.update_quality_indicators(processed_data['quality'])

    def _update_plot(self):
        # Called by the timer to update the plot with the latest data.
        self.plot_widget.repaint_curves()

    def closeEvent(self, event):
        # Ensures the controller cleans up its resources when the app closes.
        print("Main window: Close event triggered.")
        self.controller.close()
        event.accept()