from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QApplication
import config

from views.widgets.connection_bar import ConnectionBar
from views.widgets.control_sidebar import ControlSidebar
from views.widgets.alert_sidebar import AlertSidebar
from views.widgets.plot_widget import PlotWidget
from logic.app_controller import AppController
from utils.stylesheet import load_stylesheet
from utils.enums import CognitiveState


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
        central_widget.setObjectName("MainBackground")
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

    def _init_plot_timer(self):
        # A dedicated timer for updating the plot at a smooth visual frame rate.
        self.plot_update_timer = QTimer(self)
        self.plot_update_timer.setInterval(16) # ~60 FPS
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
        self.controller.sample_rate_info_changed.connect(self._on_sample_rate_info_changed)

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
        self.connection_bar.filename_input.setEnabled(enabled)
        self.connection_bar.record_timer_label.setEnabled(enabled)
        self.alert_sidebar.rules_group.setEnabled(enabled)

    def _handle_refresh_clicked(self):
        # Disables button, shows indicator, and tells controller to search.
        self.connection_bar.refresh_button.setEnabled(False)
        self.connection_bar.search_indicator_label.show()
        QApplication.processEvents()
        self.controller.find_streams()

    def _toggle_connection(self):
        # Connects or disconnects based on current button state.
        if self.connection_bar.connect_button.text() == "Connect":
            stream_id = self.connection_bar.stream_dropdown.currentData()
            if not stream_id:
                return
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

    def _update_connection_status(self, is_connected):
        # Updates the UI elements to reflect the current connection status.
        if is_connected:
            self.connection_bar.connect_button.setText("Disconnect")
            self.connection_bar.set_status_connected(True)
            self.connection_bar.refresh_button.setEnabled(False)
            self._set_analysis_controls_enabled(True)
            self.plot_widget.reset()
            self.plot_update_timer.start()

        else:
            self._set_analysis_controls_enabled(False)
            self.connection_bar.connect_button.setText("Connect")
            self.connection_bar.set_status_connected(False)
            self.connection_bar.refresh_button.setEnabled(True)
            self.plot_update_timer.stop()
            self.plot_widget.reset()
            self.control_sidebar.reset_signals_quality_indicators()
            self.control_sidebar.set_sample_rate_info(None)
            self.alert_sidebar.update_state_indicator(CognitiveState.NOMINAL)
            self._handle_refresh_clicked()

    def _on_processed_data(self, processed_data):
        # 1. Push into ring buffer
        self.plot_widget.push_sample(processed_data)

        # 2. Quality UI update
        if 'quality' in processed_data:
            self.control_sidebar.update_signals_quality_indicators(processed_data['quality'])

    def _update_plot(self):
        # Called by the timer to update the plot with the latest data.
        self.plot_widget.repaint_curves()

    def _on_sample_rate_info_changed(self, detected_hz):
        # Updates the UI labels and plot window using detected stream rate.
        self.control_sidebar.set_sample_rate_info(detected_hz)

        if detected_hz:
            self.plot_widget.set_time_window(10, int(detected_hz))

    def closeEvent(self, event):
        # Ensures the controller cleans up its resources when the app closes.
        print("Main window: Close event triggered.")
        self.controller.close()
        event.accept()