from typing import Optional

from PySide6.QtCore import QObject, Signal, QTimer
import pylsl
import config


class LSLClient(QObject):
    # LSL transport. Lives on a dedicated QThread (created by the controller).
    # On each timer tick, pulls all available samples from the inlet via
    # pull_chunk and emits them as a single chunk. Lossless by construction
    # as long as the queue downstream (controller -> recorder) keeps up.

    streams_found = Signal(list)
    connected = Signal(str)
    disconnected = Signal()
    # Payload: {'samples': [[...], [...]], 'timestamps': [t1, t2]}.
    new_data_ready = Signal(dict)
    sample_rate_detected = Signal(object)
    # Fired when a stream was found but its metadata did not pass our contract
    # check (channel count, type, etc). Payload is a short human-readable reason.
    # The connection is not entered; controller surfaces this to the UI.
    connection_rejected = Signal(str)

    # Maximum samples to pull per timer tick. A 50 Hz stream with a 20 ms tick
    # produces ~1 sample/tick; 64 is generous headroom for transient backlog.
    PULL_CHUNK_MAX = 64

    # Watchdog: if no samples arrive in this many ms, treat the stream as dead.
    WATCHDOG_MS = 5000

    # Metadata contract: what we require an OxySoft Direct-Channel stream to
    # look like before we accept the connection.
    # 32 = OD only, 33 = OD + ADC, 34 = OD + ADC + Event.
    EXPECTED_CHANNEL_COUNTS = (32, 33, 34)
    EXPECTED_STREAM_TYPE = "NIRS"

    def __init__(self):
        super().__init__()
        self.inlet = None

        self.processing_timer = QTimer(self)
        self.processing_timer.setInterval(self._tick_interval_ms(config.SAMPLE_RATE))
        self.processing_timer.timeout.connect(self._pull_chunk)

        self.watchdog_timer = QTimer(self)
        self.watchdog_timer.setInterval(self.WATCHDOG_MS)
        self.watchdog_timer.setSingleShot(True)
        self.watchdog_timer.timeout.connect(self._on_watchdog_timeout)

    @staticmethod
    def _tick_interval_ms(rate_hz) -> int:
        # Tick once per nominal sample period. Faster ticks pull empty chunks
        # cheaply; slower ticks just add latency. Floor at 1 ms.
        try:
            rate = float(rate_hz) if rate_hz else 0.0
        except (TypeError, ValueError):
            rate = 0.0
        if rate <= 0:
            return 50  # 20 Hz fallback when nothing is known yet
        return max(1, int(round(1000.0 / rate)))

    # ---------- Slots invoked from controller via queued signals ----------

    def find_streams(self) -> None:
        try:
            streams = pylsl.resolve_byprop("type", config.STREAM_TYPE, timeout=2)
        except Exception as ex:
            print(f"LSL Client: resolve_byprop failed: {ex}")
            self.streams_found.emit([])
            return
        stream_infos = [(s.name(), s.source_id()) for s in streams]
        self.streams_found.emit(stream_infos)

    def connect_to_stream(self, source_id: str) -> None:
        try:
            streams = pylsl.resolve_byprop("source_id", source_id, timeout=2)
        except Exception as ex:
            print(f"LSL Client: resolve_byprop({source_id!r}) failed: {ex}")
            self.disconnected.emit()
            return

        if not streams:
            self.disconnected.emit()
            return

        try:
            self.inlet = pylsl.StreamInlet(streams[0])
        except Exception as ex:
            print(f"LSL Client: StreamInlet creation failed: {ex}")
            self.inlet = None
            self.disconnected.emit()
            return

        # Validate the stream's metadata BEFORE we announce a connection.
        # A wrong channel count or stream type means the consumer downstream
        # would silently interpret whatever bytes arrive as OD values.
        reject_reason = self._validate_inlet_metadata()
        if reject_reason is not None:
            print(f"LSL Client: rejecting stream: {reject_reason}")
            self._close_inlet_safely()
            self.connection_rejected.emit(reject_reason)
            self.disconnected.emit()
            return

        rate = self._get_nominal_sample_rate()
        self.connected.emit(streams[0].name())
        self.sample_rate_detected.emit(rate)

        # Sync pull cadence to detected stream rate immediately.
        if rate:
            self.processing_timer.setInterval(self._tick_interval_ms(rate))

        self.processing_timer.start()
        self.watchdog_timer.start()

    def disconnect(self) -> None:
        # Idempotent: safe to call from watchdog and from explicit user action.
        self.processing_timer.stop()
        self.watchdog_timer.stop()
        if self._close_inlet_safely():
            print("LSL Client: stream closed.")
        self.disconnected.emit()

    def _close_inlet_safely(self) -> bool:
        # Returns True if there was an inlet to close.
        inlet = self.inlet
        self.inlet = None
        if inlet is None:
            return False
        try:
            inlet.close_stream()
        except Exception as ex:
            print(f"LSL Client: close_stream failed (ignored): {ex}")
        return True

    # ---------- Metadata validation ----------

    def _validate_inlet_metadata(self) -> Optional[str]:
        if self.inlet is None:
            return "no inlet"

        try:
            info = self.inlet.info()
            ch_count = info.channel_count()
            stream_type = info.type()
        except Exception as ex:
            return f"failed to read stream info: {ex}"

        if stream_type != self.EXPECTED_STREAM_TYPE:
            return (
                f"stream type {stream_type!r} != expected "
                f"{self.EXPECTED_STREAM_TYPE!r}"
            )

        if ch_count not in self.EXPECTED_CHANNEL_COUNTS:
            return (
                f"channel count {ch_count} not in "
                f"{self.EXPECTED_CHANNEL_COUNTS}; expected an OxySoft "
                f"Direct-Channel OD stream (32 OD + optional ADC + Event)"
            )

        # Information-only: log whatever per-channel descriptors the stream
        # publishes. We don't drive channel mapping from this yet because the
        # exact OxySoft 3.2.72 schema needs to be verified on a real device;
        # DataProcessor's hardcoded OctaMon layout stays authoritative until
        # then. This log is also how a user on a new device would learn what
        # their stream actually advertises.
        try:
            self._log_channel_descriptors(info)
        except Exception as ex:
            print(
                f"LSL Client: could not enumerate channel descriptors "
                f"({ex}); continuing with hardcoded layout."
            )

        return None

    def _log_channel_descriptors(self, info) -> None:
        desc = info.desc()
        ch = desc.child("channels").child("channel")
        labels = []
        while not ch.empty():
            label = ch.child_value("label") or "(no label)"
            wavelength = ch.child_value("wavelength") or ""
            ch_type = ch.child_value("type") or ""
            labels.append((label, wavelength, ch_type))
            ch = ch.next_sibling()

        if not labels:
            print("LSL Client: stream advertises no per-channel descriptors.")
            return

        print(f"LSL Client: stream advertises {len(labels)} channel descriptors.")
        # Print at most the first 8 so the log stays readable; first 8 covers
        # one OctaMon receiver's worth of optodes.
        for i, (label, wl, t) in enumerate(labels[:8]):
            print(f"  ch[{i}]: label={label!r} wavelength={wl!r} type={t!r}")

    # ---------- Internal ----------

    def _pull_chunk(self) -> None:
        if self.inlet is None:
            return

        try:
            samples, timestamps = self.inlet.pull_chunk(
                timeout=0.0, max_samples=self.PULL_CHUNK_MAX
            )
        except Exception as ex:
            # Inlet died under us. Let watchdog drive the disconnect path so
            # all the same cleanup happens in one place.
            print(f"LSL Client: pull_chunk failed: {ex}")
            return

        if not samples:
            return

        # Successful read resets the watchdog.
        self.watchdog_timer.start()
        self.new_data_ready.emit({"samples": samples, "timestamps": timestamps})

    def _get_nominal_sample_rate(self):
        if self.inlet is None:
            return None
        try:
            info = self.inlet.info()
            rate = info.nominal_srate()
        except Exception as ex:
            print(f"LSL Client: nominal_srate() failed: {ex}")
            return None
        if rate is None or rate <= 0:
            return None
        return float(rate)

    def _on_watchdog_timeout(self) -> None:
        print("LSL Client: watchdog fired; stream considered dead.")
        self.disconnect()
