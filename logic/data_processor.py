import numpy as np
import config
from utils.enums import CognitiveState


class DataProcessor:
    # Handles the scientific calculations and signal quality assessment.
    def __init__(self):
        # Initializes the DataProcessor.
        self._init_mbll_constants()

        # Rolling windows
        self.quality_buffer_size = int(config.SAMPLE_RATE * 10)  # 10 seconds buffer
        self.sample_width = None  # 16 after mapping (8 channels × 2 λ)
        self.raw_buffer = None  # (quality_buffer_size, 16)

        self.alert_history_size = config.ALERT_HISTORY_SECONDS * config.SAMPLE_RATE
        self.alert_history = None  # (8, alert_history_size)
        self.od_indices = None  # Maps OxySoft OD vector (32) -> 8ch×2λ (16)

        self.alert_ptr = 0  # Write index into alert history ring buffer
        self.baseline_od = None

    def reset(self):
        # Clears session state.
        self.raw_buffer = None
        self.alert_history = None
        self.od_indices = None
        self.sample_width = None
        self.alert_ptr = 0
        self.baseline_od = None

    def _init_od_indices(self):
        # Builds indices for 8 channels × 2 wavelengths from OxySoft OD (Rx/L) ordering.
        def rx1(l): return (l - 1)  # L1..L16 -> 0..15

        def rx2(l): return 16 + (l - 1)  # L1..L16 -> 16..31

        self.od_indices = [
            (rx1(1), rx1(2)),  # Ch0: Rx1 Tx1 (850,760)
            (rx1(3), rx1(4)),  # Ch1: Rx1 Tx2
            (rx1(5), rx1(6)),  # Ch2: Rx1 Tx3
            (rx1(7), rx1(8)),  # Ch3: Rx1 Tx4
            (rx2(9), rx2(10)),  # Ch4: Rx2 Tx5
            (rx2(11), rx2(12)),  # Ch5: Rx2 Tx6
            (rx2(13), rx2(14)),  # Ch6: Rx2 Tx7
            (rx2(15), rx2(16)),  # Ch7: Rx2 Tx8
        ]

    def _map_od_to_8ch(self, od_vec):
        # Maps OxySoft OD vector (32) into 8 channels × 2 wavelengths (16).
        if self.od_indices is None:
            self._init_od_indices()

        out = np.empty(16, dtype=float)
        j = 0
        for i850, i760 in self.od_indices:
            out[j] = od_vec[i850]
            out[j + 1] = od_vec[i760]
            j += 2

        return out

    # ---------- MBLL ----------
    def _init_mbll_constants(self):
        e_wl1 = config.EXTINCTION_COEFFICIENTS["760nm"]
        e_wl2 = config.EXTINCTION_COEFFICIENTS["850nm"]
        ext = np.array([[e_wl1["O2Hb"], e_wl1["HHb"]],
                        [e_wl2["O2Hb"], e_wl2["HHb"]]], dtype=float)
        self.inverse_extinction_matrix = np.linalg.inv(ext)

    # --- Ensure post-mapping buffers match width (16) ---
    def _ensure_buffers(self, mapped_len: int):
        if (self.sample_width == mapped_len and
                self.raw_buffer is not None and
                self.alert_history is not None):
            return

        self.sample_width = mapped_len
        phys = mapped_len // 2

        self.raw_buffer = np.zeros((self.quality_buffer_size, mapped_len), dtype=float)
        # Reset alert history
        self.alert_history = np.full((phys, self.alert_history_size), False, dtype=bool)
        self.alert_ptr = 0

    def check_for_alert(self, o2hb_values, threshold, duration_s, min_channels=2):
        # Detects sustained threshold exceedance in >=min_channels channels
        is_above = np.asarray(o2hb_values) > threshold

        self.alert_history[:, self.alert_ptr] = is_above
        self.alert_ptr = (self.alert_ptr + 1) % self.alert_history.shape[1]

        need = int(duration_s * config.SAMPLE_RATE)
        need = max(1, min(need, self.alert_history.shape[1]))

        end = self.alert_ptr
        idx = (np.arange(end - need, end) % self.alert_history.shape[1])

        recent = self.alert_history[:, idx]  # (8, need)
        sustained = np.all(recent, axis=1)  # (8,)
        return CognitiveState.LOAD if (np.sum(sustained) >= min_channels) else CognitiveState.NOMINAL

    def set_sample_rate(self, hz: float):
        # Updates internal sample-rate-dependent buffer sizes.
        hz = float(hz) if hz and hz > 0 else None
        if hz is None:
            return

        config.SAMPLE_RATE = hz  # keeps rest of app consistent
        self.quality_buffer_size = int(hz * 10)
        self.alert_history_size = int(config.ALERT_HISTORY_SECONDS * hz)

        # Force reallocation on next sample.
        self.raw_buffer = None
        self.alert_history = None
        self.sample_width = None

    def _calculate_signal_quality(self, adc_value=None):
        # Returns per-channel quality states using ADC if available, otherwise OD sanity checks.
        if adc_value is not None:
            if adc_value >= config.PLACEHOLDER_HI - config.PLACEHOLDER_EPS:
                return ['red'] * config.EXPECTED_PHYSICAL_CHANNELS
            return ['green'] * config.EXPECTED_PHYSICAL_CHANNELS

        if self.raw_buffer is None:
            return []

        latest = self.raw_buffer[-1]
        states = []
        for i in range(latest.size // 2):
            w1 = latest[i * 2]
            w2 = latest[i * 2 + 1]
            states.append('green' if (np.isfinite(w1) and np.isfinite(w2)) else 'red')
        return states

    def process_sample_od(self, lsl_sample, alert_rules):
        # Processes one LSL sample containing OxySoft OD (+ optional ADC) into Hb changes.
        vec = np.asarray(lsl_sample, dtype=float)

        adc_value = None

        if vec.size == 32:
            od_vec = vec
        elif vec.size == 33:
            od_vec = vec[:32]
            adc_value = vec[32]
        elif vec.size >= 34:
            od_vec = vec[:32]
            adc_value = vec[32]  # assume ADC is right after OD
            # vec[33] could be event/trigger; ignored here
        else:
            raise ValueError(f"Expected at least 32 OD values. Got {vec.size}")

        # Skips placeholder-only samples (often seen at stream start).
        if np.allclose(od_vec, config.PLACEHOLDER_HI, atol=config.PLACEHOLDER_EPS):
            return None

        mapped_od = self._map_od_to_8ch(od_vec)
        self._ensure_buffers(mapped_od.size)

        # Initialize baseline from the first valid mapped sample
        if self.baseline_od is None:
            self.baseline_od = mapped_od.copy()

        delta_od = mapped_od - self.baseline_od

        self.raw_buffer[:-1] = self.raw_buffer[1:]
        self.raw_buffer[-1] = delta_od

        processed = self.calculate_hemoglobin(delta_od)
        processed['quality'] = self._calculate_signal_quality(adc_value)

        thresh = alert_rules.get('threshold', 4.0)
        dur = alert_rules.get('duration', 3)
        processed['alert_state'] = self.check_for_alert(np.asarray(processed['O2Hb']), thresh, dur)

        return processed

    def calculate_hemoglobin(self, delta_od):
        # Converts ΔOD (per channel, 2 wavelengths) into ΔHb (µM) using MBLL.
        delta_od = np.asarray(delta_od, dtype=float)
        n = delta_od.size // 2
        reshaped = delta_od.reshape(n, 2)  # [850,760]

        od_760_850 = reshaped[:, [1, 0]].T  # -> [760,850] rows

        delta_c = (self.inverse_extinction_matrix @ od_760_850) / (config.DPF * config.INTEROPTODE_DISTANCE)
        delta_c = delta_c * 1000.0  # mM -> µM

        return {'O2Hb': delta_c[0, :].tolist(), 'HHb': delta_c[1, :].tolist()}