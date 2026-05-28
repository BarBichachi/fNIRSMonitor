import numpy as np
import pytest

from logic.signal_filter import BandpassFilter


@pytest.fixture
def filt():
    return BandpassFilter(num_channels=2, sample_rate=50.0, low_hz=0.01, high_hz=0.5, order=4)


def _drive(filt: BandpassFilter, signal: np.ndarray) -> np.ndarray:
    # signal shape (n_samples, num_channels). Returns same shape after sample-by-sample filtering.
    n = signal.shape[0]
    out = np.empty_like(signal)
    for i in range(n):
        out[i] = filt.process(signal[i])
    return out


def test_dc_offset_is_attenuated_by_highpass(filt):
    # Steady-state highpass response to a step input should approach 0 after
    # settling. The 0.01 Hz highpass has time constant ~16 s, so we drive for
    # 200 s (>10 tau) and check the final tail. The settling is exponential.
    n = int(200 * 50)
    signal = np.ones((n, 2), dtype=float) * 5.0
    out = _drive(filt, signal)
    tail = out[-int(5 * 50):]
    # 5.0 input -> after ~12 tau, residual should be < 0.5% of input.
    assert np.max(np.abs(tail)) < 0.05 * 5.0, (
        f"DC not removed after 200 s: max tail = {np.max(np.abs(tail))}"
    )


def test_in_band_signal_is_preserved(filt):
    # A 0.1 Hz sine should pass through with magnitude close to input amplitude.
    fs = 50.0
    f = 0.1
    n = int(120 * fs)  # 120 s = many cycles of 0.1 Hz
    t = np.arange(n) / fs
    amp = 1.0
    sig = amp * np.sin(2 * np.pi * f * t)
    signal = np.column_stack([sig, sig])
    out = _drive(filt, signal)
    # Skip startup transient.
    settled = out[int(40 * fs):]
    peak_ratio = float(np.max(np.abs(settled))) / amp
    assert 0.6 < peak_ratio < 1.4, f"In-band amplitude wrong: ratio = {peak_ratio}"


def test_high_freq_signal_is_attenuated(filt):
    # A 5 Hz sine is 10x the lowpass corner; once the long highpass-driven
    # transient has decayed (>10 tau = >160 s), output amplitude should be
    # heavily attenuated.
    fs = 50.0
    f = 5.0
    n = int(200 * fs)
    t = np.arange(n) / fs
    amp = 1.0
    sig = amp * np.sin(2 * np.pi * f * t)
    signal = np.column_stack([sig, sig])
    out = _drive(filt, signal)
    settled = out[int(180 * fs):]
    peak_ratio = float(np.max(np.abs(settled))) / amp
    assert peak_ratio < 0.05, f"High-freq not attenuated: ratio = {peak_ratio}"


def test_reset_clears_channel_state(filt):
    # Drive with a step, reset, drive with zero input. Zero-state init means
    # zero input + zero state = exactly zero output, every sample.
    n = int(30 * 50)
    sig = np.ones((n, 2)) * 10.0
    _drive(filt, sig)
    filt.reset()
    out = _drive(filt, np.zeros((int(5 * 50), 2)))
    assert np.max(np.abs(out)) < 1e-12, f"Reset failed: max = {np.max(np.abs(out))}"


def test_set_sample_rate_rebuilds_filter(filt):
    filt.set_sample_rate(100.0)
    assert filt.sample_rate == 100.0
    # Effective band should be the requested band (Nyquist 50, lowpass 0.5 << 50).
    low, high = filt.effective_band
    assert abs(low - 0.01) < 1e-6
    assert abs(high - 0.5) < 1e-6


def test_low_sample_rate_clamps_lowpass():
    # fs=1.5 Hz means Nyquist=0.75 Hz. Lowpass at 0.5 should clamp to 0.4*Nyquist = 0.3.
    filt = BandpassFilter(num_channels=1, sample_rate=1.5, low_hz=0.01, high_hz=0.5, order=4)
    low, high = filt.effective_band
    assert abs(high - 0.3) < 1e-6, f"Expected high clamped to 0.3, got {high}"


def test_degenerate_band_becomes_passthrough():
    # high < low after clamping should result in passthrough.
    filt = BandpassFilter(num_channels=1, sample_rate=2.0, low_hz=1.0, high_hz=0.5, order=4)
    assert filt.is_passthrough
    inp = np.array([42.0])
    out = filt.process(inp)
    assert out[0] == 42.0


def test_input_shape_validation(filt):
    with pytest.raises(ValueError):
        filt.process(np.array([1.0]))  # wrong shape, expected 2-channel
