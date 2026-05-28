import logging
from typing import Optional

import numpy as np
from scipy.signal import butter, sosfilt


logger = logging.getLogger(__name__)


class BandpassFilter:
    # Per-channel causal Butterworth bandpass for live streaming. One filter
    # bank covers N channels; each channel keeps its own SOS state so the
    # streams stay independent. Calling process() once per arriving sample
    # advances every channel by one sample.
    #
    # When the sample rate is too low for the requested high cutoff (less than
    # 2.5x the cutoff), the cutoff is clamped to 0.4 * Nyquist and a warning is
    # printed. When the requested band is degenerate, the filter becomes a
    # pass-through.

    def __init__(
        self,
        num_channels: int,
        sample_rate: float,
        low_hz: float,
        high_hz: float,
        order: int = 4,
    ):
        if num_channels < 1:
            raise ValueError(f"num_channels must be >= 1, got {num_channels}")
        self.num_channels = num_channels
        self.low_hz = float(low_hz)
        self.high_hz = float(high_hz)
        self.order = int(order)

        self._sample_rate: Optional[float] = None
        self._sos: Optional[np.ndarray] = None
        # Per-channel SOS filter state: shape (num_channels, n_sections, 2).
        self._zi: Optional[np.ndarray] = None
        # Set of (low, high) effectively in use after Nyquist clamping.
        self._effective_band = (0.0, 0.0)

        self.set_sample_rate(sample_rate)

    @property
    def sample_rate(self) -> Optional[float]:
        return self._sample_rate

    @property
    def effective_band(self) -> tuple:
        return self._effective_band

    @property
    def is_passthrough(self) -> bool:
        return self._sos is None

    def set_sample_rate(self, sample_rate: float) -> None:
        # Rebuilds filter coefficients and resets channel state. Call this
        # whenever the data stream's nominal sample rate changes.
        if sample_rate is None or sample_rate <= 0:
            raise ValueError(f"sample_rate must be positive, got {sample_rate}")
        self._sample_rate = float(sample_rate)
        self._rebuild()

    def reset(self) -> None:
        # Resets per-channel SOS state to all zeros. Zero-state init is the
        # right default for fNIRS because the input stream starts at exactly
        # zero (the very first delta_Hb is 0 by construction), so zero state +
        # zero input produces zero output and no spurious startup transient.
        # A baseline change in the upstream pipeline is also a return-to-zero
        # event, so the same init is correct after rebaseline.
        if self._sos is None:
            self._zi = None
            return
        n_sections = self._sos.shape[0]
        self._zi = np.zeros((self.num_channels, n_sections, 2), dtype=float)

    def process(self, samples: np.ndarray) -> np.ndarray:
        # samples: shape (num_channels,). Returns filtered samples, same shape.
        samples = np.asarray(samples, dtype=float)
        if samples.shape != (self.num_channels,):
            raise ValueError(
                f"expected shape ({self.num_channels},), got {samples.shape}"
            )
        if self._sos is None or self._zi is None:
            return samples.copy()

        out = np.empty(self.num_channels, dtype=float)
        for i in range(self.num_channels):
            x = samples[i : i + 1]  # 1-element view, avoids re-allocation
            y, self._zi[i] = sosfilt(self._sos, x, zi=self._zi[i])
            out[i] = y[0]
        return out

    def _rebuild(self) -> None:
        fs = self._sample_rate
        nyquist = fs / 2.0
        # Leave 20% headroom under Nyquist for the lowpass edge.
        max_high = 0.4 * nyquist
        high = min(self.high_hz, max_high)
        low = max(self.low_hz, 1e-4)

        if high <= low or high <= 0:
            logger.warning(
                "Degenerate band (low=%s, high=%s, fs=%s); running as pass-through.",
                low, high, fs,
            )
            self._sos = None
            self._zi = None
            self._effective_band = (0.0, 0.0)
            return

        if high < self.high_hz:
            logger.warning(
                "Lowpass clamped from %s Hz to %.4f Hz (fs=%s Hz, Nyquist=%s Hz).",
                self.high_hz, high, fs, nyquist,
            )

        sos = butter(self.order, [low, high], btype="band", fs=fs, output="sos")
        self._sos = sos
        # Zero-state initial conditions: see reset() docstring for rationale.
        n_sections = sos.shape[0]
        self._zi = np.zeros((self.num_channels, n_sections, 2), dtype=float)
        self._effective_band = (low, high)
