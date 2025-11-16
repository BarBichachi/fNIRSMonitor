from PySide6.QtCore import QObject, Signal, QTimer
import pylsl
from logic.data_processor import DataProcessor
import config

class LSLClient(QObject):
    # This class handles all LSL communication and data processing using a non-blocking timer.
    streams_found = Signal(list)
    connected = Signal(str)
    disconnected = Signal()
    new_data_ready = Signal(dict)

    def __init__(self):
        super().__init__()
        self.inlet = None
        self.data_processor = DataProcessor()

        # --- Non-Blocking Timer ---
        self.processing_timer = QTimer(self)
        self.processing_timer.setInterval(1000 // config.SAMPLE_RATE)
        self.processing_timer.timeout.connect(self._pull_sample)

        # --- Watchdog Timer for Auto-Disconnect ---
        self.watchdog_timer = QTimer(self)
        self.watchdog_timer.setInterval(5000) # 5 seconds
        self.watchdog_timer.setSingleShot(True) # It will only fire once if not reset
        self.watchdog_timer.timeout.connect(self.disconnect)

    def find_streams(self):
        # Finds all available LSL streams of type 'fNIRS' on the network
        streams = pylsl.resolve_byprop('type', config.STREAM_TYPE, timeout=2)
        stream_infos = [(s.name(), s.source_id()) for s in streams]
        self.streams_found.emit(stream_infos)

    def connect_to_stream(self, source_id):
        # Connects to a specific stream using its unique source_id
        streams = pylsl.resolve_byprop('source_id', source_id, timeout=2)
        if streams:
            self.inlet = pylsl.StreamInlet(streams[0])
            self.connected.emit(streams[0].name())
            self.processing_timer.start()
            self.watchdog_timer.start()
        else:
            self.disconnected.emit()

    def _pull_sample(self):
        # This method is called repeatedly by the QTimer to get raw data
        if not self.inlet:
            return

        # Pull a sample without blocking the thread for long
        sample, timestamp = self.inlet.pull_sample(timeout=0.0)

        print("LSL Client: Pulled sample:", sample)
        if sample:
            # Reset the watchdog timer since we received data
            self.watchdog_timer.start()
            # Emit the raw data for the controller to handle
            self.new_data_ready.emit({'raw': sample, 'timestamp': timestamp})

    def get_nominal_sample_rate(self):
        # Return the nominal LSL sample rate of the connected stream, or None
        if self.inlet is None:
            return None

        info = self.inlet.info()
        rate = info.nominal_srate()

        if rate is None or rate <= 0:
            return None

        return float(rate)

    def update_processing_interval(self, hz: float):
        # Adjust the pull cadence to match the chosen processing Hz
        if hz is not None and hz > 0:
            interval_ms = max(1, int(1000 // hz))
            self.processing_timer.setInterval(interval_ms)

    def disconnect(self):
        # Stops the timer and disconnects from the stream
        self.processing_timer.stop()
        self.watchdog_timer.stop()
        if self.inlet:
            print("LSL Client: Watchdog timed out or disconnect called. Closing stream.")
            self.inlet.close_stream()
        self.inlet = None
        self.disconnected.emit()