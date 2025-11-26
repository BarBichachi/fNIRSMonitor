import numpy as np
import config


class DataProcessor:
    # Handles the scientific calculations and signal quality assessment.
    def __init__(self):
        # Initializes the DataProcessor.
        self.baseline_mean = None
        self._init_mbll_constants()

        # Rolling windows
        self.quality_buffer_size = int(config.SAMPLE_RATE * 10)  # 10 seconds buffer
        self.sample_width = None  # 16 after mapping (8 channels × 2 λ)
        self.raw_buffer = None  # (quality_buffer_size, 16)

        self.alert_history_size = config.ALERT_HISTORY_SECONDS * config.SAMPLE_RATE
        self.alert_history = None  # (8, alert_history_size)

        # Calibration + mapping
        self.calibration_buffer = []  # list of raw rows (np.ndarray)
        self.pair_indices = None  # list of 8 tuples: [(i850, i760), ...]

    # ---------- MBLL ----------
    def _init_mbll_constants(self):
        e_wl1 = config.EXTINCTION_COEFFICIENTS["760nm"]
        e_wl2 = config.EXTINCTION_COEFFICIENTS["850nm"]
        ext = np.array([[e_wl1["O2Hb"], e_wl1["HHb"]],
                        [e_wl2["O2Hb"], e_wl2["HHb"]]], dtype=float)
        self.inverse_extinction_matrix = np.linalg.inv(ext)

    # ---------- Raw-only guards ----------
    def _looks_like_raw(self, vec: np.ndarray) -> bool:
        if vec.size not in config.RAW_ALLOWED_LENGTHS or (vec.size % 2 != 0):
            return False
        if np.any(vec <= 0):
            return False
        return True

    def _assert_raw_or_raise(self, vec: np.ndarray, ctx: str):
    # Handle OxySoft extra trigger channel (33rd value)
        if vec.size == 33:
            vec = vec[:32]

        if not self._looks_like_raw(vec):
            raise ValueError(
                f"Raw-only mode: rejecting non-raw sample in {ctx}. "
                f"Expected positive intensities with length in {sorted(config.RAW_ALLOWED_LENGTHS)}, "
                f"got len={vec.size} (min={vec.min():.6g})."
            )

        # Return the trimmed/validated vector for downstream use
        return vec

    # --- Ensure post-mapping buffers match width (16) ---
    def _ensure_buffers(self, mapped_len: int):
        if (self.sample_width == mapped_len and
            self.raw_buffer is not None and
            self.alert_history is not None):
            return
        self.sample_width = mapped_len  # should be 16
        phys = mapped_len // 2
        self.raw_buffer = np.zeros((self.quality_buffer_size, mapped_len), dtype=float)
        self.alert_history = np.full((phys, self.alert_history_size), False, dtype=bool)
        if self.baseline_mean is None or len(self.baseline_mean) != mapped_len:
            self.baseline_mean = None
            self.calibration_buffer = []


    @staticmethod
    def _is_placeholder(mean_val: float) -> bool:
        return (abs(mean_val - config.PLACEHOLDER_HI) < config.PLACEHOLDER_EPS) or \
               (abs(mean_val - config.PLACEHOLDER_LO) < config.PLACEHOLDER_EPS)

    @staticmethod
    def _pair_variance(calib: np.ndarray, i850: int, i760: int) -> float:
        return float(np.var(calib[:, i850]) + np.var(calib[:, i760]))

    def _detect_active_pairs(self, calib: np.ndarray) -> list[tuple[int, int]]:
        """ Returns 8 pairs (i850, i760).
        Supports incoming calibration rows of length 16 (already 8 pairs) or 32 (Rx1+Rx2).
        Assumes contiguous pairs (0,1), (2,3), ... with wavelength order [850,760]. """

        raw_len = calib.shape[1]
        all_pairs = [(2*i, 2*i + 1) for i in range(raw_len // 2)]

        def select_top4(pairs_slice):
            scored = []
            for i850, i760 in pairs_slice:
                m1, m2 = float(np.mean(calib[:, i850])), float(np.mean(calib[:, i760]))
                if self._is_placeholder(m1) and self._is_placeholder(m2):
                    score = 0.0
                else:
                    score = self._pair_variance(calib, i850, i760)
                scored.append(((i850, i760), score))
            active = [p for p, s in scored if s > config.PAIR_VARIANCE_THRESH]
            if len(active) < 4:
                active = [p for p, _ in sorted(scored, key=lambda x: x[1], reverse=True)[:4]]
            else:
                active = active[:4]
            return active

        if raw_len == 32:
            rx1_pairs = all_pairs[:8]    # 16 values => 8 pairs
            rx2_pairs = all_pairs[8:16]
            return select_top4(rx1_pairs) + select_top4(rx2_pairs)  # 4 + 4

        # raw_len == 16 → exactly 8 pairs: drop obvious placeholders if present
        scored = []
        for i850, i760 in all_pairs:
            m1, m2 = float(np.mean(calib[:, i850])), float(np.mean(calib[:, i760]))
            if self._is_placeholder(m1) and self._is_placeholder(m2):
                score = 0.0
            else:
                score = self._pair_variance(calib, i850, i760)
            scored.append(((i850, i760), score))
        nonzero = [p for p, s in scored if s > config.PAIR_VARIANCE_THRESH]
        if len(nonzero) >= config.EXPECTED_PHYSICAL_CHANNELS:
            return nonzero[:config.EXPECTED_PHYSICAL_CHANNELS]
        return [p for p, _ in sorted(scored, key=lambda x: x[1], reverse=True)
                [:config.EXPECTED_PHYSICAL_CHANNELS]]

    def _map_raw_to_phys(self, raw_vec: np.ndarray) -> np.ndarray:
        """ Map incoming raw to 16-length vector:
        [I850_1, I760_1, ..., I850_8, I760_8] """
        out = np.empty(2 * len(self.pair_indices), dtype=float)
        j = 0
        for i850, i760 in self.pair_indices:
            out[j] = raw_vec[i850]
            out[j + 1] = raw_vec[i760]
            j += 2
        # clamp to positive to avoid log(0)
        np.maximum(out, config.RAW_MIN_POS, out=out)
        return out

    # ---------- Public API ----------
    def start_calibration(self):
        print("Data Processor: Starting new calibration (raw-only).")
        self.calibration_buffer = []
        if self.alert_history is not None:
            self.alert_history.fill(False)
        self.baseline_mean = None
        self.pair_indices = None

    def add_calibration_sample(self, raw_sample):
        raw = np.asarray(raw_sample, dtype=float)
        raw = self._assert_raw_or_raise(raw, "add_calibration_sample")
        self.calibration_buffer.append(raw)

    def finish_calibration(self):
        min_needed = int(config.SAMPLE_RATE * (config.CALIBRATION_DURATION - 2))
        if len(self.calibration_buffer) < max(1, min_needed):
            print("Data Processor: Calibration failed, not enough data.")
            self.calibration_buffer = []
            return False, None

        calib = np.asarray(self.calibration_buffer, dtype=float)
        # quick sanity: every row must look raw
        if not all(self._looks_like_raw(row) for row in calib):
            print("Data Processor: Calibration aborted — input not raw.")
            self.calibration_buffer = []
            return False, None

        # 1) Detect mapping once
        self.pair_indices = self._detect_active_pairs(calib)

        # 2) Map entire calibration window to 16 columns
        mapped_calib = np.stack([self._map_raw_to_phys(row) for row in calib], axis=0)

        # 3) Init buffers and compute baseline
        self._ensure_buffers(mapped_calib.shape[1])  # 16
        self.baseline_mean = np.mean(mapped_calib, axis=0)

        # 4) Cleanup
        self.calibration_buffer = []
        print("Data Processor: New baseline established (8 channels × 2 λ).")
        return True, self.baseline_mean

    def abort_calibration(self):
        print("Data Processor: Calibration aborted.")
        self.calibration_buffer = []

    def check_for_alert(self, o2hb_values, threshold, duration_s):
        is_above = o2hb_values > threshold
        self.alert_history = np.roll(self.alert_history, -1, axis=1)
        self.alert_history[:, -1] = is_above
        need = int(duration_s * config.SAMPLE_RATE)
        recent = self.alert_history[:, -need:]
        return "Cognitive Load" if np.any(np.all(recent, axis=1)) else "Nominal"

    def _calculate_signal_quality(self):
        if self.raw_buffer is None:
            return []
        phys = self.raw_buffer.shape[1] // 2
        states = []
        for i in range(phys):
            ch0 = i * 2  # wavelength #1 trace as proxy
            std_dev = float(np.std(self.raw_buffer[:, ch0]))
            states.append('red' if std_dev < config.QUALITY_STD_LOWER else 'green')
        return states

    def estimate_quality_during_calibration(self):
        # Estimates signal quality for each physical channel
        # based on the calibration_buffer (raw intensities).
        if not self.calibration_buffer:
            return []

        calib = np.asarray(self.calibration_buffer, dtype=float)

        # Limit to last N samples for a stable but responsive estimate
        if calib.shape[0] > self.quality_buffer_size:
            calib = calib[-self.quality_buffer_size:, :]

        raw_len = calib.shape[1]
        phys = raw_len // 2  # 2 wavelengths per channel

        states = []
        for i in range(phys):
            ch0 = 2 * i  # use first wavelength as proxy
            std_dev = float(np.std(calib[:, ch0]))
            if std_dev < config.QUALITY_STD_LOWER:
                states.append("red")
            else:
                states.append("green")

        return states

    def process_sample_with_baseline(self, raw_sample, alert_rules):
        raw = np.asarray(raw_sample, dtype=float)
        raw = self._assert_raw_or_raise(raw, "process_sample_with_baseline")

        if self.pair_indices is None:
            return None  # not calibrated yet

        # 1) map -> 16-width
        mapped = self._map_raw_to_phys(raw)

        # 2) ensure buffers
        self._ensure_buffers(mapped.size)

        # 3) roll + append
        self.raw_buffer[:-1] = self.raw_buffer[1:]
        self.raw_buffer[-1] = mapped

        if self.baseline_mean is None:
            return None

        # 4) ΔOD and MBLL
        delta_od = -np.log(mapped / self.baseline_mean)
        processed = self.calculate_hemoglobin(delta_od)
        processed['quality'] = self._calculate_signal_quality()

        # 5) Alerts
        processed['alert_state'] = self.check_for_alert(
            np.asarray(processed['O2Hb'], dtype=float),
            alert_rules['threshold'],
            alert_rules['duration']
        )
        return processed

    def calculate_hemoglobin(self, delta_od):
        delta_od = np.asarray(delta_od, dtype=float)
        n = delta_od.size // 2
        delta_od_reshaped = delta_od.reshape(n, 2)
        delta_c = self.inverse_extinction_matrix @ delta_od_reshaped.T / (config.DPF * config.INTEROPTODE_DISTANCE)
        return {'O2Hb': delta_c[0, :].tolist(), 'HHb': delta_c[1, :].tolist()}