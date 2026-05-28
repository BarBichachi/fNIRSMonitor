from collections import deque
from typing import Optional

import numpy as np

import config
from logic.signal_filter import BandpassFilter
from utils.enums import CognitiveState


# Number of physical channels (post-mapping) and wavelengths per channel.
# Used as the filter dimensionality (16 = 8 O2Hb + 8 HHb).
_N_PHYSICAL = 8
_N_FILTERED = _N_PHYSICAL * 2


class DataProcessor:
    # Owns MBLL math, baseline state, signal conditioning, and the alert
    # ring buffer. One instance per LSL connection; reset() between sessions.

    def __init__(self):
        self._init_mbll_constants()

        # Sample rate tracked as instance state. config.SAMPLE_RATE is only the
        # pre-connect default used for initial buffer sizing; set_sample_rate
        # is called once the LSL stream reports its actual nominal rate.
        self.sample_rate = float(config.SAMPLE_RATE)

        # Alert ring buffer.
        self.alert_history_size = int(config.ALERT_HISTORY_SECONDS * self.sample_rate)
        self.alert_history = None  # (N_PHYSICAL, alert_history_size)
        self.alert_ptr = 0

        # Channel mapping is materialized on first sample.
        self.sample_width: Optional[int] = None
        self.od_indices = None

        # Baseline state.
        self.baseline_mode: str = getattr(config, "BASELINE_MODE", "single_sample")
        self.baseline_window_samples = max(
            1, int(getattr(config, "BASELINE_WINDOW_S", 10) * self.sample_rate)
        )
        self.baseline_od: Optional[np.ndarray] = None
        # When in "window" mode, mapped OD samples accumulate here until the
        # buffer reaches baseline_window_samples; the mean becomes the baseline.
        self._baseline_buffer: Optional[list] = None

        # Rolling history of recent mapped OD samples. Drives the manual
        # "Set Baseline" action (Phase 6 button); recompute_baseline_from_window
        # takes the mean of whatever is in here.
        self._od_history: deque = deque(maxlen=self.baseline_window_samples)

        # Bandpass filter applied to post-MBLL O2Hb/HHb (16 traces).
        # Filtered values feed display + alerts; raw post-MBLL values are also
        # exposed so the recorder can keep an unfiltered audit trail.
        self.filter: Optional[BandpassFilter] = None
        self._init_filter()

    # ---------- Lifecycle ----------

    def reset(self):
        # Clears per-session state. Called on every fresh stream connect.
        self.alert_history = None
        self.alert_ptr = 0
        self.od_indices = None
        self.sample_width = None
        self.baseline_od = None
        self._baseline_buffer = None
        self._od_history.clear()
        if self.filter is not None:
            self.filter.reset()

    def set_sample_rate(self, hz: float):
        # Updates internal sample-rate-dependent buffer sizes and rebuilds
        # the filter for the new rate.
        hz = float(hz) if hz and hz > 0 else None
        if hz is None:
            return

        self.sample_rate = hz
        self.alert_history_size = int(config.ALERT_HISTORY_SECONDS * hz)
        self.baseline_window_samples = max(
            1, int(getattr(config, "BASELINE_WINDOW_S", 10) * hz)
        )

        # Resize the OD history without discarding what we already collected.
        old_items = list(self._od_history)
        self._od_history = deque(old_items, maxlen=self.baseline_window_samples)

        # Force alert ring re-alloc on next sample.
        self.alert_history = None
        self.sample_width = None

        # Rebuild filter at the new rate. Resets channel state implicitly.
        if self.filter is not None:
            self.filter.set_sample_rate(hz)

    def rebuild_filter(self) -> None:
        # Re-reads config.FILTER_* and instantiates a fresh filter. Phase 6
        # calls this after the Settings dialog saves new filter parameters.
        self._init_filter()

    def set_baseline_mode(self, mode: str) -> None:
        # Switches between "single_sample" and "window" baseline establishment.
        # Discards any in-flight baseline accumulation; the next sample re-starts
        # baseline establishment under the new mode.
        if mode not in ("single_sample", "window"):
            raise ValueError(f"unknown baseline mode {mode!r}")
        self.baseline_mode = mode
        self.baseline_od = None
        self._baseline_buffer = None

    def recompute_baseline_from_window(self) -> bool:
        # Sets the baseline to the mean of the rolling OD history (whatever
        # is currently buffered, up to BASELINE_WINDOW_S of samples).
        # Returns True on success. Phase 6 wires the "Set Baseline" button
        # to this; analysts press it after the subject is settled.
        if len(self._od_history) == 0:
            return False
        stacked = np.stack(list(self._od_history), axis=0)
        self.baseline_od = np.mean(stacked, axis=0)
        if self.filter is not None:
            self.filter.reset()
        return True

    # ---------- Channel mapping ----------

    def _init_od_indices(self):
        # 8 channels x 2 wavelengths mapped from the OxySoft 32-OD vector.
        # OctaMon convention: Rx1 sees light sources L1..L8 (active half),
        # Rx2 sees L9..L16. Within a Tx pair, odd index = 850 nm, even = 760 nm.
        def rx1(l): return (l - 1)
        def rx2(l): return 16 + (l - 1)

        self.od_indices = [
            (rx1(1), rx1(2)),
            (rx1(3), rx1(4)),
            (rx1(5), rx1(6)),
            (rx1(7), rx1(8)),
            (rx2(9), rx2(10)),
            (rx2(11), rx2(12)),
            (rx2(13), rx2(14)),
            (rx2(15), rx2(16)),
        ]

    def _map_od_to_8ch(self, od_vec):
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
        ext = np.array(
            [
                [e_wl1["O2Hb"], e_wl1["HHb"]],
                [e_wl2["O2Hb"], e_wl2["HHb"]],
            ],
            dtype=float,
        )
        self.inverse_extinction_matrix = np.linalg.inv(ext)

    def calculate_hemoglobin(self, delta_od):
        # Converts deltaOD (per channel, 2 wavelengths) into deltaHb (uM).
        # Mapping convention: delta_od is laid out as [Ch0_850, Ch0_760, Ch1_850, ...].
        # OD is unitless (log10 of intensity ratio). MBLL: deltaC = inv(eps) * deltaOD / (DPF * L).
        delta_od = np.asarray(delta_od, dtype=float)
        n = delta_od.size // 2
        reshaped = delta_od.reshape(n, 2)              # cols [850, 760]
        od_760_850 = reshaped[:, [1, 0]].T             # rows [760, 850]
        delta_c = (self.inverse_extinction_matrix @ od_760_850) / (
            config.DPF * config.INTEROPTODE_DISTANCE
        )
        delta_c = delta_c * 1000.0  # mM -> uM
        return {"O2Hb": delta_c[0, :], "HHb": delta_c[1, :]}

    # ---------- Filter ----------

    def _init_filter(self) -> None:
        try:
            self.filter = BandpassFilter(
                num_channels=_N_FILTERED,
                sample_rate=self.sample_rate,
                low_hz=float(getattr(config, "FILTER_HIGHPASS_HZ", 0.01)),
                high_hz=float(getattr(config, "FILTER_LOWPASS_HZ", 0.5)),
                order=int(getattr(config, "FILTER_ORDER", 4)),
            )
        except Exception as ex:
            print(f"DataProcessor: filter init failed ({ex}); running unfiltered.")
            self.filter = None

    # ---------- Alert ring buffer ----------

    def _ensure_buffers(self, mapped_len: int):
        phys = mapped_len // 2
        if (
            self.sample_width == mapped_len
            and self.alert_history is not None
            and self.alert_history.shape == (phys, self.alert_history_size)
        ):
            return
        self.sample_width = mapped_len
        self.alert_history = np.full((phys, self.alert_history_size), False, dtype=bool)
        self.alert_ptr = 0

    def check_for_alert(self, o2hb_values, threshold, duration_s, min_channels=2):
        is_above = np.asarray(o2hb_values) > threshold

        self.alert_history[:, self.alert_ptr] = is_above
        self.alert_ptr = (self.alert_ptr + 1) % self.alert_history.shape[1]

        need = int(duration_s * self.sample_rate)
        need = max(1, min(need, self.alert_history.shape[1]))

        end = self.alert_ptr
        idx = (np.arange(end - need, end) % self.alert_history.shape[1])
        recent = self.alert_history[:, idx]
        sustained = np.all(recent, axis=1)
        return CognitiveState.LOAD if (np.sum(sustained) >= min_channels) else CognitiveState.NOMINAL

    # ---------- Signal quality ----------

    def _calculate_signal_quality(self, adc_value=None, mapped_od=None):
        # Phase 5 will replace this with std/CV/heartbeat detection.
        if adc_value is not None:
            if adc_value >= config.PLACEHOLDER_HI - config.PLACEHOLDER_EPS:
                return ["red"] * config.EXPECTED_PHYSICAL_CHANNELS
            return ["green"] * config.EXPECTED_PHYSICAL_CHANNELS

        if mapped_od is None:
            return ["red"] * config.EXPECTED_PHYSICAL_CHANNELS

        states = []
        for i in range(mapped_od.size // 2):
            w1 = mapped_od[i * 2]
            w2 = mapped_od[i * 2 + 1]
            states.append("green" if (np.isfinite(w1) and np.isfinite(w2)) else "red")
        return states

    # ---------- Main entry point ----------

    def process_sample_od(self, lsl_sample, alert_rules):
        # Returns a dict with both filtered (O2Hb/HHb, used by UI + alerts)
        # and raw post-MBLL values (O2Hb_raw/HHb_raw, recorded to disk).
        # Returns None if the sample is purely OxySoft's placeholder code.
        vec = np.asarray(lsl_sample, dtype=float)

        adc_value = None
        if vec.size == 32:
            od_vec = vec
        elif vec.size == 33:
            od_vec = vec[:32]
            adc_value = vec[32]
        elif vec.size >= 34:
            od_vec = vec[:32]
            adc_value = vec[32]
        else:
            raise ValueError(f"Expected at least 32 OD values. Got {vec.size}")

        # Placeholder-only sample (typical at stream start; OxySoft emits
        # 4.81625 = log10(2^16-1) on every channel before real data flows).
        if np.allclose(od_vec, config.PLACEHOLDER_HI, atol=config.PLACEHOLDER_EPS):
            return None

        mapped_od = self._map_od_to_8ch(od_vec)
        self._ensure_buffers(mapped_od.size)

        # Roll the OD history for the manual "Set Baseline" action.
        self._od_history.append(mapped_od.copy())

        # Baseline establishment.
        if self.baseline_od is None:
            if self.baseline_mode == "window":
                warmup_state = self._accumulate_window_baseline(mapped_od)
                if warmup_state is not None:
                    return warmup_state
                # Baseline just established this sample; fall through and emit
                # a real (delta=0) row so plots start moving immediately.
            else:
                # single_sample mode: first valid sample is the baseline.
                self.baseline_od = mapped_od.copy()

        delta_od = mapped_od - self.baseline_od

        # MBLL.
        raw_hb = self.calculate_hemoglobin(delta_od)
        o2hb_raw = np.asarray(raw_hb["O2Hb"], dtype=float)
        hhb_raw = np.asarray(raw_hb["HHb"], dtype=float)

        # Filter (single pass over 16 stacked channels: 8 O2 + 8 HHb).
        if self.filter is not None:
            combined = np.concatenate([o2hb_raw, hhb_raw])
            combined_filt = self.filter.process(combined)
            o2hb_filt = combined_filt[:8]
            hhb_filt = combined_filt[8:]
        else:
            o2hb_filt = o2hb_raw
            hhb_filt = hhb_raw

        quality = self._calculate_signal_quality(adc_value=adc_value, mapped_od=mapped_od)

        thresh = alert_rules.get("threshold", 4.0)
        dur = alert_rules.get("duration", 3)
        alert_state = self.check_for_alert(o2hb_filt, thresh, dur)

        return {
            "O2Hb": o2hb_filt.tolist(),
            "HHb": hhb_filt.tolist(),
            "O2Hb_raw": o2hb_raw.tolist(),
            "HHb_raw": hhb_raw.tolist(),
            "quality": quality,
            "alert_state": alert_state,
        }

    def _accumulate_window_baseline(self, mapped_od: np.ndarray):
        # Called while in "window" mode and before baseline is established.
        # Buffers samples until we have enough, then sets the baseline as the
        # mean. Returns a WARMING_UP processed dict while still accumulating,
        # or None once the baseline has been established.
        if self._baseline_buffer is None:
            self._baseline_buffer = []
        self._baseline_buffer.append(mapped_od.copy())

        if len(self._baseline_buffer) < self.baseline_window_samples:
            return {
                "O2Hb": [0.0] * 8,
                "HHb": [0.0] * 8,
                "O2Hb_raw": None,
                "HHb_raw": None,
                "quality": ["red"] * config.EXPECTED_PHYSICAL_CHANNELS,
                "alert_state": CognitiveState.WARMING_UP,
            }

        # Buffer full: establish baseline and clear the buffer.
        stacked = np.stack(self._baseline_buffer, axis=0)
        self.baseline_od = np.mean(stacked, axis=0)
        self._baseline_buffer = None
        if self.filter is not None:
            self.filter.reset()
        return None
