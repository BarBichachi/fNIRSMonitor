import time

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

        self.record_start_ms = None

        self._init_ui()
        self._init_plot_timer()
        self._init_record_timer()
        self._init_record_flash_timer()
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
        self.connection_bar.record_button.toggled.connect(self._on_record_toggled)
        self.connection_bar.auto_record_checkbox.toggled.connect(self._on_auto_record_toggled)
        self.connection_bar.filename_input.textChanged.connect(self._on_session_name_changed)

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
        self.connection_bar.auto_record_checkbox.setEnabled(True)

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
            self.controller.set_auto_record_on_connect(self.connection_bar.auto_record_checkbox.isChecked(),
                session_name=self.connection_bar.filename_input.text().strip())

            if self.connection_bar.auto_record_checkbox.isChecked():
                self.connection_bar.record_button.setChecked(True)

            self.plot_widget.reset()
            self.plot_update_timer.start()

        else:
            self._set_analysis_controls_enabled(False)
            if self.connection_bar.record_button.isChecked():
                self.connection_bar.record_button.setChecked(False)
            self._stop_record_timer()
            self._stop_record_flash()
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

    def _init_record_timer(self):
        # Updates the record timer label while recording
        self.record_timer = QTimer(self)
        self.record_timer.setInterval(200)
        self.record_timer.timeout.connect(self._update_record_timer_label)

    def _start_record_timer(self):
        # Starts the UI timer for the recording label
        self.record_start_ms = self._now_ms()
        self.connection_bar.record_timer_label.setText("00:00:00")
        self.record_timer.start()

    def _stop_record_timer(self):
        # Stops the UI timer and resets label
        self.record_timer.stop()
        self.record_start_ms = None
        self.connection_bar.record_timer_label.setText("00:00:00")

    def _update_record_timer_label(self):
        # Updates the HH:MM:SS timer label based on elapsed recording time
        if self.record_start_ms is None:
            return

        elapsed_ms = self._now_ms() - self.record_start_ms
        if elapsed_ms < 0:
            elapsed_ms = 0

        total_sec = elapsed_ms // 1000
        hh = total_sec // 3600
        mm = (total_sec % 3600) // 60
        ss = total_sec % 60

        self.connection_bar.record_timer_label.setText(f"{hh:02d}:{mm:02d}:{ss:02d}")

    def _now_ms(self):
        # Returns current time in ms (monotonic)
        return int(time.monotonic() * 1000)

    def _on_record_toggled(self, checked: bool):
        # Starts/stops recording via controller based on Record toggle
        if checked:
            session_name = self.connection_bar.filename_input.text().strip()
            if not session_name:
                self.connection_bar.record_button.setChecked(False)
                return

            self.controller.start_recording(session_name)

            if self.controller.recorder.is_recording:
                self.connection_bar.record_button.setText("Stop Recording")
                self.connection_bar.filename_input.setEnabled(False)
                self._start_record_timer()
                self._start_record_flash()
            else:
                self.connection_bar.record_button.setChecked(False)
                self.connection_bar.record_button.setText("Record")
                self.connection_bar.filename_input.setEnabled(True)
                self._start_record_flash()
        else:
            self.controller.stop_recording()
            self.connection_bar.record_button.setText("Record")
            self.connection_bar.filename_input.setEnabled(True)
            self._stop_record_timer()
            self._start_record_flash()

    def _on_auto_record_toggled(self, checked: bool):
        # Arms/disarms auto-record on connect
        session_name = self.connection_bar.filename_input.text().strip()
        self.controller.set_auto_record_on_connect(bool(checked), session_name=session_name)

    def _on_session_name_changed(self, _):
        # Keeps controller's auto-record session name in sync with UI
        if self.connection_bar.auto_record_checkbox.isChecked():
            session_name = self.connection_bar.filename_input.text().strip()
            self.controller.set_auto_record_on_connect(True, session_name=session_name)

    def _init_record_flash_timer(self):
        # Flashes the record button while recording
        self.m_RecordFlashOn = False
        self.m_RecordFlashTimer = QTimer(self)
        self.m_RecordFlashTimer.setInterval(450)
        self.m_RecordFlashTimer.timeout.connect(self._toggle_record_flash)

    def _start_record_flash(self):
        # Starts flashing the record button
        self.m_RecordFlashOn = True
        self.connection_bar.record_button.setProperty("flash", True)
        self._repolish_widget(self.connection_bar.record_button)
        self.m_RecordFlashTimer.start()

    def _stop_record_flash(self):
        # Stops flashing the record button and resets style
        if hasattr(self, "m_RecordFlashTimer"):
            self.m_RecordFlashTimer.stop()
        self.m_RecordFlashOn = False
        self.connection_bar.record_button.setProperty("flash", False)
        self._repolish_widget(self.connection_bar.record_button)

    def _toggle_record_flash(self):
        # Toggles the flash property (drives stylesheet)
        if not self.connection_bar.record_button.isChecked():
            self._stop_record_flash()
            return

        self.m_RecordFlashOn = not self.m_RecordFlashOn
        self.connection_bar.record_button.setProperty("flash", self.m_RecordFlashOn)
        self._repolish_widget(self.connection_bar.record_button)

    def _repolish_widget(self, i_Widget):
        # Re-applies stylesheet after dynamic property change
        i_Widget.style().unpolish(i_Widget)
        i_Widget.style().polish(i_Widget)
        i_Widget.update()
