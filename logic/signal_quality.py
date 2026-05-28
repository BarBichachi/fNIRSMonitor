from typing import List

import numpy as np


class SignalQualityEvaluator:
    # Per-channel signal quality from a rolling window of single-wavelength OD.
    # Three independent criteria are evaluated; the channel's status is the
    # count: 3/3 = green, 2/3 = yellow, <=1 = red.
    #
    # 1) std > std_threshold
    #    Flat-lined channels (broken cable, saturated detector) have near-zero
    #    variance over a 5 s window. Anything below the threshold is suspect.
    #
    # 2) coefficient of variation < cv_threshold
    #    Real fNIRS OD sits in a narrow band relative to its mean. CV that
    #    explodes (>5% of mean for OD ~ 1.0) means the channel is unstable or
    #    crawling away from its operating point.
    #
    # 3) heartbeat present in 0.8-2.0 Hz band
    #    A well-coupled optode picks up cardiac pulsation. An FFT peak in the
    #    HR band that exceeds the noise floor (median spectrum in 2.5-5.0 Hz)
    #    by at least hr_snr_threshold confirms skin contact. The FFT is
    #    expensive, so it's recomputed only every hr_recompute_s seconds and
    #    the result is cached between recomputations.

    def __init__(
        self,
        num_channels: int,
        sample_rate: float,
        window_s: float = 5.0,
        hr_recompute_s: float = 1.0,
        std_threshold: float = 0.005,
        cv_threshold: float = 0.05,
        hr_snr_threshold: float = 3.0,
    ):
        self.num_channels = int(num_channels)
        self.sample_rate = float(sample_rate)
        self.window_s = float(window_s)
        self.hr_recompute_s = float(hr_recompute_s)

        self.std_threshold = float(std_threshold)
        self.cv_threshold = float(cv_threshold)
        self.hr_snr_threshold = float(hr_snr_threshold)

        self._allocate_buffers()

    # ---------- Public ----------

    def set_sample_rate(self, hz: float) -> None:
        self.sample_rate = float(hz)
        self._allocate_buffers()

    def reset(self) -> None:
        self._allocate_buffers()

    def update(self, od_per_channel: np.ndarray) -> List[str]:
        # od_per_channel: shape (num_channels,) - single-wavelength OD per channel.
        # Advances the rolling buffer, recomputes HR if due, returns the
        # per-channel state list.
        od_per_channel = np.asarray(od_per_channel, dtype=float)
        if od_per_channel.shape != (self.num_channels,):
            raise ValueError(
                f"expected shape ({self.num_channels},), got {od_per_channel.shape}"
            )

        self._od_buffer[:, self._ptr] = od_per_channel
        self._ptr = (self._ptr + 1) % self._window_samples
        if self._ptr == 0:
            self._filled = True

        if not self._filled:
            return ["red"] * self.num_channels

        std_vec = np.std(self._od_buffer, axis=1)
        mean_vec = np.mean(self._od_buffer, axis=1)
        # Avoid divide-by-zero when a channel sits at exactly 0; treat as
        # CV=infinity in that case so the CV criterion fails (channel is red).
        denom = np.where(np.abs(mean_vec) > 1e-9, np.abs(mean_vec), np.nan)
        with np.errstate(invalid="ignore", divide="ignore"):
            cv_vec = std_vec / denom

        std_ok = std_vec > self.std_threshold
        cv_ok = np.isfinite(cv_vec) & (cv_vec < self.cv_threshold)

        # Recompute heartbeat presence periodically; cache otherwise.
        self._samples_since_hr += 1
        if self._samples_since_hr >= self._recompute_interval_samples:
            self._samples_since_hr = 0
            self._heartbeat_good = self._compute_heartbeat()

        scores = std_ok.astype(int) + cv_ok.astype(int) + self._heartbeat_good.astype(int)

        states: List[str] = []
        for s in scores:
            if s >= 3:
                states.append("green")
            elif s == 2:
                states.append("yellow")
            else:
                states.append("red")
        return states

    # ---------- Internal ----------

    def _allocate_buffers(self) -> None:
        self._window_samples = max(2, int(self.window_s * self.sample_rate))
        self._recompute_interval_samples = max(1, int(self.hr_recompute_s * self.sample_rate))

        self._od_buffer = np.zeros((self.num_channels, self._window_samples), dtype=float)
        self._ptr = 0
        self._filled = False
        self._heartbeat_good = np.zeros(self.num_channels, dtype=bool)
        self._samples_since_hr = 0

    def _compute_heartbeat(self) -> np.ndarray:
        fs = self.sample_rate
        n = self._window_samples

        # Detrend per-channel so the DC bin doesn't dominate.
        signal = self._od_buffer - np.mean(self._od_buffer, axis=1, keepdims=True)

        spec = np.abs(np.fft.rfft(signal, axis=1))
        freqs = np.fft.rfftfreq(n, d=1.0 / fs)

        hr_mask = (freqs >= 0.8) & (freqs <= 2.0)
        noise_mask = (freqs >= 2.5) & (freqs <= 5.0)

        good = np.zeros(self.num_channels, dtype=bool)
        if not np.any(hr_mask) or not np.any(noise_mask):
            # Window too short / sample rate too low to resolve the HR band.
            return good

        peak_per_ch = np.max(spec[:, hr_mask], axis=1)
        noise_per_ch = np.median(spec[:, noise_mask], axis=1)

        with np.errstate(invalid="ignore", divide="ignore"):
            snr = peak_per_ch / np.where(noise_per_ch > 0, noise_per_ch, np.nan)
        good = np.isfinite(snr) & (snr > self.hr_snr_threshold)
        return good
