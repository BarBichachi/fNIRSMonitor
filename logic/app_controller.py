from PySide6.QtCore import QObject, QThread, Signal, QTimer

import config
import numpy as np
from logic.lsl_client import LSLClient
from logic.data_processor import DataProcessor
from utils.sound_player import SoundPlayer


class AppController(QObject):
    # The main controller for the application, handling all backend logic.
    streams_found = Signal(list)
    connection_status = Signal(bool, str)
    processed_data_ready = Signal(dict)
    alert_state_changed = Signal(str)

    # Calibration Signals
    calibration_started = Signal()
    calibration_progress = Signal(int)
    calibration_finished = Signal(bool, object) # Emits success (bool) and baseline_data (object/None)

    # Signals to safely trigger actions on the background thread
    find_streams_requested = Signal()
    connect_requested = Signal(str)
    disconnect_requested = Signal()

    def __init__(self, parent=None):
        # Initializes the AppController.
        super().__init__(parent)
        self.lsl_client = LSLClient()
        self.data_processor = DataProcessor()
        self.sound_player = SoundPlayer()
        self.lsl_thread = QThread()
        self.lsl_client.moveToThread(self.lsl_thread)
        self.is_calibrating = False
        self.last_alert_state = "Nominal"
        self.alert_rules = {}

        # --- Calibration Timer ---
        self.calibration_timer = QTimer(self)
        self.calibration_timer.setInterval(1000) # 1 second interval
        self.calibration_timer.timeout.connect(self._update_calibration_progress)
        self.calibration_seconds_left = 0

        # --- Connect controller request signals to client slots ---
        self.find_streams_requested.connect(self.lsl_client.find_streams)
        self.connect_requested.connect(self.lsl_client.connect_to_stream)
        self.disconnect_requested.connect(self.lsl_client.disconnect)

        # --- Connect signals from the client back to the controller's slots ---
        self.lsl_client.streams_found.connect(self.streams_found)
        self.lsl_client.connected.connect(self._on_connected)
        self.lsl_client.disconnected.connect(self._on_disconnected)
        self.lsl_client.new_data_ready.connect(self._on_new_data)

        self.lsl_thread.start()

    def set_alert_rules(self, rules):
        # Updates the alert rules used by the data processor.
        self.alert_rules = rules

    def start_calibration(self):
        # Starts the calibration process.
        if self.is_calibrating or not self.lsl_client.inlet:
            return

        print("Controller: Starting calibration.")
        self.is_calibrating = True
        self.data_processor.start_calibration()
        self.calibration_seconds_left = config.CALIBRATION_DURATION
        self.calibration_timer.start()
        self.calibration_started.emit()
        self.calibration_progress.emit(self.calibration_seconds_left)

    def abort_calibration(self):
        # Aborts the calibration process.
        if not self.is_calibrating:
            return

        print("Controller: Aborting calibration.")
        self.calibration_timer.stop()
        self.is_calibrating = False
        self.data_processor.abort_calibration()
        self.calibration_finished.emit(False, None)

    def _update_calibration_progress(self):
        # Updates the countdown and finishes calibration when timer ends.
        self.calibration_seconds_left -= 1
        self.calibration_progress.emit(self.calibration_seconds_left)
        if self.calibration_seconds_left <= 0:
            self.calibration_timer.stop()
            self.is_calibrating = False
            success, baseline = self.data_processor.finish_calibration()
            self.calibration_finished.emit(success, baseline)

    def find_streams(self):
        # Emits a signal to trigger a stream search on the background thread.
        print("Controller: Requesting stream search...")
        self.find_streams_requested.emit()

    def connect_to_stream(self, source_id):
        # Emits a signal to trigger a connection on the background thread.
        if source_id:
            self.connect_requested.emit(source_id)

    def disconnect_from_stream(self):
        # Emits a signal to trigger a disconnection on the background thread.
        self.disconnect_requested.emit()

    def _on_connected(self, stream_name):
        # Handles the connected signal from the client and forwards it.
        self.connection_status.emit(True, stream_name)

    def _on_disconnected(self):
        # Handles the disconnected signal from the client and forwards it.
        self.connection_status.emit(False, "")

    def _on_new_data(self, data):
        # Routes incoming data to the correct processor method based on state.
        if self.is_calibrating:
            self.data_processor.add_calibration_sample(data['raw'])
        else:
            raw_sample = np.asarray(data['raw'], dtype=float)

            # Handle possible trigger/timestamp channel
            if raw_sample.size == 33:
                raw_sample = raw_sample[:32]

            processed = self.data_processor.process_sample_with_baseline(raw_sample, self.alert_rules)
            if processed:
                processed['timestamp'] = data['timestamp']
                self.processed_data_ready.emit(processed)

                # --- Check if alert state has changed and notify the UI ---
                current_alert_state = processed.get('alert_state', 'Nominal')
                if current_alert_state != self.last_alert_state:
                    self.last_alert_state = current_alert_state
                    self.alert_state_changed.emit(current_alert_state)
                    # --- Play sound based on state change ---
                    if current_alert_state == "Cognitive Load":
                        self.sound_player.play('alert')
                        print("CONTROLLER: Playing 'Cognitive Load' sound.")
                    else:
                        self.sound_player.play('nominal')
                        print("CONTROLLER: Playing 'Nominal' sound.")

    def close(self):
        # Thread-safely tells the client to disconnect and cleans up the thread.
        print("Controller: Closing...")
        self.disconnect_from_stream()
        self.lsl_thread.quit()
        if not self.lsl_thread.wait(3000): # Wait up to 3 seconds
            print("Controller: LSL thread did not shut down gracefully. Terminating.")
            self.lsl_thread.terminate()