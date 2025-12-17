from PySide6.QtCore import QObject, QThread, Signal
from logic.lsl_client import LSLClient
from logic.data_processor import DataProcessor
from utils.sound_player import SoundPlayer
from utils.enums import CognitiveState


class AppController(QObject):
    # The main controller for the application, handling all backend logic.
    streams_found = Signal(list)
    connection_status = Signal(bool)
    processed_data_ready = Signal(dict)
    alert_state_changed = Signal(object)

    # Signals to safely trigger actions on the background thread
    find_streams_requested = Signal()
    connect_requested = Signal(str)
    disconnect_requested = Signal()
    sample_rate_info_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.lsl_client = LSLClient()
        self.data_processor = DataProcessor()
        self.sound_player = SoundPlayer()
        self.lsl_thread = QThread()

        self.lsl_client.moveToThread(self.lsl_thread)
        self.is_connected = False
        self.last_alert_state = CognitiveState.NOMINAL
        self.alert_rules = {}

        self.detected_stream_rate = None

        # --- Connect controller request signals to client slots ---
        self.find_streams_requested.connect(self.lsl_client.find_streams)
        self.connect_requested.connect(self.lsl_client.connect_to_stream)
        self.disconnect_requested.connect(self.lsl_client.disconnect)

        # --- Connect signals from the client back to the controller's slots ---
        self.lsl_client.streams_found.connect(self.streams_found)
        self.lsl_client.connected.connect(self._on_connected)
        self.lsl_client.disconnected.connect(self._on_disconnected)
        self.lsl_client.new_data_ready.connect(self._on_new_data)
        self.lsl_client.sample_rate_detected.connect(self._on_sample_rate_detected)

        self.lsl_thread.start()

    def _emit_sample_rate_info(self):
        # Emits the detected LSL stream Hz to the UI.
        self.sample_rate_info_changed.emit(self.detected_stream_rate)

    def _on_sample_rate_detected(self, rate):
        # This runs in the controller/UI thread, safe to touch controller state
        self.detected_stream_rate = float(rate) if rate and rate > 0 else None
        self.data_processor.set_sample_rate(self.detected_stream_rate)
        self._emit_sample_rate_info()

    def set_alert_rules(self, rules):
        # Updates the alert rules used by the data processor
        self.alert_rules = rules

    def find_streams(self):
        # Emits a signal to trigger a stream search on the background thread
        print("Controller: Requesting stream search...")
        self.find_streams_requested.emit()

    def connect_to_stream(self, source_id):
        # Emits a signal to trigger a connection on the background thread
        if self.is_connected:
            return

        self.connect_requested.emit(source_id)

    def disconnect_from_stream(self):
        # Emits a signal to trigger a disconnection on the background thread
        self.disconnect_requested.emit()

    def _on_connected(self):
        # Handles the connected signal from the client
        self.is_connected = True
        self.data_processor.reset()
        self.connection_status.emit(True)

    def _on_disconnected(self):
        # Handles the disconnected signal from the client
        self.is_connected = False
        self.detected_stream_rate = None
        self._emit_sample_rate_info()
        self.connection_status.emit(False)

    def _on_new_data(self, data):
        # Ignore any late samples after disconnect
        if not self.is_connected:
            return

        # 1. Standard Processing (No calibration check needed)
        # Processes one OD(+ADC) sample into Hb and state.
        try:
            processed = self.data_processor.process_sample_od(data['raw'], self.alert_rules)
        except Exception as ex:
            print(f"Controller: Processing failed: {ex}")
            return

        if not processed:
            return

        processed['timestamp'] = data['timestamp']
        self.processed_data_ready.emit(processed)

        # 2. Update Audio/State
        current_state = processed.get('alert_state', CognitiveState.NOMINAL)
        if current_state != self.last_alert_state:
            self.last_alert_state = current_state
            self.alert_state_changed.emit(current_state)

            if current_state == CognitiveState.LOAD:
                self.sound_player.play('alert')
            else:
                self.sound_player.play('nominal')

    def close(self):
        # Thread-safely tells the client to disconnect and cleans up the thread.
        print("Controller: Closing...")
        self.disconnect_from_stream()
        self.lsl_thread.msleep(50)
        self.lsl_thread.quit()
        if not self.lsl_thread.wait(3000): # Wait up to 3 seconds
            print("Controller: LSL thread did not shut down gracefully. Terminating.")
            self.lsl_thread.terminate()