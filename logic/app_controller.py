import time

import numpy as np
from PySide6.QtCore import QObject, QThread, QTimer, Signal

import config
from logic.lsl_client import LSLClient
from logic.data_processor import DataProcessor
from utils.sound_player import SoundPlayer
from utils.enums import CognitiveState
from utils.session_recorder import SessionRecorder
from utils.session_naming import (
    split_name_and_index,
    get_next_index_for_prefix,
    format_name,
    get_today_recordings_folder,
)
from utils.os_helpers import open_folder


# Reconnect tolerance: if the stream drops and comes back within this many ms,
# the in-flight recording is resumed in-place rather than closed.
RECONNECT_TOLERANCE_MS = 5000


class AppController(QObject):
    # Main controller: owns the LSL client thread, data processor, recorder,
    # and alert/audio orchestration.

    streams_found = Signal(list)
    connection_status = Signal(bool)
    processed_data_ready = Signal(dict)
    alert_state_changed = Signal(object)

    # Signals to safely trigger actions on the background thread.
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

        self.recorder = SessionRecorder()

        self.connected_stream_name = None
        self.connected_source_id = None

        self.auto_record_on_connect = False
        self.auto_record_session_name = None

        # Distinguishes a user-clicked Disconnect from a watchdog/error-driven
        # disconnect so we can decide whether to pause-and-wait or stop fully.
        self._user_initiated_disconnect = False

        # Tolerance timer that fires if the stream does not come back in time.
        self._pause_timer = QTimer(self)
        self._pause_timer.setSingleShot(True)
        self._pause_timer.setInterval(RECONNECT_TOLERANCE_MS)
        self._pause_timer.timeout.connect(self._on_pause_timeout)
        self._disconnect_time_ms = None

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

    # ---------- Stream / rate plumbing ----------

    def _emit_sample_rate_info(self):
        self.sample_rate_info_changed.emit(self.detected_stream_rate)

    def _on_sample_rate_detected(self, rate):
        self.detected_stream_rate = float(rate) if rate and rate > 0 else None
        self.data_processor.set_sample_rate(self.detected_stream_rate)
        self._emit_sample_rate_info()

    def set_alert_rules(self, rules):
        self.alert_rules = rules

    def find_streams(self):
        print("Controller: Requesting stream search...")
        self.find_streams_requested.emit()

    def connect_to_stream(self, source_id):
        if self.is_connected:
            return
        self.connected_source_id = source_id
        self.connect_requested.emit(source_id)

    def disconnect_from_stream(self):
        # Explicit user action: do not pause/resume, just stop.
        self._user_initiated_disconnect = True
        self.disconnect_requested.emit()

    # ---------- Connection lifecycle ----------

    def _on_connected(self, stream_name: str):
        self.is_connected = True
        self.connected_stream_name = stream_name

        stream_info = self._current_stream_info()

        # If we are inside the tolerance window for a previous recording and the
        # incoming stream is the same source, resume in-place instead of cutting
        # a new file.
        if self.recorder.can_resume(stream_info):
            self._pause_timer.stop()
            gap_ms = self._compute_gap_ms()
            self.recorder.resume(gap_ms)
            self._disconnect_time_ms = None
            self.connection_status.emit(True)
            return

        # Fresh session: reset processor state and possibly auto-start recording.
        self.data_processor.reset()
        self.connection_status.emit(True)

        if self.auto_record_on_connect and self.auto_record_session_name:
            self.start_recording(self.auto_record_session_name)

    def _on_disconnected(self):
        user_initiated = self._user_initiated_disconnect
        self._user_initiated_disconnect = False

        was_connected = self.is_connected
        self.is_connected = False
        self.connected_stream_name = None
        self.detected_stream_rate = None
        self._emit_sample_rate_info()

        if user_initiated:
            self._pause_timer.stop()
            if self.recorder.is_recording:
                self.stop_recording()
            self.connected_source_id = None
            self._disconnect_time_ms = None
            self.connection_status.emit(False)
            return

        # Watchdog / network drop. Hold the recording open for a tolerance window.
        if was_connected and self.recorder.is_recording and not self.recorder.is_paused:
            self.recorder.pause()
            self._disconnect_time_ms = self._now_ms()
            self._pause_timer.start()

        self.connection_status.emit(False)

    def _on_pause_timeout(self):
        # Tolerance window expired without a reconnect. Close out the recording.
        if self.recorder.is_paused:
            print("Controller: reconnect tolerance expired; stopping recording.")
            self.stop_recording()
        self.connected_source_id = None
        self._disconnect_time_ms = None

    # ---------- Sample processing ----------

    def _on_new_data(self, data):
        if not self.is_connected:
            return

        samples = data.get("samples", [])
        timestamps = data.get("timestamps", [])

        for sample, timestamp in zip(samples, timestamps):
            self._process_one_sample(sample, timestamp)

    def _process_one_sample(self, sample, timestamp):
        try:
            vec = np.asarray(sample, dtype=float)
        except Exception:
            return

        od32 = []
        adc = 0
        event = 0

        if vec.size >= 32:
            od32 = vec[:32].tolist()
        if vec.size >= 33 and np.isfinite(vec[32]):
            adc = int(vec[32])
        if vec.size >= 34 and np.isfinite(vec[33]):
            event = int(vec[33])

        # NaN guard: a single non-finite OD value would propagate through MBLL
        # and through the alert ring buffer. Drop the sample with a sentinel
        # recording row and skip processing.
        od_finite = (len(od32) == 32) and bool(np.isfinite(od32).all())
        if not od_finite:
            self._record_row(od32 if len(od32) == 32 else None, None, None, adc, event, dropped=True)
            return

        try:
            processed = self.data_processor.process_sample_od(sample, self.alert_rules)
        except Exception as ex:
            print(f"Controller: processing failed: {ex}")
            self._record_row(od32, None, None, adc, event, dropped=True)
            return

        if processed is None:
            # Placeholder-only sample (typical at stream start). Record raw row,
            # leave calc as sentinel zeros so files stay row-aligned.
            self._record_row(od32, None, None, adc, event, dropped=False)
            return

        processed["timestamp"] = timestamp
        self.processed_data_ready.emit(processed)
        self._record_row(od32, processed.get("O2Hb"), processed.get("HHb"), adc, event, dropped=False)

        current_state = processed.get("alert_state", CognitiveState.NOMINAL)
        if current_state != self.last_alert_state:
            self.last_alert_state = current_state
            self.alert_state_changed.emit(current_state)
            if current_state == CognitiveState.LOAD:
                self.sound_player.play("alert")
            else:
                self.sound_player.play("nominal")

    def _record_row(self, od32, o2hb, hhb, adc, event, dropped):
        if not self.recorder.is_recording or self.recorder.is_paused:
            return
        self.recorder.write(od32, o2hb, hhb, adc=adc, event=event, dropped=dropped)

    # ---------- Recording control ----------

    def close(self):
        print("Controller: Closing...")
        # If the user closes the window mid-recording, treat that as a manual stop.
        self._user_initiated_disconnect = True
        self._pause_timer.stop()
        self.stop_recording()
        self.disconnect_requested.emit()
        self.lsl_thread.msleep(50)
        self.lsl_thread.quit()
        if not self.lsl_thread.wait(3000):
            print("Controller: LSL thread did not shut down gracefully. Terminating.")
            self.lsl_thread.terminate()

    def set_auto_record_on_connect(self, enabled: bool, session_name: str = None):
        self.auto_record_on_connect = bool(enabled)
        self.auto_record_session_name = session_name

    def start_recording(self, session_name: str):
        if not self.is_connected:
            return
        if self.recorder.is_recording:
            return

        rate = float(self.detected_stream_rate) if self.detected_stream_rate else float(config.SAMPLE_RATE)
        stream_info = self._current_stream_info()
        cfg_snapshot = {
            "DPF": config.DPF,
            "INTEROPTODE_DISTANCE": config.INTEROPTODE_DISTANCE,
            "WAVELENGTH_ORDER": getattr(config, "WAVELENGTH_ORDER", None),
            "EXTINCTION_COEFFICIENTS": getattr(config, "EXTINCTION_COEFFICIENTS", None),
            "CHANNEL_NAMES": getattr(config, "CHANNEL_NAMES", None),
        }
        self.recorder.start(session_name, stream_info, rate, cfg_snapshot)

    def stop_recording(self):
        self.recorder.stop()

    def open_today_recordings_folder(self):
        folder = get_today_recordings_folder(self.recorder.recordings_root)
        open_folder(folder)

    def normalize_session_name(self, text: str) -> str:
        prefix, idx = split_name_and_index(text)
        if not prefix:
            return ""
        if idx is not None:
            return format_name(prefix, idx)
        next_idx = get_next_index_for_prefix(self.recorder.recordings_root, prefix)
        return format_name(prefix, next_idx)

    def get_next_session_name(self, current_text: str | None = None) -> str:
        prefix, idx = split_name_and_index(current_text or "")
        if not prefix:
            prefix = "session"
        next_idx = get_next_index_for_prefix(self.recorder.recordings_root, prefix)
        return format_name(prefix, next_idx)

    def save_recording_notes(self, notes_text: str):
        self.recorder.write_notes(notes_text)

    # ---------- Helpers ----------

    def _current_stream_info(self) -> dict:
        return {
            "name": self.connected_stream_name or "",
            "type": config.STREAM_TYPE or "",
            "source_id": self.connected_source_id or "",
        }

    @staticmethod
    def _now_ms() -> int:
        return int(time.monotonic() * 1000)

    def _compute_gap_ms(self) -> int:
        if self._disconnect_time_ms is None:
            return 0
        return self._now_ms() - self._disconnect_time_ms
