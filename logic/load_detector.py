from collections import deque
from typing import Optional

import numpy as np

from utils.enums import CognitiveState


# OctaMon channel layout convention used everywhere in this app.
# Channels 0..3 are left-hemisphere PFC (L1..L4); 4..7 are right (R1..R4).
LEFT_INDICES = (0, 1, 2, 3)
RIGHT_INDICES = (4, 5, 6, 7)


class LoadDetector:
    # Pluggable interface. The DataProcessor delegates per-sample state
    # decisions to whatever implementation is installed; future detectors
    # (trained on labeled cognitive-task data) can swap in by implementing
    # the same surface.

    def update(
        self,
        o2hb: np.ndarray,
        hhb: np.ndarray,
        quality: list,
    ) -> CognitiveState:
        raise NotImplementedError

    def start_calibration(self) -> None:
        raise NotImplementedError

    def reset(self) -> None:
        raise NotImplementedError

    def set_sample_rate(self, hz: float) -> None:
        raise NotImplementedError

    @property
    def is_calibrating(self) -> bool:
        raise NotImplementedError

    @property
    def is_calibrated(self) -> bool:
        raise NotImplementedError

    @property
    def calibration_progress(self) -> float:
        # 0.0 to 1.0 during calibration; undefined otherwise.
        raise NotImplementedError

    @property
    def baseline_summary(self) -> Optional[dict]:
        # After calibration: per-channel baseline mean and SD, plus asymmetry
        # baseline. None before calibration.
        raise NotImplementedError


class ThresholdAsymmetryDetector(LoadDetector):
    # Phase A algorithm (per remediation plan):
    # - Acquire per-subject baseline: subject sits quietly for `rest_window_s`.
    #   We collect O2Hb and HHb stats, plus the asymmetry-index distribution.
    # - During monitoring, over the last `active_window_s` of post-filter data,
    #   compute per-channel current mean O2Hb / HHb.
    # - A channel is "elevated" iff
    #       curr_O2Hb_i > baseline_mean_i + k_sd * baseline_std_i
    #       AND
    #       curr_HHb_i <= baseline_HHb_mean_i + hhb_tol_um
    #       AND quality[i] is good.
    #   The HHb sanity gate distinguishes neural activation (O2Hb up, HHb flat
    #   or down) from systemic / motion artifacts (both go up together).
    # - Right-hemisphere PFC bias: load is signaled when at least
    #   `min_elevated_channels` of the 4 right channels are elevated, OR when
    #   the running right-minus-left asymmetry exceeds its own k_sd ceiling.

    def __init__(
        self,
        sample_rate: float,
        rest_window_s: float = 60.0,
        active_window_s: float = 30.0,
        k_sd: float = 1.5,
        min_elevated_channels: int = 2,
        hhb_tol_um: float = 0.5,
    ):
        self.sample_rate = float(sample_rate)
        self.rest_window_s = float(rest_window_s)
        self.active_window_s = float(active_window_s)
        self.k_sd = float(k_sd)
        self.min_elevated_channels = int(min_elevated_channels)
        self.hhb_tol_um = float(hhb_tol_um)

        # Calibration state.
        self._calibrating: bool = False
        self._cal_o2: list = []
        self._cal_hhb: list = []

        # Baseline summary (set after calibration finishes).
        self._baseline_mean: Optional[np.ndarray] = None  # shape (8,)
        self._baseline_std: Optional[np.ndarray] = None
        self._baseline_hhb_mean: Optional[np.ndarray] = None
        self._baseline_asymmetry_mean: float = 0.0
        self._baseline_asymmetry_std: float = 0.0

        # Active sliding windows for current state evaluation.
        self._active_n = max(1, int(self.active_window_s * self.sample_rate))
        self._active_o2: deque = deque(maxlen=self._active_n)
        self._active_hhb: deque = deque(maxlen=self._active_n)

    # ---------- Interface ----------

    @property
    def is_calibrating(self) -> bool:
        return self._calibrating

    @property
    def is_calibrated(self) -> bool:
        return self._baseline_mean is not None

    @property
    def calibration_progress(self) -> float:
        # Monotonic across one calibration cycle: rises from 0 to 1 while the
        # buffer fills, stays at 1.0 once calibration has finalized (so the UI
        # does not "fall back" to 0 the instant calibration completes), and
        # returns to 0 only after reset() / a fresh start_calibration() call.
        if self._calibrating:
            needed = max(1, int(self.rest_window_s * self.sample_rate))
            return min(1.0, len(self._cal_o2) / needed)
        if self.is_calibrated:
            return 1.0
        return 0.0

    @property
    def baseline_summary(self) -> Optional[dict]:
        if not self.is_calibrated:
            return None
        return {
            "mean_o2hb": self._baseline_mean.tolist(),
            "std_o2hb": self._baseline_std.tolist(),
            "mean_hhb": self._baseline_hhb_mean.tolist(),
            "asymmetry_mean": self._baseline_asymmetry_mean,
            "asymmetry_std": self._baseline_asymmetry_std,
            "rest_window_s": self.rest_window_s,
            "k_sd": self.k_sd,
        }

    def start_calibration(self) -> None:
        # Begin collecting a fresh baseline. Existing baseline stats are
        # cleared so the UI's progress indicator drops to 0 immediately and
        # the detector is honestly "uncalibrated" while recalibration runs.
        self._calibrating = True
        self._cal_o2 = []
        self._cal_hhb = []
        self._baseline_mean = None
        self._baseline_std = None
        self._baseline_hhb_mean = None
        self._baseline_asymmetry_mean = 0.0
        self._baseline_asymmetry_std = 0.0
        self._active_o2.clear()
        self._active_hhb.clear()

    def reset(self) -> None:
        self._calibrating = False
        self._cal_o2 = []
        self._cal_hhb = []
        self._baseline_mean = None
        self._baseline_std = None
        self._baseline_hhb_mean = None
        self._baseline_asymmetry_mean = 0.0
        self._baseline_asymmetry_std = 0.0
        self._active_o2.clear()
        self._active_hhb.clear()

    def set_sample_rate(self, hz: float) -> None:
        self.sample_rate = float(hz)
        new_n = max(1, int(self.active_window_s * self.sample_rate))
        # Preserve whatever has accumulated so far; truncate/pad maxlen.
        old_o2 = list(self._active_o2)
        old_hhb = list(self._active_hhb)
        self._active_n = new_n
        self._active_o2 = deque(old_o2, maxlen=new_n)
        self._active_hhb = deque(old_hhb, maxlen=new_n)

    def update(
        self,
        o2hb: np.ndarray,
        hhb: np.ndarray,
        quality: list,
    ) -> CognitiveState:
        o2hb = np.asarray(o2hb, dtype=float)
        hhb = np.asarray(hhb, dtype=float)

        # Calibration accumulation runs to the exclusion of active evaluation.
        if self._calibrating:
            self._cal_o2.append(o2hb)
            self._cal_hhb.append(hhb)
            needed = max(1, int(self.rest_window_s * self.sample_rate))
            if len(self._cal_o2) >= needed:
                self._finalize_calibration()
            return CognitiveState.CALIBRATING

        # Without a baseline, we have no basis to flag load. Stay nominal.
        if not self.is_calibrated:
            return CognitiveState.NOMINAL

        # Roll active window.
        self._active_o2.append(o2hb)
        self._active_hhb.append(hhb)

        # Need a full active window before evaluating.
        if len(self._active_o2) < self._active_n:
            return CognitiveState.NOMINAL

        curr_o2 = np.mean(np.stack(self._active_o2), axis=0)
        curr_hhb = np.mean(np.stack(self._active_hhb), axis=0)

        good = self._quality_mask(quality)

        # Per-channel elevation with HHb sanity gate and quality gate.
        elevation_threshold = self._baseline_mean + self.k_sd * self._baseline_std
        hhb_ok = curr_hhb <= (self._baseline_hhb_mean + self.hhb_tol_um)
        per_channel_elevated = (
            (curr_o2 > elevation_threshold) & hhb_ok & good
        )

        right_elevated = int(np.sum(per_channel_elevated[list(RIGHT_INDICES)]))

        # Asymmetry: right PFC minus left PFC mean O2Hb over the active window.
        curr_asym = float(
            np.mean(curr_o2[list(RIGHT_INDICES)])
            - np.mean(curr_o2[list(LEFT_INDICES)])
        )
        asym_threshold = (
            self._baseline_asymmetry_mean + self.k_sd * self._baseline_asymmetry_std
        )
        elevated_asymmetry = curr_asym > asym_threshold

        if right_elevated >= self.min_elevated_channels or elevated_asymmetry:
            return CognitiveState.LOAD
        return CognitiveState.NOMINAL

    # ---------- Internal ----------

    def _finalize_calibration(self) -> None:
        stacked_o2 = np.stack(self._cal_o2, axis=0)        # (N, 8)
        stacked_hhb = np.stack(self._cal_hhb, axis=0)      # (N, 8)
        self._baseline_mean = np.mean(stacked_o2, axis=0)
        # ddof=1 (sample SD). For a 60s @ 50Hz window we have 3000 samples,
        # the population/sample distinction is numerically negligible, but
        # ddof=1 matches what most stats packages do.
        self._baseline_std = np.std(stacked_o2, axis=0, ddof=1)
        # Floor SD to avoid divide-by-near-zero or vanishing thresholds when
        # a channel happens to be perfectly steady in the rest window.
        self._baseline_std = np.maximum(self._baseline_std, 1e-3)
        self._baseline_hhb_mean = np.mean(stacked_hhb, axis=0)

        asym_series = (
            np.mean(stacked_o2[:, list(RIGHT_INDICES)], axis=1)
            - np.mean(stacked_o2[:, list(LEFT_INDICES)], axis=1)
        )
        self._baseline_asymmetry_mean = float(np.mean(asym_series))
        self._baseline_asymmetry_std = float(np.maximum(np.std(asym_series, ddof=1), 1e-3))

        self._calibrating = False
        self._cal_o2 = []
        self._cal_hhb = []

        # Active windows accumulated during calibration are stale relative to
        # the just-frozen baseline; drop them so the first decision is made
        # against a freshly-collected active window.
        self._active_o2.clear()
        self._active_hhb.clear()

    @staticmethod
    def _quality_mask(quality: list) -> np.ndarray:
        # Translate the per-channel quality strings to a green=True mask.
        # If quality info is missing, fall through with all-True (trust all
        # channels) rather than refuse to ever fire.
        if not quality:
            return np.ones(8, dtype=bool)
        flags = [str(q).lower() == "green" for q in quality[:8]]
        if len(flags) < 8:
            flags.extend([True] * (8 - len(flags)))
        return np.array(flags, dtype=bool)
